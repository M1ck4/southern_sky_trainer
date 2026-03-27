"""
app_window.py

Main application window for the Southern Sky Trainer.

This window is responsible for:
- Displaying the current quiz prompt
- Hosting the interactive star map
- Showing score and feedback
- Handling high-level user actions such as:
  - generating a new question
  - showing the answer
  - resetting the score

This file assumes the existence of:
- star_map.py -> StarMapWidget
- quiz_engine.py -> QuizEngine
"""

from __future__ import annotations

from typing import List, Optional

from PySide6.QtCore import Qt, QPropertyAnimation, QEasingCurve, QTimer
from PySide6.QtGui import QAction, QColor, QFont, QFontDatabase, QPalette, QIcon
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSlider,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from quiz_engine import QuizEngine
from star_map import StarMapWidget
from celestial_sphere import CelestialSphereWidget
from coordinates import angular_separation_deg


# ------------------------------------------------------------------
# COLOUR PALETTE
# ------------------------------------------------------------------

class SpaceTheme:
    """
    Centralised colour and style constants for the dark space theme.
    """

    # Backgrounds
    BG_DEEPEST = "#050810"
    BG_DARK = "#0a0f1a"
    BG_PANEL = "#0d1322"
    BG_SURFACE = "#111827"
    BG_ELEVATED = "#162033"
    BG_HOVER = "#1c2a42"

    # Borders
    BORDER_SUBTLE = "#1a2540"
    BORDER_ACCENT = "#2a3d66"
    BORDER_GLOW = "#3b5998"

    # Text
    TEXT_PRIMARY = "#e0e6f0"
    TEXT_SECONDARY = "#8a9bbd"
    TEXT_MUTED = "#5a6a8a"
    TEXT_BRIGHT = "#f0f4ff"

    # Accents
    ACCENT_BLUE = "#4a90d9"
    ACCENT_CYAN = "#5cc8e8"
    ACCENT_GOLD = "#d4a853"
    ACCENT_GREEN = "#5ce89a"
    ACCENT_RED = "#e86565"
    ACCENT_PURPLE = "#8a7dd4"

    # Feedback
    SUCCESS = "#5ce89a"
    ERROR = "#e86565"
    INFO = "#5cc8e8"
    WARNING = "#d4a853"


STYLESHEET = f"""
    QMainWindow {{
        background-color: {SpaceTheme.BG_DEEPEST};
    }}

    QMenuBar {{
        background-color: {SpaceTheme.BG_DARK};
        color: {SpaceTheme.TEXT_SECONDARY};
        border-bottom: 1px solid {SpaceTheme.BORDER_SUBTLE};
        padding: 2px 0px;
        font-size: 13px;
    }}

    QMenuBar::item {{
        padding: 6px 14px;
        border-radius: 4px;
    }}

    QMenuBar::item:selected {{
        background-color: {SpaceTheme.BG_ELEVATED};
        color: {SpaceTheme.TEXT_PRIMARY};
    }}

    QMenu {{
        background-color: {SpaceTheme.BG_PANEL};
        color: {SpaceTheme.TEXT_PRIMARY};
        border: 1px solid {SpaceTheme.BORDER_ACCENT};
        border-radius: 6px;
        padding: 4px;
    }}

    QMenu::item {{
        padding: 8px 28px 8px 16px;
        border-radius: 4px;
    }}

    QMenu::item:selected {{
        background-color: {SpaceTheme.BG_HOVER};
    }}

    QStatusBar {{
        background-color: {SpaceTheme.BG_DARK};
        color: {SpaceTheme.TEXT_MUTED};
        border-top: 1px solid {SpaceTheme.BORDER_SUBTLE};
        font-size: 12px;
        padding: 2px 8px;
    }}

    QPushButton {{
        background-color: {SpaceTheme.BG_ELEVATED};
        color: {SpaceTheme.TEXT_PRIMARY};
        border: 1px solid {SpaceTheme.BORDER_ACCENT};
        border-radius: 6px;
        padding: 10px 18px;
        font-size: 13px;
        font-weight: 600;
        min-height: 20px;
    }}

    QPushButton:hover {{
        background-color: {SpaceTheme.BG_HOVER};
        border-color: {SpaceTheme.BORDER_GLOW};
        color: {SpaceTheme.TEXT_BRIGHT};
    }}

    QPushButton:pressed {{
        background-color: {SpaceTheme.BG_SURFACE};
        border-color: {SpaceTheme.ACCENT_BLUE};
    }}

    QPushButton:disabled {{
        background-color: {SpaceTheme.BG_DARK};
        color: {SpaceTheme.TEXT_MUTED};
        border-color: {SpaceTheme.BORDER_SUBTLE};
    }}

    QPushButton#button_new_question {{
        background-color: #1a2d50;
        border-color: {SpaceTheme.ACCENT_BLUE};
        color: {SpaceTheme.ACCENT_CYAN};
        padding: 4px 14px;
        font-size: 12px;
        min-height: 14px;
    }}

    QPushButton#button_new_question:hover {{
        background-color: #1e3460;
        border-color: {SpaceTheme.ACCENT_CYAN};
        color: {SpaceTheme.TEXT_BRIGHT};
    }}

    QPushButton#button_show_answer {{
        background-color: #2a2518;
        border-color: #665522;
        color: {SpaceTheme.ACCENT_GOLD};
        padding: 4px 14px;
        font-size: 12px;
        min-height: 14px;
    }}

    QPushButton#button_show_answer:hover {{
        background-color: #352e1e;
        border-color: {SpaceTheme.ACCENT_GOLD};
        color: {SpaceTheme.TEXT_BRIGHT};
    }}

    QPushButton#button_reset_score {{
        background-color: {SpaceTheme.BG_ELEVATED};
        border-color: {SpaceTheme.BORDER_ACCENT};
        color: {SpaceTheme.TEXT_SECONDARY};
        padding: 4px 10px;
        font-size: 12px;
        min-height: 14px;
    }}

    QPushButton#button_reset_score:hover {{
        background-color: #2a1820;
        border-color: {SpaceTheme.ACCENT_RED};
        color: {SpaceTheme.ACCENT_RED};
    }}

    QPushButton#button_mode_toggle {{
        background-color: #18222e;
        border-color: {SpaceTheme.ACCENT_PURPLE};
        color: {SpaceTheme.ACCENT_PURPLE};
        padding: 6px 10px;
        font-size: 12px;
    }}

    QPushButton#button_mode_toggle:hover {{
        background-color: #1e2838;
        border-color: #a89de0;
        color: {SpaceTheme.TEXT_BRIGHT};
    }}

    QMessageBox {{
        background-color: {SpaceTheme.BG_PANEL};
        color: {SpaceTheme.TEXT_PRIMARY};
    }}

    QMessageBox QLabel {{
        color: {SpaceTheme.TEXT_PRIMARY};
    }}
"""


