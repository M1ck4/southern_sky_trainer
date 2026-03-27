"""
star_map.py

Interactive star map widget for the Astronomy Trainer application.

This widget provides:
- three projection modes: equatorial, polar (planisphere), horizon
- rendering of stars and deep-sky objects
- constellation line drawing
- optional constellation labels
- pan and zoom controls
- click selection of objects
- question target highlighting
- answer reveal support
- time-dependent sky views for polar and horizon modes
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple

from PySide6.QtCore import QPoint, QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QLinearGradient, QMouseEvent, QPainter, QPaintEvent, QPen, QWheelEvent
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
    horizon_view_xy,
    horizon_xy_to_alt_az,
    is_above_horizon,
    map_xy_to_sky,
    polar_stereo_xy,
    ra_dec_to_alt_az,
    sky_to_map_xy,
    DEFAULT_LATITUDE,
    DEFAULT_LONGITUDE,
)

CatalogObject = Dict[str, Any]
ConstellationLines = Dict[str, List[List[str]]]
ConstellationMetadata = Dict[str, Dict[str, Any]]

VIEW_EQUATORIAL = "equatorial"
VIEW_POLAR = "polar"
VIEW_HORIZON = "horizon"


class StarMapWidget(QWidget):
    """Interactive star map widget with multiple projection modes."""

    object_clicked = Signal(dict)
    sky_clicked = Signal(float, float)  # ra_deg, dec_deg for identify tool

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

        # View mode
        self.view_mode: str = VIEW_EQUATORIAL

        # Observer state — auto-detected from system timezone
        _lat, _lon, self.observer_city = detect_observer_location()
        self.observer_lat: float = _lat
        self.observer_lon: float = _lon
        self.utc_offset: float = _detect_utc_offset()
        self.lst_deg: float = current_lst(self.observer_lon, self.utc_offset)
        self.auto_time: bool = True

        # Horizon view
        self.facing_az_deg: float = 180.0
        self.horizon_fov_deg: float = 120.0
        self.horizon_alt_center: float = 35.0  # altitude at vertical centre

        # Polar view
        self.polar_zoom: float = 1.0

        # Equatorial view
        self.zoom_factor: float = 1.0
        self.min_zoom: float = 1.0
        self.max_zoom: float = 25.0
        self.center_ra_deg: float = 180.0
        self.center_dec_deg: float = 0.0

        # Interaction
        self._dragging: bool = False
        self._last_mouse_pos: Optional[QPoint] = None

        # Highlights
        self.hovered_object: Optional[CatalogObject] = None
        self.selected_object: Optional[CatalogObject] = None
        self.target_object: Optional[CatalogObject] = None
        self.revealed_answer: Optional[CatalogObject] = None
        self.result_clicked_object: Optional[CatalogObject] = None
        self.result_target_object: Optional[CatalogObject] = None
        self.result_is_correct: Optional[bool] = None

        # Pointer tool (explore mode)
        self.pointer_anchor: Optional[CatalogObject] = None
        self.pointer_target: Optional[CatalogObject] = None
        self.pointer_path: List[CatalogObject] = []  # for path tool

        # Rendering
        self.show_grid: bool = True
        self.show_sub_grid: bool = True
        self.show_labels: bool = True
        self.show_hover_label: bool = True
        self.show_stars: bool = True
        self.show_deep_sky: bool = True
        self.show_constellation_lines: bool = True
        self.show_constellation_labels: bool = True
        self.show_horizon_clip: bool = True
        self.show_crosshair: bool = True
        self.explore_mode_active: bool = False
        self.invert_ra: bool = True
        self.max_visible_magnitude: float = 6.5

        # Cursor tracking for crosshair / tooltip
        self._cursor_x: float = -1.0
        self._cursor_y: float = -1.0
        self._cursor_ra: Optional[float] = None
        self._cursor_dec: Optional[float] = None
        self._cursor_alt: Optional[float] = None
        self._cursor_az: Optional[float] = None

        self._projected_objects: List[Tuple[CatalogObject, float, float, float]] = []

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
        self._center_on_object(target_object)
        self.update()

    def set_view_mode(self, mode: str) -> None:
        if mode in (VIEW_EQUATORIAL, VIEW_POLAR, VIEW_HORIZON):
            self.view_mode = mode
            self.update()

    def set_facing(self, az_deg: float) -> None:
        self.facing_az_deg = az_deg % 360.0
        self.update()

    def refresh_time(self) -> None:
        if self.auto_time:
            self.lst_deg = current_lst(self.observer_lon, self.utc_offset)
            self.update()

    def set_lst(self, lst_deg: float) -> None:
        self.lst_deg = lst_deg % 360.0
        self.auto_time = False
        self.update()

    # ------------------------------------------------------------------
    # DATA LOADING
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
            self.stars = self._fallback_stars()

        try:
            self.deep_sky_objects = load_deep_sky_catalog()
        except Exception:
            self.deep_sky_objects = self._fallback_deep_sky()

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

    def _fallback_stars(self) -> List[CatalogObject]:
        return [
            {"id": "sirius", "name": "Sirius", "aliases": ["Alpha Canis Majoris"],
             "ra_deg": 101.2872, "dec_deg": -16.7161, "ra_text": format_ra(101.2872),
             "dec_text": format_dec(-16.7161), "magnitude": -1.46,
             "constellation": "Canis Major", "object_type": "star"},
            {"id": "betelgeuse", "name": "Betelgeuse", "aliases": ["Alpha Orionis"],
             "ra_deg": 88.7929, "dec_deg": 7.4071, "ra_text": format_ra(88.7929),
             "dec_text": format_dec(7.4071), "magnitude": 0.42,
             "constellation": "Orion", "object_type": "star"},
        ]

    def _fallback_deep_sky(self) -> List[CatalogObject]:
        return [
            {"id": "m42", "name": "Orion Nebula", "aliases": ["M42"],
             "ra_deg": 83.8221, "dec_deg": -5.3911, "ra_text": format_ra(83.8221),
             "dec_text": format_dec(-5.3911), "magnitude": 4.0,
             "constellation": "Orion", "object_type": "nebula"},
        ]

    # ------------------------------------------------------------------
    # PAINTING
    # ------------------------------------------------------------------

    def paintEvent(self, event: QPaintEvent) -> None:
        if self.auto_time and self.view_mode != VIEW_EQUATORIAL:
            self.lst_deg = current_lst(self.observer_lon, self.utc_offset)

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setRenderHint(QPainter.TextAntialiasing, True)

        self._draw_background(painter)

        if self.view_mode == VIEW_POLAR:
            self._draw_polar_grid(painter)
        elif self.view_mode == VIEW_HORIZON:
            self._draw_horizon_grid(painter)
        else:
            self._draw_equatorial_grid(painter)

        self._draw_constellation_lines(painter)
        self._draw_objects(painter)
        self._draw_constellation_labels(painter)
        self._draw_highlights(painter)

        if self.view_mode == VIEW_HORIZON:
            self._draw_ground_overlay(painter)

        self._draw_cursor_crosshair(painter)
        self._draw_overlay_info(painter)
        painter.end()

    def _draw_background(self, painter: QPainter) -> None:
        painter.fillRect(self.rect(), QColor(8, 12, 20))

    def _draw_ground_overlay(self, painter: QPainter) -> None:
        """
        Draw a darkened ground area below the horizon line with a
        gradient fade to make the transition from sky to ground smooth.
        """
        w, h = float(self.width()), float(self.height())

        # Find the Y position of the horizon (altitude = 0°)
        v_fov = self.horizon_fov_deg * (h / w)
        default_center_alt = v_fov / 2.0
        alt_shift = (self.horizon_alt_center - default_center_alt) / v_fov * h

        # Horizon Y in the base projection (alt=0)
        horizon_y = h + alt_shift

        if horizon_y < 0:
            # Horizon is above the viewport — entire view is ground
            painter.fillRect(0, 0, int(w), int(h), QColor(6, 8, 12, 200))
            return

        if horizon_y > h:
            # Horizon is below the viewport — no ground visible
            return

        # Gradient fade zone: 30 pixels above the horizon line
        fade_height = 30
        fade_top = max(0, int(horizon_y) - fade_height)

        # Draw gradient fade from transparent to ground colour
        gradient = QLinearGradient(0, fade_top, 0, horizon_y)
        gradient.setColorAt(0.0, QColor(6, 8, 12, 0))
        gradient.setColorAt(1.0, QColor(6, 8, 12, 180))
        painter.setPen(Qt.NoPen)
        painter.setBrush(gradient)
        painter.drawRect(0, fade_top, int(w), int(horizon_y) - fade_top + 1)

        # Solid ground below the horizon
        if horizon_y < h:
            painter.setBrush(QColor(6, 8, 12, 210))
            painter.drawRect(0, int(horizon_y), int(w), int(h - horizon_y) + 1)

        # Horizon line — subtle warm glow
        pen = QPen(QColor(80, 65, 40, 140))
        pen.setWidth(1)
        painter.setPen(pen)
        painter.drawLine(0, int(horizon_y), int(w), int(horizon_y))

    def _draw_equatorial_grid(self, painter: QPainter) -> None:
        if not self.show_grid:
            return
        w, h = float(self.width()), float(self.height())

        # Pen styles
        minor = QPen(QColor(25, 35, 55))
        major = QPen(QColor(35, 50, 75))
        sub_pen = QPen(QColor(20, 30, 48))
        sub_pen.setStyle(Qt.DashLine)
        tc = QColor(160, 140, 90)
        tc_sub = QColor(120, 110, 75)
        font = QFont()
        font.setPointSize(8)
        painter.setFont(font)

        # Compute the virtual map dimensions (same as _sky_to_eq)
        map_w = max(w, h * 2.0)
        map_h = map_w / 2.0

        center_ra = self.center_ra_deg % 360.0
        center_dec_clamped = max(-90.0, min(90.0, self.center_dec_deg))
        _, cy_center = sky_to_map_xy(center_ra, center_dec_clamped,
                                      map_w, map_h, invert_ra=self.invert_ra)
        dec_overflow = self.center_dec_deg - center_dec_clamped
        cy_center -= dec_overflow * (map_h / 180.0)

        # Determine sub-grid detail level based on zoom
        z = self.zoom_factor
        dec_sub_step, ra_sub_step_deg = self._grid_sub_steps(z)
        sub_active = self.show_sub_grid and dec_sub_step is not None

        # --- Declination lines ---
        # When sub-grid is active, draw all lines in one unified pass
        # so primary labels blend with the finer grid. When inactive,
        # draw only the primary 15° lines.
        if sub_active:
            step_10 = int(dec_sub_step * 10)
            for dec_10 in range(-900, 901, step_10):
                dec = dec_10 / 10.0
                vy = (90.0 - dec) / 180.0 * map_h
                y = (vy - cy_center) * self.zoom_factor + h / 2.0
                if not (0 <= y <= h):
                    continue
                is_primary = (dec_10 % 150 == 0)
                is_major = (dec_10 % 300 == 0)
                if is_primary:
                    painter.setPen(major if is_major else minor)
                else:
                    painter.setPen(sub_pen)
                painter.drawLine(0, int(y), int(w), int(y))
                # Unified labels: primary lines in bright colour, sub in dim
                painter.setPen(tc if is_primary else tc_sub)
                if dec == int(dec):
                    painter.drawText(8, int(y) - 4, f"{int(dec):+d}°")
                else:
                    painter.drawText(8, int(y) - 4, f"{dec:+.1f}°")
        else:
            for dec in range(-90, 91, 15):
                vy = (90.0 - dec) / 180.0 * map_h
                y = (vy - cy_center) * self.zoom_factor + h / 2.0
                if 0 <= y <= h:
                    painter.setPen(major if dec % 30 == 0 else minor)
                    painter.drawLine(0, int(y), int(w), int(y))
                    painter.setPen(tc)
                    painter.drawText(8, int(y) - 4, f"{dec:+d}°")

        # --- RA lines ---
        # Same unified approach: when sub-grid is active, iterate at
        # the sub-grid resolution and style primary lines differently.
        if sub_active:
            step_10 = int(ra_sub_step_deg * 10)
            for ra_10 in range(0, 3600, step_10):
                ra_d = ra_10 / 10.0
                x, _ = self.sky_to_viewport(ra_d, 0.0)
                if not (0 <= x <= w):
                    continue
                is_primary = (ra_10 % 150 == 0)
                is_major = is_primary and ((ra_10 // 150) % 2 == 0)
                if is_primary:
                    painter.setPen(major if is_major else minor)
                else:
                    painter.setPen(sub_pen)
                painter.drawLine(int(x), 0, int(x), int(h))
                # Unified RA labels: always show HHhMMm format
                ra_h = ra_d / 15.0
                hrs = int(ra_h)
                mins = int(round((ra_h - hrs) * 60.0))
                if mins == 60:
                    mins = 0
                    hrs = (hrs + 1) % 24
                painter.setPen(tc if is_primary else tc_sub)
                if mins == 0:
                    painter.drawText(int(x) + 4, 16, f"{hrs:02d}h")
                else:
                    painter.drawText(int(x) + 4, 16, f"{hrs:02d}h{mins:02d}m")
        else:
            for rh in range(0, 24):
                rd = rh * 15.0
                x, _ = self.sky_to_viewport(rd, 0.0)
                if 0 <= x <= w:
                    painter.setPen(major if rh % 2 == 0 else minor)
                    painter.drawLine(int(x), 0, int(x), int(h))
                    painter.setPen(tc)
                    painter.drawText(int(x) + 4, 16, f"{rh:02d}h")

    def _draw_polar_grid(self, painter: QPainter) -> None:
        if not self.show_grid:
            return
        cx = self.width() / 2.0 + getattr(self, '_polar_offset_x', 0.0)
        cy = self.height() / 2.0 + getattr(self, '_polar_offset_y', 0.0)
        cr = min(self.width(), self.height()) / 2.0 * 0.9 * self.polar_zoom
        line = QPen(QColor(25, 35, 55))
        maj = QPen(QColor(35, 50, 75))
        sub_pen = QPen(QColor(20, 30, 48))
        sub_pen.setStyle(Qt.DashLine)
        tc = QColor(160, 140, 90)
        tc_sub = QColor(120, 110, 75)
        font = QFont()
        font.setPointSize(8)
        painter.setFont(font)

        z = self.polar_zoom
        dec_sub_step, _ = self._grid_sub_steps(z)
        sub_active = self.show_sub_grid and dec_sub_step is not None

        # Declination rings — unified pass when sub-grid is active
        if sub_active:
            step_10 = int(dec_sub_step * 10)
            for dec_10 in range(-900, 10, step_10):
                dec = dec_10 / 10.0
                r = ((dec + 90.0) / 180.0) * cr
                if r < 1:
                    continue
                is_primary = (dec_10 % 150 == 0)
                is_major = is_primary and (dec_10 % 300 == 0)
                if is_primary:
                    painter.setPen(maj if is_major else line)
                else:
                    painter.setPen(sub_pen)
                painter.setBrush(Qt.NoBrush)
                painter.drawEllipse(QPointF(cx, cy), r, r)
                painter.setPen(tc if is_primary else tc_sub)
                painter.drawText(int(cx + r + 4), int(cy + 4), f"{int(dec)}°")
        else:
            for dec in range(-90, 1, 15):
                r = ((dec + 90.0) / 180.0) * cr
                if r < 1:
                    continue
                painter.setPen(maj if dec % 30 == 0 else line)
                painter.setBrush(Qt.NoBrush)
                painter.drawEllipse(QPointF(cx, cy), r, r)
                painter.setPen(tc)
                painter.drawText(int(cx + r + 4), int(cy + 4), f"{dec}°")

        # RA lines — unified pass when sub-grid is active
        if sub_active:
            ra_step = 1.0 if z < 3.0 else 0.5  # hours
            step_10 = int(ra_step * 10)
            for h_10 in range(0, 240, step_10):
                h_val = h_10 / 10.0
                rd = (self.lst_deg + h_val * 15.0) % 360.0
                x, y = polar_stereo_xy(rd, 0.0, self.lst_deg, cr, south_pole=True)
                is_primary = (h_10 % 20 == 0)
                painter.setPen(line if is_primary else sub_pen)
                painter.drawLine(QPointF(cx, cy), QPointF(cx + x, cy + y))
                hrs = int(h_val)
                mins = int(round((h_val - hrs) * 60.0))
                if mins == 60:
                    mins = 0
                    hrs = (hrs + 1) % 24
                painter.setPen(tc if is_primary else tc_sub)
                lbl = f"{hrs:02d}h" if mins == 0 else f"{hrs:02d}h{mins:02d}m"
                painter.drawText(int(cx + x * 1.06) - 8, int(cy + y * 1.06) + 4, lbl)
        else:
            for h in range(0, 24, 2):
                rd = (self.lst_deg + h * 15.0) % 360.0
                x, y = polar_stereo_xy(rd, 0.0, self.lst_deg, cr, south_pole=True)
                painter.setPen(line)
                painter.drawLine(QPointF(cx, cy), QPointF(cx + x, cy + y))
                painter.setPen(tc)
                painter.drawText(int(cx + x * 1.06) - 8, int(cy + y * 1.06) + 4, f"{h:02d}h")

        horizon_dec = -(90.0 + self.observer_lat)
        if -90.0 < horizon_dec < 90.0:
            r = ((horizon_dec + 90.0) / 180.0) * cr
            hp = QPen(QColor(100, 60, 40, 120))
            hp.setWidth(2)
            hp.setStyle(Qt.DashLine)
            painter.setPen(hp)
            painter.setBrush(Qt.NoBrush)
            painter.drawEllipse(QPointF(cx, cy), r, r)

        painter.setPen(QColor(180, 200, 230))
        painter.drawText(int(cx) - 12, int(cy) - 6, "SCP")

    def _draw_horizon_grid(self, painter: QPainter) -> None:
        if not self.show_grid:
            return
        w, h = float(self.width()), float(self.height())
        line = QPen(QColor(25, 35, 55))
        maj = QPen(QColor(35, 50, 75))
        hp = QPen(QColor(100, 80, 50))
        hp.setWidth(2)
        sub_pen = QPen(QColor(20, 30, 48))
        sub_pen.setStyle(Qt.DashLine)
        tc = QColor(160, 140, 90)
        tc_sub = QColor(120, 110, 75)
        font = QFont()
        font.setPointSize(8)
        painter.setFont(font)

        v_fov = self.horizon_fov_deg * (h / w)
        default_center_alt = v_fov / 2.0
        alt_shift = (self.horizon_alt_center - default_center_alt) / v_fov * h

        fov_zoom = 120.0 / max(self.horizon_fov_deg, 30.0)
        sub_active = self.show_sub_grid and fov_zoom >= 1.3

        # Altitude lines — unified pass
        if sub_active:
            alt_sub = 5 if fov_zoom < 2.5 else 2
            for alt in range(-15, 91, alt_sub):
                base_y = h - (alt / v_fov) * h
                y = base_y + alt_shift
                if not (0 <= y <= h):
                    continue
                is_primary = (alt % 15 == 0)
                if alt == 0:
                    painter.setPen(hp)
                elif is_primary:
                    painter.setPen(maj if alt % 30 == 0 else line)
                else:
                    painter.setPen(sub_pen)
                painter.drawLine(0, int(y), int(w), int(y))
                painter.setPen(tc if is_primary else tc_sub)
                if alt == 0:
                    painter.drawText(8, int(y) - 4, "Horizon")
                else:
                    painter.drawText(8, int(y) - 4, f"{alt}°")
        else:
            for alt in range(-15, 91, 15):
                base_y = h - (alt / v_fov) * h
                y = base_y + alt_shift
                if 0 <= y <= h:
                    painter.setPen(hp if alt == 0 else (maj if alt % 30 == 0 else line))
                    painter.drawLine(0, int(y), int(w), int(y))
                    painter.setPen(tc)
                    painter.drawText(8, int(y) - 4, "Horizon" if alt == 0 else f"{alt}°")

        # Azimuth lines — unified pass
        compass = {0: "N", 45: "NE", 90: "E", 135: "SE",
                   180: "S", 225: "SW", 270: "W", 315: "NW"}
        if sub_active:
            az_sub = 5 if fov_zoom < 2.5 else 2
            for az in range(0, 360, az_sub):
                offset = (az - self.facing_az_deg + 180.0) % 360.0 - 180.0
                if abs(offset) > self.horizon_fov_deg / 2.0:
                    continue
                x = (w / 2.0) + (offset / self.horizon_fov_deg) * w
                is_primary = (az % 15 == 0)
                if is_primary:
                    painter.setPen(maj if az % 45 == 0 else line)
                else:
                    painter.setPen(sub_pen)
                painter.drawLine(int(x), 0, int(x), int(h))
                painter.setPen(tc if is_primary else tc_sub)
                painter.drawText(int(x) + 4, 16, compass.get(az, f"{az}°"))
        else:
            for az in range(0, 360, 15):
                offset = (az - self.facing_az_deg + 180.0) % 360.0 - 180.0
                if abs(offset) > self.horizon_fov_deg / 2.0:
                    continue
                x = (w / 2.0) + (offset / self.horizon_fov_deg) * w
                painter.setPen(maj if az % 45 == 0 else line)
                painter.drawLine(int(x), 0, int(x), int(h))
                painter.setPen(tc)
                painter.drawText(int(x) + 4, 16, compass.get(az, f"{az}°"))

        facing = compass.get(int(self.facing_az_deg), f"{self.facing_az_deg:.0f}°")
        painter.setPen(QColor(200, 220, 240))
        font.setPointSize(11)
        painter.setFont(font)
        painter.drawText(int(w / 2) - 20, 36, f"Facing {facing}")

    # --- Constellation lines ---

    def _draw_constellation_lines(self, painter: QPainter) -> None:
        if not self.show_constellation_lines or not self.constellation_lines or not self.star_index:
            return
        pen = QPen(QColor(70, 110, 180, 180))
        pen.setWidth(1)
        painter.setPen(pen)
        w = float(self.width())
        h = float(self.height())
        map_w = max(w, h * 2.0)
        world_w = map_w * self.zoom_factor

        for _, segments in self.constellation_lines.items():
            for segment in segments:
                if len(segment) != 2:
                    continue
                sa = self.star_index.get(segment[0])
                sb = self.star_index.get(segment[1])
                if not sa or not sb:
                    continue

                ra_a, dec_a = float(sa.get("ra_deg", 0)), float(sa.get("dec_deg", 0))
                ra_b, dec_b = float(sb.get("ra_deg", 0)), float(sb.get("dec_deg", 0))

                sep = angular_separation_deg(ra_a, dec_a, ra_b, dec_b)
                if sep > 90.0:
                    continue

                if self.view_mode == VIEW_HORIZON:
                    a1, _ = ra_dec_to_alt_az(ra_a, dec_a, self.lst_deg, self.observer_lat)
                    a2, _ = ra_dec_to_alt_az(ra_b, dec_b, self.lst_deg, self.observer_lat)
                    if a1 < -5.0 and a2 < -5.0:
                        continue

                x1, y1 = self.sky_to_viewport(ra_a, dec_a)
                x2, y2 = self.sky_to_viewport(ra_b, dec_b)

                # In equatorial mode, handle lines that cross the RA wrap
                if self.view_mode == VIEW_EQUATORIAL:
                    pixel_gap = abs(x2 - x1)
                    if pixel_gap > w * 0.4:
                        # Try shifting one endpoint by a full world width
                        best_gap = pixel_gap
                        best_x1, best_x2 = x1, x2

                        for shift_x1, shift_x2 in [
                            (x1 + world_w, x2),
                            (x1 - world_w, x2),
                            (x1, x2 + world_w),
                            (x1, x2 - world_w),
                        ]:
                            gap = abs(shift_x1 - shift_x2)
                            if gap < best_gap:
                                best_gap = gap
                                best_x1, best_x2 = shift_x1, shift_x2

                        if best_gap < pixel_gap:
                            x1, x2 = best_x1, best_x2
                        else:
                            # No shift helped — this line can't render
                            # cleanly on a flat chart (e.g. polar stars)
                            continue

                if self._is_on_screen(x1, y1, 100) or self._is_on_screen(x2, y2, 100):
                    painter.drawLine(QPointF(x1, y1), QPointF(x2, y2))

    def _draw_constellation_labels(self, painter: QPainter) -> None:
        if not self.show_constellation_labels or not self.constellation_metadata:
            return
        font = painter.font()
        font.setPointSize(10)
        painter.setFont(font)
        painter.setPen(QColor(110, 145, 190, 180))

        for _, meta in self.constellation_metadata.items():
            ra = meta.get("label_ra_deg")
            dec = meta.get("label_dec_deg")
            if ra is None or dec is None:
                continue
            if self.view_mode == VIEW_HORIZON:
                if not is_above_horizon(float(ra), float(dec), self.lst_deg,
                                        self.observer_lat, -5.0):
                    continue
            x, y = self.sky_to_viewport(float(ra), float(dec))
            if self._is_on_screen(x, y, 50):
                painter.drawText(int(x), int(y), str(meta.get("abbr", "")))

    # --- Objects ---

    def _draw_objects(self, painter: QPainter) -> None:
        self._projected_objects.clear()
        if self.show_stars:
            self._draw_stars(painter)
        if self.show_deep_sky:
            self._draw_deep_sky(painter)

    def _is_visible(self, ra: float, dec: float) -> bool:
        if self.view_mode == VIEW_HORIZON and self.show_horizon_clip:
            return is_above_horizon(ra, dec, self.lst_deg, self.observer_lat, -5.0)
        if self.view_mode == VIEW_POLAR:
            # In polar (south-centred) view, only show objects that can
            # ever be above the horizon from this latitude.
            # For Brisbane (-27.47°), the northern limit is dec < 90 + lat = 62.5°
            max_visible_dec = 90.0 + self.observer_lat  # e.g. 62.5° for Brisbane
            return dec < max_visible_dec + 5.0  # small margin
        return True

    def _draw_stars(self, painter: QPainter) -> None:
        for star in self.stars:
            mag = float(star.get("magnitude", 99.0))
            if mag > self.max_visible_magnitude:
                continue
            ra = float(star.get("ra_deg", 0.0))
            dec = float(star.get("dec_deg", 0.0))
            if not self._is_visible(ra, dec):
                continue

            x, y = self.sky_to_viewport(ra, dec)
            if not self._is_on_screen(x, y, 40):
                continue

            r = self._star_radius(mag)
            painter.setPen(Qt.NoPen)
            painter.setBrush(self._star_color(mag))
            painter.drawEllipse(QPointF(x, y), r, r)
            self._projected_objects.append((star, x, y, r))

            if self.show_labels and self._should_label_star(mag):
                painter.setPen(QColor(220, 230, 245))
                f = painter.font()
                f.setPointSize(8)
                painter.setFont(f)
                painter.drawText(int(x + r + 4), int(y - r - 2), star.get("name", ""))

    def _draw_deep_sky(self, painter: QPainter) -> None:
        for obj in self.deep_sky_objects:
            mag = float(obj.get("magnitude", 99.0))
            if mag > max(self.max_visible_magnitude + 3.0, 10.0):
                continue
            ra = float(obj.get("ra_deg", 0.0))
            dec = float(obj.get("dec_deg", 0.0))
            if not self._is_visible(ra, dec):
                continue

            x, y = self.sky_to_viewport(ra, dec)
            if not self._is_on_screen(x, y, 50):
                continue

            r = self._dso_radius(obj)
            color = self._dso_color(obj)
            otype = str(obj.get("object_type", "")).strip().lower()

            pen = QPen(color)
            pen.setWidth(1)
            painter.setPen(pen)
            painter.setBrush(Qt.NoBrush)

            if otype == "galaxy":
                painter.drawEllipse(QPointF(x, y), r * 1.6, r)
            elif otype in {"globular_cluster", "open_cluster"}:
                painter.drawEllipse(QPointF(x, y), r, r)
                painter.drawLine(int(x - r), int(y), int(x + r), int(y))
                painter.drawLine(int(x), int(y - r), int(x), int(y + r))
            elif otype == "planetary_nebula":
                painter.drawEllipse(QPointF(x, y), r, r)
                painter.drawEllipse(QPointF(x, y), max(1.0, r - 3.0), max(1.0, r - 3.0))
            elif otype == "dark_nebula":
                dp = QPen(QColor(120, 100, 70))
                dp.setWidth(2)
                painter.setPen(dp)
                painter.drawRect(int(x - r), int(y - r), int(r * 2), int(r * 2))
            elif otype == "supernova_remnant":
                painter.drawEllipse(QPointF(x, y), r, r)
                painter.drawEllipse(QPointF(x, y), r * 1.3, r * 1.3)
            else:
                painter.drawRect(int(x - r), int(y - r), int(r * 2), int(r * 2))

            self._projected_objects.append((obj, x, y, max(r, 6.0)))

            if self.show_labels and self._should_label_dso(obj):
                painter.setPen(color)
                f = painter.font()
                f.setPointSize(8)
                painter.setFont(f)
                painter.drawText(int(x + r + 4), int(y - r - 2), obj.get("name", ""))

    # --- Highlights ---

    def _draw_highlights(self, painter: QPainter) -> None:
        if self.result_target_object:
            self._draw_ring(painter, self.result_target_object, QColor(100, 220, 255), 14, 2)
        if self.result_clicked_object and self.result_is_correct is False:
            self._draw_ring(painter, self.result_clicked_object, QColor(255, 110, 110), 11, 2)
        if self.result_clicked_object and self.result_is_correct is True:
            self._draw_ring(painter, self.result_clicked_object, QColor(120, 255, 140), 13, 2)
        if self.revealed_answer:
            self._draw_crosshair(painter, self.revealed_answer, QColor(255, 220, 90), 18, 2)
        if self.hovered_object:
            self._draw_ring(painter, self.hovered_object, QColor(255, 255, 255), 10, 1)

        # Pointer tool rendering
        if self.pointer_anchor:
            self._draw_ring(painter, self.pointer_anchor, QColor(255, 180, 50), 12, 2)

        if self.pointer_target:
            self._draw_ring(painter, self.pointer_target, QColor(255, 180, 50), 12, 2)

        if self.pointer_anchor and self.pointer_target:
            self._draw_pointer_line(painter)

        # Path tool rendering
        if len(self.pointer_path) >= 2:
            self._draw_path_lines(painter)
        elif len(self.pointer_path) == 1:
            self._draw_ring(painter, self.pointer_path[0], QColor(130, 220, 130), 12, 2)

    def _draw_path_lines(self, painter: QPainter) -> None:
        """Draw connected path segments with cumulative distances."""
        path = self.pointer_path
        pen = QPen(QColor(130, 220, 130, 180))
        pen.setWidth(2)
        pen.setStyle(Qt.DashLine)

        for i in range(len(path)):
            obj = path[i]
            x, y = self.sky_to_viewport(float(obj.get("ra_deg", 0)), float(obj.get("dec_deg", 0)))

            # Draw node marker
            ring_pen = QPen(QColor(130, 220, 130))
            ring_pen.setWidth(2)
            painter.setPen(ring_pen)
            painter.setBrush(Qt.NoBrush)
            painter.drawEllipse(QPointF(x, y), 10, 10)

            # Draw number label
            painter.setPen(QColor(130, 220, 130))
            font = painter.font()
            font.setPointSize(8)
            font.setBold(True)
            painter.setFont(font)
            painter.drawText(int(x) - 4, int(y) + 4, str(i + 1))
            font.setBold(False)
            painter.setFont(font)

            # Draw line to previous
            if i > 0:
                prev = path[i - 1]
                px, py = self.sky_to_viewport(
                    float(prev.get("ra_deg", 0)), float(prev.get("dec_deg", 0)))

                painter.setPen(pen)
                painter.drawLine(QPointF(px, py), QPointF(x, y))

                # Leg distance at midpoint
                dist = angular_separation_deg(
                    float(prev.get("ra_deg", 0)), float(prev.get("dec_deg", 0)),
                    float(obj.get("ra_deg", 0)), float(obj.get("dec_deg", 0)),
                )
                mx, my = (px + x) / 2.0, (py + y) / 2.0
                painter.setPen(QColor(160, 240, 160))
                font = painter.font()
                font.setPointSize(9)
                painter.setFont(font)
                painter.drawText(int(mx) + 6, int(my) - 6, f"{dist:.1f}°")

    def _draw_pointer_line(self, painter: QPainter) -> None:
        """Draw a dashed measurement line between pointer anchor and target."""
        a = self.pointer_anchor
        t = self.pointer_target
        if not a or not t:
            return

        x1, y1 = self.sky_to_viewport(float(a.get("ra_deg", 0)), float(a.get("dec_deg", 0)))
        x2, y2 = self.sky_to_viewport(float(t.get("ra_deg", 0)), float(t.get("dec_deg", 0)))

        if not (self._is_on_screen(x1, y1, 100) or self._is_on_screen(x2, y2, 100)):
            return

        pen = QPen(QColor(255, 180, 50, 160))
        pen.setWidth(2)
        pen.setStyle(Qt.DashLine)
        painter.setPen(pen)
        painter.drawLine(QPointF(x1, y1), QPointF(x2, y2))

        # Draw distance label at midpoint
        mx, my = (x1 + x2) / 2.0, (y1 + y2) / 2.0
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

    def _draw_cursor_crosshair(self, painter: QPainter) -> None:
        """Draw a subtle crosshair at the cursor position with coordinate tooltip.
        Only active in explore mode."""
        if not self.show_crosshair or not self.explore_mode_active:
            return
        if self._cursor_x < 0 or self._cursor_y < 0:
            return

        cx, cy = self._cursor_x, self._cursor_y
        w, h = float(self.width()), float(self.height())

        # Don't draw if cursor is in the overlay info panel area
        if cy > h - 110 and cx < 580:
            return

        # Subtle crosshair lines
        pen = QPen(QColor(120, 140, 180, 60))
        pen.setWidth(1)
        pen.setStyle(Qt.DashLine)
        painter.setPen(pen)

        # Horizontal and vertical lines through cursor
        painter.drawLine(int(cx), 0, int(cx), int(h))
        painter.drawLine(0, int(cy), int(w), int(cy))

        # Small bright cross at cursor centre
        cp = QPen(QColor(180, 200, 230, 140))
        cp.setWidth(1)
        painter.setPen(cp)
        cross_size = 8
        painter.drawLine(int(cx - cross_size), int(cy), int(cx - 3), int(cy))
        painter.drawLine(int(cx + 3), int(cy), int(cx + cross_size), int(cy))
        painter.drawLine(int(cx), int(cy - cross_size), int(cx), int(cy - 3))
        painter.drawLine(int(cx), int(cy + 3), int(cx), int(cy + cross_size))

        # Coordinate tooltip near cursor
        label = self._cursor_coord_text()
        if not label:
            return

        font = QFont()
        font.setPointSize(9)
        painter.setFont(font)
        fm = painter.fontMetrics()
        text_w = fm.horizontalAdvance(label) + 16
        text_h = fm.height() + 8

        # Position tooltip offset from cursor (avoid going off-screen)
        tx = cx + 14
        ty = cy - 14 - text_h
        if tx + text_w > w:
            tx = cx - 14 - text_w
        if ty < 0:
            ty = cy + 14

        # Background
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(8, 12, 24, 200))
        painter.drawRoundedRect(int(tx), int(ty), int(text_w), int(text_h), 4, 4)

        # Border
        bp = QPen(QColor(60, 80, 120, 160))
        bp.setWidth(1)
        painter.setPen(bp)
        painter.drawRoundedRect(int(tx), int(ty), int(text_w), int(text_h), 4, 4)

        # Text
        painter.setPen(QColor(200, 215, 240))
        painter.drawText(int(tx + 8), int(ty + text_h - 6), label)

    def _cursor_coord_text(self) -> str:
        """Build the coordinate text for the cursor tooltip."""
        if self.view_mode == VIEW_HORIZON:
            if self._cursor_alt is not None and self._cursor_az is not None:
                dirs = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
                compass = dirs[int((self._cursor_az + 22.5) % 360 / 45)]
                return f"Alt {self._cursor_alt:.1f}°  Az {self._cursor_az:.1f}° {compass}"
            return ""
        else:
            if self._cursor_ra is not None and self._cursor_dec is not None:
                ra_text = format_ra(self._cursor_ra % 360.0)
                dec_text = format_dec(max(-90.0, min(90.0, self._cursor_dec)))
                return f"RA {ra_text}  Dec {dec_text}"
            return ""

    @staticmethod
    def _grid_sub_steps(zoom: float) -> Tuple[Optional[float], Optional[float]]:
        """
        Determine sub-grid step sizes based on zoom level.

        Returns:
            tuple: (dec_sub_step_deg, ra_sub_step_deg) or (None, None) if
                   sub-grid should not be shown at this zoom level.

        The logic creates an adaptive grid:
        - Zoom < 1.5: No sub-grid (full sky view, too cluttered)
        - Zoom 1.5-3.0: 5° Dec, 7.5° RA (30min)
        - Zoom 3.0-6.0: 5° Dec, 3.75° RA (15min)
        - Zoom 6.0-12.0: 2° Dec, 3.75° RA (15min)
        - Zoom 12.0+: 1° Dec, 1.875° RA (7.5min)
        """
        if zoom < 1.5:
            return None, None
        elif zoom < 3.0:
            return 5.0, 7.5     # 5° dec, 30min RA
        elif zoom < 6.0:
            return 5.0, 3.75    # 5° dec, 15min RA
        elif zoom < 12.0:
            return 2.0, 3.75    # 2° dec, 15min RA
        else:
            return 1.0, 1.875   # 1° dec, 7.5min RA

    # --- Overlay ---

    def _draw_overlay_info(self, painter: QPainter) -> None:
        margin = 10
        # Show cursor coords only in explore mode
        show_cursor = (self.explore_mode_active and self.show_crosshair
                       and self._cursor_x >= 0)
        panel_h = 90 if show_cursor else 72
        pr = QRectF(margin, self.height() - panel_h - 10, 560, panel_h)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(0, 0, 0, 150))
        painter.drawRoundedRect(pr, 8, 8)
        painter.setPen(QColor(220, 230, 240))
        font = painter.font()
        font.setPointSize(9)
        painter.setFont(font)

        if self.view_mode == VIEW_EQUATORIAL:
            t1 = (f"Equatorial   |   Center RA {format_ra(self.center_ra_deg)}, "
                  f"Dec {format_dec(self.center_dec_deg)}   |   Zoom x{self.zoom_factor:.1f}")
        elif self.view_mode == VIEW_POLAR:
            t1 = f"Polar (South)   |   LST {self.lst_deg / 15:.1f}h   |   Lat {self.observer_lat:+.1f}°"
        else:
            cd = {0:"N",90:"E",180:"S",270:"W"}
            f_l = cd.get(int(self.facing_az_deg), f"{self.facing_az_deg:.0f}°")
            t1 = f"Horizon   |   Facing {f_l}   |   LST {self.lst_deg / 15:.1f}h   |   FOV {self.horizon_fov_deg:.0f}°"

        painter.drawText(pr.adjusted(10, 8, -10, -52), Qt.AlignLeft | Qt.AlignVCenter, t1)

        t2 = (f"Stars [{'On' if self.show_stars else 'Off'}]   "
              f"Deep Sky [{'On' if self.show_deep_sky else 'Off'}]   "
              f"Constellations [{'On' if self.show_constellation_lines else 'Off'}]   "
              f"Sub-Grid [{'On' if self.show_sub_grid else 'Off'}]")
        painter.drawText(pr.adjusted(10, 24, -10, -36), Qt.AlignLeft | Qt.AlignVCenter, t2)

        # Cursor coordinate readout (explore mode only)
        if show_cursor:
            cursor_text = ""
            if self._cursor_ra is not None and self._cursor_dec is not None:
                ra_str = format_ra(self._cursor_ra % 360.0)
                dec_str = format_dec(max(-90.0, min(90.0, self._cursor_dec)))
                cursor_text = f"Cursor: RA {ra_str}, Dec {dec_str}"
                if self._cursor_alt is not None:
                    cursor_text += f"   |   Alt {self._cursor_alt:.1f}°"
            elif self._cursor_alt is not None and self._cursor_az is not None:
                dirs = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
                compass = dirs[int((self._cursor_az + 22.5) % 360 / 45)]
                cursor_text = f"Cursor: Alt {self._cursor_alt:.1f}°, Az {self._cursor_az:.1f}° {compass}"

            if cursor_text:
                painter.setPen(QColor(160, 180, 210))
                painter.drawText(pr.adjusted(10, 40, -10, -20), Qt.AlignLeft | Qt.AlignVCenter, cursor_text)

            hover_y_offset = 56
        else:
            hover_y_offset = 40

        t3 = "Hover: none"
        if self.hovered_object and self.show_hover_label:
            t3 = self._obj_desc(self.hovered_object)
        painter.drawText(pr.adjusted(10, hover_y_offset, -10, -4), Qt.AlignLeft | Qt.AlignVCenter, t3)

    # ------------------------------------------------------------------
    # INTERACTION
    # ------------------------------------------------------------------

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.LeftButton:
            obj = self._nearest_visible_object(event.position().x(), event.position().y())
            if obj is not None:
                self.selected_object = obj
                self.object_clicked.emit(obj)
                self.update()
            else:
                # Emit sky position for identify tool
                ra, dec = self.viewport_to_sky(event.position().x(), event.position().y())
                self.sky_clicked.emit(ra, dec)
                self._dragging = True
                self._last_mouse_pos = event.pos()
        elif event.button() in (Qt.MiddleButton, Qt.RightButton):
            self._dragging = True
            self._last_mouse_pos = event.pos()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        # Always update cursor position for crosshair display
        self._cursor_x = event.position().x()
        self._cursor_y = event.position().y()
        self._update_cursor_coords()

        if self._dragging and self._last_mouse_pos is not None:
            d = event.pos() - self._last_mouse_pos
            self._pan_by_pixels(d.x(), d.y())
            self._last_mouse_pos = event.pos()
            self.update()
        else:
            h = self._nearest_visible_object(event.position().x(), event.position().y(), 12.0)
            if h != self.hovered_object:
                self.hovered_object = h
            self.update()
        super().mouseMoveEvent(event)

    def leaveEvent(self, event) -> None:
        """Clear cursor position when mouse leaves the widget."""
        self._cursor_x = -1.0
        self._cursor_y = -1.0
        self._cursor_ra = None
        self._cursor_dec = None
        self._cursor_alt = None
        self._cursor_az = None
        self.update()
        super().leaveEvent(event)

    def _update_cursor_coords(self) -> None:
        """Compute the sky coordinates under the cursor."""
        if self._cursor_x < 0 or self._cursor_y < 0:
            self._cursor_ra = None
            self._cursor_dec = None
            self._cursor_alt = None
            self._cursor_az = None
            return

        if self.view_mode == VIEW_HORIZON:
            az, alt = self._horizon_to_sky(self._cursor_x, self._cursor_y)
            self._cursor_alt = alt
            self._cursor_az = az
            # Also compute approximate RA/Dec for reference
            # (reverse of ra_dec_to_alt_az is complex, so we store alt/az)
            self._cursor_ra = None
            self._cursor_dec = None
        else:
            ra, dec = self.viewport_to_sky(self._cursor_x, self._cursor_y)
            self._cursor_ra = ra
            self._cursor_dec = dec
            # Compute alt/az too for equatorial/polar modes
            alt, az = ra_dec_to_alt_az(ra, dec, self.lst_deg, self.observer_lat)
            self._cursor_alt = alt
            self._cursor_az = az

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() in (Qt.LeftButton, Qt.MiddleButton, Qt.RightButton):
            self._dragging = False
            self._last_mouse_pos = None
        super().mouseReleaseEvent(event)

    def wheelEvent(self, event: QWheelEvent) -> None:
        a = event.angleDelta().y()
        if a == 0:
            return
        if self.view_mode == VIEW_HORIZON:
            self.horizon_fov_deg = max(30, min(180, self.horizon_fov_deg + (-5 if a > 0 else 5)))
            self.update()
            return
        if self.view_mode == VIEW_POLAR:
            zs = 1.15 if a > 0 else 1.0 / 1.15
            self.polar_zoom = max(0.5, min(5.0, self.polar_zoom * zs))
            self.update()
            return
        zs = 1.15 if a > 0 else 1.0 / 1.15
        nz = max(self.min_zoom, min(self.max_zoom, self.zoom_factor * zs))
        if math.isclose(nz, self.zoom_factor, rel_tol=1e-9):
            return
        mx, my = event.position().x(), event.position().y()
        ra_b, dec_b = self.viewport_to_sky(mx, my)
        self.zoom_factor = nz
        ra_a, dec_a = self.viewport_to_sky(mx, my)
        self.center_ra_deg = (self.center_ra_deg + (ra_b - ra_a)) % 360.0
        self.center_dec_deg = max(-120, min(120, self.center_dec_deg + (dec_b - dec_a)))
        self.update()
        super().wheelEvent(event)

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        obj = self._nearest_visible_object(event.position().x(), event.position().y())
        if obj is not None:
            self._center_on_object(obj)
            self.selected_object = obj
            self.update()
        super().mouseDoubleClickEvent(event)

    # ------------------------------------------------------------------
    # VIEW TRANSFORMS
    # ------------------------------------------------------------------

    def sky_to_viewport(self, ra: float, dec: float) -> Tuple[float, float]:
        if self.view_mode == VIEW_POLAR:
            return self._sky_to_polar(ra, dec)
        if self.view_mode == VIEW_HORIZON:
            return self._sky_to_horizon(ra, dec)
        return self._sky_to_eq(ra, dec)

    def viewport_to_sky(self, x: float, y: float) -> Tuple[float, float]:
        if self.view_mode == VIEW_HORIZON:
            return self._horizon_to_sky(x, y)
        return self._eq_to_sky(x, y)

    def _sky_to_eq(self, ra: float, dec: float) -> Tuple[float, float]:
        w, h = float(self.width()), float(self.height())

        # Use a virtual map with 2:1 aspect ratio (360° x 180°)
        map_w = max(w, h * 2.0)
        map_h = map_w / 2.0

        fx, fy = sky_to_map_xy(ra, dec, map_w, map_h, invert_ra=self.invert_ra)

        # For the centre, don't clamp dec — use raw value to allow
        # the viewport to scroll a little past the poles
        center_ra = self.center_ra_deg % 360.0
        center_dec_clamped = max(-90.0, min(90.0, self.center_dec_deg))
        cx, cy = sky_to_map_xy(center_ra, center_dec_clamped,
                                map_w, map_h, invert_ra=self.invert_ra)

        # Offset cy by the unclamped portion so scrolling past poles
        # reveals empty space rather than hitting a hard wall
        dec_overflow = self.center_dec_deg - center_dec_clamped
        cy -= dec_overflow * (map_h / 180.0)

        x = (fx - cx) * self.zoom_factor + w / 2.0
        y = (fy - cy) * self.zoom_factor + h / 2.0

        # Horizontal wrapping for RA
        ww = map_w * self.zoom_factor
        while x < -ww * 0.3:
            x += ww
        while x > w + ww * 0.3:
            x -= ww

        return x, y

    def _eq_to_sky(self, x: float, y: float) -> Tuple[float, float]:
        w, h = float(self.width()), float(self.height())

        map_w = max(w, h * 2.0)
        map_h = map_w / 2.0

        center_ra = self.center_ra_deg % 360.0
        center_dec_clamped = max(-90.0, min(90.0, self.center_dec_deg))
        cx, cy = sky_to_map_xy(center_ra, center_dec_clamped,
                                map_w, map_h, invert_ra=self.invert_ra)
        dec_overflow = self.center_dec_deg - center_dec_clamped
        cy -= dec_overflow * (map_h / 180.0)

        fx = ((x - w / 2.0) / self.zoom_factor) + cx
        fy = ((y - h / 2.0) / self.zoom_factor) + cy

        return map_xy_to_sky(fx, fy, map_w, map_h, invert_ra=self.invert_ra)

    def _sky_to_polar(self, ra: float, dec: float) -> Tuple[float, float]:
        cx = self.width() / 2.0 + getattr(self, '_polar_offset_x', 0.0)
        cy = self.height() / 2.0 + getattr(self, '_polar_offset_y', 0.0)
        cr = min(self.width(), self.height()) / 2.0 * 0.9 * self.polar_zoom
        dx, dy = polar_stereo_xy(ra, dec, self.lst_deg, cr, south_pole=True)
        return cx + dx, cy + dy

    def _sky_to_horizon(self, ra: float, dec: float) -> Tuple[float, float]:
        alt, az = ra_dec_to_alt_az(ra, dec, self.lst_deg, self.observer_lat)
        w, h = float(self.width()), float(self.height())
        # Offset altitude by the centre altitude so we can look up/down
        x, y = horizon_view_xy(alt, az, self.facing_az_deg, w, h, self.horizon_fov_deg)
        # Shift y based on where we're centred vertically
        v_fov = self.horizon_fov_deg * (h / w)
        default_center_alt = v_fov / 2.0  # default centre is halfway up the vertical FOV
        alt_shift = (self.horizon_alt_center - default_center_alt) / v_fov * h
        y += alt_shift
        return x, y

    def _horizon_to_sky(self, x: float, y: float) -> Tuple[float, float]:
        w, h = float(self.width()), float(self.height())
        v_fov = self.horizon_fov_deg * (h / w)
        default_center_alt = v_fov / 2.0
        alt_shift = (self.horizon_alt_center - default_center_alt) / v_fov * h
        y_adj = y - alt_shift
        alt, az = horizon_xy_to_alt_az(x, y_adj, self.facing_az_deg, w, h, self.horizon_fov_deg)
        return az, alt

    # ------------------------------------------------------------------
    # HELPERS
    # ------------------------------------------------------------------

    def _nearest_visible_object(self, x: float, y: float, threshold_px: float = 10.0) -> Optional[CatalogObject]:
        if not self._projected_objects:
            self.update()
            self.repaint()
        best, best_d = None, float("inf")
        for obj, sx, sy, r in self._projected_objects:
            d = math.hypot(sx - x, sy - y)
            if d <= max(threshold_px, r + 4.0) and d < best_d:
                best_d, best = d, obj
        return best

    def _active_zoom(self) -> float:
        """Return the effective zoom factor for the current view mode."""
        if self.view_mode == VIEW_POLAR:
            return self.polar_zoom
        return self.zoom_factor

    def _star_radius(self, mag: float) -> float:
        z = self._active_zoom()
        r = max(1.2, min(8.0, 6.5 - mag))
        r *= 0.65 + 0.15 * min(z, 6.0)
        return max(1.4, min(10.0, r))

    def _dso_radius(self, obj: CatalogObject) -> float:
        z = self._active_zoom()
        mag = float(obj.get("magnitude", 10.0))
        r = max(4.0, min(10.0, 7.5 - min(mag, 8.0)))
        r *= 0.75 + 0.08 * min(z, 6.0)
        return max(4.0, min(14.0, r))

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
        if t == "dark_nebula": return QColor(160, 130, 90)
        return QColor(200, 220, 240)

    def _should_label_star(self, mag: float) -> bool:
        z = self._active_zoom()
        return mag <= 2.0 + min(z - 1.0, 4.0) * 0.75

    def _should_label_dso(self, obj: CatalogObject) -> bool:
        z = self._active_zoom()
        return float(obj.get("magnitude", 99.0)) <= 6.5 or z >= 3.0

    def _obj_desc(self, obj: CatalogObject) -> str:
        n = obj.get("name", "?")
        c = obj.get("constellation", "?")
        m = obj.get("magnitude", "?")
        t = obj.get("object_type", "?")
        desc = f"{n} | {t} | {c} | mag {m}"
        if self.view_mode in (VIEW_HORIZON, VIEW_POLAR):
            ra = float(obj.get("ra_deg", 0))
            dec = float(obj.get("dec_deg", 0))
            alt, az = ra_dec_to_alt_az(ra, dec, self.lst_deg, self.observer_lat)
            dirs = ["N","NE","E","SE","S","SW","W","NW"]
            desc += f" | Alt {alt:.0f}° {dirs[int((az+22.5)%360/45)]}"
        return desc

    def _center_on_object(self, obj: CatalogObject) -> None:
        ra = float(obj.get("ra_deg", self.center_ra_deg))
        dec = float(obj.get("dec_deg", self.center_dec_deg))
        if self.view_mode == VIEW_EQUATORIAL:
            self.center_ra_deg = ra % 360.0
            self.center_dec_deg = dec
        elif self.view_mode == VIEW_HORIZON:
            _, az = ra_dec_to_alt_az(ra, dec, self.lst_deg, self.observer_lat)
            self.facing_az_deg = az

    def _pan_by_pixels(self, dx: float, dy: float) -> None:
        w, h = float(self.width()), float(self.height())
        if w <= 0 or h <= 0:
            return
        if self.view_mode == VIEW_EQUATORIAL:
            map_w = max(w, h * 2.0)
            rpp = (360.0 / self.zoom_factor) / map_w
            dpp = (180.0 / self.zoom_factor) / (map_w / 2.0)
            self.center_ra_deg = (self.center_ra_deg + (dx if self.invert_ra else -dx) * rpp) % 360.0
            # Allow scrolling up to 30° past each pole for comfortable viewing
            new_dec = self.center_dec_deg + dy * dpp
            self.center_dec_deg = max(-120.0, min(120.0, new_dec))
        elif self.view_mode == VIEW_HORIZON:
            # Mirrored sky view: drag right pans facing eastward
            self.facing_az_deg = (self.facing_az_deg - dx * self.horizon_fov_deg / w) % 360.0
            v_fov = self.horizon_fov_deg * (h / w)
            alt_per_pixel = v_fov / h
            self.horizon_alt_center = max(-10.0, min(90.0, self.horizon_alt_center + dy * alt_per_pixel))
        elif self.view_mode == VIEW_POLAR:
            # Pan the polar chart by shifting pixel offset
            self._polar_offset_x = getattr(self, '_polar_offset_x', 0.0) + dx
            self._polar_offset_y = getattr(self, '_polar_offset_y', 0.0) + dy
            # Clamp so the SCP stays reachable
            max_offset = max(self.width(), self.height()) * self.polar_zoom
            self._polar_offset_x = max(-max_offset, min(max_offset, self._polar_offset_x))
            self._polar_offset_y = max(-max_offset, min(max_offset, self._polar_offset_y))

    def _draw_ring(self, p: QPainter, obj: CatalogObject, c: QColor, r: float, w: int) -> None:
        x, y = self.sky_to_viewport(float(obj.get("ra_deg", 0)), float(obj.get("dec_deg", 0)))
        if not self._is_on_screen(x, y, 50): return
        pen = QPen(c); pen.setWidth(w); p.setPen(pen); p.setBrush(Qt.NoBrush)
        p.drawEllipse(QPointF(x, y), r, r)

    def _draw_crosshair(self, p: QPainter, obj: CatalogObject, c: QColor, s: float, w: int) -> None:
        x, y = self.sky_to_viewport(float(obj.get("ra_deg", 0)), float(obj.get("dec_deg", 0)))
        if not self._is_on_screen(x, y, 50): return
        pen = QPen(c); pen.setWidth(w); p.setPen(pen)
        p.drawLine(QPointF(x-s,y), QPointF(x-5,y)); p.drawLine(QPointF(x+5,y), QPointF(x+s,y))
        p.drawLine(QPointF(x,y-s), QPointF(x,y-5)); p.drawLine(QPointF(x,y+5), QPointF(x,y+s))

    def _is_on_screen(self, x: float, y: float, margin: float = 0.0) -> bool:
        return -margin <= x <= self.width() + margin and -margin <= y <= self.height() + margin

    # ------------------------------------------------------------------
    # KEYBOARD
    # ------------------------------------------------------------------

    def keyPressEvent(self, event) -> None:
        k = event.key()

        if k in (Qt.Key_Plus, Qt.Key_Equal):
            if self.view_mode == VIEW_EQUATORIAL:
                self.zoom_factor = min(self.max_zoom, self.zoom_factor * 1.15)
            elif self.view_mode == VIEW_HORIZON:
                self.horizon_fov_deg = max(30, self.horizon_fov_deg - 10)
            elif self.view_mode == VIEW_POLAR:
                self.polar_zoom = min(5.0, self.polar_zoom * 1.15)
            self.update(); return

        if k in (Qt.Key_Minus, Qt.Key_Underscore):
            if self.view_mode == VIEW_EQUATORIAL:
                self.zoom_factor = max(self.min_zoom, self.zoom_factor / 1.15)
            elif self.view_mode == VIEW_HORIZON:
                self.horizon_fov_deg = min(180, self.horizon_fov_deg + 10)
            elif self.view_mode == VIEW_POLAR:
                self.polar_zoom = max(0.5, self.polar_zoom / 1.15)
            self.update(); return

        if k == Qt.Key_R:
            self.zoom_factor = 1.0; self.center_ra_deg = 180.0; self.center_dec_deg = 0.0
            self.facing_az_deg = 180.0; self.horizon_fov_deg = 120.0
            self.horizon_alt_center = 35.0; self.polar_zoom = 1.0
            self._polar_offset_x = 0.0; self._polar_offset_y = 0.0
            self.update(); return

        if k == Qt.Key_1: self.show_stars = not self.show_stars; self.update(); return
        if k == Qt.Key_2: self.show_deep_sky = not self.show_deep_sky; self.update(); return
        if k == Qt.Key_3: self.show_constellation_lines = not self.show_constellation_lines; self.update(); return
        if k == Qt.Key_4: self.show_sub_grid = not self.show_sub_grid; self.update(); return
        if k == Qt.Key_5: self.show_crosshair = not self.show_crosshair; self.update(); return

        if self.view_mode == VIEW_EQUATORIAL:
            s_ra, s_dec = 8.0 / self.zoom_factor, 6.0 / self.zoom_factor
            if k == Qt.Key_Left:  self.center_ra_deg = (self.center_ra_deg - s_ra) % 360; self.update(); return
            if k == Qt.Key_Right: self.center_ra_deg = (self.center_ra_deg + s_ra) % 360; self.update(); return
            if k == Qt.Key_Up:    self.center_dec_deg = min(120, self.center_dec_deg + s_dec); self.update(); return
            if k == Qt.Key_Down:  self.center_dec_deg = max(-120, self.center_dec_deg - s_dec); self.update(); return
        elif self.view_mode == VIEW_HORIZON:
            if k == Qt.Key_Left:  self.facing_az_deg = (self.facing_az_deg + 10) % 360; self.update(); return
            if k == Qt.Key_Right: self.facing_az_deg = (self.facing_az_deg - 10) % 360; self.update(); return
            if k == Qt.Key_Up:    self.horizon_alt_center = min(90, self.horizon_alt_center + 8); self.update(); return
            if k == Qt.Key_Down:  self.horizon_alt_center = max(-10, self.horizon_alt_center - 8); self.update(); return
        elif self.view_mode == VIEW_POLAR:
            if k in (Qt.Key_Plus, Qt.Key_Equal):
                self.polar_zoom = min(5.0, self.polar_zoom * 1.15); self.update(); return
            if k in (Qt.Key_Minus, Qt.Key_Underscore):
                self.polar_zoom = max(0.5, self.polar_zoom / 1.15); self.update(); return

        super().keyPressEvent(event)