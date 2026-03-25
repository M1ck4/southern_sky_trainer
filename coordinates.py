"""
coordinates.py

Coordinate helpers for the Astronomy Trainer application.

This module centralizes logic related to:
- right ascension and declination formatting
- parsing simple RA/Dec text values
- normalization of coordinate values
- converting celestial coordinates to 2D map coordinates
- angular separation calculations

The first version of the app uses a simple rectangular equatorial map:
- X axis: Right Ascension from 0 to 360 degrees
- Y axis: Declination from +90 to -90 degrees

This keeps the educational value high because the map directly reflects
the coordinate system being learned.
"""

from __future__ import annotations

import math
import re
from typing import Optional, Tuple


# ----------------------------------------------------------------------
# BASIC NORMALIZATION
# ----------------------------------------------------------------------

def normalize_ra_deg(ra_deg: float) -> float:
    """
    Normalize right ascension into the range [0, 360).

    Args:
        ra_deg: Right ascension in degrees.

    Returns:
        float: Normalized right ascension.
    """
    return ra_deg % 360.0


def clamp_dec_deg(dec_deg: float) -> float:
    """
    Clamp declination into the valid range [-90, +90].

    Args:
        dec_deg: Declination in degrees.

    Returns:
        float: Clamped declination.
    """
    return max(-90.0, min(90.0, dec_deg))


# ----------------------------------------------------------------------
# RA / DEC CONVERSIONS
# ----------------------------------------------------------------------

def ra_deg_to_hours(ra_deg: float) -> float:
    """
    Convert right ascension from degrees to hours.

    Args:
        ra_deg: Right ascension in degrees.

    Returns:
        float: Right ascension in hours.
    """
    return normalize_ra_deg(ra_deg) / 15.0


def ra_hours_to_deg(ra_hours: float) -> float:
    """
    Convert right ascension from hours to degrees.

    Args:
        ra_hours: Right ascension in hours.

    Returns:
        float: Right ascension in degrees.
    """
    return (ra_hours * 15.0) % 360.0


