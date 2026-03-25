"""
quiz_engine.py

Quiz logic for the Astronomy Trainer application.

Responsibilities:
- Load stars and deep-sky objects
- Generate questions from one or both catalogs
- Check answers
- Track score
- Provide clean target data back to the UI
- Spaced repetition for missed objects
- Avoid repeating recent questions

Supported quiz modes:
- name_to_star: find a named star
- coords_to_star: find a star by coordinates
- name_to_deep_sky: find a named deep-sky object
- coords_to_deep_sky: find a deep-sky object by coordinates
- name_to_object: find any named object
- coords_to_object: find any object by coordinates
- alias_to_object: find an object by one of its aliases
- constellation_find: find any object in a named constellation
"""

from __future__ import annotations

import random
from collections import deque
from typing import Any, Dict, List, Optional, Set

try:
    from catalog_loader import (
        load_all_catalog_objects,
        load_deep_sky_catalog,
        load_star_catalog,
    )
except ImportError:
    load_star_catalog = None
    load_deep_sky_catalog = None
    load_all_catalog_objects = None

from coordinates import format_ra, format_dec
from object_matcher import angular_match, build_match_result, exact_id_match

CatalogObject = Dict[str, Any]
QuestionObject = Dict[str, Any]
ResultObject = Dict[str, Any]


# How many recent object IDs to remember for deduplication.
RECENT_HISTORY_SIZE = 12

# Probability of pulling a missed object for spaced repetition
# when missed objects are available.
SPACED_REPETITION_CHANCE = 0.4


