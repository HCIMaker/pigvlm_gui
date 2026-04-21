"""
Read-only reference card for the DLC-labeling keyboard shortcuts.

Distinct from `dialogs/shortcuts.py`'s `ShortcutDialog`, which is the upstream
editor (all actions, editable QKeySequenceEdit fields, modal). This dialog
shows a curated DLC-relevant subset in a non-modal two-column table, so a
labeler can pop it open and keep labeling while they peek at the bindings.
"""

from qtpy import QtCore, QtWidgets

from sleap.gui.shortcuts import Shortcuts


# --- T6f USER CONTRIBUTION POINT -------------------------------------------
# Curated list of (shortcut-action-name-in-yaml, display-label) pairs to show
# in the reference dialog. Keep to ~5-10 rows so the dialog stays a quick
# glance, not a full cheat-sheet. The first element MUST match a key in
# `sleap/config/shortcuts.yaml`; the second is the label shown to the user.
#
# Edit this list to change what rows appear. Rows whose yaml binding is empty
# at open-time are silently dropped (so unbound optional actions like
# `add instance` won't show a blank key column).
DLC_SHORTCUT_ENTRIES: list[tuple[str, str]] = [
    ("add instance default", "Add Instance (Default)"),
    ("add instance copy prior", "Add Instance (Copy Prior Frame)"),
    ("frame prev", "Previous Frame"),
    ("frame next", "Next Frame"),
    ("save", "Save Project"),
    ("clear selection", "Clear Selection"),
]
# --- end contribution point ------------------------------------------------


class DLCShortcutsReferenceDialog(QtWidgets.QDialog):
    """Non-modal two-column reference of DLC-relevant keyboard shortcuts."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setWindowTitle("DLC Shortcuts")
        # Non-modal: stays on top of the main window but doesn't block it.
        self.setWindowFlags(self.windowFlags() | QtCore.Qt.Tool)
        self._build_ui()

    def _build_ui(self):
        shortcuts = Shortcuts()
        rows = []
        for action, label in DLC_SHORTCUT_ENTRIES:
            key_seq = shortcuts[action]
            key_text = key_seq.toString() if hasattr(key_seq, "toString") else str(key_seq)
            if not key_text.strip():
                continue
            rows.append((key_text, label))

        table = QtWidgets.QTableWidget(len(rows), 2, self)
        table.setHorizontalHeaderLabels(["Key", "Action"])
        table.verticalHeader().setVisible(False)
        table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        table.setSelectionMode(QtWidgets.QAbstractItemView.NoSelection)
        table.setFocusPolicy(QtCore.Qt.NoFocus)
        for row_idx, (key_text, label) in enumerate(rows):
            table.setItem(row_idx, 0, QtWidgets.QTableWidgetItem(key_text))
            table.setItem(row_idx, 1, QtWidgets.QTableWidgetItem(label))
        table.resizeColumnsToContents()
        table.horizontalHeader().setStretchLastSection(True)

        close_btn = QtWidgets.QPushButton("Close", self)
        close_btn.clicked.connect(self.close)

        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(table)
        btn_row = QtWidgets.QHBoxLayout()
        btn_row.addStretch(1)
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)
