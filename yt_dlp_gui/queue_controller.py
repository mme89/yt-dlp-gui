"""Download queue management and sequential processing controller."""

from collections.abc import Callable
from typing import TYPE_CHECKING, Any, cast

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QMessageBox, QTableWidgetItem, QWidget

from .commands import build_output_template
from .workers import DownloadThread


class QueueMixin:
    """Mixin coordinating queue entries, table rendering, and sequential downloads."""

    COLORS: dict[str, str]
    download_queue: list[dict[str, Any]]
    is_processing_queue: bool
    current_queue_item: Any
    download_thread: Any
    analyzed_url: Any
    is_closing: bool
    title_label: Any
    queue_table: Any
    queue_status_label: Any
    progress_bar: Any
    status_label: Any
    abort_btn: Any

    if TYPE_CHECKING:
        get_validated_url: Callable[[], str | None]
        build_selected_download_args: Callable[[], Any]
        calculate_format_size: Callable[[str], str]
        build_ytdlp_args: Callable[..., Any]
        get_ytdlp_path: Callable[[], str]
        set_command_controls_enabled: Callable[[bool], None]
        warn_if_ytdlp_command_running: Callable[[], bool]
        track_worker_thread: Callable[[Any], None]
        append_terminal_output: Callable[[str], None]
        statusBar: Callable[[], Any]
        sender: Callable[[], Any]

    def add_to_queue(self):
        """Add current video to download queue."""
        url = self.get_validated_url()
        if url is None:
            return

        selection = self.build_selected_download_args()
        if not selection:
            return

        args, format_id, format_display = selection

        if url == self.analyzed_url and self.title_label.text() != "Title: -":
            title = self.title_label.text().removeprefix("Title: ")
            total_size = self.calculate_format_size(format_id)
        else:
            title = "Unknown"
            total_size = "Unknown"

        queue_item = {
            "url": url,
            "args": args,
            "format": format_id,
            "format_display": format_display,
            "title": title,
            "size": total_size,
            "status": "Pending",
        }
        self.download_queue.append(queue_item)
        self.update_queue_table()
        self.set_command_controls_enabled(True)

        QMessageBox.information(
            cast(QWidget, self),
            "Added to Queue",
            f"Video added to queue!\n\nTotal items in queue: {len(self.download_queue)}",
        )

    def update_queue_table(self):
        """Update the queue table display."""
        self.queue_table.setRowCount(len(self.download_queue))

        for i, item in enumerate(self.download_queue):
            index_item = QTableWidgetItem(str(i + 1))
            index_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.queue_table.setItem(i, 0, index_item)

            status_item = QTableWidgetItem(item["status"])
            status_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            if item["status"] == "Completed":
                status_item.setForeground(QColor(self.COLORS["success"]))
            elif item["status"] == "Failed":
                status_item.setForeground(QColor(self.COLORS["error"]))
            elif item["status"] == "Downloading":
                status_item.setForeground(QColor(self.COLORS["info"]))
            elif item["status"] == "Aborted":
                status_item.setForeground(QColor(self.COLORS["warning"]))
            self.queue_table.setItem(i, 1, status_item)

            url_display = item["url"][:50] + "..." if len(item["url"]) > 50 else item["url"]
            self.queue_table.setItem(i, 2, QTableWidgetItem(url_display))

            self.queue_table.setItem(i, 3, QTableWidgetItem(item["title"]))

            format_display = item.get("format_display", item["format"])
            format_item = QTableWidgetItem(format_display)
            format_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.queue_table.setItem(i, 4, format_item)

            size_display = item.get("size", "Unknown")
            size_item = QTableWidgetItem(size_display)
            size_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.queue_table.setItem(i, 5, size_item)

        if len(self.download_queue) == 0:
            self.queue_status_label.setText("Queue is empty. Add videos from the Download tab.")
        else:
            completed = sum(1 for item in self.download_queue if item["status"] == "Completed")
            failed = sum(1 for item in self.download_queue if item["status"] == "Failed")
            pending = sum(1 for item in self.download_queue if item["status"] == "Pending")
            downloading = sum(1 for item in self.download_queue if item["status"] == "Downloading")
            aborted = sum(1 for item in self.download_queue if item["status"] == "Aborted")
            parts = [
                f"Total: {len(self.download_queue)}",
                f"Pending: {pending}",
            ]
            if downloading:
                parts.append(f"Downloading: {downloading}")
            parts.extend([f"Completed: {completed}", f"Failed: {failed}"])
            if aborted:
                parts.append(f"Aborted: {aborted}")
            self.queue_status_label.setText(" | ".join(parts))

    def start_queue_processing(self):
        """Start processing the download queue."""
        if not self.download_queue:
            QMessageBox.warning(cast(QWidget, self), "Error", "Queue is empty!")
            return

        if not any(item["status"] == "Pending" for item in self.download_queue):
            QMessageBox.information(
                cast(QWidget, self), "Queue", "There are no pending items in the queue."
            )
            return

        if self.is_processing_queue:
            QMessageBox.warning(cast(QWidget, self), "Error", "Queue is already being processed!")
            return

        if self.warn_if_ytdlp_command_running():
            return

        self.is_processing_queue = True
        self.set_command_controls_enabled(False)
        self.statusBar().showMessage("Processing queue...")
        self.process_next_in_queue()

    def process_next_in_queue(self):
        """Process the next item in the queue."""
        if not self.is_processing_queue:
            return

        next_item = None
        for item in self.download_queue:
            if item["status"] == "Pending":
                next_item = item
                break

        if not next_item:
            self.is_processing_queue = False
            self.set_command_controls_enabled(True)
            self.progress_bar.setValue(0)
            self.progress_bar.setTextVisible(False)
            self.status_label.setText("")
            self.abort_btn.setEnabled(False)
            self.statusBar().showMessage("Queue processing completed!", 5000)
            QMessageBox.information(
                cast(QWidget, self),
                "Queue Complete",
                "All downloads in the queue have been processed!",
            )
            return

        next_item["status"] = "Downloading"
        self.current_queue_item = next_item
        self.update_queue_table()

        if not self.run_yt_dlp_queue(
            next_item["args"], next_item["url"], next_item.get("format_display", "")
        ):
            next_item["status"] = "Pending"
            self.current_queue_item = None
            self.is_processing_queue = False
            self.set_command_controls_enabled(True)
            self.update_queue_table()

    def run_yt_dlp_queue(self, args, url, format_display=""):
        """Run yt-dlp for queue item."""
        if self.warn_if_ytdlp_command_running():
            return False

        output_template = build_output_template(format_display, fallback_format_id=True)

        args = self.build_ytdlp_args(args, is_download=True, output_template=output_template)
        if args is None:
            return False

        self.append_terminal_output(f"\n{'='*60}\n")
        self.append_terminal_output(f"Queue: Processing {url}\n")
        self.append_terminal_output(f"Running: yt-dlp {' '.join(args)}\n")
        self.append_terminal_output(f"{'='*60}\n")

        self.set_command_controls_enabled(False)

        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.status_label.setText("Starting download...")
        self.abort_btn.setEnabled(True)

        self.download_thread = DownloadThread(args, url, self.get_ytdlp_path())
        self.track_worker_thread(self.download_thread)
        self.download_thread.output.connect(self.append_terminal_output)
        self.download_thread.progress.connect(self.update_queue_progress)
        self.download_thread.finished_signal.connect(self.on_queue_download_finished)
        self.download_thread.start()
        return True

    def update_queue_progress(self, percentage, status):
        """Update progress bar and status label on Download page."""
        self.progress_bar.setValue(percentage)
        self.status_label.setText(status)

    def on_queue_download_finished(self, exit_code):
        """Handle completion of queue item download."""
        thread = self.sender()
        if thread is not self.download_thread:
            return
        stop_requested = getattr(thread, "stop_requested", False)
        self.download_thread = None
        if self.is_closing:
            return

        was_aborted = stop_requested and exit_code != 0
        finished_item = self.current_queue_item
        self.current_queue_item = None

        if finished_item:
            if exit_code == 0:
                finished_item["status"] = "Completed"
            elif was_aborted:
                finished_item["status"] = "Aborted"
            else:
                finished_item["status"] = "Failed"
            self.update_queue_table()

        if self.is_processing_queue:
            self.process_next_in_queue()
        else:
            self.abort_btn.setEnabled(False)
            self.set_command_controls_enabled(True)

    def stop_queue_processing(self):
        """Stop processing the queue."""
        if not self.is_processing_queue:
            return

        reply = QMessageBox.question(
            cast(QWidget, self),
            "Stop Queue",
            "Stop processing the queue?\n\nThe current download will be aborted.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.Yes:
            if not self.is_processing_queue:
                return
            self.is_processing_queue = False

            self.progress_bar.setValue(0)
            self.progress_bar.setTextVisible(False)
            self.status_label.setText("")
            self.abort_btn.setEnabled(False)

            thread = self.download_thread
            if thread and thread.isRunning():
                thread.stop()

            if self.current_queue_item and self.current_queue_item["status"] == "Downloading":
                self.current_queue_item["status"] = "Pending"
                self.update_queue_table()
            self.current_queue_item = None
            self.set_command_controls_enabled(True)

            self.statusBar().showMessage("Queue processing stopped", 3000)

    def clear_queue(self):
        """Clear all items from the queue."""
        if not self.download_queue:
            return

        if self.is_processing_queue:
            QMessageBox.warning(
                cast(QWidget, self),
                "Queue Running",
                "Cannot clear the queue while it is being processed. Stop the queue first.",
            )
            return

        reply = QMessageBox.question(
            cast(QWidget, self),
            "Clear Queue",
            f"Remove all {len(self.download_queue)} items from the queue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.Yes:
            if self.is_processing_queue:
                return
            self.download_queue.clear()
            self.update_queue_table()
            self.set_command_controls_enabled(True)

    def remove_selected_from_queue(self):
        """Remove selected items from the queue."""
        selected_rows = sorted(set(item.row() for item in self.queue_table.selectedItems()))

        if not selected_rows:
            QMessageBox.warning(cast(QWidget, self), "Error", "Please select items to remove!")
            return

        items_to_remove = [
            self.download_queue[row] for row in selected_rows if row < len(self.download_queue)
        ]
        if any(item["status"] == "Downloading" for item in items_to_remove):
            QMessageBox.warning(
                cast(QWidget, self),
                "Error",
                "Cannot remove item that is currently downloading!",
            )
            return

        reply = QMessageBox.question(
            cast(QWidget, self),
            "Remove Items",
            f"Remove {len(items_to_remove)} selected item(s) from queue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.Yes:
            removable_ids = {
                id(item) for item in items_to_remove if item["status"] != "Downloading"
            }
            self.download_queue = [
                item for item in self.download_queue if id(item) not in removable_ids
            ]

            self.update_queue_table()
            self.set_command_controls_enabled(True)
