"""Separate Qt window for displaying and clearing yt-dlp output."""

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFontDatabase, QTextCursor
from PySide6.QtWidgets import QHBoxLayout, QPlainTextEdit, QPushButton, QVBoxLayout, QWidget


class TerminalWindow(QWidget):
    """Separate window for terminal output."""

    closed = Signal()
    cleared = Signal()
    MAX_BLOCKS = 5000

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

        self.output = QPlainTextEdit()
        self.output.setReadOnly(True)
        self.output.setMaximumBlockCount(self.MAX_BLOCKS)
        fixed_font = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
        fixed_font.setPointSize(10)
        self.output.setFont(fixed_font)
        layout.addWidget(self.output)

        button_layout = QHBoxLayout()
        clear_btn = QPushButton("Clear")
        clear_btn.clicked.connect(self.clear)
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
        """Append plain text without adding extra blank lines."""
        cursor = self.output.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        cursor.insertText(text)
        self.output.setTextCursor(cursor)
        self.output.ensureCursorVisible()

    def set_text(self, text):
        """Replace output content with buffered plain text and scroll to the end."""
        self.output.setPlainText(text)
        cursor = self.output.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self.output.setTextCursor(cursor)
        self.output.ensureCursorVisible()

    def clear(self):
        """Clear the output and notify listeners."""
        self.output.clear()
        self.cleared.emit()
