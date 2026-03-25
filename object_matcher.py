"""
object_matcher.py

Matching helpers for the Astronomy Trainer application.

This module handles:
- exact object matching by ID
- matching by name or alias
- angular-distance based matching
- nearest-object lookup
- answer tolerance logic for gameplay

This allows the app to grow beyond simple exact-click logic.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from coordinates import angular_separation_deg

StarObject = Dict[str, Any]
MatchResult = Dict[str, Any]


def exact_id_match(target_object: StarObject, candidate_object: StarObject) -> bool:
    """
    Check whether two objects match by ID.

    Args:
        target_object: The correct target object.
        candidate_object: The user's selected object.

    Returns:
        bool
    """
    target_id = str(target_object.get("id", "")).strip().casefold()
    candidate_id = str(candidate_object.get("id", "")).strip().casefold()

    return bool(target_id) and target_id == candidate_id


def name_or_alias_match(target_object: StarObject, candidate_text: str) -> bool:
    """
    Check whether a text label matches an object's name or aliases.

    Args:
        target_object: The object to compare against.
        candidate_text: The text entered or selected.

    Returns:
        bool
    """
    if not candidate_text:
        return False

    candidate = candidate_text.strip().casefold()
    if not candidate:
        return False

    names_to_check = [str(target_object.get("name", "")).strip()]
    names_to_check.extend(target_object.get("aliases", []))

    for name in names_to_check:
        if str(name).strip().casefold() == candidate:
            return True

    return False


def angular_match(
    target_object: StarObject,
    candidate_object: StarObject,
    tolerance_deg: float = 1.0,
) -> MatchResult:
    """
    Check whether a candidate object is within a given angular tolerance
    of the target object.

    Args:
        target_object: The correct object.
        candidate_object: The selected object.
        tolerance_deg: Allowed angular separation in degrees.

    Returns:
        dict: Match result containing correctness and distance.
    """
    target_ra = _safe_float(target_object.get("ra_deg"))
    target_dec = _safe_float(target_object.get("dec_deg"))
    candidate_ra = _safe_float(candidate_object.get("ra_deg"))
    candidate_dec = _safe_float(candidate_object.get("dec_deg"))

    if None in (target_ra, target_dec, candidate_ra, candidate_dec):
        return {
            "correct": False,
            "distance_deg": None,
            "message": "Missing coordinates for angular match.",
        }

    distance = angular_separation_deg(
        ra1_deg=target_ra,
        dec1_deg=target_dec,
        ra2_deg=candidate_ra,
        dec2_deg=candidate_dec,
    )

    correct = distance <= tolerance_deg

    return {
        "correct": correct,
        "distance_deg": distance,
        "message": (
            f"Within tolerance, {distance:.3f}° away."
            if correct
            else f"Outside tolerance, {distance:.3f}° away."
        ),
    }


def nearest_object_to_coordinates(
    ra_deg: float,
    dec_deg: float,
    objects: List[StarObject],
) -> Optional[StarObject]:
    """
    Find the nearest object in a catalog to a given coordinate.

    Args:
        ra_deg: Query right ascension in degrees.
        dec_deg: Query declination in degrees.
        objects: Catalog objects.

    Returns:
        dict | None: Nearest object, or None if no valid objects exist.
    """
    best_object: Optional[StarObject] = None
    best_distance: float = float("inf")

    for obj in objects:
        obj_ra = _safe_float(obj.get("ra_deg"))
        obj_dec = _safe_float(obj.get("dec_deg"))

        if obj_ra is None or obj_dec is None:
            continue

        distance = angular_separation_deg(
            ra1_deg=ra_deg,
            dec1_deg=dec_deg,
            ra2_deg=obj_ra,
            dec2_deg=obj_dec,
        )

        if distance < best_distance:
            best_distance = distance
            best_object = obj

    return best_object


def nearest_object_to_object(
    target_object: StarObject,
    objects: List[StarObject],
    exclude_same_id: bool = False,
) -> Optional[StarObject]:
    """
    Find the nearest object in a catalog to the target object.

    Args:
        target_object: The reference object.
        objects: Catalog objects.
        exclude_same_id: Whether to ignore the same object ID.

    Returns:
        dict | None
    """
    target_ra = _safe_float(target_object.get("ra_deg"))
    target_dec = _safe_float(target_object.get("dec_deg"))

    if target_ra is None or target_dec is None:
        return None

    target_id = str(target_object.get("id", "")).strip().casefold()

    best_object: Optional[StarObject] = None
    best_distance: float = float("inf")

    for obj in objects:
        obj_id = str(obj.get("id", "")).strip().casefold()

        if exclude_same_id and obj_id == target_id:
            continue

        obj_ra = _safe_float(obj.get("ra_deg"))
        obj_dec = _safe_float(obj.get("dec_deg"))

        if obj_ra is None or obj_dec is None:
            continue

        distance = angular_separation_deg(
            ra1_deg=target_ra,
            dec1_deg=target_dec,
            ra2_deg=obj_ra,
            dec2_deg=obj_dec,
        )

        if distance < best_distance:
            best_distance = distance
            best_object = obj

    return best_object


def build_match_result(
    target_object: StarObject,
    clicked_object: Optional[StarObject],
    correct: bool,
    distance_deg: Optional[float] = None,
) -> MatchResult:
    """
    Build a standard match result dictionary.

    Args:
        target_object: The correct target object.
        clicked_object: The selected object, if any.
        correct: Whether the answer is correct.
        distance_deg: Optional angular distance.

    Returns:
        dict
    """
    target_name = target_object.get("name", "Unknown object")

    if clicked_object is None:
        return {
            "correct": False,
            "target_object": target_object,
            "clicked_object": None,
            "distance_deg": distance_deg,
            "message": f"No object selected. The correct answer was {target_name}.",
        }

    clicked_name = clicked_object.get("name", "Unknown object")

    if correct:
        if distance_deg is not None:
            return {
                "correct": True,
                "target_object": target_object,
                "clicked_object": clicked_object,
                "distance_deg": distance_deg,
                "message": f"Correct. You found {target_name} ({distance_deg:.3f}° away).",
            }

        return {
            "correct": True,
            "target_object": target_object,
            "clicked_object": clicked_object,
            "distance_deg": distance_deg,
            "message": f"Correct. You found {target_name}.",
        }

    if distance_deg is not None:
        return {
            "correct": False,
            "target_object": target_object,
            "clicked_object": clicked_object,
            "distance_deg": distance_deg,
            "message": (
                f"Not quite. You selected {clicked_name}. "
                f"The correct answer was {target_name} "
                f"({distance_deg:.3f}° away)."
            ),
        }

    return {
        "correct": False,
        "target_object": target_object,
        "clicked_object": clicked_object,
        "distance_deg": distance_deg,
        "message": f"Not quite. You selected {clicked_name}. The correct answer was {target_name}.",
    }


def _safe_float(value: Any) -> Optional[float]:
    """
    Safely convert a value to float.

    Args:
        value: Input value.

    Returns:
        float | None
    """
    try:
        if value is None or str(value).strip() == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None