class AppWindow(QMainWindow):
    """
    Main application window.

    Coordinates the user interface and connects the quiz system
    with the interactive star map.
    """

    def __init__(self) -> None:
        super().__init__()

        self.setWindowTitle("Southern Sky Trainer")
        self.resize(1400, 850)
        self.showMaximized()

        # Core state
        self.quiz_engine = QuizEngine()
        self.current_question: Optional[dict] = None
        self.answer_revealed: bool = False
        self.current_streak: int = 0
        self.best_streak: int = 0
        self.explore_mode: bool = False
        self.explore_tool: str = "select"  # select, distance, path, identify
        self.path_objects: List[dict] = []  # for path tool

        # UI elements
        self.question_label: Optional[QLabel] = None
        self.feedback_label: Optional[QLabel] = None
        self.score_label: Optional[QLabel] = None
        self.streak_label: Optional[QLabel] = None
        self.mode_label: Optional[QLabel] = None
        self.catalog_label: Optional[QLabel] = None
        self.object_count_label: Optional[QLabel] = None
        self.target_name_label: Optional[QLabel] = None
        self.target_type_label: Optional[QLabel] = None
        self.target_constellation_label: Optional[QLabel] = None
        self.target_magnitude_label: Optional[QLabel] = None
        self.target_coords_label: Optional[QLabel] = None
        self.target_aliases_label: Optional[QLabel] = None
        self.target_properties_label: Optional[QLabel] = None
        self.target_transit_label: Optional[QLabel] = None
        self.nearby_label: Optional[QLabel] = None
        self.pointer_label: Optional[QLabel] = None
        self.pointer_header_widget: Optional[QLabel] = None
        self.star_map: Optional[StarMapWidget] = None
        self.sphere_widget: Optional[CelestialSphereWidget] = None
        self.active_map_widget: Optional[QWidget] = None  # points to whichever is visible
        self.map_container_layout: Optional[QVBoxLayout] = None
        self.status_bar: Optional[QStatusBar] = None

        # Widget groups for mode toggling
        self.quiz_widgets: List[QWidget] = []
        self.button_mode_toggle: Optional[QPushButton] = None
        self.btn_view_eq: Optional[QPushButton] = None
        self.btn_view_polar: Optional[QPushButton] = None
        self.btn_view_horizon: Optional[QPushButton] = None
        self.btn_view_sphere: Optional[QPushButton] = None
        self.facing_row_widget: Optional[QWidget] = None
        self.sphere_nav_widget: Optional[QWidget] = None
        self.time_label: Optional[QLabel] = None
        self.tools_container: Optional[QWidget] = None
        self.btn_tool_select: Optional[QPushButton] = None
        self.btn_tool_distance: Optional[QPushButton] = None
        self.btn_tool_path: Optional[QPushButton] = None
        self.btn_tool_identify: Optional[QPushButton] = None
        self.tool_desc_label: Optional[QLabel] = None

        # Time scrubber
        self.time_scrubber_container: Optional[QWidget] = None
        self.time_slider: Optional[QSlider] = None
        self.time_display_label: Optional[QLabel] = None
        self.time_offset_label: Optional[QLabel] = None
        self._time_offset_minutes: float = 0.0  # offset from real time
        self._time_animating: bool = False
        self._time_anim_speed: float = 60.0  # minutes per second
        self._time_anim_timer: Optional[QTimer] = None

        self._apply_theme()
        self._build_ui()
        self._build_menu()
        self._connect_signals()

        # Timer to refresh the sky view every 30 seconds for live time
        self._time_timer = QTimer(self)
        self._time_timer.timeout.connect(self._refresh_sky_time)
        self._time_timer.start(30000)

        self.load_new_question()

        # Set initial view button state
        self._set_view_mode("equatorial")

    # ------------------------------------------------------------------
    # THEME
    # ------------------------------------------------------------------

    def _apply_theme(self) -> None:
        """
        Apply the dark space theme to the application.
        """
        self.setStyleSheet(STYLESHEET)

        palette = QPalette()
        palette.setColor(QPalette.Window, QColor(SpaceTheme.BG_DEEPEST))
        palette.setColor(QPalette.WindowText, QColor(SpaceTheme.TEXT_PRIMARY))
        palette.setColor(QPalette.Base, QColor(SpaceTheme.BG_DARK))
        palette.setColor(QPalette.AlternateBase, QColor(SpaceTheme.BG_PANEL))
        palette.setColor(QPalette.Text, QColor(SpaceTheme.TEXT_PRIMARY))
        palette.setColor(QPalette.Button, QColor(SpaceTheme.BG_ELEVATED))
        palette.setColor(QPalette.ButtonText, QColor(SpaceTheme.TEXT_PRIMARY))
        palette.setColor(QPalette.Highlight, QColor(SpaceTheme.ACCENT_BLUE))
        palette.setColor(QPalette.HighlightedText, QColor(SpaceTheme.TEXT_BRIGHT))
        self.setPalette(palette)

    # ------------------------------------------------------------------
    # UI BUILDING
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        """
        Build the main window layout.
        """
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        root_layout = QHBoxLayout(central_widget)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # Map takes all available space
        map_container = self._build_map_area()
        root_layout.addWidget(map_container, stretch=1)

        # Side panel is fixed width
        side_panel = self._build_side_panel()
        root_layout.addWidget(side_panel, stretch=0)

        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Ready — click the map to answer questions")

    def _build_map_area(self) -> QWidget:
        """
        Build the map area with the question/action bar at top.
        Score, quiz buttons, and feedback are in the top bar.
        """
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # --- Top action bar ---
        action_bar = QWidget()
        action_bar.setStyleSheet(
            f"background-color: {SpaceTheme.BG_DARK};"
            f"border-bottom: 1px solid {SpaceTheme.BORDER_SUBTLE};"
        )
        ab_layout = QVBoxLayout(action_bar)
        ab_layout.setContentsMargins(16, 8, 16, 8)
        ab_layout.setSpacing(4)

        # Row 1: question + score
        top_row = QHBoxLayout()
        top_row.setSpacing(12)

        self.question_label = QLabel("Loading question...")
        self.question_label.setWordWrap(True)
        self.question_label.setStyleSheet(
            f"font-size: 16px;"
            f"font-weight: 600;"
            f"color: {SpaceTheme.TEXT_BRIGHT};"
            f"background: transparent;"
            f"border: none;"
        )

        self.score_label = QLabel("0 / 0")
        self.score_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.score_label.setStyleSheet(
            f"font-size: 20px;"
            f"font-weight: 700;"
            f"color: {SpaceTheme.ACCENT_CYAN};"
            f"background: transparent;"
            f"border: none;"
            f"min-width: 80px;"
        )

        self.streak_label = QLabel("")
        self.streak_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.streak_label.setStyleSheet(
            f"font-size: 11px;"
            f"color: {SpaceTheme.TEXT_MUTED};"
            f"background: transparent;"
            f"border: none;"
            f"min-width: 100px;"
        )

        top_row.addWidget(self.question_label, stretch=1)
        top_row.addWidget(self.streak_label)
        top_row.addWidget(self.score_label)

        ab_layout.addLayout(top_row)

        # Row 2: feedback + buttons
        bottom_row = QHBoxLayout()
        bottom_row.setSpacing(8)

        self.feedback_label = QLabel("Click on the map to answer.")
        self.feedback_label.setWordWrap(True)
        self.feedback_label.setStyleSheet(
            f"font-size: 12px;"
            f"color: {SpaceTheme.TEXT_SECONDARY};"
            f"background: transparent;"
            f"border: none;"
        )

        button_new = QPushButton("New Question")
        button_new.setObjectName("button_new_question")
        button_new.setCursor(Qt.PointingHandCursor)
        button_new.setFixedHeight(28)
        button_new.setStyleSheet(
            button_new.styleSheet() + "padding: 4px 12px; font-size: 12px;"
        )
        self.quiz_widgets.append(button_new)

        button_show = QPushButton("Show Answer")
        button_show.setObjectName("button_show_answer")
        button_show.setCursor(Qt.PointingHandCursor)
        button_show.setFixedHeight(28)
        button_show.setStyleSheet(
            button_show.styleSheet() + "padding: 4px 12px; font-size: 12px;"
        )
        self.quiz_widgets.append(button_show)

        button_reset = QPushButton("Reset")
        button_reset.setObjectName("button_reset_score")
        button_reset.setCursor(Qt.PointingHandCursor)
        button_reset.setFixedHeight(28)
        button_reset.setStyleSheet(
            button_reset.styleSheet() + "padding: 4px 10px; font-size: 12px;"
        )
        self.quiz_widgets.append(button_reset)

        bottom_row.addWidget(self.feedback_label, stretch=1)
        bottom_row.addWidget(button_new)
        bottom_row.addWidget(button_show)
        bottom_row.addWidget(button_reset)

        ab_layout.addLayout(bottom_row)

        layout.addWidget(action_bar)

        # Star map (2D projections)
        self.star_map = StarMapWidget()
        self.star_map.setMinimumSize(600, 400)
        self.star_map.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        layout.addWidget(self.star_map)

        # Celestial sphere (3D view)
        self.sphere_widget = CelestialSphereWidget()
        self.sphere_widget.setMinimumSize(600, 400)
        self.sphere_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.sphere_widget.setVisible(False)
        layout.addWidget(self.sphere_widget)

        self.active_map_widget = self.star_map
        self.map_container_layout = layout

        return container

    def _build_side_panel(self) -> QWidget:
        """
        Build the side panel: mode toggle, sky view, tools, target info, nearby.
        Wrapped in a QScrollArea so long content (path chains etc.) doesn't
        push things off screen.
        """
        # Outer container with fixed width
        outer = QWidget()
        outer.setFixedWidth(270)
        outer.setStyleSheet(
            f"background-color: {SpaceTheme.BG_PANEL};"
            f"border-left: 1px solid {SpaceTheme.BORDER_SUBTLE};"
        )
        outer_layout = QVBoxLayout(outer)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(0)

        # Scroll area wrapping the inner content
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setStyleSheet(
            f"QScrollArea {{ background: transparent; border: none; }}"
            f"QScrollBar:vertical {{"
            f"  background: {SpaceTheme.BG_DARK};"
            f"  width: 6px; margin: 0px;"
            f"}}"
            f"QScrollBar::handle:vertical {{"
            f"  background: {SpaceTheme.BORDER_ACCENT};"
            f"  border-radius: 3px; min-height: 30px;"
            f"}}"
            f"QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{"
            f"  height: 0px;"
            f"}}"
        )

        # Inner widget that holds all the content
        inner = QWidget()
        inner.setObjectName("side_panel_inner")
        inner.setStyleSheet(
            f"QWidget#side_panel_inner {{ background: {SpaceTheme.BG_PANEL}; border: none; }}"
        )
        layout = QVBoxLayout(inner)
        layout.setContentsMargins(10, 12, 10, 12)
        layout.setSpacing(0)

        # --- App title ---
        title_label = QLabel("Southern Sky Trainer")
        title_label.setAlignment(Qt.AlignLeft)
        title_label.setStyleSheet(
            f"font-size: 18px;"
            f"font-weight: 700;"
            f"color: {SpaceTheme.TEXT_BRIGHT};"
            f"padding-bottom: 2px;"
            f"border: none;"
        )
        layout.addWidget(title_label)

        subtitle = QLabel("Sky Navigation Practice")
        subtitle.setStyleSheet(
            f"font-size: 10px;"
            f"color: {SpaceTheme.TEXT_MUTED};"
            f"letter-spacing: 2px;"
            f"padding-bottom: 10px;"
            f"border: none;"
        )
        layout.addWidget(subtitle)

        layout.addWidget(self._make_divider())
        layout.addSpacing(8)

        # --- Mode toggle ---
        self.button_mode_toggle = QPushButton("Switch to Explore")
        self.button_mode_toggle.setObjectName("button_mode_toggle")
        self.button_mode_toggle.setCursor(Qt.PointingHandCursor)
        layout.addWidget(self.button_mode_toggle)
        layout.addSpacing(8)

        # --- View projection controls ---
        view_header = self._make_section_header("SKY VIEW")
        layout.addWidget(view_header)
        layout.addSpacing(4)

        # 2x2 grid: top row = flat projections, bottom row = 3D + inside toggle
        view_grid = QVBoxLayout()
        view_grid.setSpacing(3)

        view_row_1 = QHBoxLayout()
        view_row_1.setSpacing(3)

        self.btn_view_eq = QPushButton("Chart")
        self.btn_view_eq.setCursor(Qt.PointingHandCursor)
        self.btn_view_eq.setFixedHeight(26)
        self.btn_view_eq.clicked.connect(lambda: self._set_view_mode("equatorial"))

        self.btn_view_polar = QPushButton("Polar")
        self.btn_view_polar.setCursor(Qt.PointingHandCursor)
        self.btn_view_polar.setFixedHeight(26)
        self.btn_view_polar.clicked.connect(lambda: self._set_view_mode("polar"))

        self.btn_view_horizon = QPushButton("Horizon")
        self.btn_view_horizon.setCursor(Qt.PointingHandCursor)
        self.btn_view_horizon.setFixedHeight(26)
        self.btn_view_horizon.clicked.connect(lambda: self._set_view_mode("horizon"))

        view_row_1.addWidget(self.btn_view_eq)
        view_row_1.addWidget(self.btn_view_polar)
        view_row_1.addWidget(self.btn_view_horizon)
        view_grid.addLayout(view_row_1)

        view_row_2 = QHBoxLayout()
        view_row_2.setSpacing(3)

        self.btn_view_sphere = QPushButton("Sphere")
        self.btn_view_sphere.setCursor(Qt.PointingHandCursor)
        self.btn_view_sphere.setFixedHeight(26)
        self.btn_view_sphere.setToolTip("3D celestial sphere — see RA/Dec as a globe")
        self.btn_view_sphere.clicked.connect(lambda: self._set_view_mode("sphere"))

        self.btn_view_inside = QPushButton("Inside")
        self.btn_view_inside.setCursor(Qt.PointingHandCursor)
        self.btn_view_inside.setFixedHeight(26)
        self.btn_view_inside.setToolTip("Toggle inside/outside view of the sphere (I)")
        self.btn_view_inside.setVisible(False)
        self.btn_view_inside.clicked.connect(self._toggle_sphere_inside)

        view_row_2.addWidget(self.btn_view_sphere)
        view_row_2.addWidget(self.btn_view_inside)
        view_grid.addLayout(view_row_2)

        # Sphere navigation buttons (visible only in sphere mode)
        self.sphere_nav_widget = QWidget()
        sphere_nav_layout = QVBoxLayout(self.sphere_nav_widget)
        sphere_nav_layout.setContentsMargins(0, 2, 0, 0)
        sphere_nav_layout.setSpacing(2)

        _nav_btn_style = (
            f"font-size: 10px; padding: 2px 4px; min-width: 32px;"
            f"border-radius: 3px; font-weight: 600;"
        )

        # Row 1: Your Sky + compass
        nav_row1 = QHBoxLayout()
        nav_row1.setSpacing(2)

        btn_yoursky = QPushButton("Your Sky")
        btn_yoursky.setCursor(Qt.PointingHandCursor)
        btn_yoursky.setFixedHeight(24)
        btn_yoursky.setStyleSheet(
            _nav_btn_style +
            f"background-color: #1a2d50; border: 1px solid {SpaceTheme.ACCENT_BLUE};"
            f"color: {SpaceTheme.ACCENT_CYAN};"
        )
        btn_yoursky.setToolTip("Jump to view centred on your sky")
        btn_yoursky.clicked.connect(lambda: self._sphere_navigate("your_sky"))

        for label, preset in [("N", "north"), ("E", "east"),
                               ("S", "south"), ("W", "west")]:
            btn = QPushButton(label)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setFixedHeight(24)
            btn.setFixedWidth(28)
            btn.setStyleSheet(_nav_btn_style)
            btn.setToolTip(f"Look {preset.title()}")
            btn.clicked.connect(
                lambda checked, p=preset: self._sphere_navigate(p))
            nav_row1.addWidget(btn)

        nav_row1.insertWidget(0, btn_yoursky)
        sphere_nav_layout.addLayout(nav_row1)

        # Row 2: Zenith + poles
        nav_row2 = QHBoxLayout()
        nav_row2.setSpacing(2)

        for label, preset in [("Zenith", "zenith"), ("SCP", "scp"), ("NCP", "ncp")]:
            btn = QPushButton(label)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setFixedHeight(24)
            btn.setStyleSheet(_nav_btn_style)
            btn.setToolTip(f"Look at {label}")
            btn.clicked.connect(
                lambda checked, p=preset: self._sphere_navigate(p))
            nav_row2.addWidget(btn)

        nav_row2.addStretch()
        sphere_nav_layout.addLayout(nav_row2)

        layout.addWidget(self.sphere_nav_widget)
        self.sphere_nav_widget.setVisible(False)

        layout.addLayout(view_grid)
        layout.addSpacing(4)

        # Facing direction (horizon only)
        self.facing_row_widget = QWidget()
        facing_row = QHBoxLayout(self.facing_row_widget)
        facing_row.setContentsMargins(0, 0, 0, 0)
        facing_row.setSpacing(4)

        for label, az in [("N", 0), ("E", 90), ("S", 180), ("W", 270)]:
            btn = QPushButton(label)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setFixedHeight(26)
            btn.setFixedWidth(48)
            btn.setStyleSheet(
                f"padding: 2px 4px; font-size: 12px; font-weight: 600;"
                f"min-width: 40px;"
            )
            btn.clicked.connect(lambda checked, a=az: self._set_facing(a))
            facing_row.addWidget(btn)

        layout.addWidget(self.facing_row_widget)
        self.facing_row_widget.setVisible(False)

        # Sphere navigation controls (sphere view only)
        self.sphere_nav_widget = QWidget()
        sphere_nav_layout = QVBoxLayout(self.sphere_nav_widget)
        sphere_nav_layout.setContentsMargins(0, 2, 0, 0)
        sphere_nav_layout.setSpacing(3)

        _nav_btn_style = (
            f"padding: 2px 4px; font-size: 11px; font-weight: 600;"
            f"min-width: 36px; border-radius: 3px;"
        )

        # Row 1: compass directions — rotate the view to face N/E/S/W
        compass_row = QHBoxLayout()
        compass_row.setSpacing(3)

        for label, rot_y in [("N", 0), ("E", 90), ("S", 180), ("W", 270)]:
            btn = QPushButton(label)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setFixedHeight(24)
            btn.setStyleSheet(_nav_btn_style)
            btn.setToolTip(f"Look {label}")
            btn.clicked.connect(
                lambda checked, ry=rot_y: self._sphere_look_direction(ry))
            compass_row.addWidget(btn)

        sphere_nav_layout.addLayout(compass_row)

        # Row 2: preset views — quick jumps to useful orientations
        preset_row = QHBoxLayout()
        preset_row.setSpacing(3)

        btn_zenith = QPushButton("Zenith")
        btn_zenith.setCursor(Qt.PointingHandCursor)
        btn_zenith.setFixedHeight(24)
        btn_zenith.setStyleSheet(_nav_btn_style)
        btn_zenith.setToolTip("Look straight up at the zenith")
        btn_zenith.clicked.connect(lambda: self._sphere_preset_view("zenith"))

        btn_scp = QPushButton("SCP")
        btn_scp.setCursor(Qt.PointingHandCursor)
        btn_scp.setFixedHeight(24)
        btn_scp.setStyleSheet(_nav_btn_style)
        btn_scp.setToolTip("Look towards the south celestial pole")
        btn_scp.clicked.connect(lambda: self._sphere_preset_view("scp"))

        btn_ncp = QPushButton("NCP")
        btn_ncp.setCursor(Qt.PointingHandCursor)
        btn_ncp.setFixedHeight(24)
        btn_ncp.setStyleSheet(_nav_btn_style)
        btn_ncp.setToolTip("Look towards the north celestial pole")
        btn_ncp.clicked.connect(lambda: self._sphere_preset_view("ncp"))

        btn_reset_view = QPushButton("Reset")
        btn_reset_view.setCursor(Qt.PointingHandCursor)
        btn_reset_view.setFixedHeight(24)
        btn_reset_view.setStyleSheet(_nav_btn_style)
        btn_reset_view.setToolTip("Reset to default view (R)")
        btn_reset_view.clicked.connect(lambda: self._sphere_preset_view("reset"))

        preset_row.addWidget(btn_zenith)
        preset_row.addWidget(btn_scp)
        preset_row.addWidget(btn_ncp)
        preset_row.addWidget(btn_reset_view)

        sphere_nav_layout.addLayout(preset_row)

        layout.addWidget(self.sphere_nav_widget)
        self.sphere_nav_widget.setVisible(False)

        # Time label
        self.time_label = QLabel("")
        self.time_label.setStyleSheet(
            f"font-size: 11px;"
            f"color: {SpaceTheme.TEXT_MUTED};"
            f"padding: 2px 0px 0px 0px;"
            f"border: none;"
        )
        layout.addWidget(self.time_label)
        self.time_label.setVisible(False)

        layout.addSpacing(6)

        # --- Explore tools (visible only in explore mode) ---
        self.tools_container = QWidget()
        tools_layout = QVBoxLayout(self.tools_container)
        tools_layout.setContentsMargins(0, 0, 0, 0)
        tools_layout.setSpacing(3)

        tools_header = self._make_section_header("TOOLS")
        tools_layout.addWidget(tools_header)
        tools_layout.addSpacing(2)

        # Icon buttons — compact single row
        # ◎ Select  ↔ Distance  ⋯ Path  ⊕ Identify
        tools_row = QHBoxLayout()
        tools_row.setSpacing(3)

        tool_btn_style = (
            f"font-size: 13px; min-width: 44px; max-width: 56px;"
            f"padding: 3px 2px; border-radius: 4px;"
        )

        self.btn_tool_select = QPushButton("◎")
        self.btn_tool_select.setCursor(Qt.PointingHandCursor)
        self.btn_tool_select.setFixedHeight(30)
        self.btn_tool_select.setToolTip("Select — browse and view object details")
        self.btn_tool_select.clicked.connect(lambda: self._set_explore_tool("select"))

        self.btn_tool_distance = QPushButton("↔")
        self.btn_tool_distance.setCursor(Qt.PointingHandCursor)
        self.btn_tool_distance.setFixedHeight(30)
        self.btn_tool_distance.setToolTip("Distance — measure angle between two objects")
        self.btn_tool_distance.clicked.connect(lambda: self._set_explore_tool("distance"))

        self.btn_tool_path = QPushButton("⋯")
        self.btn_tool_path.setCursor(Qt.PointingHandCursor)
        self.btn_tool_path.setFixedHeight(30)
        self.btn_tool_path.setToolTip("Path — build a star-hop chain")
        self.btn_tool_path.clicked.connect(lambda: self._set_explore_tool("path"))

        self.btn_tool_identify = QPushButton("⊕")
        self.btn_tool_identify.setCursor(Qt.PointingHandCursor)
        self.btn_tool_identify.setFixedHeight(30)
        self.btn_tool_identify.setToolTip("Identify — click sky to see RA/Dec + nearest objects")
        self.btn_tool_identify.clicked.connect(lambda: self._set_explore_tool("identify"))

        tools_row.addWidget(self.btn_tool_select)
        tools_row.addWidget(self.btn_tool_distance)
        tools_row.addWidget(self.btn_tool_path)
        tools_row.addWidget(self.btn_tool_identify)
        tools_row.addStretch()
        tools_layout.addLayout(tools_row)

        # Tool description — shows name + purpose of active tool
        self.tool_desc_label = QLabel("Select — click objects to view details.")
        self.tool_desc_label.setWordWrap(True)
        self.tool_desc_label.setStyleSheet(
            f"font-size: 10px;"
            f"color: {SpaceTheme.TEXT_MUTED};"
            f"padding: 2px 0px 0px 0px;"
            f"border: none;"
        )
        tools_layout.addWidget(self.tool_desc_label)

        layout.addWidget(self.tools_container)
        self.tools_container.setVisible(False)

        layout.addSpacing(4)

        # --- Time Scrubber (explore mode only) ---
        self.time_scrubber_container = QWidget()
        ts_layout = QVBoxLayout(self.time_scrubber_container)
        ts_layout.setContentsMargins(0, 0, 0, 0)
        ts_layout.setSpacing(2)

        ts_header = self._make_section_header("TIME TRAVEL")
        ts_layout.addWidget(ts_header)
        ts_layout.addSpacing(2)

        # Time display
        self.time_display_label = QLabel("")
        self.time_display_label.setWordWrap(True)
        self.time_display_label.setStyleSheet(
            f"font-size: 11px;"
            f"color: {SpaceTheme.TEXT_PRIMARY};"
            f"padding: 1px 0px;"
            f"border: none;"
        )
        ts_layout.addWidget(self.time_display_label)

        # Offset label
        self.time_offset_label = QLabel("Now (live)")
        self.time_offset_label.setStyleSheet(
            f"font-size: 10px;"
            f"color: {SpaceTheme.ACCENT_GOLD};"
            f"padding: 0px;"
            f"border: none;"
        )
        ts_layout.addWidget(self.time_offset_label)
        ts_layout.addSpacing(2)

        # Slider: ±720 minutes (12 hours) range
        self.time_slider = QSlider(Qt.Horizontal)
        self.time_slider.setRange(-720, 720)
        self.time_slider.setValue(0)
        self.time_slider.setTickInterval(60)
        self.time_slider.setSingleStep(5)
        self.time_slider.setPageStep(60)
        self.time_slider.setStyleSheet(
            f"QSlider::groove:horizontal {{"
            f"  background: {SpaceTheme.BG_SURFACE};"
            f"  height: 6px; border-radius: 3px;"
            f"  border: 1px solid {SpaceTheme.BORDER_SUBTLE};"
            f"}}"
            f"QSlider::handle:horizontal {{"
            f"  background: {SpaceTheme.ACCENT_BLUE};"
            f"  width: 14px; margin: -5px 0;"
            f"  border-radius: 7px;"
            f"  border: 1px solid {SpaceTheme.ACCENT_CYAN};"
            f"}}"
            f"QSlider::handle:horizontal:hover {{"
            f"  background: {SpaceTheme.ACCENT_CYAN};"
            f"}}"
        )
        self.time_slider.valueChanged.connect(self._on_time_slider_changed)
        ts_layout.addWidget(self.time_slider)
        ts_layout.addSpacing(2)

        # Step buttons row 1: fine steps
        step_row1 = QHBoxLayout()
        step_row1.setSpacing(2)

        _step_btn_style = (
            f"font-size: 10px; padding: 2px 4px; min-width: 32px;"
            f"border-radius: 3px;"
        )

        for label, minutes in [("-1h", -60), ("-10m", -10), ("-1m", -1),
                                ("+1m", 1), ("+10m", 10), ("+1h", 60)]:
            btn = QPushButton(label)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setFixedHeight(22)
            btn.setStyleSheet(_step_btn_style)
            btn.clicked.connect(
                lambda checked, m=minutes: self._step_time(m))
            step_row1.addWidget(btn)

        ts_layout.addLayout(step_row1)

        # Step buttons row 2: coarse steps + play/reset
        step_row2 = QHBoxLayout()
        step_row2.setSpacing(2)

        for label, minutes in [("-1d", -1440), ("-6h", -360),
                                ("+6h", 360), ("+1d", 1440)]:
            btn = QPushButton(label)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setFixedHeight(22)
            btn.setStyleSheet(_step_btn_style)
            btn.clicked.connect(
                lambda checked, m=minutes: self._step_time(m))
            step_row2.addWidget(btn)

        ts_layout.addLayout(step_row2)
        ts_layout.addSpacing(2)

        # Play/pause and reset row
        ctrl_row = QHBoxLayout()
        ctrl_row.setSpacing(3)

        self._btn_time_play = QPushButton("▶ Play")
        self._btn_time_play.setCursor(Qt.PointingHandCursor)
        self._btn_time_play.setFixedHeight(24)
        self._btn_time_play.setStyleSheet(
            f"font-size: 10px; padding: 2px 8px; border-radius: 3px;"
            f"background-color: #1a2d50;"
            f"border: 1px solid {SpaceTheme.ACCENT_BLUE};"
            f"color: {SpaceTheme.ACCENT_CYAN};"
        )
        self._btn_time_play.clicked.connect(self._toggle_time_animation)

        self._btn_time_reset = QPushButton("Now")
        self._btn_time_reset.setCursor(Qt.PointingHandCursor)
        self._btn_time_reset.setFixedHeight(24)
        self._btn_time_reset.setStyleSheet(
            f"font-size: 10px; padding: 2px 8px; border-radius: 3px;"
            f"background-color: #2a2518;"
            f"border: 1px solid #665522;"
            f"color: {SpaceTheme.ACCENT_GOLD};"
        )
        self._btn_time_reset.clicked.connect(self._reset_time)

        ctrl_row.addWidget(self._btn_time_play)
        ctrl_row.addWidget(self._btn_time_reset)
        ctrl_row.addStretch()
        ts_layout.addLayout(ctrl_row)

        layout.addWidget(self.time_scrubber_container)
        self.time_scrubber_container.setVisible(False)

        layout.addSpacing(6)
        layout.addWidget(self._make_divider())
        layout.addSpacing(8)

        # --- Question info (quiz only, compact) ---
        self.mode_label = QLabel("Type: —")
        self.mode_label.setWordWrap(True)
        self.mode_label.setStyleSheet(
            f"font-size: 12px;"
            f"color: {SpaceTheme.TEXT_SECONDARY};"
            f"padding: 1px 0px;"
            f"border: none;"
        )
        layout.addWidget(self.mode_label)
        self.quiz_widgets.append(self.mode_label)

        self.catalog_label = QLabel("")
        self.catalog_label.setWordWrap(True)
        self.catalog_label.setStyleSheet(
            f"font-size: 11px;"
            f"color: {SpaceTheme.TEXT_MUTED};"
            f"padding: 1px 0px;"
            f"border: none;"
        )
        layout.addWidget(self.catalog_label)
        self.quiz_widgets.append(self.catalog_label)

        self.object_count_label = QLabel("")
        self.object_count_label.setWordWrap(True)
        self.object_count_label.setStyleSheet(
            f"font-size: 11px;"
            f"color: {SpaceTheme.TEXT_MUTED};"
            f"padding: 1px 0px 4px 0px;"
            f"border: none;"
        )
        layout.addWidget(self.object_count_label)
        self.quiz_widgets.append(self.object_count_label)

        layout.addWidget(self._make_divider())
        layout.addSpacing(8)

        # --- Target context ---
        target_header = self._make_section_header("TARGET INFO")
        layout.addWidget(target_header)
        layout.addSpacing(4)

        self.target_name_label = QLabel("—")
        self.target_name_label.setWordWrap(True)
        self.target_name_label.setStyleSheet(
            f"font-size: 15px;"
            f"font-weight: 600;"
            f"color: {SpaceTheme.TEXT_BRIGHT};"
            f"padding: 1px 0px;"
            f"border: none;"
        )
        layout.addWidget(self.target_name_label)

        self.target_type_label = QLabel("")
        self.target_type_label.setWordWrap(True)
        self.target_type_label.setStyleSheet(
            f"font-size: 12px;"
            f"color: {SpaceTheme.TEXT_SECONDARY};"
            f"padding: 1px 0px;"
            f"border: none;"
        )
        layout.addWidget(self.target_type_label)

        self.target_constellation_label = QLabel("")
        self.target_constellation_label.setWordWrap(True)
        self.target_constellation_label.setStyleSheet(
            f"font-size: 12px;"
            f"color: {SpaceTheme.TEXT_SECONDARY};"
            f"padding: 1px 0px;"
            f"border: none;"
        )
        layout.addWidget(self.target_constellation_label)

        self.target_magnitude_label = QLabel("")
        self.target_magnitude_label.setStyleSheet(
            f"font-size: 12px;"
            f"color: {SpaceTheme.TEXT_SECONDARY};"
            f"padding: 1px 0px;"
            f"border: none;"
        )
        layout.addWidget(self.target_magnitude_label)

        self.target_coords_label = QLabel("")
        self.target_coords_label.setWordWrap(True)
        self.target_coords_label.setStyleSheet(
            f"font-size: 12px;"
            f"color: {SpaceTheme.TEXT_MUTED};"
            f"padding: 1px 0px;"
            f"border: none;"
        )
        layout.addWidget(self.target_coords_label)

        self.target_aliases_label = QLabel("")
        self.target_aliases_label.setWordWrap(True)
        self.target_aliases_label.setStyleSheet(
            f"font-size: 11px;"
            f"color: {SpaceTheme.TEXT_MUTED};"
            f"padding: 1px 0px 8px 0px;"
            f"border: none;"
        )
        layout.addWidget(self.target_aliases_label)

        # Physical properties (distance, spectral type, luminosity)
        self.target_properties_label = QLabel("")
        self.target_properties_label.setWordWrap(True)
        self.target_properties_label.setStyleSheet(
            f"font-size: 11px;"
            f"color: {SpaceTheme.TEXT_SECONDARY};"
            f"padding: 1px 0px;"
            f"border: none;"
        )
        layout.addWidget(self.target_properties_label)

        # Transit time
        self.target_transit_label = QLabel("")
        self.target_transit_label.setWordWrap(True)
        self.target_transit_label.setStyleSheet(
            f"font-size: 11px;"
            f"color: {SpaceTheme.TEXT_MUTED};"
            f"padding: 1px 0px 6px 0px;"
            f"border: none;"
        )
        layout.addWidget(self.target_transit_label)

        layout.addSpacing(4)
        layout.addWidget(self._make_divider())
        layout.addSpacing(12)

        # --- Nearby objects (shown after answering) ---
        nearby_header = self._make_section_header("NEARBY OBJECTS")
        layout.addWidget(nearby_header)
        layout.addSpacing(6)

        self.nearby_label = QLabel("Answer to reveal nearby objects.")
        self.nearby_label.setWordWrap(True)
        self.nearby_label.setStyleSheet(
            f"font-size: 12px;"
            f"color: {SpaceTheme.TEXT_MUTED};"
            f"padding: 1px 0px;"
            f"border: none;"
        )
        layout.addWidget(self.nearby_label)

        layout.addSpacing(4)
        layout.addWidget(self._make_divider())
        layout.addSpacing(8)

        # --- Pointer measurement (explore mode only) ---
        pointer_header = self._make_section_header("POINTER")
        layout.addWidget(pointer_header)
        self.pointer_header_widget = pointer_header
        layout.addSpacing(4)

        self.pointer_label = QLabel("Click two objects to measure distance.")
        self.pointer_label.setWordWrap(True)
        self.pointer_label.setStyleSheet(
            f"font-size: 12px;"
            f"color: {SpaceTheme.TEXT_MUTED};"
            f"padding: 1px 0px;"
            f"border: none;"
        )
        layout.addWidget(self.pointer_label)

        # Initially hidden (only visible in explore mode)
        self.pointer_header_widget.setVisible(False)
        self.pointer_label.setVisible(False)

        layout.addStretch()

        # Set inner widget into scroll area
        scroll.setWidget(inner)
        outer_layout.addWidget(scroll)

        return outer

    def _make_divider(self) -> QWidget:
        """
        Create a subtle horizontal divider line.
        """
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setStyleSheet(
            f"background-color: {SpaceTheme.BORDER_SUBTLE};"
            f"border: none;"
            f"max-height: 1px;"
        )
        return line

    def _make_section_header(self, text: str) -> QLabel:
        """
        Create a small uppercase section header label.
        """
        label = QLabel(text)
        label.setStyleSheet(
            f"font-size: 10px;"
            f"font-weight: 700;"
            f"color: {SpaceTheme.TEXT_MUTED};"
            f"letter-spacing: 2px;"
            f"padding: 0px;"
            f"border: none;"
        )
        return label

    def _build_menu(self) -> None:
        """
        Build the application menu bar.
        """
        menu_bar = self.menuBar()

        file_menu = menu_bar.addMenu("&File")
        game_menu = menu_bar.addMenu("&Game")
        help_menu = menu_bar.addMenu("&Help")

        exit_action = QAction("Exit", self)
        exit_action.triggered.connect(self.close)

        new_question_action = QAction("New Question", self)
        new_question_action.setShortcut("Ctrl+N")
        new_question_action.triggered.connect(self.load_new_question)

        show_answer_action = QAction("Show Answer", self)
        show_answer_action.setShortcut("Ctrl+A")
        show_answer_action.triggered.connect(self.show_answer)

        reset_score_action = QAction("Reset Score", self)
        reset_score_action.triggered.connect(self.reset_score)

        toggle_mode_action = QAction("Toggle Explore / Quiz", self)
        toggle_mode_action.setShortcut("Ctrl+E")
        toggle_mode_action.triggered.connect(self.toggle_mode)

        about_action = QAction("About", self)
        about_action.triggered.connect(self.show_about_dialog)

        file_menu.addAction(exit_action)
        game_menu.addAction(new_question_action)
        game_menu.addAction(show_answer_action)
        game_menu.addSeparator()
        game_menu.addAction(toggle_mode_action)
        game_menu.addSeparator()
        game_menu.addAction(reset_score_action)
        help_menu.addAction(about_action)

    def _connect_signals(self) -> None:
        """
        Connect UI signals to handlers.
        """
        assert self.star_map is not None

        self.star_map.object_clicked.connect(self.handle_map_click)
        self.star_map.sky_clicked.connect(self._handle_sky_click)

        if self.sphere_widget:
            self.sphere_widget.object_clicked.connect(self.handle_map_click)
            self.sphere_widget.sky_clicked.connect(self._handle_sky_click)

        button_new = self.findChild(QPushButton, "button_new_question")
        button_show = self.findChild(QPushButton, "button_show_answer")
        button_reset = self.findChild(QPushButton, "button_reset_score")

        if button_new:
            button_new.clicked.connect(self.load_new_question)

        if button_show:
            button_show.clicked.connect(self.show_answer)

        if button_reset:
            button_reset.clicked.connect(self.reset_score)

        if self.button_mode_toggle:
            self.button_mode_toggle.clicked.connect(self.toggle_mode)

    # ------------------------------------------------------------------
    # MODE SWITCHING
    # ------------------------------------------------------------------

    def toggle_mode(self) -> None:
        """
        Switch between Quiz mode and Explore mode.
        """
        self.explore_mode = not self.explore_mode
        self._apply_mode_ui()

    def _set_view_mode(self, mode: str) -> None:
        """Switch the star map projection mode and update UI."""
        if not self.star_map:
            return

        is_sphere = (mode == "sphere")

        # Widget swapping: show sphere or star map
        if is_sphere:
            self.star_map.setVisible(False)
            if self.sphere_widget:
                self.sphere_widget.setVisible(True)
                self.active_map_widget = self.sphere_widget
        else:
            if self.sphere_widget:
                self.sphere_widget.setVisible(False)
            self.star_map.setVisible(True)
            self.star_map.set_view_mode(mode)
            self.active_map_widget = self.star_map

        # Update all view button styling
        all_buttons = [
            (self.btn_view_eq, "equatorial"),
            (self.btn_view_polar, "polar"),
            (self.btn_view_horizon, "horizon"),
            (self.btn_view_sphere, "sphere"),
        ]
        for btn, m in all_buttons:
            if btn is None:
                continue
            if m == mode:
                btn.setStyleSheet(
                    f"background-color: {SpaceTheme.ACCENT_BLUE};"
                    f"color: {SpaceTheme.TEXT_BRIGHT};"
                    f"border: 1px solid {SpaceTheme.ACCENT_CYAN};"
                    f"border-radius: 4px;"
                    f"font-size: 12px;"
                    f"font-weight: 600;"
                )
            else:
                btn.setStyleSheet(
                    f"background-color: {SpaceTheme.BG_ELEVATED};"
                    f"color: {SpaceTheme.TEXT_SECONDARY};"
                    f"border: 1px solid {SpaceTheme.BORDER_ACCENT};"
                    f"border-radius: 4px;"
                    f"font-size: 12px;"
                )

        # Show/hide view-specific controls
        show_sky = mode in ("polar", "horizon")
        if self.facing_row_widget:
            self.facing_row_widget.setVisible(mode == "horizon")
        if self.sphere_nav_widget:
            self.sphere_nav_widget.setVisible(is_sphere)
        if self.time_label:
            self.time_label.setVisible(show_sky)

        # Show/hide sphere-specific controls
        if hasattr(self, 'btn_view_inside') and self.btn_view_inside:
            self.btn_view_inside.setVisible(is_sphere)
            if is_sphere:
                self._update_inside_button()
        if hasattr(self, 'sphere_nav_widget') and self.sphere_nav_widget:
            self.sphere_nav_widget.setVisible(is_sphere)

        # Disable distance/path/identify tools in sphere mode
        # (they don't render well on a 3D surface)
        sphere_disabled_tools = [
            self.btn_tool_distance,
            self.btn_tool_path,
            self.btn_tool_identify,
        ]
        for btn in sphere_disabled_tools:
            if btn:
                btn.setEnabled(not is_sphere)
                if is_sphere:
                    btn.setToolTip(btn.toolTip().split(" (")[0] + " (not available in sphere view)")
                else:
                    # Restore original tooltip by stripping the suffix
                    tip = btn.toolTip()
                    if "(not available" in tip:
                        btn.setToolTip(tip.split(" (not available")[0])

        # If switching to sphere with a non-select tool active, revert to select
        if is_sphere and self.explore_mode and self.explore_tool != "select":
            self._set_explore_tool("select")

        # Time scrubber: hide in chart mode (RA/Dec is fixed),
        # show in polar/horizon/sphere when in explore mode
        show_scrubber = (mode != "equatorial") and self.explore_mode
        if self.time_scrubber_container:
            self.time_scrubber_container.setVisible(show_scrubber)
            if not show_scrubber and self._time_offset_minutes != 0.0:
                self._reset_time()

        if show_sky:
            self._update_time_label()

        if self.status_bar:
            labels = {
                "equatorial": "Chart view",
                "polar": "Polar planisphere",
                "horizon": "Horizon view",
                "sphere": "Celestial sphere — drag to rotate, I to toggle inside/outside",
            }
            self.status_bar.showMessage(labels.get(mode, mode))

    def _toggle_sphere_inside(self) -> None:
        """Toggle inside/outside view of the celestial sphere."""
        if self.sphere_widget:
            self.sphere_widget.toggle_inside_outside()
            self._update_inside_button()

    def _sphere_navigate(self, preset: str) -> None:
        """Navigate the sphere to a preset orientation."""
        if self.sphere_widget:
            self.sphere_widget.navigate_to(preset)

    def _update_inside_button(self) -> None:
        """Update the inside/outside button label."""
        if not hasattr(self, 'btn_view_inside') or not self.btn_view_inside:
            return
        if self.sphere_widget and not self.sphere_widget.view_outside:
            self.btn_view_inside.setText("Outside")
            self.btn_view_inside.setToolTip("Switch to outside view of the sphere")
        else:
            self.btn_view_inside.setText("Inside")
            self.btn_view_inside.setToolTip("Switch to inside view — see sky as observer")

    def _sphere_look_direction(self, rot_y_deg: float) -> None:
        """Rotate the sphere view to face a compass direction.

        In inside (dome) mode, this sets the gaze direction so
        that the chosen compass direction is centred on screen.
        In outside (globe) mode, this spins the globe so the
        observer's meridian faces that direction.

        Directions: N=0, E=90, S=180, W=270
        """
        if not self.sphere_widget:
            return

        if self.sphere_widget.view_outside:
            # Outside: spin the globe. rot_y controls the horizontal
            # rotation. We want the observer's meridian (HA=0) to face
            # the camera. Compass directions map to different rot_y values.
            # S=0 (default front), W=90, N=180, E=270
            globe_angles = {0: 180, 90: 270, 180: 0, 270: 90}
            self.sphere_widget.rot_y = float(globe_angles.get(
                int(rot_y_deg), rot_y_deg))
        else:
            # Inside: set gaze direction
            # The dome view has south as default forward (rot_y=0)
            # N=180, E=-90 (or 270), S=0, W=90
            dome_angles = {0: 180, 90: 270, 180: 0, 270: 90}
            self.sphere_widget.rot_y = float(dome_angles.get(
                int(rot_y_deg), rot_y_deg))

        self.sphere_widget.update()

    def _sphere_preset_view(self, preset: str) -> None:
        """Jump to a preset orientation on the sphere.

        Presets:
        - zenith: look straight up (inside) or top-down (outside)
        - scp: look towards the south celestial pole
        - ncp: look towards the north celestial pole
        - reset: return to default view
        """
        if not self.sphere_widget:
            return

        sw = self.sphere_widget

        if preset == "zenith":
            if sw.view_outside:
                # Outside: tilt to look down at the globe from above
                sw.rot_x = -89.0
                sw.rot_y = 0.0
            else:
                # Inside: look straight up
                sw.rot_x = -89.0
                sw.rot_y = 0.0

        elif preset == "scp":
            if sw.view_outside:
                # Outside: tilt so the SCP (bottom of the globe) faces us
                sw.rot_x = 89.0
                sw.rot_y = 0.0
            else:
                # Inside: look towards the SCP
                # SCP altitude from Brisbane = -(90 + lat) = -(90-27.5) = -62.5°
                # ... actually the SCP alt = lat = -27.5° (it's |lat| above the
                # southern horizon). So we need to look south and up by |lat|.
                sw.rot_x = sw.observer_lat  # negative = look up
                sw.rot_y = 0.0  # south is forward

        elif preset == "ncp":
            if sw.view_outside:
                # Outside: tilt so the NCP (top of globe) faces us
                sw.rot_x = -89.0
                sw.rot_y = 0.0
            else:
                # Inside: look north and down towards horizon
                # NCP is below the horizon from Brisbane
                sw.rot_x = -sw.observer_lat
                sw.rot_y = 180.0  # north

        elif preset == "reset":
            sw.rot_x = sw.observer_lat
            sw.rot_y = 0.0
            sw.sphere_zoom = 1.0

        sw.update()

    @property
    def _active_sky(self):
        """Return whichever sky widget is currently visible (star_map or sphere)."""
        if self.sphere_widget and self.sphere_widget.isVisible():
            return self.sphere_widget
        return self.star_map

    def _set_facing(self, az_deg: float) -> None:
        """Set the facing direction for horizon view."""
        if self.star_map:
            self.star_map.set_facing(az_deg)

    def _refresh_sky_time(self) -> None:
        """Called by timer to refresh the sky view with current time.
        Respects the time offset from the scrubber."""
        if self._time_offset_minutes != 0.0:
            # When offset is active, we set LST manually
            self._apply_time_offset()
            return
        if self.star_map and self.star_map.auto_time:
            if self.star_map.view_mode != "equatorial":
                self.star_map.refresh_time()
                self._update_time_label()
        if self.sphere_widget and self.sphere_widget.auto_time:
            self.sphere_widget.refresh_time()
        self._update_time_scrubber_display()

    def _update_time_label(self) -> None:
        """Update the time display label in the side panel."""
        if not self.time_label or not self.star_map:
            return
        import datetime
        now = datetime.datetime.now()
        if self._time_offset_minutes != 0.0:
            now += datetime.timedelta(minutes=self._time_offset_minutes)
        lst_h = self.star_map.lst_deg / 15.0
        auto_tag = "live" if self._time_offset_minutes == 0.0 else "offset"
        self.time_label.setText(
            f"Local: {now.strftime('%H:%M')}  |  LST: {lst_h:.1f}h  ({auto_tag})"
        )

    # ------------------------------------------------------------------
    # TIME SCRUBBER
    # ------------------------------------------------------------------

    def _on_time_slider_changed(self, value: int) -> None:
        """Handle slider movement — set time offset in minutes."""
        self._time_offset_minutes = float(value)
        self._apply_time_offset()

    def _step_time(self, minutes: float) -> None:
        """Step the time offset by the given number of minutes."""
        self._time_offset_minutes += minutes
        # Update slider if within range, otherwise just track offset
        if self.time_slider:
            clamped = max(-720, min(720, int(self._time_offset_minutes)))
            self.time_slider.blockSignals(True)
            self.time_slider.setValue(clamped)
            self.time_slider.blockSignals(False)
        self._apply_time_offset()

    def _reset_time(self) -> None:
        """Reset to live (real-time) mode."""
        self._time_offset_minutes = 0.0
        if self.time_slider:
            self.time_slider.blockSignals(True)
            self.time_slider.setValue(0)
            self.time_slider.blockSignals(False)
        # Re-enable auto time on both widgets
        if self.star_map:
            self.star_map.auto_time = True
            self.star_map.refresh_time()
        if self.sphere_widget:
            self.sphere_widget.auto_time = True
            self.sphere_widget.refresh_time()
        self._stop_time_animation()
        self._update_time_scrubber_display()
        self._update_time_label()

    def _apply_time_offset(self) -> None:
        """Compute and apply the offset LST to all sky widgets."""
        import datetime
        from coordinates import current_lst, _detect_utc_offset

        # Compute what the LST would be at now + offset
        now = datetime.datetime.now()
        offset_time = now + datetime.timedelta(minutes=self._time_offset_minutes)

        # We need to compute LST for the offset time.
        # Since current_lst uses datetime.now() internally, we compute
        # the JD manually for the offset time.
        from coordinates import datetime_to_jd, local_sidereal_time

        utc_offset = _detect_utc_offset()
        jd = datetime_to_jd(
            year=offset_time.year,
            month=offset_time.month,
            day=offset_time.day,
            hour=offset_time.hour,
            minute=offset_time.minute,
            second=offset_time.second,
            utc_offset_hours=utc_offset,
        )

        if self.star_map:
            lon = self.star_map.observer_lon
            lst = local_sidereal_time(jd, lon)
            self.star_map.auto_time = False
            self.star_map.lst_deg = lst
            self.star_map.update()

        if self.sphere_widget:
            lon = self.sphere_widget.observer_lon
            lst = local_sidereal_time(jd, lon)
            self.sphere_widget.auto_time = False
            self.sphere_widget.lst_deg = lst
            self.sphere_widget.update()

        self._update_time_scrubber_display()
        self._update_time_label()

    def _update_time_scrubber_display(self) -> None:
        """Update the time scrubber labels."""
        if not self.time_display_label:
            return
        import datetime

        now = datetime.datetime.now()
        sim_time = now + datetime.timedelta(minutes=self._time_offset_minutes)

        # Get LST from whichever widget is active
        lst_h = 0.0
        widget = self._active_sky
        if widget:
            lst_h = widget.lst_deg / 15.0

        self.time_display_label.setText(
            f"Simulated: {sim_time.strftime('%a %d %b %H:%M')}   "
            f"LST: {lst_h:.1f}h"
        )

        if self.time_offset_label:
            if abs(self._time_offset_minutes) < 0.5:
                self.time_offset_label.setText("Now (live)")
                self.time_offset_label.setStyleSheet(
                    f"font-size: 10px; color: {SpaceTheme.ACCENT_GREEN};"
                    f"padding: 0px; border: none;"
                )
            else:
                total = self._time_offset_minutes
                sign = "+" if total >= 0 else ""
                if abs(total) < 60:
                    offset_str = f"{sign}{total:.0f} min"
                elif abs(total) < 1440:
                    offset_str = f"{sign}{total / 60:.1f} hrs"
                else:
                    offset_str = f"{sign}{total / 1440:.1f} days"
                self.time_offset_label.setText(f"Offset: {offset_str}")
                self.time_offset_label.setStyleSheet(
                    f"font-size: 10px; color: {SpaceTheme.ACCENT_GOLD};"
                    f"padding: 0px; border: none;"
                )

    def _toggle_time_animation(self) -> None:
        """Start or stop time animation (play/pause)."""
        if self._time_animating:
            self._stop_time_animation()
        else:
            self._start_time_animation()

    def _start_time_animation(self) -> None:
        """Start advancing time automatically."""
        self._time_animating = True
        if self._btn_time_play:
            self._btn_time_play.setText("⏸ Pause")
        if self._time_anim_timer is None:
            self._time_anim_timer = QTimer(self)
            self._time_anim_timer.timeout.connect(self._time_anim_tick)
        # Tick every 50ms for smooth animation
        self._time_anim_timer.start(50)

    def _stop_time_animation(self) -> None:
        """Stop time animation."""
        self._time_animating = False
        if self._btn_time_play:
            self._btn_time_play.setText("▶ Play")
        if self._time_anim_timer:
            self._time_anim_timer.stop()

    def _time_anim_tick(self) -> None:
        """Advance time by one animation frame."""
        # _time_anim_speed is minutes per second
        # At 50ms intervals, that's speed * 0.05 minutes per tick
        step = self._time_anim_speed * 0.05
        self._time_offset_minutes += step
        # Update slider if in range
        if self.time_slider:
            clamped = max(-720, min(720, int(self._time_offset_minutes)))
            self.time_slider.blockSignals(True)
            self.time_slider.setValue(clamped)
            self.time_slider.blockSignals(False)
        self._apply_time_offset()

    def _apply_mode_ui(self) -> None:
        """
        Update the UI to reflect the current mode.
        """
        if self.explore_mode:
            # Hide quiz widgets
            for widget in self.quiz_widgets:
                widget.setVisible(False)

            if self.button_mode_toggle:
                self.button_mode_toggle.setText("Switch to Quiz")

            if self.question_label:
                self.question_label.setText("Explore Mode")

            self._set_feedback("Click any object on the map to learn about it.")

            # Clear quiz highlights
            if self.star_map:
                self.star_map.clear_highlights()
                self.star_map.explore_mode_active = True
            if self.sphere_widget:
                self.sphere_widget.clear_highlights()
                self.sphere_widget.explore_mode_active = True

            # Reset target and nearby panels
            self._update_target_info(None)
            if self.nearby_label:
                self.nearby_label.setText("Click an object to see what is nearby.")
                self.nearby_label.setStyleSheet(
                    f"font-size: 12px;"
                    f"color: {SpaceTheme.TEXT_MUTED};"
                    f"padding: 1px 0px;"
                    f"border: none;"
                )

            self.current_question = None

            # Show tools and pointer sections
            if self.tools_container:
                self.tools_container.setVisible(True)
            if self.pointer_header_widget:
                self.pointer_header_widget.setVisible(True)
            if self.pointer_label:
                self.pointer_label.setVisible(True)

            # Show time scrubber (unless in chart mode)
            is_chart = (self.star_map and self.star_map.view_mode == "equatorial"
                        and self.star_map.isVisible())
            if self.time_scrubber_container:
                self.time_scrubber_container.setVisible(not is_chart)
                if not is_chart:
                    self._update_time_scrubber_display()

            # Set default tool
            self._set_explore_tool("select")

            if self.status_bar:
                self.status_bar.showMessage("Explore mode — click any object to inspect it")

        else:
            # Show quiz widgets
            for widget in self.quiz_widgets:
                widget.setVisible(True)

            if self.button_mode_toggle:
                self.button_mode_toggle.setText("Switch to Explore")

            # Hide tools and pointer sections
            if self.tools_container:
                self.tools_container.setVisible(False)
            if self.pointer_header_widget:
                self.pointer_header_widget.setVisible(False)
            if self.pointer_label:
                self.pointer_label.setVisible(False)

            # Hide time scrubber and reset to live time
            if self.time_scrubber_container:
                self.time_scrubber_container.setVisible(False)
            self._reset_time()

            # Clear tool state
            self.path_objects = []
            if self.star_map:
                self.star_map.pointer_anchor = None
                self.star_map.pointer_target = None
                self.star_map.pointer_path = []
                self.star_map.explore_mode_active = False
            if self.sphere_widget:
                self.sphere_widget.explore_mode_active = False

            # Load a fresh question
            self.load_new_question()

            if self.status_bar:
                self.status_bar.showMessage("Quiz mode")

    def _set_explore_tool(self, tool: str) -> None:
        """Switch the active explore tool and update button styling."""
        self.explore_tool = tool

        # Clear previous tool state
        if self.star_map:
            self.star_map.pointer_anchor = None
            self.star_map.pointer_target = None
            self.star_map.pointer_path = []
            self.star_map.update()

        self.path_objects = []

        # Update button styling
        tool_buttons = {
            "select": self.btn_tool_select,
            "distance": self.btn_tool_distance,
            "path": self.btn_tool_path,
            "identify": self.btn_tool_identify,
        }
        for t, btn in tool_buttons.items():
            if btn is None:
                continue
            if t == tool:
                btn.setStyleSheet(
                    f"background-color: {SpaceTheme.ACCENT_BLUE};"
                    f"color: {SpaceTheme.TEXT_BRIGHT};"
                    f"border: 1px solid {SpaceTheme.ACCENT_CYAN};"
                    f"border-radius: 4px; font-size: 15px; font-weight: 600;"
                )
            else:
                btn.setStyleSheet(
                    f"background-color: {SpaceTheme.BG_ELEVATED};"
                    f"color: {SpaceTheme.TEXT_SECONDARY};"
                    f"border: 1px solid {SpaceTheme.BORDER_ACCENT};"
                    f"border-radius: 4px; font-size: 15px;"
                )

        # Update description — tool name + what it does
        descs = {
            "select": "Select — click objects to view details.",
            "distance": "Distance — click two objects to measure separation + hand size.",
            "path": "Path — click objects to build a star-hop chain. Click first stop to clear.",
            "identify": "Identify — click anywhere to see RA/Dec, constellation + nearest objects.",
        }
        if self.tool_desc_label:
            self.tool_desc_label.setText(descs.get(tool, ""))

        # Update pointer label with initial prompt
        if self.pointer_label:
            prompts = {
                "select": "",
                "distance": "Click first object (anchor).",
                "path": "Click first object to start the chain.",
                "identify": "Click anywhere on the sky.",
            }
            self.pointer_label.setText(prompts.get(tool, ""))
            self.pointer_label.setStyleSheet(
                f"font-size: 12px;"
                f"color: {SpaceTheme.TEXT_MUTED};"
                f"padding: 1px 0px;"
                f"border: none;"
            )

    def _handle_explore_click(self, clicked_object: dict) -> None:
        """
        Handle a click on an object in explore mode.
        Dispatches to the active tool.
        """
        if not self.star_map:
            return

        if self.explore_tool == "select":
            self._handle_select_click(clicked_object)
        elif self.explore_tool == "distance":
            self._handle_distance_click(clicked_object)
        elif self.explore_tool == "path":
            self._handle_path_click(clicked_object)
        elif self.explore_tool == "identify":
            # Object was clicked, treat as select
            self._handle_select_click(clicked_object)

    def _handle_sky_click(self, ra_deg: float, dec_deg: float) -> None:
        """Handle a click on empty sky (no object hit)."""
        if not self.explore_mode:
            return
        if self.explore_tool != "identify":
            return

        from coordinates import format_ra, format_dec

        ra_text = format_ra(ra_deg)
        dec_text = format_dec(dec_deg)

        if self.question_label:
            self.question_label.setText("Sky Position")

        self._set_feedback(f"RA {ra_text}, Dec {dec_text}", is_info=True)

        # Clear target info
        self._update_target_info(None)

        # Find nearest objects to clicked position
        all_objects = getattr(self.quiz_engine, "all_objects", [])
        if all_objects:
            neighbours = []
            for obj in all_objects:
                obj_ra = obj.get("ra_deg")
                obj_dec = obj.get("dec_deg")
                if obj_ra is None or obj_dec is None:
                    continue
                dist = angular_separation_deg(
                    ra_deg, dec_deg, float(obj_ra), float(obj_dec))
                neighbours.append((obj, dist))
            neighbours.sort(key=lambda x: x[1])

            # Determine nearest constellation
            nearest_const = "Unknown"
            if neighbours:
                nearest_const = neighbours[0][0].get("constellation", "Unknown")

            # Build structured nearby list
            if self.nearby_label:
                lines = []
                for obj, dist in neighbours[:5]:
                    name = obj.get("name", "?")
                    otype = str(obj.get("object_type", "")).replace("_", " ")
                    lines.append(f"{name} ({otype}, {dist:.1f}°)")
                self.nearby_label.setText("\n".join(lines))
                self.nearby_label.setStyleSheet(
                    f"font-size: 12px;"
                    f"color: {SpaceTheme.TEXT_SECONDARY};"
                    f"padding: 1px 0px;"
                    f"border: none;"
                )

            # Count objects within 5°
            within_5 = sum(1 for _, d in neighbours if d <= 5.0)
            within_10 = sum(1 for _, d in neighbours if d <= 10.0)

            # Find nearest star and nearest DSO separately
            nearest_star = next(
                (o for o, d in neighbours if o.get("object_type") == "star"), None)
            nearest_dso = next(
                (o for o, d in neighbours if o.get("object_type") != "star"), None)

            # Build pointer label with structured info
            if self.pointer_label:
                info = [f"RA {ra_text}", f"Dec {dec_text}"]
                info.append(f"Near: {nearest_const}")

                if nearest_star:
                    sd = next(d for o, d in neighbours if o is nearest_star)
                    info.append(f"Nearest star: {nearest_star.get('name','?')} ({sd:.1f}°)")
                if nearest_dso:
                    dd = next(d for o, d in neighbours if o is nearest_dso)
                    info.append(f"Nearest DSO: {nearest_dso.get('name','?')} ({dd:.1f}°)")

                info.append(f"Within 5°: {within_5} objects")

                self.pointer_label.setText("\n".join(info))
                self.pointer_label.setStyleSheet(
                    f"font-size: 11px;"
                    f"color: {SpaceTheme.INFO};"
                    f"padding: 1px 0px;"
                    f"border: none;"
                )

        if self.status_bar:
            self.status_bar.showMessage(f"Sky: RA {ra_text}, Dec {dec_text} — near {nearest_const}")

    def _handle_select_click(self, clicked_object: dict) -> None:
        """Select tool — just show object details."""
        name = clicked_object.get("name", "Unknown")
        object_type = str(clicked_object.get("object_type", "object")).replace("_", " ")

        if self.question_label:
            self.question_label.setText(name)

        self._set_feedback(
            f"{object_type.title()} in {clicked_object.get('constellation', 'Unknown')}",
            is_info=True,
        )

        self._update_target_info(clicked_object, reveal_position=True)
        self._update_nearby_objects(clicked_object)

        if self.status_bar:
            self.status_bar.showMessage(f"Viewing: {name}")

    def _handle_distance_click(self, clicked_object: dict) -> None:
        """Distance tool — two-object measurement."""
        name = clicked_object.get("name", "Unknown")
        object_type = str(clicked_object.get("object_type", "object")).replace("_", " ")
        clicked_id = str(clicked_object.get("id", ""))

        anchor = self.star_map.pointer_anchor
        anchor_id = str(anchor.get("id", "")) if anchor else ""

        if anchor is None:
            self.star_map.pointer_anchor = clicked_object
            self.star_map.pointer_target = None
        elif clicked_id == anchor_id:
            self.star_map.pointer_anchor = None
            self.star_map.pointer_target = None
        else:
            self.star_map.pointer_target = clicked_object

        self._update_pointer_label()

        if self.question_label:
            self.question_label.setText(name)
        self._set_feedback(
            f"{object_type.title()} in {clicked_object.get('constellation', 'Unknown')}",
            is_info=True,
        )
        self._update_target_info(clicked_object, reveal_position=True)
        self._update_nearby_objects(clicked_object)

    def _handle_path_click(self, clicked_object: dict) -> None:
        """Path tool — build a star-hop chain.

        Click behaviour:
        - Click new object: add to the chain
        - Re-click the last object: undo (remove it)
        - Click the first object: clear the entire path
        - Click any other existing object: ignored (no duplicate)
        """
        name = clicked_object.get("name", "Unknown")
        object_type = str(clicked_object.get("object_type", "object")).replace("_", " ")
        clicked_id = str(clicked_object.get("id", ""))

        if self.path_objects:
            first_id = str(self.path_objects[0].get("id", ""))
            last_id = str(self.path_objects[-1].get("id", ""))

            if clicked_id == first_id:
                # Clicked the first object — clear entire path
                self.path_objects = []
                self.star_map.pointer_path = []
                self.star_map.update()
                if self.pointer_label:
                    self.pointer_label.setText(
                        "Path cleared. Click an object to start a new chain."
                    )
                    self.pointer_label.setStyleSheet(
                        f"font-size: 12px;"
                        f"color: {SpaceTheme.TEXT_MUTED};"
                        f"padding: 1px 0px;"
                        f"border: none;"
                    )
            elif clicked_id == last_id and len(self.path_objects) > 1:
                # Re-clicked the last object — undo it
                self.path_objects.pop()
                self.star_map.pointer_path = list(self.path_objects)
                self.star_map.update()
                self._update_path_label()
            elif clicked_id not in [str(o.get("id", "")) for o in self.path_objects]:
                # New object — add to chain
                self.path_objects.append(clicked_object)
                self.star_map.pointer_path = list(self.path_objects)
                self.star_map.update()
                self._update_path_label()
            # else: object already in the middle of the chain — ignore
        else:
            # No path yet — start one
            self.path_objects.append(clicked_object)
            self.star_map.pointer_path = list(self.path_objects)
            self.star_map.update()
            self._update_path_label()

        if self.question_label:
            self.question_label.setText(name)
        self._set_feedback(
            f"{object_type.title()} in {clicked_object.get('constellation', 'Unknown')}",
            is_info=True,
        )
        self._update_target_info(clicked_object, reveal_position=True)
        self._update_nearby_objects(clicked_object)

    def _update_path_label(self) -> None:
        """Update the pointer label with path chain info."""
        if not self.pointer_label:
            return

        if len(self.path_objects) < 2:
            name = self.path_objects[0].get("name", "?") if self.path_objects else "?"
            self.pointer_label.setText(f"Start: {name}\nClick next object in the hop.")
            self.pointer_label.setStyleSheet(
                f"font-size: 12px;"
                f"color: {SpaceTheme.ACCENT_GREEN};"
                f"padding: 1px 0px;"
                f"border: none;"
            )
            return

        # Build chain description with per-leg distances
        total_angular = 0.0
        total_ly = 0.0
        has_all_ly = True
        longest_leg = 0.0
        leg_lines = []

        for i in range(1, len(self.path_objects)):
            prev = self.path_objects[i - 1]
            curr = self.path_objects[i]

            # Angular distance on the sky
            dist = angular_separation_deg(
                float(prev.get("ra_deg", 0)), float(prev.get("dec_deg", 0)),
                float(curr.get("ra_deg", 0)), float(curr.get("dec_deg", 0)),
            )
            total_angular += dist
            longest_leg = max(longest_leg, dist)

            # 3D distance in light years between the two objects
            prev_ly_str = prev.get("distance_ly", "")
            curr_ly_str = curr.get("distance_ly", "")
            prev_tag = self._format_ly_short(prev_ly_str)
            curr_tag = self._format_ly_short(curr_ly_str)

            leg_ly_text = ""
            if prev_ly_str and curr_ly_str:
                try:
                    leg_ly = self._compute_3d_distance(prev, curr)
                    total_ly += leg_ly
                    leg_ly_text = f" [{self._format_ly_short(str(leg_ly))} apart]"
                except (ValueError, TypeError):
                    has_all_ly = False
            else:
                has_all_ly = False

            prev_name = prev.get("name", "?")
            curr_name = curr.get("name", "?")

            if prev_tag and curr_tag:
                leg_lines.append(
                    f"  {i}. {prev_name} ({prev_tag}) → "
                    f"{curr_name} ({curr_tag}): {dist:.1f}°{leg_ly_text}"
                )
            else:
                leg_lines.append(
                    f"  {i}. {prev_name} → {curr_name}: {dist:.1f}°"
                )

        hand = self._hand_measurement(total_angular)
        avg = total_angular / len(leg_lines) if leg_lines else 0

        text = f"On the sky: {total_angular:.1f}° — {hand}\n"
        if has_all_ly and total_ly > 0:
            text += f"Through space: {self._format_ly_short(str(total_ly))}\n"
        text += f"{len(self.path_objects)} stops, {len(leg_lines)} hops\n"
        text += f"Avg: {avg:.1f}°  Longest: {longest_leg:.1f}°\n"
        text += "\n".join(leg_lines)
        text += f"\n\nClick first stop to clear."

        self.pointer_label.setText(text)
        self.pointer_label.setStyleSheet(
            f"font-size: 11px;"
            f"color: {SpaceTheme.ACCENT_GREEN};"
            f"padding: 1px 0px;"
            f"border: none;"
        )

    @staticmethod
    def _compute_3d_distance(obj_a: dict, obj_b: dict) -> float:
        """
        Compute the 3D Euclidean distance in light years between two objects.

        Converts RA/Dec/distance to cartesian coordinates and computes
        the straight-line distance through space.
        """
        import math

        ra1 = math.radians(float(obj_a.get("ra_deg", 0)))
        dec1 = math.radians(float(obj_a.get("dec_deg", 0)))
        d1 = float(obj_a.get("distance_ly", 0))

        ra2 = math.radians(float(obj_b.get("ra_deg", 0)))
        dec2 = math.radians(float(obj_b.get("dec_deg", 0)))
        d2 = float(obj_b.get("distance_ly", 0))

        # Convert to cartesian (x toward vernal equinox, z toward NCP)
        x1 = d1 * math.cos(dec1) * math.cos(ra1)
        y1 = d1 * math.cos(dec1) * math.sin(ra1)
        z1 = d1 * math.sin(dec1)

        x2 = d2 * math.cos(dec2) * math.cos(ra2)
        y2 = d2 * math.cos(dec2) * math.sin(ra2)
        z2 = d2 * math.sin(dec2)

        return math.sqrt((x2 - x1)**2 + (y2 - y1)**2 + (z2 - z1)**2)

    @staticmethod
    def _format_ly_short(distance_ly: str) -> str:
        """Format a light-year distance as a compact string."""
        if not distance_ly:
            return ""
        try:
            d = float(distance_ly)
            if d < 100:
                return f"{d:.1f} ly"
            elif d < 1000000:
                return f"{d:,.0f} ly"
            else:
                return f"{d / 1000000:.1f}M ly"
        except (ValueError, TypeError):
            return ""

    def _update_pointer_label(self) -> None:
        """
        Update the pointer measurement display in the side panel.
        """
        if not self.pointer_label or not self.star_map:
            return

        anchor = self.star_map.pointer_anchor
        target = self.star_map.pointer_target

        if anchor is None:
            self.pointer_label.setText("Click two objects to measure distance.")
            self.pointer_label.setStyleSheet(
                f"font-size: 12px;"
                f"color: {SpaceTheme.TEXT_MUTED};"
                f"padding: 1px 0px;"
                f"border: none;"
            )
            return

        anchor_name = anchor.get("name", "?")

        if target is None:
            self.pointer_label.setText(
                f"Anchor: {anchor_name}\nClick another object to measure."
            )
            self.pointer_label.setStyleSheet(
                f"font-size: 12px;"
                f"color: {SpaceTheme.ACCENT_GOLD};"
                f"padding: 1px 0px;"
                f"border: none;"
            )
            return

        target_name = target.get("name", "?")

        ra1 = float(anchor.get("ra_deg", 0))
        dec1 = float(anchor.get("dec_deg", 0))
        ra2 = float(target.get("ra_deg", 0))
        dec2 = float(target.get("dec_deg", 0))

        dist = angular_separation_deg(ra1, dec1, ra2, dec2)
        hand = self._hand_measurement(dist)

        # RA and Dec differences
        ra_diff = (ra2 - ra1 + 180) % 360 - 180  # signed shortest path
        dec_diff = dec2 - dec1

        # Direction description
        dirs = []
        if abs(dec_diff) > 0.5:
            dirs.append("north" if dec_diff > 0 else "south")
        if abs(ra_diff) > 0.5:
            # RA increases east (but displayed right-to-left)
            dirs.append("east" if ra_diff > 0 else "west")
        direction = " and ".join(dirs) if dirs else "same position"

        # FOV equivalence
        if dist <= 5:
            fov_note = "fits in a binocular field (5°)"
        elif dist <= 7:
            fov_note = "fills a wide binocular field"
        elif dist <= 1:
            fov_note = "fits in a telescope eyepiece"
        else:
            fov_note = ""

        lines = [f"{anchor_name} → {target_name}"]
        lines.append(f"{dist:.1f}° — {hand}")
        lines.append(f"Direction: {direction}")
        lines.append(f"ΔRA {abs(ra_diff):.1f}°  ΔDec {abs(dec_diff):.1f}°")
        if fov_note:
            lines.append(fov_note)
        lines.append(f"Click anchor to clear.")

        self.pointer_label.setText("\n".join(lines))
        self.pointer_label.setStyleSheet(
            f"font-size: 11px;"
            f"color: {SpaceTheme.ACCENT_GOLD};"
            f"padding: 1px 0px;"
            f"border: none;"
        )

    @staticmethod
    def _hand_measurement(degrees: float) -> str:
        """
        Convert angular degrees to a hand-at-arm's-length analogy.

        Standard hand measurements at arm's length:
          1°  ≈ pinky finger width
          2°  ≈ index finger width
          5°  ≈ three middle fingers
          10° ≈ closed fist width
          15° ≈ spread pinky to middle finger
          25° ≈ full hand span (thumb to pinky)
        """
        if degrees < 1.5:
            return f"about {degrees:.0f} pinky width"
        if degrees < 3.0:
            return f"about {degrees:.0f} finger widths"
        if degrees < 7.0:
            fingers = degrees / 5.0
            if fingers < 0.8:
                return "less than three-finger width"
            return f"about three-finger width"
        if degrees < 12.0:
            fists = degrees / 10.0
            return f"about {fists:.1f} fist widths"
        if degrees < 20.0:
            fists = degrees / 10.0
            return f"about {fists:.1f} fist widths"
        if degrees < 30.0:
            spans = degrees / 25.0
            return f"about {spans:.1f} hand spans"
        spans = degrees / 25.0
        return f"about {spans:.1f} hand spans"

        if self.status_bar:
            self.status_bar.showMessage(f"Viewing: {name}")

    # ------------------------------------------------------------------
    # QUIZ FLOW
    # ------------------------------------------------------------------

    def load_new_question(self) -> None:
        """
        Generate and display a new question from the quiz engine.
        """
        try:
            self.current_question = self.quiz_engine.generate_question()
            self.answer_revealed = False

            if not self.current_question:
                self._set_feedback("No question could be generated.", is_error=True)
                return

            prompt = self.current_question.get("prompt", "Unknown question")
            mode = self.current_question.get("mode", "unknown")

            if self.question_label:
                self.question_label.setText(prompt)

            if self.mode_label:
                self.mode_label.setText(
                    f"Type: {self._humanize_mode(mode)}"
                )

            self._update_catalog_label()
            self._update_object_count_label()

            if self.star_map:
                self.star_map.clear_highlights()
                self.star_map.set_target(None)
            if self.sphere_widget:
                self.sphere_widget.clear_highlights()
                self.sphere_widget.set_target(None)

            self._set_feedback("Click on the map to answer.")
            self._update_score_label()

            # Populate target context (partial — hides spoilers)
            target_object = self.current_question.get("target_object")
            self._update_target_info(target_object, reveal_position=False)
            self._update_nearby_objects(None)

            if self.status_bar:
                self.status_bar.showMessage("New question loaded")

        except Exception as exc:
            self._show_error(
                "Question Error",
                f"An error occurred while loading a new question:\n{exc}",
            )

    def handle_map_click(self, clicked_object: dict) -> None:
        """
        Handle an object click from the star map.

        Routes to either quiz answer checking or explore inspection
        depending on the current mode.

        Args:
            clicked_object: Dictionary representing the clicked object.
        """
        if self.explore_mode:
            self._handle_explore_click(clicked_object)
            return

        if not self.current_question:
            self._set_feedback("No active question.", is_error=True)
            return

        if self.answer_revealed:
            self._set_feedback(
                "Answer revealed. Press New Question to continue."
            )
            return

        try:
            result = self.quiz_engine.check_answer(
                question=self.current_question,
                clicked_object=clicked_object,
            )

            is_correct = result.get("correct", False)
            message = result.get("message", "No result message.")
            target_object = result.get("target_object")

            if is_correct:
                self.current_streak += 1
                if self.current_streak > self.best_streak:
                    self.best_streak = self.current_streak
                self._set_feedback(message, is_success=True)
            else:
                self.current_streak = 0
                self._set_feedback(message, is_error=True)

            if self._active_sky and target_object:
                self._active_sky.highlight_result(
                    clicked_object=clicked_object,
                    target_object=target_object,
                    is_correct=is_correct,
                )

            # Reveal full target info and nearby objects
            self._update_target_info(target_object, reveal_position=True)
            self._update_nearby_objects(target_object)

            self._update_score_label()

            if self.status_bar:
                self.status_bar.showMessage(message)

        except Exception as exc:
            self._show_error(
                "Answer Check Error",
                f"An error occurred while checking the answer:\n{exc}",
            )

    def show_answer(self) -> None:
        """
        Reveal the correct answer on the map.
        """
        if not self.current_question:
            self._set_feedback("No active question to reveal.")
            return

        try:
            target_object = self.current_question.get("target_object")
            if not target_object:
                self._set_feedback("This question has no target object.", is_error=True)
                return

            self.answer_revealed = True
            self.current_streak = 0

            if self._active_sky:
                self._active_sky.show_answer(target_object)

            target_name = target_object.get("name", "Unknown object")
            ra_text = target_object.get("ra_text", "Unknown RA")
            dec_text = target_object.get("dec_text", "Unknown Dec")
            constellation = target_object.get("constellation", "Unknown")
            object_type = str(target_object.get("object_type", "object")).replace("_", " ")

            self._set_feedback(
                f"Answer: {target_name} ({object_type}) in {constellation} "
                f"— RA {ra_text}, Dec {dec_text}",
                is_info=True,
            )

            # Reveal full target info and nearby objects
            self._update_target_info(target_object, reveal_position=True)
            self._update_nearby_objects(target_object)

            self._update_score_label()

            if self.status_bar:
                self.status_bar.showMessage("Answer revealed")

        except Exception as exc:
            self._show_error(
                "Reveal Error",
                f"An error occurred while revealing the answer:\n{exc}",
            )

    def reset_score(self) -> None:
        """
        Reset quiz score and refresh the display.
        """
        try:
            self.quiz_engine.reset_score()
            self.current_streak = 0
            self.best_streak = 0
            self._update_score_label()
            self._set_feedback("Score reset.")
            if self.status_bar:
                self.status_bar.showMessage("Score reset")
        except Exception as exc:
            self._show_error(
                "Reset Error",
                f"An error occurred while resetting the score:\n{exc}",
            )

    # ------------------------------------------------------------------
    # UI HELPERS
    # ------------------------------------------------------------------

    def _update_score_label(self) -> None:
        """
        Refresh the score and streak displays.
        """
        correct = self.quiz_engine.correct_answers
        total = self.quiz_engine.total_attempts

        if self.score_label:
            self.score_label.setText(f"{correct} / {total}")

        if self.streak_label:
            self.streak_label.setText(
                f"Streak: {self.current_streak}  |  Best: {self.best_streak}"
            )

    def _update_catalog_label(self) -> None:
        """
        Show which catalogs are currently enabled for question generation.
        """
        if not self.catalog_label:
            return

        include_stars = getattr(self.quiz_engine, "include_stars", False)
        include_deep_sky = getattr(self.quiz_engine, "include_deep_sky", False)

        if include_stars and include_deep_sky:
            text = "Catalogs: Stars + deep-sky"
        elif include_stars:
            text = "Catalogs: Stars only"
        elif include_deep_sky:
            text = "Catalogs: Deep-sky only"
        else:
            text = "Catalogs: None enabled"

        self.catalog_label.setText(text)

    def _update_object_count_label(self) -> None:
        """
        Show how many objects are currently loaded.
        """
        if not self.object_count_label:
            return

        star_count = len(getattr(self.quiz_engine, "star_catalog", []))
        deep_sky_count = len(getattr(self.quiz_engine, "deep_sky_catalog", []))

        self.object_count_label.setText(
            f"Objects: {star_count} stars, {deep_sky_count} DSOs"
        )

    def _set_feedback(
        self,
        message: str,
        is_success: bool = False,
        is_error: bool = False,
        is_info: bool = False,
    ) -> None:
        """
        Update the feedback label styling and content.

        Args:
            message: Message to display.
            is_success: Whether this is a success message.
            is_error: Whether this is an error message.
            is_info: Whether this is an informational message.
        """
        if not self.feedback_label:
            return

        color = SpaceTheme.TEXT_SECONDARY
        if is_success:
            color = SpaceTheme.SUCCESS
        elif is_error:
            color = SpaceTheme.ERROR
        elif is_info:
            color = SpaceTheme.INFO

        self.feedback_label.setText(message)
        self.feedback_label.setStyleSheet(
            f"font-size: 13px;"
            f"color: {color};"
            f"padding: 0px;"
            f"background: transparent;"
            f"border: none;"
        )

    def _update_target_info(self, target_object: Optional[dict], reveal_position: bool = False) -> None:
        """
        Populate the target context panel from a question's target object.

        For name-based questions, the coordinates are hidden until the
        answer is revealed. For coordinate-based questions, the name and
        aliases are hidden until reveal.

        Args:
            target_object: The current question's target object dict.
            reveal_position: Whether to show full details (after answering).
        """
        if not target_object:
            if self.target_name_label:
                self.target_name_label.setText("—")
            for label in (
                self.target_type_label,
                self.target_constellation_label,
                self.target_magnitude_label,
                self.target_coords_label,
                self.target_aliases_label,
                self.target_properties_label,
                self.target_transit_label,
            ):
                if label:
                    label.setText("")
            return

        mode = ""
        if self.current_question:
            mode = self.current_question.get("mode", "")

        is_coords_mode = "coords" in mode
        is_alias_mode = mode == "alias_to_object"
        is_constellation_mode = mode == "constellation_find"

        # Name — hide for coordinate and alias questions until revealed
        name = target_object.get("name", "Unknown")
        if (is_coords_mode or is_alias_mode) and not reveal_position:
            if self.target_name_label:
                self.target_name_label.setText("???")
        elif is_constellation_mode and not reveal_position:
            constellation = target_object.get("constellation", "Unknown")
            if self.target_name_label:
                self.target_name_label.setText(constellation)
        else:
            if self.target_name_label:
                self.target_name_label.setText(name)

        # Object type — always show
        object_type = str(target_object.get("object_type", "object")).replace("_", " ").title()
        if self.target_type_label:
            self.target_type_label.setText(object_type)

        # Constellation — always show
        constellation = target_object.get("constellation", "Unknown")
        if self.target_constellation_label:
            self.target_constellation_label.setText(f"in {constellation}")

        # Magnitude — always show
        magnitude = target_object.get("magnitude")
        if self.target_magnitude_label:
            if magnitude is not None:
                try:
                    mag_val = float(magnitude)
                    if mag_val < 0:
                        brightness = "very bright"
                    elif mag_val < 1.5:
                        brightness = "bright"
                    elif mag_val < 3.0:
                        brightness = "moderate"
                    elif mag_val < 5.0:
                        brightness = "faint"
                    else:
                        brightness = "very faint"
                    self.target_magnitude_label.setText(
                        f"Magnitude {mag_val:+.2f} ({brightness})"
                    )
                except (ValueError, TypeError):
                    self.target_magnitude_label.setText("")
            else:
                self.target_magnitude_label.setText("")

        # Coordinates — hide for non-coordinate modes until revealed
        ra_text = target_object.get("ra_text", "")
        dec_text = target_object.get("dec_text", "")
        if self.target_coords_label:
            if not is_coords_mode and not reveal_position:
                self.target_coords_label.setText("Coordinates hidden until answered")
                self.target_coords_label.setStyleSheet(
                    f"font-size: 11px;"
                    f"font-style: italic;"
                    f"color: {SpaceTheme.TEXT_MUTED};"
                    f"padding: 1px 0px;"
                    f"border: none;"
                )
            else:
                self.target_coords_label.setText(f"RA {ra_text}, Dec {dec_text}")
                self.target_coords_label.setStyleSheet(
                    f"font-size: 12px;"
                    f"color: {SpaceTheme.TEXT_MUTED};"
                    f"padding: 1px 0px;"
                    f"border: none;"
                )

        # Aliases — hide for coordinate and alias questions until revealed
        aliases = target_object.get("aliases", [])
        if self.target_aliases_label:
            if (is_coords_mode or is_alias_mode) and not reveal_position:
                self.target_aliases_label.setText("")
            elif is_constellation_mode and not reveal_position:
                self.target_aliases_label.setText("Click any object in the constellation.")
            elif aliases:
                alias_text = ", ".join(str(a) for a in aliases[:4])
                if len(aliases) > 4:
                    alias_text += f" (+{len(aliases) - 4} more)"
                self.target_aliases_label.setText(f"Also: {alias_text}")
            else:
                self.target_aliases_label.setText("")

        # Physical properties — always show (not spoilers)
        if self.target_properties_label:
            props = []
            distance = target_object.get("distance_ly")
            if distance:
                try:
                    d = float(distance)
                    if d < 100:
                        props.append(f"{d:.1f} light years away")
                    elif d < 1000000:
                        props.append(f"{d:,.0f} light years away")
                    else:
                        # Millions of light years for galaxies
                        props.append(f"{d / 1000000:.1f} million light years away")
                except (ValueError, TypeError):
                    pass

            colour = target_object.get("colour_desc", "")
            if colour:
                props.append(colour)

            lum = target_object.get("luminosity_solar")
            if lum:
                try:
                    l = float(lum)
                    if l < 0.01:
                        props.append(f"{l:.4f}× Sun luminosity")
                    elif l < 1.0:
                        props.append(f"{l:.2f}× Sun luminosity")
                    elif l < 100:
                        props.append(f"{l:.1f}× Sun luminosity")
                    else:
                        props.append(f"{l:,.0f}× Sun luminosity")
                except (ValueError, TypeError):
                    # Non-numeric luminosity (e.g. DSO special notes)
                    props.append(str(lum))

            notes = target_object.get("notes", "")
            if notes:
                props.append(notes)

            if props:
                self.target_properties_label.setText("\n".join(props))
            else:
                self.target_properties_label.setText("")

        # Transit time — computed live
        if self.target_transit_label and self.star_map:
            ra_deg = target_object.get("ra_deg")
            if ra_deg is not None:
                try:
                    self.target_transit_label.setText(
                        self._compute_transit_text(float(ra_deg))
                    )
                except (ValueError, TypeError):
                    self.target_transit_label.setText("")
            else:
                self.target_transit_label.setText("")

    def _update_nearby_objects(self, target_object: Optional[dict]) -> None:
        """
        Show notable objects near the target after answering.

        Finds the closest objects from the full catalogue and displays
        them with angular distances to help build spatial awareness.

        Args:
            target_object: The answered question's target object dict.
        """
        if not self.nearby_label:
            return

        if not target_object:
            self.nearby_label.setText("Answer to reveal nearby objects.")
            self.nearby_label.setStyleSheet(
                f"font-size: 12px;"
                f"color: {SpaceTheme.TEXT_MUTED};"
                f"padding: 1px 0px;"
                f"border: none;"
            )
            return

        target_ra = target_object.get("ra_deg")
        target_dec = target_object.get("dec_deg")
        target_id = str(target_object.get("id", "")).strip()

        if target_ra is None or target_dec is None:
            self.nearby_label.setText("No coordinate data available.")
            return

        target_ra = float(target_ra)
        target_dec = float(target_dec)

        # Gather all objects from the quiz engine catalogues
        all_objects = getattr(self.quiz_engine, "all_objects", [])
        if not all_objects:
            self.nearby_label.setText("No catalogue loaded.")
            return

        # Compute distances and sort
        neighbours = []
        for obj in all_objects:
            obj_id = str(obj.get("id", "")).strip()
            if obj_id == target_id:
                continue

            obj_ra = obj.get("ra_deg")
            obj_dec = obj.get("dec_deg")
            if obj_ra is None or obj_dec is None:
                continue

            distance = angular_separation_deg(
                ra1_deg=target_ra,
                dec1_deg=target_dec,
                ra2_deg=float(obj_ra),
                dec2_deg=float(obj_dec),
            )
            neighbours.append((obj, distance))

        neighbours.sort(key=lambda x: x[1])

        # Show the closest 4
        lines = []
        for obj, dist in neighbours[:4]:
            obj_name = obj.get("name", "Unknown")
            obj_type = str(obj.get("object_type", "")).replace("_", " ")
            lines.append(f"{obj_name} ({obj_type}, {dist:.1f}°)")

        if lines:
            self.nearby_label.setText("\n".join(lines))
            self.nearby_label.setStyleSheet(
                f"font-size: 12px;"
                f"color: {SpaceTheme.TEXT_SECONDARY};"
                f"padding: 1px 0px;"
                f"border: none;"
            )
        else:
            self.nearby_label.setText("No nearby objects found.")

    def _compute_transit_text(self, ra_deg: float) -> str:
        """
        Compute when an object transits (crosses the meridian) tonight.

        Transit occurs when LST = object's RA. We compute the local
        civil time when this happens.

        Args:
            ra_deg: Object's right ascension in degrees.

        Returns:
            str: Transit time description.
        """
        if not self.star_map:
            return ""

        import datetime

        current_lst = self.star_map.lst_deg
        now = datetime.datetime.now()

        # How many degrees of LST until the object transits
        # LST advances ~360° per sidereal day (23h 56m)
        lst_to_transit = (ra_deg - current_lst) % 360.0

        # Convert LST degrees to solar hours (360° ≈ 23.9345 hours)
        hours_until = lst_to_transit / 15.041

        transit_time = now + datetime.timedelta(hours=hours_until)

        if hours_until < 0.25:
            return "Transiting now (on the meridian)"
        elif hours_until < 1.0:
            return f"Transits at {transit_time.strftime('%H:%M')} (in {hours_until * 60:.0f} min)"
        elif hours_until < 12.0:
            return f"Transits at {transit_time.strftime('%H:%M')} (in {hours_until:.1f} hrs)"
        else:
            return f"Transits at {transit_time.strftime('%H:%M')} tomorrow"

    def _show_error(self, title: str, message: str) -> None:
        """
        Show a message box for unexpected errors.
        """
        QMessageBox.critical(self, title, message)

    def _humanize_mode(self, mode: str) -> str:
        """
        Turn an internal mode string into a readable label.
        """
        mode_map = {
            "name_to_star": "Find a named star",
            "coords_to_star": "Star by coordinates",
            "name_to_deep_sky": "Find a named DSO",
            "coords_to_deep_sky": "DSO by coordinates",
            "name_to_object": "Find a named object",
            "coords_to_object": "Object by coordinates",
            "alias_to_object": "Find by alias",
            "constellation_find": "Find in constellation",
        }

        if mode in mode_map:
            return mode_map[mode]

        return mode.replace("_", " ").title()

    def show_about_dialog(self) -> None:
        """
        Show an about dialog with controls reference.
        """
        QMessageBox.information(
            self,
            "About Southern Sky Trainer",
            (
                "Southern Sky Trainer\n\n"
                "An educational star map and sky navigation tool.\n"
                "Learn to find stars, deep-sky objects, and constellations "
                "using right ascension and declination.\n\n"
                "Controls:\n"
                "  Scroll wheel — Zoom in / out\n"
                "  Drag — Pan the map\n"
                "  Double-click — Centre on an object\n"
                "  1 — Toggle stars\n"
                "  2 — Toggle deep-sky objects\n"
                "  3 — Toggle constellation lines\n"
                "  4 — Toggle sub-grid lines\n"
                "  5 — Toggle cursor crosshair\n"
                "  R — Reset view\n"
                "  +  /  − — Zoom in / out\n"
                "  Arrow keys — Pan\n"
                "  Ctrl+N — New question\n"
                "  Ctrl+A — Show answer\n"
                "  Ctrl+E — Toggle Explore / Quiz mode\n\n"
                "Sky Views:\n"
                "  Chart — flat RA/Dec equatorial projection\n"
                "  Polar — south-centred planisphere (live time)\n"
                "  Horizon — local sky view facing N/E/S/W (live time)\n"
                "  Sphere — 3D celestial sphere you can rotate\n\n"
                "Sphere Controls:\n"
                "  Drag — rotate the sphere\n"
                "  I — toggle inside/outside view\n"
                "  Arrow keys — rotate\n\n"
                "In Horizon view, drag to rotate facing direction.\n"
                "Arrow keys rotate facing. Scroll to zoom FOV."
            ),
        )