class QuizEngine:
    """
    Main quiz engine for the astronomy trainer.

    Tracks score, generates questions with variety, avoids repeats,
    and uses spaced repetition to reinforce missed objects.
    """

    def __init__(self) -> None:
        self.correct_answers: int = 0
        self.total_attempts: int = 0

        # Catalog storage
        self.star_catalog: List[CatalogObject] = []
        self.deep_sky_catalog: List[CatalogObject] = []
        self.all_objects: List[CatalogObject] = []

        # Derived pools
        self._alias_pool: List[CatalogObject] = []
        self._constellations: List[str] = []
        self._constellation_index: Dict[str, List[CatalogObject]] = {}

        # Active quiz pools
        self.include_stars: bool = True
        self.include_deep_sky: bool = True

        # Current matching tolerance for informational feedback
        self.angular_tolerance_deg: float = 1.0

        # Repeat prevention: ring buffer of recently asked object IDs
        self._recent_ids: deque = deque(maxlen=RECENT_HISTORY_SIZE)

        # Spaced repetition: track objects the user has missed
        # Maps object ID -> number of outstanding misses
        self._miss_counts: Dict[str, int] = {}

        # Last question for reference
        self.last_question: Optional[QuestionObject] = None

        self._load_catalogs()

    # ------------------------------------------------------------------
    # PUBLIC API
    # ------------------------------------------------------------------

    def generate_question(self) -> QuestionObject:
        """
        Generate a new question using the enabled catalog pools.

        Avoids recently asked objects and biases towards objects the
        user has previously answered incorrectly.

        Returns:
            dict: A question object containing prompt, mode, and target.

        Raises:
            ValueError: If no valid objects are available.
        """
        available_modes = self._get_available_modes()
        if not available_modes:
            raise ValueError("No quiz modes are available for the current catalog settings.")

        mode = random.choice(available_modes)

        # Constellation mode picks a constellation, not an object
        if mode == "constellation_find":
            question = self._generate_constellation_question()
            self.last_question = question
            return question

        pool = self._get_pool_for_mode(mode)
        if not pool:
            raise ValueError(f"No objects available for mode: {mode}")

        # Pick target with spaced repetition and deduplication
        target_object = self._pick_target(pool)

        # For alias mode, pick a specific alias to use in the prompt
        chosen_alias = None
        if mode == "alias_to_object":
            aliases = target_object.get("aliases", [])
            if aliases:
                chosen_alias = random.choice(aliases)

        prompt = self._build_prompt(
            mode=mode,
            target_object=target_object,
            chosen_alias=chosen_alias,
        )

        question: QuestionObject = {
            "mode": mode,
            "prompt": prompt,
            "target_object": target_object,
            "chosen_alias": chosen_alias,
        }

        # Record this object as recently asked
        obj_id = str(target_object.get("id", ""))
        if obj_id:
            self._recent_ids.append(obj_id)

        self.last_question = question
        return question

    def check_answer(
        self,
        question: QuestionObject,
        clicked_object: CatalogObject,
    ) -> ResultObject:
        """
        Check whether the clicked object is the correct answer.

        For most modes, this requires an exact ID match.
        For constellation_find mode, any object in the target
        constellation is accepted.

        Args:
            question: The active question object.
            clicked_object: The object clicked by the user on the star map.

        Returns:
            dict: Result data including correctness, message, and target.
        """
        target_object = question.get("target_object")
        mode = question.get("mode", "")

        if not target_object:
            return {
                "correct": False,
                "message": "This question has no target object.",
                "target_object": None,
                "clicked_object": clicked_object,
                "distance_deg": None,
            }

        self.total_attempts += 1

        # Constellation mode: any object in the constellation is correct
        if mode == "constellation_find":
            return self._check_constellation_answer(question, clicked_object)

        # Standard modes: exact ID match
        is_correct = exact_id_match(target_object, clicked_object)

        angular_result = angular_match(
            target_object=target_object,
            candidate_object=clicked_object,
            tolerance_deg=self.angular_tolerance_deg,
        )
        distance_deg = angular_result.get("distance_deg")

        result = build_match_result(
            target_object=target_object,
            clicked_object=clicked_object,
            correct=is_correct,
            distance_deg=distance_deg,
        )

        # Update spaced repetition tracking
        target_id = str(target_object.get("id", ""))
        if is_correct:
            self.correct_answers += 1
            self._record_correct(target_id)
        else:
            self._record_miss(target_id)

        return result

    def reset_score(self) -> None:
        """
        Reset score counters and spaced repetition history.
        """
        self.correct_answers = 0
        self.total_attempts = 0
        self._miss_counts.clear()
        self._recent_ids.clear()

    def set_catalog_usage(
        self,
        include_stars: bool = True,
        include_deep_sky: bool = True,
    ) -> None:
        """
        Control which object groups are included in question generation.

        Args:
            include_stars: Whether stars can be used in questions.
            include_deep_sky: Whether deep-sky objects can be used.
        """
        self.include_stars = include_stars
        self.include_deep_sky = include_deep_sky

    # ------------------------------------------------------------------
    # TARGET SELECTION
    # ------------------------------------------------------------------

    def _pick_target(self, pool: List[CatalogObject]) -> CatalogObject:
        """
        Pick a target object from a pool, avoiding recent repeats and
        biasing towards previously missed objects.

        Args:
            pool: The list of candidate objects.

        Returns:
            dict: The chosen target object.
        """
        recent_set = set(self._recent_ids)

        # Try spaced repetition: pull from missed objects
        if self._miss_counts and random.random() < SPACED_REPETITION_CHANCE:
            missed_pool = [
                obj for obj in pool
                if str(obj.get("id", "")) in self._miss_counts
                and str(obj.get("id", "")) not in recent_set
            ]
            if missed_pool:
                # Weight by miss count — objects missed more often are more likely
                weights = [
                    self._miss_counts.get(str(obj.get("id", "")), 1)
                    for obj in missed_pool
                ]
                return random.choices(missed_pool, weights=weights, k=1)[0]

        # Normal selection: avoid recent objects
        fresh_pool = [
            obj for obj in pool
            if str(obj.get("id", "")) not in recent_set
        ]

        # If everything is recent (small pool), fall back to full pool
        if not fresh_pool:
            fresh_pool = pool

        return random.choice(fresh_pool)

    def _record_miss(self, object_id: str) -> None:
        """
        Record that the user missed an object.
        """
        if not object_id:
            return
        self._miss_counts[object_id] = self._miss_counts.get(object_id, 0) + 1

    def _record_correct(self, object_id: str) -> None:
        """
        Record that the user got an object correct.
        Reduces the miss count, removing it entirely when it reaches zero.
        """
        if not object_id:
            return
        if object_id in self._miss_counts:
            self._miss_counts[object_id] -= 1
            if self._miss_counts[object_id] <= 0:
                del self._miss_counts[object_id]

    # ------------------------------------------------------------------
    # CONSTELLATION MODE
    # ------------------------------------------------------------------

    def _generate_constellation_question(self) -> QuestionObject:
        """
        Generate a 'find any object in constellation X' question.

        Picks a constellation that has at least 2 objects in the current
        pool, then picks one representative target (for map highlighting
        and distance feedback) while accepting any object in that
        constellation as correct.
        """
        pool = self._get_active_pool()

        # Build constellation options from the active pool
        const_objects: Dict[str, List[CatalogObject]] = {}
        for obj in pool:
            c = obj.get("constellation", "Unknown")
            if c and c != "Unknown":
                const_objects.setdefault(c, []).append(obj)

        # Only pick constellations with 2+ objects so there is some choice
        valid_constellations = [
            c for c, objs in const_objects.items() if len(objs) >= 2
        ]

        if not valid_constellations:
            # Fall back to any constellation
            valid_constellations = list(const_objects.keys())

        if not valid_constellations:
            raise ValueError("No constellations available for questions.")

        constellation = random.choice(valid_constellations)
        members = const_objects[constellation]

        # Pick a representative target (for highlighting), avoiding recents
        target_object = self._pick_target(members)

        prompt = f"Find any object in {constellation}."

        question: QuestionObject = {
            "mode": "constellation_find",
            "prompt": prompt,
            "target_object": target_object,
            "constellation": constellation,
        }

        obj_id = str(target_object.get("id", ""))
        if obj_id:
            self._recent_ids.append(obj_id)

        return question

    def _check_constellation_answer(
        self,
        question: QuestionObject,
        clicked_object: CatalogObject,
    ) -> ResultObject:
        """
        Check a constellation_find answer: any object in the target
        constellation is correct.
        """
        target_constellation = question.get("constellation", "")
        target_object = question.get("target_object")
        clicked_constellation = str(clicked_object.get("constellation", "")).strip()

        is_correct = (
            clicked_constellation.casefold() == target_constellation.casefold()
        )

        # Compute distance to the representative target for feedback
        distance_deg = None
        if target_object:
            angular_result = angular_match(
                target_object=target_object,
                candidate_object=clicked_object,
                tolerance_deg=self.angular_tolerance_deg,
            )
            distance_deg = angular_result.get("distance_deg")

        clicked_name = clicked_object.get("name", "Unknown")

        if is_correct:
            self.correct_answers += 1
            message = (
                f"Correct! {clicked_name} is in {target_constellation}."
            )
            if target_object:
                target_id = str(target_object.get("id", ""))
                self._record_correct(target_id)
        else:
            message = (
                f"Not quite. {clicked_name} is in {clicked_constellation}, "
                f"not {target_constellation}."
            )
            if target_object:
                target_id = str(target_object.get("id", ""))
                self._record_miss(target_id)

        return {
            "correct": is_correct,
            "target_object": target_object,
            "clicked_object": clicked_object,
            "distance_deg": distance_deg,
            "message": message,
        }

    # ------------------------------------------------------------------
    # MODE AND POOL MANAGEMENT
    # ------------------------------------------------------------------

    def _get_available_modes(self) -> List[str]:
        """
        Return quiz modes that are valid for the currently enabled pools.

        Weights modes to avoid over-representing mixed modes when both
        catalogs are active.
        """
        modes: List[str] = []

        has_stars = self.include_stars and bool(self.star_catalog)
        has_deep_sky = self.include_deep_sky and bool(self.deep_sky_catalog)

        if has_stars:
            modes.append("name_to_star")
            modes.append("coords_to_star")

        if has_deep_sky:
            modes.append("name_to_deep_sky")
            modes.append("coords_to_deep_sky")

        # Mixed modes — only add one of each to avoid dilution
        if has_stars or has_deep_sky:
            modes.append("name_to_object")
            modes.append("coords_to_object")

        # Alias mode — only if there are objects with aliases
        if self._alias_pool:
            modes.append("alias_to_object")

        # Constellation mode — only if there are constellations with 2+ objects
        if len(self._constellations) >= 1:
            modes.append("constellation_find")

        return modes

    def _get_pool_for_mode(self, mode: str) -> List[CatalogObject]:
        """
        Return the object pool associated with a quiz mode.
        """
        if mode in {"name_to_star", "coords_to_star"}:
            return self.star_catalog

        if mode in {"name_to_deep_sky", "coords_to_deep_sky"}:
            return self.deep_sky_catalog

        if mode == "alias_to_object":
            return self._alias_pool

        if mode in {"name_to_object", "coords_to_object"}:
            return self._get_active_pool()

        return []

    def _get_active_pool(self) -> List[CatalogObject]:
        """
        Return the combined pool of currently enabled objects.
        """
        pool: List[CatalogObject] = []
        if self.include_stars:
            pool.extend(self.star_catalog)
        if self.include_deep_sky:
            pool.extend(self.deep_sky_catalog)
        return pool

    # ------------------------------------------------------------------
    # PROMPT BUILDING
    # ------------------------------------------------------------------

    def _build_prompt(
        self,
        mode: str,
        target_object: CatalogObject,
        chosen_alias: Optional[str] = None,
    ) -> str:
        """
        Build a user-facing prompt string for a given mode.
        """
        name = target_object.get("name", "Unknown object")
        ra_text = target_object.get("ra_text", "Unknown RA")
        dec_text = target_object.get("dec_text", "Unknown Dec")
        constellation = target_object.get("constellation", "Unknown constellation")
        object_type = str(target_object.get("object_type", "object")).replace("_", " ")

        if mode == "name_to_star":
            return f"Find the star {name} in {constellation}."

        if mode == "coords_to_star":
            return f"Find the star at RA {ra_text}, Dec {dec_text} (in {constellation})."

        if mode == "name_to_deep_sky":
            return f"Find the {object_type} {name} in {constellation}."

        if mode == "coords_to_deep_sky":
            return f"Find the deep-sky object at RA {ra_text}, Dec {dec_text} (in {constellation})."

        if mode == "name_to_object":
            return f"Find {name}, a {object_type}, in {constellation}."

        if mode == "coords_to_object":
            return f"Find the object at RA {ra_text}, Dec {dec_text} (in {constellation})."

        if mode == "alias_to_object":
            alias = chosen_alias or name
            return f"Find {alias}."

        if mode == "constellation_find":
            return f"Find any object in {constellation}."

        return f"Find {name}."

    # ------------------------------------------------------------------
    # CATALOG LOADING
    # ------------------------------------------------------------------

    def _load_catalogs(self) -> None:
        """
        Load star and deep-sky catalogs, build derived pools.
        """
        self.star_catalog = self._load_star_catalog()
        self.deep_sky_catalog = self._load_deep_sky_catalog()
        self.all_objects = list(self.star_catalog) + list(self.deep_sky_catalog)

        self._build_derived_pools()

    def _build_derived_pools(self) -> None:
        """
        Build the alias pool and constellation index from loaded catalogs.
        """
        # Alias pool: objects that have at least one alias
        self._alias_pool = [
            obj for obj in self.all_objects
            if obj.get("aliases") and len(obj["aliases"]) > 0
        ]

        # Constellation index
        self._constellation_index.clear()
        for obj in self.all_objects:
            c = obj.get("constellation", "Unknown")
            if c and c != "Unknown":
                self._constellation_index.setdefault(c, []).append(obj)

        # Constellations with at least 2 objects (for meaningful questions)
        self._constellations = [
            c for c, objs in self._constellation_index.items()
            if len(objs) >= 2
        ]

    def _load_star_catalog(self) -> List[CatalogObject]:
        """
        Load star catalog or fallback stars.
        """
        if load_star_catalog is not None:
            try:
                stars = load_star_catalog()
                if stars:
                    return self._normalize_catalog(stars)
            except Exception:
                pass

        return self._normalize_catalog(self._fallback_stars())

    def _load_deep_sky_catalog(self) -> List[CatalogObject]:
        """
        Load deep-sky catalog or fallback deep-sky objects.
        """
        if load_deep_sky_catalog is not None:
            try:
                objects = load_deep_sky_catalog()
                if objects:
                    return self._normalize_catalog(objects)
            except Exception:
                pass

        return self._normalize_catalog(self._fallback_deep_sky())

    def _normalize_catalog(self, objects: List[CatalogObject]) -> List[CatalogObject]:
        """
        Normalize catalog objects so required fields exist.
        """
        normalized: List[CatalogObject] = []

        for index, obj in enumerate(objects):
            ra_deg = self._safe_float(obj.get("ra_deg", 0.0))
            dec_deg = self._safe_float(obj.get("dec_deg", 0.0))

            normalized_object: CatalogObject = {
                "id": obj.get("id", f"object_{index}"),
                "name": obj.get("name", f"Unnamed Object {index}"),
                "aliases": obj.get("aliases", []),
                "ra_deg": ra_deg,
                "dec_deg": dec_deg,
                "ra_text": obj.get("ra_text", format_ra(ra_deg)),
                "dec_text": obj.get("dec_text", format_dec(dec_deg)),
                "magnitude": self._safe_float(obj.get("magnitude", 99.0)),
                "constellation": obj.get("constellation", "Unknown"),
                "object_type": obj.get("object_type", "object"),
            }

            for key, value in obj.items():
                if key not in normalized_object:
                    normalized_object[key] = value

            normalized.append(normalized_object)

        return normalized

    # ------------------------------------------------------------------
    # FALLBACK DATA
    # ------------------------------------------------------------------

    def _fallback_stars(self) -> List[CatalogObject]:
        """
        Fallback starter stars if the CSV cannot be loaded.
        """
        return [
            {
                "id": "sirius",
                "name": "Sirius",
                "aliases": ["Alpha Canis Majoris", "α CMa", "Dog Star"],
                "ra_deg": 101.2872,
                "dec_deg": -16.7161,
                "magnitude": -1.46,
                "constellation": "Canis Major",
                "object_type": "star",
            },
            {
                "id": "betelgeuse",
                "name": "Betelgeuse",
                "aliases": ["Alpha Orionis", "α Ori"],
                "ra_deg": 88.7929,
                "dec_deg": 7.4071,
                "magnitude": 0.42,
                "constellation": "Orion",
                "object_type": "star",
            },
            {
                "id": "vega",
                "name": "Vega",
                "aliases": ["Alpha Lyrae", "α Lyr"],
                "ra_deg": 279.2347,
                "dec_deg": 38.7837,
                "magnitude": 0.03,
                "constellation": "Lyra",
                "object_type": "star",
            },
        ]

    def _fallback_deep_sky(self) -> List[CatalogObject]:
        """
        Fallback starter deep-sky objects if the CSV cannot be loaded.
        """
        return [
            {
                "id": "m42",
                "name": "Orion Nebula",
                "aliases": ["M42", "NGC 1976"],
                "ra_deg": 83.8221,
                "dec_deg": -5.3911,
                "magnitude": 4.0,
                "constellation": "Orion",
                "object_type": "nebula",
            },
            {
                "id": "m31",
                "name": "Andromeda Galaxy",
                "aliases": ["M31", "NGC 224"],
                "ra_deg": 10.6847,
                "dec_deg": 41.2692,
                "magnitude": 3.4,
                "constellation": "Andromeda",
                "object_type": "galaxy",
            },
            {
                "id": "ngc5139",
                "name": "Omega Centauri",
                "aliases": ["NGC 5139", "Omega Cen"],
                "ra_deg": 201.6970,
                "dec_deg": -47.4794,
                "magnitude": 3.7,
                "constellation": "Centaurus",
                "object_type": "globular_cluster",
            },
        ]

    # ------------------------------------------------------------------
    # UTILITIES
    # ------------------------------------------------------------------

    @staticmethod
    def _safe_float(value: Any, default: float = 0.0) -> float:
        """
        Safely convert a value to float.
        """
        try:
            return float(value)
        except (TypeError, ValueError):
            return default