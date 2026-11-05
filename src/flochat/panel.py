"""Optional Qt native desktop client. No database, credentials, engine or API access."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from contextlib import suppress

from flochat.errors import FloChatError
from flochat.ipc import Client


def show_panel(config):
    try:
        from PySide6.QtCore import QObject, QRunnable, Qt, QThreadPool, QTimer, Signal
        from PySide6.QtWidgets import (
            QApplication,
            QComboBox,
            QDialog,
            QHBoxLayout,
            QLabel,
            QLineEdit,
            QMainWindow,
            QMessageBox,
            QPlainTextEdit,
            QPushButton,
            QVBoxLayout,
            QWidget,
        )
    except (ImportError, OSError):
        raise FloChatError(
            "Qt could not load. Install .[desktop] in the existing venv and check native "
            "shared libraries (Linux: GL/EGL, xkbcommon, D-Bus) and display. "
            "An installed Python extra does not verify native runtime support."
        ) from None

    class Replies(QObject):
        finished = Signal(str, object, object, int)

    class Request(QRunnable):
        def __init__(self, client, replies, command, args, generation):
            super().__init__()
            self.client, self.replies, self.command, self.args = client, replies, command, args
            self.generation = generation

        def run(self):
            try:
                self.replies.finished.emit(
                    self.command, self.client.call(self.command, **self.args), None, self.generation
                )
            except FloChatError as exc:
                self.replies.finished.emit(self.command, None, str(exc), self.generation)
            except Exception:
                self.replies.finished.emit(
                    self.command,
                    None,
                    "Local UI operation failed; inspect status/history. No automatic retry.",
                    self.generation,
                )

    class Window(QMainWindow):
        def __init__(self):
            super().__init__()
            self.client = Client(config)
            self.client.call("attach")
            self.pool = QThreadPool(self)
            self.pool.setMaxThreadCount(4)
            self.replies = Replies(self)
            self.replies.finished.connect(self.complete)
            self.polling = False
            self.busy = False
            self.review = None
            self.review_observed_at = 0.0
            self.generation = 0
            self.mode = "manual"
            self.setWindowTitle("FloChat · Your Live Chat, Always Within Reach")
            self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
            self.resize(410, 600)
            container = QWidget()
            layout = QVBoxLayout(container)
            layout.setSpacing(10)
            self.setCentralWidget(container)
            title = QLabel("FloChat")
            title.setStyleSheet("font-size:22px;font-weight:600;")
            layout.addWidget(title)
            self.status = QPlainTextEdit()
            self.status.setReadOnly(True)
            self.status.setMaximumHeight(145)
            self.status.setAccessibleName("Application, connection and destination status")
            layout.addWidget(self.status)
            self.editor = QPlainTextEdit()
            self.editor.setPlaceholderText("Prepare a comment locally…")
            self.editor.setAccessibleName("Comment editor")
            layout.addWidget(self.editor)
            row = QHBoxLayout()
            self.drafts = QComboBox()
            self.drafts.setAccessibleName("Saved drafts")
            row.addWidget(self.drafts)
            self.button(row, "Open draft", lambda: self.send("draft", id=self.drafts.currentData()))
            layout.addLayout(row)
            row = QHBoxLayout()
            self.button(
                row, "Save editor", lambda: self.send("edit", text=self.editor.toPlainText())
            )
            self.button(row, "Preview", lambda: self.send("preview"))
            self.button(row, "Review & send", lambda: self.send("prepare"))
            layout.addLayout(row)
            row = QHBoxLayout()
            for name in ("Start", "Pause", "Resume", "Stop"):
                action = name.lower()
                self.button(row, name, lambda checked=False, action=action: self.send(action))
            layout.addLayout(row)
            row = QHBoxLayout()
            self.button(row, "Recover connection", lambda: self.send("recover"))
            self.button(row, "Cancel review", lambda: self.send("cancel"))
            self.button(row, "Open terminal", self.terminal_help)
            layout.addLayout(row)
            self.notice = QLabel("No automatic submission. Topmost is a window-manager hint.")
            self.notice.setTextFormat(Qt.TextFormat.PlainText)
            self.notice.setWordWrap(True)
            layout.addWidget(self.notice)
            self.setStyleSheet(
                "QWidget{background:#f6f7f9;color:#202124;font-size:12px;} "
                "QPlainTextEdit,QComboBox{background:white;border:1px solid"
                " #d8dbe1;border-radius:6px;padding:7px;} "
                "QPushButton{background:white;border:1px solid "
                "#d8dbe1;border-radius:6px;padding:7px;} "
                "QPushButton:focus{border:2px solid #2563eb;} "
                "QPushButton:hover{background:#eaf1ff;}"
            )
            self.timer = QTimer(self)
            self.timer.timeout.connect(self.poll)
            self.timer.start(2000)
            self.send("status")
            self.send("drafts")

        def button(self, layout, text, callback):
            widget = QPushButton(text)
            widget.clicked.connect(callback)
            layout.addWidget(widget)
            return widget

        def terminal_help(self):
            command = [sys.executable, "-m", "flochat.cli", "safety"]
            environment = dict(os.environ)
            environment["FLOCHAT_HOME"] = str(config.resolved_data_dir)
            environment["FLOCHAT_DB"] = str(config.resolved_db_path)
            if os.name == "nt":
                subprocess.Popen(
                    command, env=environment, creationflags=subprocess.CREATE_NEW_CONSOLE
                )
            elif sys.platform == "darwin":
                subprocess.Popen(["open", "-a", "Terminal"])
                QMessageBox.information(
                    self,
                    "FloChat terminal",
                    "Terminal opened. Run flochat safety from the same "
                    "clone/environment. No Automation permission is requested.",
                )
            else:
                executable = next(
                    (
                        shutil.which(n)
                        for n in ("x-terminal-emulator", "gnome-terminal", "konsole", "xterm")
                        if shutil.which(n)
                    ),
                    None,
                )
                if not executable:
                    QMessageBox.information(
                        self,
                        "Terminal unavailable",
                        "Open your terminal manually and run flochat safety. No "
                        "terminal emulator was found.",
                    )
                    return
                subprocess.Popen(
                    [executable, "--" if "gnome-terminal" in executable else "-e", *command],
                    env=environment,
                )

        def poll(self):
            if not self.polling:
                self.send("status")

        def send(self, command, **args):
            if command == "edit" and self.editor.isReadOnly():
                self.notice.setText("Oversized editor is read-only. Use the CLI to edit full text.")
                return
            if command == "prepare" and self.editor.document().isModified():
                self.notice.setText("Save editor changes before requesting a core review.")
                return
            if command == "status":
                self.polling = True
            elif command not in ("stop", "cancel", "drafts"):
                if self.busy:
                    return
                self.busy = True
            if command not in ("status", "drafts"):
                self.generation += 1
            if command == "confirm":
                self.notice.setText("SUBMITTING · one attempt; never an automatic retry.")
            self.pool.start(Request(self.client, self.replies, command, args, self.generation))

        def complete(self, command, result, error, generation):
            if command == "status":
                self.polling = False
            elif command not in ("stop", "cancel", "drafts"):
                self.busy = False
            # Never overwrite a newer control action with an older reply. A write's
            # eventual result/error must still be surfaced, even after Stop.
            if generation != self.generation and command != "confirm":
                return
            if isinstance(result, dict):
                self.review_observed_at = max(self.review_observed_at, result.get("observed_at", 0))
            if error:
                self.status.setPlainText(
                    "State unverified after action/connection error.\n" + error
                )
                self.notice.setText(error)
                if command != "status":
                    self.poll()
                if self.review:
                    self.review.reject()
                    self.review = None
                return
            if command == "status":
                if result["observed_at"] < self.review_observed_at:
                    return
                self.mode = result["mode"]
                selected = result.get("selection") or {}
                connection = result["connection"]
                safety = result["safety"]
                self.status.setPlainText(
                    f"{result['availability']} · {safety['session']} · {self.mode}\n"
                    f"Account: {(connection.get('account') or {}).get('title', 'Unverified')} "
                    f"· {selected.get('account_channel_id', 'Not selected')}\n"
                    f"Chat: {selected.get('live_chat_id', 'Not selected')}\n"
                    f"Stream: {selected.get('title', '—')}\n"
                    f"Connection: {connection['state']} · {connection.get('reason', '')}\n"
                    f"Cooldown remaining: {safety['cooldown_remaining']:.1f}s "
                    f"(policy {safety['cooldown_seconds']}s).\n"
                    + json.dumps(safety.get("attempts", [])[:1], ensure_ascii=False)
                )
                if not self.editor.document().isModified() and not self.editor.hasFocus():
                    self.editor.setPlainText(result["editor"]["text"])
                    self.editor.setReadOnly(bool(result["editor"].get("truncated")))
                    self.editor.document().setModified(False)
                if self.review and (not safety["approval_pending"] or not result["owns_review"]):
                    self.review.reject()
                    self.review = None
            elif command == "drafts":
                self.drafts.clear()
                for draft in result:
                    self.drafts.addItem(draft["title"], draft["id"])
            elif command == "prepare":
                self.open_review(result)
            elif command == "preview":
                QMessageBox.information(
                    self,
                    "Local preview — not approval",
                    json.dumps(result, ensure_ascii=False, indent=2),
                )
            else:
                self.notice.setText(json.dumps(result, ensure_ascii=False))
                if command in ("edit", "draft"):
                    self.editor.setPlainText(result["text"])
                    self.editor.setReadOnly(bool(result.get("truncated")))
                    self.editor.document().setModified(False)
                self.poll()

        def open_review(self, view):
            self.review_observed_at = max(self.review_observed_at, view["observed_at"])
            dialog = QDialog(self)
            dialog.setWindowTitle("Approve ONE exact comment")
            dialog.setWindowModality(Qt.WindowModality.ApplicationModal)
            layout = QVBoxLayout(dialog)
            layout.addWidget(QLabel("Review required. Confirming attempts ONE YouTube submission."))
            exact = QPlainTextEdit()
            exact.setReadOnly(True)
            exact.setPlainText(
                json.dumps(view, ensure_ascii=True, indent=2) + "\nExact text:\n" + view["text"]
            )
            layout.addWidget(exact)
            phrase = QLineEdit()
            phrase.setPlaceholderText("SEND " + view["approval_id"])
            phrase.setAccessibleName("Type the displayed exact one-use confirmation phrase")
            layout.addWidget(phrase)
            row = QHBoxLayout()
            layout.addLayout(row)

            def approve():
                value = phrase.text()
                dialog.accept()
                self.review = None
                self.send("confirm", approval_id=view["approval_id"], phrase=value)

            confirmation = self.button(row, "Confirm this one attempt", approve)
            confirmation.setEnabled(False)
            phrase.textChanged.connect(
                lambda value: confirmation.setEnabled(value == "SEND " + view["approval_id"])
            )
            self.button(row, "Cancel", dialog.reject)
            dialog.rejected.connect(lambda: self.send("cancel"))
            self.review = dialog
            dialog.resize(470, 420)
            dialog.show()
            expiry = QTimer(dialog)
            expiry.setSingleShot(True)
            expiry.timeout.connect(dialog.reject)
            dialog.finished.connect(expiry.stop)
            expiry.start(max(1, int(view["expires_in_seconds"] * 1000)))

        def closeEvent(self, event):
            if self.busy:
                self.send("stop")
                self.notice.setText(
                    "Stop requested. Wait for the actual in-flight result before closing."
                )
                event.ignore()
                return
            self.timer.stop()
            with suppress(FloChatError):
                self.client.call("detach")
            super().closeEvent(event)

    app = QApplication.instance() or QApplication([])
    app.setApplicationName("FloChat")
    window = Window()
    window.show()
    return app.exec()
