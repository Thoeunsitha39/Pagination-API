import json
import uuid

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QMessageBox

from api_tool.ui.dialogs.help.help_dialog import HelpDialog
from api_tool.ui.dialogs.stub_preview_dialog import REPLACE, StubPreviewDialog
from api_tool.ui.icons import app_icon
from api_tool.ui.windows.stub_ai_window import StubAIWindow


class AIFeaturesMixin:
    """AI integration in the main window: context, Ask AI windows, adding AI stubs, Help.

    Mixed into ApiTool; uses its widgets and state through self."""

    def _show_help(self, tab="Templates"):
        if self._help_window is None:
            self._help_window = HelpDialog(None, start_tab=tab)
        else:
            self._help_window.show_tab(tab)
        self._open_window(self._help_window)

    def _ai_context(self):
        """What the AI may see: never the Basic Auth password or any API key."""
        server = (
            f"http://{self.server_host}:{self.server_port} "
            f"({'running' if self.local_server else 'NOT running'}; "
            f"Security: {self.security.describe()})"
        )
        if self._public_summary():
            server += f"; reachable at {self._public_summary()}"
        current = self._stub_by_id(self.current_stub_id)
        selected = current.get("name") if current else None
        if selected and self.editor_dirty:
            selected += " (has unsaved edits in the editor)"
        log_entries = list(self.log_entries)
        return server, self.stubs, selected, log_entries

    def _ask_ai_about_stub(self):
        """Open (or bring back) the movable "Ask AI" chat window for the selected stub."""
        stub = self._stub_by_id(self.current_stub_id)
        if stub is None:
            return
        if self.editor_dirty:
            box = QMessageBox(self)
            box.setIcon(QMessageBox.Icon.Question)
            box.setWindowTitle("Unsaved changes")
            box.setText("The AI only sees the saved version of this stub. Save your changes first?")
            save_btn = box.addButton("Save and ask", QMessageBox.ButtonRole.AcceptRole)
            saved_btn = box.addButton("Ask about the saved version", QMessageBox.ButtonRole.ActionRole)
            box.addButton(QMessageBox.StandardButton.Cancel)
            box.exec()
            if box.clickedButton() == save_btn:
                if not self._save_current_stub():
                    return
            elif box.clickedButton() != saved_btn:
                return
        window = self._stub_ai_windows.get(stub["id"])
        if window is None:
            window = StubAIWindow(self, stub["id"])
            self._stub_ai_windows[stub["id"]] = window
        window.refresh()
        self._open_window(window)
        window.panel.input_edit.setFocus()

    def _add_stubs_from_ai(self, stubs):
        """Show the preview; add or replace the stubs the user keeps. True if anything changed."""
        if not self._confirm_leave_editor():
            return False
        dialog = StubPreviewDialog(stubs, self.stubs, None)  # parentless: GNOME won't glue it down
        dialog.setWindowIcon(app_icon())
        dialog.setWindowModality(Qt.WindowModality.ApplicationModal)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return False
        choices = dialog.choices()
        if not choices:
            return False
        updated = list(self.stubs)
        existing_ids = {s["id"] for s in updated}
        added = replaced = 0
        first_id = None
        for stub, action, target_id in choices:
            stub = json.loads(json.dumps(stub))
            if action == REPLACE and target_id in existing_ids:
                stub["id"] = target_id  # keeps its place in the list
                updated = [stub if s["id"] == target_id else s for s in updated]
                replaced += 1
            else:
                if stub["id"] in existing_ids:
                    stub["id"] = str(uuid.uuid4())
                existing_ids.add(stub["id"])
                updated.append(stub)
                added += 1
            first_id = first_id or stub["id"]
        self.stubs = updated
        self._persist_stubs()
        self._refresh_stub_list(select_id=first_id)
        for window in self._stub_ai_windows.values():
            window.refresh()
        self.tabs.setCurrentIndex(0)
        parts = [f"added {added}"] if added else []
        if replaced:
            parts.append(f"replaced {replaced}")
        self.statusBar().showMessage(f"AI stubs: {' and '.join(parts)} — review, then Test…", 8000)
        return True