def format_ra(ra_deg: float) -> str:
    """
    Format right ascension in degrees as hh mm ss.

    Args:
        ra_deg: Right ascension in degrees.

    Returns:
        str: Formatted RA string.
    """
    total_hours = ra_deg_to_hours(ra_deg)

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
    Format declination in degrees as signed dd mm ss.

    Args:
        dec_deg: Declination in degrees.

    Returns:
        str: Formatted declination string.
    """
    dec_deg = clamp_dec_deg(dec_deg)
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


def degrees_to_hms(ra_deg: float) -> Tuple[int, int, int]:
    """
    Convert RA in degrees to integer hours, minutes, seconds.

    Args:
        ra_deg: Right ascension in degrees.

    Returns:
        tuple[int, int, int]: Hours, minutes, seconds.
    """
    total_hours = ra_deg_to_hours(ra_deg)

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

    return hours % 24, minutes, seconds


def degrees_to_dms(dec_deg: float) -> Tuple[str, int, int, int]:
    """
    Convert declination in degrees to sign, degrees, minutes, seconds.

    Args:
        dec_deg: Declination in degrees.

    Returns:
        tuple[str, int, int, int]: Sign, degrees, minutes, seconds.
    """
    dec_deg = clamp_dec_deg(dec_deg)
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

    return sign, degrees, minutes, seconds


# ----------------------------------------------------------------------
# PARSING
# ----------------------------------------------------------------------

def parse_ra_text(text: str) -> Optional[float]:
    """
    Parse a right ascension string into degrees.

    Supports examples like:
    - 05h 55m 10s
    - 5 55 10
    - 5:55:10
    - 5.9194h

    Returns:
        float | None: RA in degrees, or None if parsing fails.
    """
    if not text or not text.strip():
        return None

    cleaned = text.strip().lower()
    cleaned = cleaned.replace("hours", "h").replace("hour", "h")
    cleaned = cleaned.replace("minutes", "m").replace("minute", "m")
    cleaned = cleaned.replace("seconds", "s").replace("second", "s")

    match_decimal_hours = re.fullmatch(r"\s*([0-9]+(?:\.[0-9]+)?)\s*h\s*", cleaned)
    if match_decimal_hours:
        hours = float(match_decimal_hours.group(1))
        return ra_hours_to_deg(hours)

    parts = re.split(r"[hms:\s]+", cleaned)
    parts = [p for p in parts if p]

    try:
        if len(parts) == 1:
            hours = float(parts[0])
            return ra_hours_to_deg(hours)

        if len(parts) == 2:
            hours = float(parts[0])
            minutes = float(parts[1])
            total_hours = hours + (minutes / 60.0)
            return ra_hours_to_deg(total_hours)

        if len(parts) >= 3:
            hours = float(parts[0])
            minutes = float(parts[1])
            seconds = float(parts[2])
            total_hours = hours + (minutes / 60.0) + (seconds / 3600.0)
            return ra_hours_to_deg(total_hours)

    except ValueError:
        return None

    return None


def parse_dec_text(text: str) -> Optional[float]:
    """
    Parse a declination string into degrees.

    Supports examples like:
    - +07° 24′ 25″
    - -16 42 58
    - -16:42:58
    - +7.4

    Returns:
        float | None: Declination in degrees, or None if parsing fails.
    """
    if not text or not text.strip():
        return None

    cleaned = text.strip()
    sign = -1.0 if cleaned.startswith("-") else 1.0

    cleaned = cleaned.replace("+", "").replace("-", "")
    cleaned = cleaned.replace("°", " ").replace("º", " ")
    cleaned = cleaned.replace("′", " ").replace("'", " ")
    cleaned = cleaned.replace("″", " ").replace('"', " ")
    cleaned = cleaned.replace(":", " ")

    parts = [p for p in cleaned.split() if p]

    try:
        if len(parts) == 1:
            degrees = float(parts[0])
            return clamp_dec_deg(sign * degrees)

        if len(parts) == 2:
            degrees = float(parts[0])
            minutes = float(parts[1])
            value = degrees + (minutes / 60.0)
            return clamp_dec_deg(sign * value)

        if len(parts) >= 3:
            degrees = float(parts[0])
            minutes = float(parts[1])
            seconds = float(parts[2])
            value = degrees + (minutes / 60.0) + (seconds / 3600.0)
            return clamp_dec_deg(sign * value)

    except ValueError:
        return None

    return None


# ----------------------------------------------------------------------
# MAP PROJECTION HELPERS
# ----------------------------------------------------------------------

def sky_to_map_xy(
    ra_deg: float,
    dec_deg: float,
    width: float,
    height: float,
    invert_ra: bool = True,
) -> Tuple[float, float]:
    """
    Convert RA/Dec to 2D map coordinates for a rectangular equatorial map.

    Args:
        ra_deg: Right ascension in degrees.
        dec_deg: Declination in degrees.
        width: Map width in pixels.
        height: Map height in pixels.
        invert_ra: If True, RA increases to the left, similar to many sky charts.

    Returns:
        tuple[float, float]: x, y pixel position
    """
    ra_deg = normalize_ra_deg(ra_deg)
    dec_deg = clamp_dec_deg(dec_deg)

    x_fraction = ra_deg / 360.0
    y_fraction = (90.0 - dec_deg) / 180.0

    if invert_ra:
        x_fraction = 1.0 - x_fraction

    x = x_fraction * width
    y = y_fraction * height

    return x, y


def map_xy_to_sky(
    x: float,
    y: float,
    width: float,
    height: float,
    invert_ra: bool = True,
) -> Tuple[float, float]:
    """
    Convert map pixel coordinates back into RA/Dec.

    Args:
        x: X position in pixels
        y: Y position in pixels
        width: Map width in pixels
        height: Map height in pixels
        invert_ra: If True, RA increases to the left

    Returns:
        tuple[float, float]: RA degrees, Dec degrees
    """
    if width <= 0 or height <= 0:
        raise ValueError("Map width and height must be greater than zero.")

    x_fraction = x / width
    y_fraction = y / height

    if invert_ra:
        x_fraction = 1.0 - x_fraction

    ra_deg = normalize_ra_deg(x_fraction * 360.0)
    dec_deg = clamp_dec_deg(90.0 - (y_fraction * 180.0))

    return ra_deg, dec_deg


# ----------------------------------------------------------------------
# DISTANCE / MATCHING
# ----------------------------------------------------------------------

def angular_separation_deg(
    ra1_deg: float,
    dec1_deg: float,
    ra2_deg: float,
    dec2_deg: float,
) -> float:
    """
    Compute angular separation between two celestial coordinates in degrees.

    Uses the spherical law of cosines.

    Args:
        ra1_deg: First RA in degrees
        dec1_deg: First Dec in degrees
        ra2_deg: Second RA in degrees
        dec2_deg: Second Dec in degrees

    Returns:
        float: Angular separation in degrees
    """
    ra1_rad = math.radians(normalize_ra_deg(ra1_deg))
    dec1_rad = math.radians(clamp_dec_deg(dec1_deg))
    ra2_rad = math.radians(normalize_ra_deg(ra2_deg))
    dec2_rad = math.radians(clamp_dec_deg(dec2_deg))

    cos_sep = (
        math.sin(dec1_rad) * math.sin(dec2_rad)
        + math.cos(dec1_rad) * math.cos(dec2_rad) * math.cos(ra1_rad - ra2_rad)
    )

    # Guard against tiny floating-point overflow
    cos_sep = max(-1.0, min(1.0, cos_sep))

    return math.degrees(math.acos(cos_sep))


def nearest_object(
    ra_deg: float,
    dec_deg: float,
    objects: list[dict],
) -> Optional[dict]:
    """
    Find the nearest object in a list to the given RA/Dec.

    Each object is expected to contain:
    - ra_deg
    - dec_deg

    Args:
        ra_deg: Query RA in degrees
        dec_deg: Query Dec in degrees
        objects: List of object dictionaries

    Returns:
        dict | None: Nearest object, or None if list is empty
    """
    if not objects:
        return None

    best_object = None
    best_distance = float("inf")

    for obj in objects:
        obj_ra = obj.get("ra_deg")
        obj_dec = obj.get("dec_deg")

        if obj_ra is None or obj_dec is None:
            continue

        distance = angular_separation_deg(
            ra1_deg=ra_deg,
            dec1_deg=dec_deg,
            ra2_deg=float(obj_ra),
            dec2_deg=float(obj_dec),
        )

        if distance < best_distance:
            best_distance = distance
            best_object = obj

    return best_object


# ----------------------------------------------------------------------
# DISPLAY HELPERS
# ----------------------------------------------------------------------

def coordinate_label(ra_deg: float, dec_deg: float) -> str:
    """
    Create a display label combining formatted RA and Dec.

    Args:
        ra_deg: Right ascension in degrees
        dec_deg: Declination in degrees

    Returns:
        str
    """
    return f"RA {format_ra(ra_deg)}, Dec {format_dec(dec_deg)}"


def decimal_coordinate_label(ra_deg: float, dec_deg: float) -> str:
    """
    Create a decimal-degree coordinate label.

    Args:
        ra_deg: Right ascension in degrees
        dec_deg: Declination in degrees

    Returns:
        str
    """
    return f"RA {normalize_ra_deg(ra_deg):.4f}°, Dec {clamp_dec_deg(dec_deg):+.4f}°"


# ----------------------------------------------------------------------
# OBSERVER AND TIME
# ----------------------------------------------------------------------

# Default observer: Brisbane, Queensland
DEFAULT_LATITUDE = -27.4698
DEFAULT_LONGITUDE = 153.0251


def julian_date(year: int, month: int, day: int, hour: float = 0.0) -> float:
    """
    Compute the Julian Date for a given UTC date and time.

    Uses the standard algorithm valid for dates after 1582.

    Args:
        year: UTC year
        month: UTC month (1-12)
        day: UTC day (1-31)
        hour: UTC hour as a decimal (e.g. 14.5 for 2:30 PM)

    Returns:
        float: Julian Date
    """
    if month <= 2:
        year -= 1
        month += 12

    a = int(year / 100)
    b = 2 - a + int(a / 4)

    jd = (
        int(365.25 * (year + 4716))
        + int(30.6001 * (month + 1))
        + day
        + hour / 24.0
        + b
        - 1524.5
    )
    return jd


def greenwich_mean_sidereal_time(jd: float) -> float:
    """
    Compute Greenwich Mean Sidereal Time in degrees for a given Julian Date.

    Uses the IAU formula for GMST.

    Args:
        jd: Julian Date

    Returns:
        float: GMST in degrees [0, 360)
    """
    t = (jd - 2451545.0) / 36525.0

    gmst_seconds = (
        280.46061837
        + 360.98564736629 * (jd - 2451545.0)
        + 0.000387933 * t * t
        - (t * t * t) / 38710000.0
    )

    return gmst_seconds % 360.0


def local_sidereal_time(
    jd: float,
    longitude_deg: float = DEFAULT_LONGITUDE,
) -> float:
    """
    Compute Local Sidereal Time in degrees.

    Args:
        jd: Julian Date
        longitude_deg: Observer longitude in degrees (east positive)

    Returns:
        float: LST in degrees [0, 360)
    """
    gmst = greenwich_mean_sidereal_time(jd)
    return (gmst + longitude_deg) % 360.0


def datetime_to_jd(
    year: int,
    month: int,
    day: int,
    hour: int = 0,
    minute: int = 0,
    second: int = 0,
    utc_offset_hours: float = 0.0,
) -> float:
    """
    Convert a civil datetime to Julian Date.

    Args:
        year: Year
        month: Month (1-12)
        day: Day (1-31)
        hour: Hour (0-23)
        minute: Minute (0-59)
        second: Second (0-59)
        utc_offset_hours: Local timezone offset from UTC in hours
                          (e.g. +10 for AEST)

    Returns:
        float: Julian Date in UTC
    """
    decimal_hour = hour + minute / 60.0 + second / 3600.0
    utc_hour = decimal_hour - utc_offset_hours
    return julian_date(year, month, day, utc_hour)


def _detect_utc_offset() -> float:
    """
    Detect the local UTC offset from the system clock.

    Uses datetime.now().astimezone() which reliably handles
    Windows timezone settings and daylight saving transitions.

    Returns:
        float: UTC offset in hours (e.g. 10.0 for AEST, 11.0 for AEDT)
    """
    import datetime

    # Get the current local timezone offset via datetime
    # This works reliably on Windows, macOS, and Linux
    local_now = datetime.datetime.now(datetime.timezone.utc).astimezone()
    offset = local_now.utcoffset()

    if offset is not None:
        return offset.total_seconds() / 3600.0

    # Fallback to time module if datetime method fails
    import time
    now = time.localtime()
    if now.tm_isdst and time.daylight:
        return -time.altzone / 3600.0
    return -time.timezone / 3600.0


def current_lst(
    longitude_deg: float = DEFAULT_LONGITUDE,
    utc_offset_hours: Optional[float] = None,
) -> float:
    """
    Compute the current Local Sidereal Time using the system clock.

    Args:
        longitude_deg: Observer longitude in degrees (east positive)
        utc_offset_hours: Local timezone offset from UTC. If None,
                          auto-detected from the system clock (handles DST).

    Returns:
        float: LST in degrees [0, 360)
    """
    import datetime

    if utc_offset_hours is None:
        utc_offset_hours = _detect_utc_offset()

    now = datetime.datetime.now()
    jd = datetime_to_jd(
        year=now.year,
        month=now.month,
        day=now.day,
        hour=now.hour,
        minute=now.minute,
        second=now.second,
        utc_offset_hours=utc_offset_hours,
    )
    return local_sidereal_time(jd, longitude_deg)


# ----------------------------------------------------------------------
# HORIZONTAL COORDINATES (Alt/Az)
# ----------------------------------------------------------------------

def ra_dec_to_alt_az(
    ra_deg: float,
    dec_deg: float,
    lst_deg: float,
    latitude_deg: float = DEFAULT_LATITUDE,
) -> Tuple[float, float]:
    """
    Convert equatorial coordinates (RA/Dec) to horizontal (altitude/azimuth).

    Args:
        ra_deg: Right ascension in degrees
        dec_deg: Declination in degrees
        lst_deg: Local Sidereal Time in degrees
        latitude_deg: Observer latitude in degrees (south negative)

    Returns:
        tuple[float, float]: (altitude_deg, azimuth_deg)
            altitude: degrees above horizon (-90 to +90)
            azimuth: degrees from north clockwise (0 to 360)
    """
    ha_deg = (lst_deg - ra_deg) % 360.0
    ha_rad = math.radians(ha_deg)
    dec_rad = math.radians(dec_deg)
    lat_rad = math.radians(latitude_deg)

    sin_alt = (
        math.sin(dec_rad) * math.sin(lat_rad)
        + math.cos(dec_rad) * math.cos(lat_rad) * math.cos(ha_rad)
    )
    sin_alt = max(-1.0, min(1.0, sin_alt))
    alt_rad = math.asin(sin_alt)

    cos_alt = math.cos(alt_rad)
    if abs(cos_alt) < 1e-10:
        az_deg = 0.0
    else:
        cos_az = (
            math.sin(dec_rad) - math.sin(alt_rad) * math.sin(lat_rad)
        ) / (cos_alt * math.cos(lat_rad))
        cos_az = max(-1.0, min(1.0, cos_az))
        az_rad = math.acos(cos_az)

        if math.sin(ha_rad) > 0:
            az_deg = 360.0 - math.degrees(az_rad)
        else:
            az_deg = math.degrees(az_rad)

    alt_deg = math.degrees(alt_rad)
    return alt_deg, az_deg


def is_above_horizon(
    ra_deg: float,
    dec_deg: float,
    lst_deg: float,
    latitude_deg: float = DEFAULT_LATITUDE,
    min_altitude_deg: float = 0.0,
) -> bool:
    """
    Check whether an object is above the horizon.

    Args:
        ra_deg: Right ascension in degrees
        dec_deg: Declination in degrees
        lst_deg: Local Sidereal Time in degrees
        latitude_deg: Observer latitude
        min_altitude_deg: Minimum altitude to count as visible

    Returns:
        bool
    """
    alt, _ = ra_dec_to_alt_az(ra_deg, dec_deg, lst_deg, latitude_deg)
    return alt >= min_altitude_deg


# ----------------------------------------------------------------------
# STEREOGRAPHIC POLAR PROJECTION
# ----------------------------------------------------------------------

def polar_stereo_xy(
    ra_deg: float,
    dec_deg: float,
    lst_deg: float,
    radius: float,
    south_pole: bool = True,
) -> Tuple[float, float]:
    """
    Project RA/Dec onto a circular stereographic chart centred on a pole.

    The chart is rotated so that the current LST is at the top (south)
    or bottom (north), matching what is overhead right now.

    For a south-pole chart (default for southern hemisphere):
    - Centre of the circle is the south celestial pole (Dec -90)
    - Edge of the circle is the celestial equator (Dec 0) or a
      configurable declination limit
    - Hour angle determines the angular position around the circle

    Args:
        ra_deg: Right ascension in degrees
        dec_deg: Declination in degrees
        lst_deg: Local Sidereal Time in degrees (used to rotate the chart)
        radius: Radius of the chart in pixels
        south_pole: If True, project from south pole; if False, from north

    Returns:
        tuple[float, float]: (x, y) relative to chart centre
    """
    if south_pole:
        # Distance from south pole: 0 at pole, 1 at equator
        polar_distance = (dec_deg + 90.0) / 180.0
        # Hour angle measured from LST
        angle_deg = (ra_deg - lst_deg) % 360.0
    else:
        polar_distance = (90.0 - dec_deg) / 180.0
        angle_deg = (lst_deg - ra_deg) % 360.0

    # Stereographic scaling: r = tan(polar_angle / 2)
    # But for a flat chart, simple linear scaling works better visually
    # and is what most planispheres use
    r = polar_distance * radius

    # Convert angle to radians (0° = top of chart = south/north)
    angle_rad = math.radians(angle_deg - 90.0)

    x = r * math.cos(angle_rad)
    y = r * math.sin(angle_rad)

    return x, y


# ----------------------------------------------------------------------
# HORIZON VIEW PROJECTION
# ----------------------------------------------------------------------

def horizon_view_xy(
    alt_deg: float,
    az_deg: float,
    facing_az_deg: float,
    width: float,
    height: float,
    fov_deg: float = 120.0,
) -> Tuple[float, float]:
    """
    Project altitude/azimuth onto a flat horizon view.

    The view is centred on a compass direction (facing_az_deg) and
    shows a window of the sky around it. Objects below the horizon
    are still projected but will be below the bottom of the view.

    The projection is a simple gnomonic-like mapping:
    - Azimuth offset from facing direction maps to X
    - Altitude maps to Y (horizon at bottom, zenith at top)

    Args:
        alt_deg: Altitude above horizon in degrees
        az_deg: Azimuth in degrees (0=N, 90=E, 180=S, 270=W)
        facing_az_deg: Centre azimuth the viewer is facing
        width: View width in pixels
        height: View height in pixels
        fov_deg: Horizontal field of view in degrees

    Returns:
        tuple[float, float]: (x, y) pixel position
    """
    # Azimuth offset from centre, wrapped to [-180, 180]
    az_offset = (az_deg - facing_az_deg + 180.0) % 360.0 - 180.0

    # Map azimuth offset to x: centre of view = width/2
    # Positive offset (clockwise/east) goes to the RIGHT of screen.
    # This matches holding a planisphere overhead or looking up at the sky.
    x = (width / 2.0) + (az_offset / fov_deg) * width

    # Map altitude to y: horizon at bottom, zenith at top
    # With fov_deg horizontal, vertical range is roughly fov * height/width
    vertical_fov = fov_deg * (height / width)
    y = height - (alt_deg / vertical_fov) * height

    return x, y


def horizon_xy_to_alt_az(
    x: float,
    y: float,
    facing_az_deg: float,
    width: float,
    height: float,
    fov_deg: float = 120.0,
) -> Tuple[float, float]:
    """
    Convert horizon view pixel coordinates back to altitude/azimuth.

    Args:
        x: X pixel position
        y: Y pixel position
        facing_az_deg: Centre azimuth
        width: View width in pixels
        height: View height in pixels
        fov_deg: Horizontal field of view in degrees

    Returns:
        tuple[float, float]: (altitude_deg, azimuth_deg)
    """
    az_offset = ((x - width / 2.0) / width) * fov_deg
    az_deg = (facing_az_deg + az_offset) % 360.0

    vertical_fov = fov_deg * (height / width)
    alt_deg = ((height - y) / height) * vertical_fov

    return alt_deg, az_deg