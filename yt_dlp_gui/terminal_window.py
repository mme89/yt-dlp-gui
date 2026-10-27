"""Separate Qt window for displaying and clearing yt-dlp output."""

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QHBoxLayout, QPushButton, QTextEdit, QVBoxLayout, QWidget


class TerminalWindow(QWidget):
    """Separate window for terminal output."""

    closed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent, Qt.WindowType.Window)
        self.setWindowTitle("Terminal Output - yt-dlp")
        self.setMinimumSize(800, 500)

        if parent:
            parent_geo = parent.geometry()
            self.setGeometry(
                parent_geo.x() + 50,
                parent_geo.y() + 50,
                800,
                500,
            )

        layout = QVBoxLayout(self)

        self.output = QTextEdit()
        self.output.setReadOnly(True)
        self.output.setFont(QFont("Menlo", 10))
        layout.addWidget(self.output)

        button_layout = QHBoxLayout()
        clear_btn = QPushButton("Clear")
        clear_btn.clicked.connect(self.output.clear)
        button_layout.addWidget(clear_btn)

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.close)
        button_layout.addWidget(close_btn)

        layout.addLayout(button_layout)

    def closeEvent(self, event):
        """Handle window close event."""
        self.closed.emit()
        super().closeEvent(event)

    def append(self, text):
        """Append text to the output."""
        self.output.append(text)

    def clear(self):
        """Clear the output."""
        self.output.clear()
