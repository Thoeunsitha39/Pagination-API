import json
import os
import uuid
from datetime import datetime

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QMessageBox,
    QPushButton,
    QSplitter,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from api_tool.core.paths import mappings_file_path
from api_tool.core.stubs.mappings import dump_mappings, example_stubs, load_mappings
from api_tool.core.stubs.matching import url_spec
from api_tool.core.stubs.model import (
    is_enabled,
    new_paginated_stub,
    new_stub,
    pagination_of,
    script_of,
    stub_summary,
    stub_tags,
)
from api_tool.core.stubs.webhooks import webhooks_of
from api_tool.ui.icons import icon
from api_tool.ui.theme import TEXT_MUTED
from api_tool.ui.widgets.common import WidthWatcher, _card, _icon_button, STUB_INFO_ROLE
from api_tool.ui.widgets.stub_item_delegate import StubItemDelegate


class MocksPageMixin:
    """The Mocks page: stub list, filter, create/clone/delete, import/export, persistence.

    Mixed into ApiTool; uses its widgets and state through self."""

    def _build_mocks_tab(self):
        central = QWidget()
        layout = QVBoxLayout(central)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(0)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)
        splitter.setHandleWidth(12)
        layout.addWidget(splitter, 1)

        # Left: stub list panel
        list_card, list_layout = _card(margins=(0, 0, 0, 0), spacing=0)
        list_header = QHBoxLayout()
        list_header.setContentsMargins(14, 10, 8, 6)
        list_header.setSpacing(2)
        title = QLabel("Stubs")
        title.setObjectName("panelTitle")
        list_header.addWidget(title)
        list_header.addSpacing(6)
        self.stub_count_label = QLabel("")
        self.stub_count_label.setObjectName("countBadge")
        list_header.addWidget(self.stub_count_label)
        list_header.addStretch()
        list_header.addWidget(_icon_button("copy", "Clone the selected stub", self._duplicate_stub))
        list_header.addWidget(_icon_button("trash", "Delete the selected stub", self._delete_stub))
        list_header.addWidget(_icon_button("import", "Import WireMock mappings…", self._import_stubs))
        list_header.addWidget(_icon_button("export", "Export all stubs as WireMock mappings…", self._export_stubs))
        self.examples_btn = _icon_button("examples", "Add ready-made example stubs")
        self.examples_btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        examples_menu = QMenu(self.examples_btn)
        examples_menu.addAction("Echo request values (templates)", lambda: self._add_examples([0]))
        examples_menu.addAction("Require X-Token header (script)", lambda: self._add_examples([1]))
        examples_menu.addAction("Create order + webhook (with receiver)", lambda: self._add_examples([2, 3]))
        examples_menu.addSeparator()
        examples_menu.addAction("Add all examples", lambda: self._add_examples([0, 1, 2, 3]))
        self.examples_btn.setMenu(examples_menu)
        list_header.addWidget(self.examples_btn)
        list_layout.addLayout(list_header)

        search_row = QHBoxLayout()
        search_row.setContentsMargins(12, 2, 12, 8)
        self.stub_search = QLineEdit()
        self.stub_search.setObjectName("searchField")
        self.stub_search.setPlaceholderText("Filter stubs  (Ctrl+F)")
        self.stub_search.setToolTip("Filter by name, method, URL or tag (paged, script, webhook)")
        self.stub_search.setClearButtonEnabled(True)
        self.stub_search.addAction(icon("search", TEXT_MUTED), QLineEdit.ActionPosition.LeadingPosition)
        self.stub_search.textChanged.connect(self._apply_stub_filter)
        search_row.addWidget(self.stub_search)
        list_layout.addLayout(search_row)
        list_layout.addWidget(self._divider())

        self.stub_list = QListWidget()
        self.stub_list.setObjectName("stubList")
        self.stub_list.setItemDelegate(StubItemDelegate(self.stub_list))
        self.stub_list.setMouseTracking(True)
        self.stub_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.stub_list.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.stub_list.currentItemChanged.connect(self._on_stub_selection_changed)
        list_layout.addWidget(self.stub_list, 1)
        self.stub_empty_label = QLabel("No stubs match the filter.")
        self.stub_empty_label.setObjectName("statusLabel")
        self.stub_empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.stub_empty_label.setVisible(False)
        list_layout.addWidget(self.stub_empty_label)

        new_row = QHBoxLayout()
        new_row.setContentsMargins(12, 8, 12, 12)
        new_btn = QPushButton("New stub")
        new_btn.setIcon(icon("plus", "#ffffff"))
        new_btn.setToolTip("Create a new stub")
        new_btn.clicked.connect(self._new_stub)
        new_row.addWidget(new_btn)
        list_layout.addWidget(self._divider())
        list_layout.addLayout(new_row)

        list_card.setMinimumWidth(240)
        splitter.addWidget(list_card)
        self.stub_list_card = list_card

        # Right: editor
        self.stub_editor = self._build_stub_editor()
        splitter.addWidget(self.stub_editor)

        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([300, 1000])
        # Narrow window: hide the list to give the editor room (the toolbar button brings it back).
        self._mocks_narrow = None
        WidthWatcher(central, self._on_mocks_width)

        return central

    _NARROW_MOCKS_WIDTH = 1000

    def _on_mocks_width(self, width):
        narrow = width < self._NARROW_MOCKS_WIDTH
        if narrow != self._mocks_narrow:
            self._mocks_narrow = narrow
            self._set_stub_list_visible(not narrow)

    def _set_stub_list_visible(self, visible):
        self.stub_list_card.setVisible(visible)
        self.stub_list_toggle.setChecked(visible)
        self.stub_list_toggle.setToolTip("Hide the stub list" if visible else "Show the stub list")

    def _toggle_stub_list(self):
        self.tabs.setCurrentIndex(0)
        self._set_stub_list_visible(not self.stub_list_card.isVisible())

    def _focus_stub_search(self):
        self.tabs.setCurrentIndex(0)
        self._set_stub_list_visible(True)
        self.stub_search.setFocus()
        self.stub_search.selectAll()

    def _apply_stub_filter(self, *_args):
        needle = self.stub_search.text().strip().lower()
        visible = 0
        for row in range(self.stub_list.count()):
            item = self.stub_list.item(row)
            info = item.data(STUB_INFO_ROLE) or {}
            haystack = " ".join([info.get("method", ""), info.get("url", ""), info.get("name", ""),
                                 " ".join(info.get("tags", []))]).lower()
            hidden = bool(needle) and not all(word in haystack for word in needle.split())
            item.setHidden(hidden)
            visible += not hidden
        self.stub_empty_label.setVisible(self.stub_list.count() > 0 and visible == 0)

    def _decorate_stub_item(self, item, stub):
        request = stub.get("request", {})
        key, url = url_spec(request)
        if key is None:
            url = "(any URL)"
        elif key.endswith("Pattern"):
            url = f"~ {url}"
        item.setText(self._stub_list_text(stub))
        item.setData(STUB_INFO_ROLE, {
            "method": (request.get("method") or "ANY").upper(),
            "url": url,
            "name": stub.get("name", ""),
            "tags": [t for t in stub_tags(stub) if t != "disabled"],
            "enabled": is_enabled(stub),
        })
        item.setToolTip(f"{stub_summary(stub)}\n{stub.get('name', '')}")

    def _stub_by_id(self, stub_id):
        return next((s for s in self.stubs if s["id"] == stub_id), None)

    def _stub_list_text(self, stub):
        request = stub.get("request", {})
        key, url = url_spec(request)
        if key is None:
            url = "(any URL)"
        elif key.endswith("Pattern"):
            url = f"~ {url}"
        tags = []
        if pagination_of(stub) is not None:
            tags.append("paged")
        if script_of(stub):
            tags.append("script")
        hooks = len(webhooks_of(stub))
        if hooks:
            tags.append(f"{hooks} webhook{'s' if hooks > 1 else ''}")
        suffix = "".join(f"  [{tag}]" for tag in tags)
        return f"{request.get('method', 'ANY'):<7} {url}\n{stub.get('name', '')}{suffix}"

    def _refresh_stub_list(self, select_id=None):
        self.stub_list.blockSignals(True)
        self.stub_list.clear()
        selected_row = -1
        for row, stub in enumerate(self.stubs):
            item = QListWidgetItem()
            item.setData(Qt.ItemDataRole.UserRole, stub["id"])
            self._decorate_stub_item(item, stub)
            self.stub_list.addItem(item)
            if stub["id"] == select_id:
                selected_row = row
        self.stub_list.blockSignals(False)
        active = sum(1 for s in self.stubs if is_enabled(s))
        self.stub_count_label.setText(f"{active}/{len(self.stubs)}")
        self.stub_count_label.setToolTip(f"{active} active of {len(self.stubs)} stubs")
        self._apply_stub_filter()
        if selected_row >= 0:
            self.stub_list.setCurrentRow(selected_row)
        elif select_id is None and self.stubs:
            self.stub_list.setCurrentRow(0)
        else:
            self._load_stub_into_editor(None)
        self._refresh_server_status()

    def _on_stub_selection_changed(self, current, previous):
        if self.editor_dirty and previous is not None:
            answer = QMessageBox.question(
                self,
                "Unsaved changes",
                "Save changes to the current stub before switching?",
                QMessageBox.StandardButton.Save
                | QMessageBox.StandardButton.Discard
                | QMessageBox.StandardButton.Cancel,
            )
            if answer == QMessageBox.StandardButton.Cancel:
                self.stub_list.blockSignals(True)
                self.stub_list.setCurrentItem(previous)
                self.stub_list.blockSignals(False)
                return
            if answer == QMessageBox.StandardButton.Save and not self._save_current_stub():
                self.stub_list.blockSignals(True)
                self.stub_list.setCurrentItem(previous)
                self.stub_list.blockSignals(False)
                return
        stub_id = current.data(Qt.ItemDataRole.UserRole) if current else None
        self._load_stub_into_editor(self._stub_by_id(stub_id))

    def _confirm_leave_editor(self):
        """Resolve unsaved edits before an action that changes the selection. False = abort."""
        if not self.editor_dirty:
            return True
        answer = QMessageBox.question(
            self,
            "Unsaved changes",
            "Save changes to the current stub first?",
            QMessageBox.StandardButton.Save
            | QMessageBox.StandardButton.Discard
            | QMessageBox.StandardButton.Cancel,
        )
        if answer == QMessageBox.StandardButton.Cancel:
            return False
        if answer == QMessageBox.StandardButton.Save:
            return self._save_current_stub()
        self._set_clean()
        return True

    def _new_stub(self):
        if not self._confirm_leave_editor():
            return
        stub = new_stub(name=f"Stub {len(self.stubs) + 1}")
        self.stubs = self.stubs + [stub]
        self._persist_stubs()
        self._refresh_stub_list(select_id=stub["id"])
        self.stub_name_edit.setFocus()
        self.stub_name_edit.selectAll()

    def show_stub(self, stub_id):
        """Bring the main window forward with this stub selected (used by tool windows)."""
        self.tabs.setCurrentIndex(0)
        self.stub_search.clear()
        for row in range(self.stub_list.count()):
            if self.stub_list.item(row).data(Qt.ItemDataRole.UserRole) == stub_id:
                self.stub_list.setCurrentRow(row)
                break
        self.show()
        self.raise_()
        self.activateWindow()

    def _add_examples(self, indexes):
        if not self._confirm_leave_editor():
            return
        examples = example_stubs(f"http://{self.server_host}:{self.server_port}")
        added = [examples[i] for i in indexes]
        self.stubs = self.stubs + added
        self._persist_stubs()
        self._refresh_stub_list(select_id=added[0]["id"])
        base = f"http://{self.server_host}:{self.server_port}"
        tries = {
            0: f'curl -X POST "{base}/api/echo/7?user=sitha" -H "X-Token: abc" '
               "-d '{\"customer\": {\"name\": \"Sitha\"}, \"items\": [{\"sku\": \"A-1\"}]}'",
            1: f'curl "{base}/api/secure?user=sitha" -H "X-Token: admin-token"',
            2: f"curl -X POST {base}/api/orders -d '{{\"customer\": \"Sitha\"}}'   "
               "(then watch the Request Log: the webhook arrives 3 s later)",
        }
        QMessageBox.information(
            self,
            "Example added",
            f"Added {len(added)} example stub(s). Try it with Test… or:\n\n"
            + "\n\n".join(tries[i] for i in indexes if i in tries),
        )

    def _duplicate_stub(self):
        if self.current_stub_id is None or not self._confirm_leave_editor():
            return
        original = self._stub_by_id(self.current_stub_id)
        copy_stub = json.loads(json.dumps(original))
        copy_stub["id"] = str(uuid.uuid4())
        copy_stub["name"] = f"{original.get('name', 'Stub')} (copy)"
        position = self.stubs.index(original) + 1
        self.stubs = self.stubs[:position] + [copy_stub] + self.stubs[position:]
        self._persist_stubs()
        self._refresh_stub_list(select_id=copy_stub["id"])

    def _delete_stub(self):
        stub = self._stub_by_id(self.current_stub_id)
        if stub is None:
            return
        answer = QMessageBox.question(
            self, "Delete stub", f"Delete “{stub.get('name', '')}”? This can't be undone."
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        position = self.stubs.index(stub)
        self.stubs = [s for s in self.stubs if s["id"] != stub["id"]]
        window = self._stub_ai_windows.pop(stub["id"], None)
        if window is not None:
            window.allow_close = True
            window.close()
        self._set_clean()
        self._persist_stubs()
        next_id = self.stubs[min(position, len(self.stubs) - 1)]["id"] if self.stubs else None
        self._refresh_stub_list(select_id=next_id)

    def _import_stubs(self):
        if not self._confirm_leave_editor():
            return
        path, _ = QFileDialog.getOpenFileName(
            self, "Import WireMock mappings", "", "JSON files (*.json)"
        )
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as fh:
                imported = load_mappings(fh.read())
        except (OSError, ValueError) as exc:
            QMessageBox.critical(self, "Import failed", str(exc))
            return
        scripted = [s.get("name", "") for s in imported if script_of(s)]
        if scripted:
            box = QMessageBox(self)
            box.setIcon(QMessageBox.Icon.Warning)
            box.setWindowTitle("Imported stubs contain scripts")
            box.setText(
                f"{len(scripted)} imported stub(s) contain Python scripts, which run on this PC "
                "with full access whenever the stub is called.\n\n"
                "Only keep scripts from sources you trust."
            )
            box.setDetailedText("\n".join(scripted))
            keep_btn = box.addButton("Import with scripts", QMessageBox.ButtonRole.AcceptRole)
            strip_btn = box.addButton("Import without scripts", QMessageBox.ButtonRole.DestructiveRole)
            box.addButton(QMessageBox.StandardButton.Cancel)
            box.setDefaultButton(strip_btn)
            box.exec()
            if box.clickedButton() == strip_btn:
                for stub in imported:
                    stub.get("metadata", {}).pop("script", None)
                    if stub.get("metadata") == {}:
                        del stub["metadata"]
            elif box.clickedButton() != keep_btn:
                return
        existing_ids = {s["id"] for s in self.stubs}
        for stub in imported:
            if stub["id"] in existing_ids:
                stub["id"] = str(uuid.uuid4())
            existing_ids.add(stub["id"])
        self.stubs = self.stubs + imported
        self._persist_stubs()
        self._refresh_stub_list(select_id=imported[0]["id"] if imported else self.current_stub_id)
        self.statusBar().showMessage(f"Imported {len(imported)} stub(s) from {path}", 6000)

    def _export_stubs(self):
        if not self._confirm_leave_editor():
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Export WireMock mappings", "mappings.json", "JSON files (*.json)"
        )
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(dump_mappings(self.stubs))
        except OSError as exc:
            QMessageBox.critical(self, "Export failed", str(exc))
            return
        self.statusBar().showMessage(f"Exported {len(self.stubs)} stub(s) to {path}", 6000)

    def _load_stubs_from_disk(self):
        path = mappings_file_path()
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as fh:
                    self.stubs = load_mappings(fh.read())
            except (OSError, ValueError) as exc:
                backup = f"{path}.broken-{datetime.now():%Y%m%d-%H%M%S}"
                try:
                    os.replace(path, backup)
                    kept = f"The file was moved to:\n{backup}"
                except OSError:
                    kept = "The file was left in place."
                QMessageBox.warning(
                    self,
                    "Couldn't load saved stubs",
                    f"{path}\n\n{exc}\n\n{kept}\n\nStarting with no stubs.",
                )
                self.stubs = []
        else:
            self.stubs = [
                new_stub(name="Hello world", method="GET", url_path="/api/hello"),
                new_paginated_stub(),
            ]
            self._persist_stubs()
        self._refresh_stub_list()

    def _persist_stubs(self):
        path = mappings_file_path()
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            tmp_path = f"{path}.tmp"
            with open(tmp_path, "w", encoding="utf-8") as fh:
                fh.write(dump_mappings(self.stubs))
            os.replace(tmp_path, path)
        except OSError as exc:
            self.statusBar().showMessage(f"Failed to save stubs to {path}: {exc}", 10000)
