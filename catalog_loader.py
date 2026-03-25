"""
catalog_loader.py

Loads and normalizes catalog data for the Astronomy Trainer app.

Supported files:
    data/stars.csv
    data/deep_sky.csv
    data/constellation_lines.json
    data/constellations.json

Supported object categories:
- stars
- nebulae
- clusters
- galaxies
- supernova remnants
- planetary nebulae
- dark nebulae
- other deep-sky style objects

Expected CSV columns:
    id
    name
    aliases
    ra_deg
    dec_deg
    magnitude
    constellation
    object_type

Optional CSV columns:
    ra_text
    dec_text
    size_arcmin
    notes
    and any additional metadata fields

Constellation line JSON format:
{
  "Orion": [
    ["betelgeuse", "bellatrix"],
    ["bellatrix", "mintaka"]
  ],
  "Crux": [
    ["gacrux", "acrux"]
  ]
}

Constellation metadata JSON format, optional:
{
  "Orion": {
    "abbr": "Ori",
    "label_ra_deg": 83.8,
    "label_dec_deg": -1.2
  }
}
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Dict, List, Optional


CatalogObject = Dict[str, Any]
ConstellationLines = Dict[str, List[List[str]]]
ConstellationMetadata = Dict[str, Dict[str, Any]]


DEFAULT_DATA_DIR = Path(__file__).resolve().parent / "data"
DEFAULT_STAR_CSV = DEFAULT_DATA_DIR / "stars.csv"
DEFAULT_DEEP_SKY_CSV = DEFAULT_DATA_DIR / "deep_sky.csv"
DEFAULT_CONSTELLATION_LINES_JSON = DEFAULT_DATA_DIR / "constellation_lines.json"
DEFAULT_CONSTELLATIONS_JSON = DEFAULT_DATA_DIR / "constellations.json"


def load_star_catalog(csv_path: Optional[str | Path] = None) -> List[CatalogObject]:
    """
    Load the star catalog from a CSV file.

    Args:
        csv_path: Optional custom path to the CSV file.

    Returns:
        list[dict]: A list of normalized star objects.
    """
    path = Path(csv_path) if csv_path is not None else DEFAULT_STAR_CSV
    return _load_catalog_file(path=path, default_object_type="star")


def load_deep_sky_catalog(csv_path: Optional[str | Path] = None) -> List[CatalogObject]:
    """
    Load the deep sky catalog from a CSV file.

    Args:
        csv_path: Optional custom path to the CSV file.

    Returns:
        list[dict]: A list of normalized deep-sky objects.
    """
    path = Path(csv_path) if csv_path is not None else DEFAULT_DEEP_SKY_CSV
    return _load_catalog_file(path=path, default_object_type="deep_sky")


def load_all_catalog_objects(
    star_csv_path: Optional[str | Path] = None,
    deep_sky_csv_path: Optional[str | Path] = None,
    include_stars: bool = True,
    include_deep_sky: bool = True,
) -> List[CatalogObject]:
    """
    Load all enabled catalog objects into one combined list.

    Args:
        star_csv_path: Optional custom star CSV path.
        deep_sky_csv_path: Optional custom deep-sky CSV path.
        include_stars: Whether to include stars.
        include_deep_sky: Whether to include deep-sky objects.

    Returns:
        list[dict]: Combined normalized catalog objects.
    """
    objects: List[CatalogObject] = []

    if include_stars:
        objects.extend(load_star_catalog(star_csv_path))

    if include_deep_sky:
        objects.extend(load_deep_sky_catalog(deep_sky_csv_path))

    return objects


def load_constellation_lines(
    json_path: Optional[str | Path] = None,
) -> ConstellationLines:
    """
    Load constellation line definitions from JSON.

    Args:
        json_path: Optional custom path to the JSON file.

    Returns:
        dict[str, list[list[str]]]: Constellation name to line segments.

    Raises:
        FileNotFoundError: If the JSON file does not exist.
        ValueError: If the JSON structure is invalid.
    """
    path = Path(json_path) if json_path is not None else DEFAULT_CONSTELLATION_LINES_JSON

    if not path.exists():
        raise FileNotFoundError(f"Constellation lines file not found: {path}")

    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)

    if not isinstance(data, dict):
        raise ValueError("Constellation lines JSON must be an object at the top level.")

    normalized: ConstellationLines = {}

    for constellation_name, segments in data.items():
        if not isinstance(constellation_name, str) or not constellation_name.strip():
            raise ValueError("Constellation name must be a non-empty string.")

        if not isinstance(segments, list):
            raise ValueError(f"Constellation '{constellation_name}' must map to a list of line segments.")

        clean_segments: List[List[str]] = []

        for index, segment in enumerate(segments):
            if not isinstance(segment, list) or len(segment) != 2:
                raise ValueError(
                    f"Constellation '{constellation_name}' segment {index} must be a list of two star IDs."
                )

            star_a, star_b = segment

            if not isinstance(star_a, str) or not star_a.strip():
                raise ValueError(
                    f"Constellation '{constellation_name}' segment {index} first ID must be a non-empty string."
                )

            if not isinstance(star_b, str) or not star_b.strip():
                raise ValueError(
                    f"Constellation '{constellation_name}' segment {index} second ID must be a non-empty string."
                )

            clean_segments.append([star_a.strip(), star_b.strip()])

        normalized[constellation_name.strip()] = clean_segments

    return normalized


def load_constellation_metadata(
    json_path: Optional[str | Path] = None,
) -> ConstellationMetadata:
    """
    Load optional constellation metadata from JSON.

    Args:
        json_path: Optional custom path to the metadata JSON.

    Returns:
        dict[str, dict]: Constellation metadata.
    """
    path = Path(json_path) if json_path is not None else DEFAULT_CONSTELLATIONS_JSON

    if not path.exists():
        return {}

    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)

    if not isinstance(data, dict):
        raise ValueError("Constellation metadata JSON must be an object at the top level.")

    normalized: ConstellationMetadata = {}

    for constellation_name, meta in data.items():
        if not isinstance(constellation_name, str) or not constellation_name.strip():
            raise ValueError("Constellation metadata keys must be non-empty strings.")

        if not isinstance(meta, dict):
            raise ValueError(f"Constellation metadata for '{constellation_name}' must be an object.")

        clean_meta: Dict[str, Any] = {}

        for key, value in meta.items():
            if key in {"label_ra_deg", "label_dec_deg"}:
                clean_meta[key] = _safe_float(value)
            else:
                clean_meta[key] = value

        normalized[constellation_name.strip()] = clean_meta

    return normalized


def _load_catalog_file(path: Path, default_object_type: str) -> List[CatalogObject]:
    """
    Load and normalize a generic catalog CSV file.

    Args:
        path: CSV file path.
        default_object_type: Object type to use if missing in the CSV.

    Returns:
        list[dict]: Normalized catalog objects.
    """
    if not path.exists():
        raise FileNotFoundError(f"Catalog file not found: {path}")

    objects: List[CatalogObject] = []

    with path.open(mode="r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)

        if not reader.fieldnames:
            raise ValueError(f"CSV file has no headers: {path}")

        for row_index, row in enumerate(reader, start=2):
            if _is_blank_row(row):
                continue

            try:
                obj = _normalize_catalog_row(
                    row=row,
                    default_object_type=default_object_type,
                )
                objects.append(obj)
            except ValueError as exc:
                raise ValueError(f"{path} row {row_index}: {exc}") from exc

    if not objects:
        raise ValueError(f"No valid catalog data found in: {path}")

    return objects


def _normalize_catalog_row(
    row: Dict[str, str],
    default_object_type: str,
) -> CatalogObject:
    """
    Normalize a CSV row into a clean catalog object.

    Args:
        row: Raw CSV row.
        default_object_type: Fallback object type if missing.

    Returns:
        dict: Normalized catalog object.
    """
    name = _clean_text(row.get("name"))
    if not name:
        raise ValueError("Missing required field 'name'")

    object_id = _clean_text(row.get("id")) or _slugify(name)

    ra_deg = _safe_float(row.get("ra_deg"))
    dec_deg = _safe_float(row.get("dec_deg"))

    if ra_deg is None:
        raise ValueError("Missing or invalid required field 'ra_deg'")

    if dec_deg is None:
        raise ValueError("Missing or invalid required field 'dec_deg'")

    if not (0.0 <= ra_deg < 360.0):
        raise ValueError(f"'ra_deg' must be between 0 and 360, got {ra_deg}")

    if not (-90.0 <= dec_deg <= 90.0):
        raise ValueError(f"'dec_deg' must be between -90 and +90, got {dec_deg}")

    magnitude = _safe_float(row.get("magnitude"), default=99.0)
    constellation = _clean_text(row.get("constellation")) or "Unknown"
    object_type = _clean_text(row.get("object_type")) or default_object_type

    aliases = _parse_aliases(row.get("aliases"))

    ra_text = _clean_text(row.get("ra_text")) or format_ra(ra_deg)
    dec_text = _clean_text(row.get("dec_text")) or format_dec(dec_deg)

    normalized: CatalogObject = {
        "id": object_id,
        "name": name,
        "aliases": aliases,
        "ra_deg": ra_deg,
        "dec_deg": dec_deg,
        "ra_text": ra_text,
        "dec_text": dec_text,
        "magnitude": magnitude,
        "constellation": constellation,
        "object_type": object_type,
    }

    for key, value in row.items():
        if key in normalized:
            continue

        text_value = _clean_text(value)

        if key in {"size_arcmin", "size_major_arcmin", "size_minor_arcmin"}:
            normalized[key] = _safe_float(text_value)
        else:
            normalized[key] = text_value

    return normalized


def _parse_aliases(raw_value: Optional[str]) -> List[str]:
    """
    Parse aliases from a CSV string.
    Accepts separators: comma, semicolon, pipe.
    """
    if raw_value is None:
        return []

    text = raw_value.strip()
    if not text:
        return []

    working = text.replace("|", ",").replace(";", ",")
    aliases = [part.strip() for part in working.split(",") if part.strip()]

    seen = set()
    unique_aliases: List[str] = []

    for alias in aliases:
        lowered = alias.casefold()
        if lowered not in seen:
            seen.add(lowered)
            unique_aliases.append(alias)

    return unique_aliases


def _is_blank_row(row: Dict[str, Any]) -> bool:
    """
    Check whether a CSV row is effectively blank.
    """
    return all(not str(value).strip() for value in row.values())


def _clean_text(value: Optional[str]) -> str:
    """
    Clean a text field.
    """
    if value is None:
        return ""
    return str(value).strip()


def _safe_float(value: Any, default: Optional[float] = None) -> Optional[float]:
    """
    Safely convert a value to float.
    """
    try:
        if value is None or str(value).strip() == "":
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _slugify(text: str) -> str:
    """
    Turn a name into a simple ID string.
    """
    cleaned = text.strip().lower()
    result = []

    for char in cleaned:
        if char.isalnum():
            result.append(char)
        elif char in (" ", "-", "_", "/"):
            result.append("_")

    slug = "".join(result)

    while "__" in slug:
        slug = slug.replace("__", "_")

    return slug.strip("_") or "unnamed_object"


def format_ra(ra_deg: float) -> str:
    """
    Convert right ascension in degrees to hh mm ss format.
    """
    total_hours = ra_deg / 15.0
    hours = int(total_hours)
    minutes_float = (total_hours - hours) * 60.0
    minutes = int(minutes_float)
    seconds = int(round((minutes_float - minutes) * 60.0))

    if seconds == 60:
        seconds = 0
        minutes += 1

    if minutes == 60:
        minutes = 0
        hours += 1

    hours = hours % 24
    return f"{hours:02d}h {minutes:02d}m {seconds:02d}s"


def format_dec(dec_deg: float) -> str:
    """
    Convert declination in degrees to signed dd mm ss format.
    """
    sign = "+" if dec_deg >= 0 else "-"
    absolute = abs(dec_deg)

    degrees = int(absolute)
    minutes_float = (absolute - degrees) * 60.0
    minutes = int(minutes_float)
    seconds = int(round((minutes_float - minutes) * 60.0))

    if seconds == 60:
        seconds = 0
        minutes += 1

    if minutes == 60:
        minutes = 0
        degrees += 1

    return f"{sign}{degrees:02d}° {minutes:02d}′ {seconds:02d}″"