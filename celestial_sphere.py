"""
celestial_sphere.py

Interactive 3D celestial sphere widget for the Astronomy Trainer.

Two viewing modes:
  Outside — a glass globe you rotate by dragging, with Earth at the
            centre showing the observer's position and lat/lon grid.
  Inside  — standing at Earth's centre looking outward. The sky fills
            the viewport as a dome/fisheye projection. Drag rotates
            your gaze direction.

Renders:
- RA/Dec coordinate grid as great circles on the sphere
- Stars and deep-sky objects at their correct positions
- Constellation line segments and labels
- Earth with lat/lon grid, equator, observer marker, and axis
- Celestial poles highlighted (NCP, SCP)

This widget shares the same public API as StarMapWidget so AppWindow
can swap between them.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple

from PySide6.QtCore import QPointF, QPoint, QRectF, Qt, Signal
from PySide6.QtGui import (
    QColor, QFont, QMouseEvent, QPainter, QPaintEvent,
    QPen, QWheelEvent,
)
from PySide6.QtWidgets import QWidget

from catalog_loader import (
    load_constellation_lines,
    load_constellation_metadata,
    load_deep_sky_catalog,
    load_star_catalog,
)
from coordinates import (
    _detect_utc_offset,
    angular_separation_deg,
    current_lst,
    detect_observer_location,
    format_dec,
    format_ra,
    ra_dec_to_alt_az,
    DEFAULT_LATITUDE,
    DEFAULT_LONGITUDE,
)


CatalogObject = Dict[str, Any]
ConstellationLines = Dict[str, List[List[str]]]
ConstellationMetadata = Dict[str, Dict[str, Any]]


class CelestialSphereWidget(QWidget):
    """Interactive 3D celestial sphere with rotation and object selection."""

    object_clicked = Signal(dict)
    sky_clicked = Signal(float, float)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setMinimumSize(900, 600)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)

        # Catalog data
        self.stars: List[CatalogObject] = []
        self.deep_sky_objects: List[CatalogObject] = []
        self.all_objects: List[CatalogObject] = []
        self.star_index: Dict[str, CatalogObject] = {}
        self.constellation_lines: ConstellationLines = {}
        self.constellation_metadata: ConstellationMetadata = {}
        self._load_catalogs()

        # Observer — auto-detected from system timezone
        _lat, _lon, self.observer_city = detect_observer_location()
        self.observer_lat: float = _lat
        self.observer_lon: float = _lon
        self.utc_offset: float = _detect_utc_offset()
        self.lst_deg: float = current_lst(self.observer_lon, self.utc_offset)
        self.auto_time: bool = True

        # 3D rotation — separate state for each view mode
        # Outside: tilt/spin control camera around the globe
        # Inside: tilt/spin control gaze direction (look altitude/azimuth)
        self._outside_rot_x: float = self.observer_lat  # tilt to latitude
        self._outside_rot_y: float = 0.0
        self._inside_rot_x: float = 40.0    # looking up ~40° elevation
        self._inside_rot_y: float = 0.0     # facing south (Az=180 = default)
        self.sphere_zoom: float = 1.0

        # Active rotation (points to the current mode's values)
        self.rot_x: float = self._outside_rot_x
        self.rot_y: float = self._outside_rot_y

        # View mode
        self.view_outside: bool = True

        # Interaction
        self._dragging: bool = False
        self._last_mouse_pos: Optional[QPoint] = None

        # Highlights (same API as StarMapWidget)
        self.hovered_object: Optional[CatalogObject] = None
        self.selected_object: Optional[CatalogObject] = None
        self.target_object: Optional[CatalogObject] = None
        self.revealed_answer: Optional[CatalogObject] = None
        self.result_clicked_object: Optional[CatalogObject] = None
        self.result_target_object: Optional[CatalogObject] = None
        self.result_is_correct: Optional[bool] = None

        # Pointer tool placeholders (API compatibility)
        self.pointer_anchor: Optional[CatalogObject] = None
        self.pointer_target: Optional[CatalogObject] = None
        self.pointer_path: List[CatalogObject] = []

        # Rendering
        self.show_grid: bool = True
        self.show_labels: bool = True
        self.show_hover_label: bool = True
        self.show_stars: bool = True
        self.show_deep_sky: bool = True
        self.show_constellation_lines: bool = True
        self.show_constellation_labels: bool = True
        self.show_earth: bool = True
        self.explore_mode_active: bool = False
        self.max_visible_magnitude: float = 6.5

        # Projected objects for hit testing: (obj, sx, sy, radius, depth)
        self._projected_objects: List[Tuple[CatalogObject, float, float, float, float]] = []

    # ------------------------------------------------------------------
    # PUBLIC API
    # ------------------------------------------------------------------

    def clear_highlights(self) -> None:
        self.hovered_object = None
        self.selected_object = None
        self.target_object = None
        self.revealed_answer = None
        self.result_clicked_object = None
        self.result_target_object = None
        self.result_is_correct = None
        self.pointer_anchor = None
        self.pointer_target = None
        self.pointer_path = []
        self.update()

    def set_target(self, target: Optional[CatalogObject]) -> None:
        self.target_object = target
        self.update()

    def highlight_result(self, clicked_object: Optional[CatalogObject],
                         target_object: Optional[CatalogObject],
                         is_correct: bool) -> None:
        self.result_clicked_object = clicked_object
        self.result_target_object = target_object
        self.result_is_correct = is_correct
        self.selected_object = clicked_object
        self.update()

    def show_answer(self, target_object: CatalogObject) -> None:
        self.revealed_answer = target_object
        self.target_object = target_object
        self._rotate_to_object(target_object)
        self.update()

    def set_view_mode(self, mode: str) -> None:
        pass

    def set_facing(self, az_deg: float) -> None:
        pass

    def toggle_inside_outside(self) -> None:
        """Toggle between inside and outside view with proper rotation state."""
        # Save current rotation to the active mode
        if self.view_outside:
            self._outside_rot_x = self.rot_x
            self._outside_rot_y = self.rot_y
        else:
            self._inside_rot_x = self.rot_x
            self._inside_rot_y = self.rot_y

        # Switch mode
        self.view_outside = not self.view_outside

        # Restore the other mode's rotation
        if self.view_outside:
            self.rot_x = self._outside_rot_x
            self.rot_y = self._outside_rot_y
        else:
            self.rot_x = self._inside_rot_x
            self.rot_y = self._inside_rot_y

        self.update()

    def navigate_to(self, preset: str) -> None:
        """Navigate to a preset view orientation.

        Presets work differently for outside (globe) and inside (dome):
        - Outside: rotates the globe so the preset direction faces camera
        - Inside: points the gaze towards that part of the sky
        """
        if preset == "your_sky":
            # Show what's overhead right now
            if self.view_outside:
                self.rot_x = self.observer_lat
                self.rot_y = 0.0
            else:
                # Look at zenith
                self.rot_x = 80.0
                self.rot_y = 0.0
        elif preset == "zenith":
            if self.view_outside:
                self.rot_x = -89.0
                self.rot_y = 0.0
            else:
                self.rot_x = 80.0
                self.rot_y = 0.0
        elif preset == "south":
            if self.view_outside:
                self.rot_x = self.observer_lat
                self.rot_y = 0.0
            else:
                self.rot_x = 20.0
                self.rot_y = 0.0   # _alt_az_to_3d has south along +Y at az=180 with rot_y=0
        elif preset == "north":
            if self.view_outside:
                self.rot_x = self.observer_lat
                self.rot_y = 180.0
            else:
                self.rot_x = 20.0
                self.rot_y = 180.0
        elif preset == "east":
            if self.view_outside:
                self.rot_x = self.observer_lat
                self.rot_y = 90.0
            else:
                self.rot_x = 20.0
                self.rot_y = 90.0
        elif preset == "west":
            if self.view_outside:
                self.rot_x = self.observer_lat
                self.rot_y = 270.0
            else:
                self.rot_x = 20.0
                self.rot_y = 270.0
        elif preset == "scp":
            if self.view_outside:
                self.rot_x = -89.0
                self.rot_y = 0.0
            else:
                # SCP is at alt=|lat|, az=180 from southern hemisphere
                self.rot_x = abs(self.observer_lat)
                self.rot_y = 0.0
        elif preset == "ncp":
            if self.view_outside:
                self.rot_x = 89.0
                self.rot_y = 0.0
            else:
                self.rot_x = -abs(self.observer_lat)
                self.rot_y = 180.0

        # Save to the active mode's state
        if self.view_outside:
            self._outside_rot_x = self.rot_x
            self._outside_rot_y = self.rot_y
        else:
            self._inside_rot_x = self.rot_x
            self._inside_rot_y = self.rot_y

        self.update()

    def refresh_time(self) -> None:
        if self.auto_time:
            self.lst_deg = current_lst(self.observer_lon, self.utc_offset)
            self.update()

    def set_lst(self, lst_deg: float) -> None:
        self.lst_deg = lst_deg % 360.0
        self.auto_time = False
        self.update()

    @property
    def view_mode(self) -> str:
        return "sphere"

    # ------------------------------------------------------------------
    # DATA
    # ------------------------------------------------------------------

    def _load_catalogs(self) -> None:
        self.stars = []
        self.deep_sky_objects = []
        self.all_objects = []
        self.star_index = {}
        self.constellation_lines = {}
        self.constellation_metadata = {}

        try:
            self.stars = [obj for obj in load_star_catalog()
                          if float(obj.get("magnitude", 99.0)) <= 8.0]
        except Exception:
            self.stars = []
        try:
            self.deep_sky_objects = load_deep_sky_catalog()
        except Exception:
            self.deep_sky_objects = []

        self.all_objects = list(self.stars) + list(self.deep_sky_objects)
        self.star_index = {
            str(obj.get("id", "")).strip(): obj
            for obj in self.stars if str(obj.get("id", "")).strip()
        }
        try:
            self.constellation_lines = load_constellation_lines()
        except Exception:
            self.constellation_lines = {}
        try:
            self.constellation_metadata = load_constellation_metadata()
        except Exception:
            self.constellation_metadata = {}

    # ------------------------------------------------------------------
    # 3D MATH
    # ------------------------------------------------------------------

    def _sphere_radius(self) -> float:
        return min(self.width(), self.height()) * 0.38 * self.sphere_zoom

    def _ra_dec_to_3d(self, ra_deg: float, dec_deg: float,
                      r: float = 1.0) -> Tuple[float, float, float]:
        """RA/Dec to 3D. X->RA=0, Y->RA=90, Z->NCP."""
        ra_rad = math.radians(ra_deg)
        dec_rad = math.radians(dec_deg)
        cos_dec = math.cos(dec_rad)
        return (r * cos_dec * math.cos(ra_rad),
                r * cos_dec * math.sin(ra_rad),
                r * math.sin(dec_rad))

    def _ha_dec_to_3d(self, ha_deg: float, dec_deg: float,
                      r: float = 1.0) -> Tuple[float, float, float]:
        """Convert Hour Angle and Declination to 3D on the sphere.

        HA=0, Dec=0 maps to the front of the sphere (-Y direction,
        facing the camera). HA increases westward (towards +X).
        Dec=+90 is the NCP (+Z). This means the observer's meridian
        is always at the front of the globe, and stars move west
        (left to right) as HA increases with time.
        """
        ha_rad = math.radians(ha_deg)
        dec_rad = math.radians(dec_deg)
        cos_dec = math.cos(dec_rad)
        # HA=0 → front (-Y), HA=90° → west (+X for outside view)
        x = r * cos_dec * math.sin(ha_rad)
        y = -r * cos_dec * math.cos(ha_rad)
        z = r * math.sin(dec_rad)
        return x, y, z

    def _alt_az_to_3d(self, alt_deg: float, az_deg: float,
                      r: float = 1.0) -> Tuple[float, float, float]:
        """Convert altitude/azimuth to 3D for inside dome projection.

        Convention for the dome view:
        - Y axis: towards the gaze direction (south by default)
        - X axis: right (west when facing south)
        - Z axis: up (towards zenith)

        Azimuth is measured from north clockwise.
        """
        alt_rad = math.radians(alt_deg)
        az_rad = math.radians(az_deg)
        cos_alt = math.cos(alt_rad)
        x = r * cos_alt * math.sin(az_rad)
        y = -r * cos_alt * math.cos(az_rad)
        z = r * math.sin(alt_rad)
        return x, y, z

    def _rotate_point(self, x: float, y: float,
                      z: float) -> Tuple[float, float, float]:
        """Apply user rotation (drag/arrow keys). Camera looks along -Y."""
        # Spin around Z axis
        ry = math.radians(self.rot_y)
        cos_ry, sin_ry = math.cos(ry), math.sin(ry)
        x1 = x * cos_ry - y * sin_ry
        y1 = x * sin_ry + y * cos_ry
        z1 = z

        # Tilt around X axis
        rx = math.radians(self.rot_x)
        cos_rx, sin_rx = math.cos(rx), math.sin(rx)
        x2 = x1
        y2 = y1 * cos_rx - z1 * sin_rx
        z2 = y1 * sin_rx + z1 * cos_rx

        return x2, y2, z2

    # ------------------------------------------------------------------
    # OUTSIDE PROJECTION (looking at globe from distance)
    # ------------------------------------------------------------------

    def _project_outside(self, x: float, y: float,
                         z: float) -> Tuple[float, float, float]:
        """Perspective project rotated 3D -> screen. depth<0 = front face."""
        cx = self.width() / 2.0
        cy = self.height() / 2.0
        R = self._sphere_radius()
        pd = R * 4.0
        scale = pd / (pd + y) if (pd + y) > 0.1 else 10.0
        sx = cx + x * R * scale
        sy = cy - z * R * scale
        return sx, sy, y

    # ------------------------------------------------------------------
    # INSIDE PROJECTION (standing at centre looking outward)
    # ------------------------------------------------------------------

    def _project_inside(self, x: float, y: float,
                        z: float) -> Tuple[float, float, float]:
        """
        Angular/fisheye projection from observer at the centre.

        The camera sits at the origin looking along +Y.
        Projects using equal-angle mapping so angular distance from
        gaze direction maps linearly to radial screen distance.
        """
        cx = self.width() / 2.0
        cy = self.height() / 2.0
        R = min(self.width(), self.height()) * 0.45 * self.sphere_zoom

        d_xz = math.sqrt(x * x + z * z)
        if d_xz < 1e-12 and y > 0:
            return cx, cy, -1.0

        theta = math.atan2(d_xz, y)  # 0 = ahead, pi = behind
        screen_r = (theta / math.pi) * R * 2.0

        if d_xz > 1e-12:
            # Mirror X so east/west are correct when looking at the sky
            screen_angle = math.atan2(-z, -x)
        else:
            screen_angle = 0.0

        sx = cx + screen_r * math.cos(screen_angle)
        sy = cy + screen_r * math.sin(screen_angle)

        return sx, sy, -y

    # ------------------------------------------------------------------
    # UNIFIED PROJECTION API
    # ------------------------------------------------------------------

    def _sky_to_screen(self, ra_deg: float, dec_deg: float,
                       r: float = 1.0) -> Tuple[float, float, float]:
        """Project RA/Dec to screen coordinates.

        Outside mode: converts RA to Hour Angle (HA = LST - RA) so
        that stars are positioned relative to the observer's meridian.
        HA=0 means the star is on the meridian above the observer.
        As time advances, HA increases and the star moves westward —
        exactly matching the real sky. The HA/Dec coordinates are then
        placed on the sphere using the same projection as inside mode
        uses for Alt/Az, ensuring consistency.

        Inside mode: computes the star's actual Alt/Az position
        using the observer's latitude and current LST, then projects
        as a dome/fisheye view.
        """
        if self.view_outside:
            # Convert RA to Hour Angle: HA = LST - RA
            # HA=0 = on meridian, HA>0 = west, HA<0 = east
            ha_deg = (self.lst_deg - ra_deg) % 360.0
            # Place the star on the celestial sphere using HA and Dec
            # HA replaces RA so the sky rotates with sidereal time
            # and aligns correctly with the Earth's observer position
            x, y, z = self._ha_dec_to_3d(ha_deg, dec_deg, r)
            rx, ry, rz = self._rotate_point(x, y, z)
            return self._project_outside(rx, ry, rz)
        else:
            # Inside: convert to Alt/Az first for accurate sky positions
            alt, az = ra_dec_to_alt_az(
                ra_deg, dec_deg, self.lst_deg, self.observer_lat)
            x, y, z = self._alt_az_to_3d(alt, az, r)
            rx, ry, rz = self._rotate_point(x, y, z)
            return self._project_inside(rx, ry, rz)

    def _earth_to_screen(self, lat: float, lon: float,
                         r: float = 1.0) -> Tuple[float, float, float]:
        """Project geographic lat/lon to screen.
        Earth uses the same HA-based frame so the observer's position
        always sits at HA=0 (on the meridian) on the globe."""
        # Observer's own longitude → HA=0 (meridian)
        # Other longitudes offset by their difference
        # Longitudes east of observer have negative HA (east side)
        ha_equiv = -(lon - self.observer_lon) % 360.0
        x, y, z = self._ha_dec_to_3d(ha_equiv, lat, r)
        rx, ry, rz = self._rotate_point(x, y, z)
        if self.view_outside:
            return self._project_outside(rx, ry, rz)
        else:
            return self._project_inside(rx, ry, rz)

    def _is_front_face(self, depth: float) -> bool:
        return depth < 0.05

    def _is_on_screen(self, x: float, y: float,
                      margin: float = 0.0) -> bool:
        return (-margin <= x <= self.width() + margin
                and -margin <= y <= self.height() + margin)

    # ------------------------------------------------------------------
    # PAINTING
    # ------------------------------------------------------------------

    def paintEvent(self, event: QPaintEvent) -> None:
        if self.auto_time:
            self.lst_deg = current_lst(self.observer_lon, self.utc_offset)

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setRenderHint(QPainter.TextAntialiasing, True)

        painter.fillRect(self.rect(), QColor(6, 8, 16))

        if self.view_outside:
            self._paint_outside(painter)
        else:
            self._paint_inside(painter)

        self._draw_highlights(painter)
        self._draw_overlay_info(painter)
        painter.end()

    def _paint_outside(self, painter: QPainter) -> None:
        """Render the outside (globe) view."""
        self._draw_sphere_outline(painter)

        # Back face (dim)
        self._draw_grid(painter, front=False)
        self._draw_constellation_lines_pass(painter, front=False)
        self._draw_objects_pass(painter, front=False)

        # Earth at centre
        if self.show_earth:
            self._draw_earth(painter)

        # Front face (bright)
        self._draw_grid(painter, front=True)
        self._draw_constellation_lines_pass(painter, front=True)
        self._draw_objects_pass(painter, front=True)
        self._draw_constellation_labels_pass(painter)

    def _paint_inside(self, painter: QPainter) -> None:
        """Render the inside (dome) view — sky fills the viewport."""
        # Inside: everything rendered as front-facing
        self._draw_inside_horizon(painter)
        self._draw_grid(painter, front=True)
        self._draw_constellation_lines_pass(painter, front=True)
        self._draw_objects_pass(painter, front=True)
        self._draw_constellation_labels_pass(painter)

    # ------------------------------------------------------------------
    # SPHERE OUTLINE & EARTH
    # ------------------------------------------------------------------

    def _draw_sphere_outline(self, painter: QPainter) -> None:
        cx = self.width() / 2.0
        cy = self.height() / 2.0
        R = self._sphere_radius()
        pen = QPen(QColor(30, 45, 70))
        pen.setWidth(1)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)
        painter.drawEllipse(QPointF(cx, cy), R, R)

    def _draw_earth(self, painter: QPainter) -> None:
        """Draw Earth at centre with orientation markings.

        Shows: lat/lon grid, equator, tropics, poles on Earth,
        continent reference points, Greenwich meridian, observer
        position with detected city name, and celestial pole labels.
        """
        cx = self.width() / 2.0
        cy = self.height() / 2.0
        er = self._sphere_radius() * 0.10

        # Earth body
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(15, 40, 65, 200))
        painter.drawEllipse(QPointF(cx, cy), er, er)

        # Outline
        pen = QPen(QColor(50, 90, 130, 200))
        pen.setWidth(1)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)
        painter.drawEllipse(QPointF(cx, cy), er, er)

        earth_r = 0.10

        # --- Latitude circles every 30° ---
        lat_pen = QPen(QColor(35, 60, 90, 100))
        lat_pen.setWidth(1)
        for lat in range(-60, 91, 30):
            painter.setPen(lat_pen)
            self._draw_earth_circle(painter, lat, is_lat=True, r=earth_r)

        # --- Equator (bright blue) ---
        eq_pen = QPen(QColor(80, 140, 200, 200))
        eq_pen.setWidth(2)
        painter.setPen(eq_pen)
        self._draw_earth_circle(painter, 0, is_lat=True, r=earth_r)

        # --- Tropics (subtle dashed) ---
        tropic_pen = QPen(QColor(70, 110, 60, 120))
        tropic_pen.setWidth(1)
        tropic_pen.setStyle(Qt.DashLine)
        painter.setPen(tropic_pen)
        self._draw_earth_circle(painter, 23.44, is_lat=True, r=earth_r)   # Cancer
        self._draw_earth_circle(painter, -23.44, is_lat=True, r=earth_r)  # Capricorn

        # --- Arctic/Antarctic circles ---
        arctic_pen = QPen(QColor(100, 160, 220, 100))
        arctic_pen.setWidth(1)
        arctic_pen.setStyle(Qt.DashLine)
        painter.setPen(arctic_pen)
        self._draw_earth_circle(painter, 66.56, is_lat=True, r=earth_r)   # Arctic
        self._draw_earth_circle(painter, -66.56, is_lat=True, r=earth_r)  # Antarctic

        # --- Longitude lines every 45° ---
        lon_pen = QPen(QColor(35, 60, 90, 80))
        lon_pen.setWidth(1)
        for lon in range(0, 360, 45):
            painter.setPen(lon_pen)
            self._draw_earth_circle(painter, lon, is_lat=False, r=earth_r)

        # --- Greenwich meridian (green) ---
        gm_pen = QPen(QColor(80, 160, 80, 180))
        gm_pen.setWidth(1)
        painter.setPen(gm_pen)
        self._draw_earth_circle(painter, 0, is_lat=False, r=earth_r)

        # --- North Pole marker on Earth ---
        np_x, np_y, np_d = self._earth_to_screen(90, 0, earth_r)
        if self._is_front_face(np_d):
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(120, 180, 240))
            painter.drawEllipse(QPointF(np_x, np_y), 2.5, 2.5)
            font = QFont()
            font.setPointSize(6)
            painter.setFont(font)
            painter.setPen(QColor(140, 190, 240))
            painter.drawText(int(np_x) + 4, int(np_y) - 2, "N")

        # --- South Pole marker on Earth ---
        sp_x, sp_y, sp_d = self._earth_to_screen(-90, 0, earth_r)
        if self._is_front_face(sp_d):
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(120, 180, 240))
            painter.drawEllipse(QPointF(sp_x, sp_y), 2.5, 2.5)
            font = QFont()
            font.setPointSize(6)
            painter.setFont(font)
            painter.setPen(QColor(140, 190, 240))
            painter.drawText(int(sp_x) + 4, int(sp_y) + 6, "S")

        # --- Continent reference points ---
        # Small dim dots at recognisable locations so the user
        # can see where landmasses roughly sit
        _CONTINENT_REFS = [
            # (lat, lon, label)
            (48.0, 2.0, "EU"),       # Europe (Paris)
            (35.0, 139.0, "JP"),     # Japan
            (40.0, -100.0, "NA"),    # North America (central US)
            (-15.0, -60.0, "SA"),    # South America (Brazil)
            (5.0, 20.0, "AF"),       # Africa (central)
            (-25.0, 135.0, "AU"),    # Australia
            (-80.0, 0.0, "AN"),      # Antarctica
            (30.0, 80.0, "AS"),      # Asia (India/China border)
        ]
        font = QFont()
        font.setPointSize(6)
        painter.setFont(font)
        for c_lat, c_lon, c_label in _CONTINENT_REFS:
            c_x, c_y, c_d = self._earth_to_screen(c_lat, c_lon, earth_r)
            if self._is_front_face(c_d):
                painter.setPen(Qt.NoPen)
                painter.setBrush(QColor(60, 110, 60, 140))
                painter.drawEllipse(QPointF(c_x, c_y), 1.8, 1.8)
                painter.setPen(QColor(80, 130, 80, 160))
                painter.drawText(int(c_x) + 3, int(c_y) + 3, c_label)

        # --- Observer position (bright yellow with city name) ---
        ox, oy, od = self._earth_to_screen(
            self.observer_lat, self.observer_lon, earth_r)
        city = getattr(self, 'observer_city', 'You')
        if self._is_front_face(od):
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(255, 200, 60))
            painter.drawEllipse(QPointF(ox, oy), 3.5, 3.5)
            font = QFont()
            font.setPointSize(7)
            font.setBold(True)
            painter.setFont(font)
            painter.setPen(QColor(255, 220, 100))
            painter.drawText(int(ox) + 5, int(oy) - 3, city)
            font.setBold(False)
            painter.setFont(font)
        else:
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(120, 100, 40, 100))
            painter.drawEllipse(QPointF(ox, oy), 2.5, 2.5)

        # --- Rotation axis through celestial poles ---
        nx, ny, nd = self._sky_to_screen(0, 90, 0.16)
        sx_p, sy_p, sd = self._sky_to_screen(0, -90, 0.16)
        axis_pen = QPen(QColor(100, 160, 220, 120))
        axis_pen.setWidth(1)
        axis_pen.setStyle(Qt.DashLine)
        painter.setPen(axis_pen)
        painter.drawLine(QPointF(nx, ny), QPointF(sx_p, sy_p))

        # --- Celestial pole labels (on the sphere, not Earth) ---
        font = QFont()
        font.setPointSize(8)
        font.setBold(True)
        painter.setFont(font)

        npx, npy, npd = self._sky_to_screen(0, 90, 1.08)
        painter.setPen(QColor(140, 180, 230) if self._is_front_face(npd)
                       else QColor(55, 75, 100))
        painter.drawText(int(npx) - 10, int(npy) - 6, "NCP")

        spx, spy, spd = self._sky_to_screen(0, -90, 1.08)
        painter.setPen(QColor(140, 180, 230) if self._is_front_face(spd)
                       else QColor(55, 75, 100))
        painter.drawText(int(spx) - 10, int(spy) + 14, "SCP")

        font.setBold(False)
        painter.setFont(font)

    def _draw_earth_circle(self, painter: QPainter, value: float,
                           is_lat: bool, r: float) -> None:
        """Draw a lat or lon circle on Earth."""
        segments = 36
        prev = None
        for i in range(segments + 1):
            if is_lat:
                t = (i / segments) * 360.0
                sx, sy, d = self._earth_to_screen(value, t, r)
            else:
                t = -90.0 + (i / segments) * 180.0
                sx, sy, d = self._earth_to_screen(t, value, r)
            if prev is not None:
                p_sx, p_sy, p_d = prev
                if self._is_front_face(p_d) and self._is_front_face(d):
                    painter.drawLine(QPointF(p_sx, p_sy), QPointF(sx, sy))
            prev = (sx, sy, d)

    # ------------------------------------------------------------------
    # INSIDE VIEW HELPERS
    # ------------------------------------------------------------------

    def _draw_inside_horizon(self, painter: QPainter) -> None:
        """Draw the horizon circle and compass for inside dome view.

        Uses Alt/Az projection so the horizon is drawn at Alt=0
        as seen by the observer, with compass directions labelled.
        """
        # Draw horizon circle (Alt = 0°) as a series of segments
        horizon_pen = QPen(QColor(80, 65, 40, 160))
        horizon_pen.setWidth(2)
        painter.setPen(horizon_pen)

        segments = 72
        prev = None
        for i in range(segments + 1):
            az = (i / segments) * 360.0
            x, y, z = self._alt_az_to_3d(0.0, az)
            rx, ry, rz = self._rotate_point(x, y, z)
            sx, sy, d = self._project_inside(rx, ry, rz)
            if prev is not None:
                p_sx, p_sy = prev
                if self._is_on_screen(p_sx, p_sy, 50) or self._is_on_screen(sx, sy, 50):
                    painter.drawLine(QPointF(p_sx, p_sy), QPointF(sx, sy))
            prev = (sx, sy)

        # Compass labels at the horizon
        compass = {0: "N", 45: "NE", 90: "E", 135: "SE",
                   180: "S", 225: "SW", 270: "W", 315: "NW"}
        font = QFont()
        font.setPointSize(8)
        font.setBold(True)
        painter.setFont(font)

        for az, label in compass.items():
            x, y, z = self._alt_az_to_3d(-2.0, float(az))  # slightly below horizon for label
            rx, ry, rz = self._rotate_point(x, y, z)
            sx, sy, d = self._project_inside(rx, ry, rz)
            if self._is_on_screen(sx, sy, 20):
                painter.setPen(QColor(140, 120, 70) if label in ("N", "S", "E", "W")
                               else QColor(100, 90, 55))
                painter.drawText(int(sx) - 6, int(sy) + 5, label)

        font.setBold(False)
        painter.setFont(font)

        # Zenith marker
        x, y, z = self._alt_az_to_3d(90.0, 0.0)
        rx, ry, rz = self._rotate_point(x, y, z)
        sx, sy, d = self._project_inside(rx, ry, rz)
        if self._is_on_screen(sx, sy, 30):
            painter.setPen(QColor(100, 130, 170, 120))
            font.setPointSize(8)
            painter.setFont(font)
            painter.drawText(int(sx) - 16, int(sy) - 8, "Zenith")

    # ------------------------------------------------------------------
    # GRID
    # ------------------------------------------------------------------

    def _draw_grid(self, painter: QPainter, front: bool) -> None:
        if not self.show_grid:
            return

        if front:
            grid_color = QColor(35, 55, 85)
            equator_color = QColor(70, 100, 140)
            label_color = QColor(150, 135, 85)
        else:
            grid_color = QColor(18, 28, 42)
            equator_color = QColor(30, 45, 65)
            label_color = QColor(70, 65, 45)

        grid_pen = QPen(grid_color)
        grid_pen.setWidth(1)
        eq_pen = QPen(equator_color)
        eq_pen.setWidth(2)

        font = QFont()
        font.setPointSize(7)
        painter.setFont(font)

        for dec in range(-75, 91, 15):
            painter.setPen(eq_pen if dec == 0 else grid_pen)
            self._draw_dec_circle(painter, dec, front)
            if dec % 30 == 0:
                lx, ly, ld = self._sky_to_screen(0, dec, 1.04)
                if self._is_front_face(ld) == front:
                    painter.setPen(label_color)
                    painter.drawText(int(lx) + 4, int(ly) + 3, f"{dec:+d}°")

        for ra_h in range(0, 24, 2):
            ra_deg = ra_h * 15.0
            painter.setPen(grid_pen)
            self._draw_ra_line(painter, ra_deg, front)
            lx, ly, ld = self._sky_to_screen(ra_deg, 0, 1.05)
            if self._is_front_face(ld) == front:
                painter.setPen(label_color)
                painter.drawText(int(lx) + 4, int(ly) + 3, f"{ra_h:02d}h")

    def _draw_dec_circle(self, painter: QPainter,
                         dec: float, front: bool) -> None:
        segments = 72
        prev = None
        for i in range(segments + 1):
            ra = (i / segments) * 360.0
            sx, sy, d = self._sky_to_screen(ra, dec)
            if prev is not None:
                p_sx, p_sy, p_d = prev
                if self._is_front_face(p_d) == front and self._is_front_face(d) == front:
                    if self._is_on_screen(p_sx, p_sy, 50) or self._is_on_screen(sx, sy, 50):
                        painter.drawLine(QPointF(p_sx, p_sy), QPointF(sx, sy))
            prev = (sx, sy, d)

    def _draw_ra_line(self, painter: QPainter,
                      ra_deg: float, front: bool) -> None:
        segments = 36
        prev = None
        for i in range(segments + 1):
            dec = -90.0 + (i / segments) * 180.0
            sx, sy, d = self._sky_to_screen(ra_deg, dec)
            if prev is not None:
                p_sx, p_sy, p_d = prev
                if self._is_front_face(p_d) == front and self._is_front_face(d) == front:
                    if self._is_on_screen(p_sx, p_sy, 50) or self._is_on_screen(sx, sy, 50):
                        painter.drawLine(QPointF(p_sx, p_sy), QPointF(sx, sy))
            prev = (sx, sy, d)

    # ------------------------------------------------------------------
    # CONSTELLATION LINES & LABELS
    # ------------------------------------------------------------------

    def _draw_constellation_lines_pass(self, painter: QPainter,
                                       front: bool) -> None:
        if not self.show_constellation_lines or not self.constellation_lines:
            return
        if front:
            pen = QPen(QColor(65, 105, 170, 180))
        else:
            pen = QPen(QColor(25, 40, 65, 100))
        pen.setWidth(1)
        painter.setPen(pen)

        for _, segments in self.constellation_lines.items():
            for seg in segments:
                if len(seg) != 2:
                    continue
                sa = self.star_index.get(seg[0])
                sb = self.star_index.get(seg[1])
                if not sa or not sb:
                    continue
                sx1, sy1, d1 = self._sky_to_screen(
                    float(sa.get("ra_deg", 0)), float(sa.get("dec_deg", 0)))
                sx2, sy2, d2 = self._sky_to_screen(
                    float(sb.get("ra_deg", 0)), float(sb.get("dec_deg", 0)))
                if self._is_front_face(d1) == front and self._is_front_face(d2) == front:
                    if self._is_on_screen(sx1, sy1, 80) or self._is_on_screen(sx2, sy2, 80):
                        painter.drawLine(QPointF(sx1, sy1), QPointF(sx2, sy2))

    def _draw_constellation_labels_pass(self, painter: QPainter) -> None:
        if not self.show_constellation_labels or not self.constellation_metadata:
            return
        font = QFont()
        font.setPointSize(9)
        painter.setFont(font)

        for _, meta in self.constellation_metadata.items():
            ra = meta.get("label_ra_deg")
            dec = meta.get("label_dec_deg")
            if ra is None or dec is None:
                continue
            sx, sy, d = self._sky_to_screen(float(ra), float(dec))
            if not self._is_front_face(d):
                continue
            if not self._is_on_screen(sx, sy, 30):
                continue
            alpha = max(80, min(180, int(180 + d * 200)))
            painter.setPen(QColor(100, 140, 185, alpha))
            painter.drawText(int(sx), int(sy), str(meta.get("abbr", "")))

    # ------------------------------------------------------------------
    # OBJECTS
    # ------------------------------------------------------------------

    def _draw_objects_pass(self, painter: QPainter, front: bool) -> None:
        if front:
            self._projected_objects.clear()
        if self.show_stars:
            self._draw_stars_pass(painter, front)
        if self.show_deep_sky:
            self._draw_dso_pass(painter, front)

    def _draw_stars_pass(self, painter: QPainter, front: bool) -> None:
        for star in self.stars:
            mag = float(star.get("magnitude", 99.0))
            if mag > self.max_visible_magnitude:
                continue
            ra = float(star.get("ra_deg", 0.0))
            dec = float(star.get("dec_deg", 0.0))
            sx, sy, d = self._sky_to_screen(ra, dec)
            if self._is_front_face(d) != front:
                continue
            if not self._is_on_screen(sx, sy, 20):
                continue

            r = self._star_radius(mag, front)
            color = self._star_color(mag) if front else QColor(60, 70, 90)
            painter.setPen(Qt.NoPen)
            painter.setBrush(color)
            painter.drawEllipse(QPointF(sx, sy), r, r)

            if front:
                self._projected_objects.append((star, sx, sy, r, d))
            if front and self.show_labels and mag <= 2.0:
                painter.setPen(QColor(210, 220, 240))
                f = painter.font()
                f.setPointSize(8)
                painter.setFont(f)
                painter.drawText(int(sx + r + 3), int(sy - r - 1),
                                 star.get("name", ""))

    def _draw_dso_pass(self, painter: QPainter, front: bool) -> None:
        for obj in self.deep_sky_objects:
            mag = float(obj.get("magnitude", 99.0))
            if mag > max(self.max_visible_magnitude + 3.0, 10.0):
                continue
            ra = float(obj.get("ra_deg", 0.0))
            dec = float(obj.get("dec_deg", 0.0))
            sx, sy, d = self._sky_to_screen(ra, dec)
            if self._is_front_face(d) != front:
                continue
            if not self._is_on_screen(sx, sy, 20):
                continue

            r = max(3.0, min(7.0, 6.0 - min(mag, 8.0) * 0.3))
            color = self._dso_color(obj) if front else QColor(50, 55, 70)
            pen = QPen(color)
            pen.setWidth(1)
            painter.setPen(pen)
            painter.setBrush(Qt.NoBrush)

            otype = str(obj.get("object_type", "")).strip().lower()
            if otype == "galaxy":
                painter.drawEllipse(QPointF(sx, sy), r * 1.4, r)
            elif otype in {"globular_cluster", "open_cluster"}:
                painter.drawEllipse(QPointF(sx, sy), r, r)
                painter.drawLine(int(sx - r), int(sy), int(sx + r), int(sy))
                painter.drawLine(int(sx), int(sy - r), int(sx), int(sy + r))
            else:
                painter.drawEllipse(QPointF(sx, sy), r, r)

            if front:
                self._projected_objects.append((obj, sx, sy, max(r, 5.0), d))
            if front and self.show_labels and mag <= 6.0:
                painter.setPen(color)
                f = painter.font()
                f.setPointSize(8)
                painter.setFont(f)
                painter.drawText(int(sx + r + 3), int(sy - r - 1),
                                 obj.get("name", ""))

    # ------------------------------------------------------------------
    # HIGHLIGHTS
    # ------------------------------------------------------------------

    def _draw_highlights(self, painter: QPainter) -> None:
        if self.result_target_object:
            self._draw_obj_ring(painter, self.result_target_object,
                                QColor(100, 220, 255), 14, 2)
        if self.result_clicked_object and self.result_is_correct is False:
            self._draw_obj_ring(painter, self.result_clicked_object,
                                QColor(255, 110, 110), 11, 2)
        if self.result_clicked_object and self.result_is_correct is True:
            self._draw_obj_ring(painter, self.result_clicked_object,
                                QColor(120, 255, 140), 13, 2)
        if self.revealed_answer:
            self._draw_obj_crosshair(painter, self.revealed_answer,
                                     QColor(255, 220, 90), 18, 2)
        if self.hovered_object:
            self._draw_obj_ring(painter, self.hovered_object,
                                QColor(255, 255, 255), 10, 1)

        # Pointer tool (distance measurement)
        if self.pointer_anchor:
            self._draw_obj_ring(painter, self.pointer_anchor,
                                QColor(255, 180, 50), 12, 2)
        if self.pointer_target:
            self._draw_obj_ring(painter, self.pointer_target,
                                QColor(255, 180, 50), 12, 2)
        if self.pointer_anchor and self.pointer_target:
            self._draw_pointer_line(painter)

        # Path tool (star-hop chain)
        if len(self.pointer_path) >= 2:
            self._draw_path_lines(painter)
        elif len(self.pointer_path) == 1:
            self._draw_obj_ring(painter, self.pointer_path[0],
                                QColor(130, 220, 130), 12, 2)

    def _draw_pointer_line(self, painter: QPainter) -> None:
        """Draw a dashed measurement line between pointer anchor and target."""
        a = self.pointer_anchor
        t = self.pointer_target
        if not a or not t:
            return

        ax, ay, ad = self._sky_to_screen(
            float(a.get("ra_deg", 0)), float(a.get("dec_deg", 0)))
        tx, ty, td = self._sky_to_screen(
            float(t.get("ra_deg", 0)), float(t.get("dec_deg", 0)))

        if not (self._is_front_face(ad) and self._is_front_face(td)):
            return
        if not (self._is_on_screen(ax, ay, 100) or self._is_on_screen(tx, ty, 100)):
            return

        pen = QPen(QColor(255, 180, 50, 160))
        pen.setWidth(2)
        pen.setStyle(Qt.DashLine)
        painter.setPen(pen)
        painter.drawLine(QPointF(ax, ay), QPointF(tx, ty))

        # Distance label at midpoint
        mx, my = (ax + tx) / 2.0, (ay + ty) / 2.0
        dist = angular_separation_deg(
            float(a.get("ra_deg", 0)), float(a.get("dec_deg", 0)),
            float(t.get("ra_deg", 0)), float(t.get("dec_deg", 0)),
        )
        painter.setPen(QColor(255, 200, 80))
        font = painter.font()
        font.setPointSize(10)
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(int(mx) + 8, int(my) - 8, f"{dist:.1f}°")
        font.setBold(False)
        painter.setFont(font)

    def _draw_path_lines(self, painter: QPainter) -> None:
        """Draw connected path segments with cumulative distances."""
        path = self.pointer_path
        pen = QPen(QColor(130, 220, 130, 180))
        pen.setWidth(2)
        pen.setStyle(Qt.DashLine)

        for i in range(len(path)):
            obj = path[i]
            sx, sy, d = self._sky_to_screen(
                float(obj.get("ra_deg", 0)), float(obj.get("dec_deg", 0)))

            if not self._is_front_face(d):
                continue

            # Draw node marker (green ring)
            ring_pen = QPen(QColor(130, 220, 130))
            ring_pen.setWidth(2)
            painter.setPen(ring_pen)
            painter.setBrush(Qt.NoBrush)
            painter.drawEllipse(QPointF(sx, sy), 10, 10)

            # Draw number label
            painter.setPen(QColor(130, 220, 130))
            font = painter.font()
            font.setPointSize(8)
            font.setBold(True)
            painter.setFont(font)
            painter.drawText(int(sx) - 4, int(sy) + 4, str(i + 1))
            font.setBold(False)
            painter.setFont(font)

            # Draw line to previous node
            if i > 0:
                prev = path[i - 1]
                px, py, pd = self._sky_to_screen(
                    float(prev.get("ra_deg", 0)),
                    float(prev.get("dec_deg", 0)))

                if self._is_front_face(pd):
                    painter.setPen(pen)
                    painter.drawLine(QPointF(px, py), QPointF(sx, sy))

                    # Leg distance at midpoint
                    dist = angular_separation_deg(
                        float(prev.get("ra_deg", 0)),
                        float(prev.get("dec_deg", 0)),
                        float(obj.get("ra_deg", 0)),
                        float(obj.get("dec_deg", 0)),
                    )
                    mx, my = (px + sx) / 2.0, (py + sy) / 2.0
                    painter.setPen(QColor(160, 240, 160))
                    font = painter.font()
                    font.setPointSize(9)
                    painter.setFont(font)
                    painter.drawText(int(mx) + 6, int(my) - 6, f"{dist:.1f}°")

    def _draw_obj_ring(self, painter: QPainter, obj: CatalogObject,
                       color: QColor, radius: float, width: int) -> None:
        sx, sy, d = self._sky_to_screen(
            float(obj.get("ra_deg", 0)), float(obj.get("dec_deg", 0)))
        if not self._is_front_face(d):
            return
        if not self._is_on_screen(sx, sy, 50):
            return
        pen = QPen(color)
        pen.setWidth(width)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)
        painter.drawEllipse(QPointF(sx, sy), radius, radius)

    def _draw_obj_crosshair(self, painter: QPainter, obj: CatalogObject,
                            color: QColor, size: float, width: int) -> None:
        sx, sy, d = self._sky_to_screen(
            float(obj.get("ra_deg", 0)), float(obj.get("dec_deg", 0)))
        if not self._is_front_face(d):
            return
        if not self._is_on_screen(sx, sy, 50):
            return
        pen = QPen(color)
        pen.setWidth(width)
        painter.setPen(pen)
        s = size
        painter.drawLine(QPointF(sx - s, sy), QPointF(sx - 5, sy))
        painter.drawLine(QPointF(sx + 5, sy), QPointF(sx + s, sy))
        painter.drawLine(QPointF(sx, sy - s), QPointF(sx, sy - 5))
        painter.drawLine(QPointF(sx, sy + 5), QPointF(sx, sy + s))

    # ------------------------------------------------------------------
    # OVERLAY
    # ------------------------------------------------------------------

    def _draw_overlay_info(self, painter: QPainter) -> None:
        margin = 10
        pr = QRectF(margin, self.height() - 82, 580, 72)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(0, 0, 0, 150))
        painter.drawRoundedRect(pr, 8, 8)
        painter.setPen(QColor(220, 230, 240))
        font = painter.font()
        font.setPointSize(9)
        painter.setFont(font)

        view_label = "Globe" if self.view_outside else "Sky Dome"
        city = getattr(self, 'observer_city', '?')
        lst_h = self.lst_deg / 15.0
        t1 = (f"Sphere ({view_label})   |   {city} ({self.observer_lat:+.1f}°)   |   "
              f"LST {lst_h:.1f}h   |   Zoom x{self.sphere_zoom:.1f}")
        painter.drawText(pr.adjusted(10, 10, -10, -38),
                         Qt.AlignLeft | Qt.AlignVCenter, t1)

        t2 = (f"Stars [{'On' if self.show_stars else 'Off'}]   "
              f"Deep Sky [{'On' if self.show_deep_sky else 'Off'}]   "
              f"Constellations [{'On' if self.show_constellation_lines else 'Off'}]   "
              f"Earth [{'On' if self.show_earth else 'Off'}]")
        painter.drawText(pr.adjusted(10, 28, -10, -20),
                         Qt.AlignLeft | Qt.AlignVCenter, t2)

        t3 = "Hover: none"
        if self.hovered_object and self.show_hover_label:
            t3 = self._obj_desc(self.hovered_object)
        painter.drawText(pr.adjusted(10, 45, -10, -4),
                         Qt.AlignLeft | Qt.AlignVCenter, t3)

    # ------------------------------------------------------------------
    # INTERACTION
    # ------------------------------------------------------------------

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.LeftButton:
            obj = self._nearest_visible_object(
                event.position().x(), event.position().y())
            if obj is not None:
                self.selected_object = obj
                self.object_clicked.emit(obj)
                self.update()
            else:
                self._dragging = True
                self._last_mouse_pos = event.pos()
        elif event.button() in (Qt.MiddleButton, Qt.RightButton):
            self._dragging = True
            self._last_mouse_pos = event.pos()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._dragging and self._last_mouse_pos is not None:
            d = event.pos() - self._last_mouse_pos
            sensitivity = 0.4
            if self.view_outside:
                self.rot_y += d.x() * sensitivity
                self.rot_x += d.y() * sensitivity
            else:
                # Inside: drag is inverted (turning your head)
                self.rot_y -= d.x() * sensitivity
                self.rot_x -= d.y() * sensitivity
            self.rot_x = max(-89.0, min(89.0, self.rot_x))
            self.rot_y = self.rot_y % 360.0
            self._last_mouse_pos = event.pos()
            self.update()
        else:
            h = self._nearest_visible_object(
                event.position().x(), event.position().y(), 14.0)
            if h != self.hovered_object:
                self.hovered_object = h
                self.update()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() in (Qt.LeftButton, Qt.MiddleButton, Qt.RightButton):
            self._dragging = False
            self._last_mouse_pos = None
        super().mouseReleaseEvent(event)

    def wheelEvent(self, event: QWheelEvent) -> None:
        a = event.angleDelta().y()
        if a == 0:
            return
        zs = 1.12 if a > 0 else 1.0 / 1.12
        self.sphere_zoom = max(0.5, min(4.0, self.sphere_zoom * zs))
        self.update()
        super().wheelEvent(event)

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        obj = self._nearest_visible_object(
            event.position().x(), event.position().y())
        if obj is not None:
            self._rotate_to_object(obj)
            self.selected_object = obj
            self.update()
        super().mouseDoubleClickEvent(event)

    def keyPressEvent(self, event) -> None:
        k = event.key()

        if k in (Qt.Key_Plus, Qt.Key_Equal):
            self.sphere_zoom = min(4.0, self.sphere_zoom * 1.15)
            self.update(); return
        if k in (Qt.Key_Minus, Qt.Key_Underscore):
            self.sphere_zoom = max(0.5, self.sphere_zoom / 1.15)
            self.update(); return
        if k == Qt.Key_R:
            if self.view_outside:
                self.rot_x = self.observer_lat
                self.rot_y = 0.0
                self._outside_rot_x = self.rot_x
                self._outside_rot_y = self.rot_y
            else:
                self.rot_x = 40.0
                self.rot_y = 0.0
                self._inside_rot_x = self.rot_x
                self._inside_rot_y = self.rot_y
            self.sphere_zoom = 1.0
            self.update(); return
        if k == Qt.Key_I:
            self.toggle_inside_outside()
            return
        if k == Qt.Key_1:
            self.show_stars = not self.show_stars; self.update(); return
        if k == Qt.Key_2:
            self.show_deep_sky = not self.show_deep_sky; self.update(); return
        if k == Qt.Key_3:
            self.show_constellation_lines = not self.show_constellation_lines
            self.update(); return

        rot_step = 8.0
        sign = 1.0 if self.view_outside else -1.0
        if k == Qt.Key_Left:
            self.rot_y = (self.rot_y - rot_step * sign) % 360.0
            self.update(); return
        if k == Qt.Key_Right:
            self.rot_y = (self.rot_y + rot_step * sign) % 360.0
            self.update(); return
        if k == Qt.Key_Up:
            self.rot_x = max(-89.0, self.rot_x - rot_step * sign)
            self.update(); return
        if k == Qt.Key_Down:
            self.rot_x = min(89.0, self.rot_x + rot_step * sign)
            self.update(); return

        super().keyPressEvent(event)

    # ------------------------------------------------------------------
    # HELPERS
    # ------------------------------------------------------------------

    def _nearest_visible_object(self, x: float, y: float,
                                threshold_px: float = 12.0
                                ) -> Optional[CatalogObject]:
        best, best_d = None, float("inf")
        for obj, sx, sy, r, depth in self._projected_objects:
            if not self._is_front_face(depth):
                continue
            d = math.hypot(sx - x, sy - y)
            if d <= max(threshold_px, r + 4.0) and d < best_d:
                best_d, best = d, obj
        return best

    def _rotate_to_object(self, obj: CatalogObject) -> None:
        ra = float(obj.get("ra_deg", 0))
        dec = float(obj.get("dec_deg", 0))
        if self.view_outside:
            self.rot_y = (-ra + 90.0) % 360.0
        else:
            self.rot_y = (ra + 90.0) % 360.0
        self.rot_x = max(-89.0, min(89.0, -dec))

    def _star_radius(self, mag: float, front: bool) -> float:
        if not front:
            return max(0.8, 2.5 - mag * 0.3)
        z = self.sphere_zoom
        r = max(1.0, min(6.0, 5.5 - mag))
        r *= 0.7 + 0.1 * min(z, 3.0)
        return max(1.0, min(8.0, r))

    def _star_color(self, mag: float) -> QColor:
        if mag < 0:   return QColor(225, 235, 255)
        if mag < 1:   return QColor(235, 240, 255)
        if mag < 2.5: return QColor(220, 228, 245)
        return QColor(190, 205, 225)

    def _dso_color(self, obj: CatalogObject) -> QColor:
        t = str(obj.get("object_type", "")).strip().lower()
        if t == "galaxy": return QColor(180, 210, 255)
        if t in {"nebula", "planetary_nebula"}: return QColor(120, 255, 220)
        if t in {"globular_cluster", "open_cluster"}: return QColor(255, 220, 140)
        if t == "supernova_remnant": return QColor(255, 150, 150)
        return QColor(200, 220, 240)

    def _obj_desc(self, obj: CatalogObject) -> str:
        n = obj.get("name", "?")
        c = obj.get("constellation", "?")
        m = obj.get("magnitude", "?")
        t = obj.get("object_type", "?")
        desc = f"{n} | {t} | {c} | mag {m}"
        # Add alt/az for context
        ra = obj.get("ra_deg")
        dec = obj.get("dec_deg")
        if ra is not None and dec is not None:
            alt, az = ra_dec_to_alt_az(
                float(ra), float(dec), self.lst_deg, self.observer_lat)
            dirs = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
            compass = dirs[int((az + 22.5) % 360 / 45)]
            if alt >= 0:
                desc += f" | Alt {alt:.0f}° {compass}"
            else:
                desc += f" | below horizon"
        return desc