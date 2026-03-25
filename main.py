"""
main.py

Entry point for the Astronomy Trainer application.

This file is intentionally kept small. Its job is to:
1. Create the Qt application
2. Create the main window
3. Show the window
4. Start the event loop
"""

import sys
from PySide6.QtWidgets import QApplication

from app_window import AppWindow


def main() -> int:
    """
    Main entry point for the application.

    Returns:
        int: Exit code returned by the Qt event loop.
    """
    app = QApplication(sys.argv)
    app.setApplicationName("Astronomy Trainer")
    app.setOrganizationName("Orion Labs")

    window = AppWindow()
    window.show()

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())