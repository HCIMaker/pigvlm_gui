"""
Data table widgets and view models used in GUI app.

Typically you'll need to subclass :py:class:`GenericTableModel` for your data
(unless your data is already a list of dictionaries with keys matching
the columns of the table you want), but you can use :py:class:`GenericTableView`
as is. For example::

    videos_table = GenericTableView(
        state=self.state,
        row_name="video",
        is_activatable=True,
        model=VideosTableModel(items=self.labels.videos, context=self.commands),
        )

"""

import os
from operator import itemgetter
from pathlib import Path
from typing import Any, Callable, List, Optional

import numpy as np
from qtpy import QtCore, QtGui, QtWidgets

from sleap.gui.commands import CommandContext
from sleap.gui.state import GuiState
from sleap_io.model.skeleton import Skeleton
from sleap_io import Video
from sleap_io import LabeledFrame
from sleap_io.io.video_reading import VideoBackend
from sleap.sleap_io_adaptors.skeleton_utils import get_symmetry_node
from sleap.sleap_io_adaptors.instance_utils import get_nodes_from_instance
from sleap.sleap_io_adaptors.lf_labels_utils import get_instances_to_show


class GenericTableModel(QtCore.QAbstractTableModel):
    """
    Generic Qt table model to show a list of properties for some items.

    Typically this will be used as base class. Subclasses can implement methods:
        object_to_items: allows conversion from a single object to a list of
            items which correspond to rows of table. for example, a table
            which shows skeleton nodes could implement this method and return
            the list of nodes for skeleton.
        item_to_data: if each item isn't already a dictionary with keys for
            columns of table (i.e., `properties` attribute) and values to show
            in table, then use this method to convert each item to such a dict.

    Note that if you need to convert a single object to a list of dictionaries,
    you can implement both steps in `object_to_items` (and use the default
    implementation of `item_to_data` which doesn't do any conversion), or you
    can implement this in two steps using the two methods. It doesn't make
    much difference which you do.

    For editable table, you must implement `can_set` and `set_item` methods.

    Usually it's simplest to override `properties` in the subclass, rather
    than passing as an init arg.

    Args:
        properties: The list of property names (table columns).
        items: The list of items with said properties (rows).
        context: A command context (required for editable items).
    """

    properties = None
    show_row_numbers: bool = True

    def __init__(
        self,
        items: Optional[list] = None,
        properties: Optional[List[str]] = None,
        context: Optional[CommandContext] = None,
    ):
        super(GenericTableModel, self).__init__()
        self.properties = properties or self.properties or []
        self.context = context
        self.items = items

    def object_to_items(self, item_list):
        """Virtual method, convert object to list of items to show in rows."""
        return item_list

    @property
    def items(self):
        """Gets or sets list of items to show in table."""
        return self._data

    @items.setter
    def items(self, obj):
        if not obj:
            self.beginResetModel()
            self._data = []
            self.endResetModel()
            return

        self.obj = obj
        item_list = self.object_to_items(obj)

        self.beginResetModel()
        if hasattr(self, "item_to_data"):
            self._data = []
            for item in item_list:
                item_data = self.item_to_data(obj, item)
                item_data["_original_item"] = item
                self._data.append(item_data)
        else:
            self._data = item_list
        self.endResetModel()

    @property
    def original_items(self):
        """
        Gets the original items (rather than the dictionary we build from it).
        """
        try:
            return [datum["_original_item"] for datum in self._data]
        except Exception:
            return self._data

    def get_item_color(self, item: Any, key: str):
        """Virtual method, returns color for given item."""
        return None

    def data(self, index: QtCore.QModelIndex, role=QtCore.Qt.DisplayRole):
        """Overrides Qt method, returns data to show in table."""
        if not index.isValid():
            return None

        idx = index.row()
        key = self.properties[index.column()]

        if idx >= self.rowCount():
            return None

        item = self.items[idx]
        if role == QtCore.Qt.DisplayRole or role == QtCore.Qt.EditRole:
            if isinstance(item, dict) and key in item:
                return item[key]

            if hasattr(item, key):
                return getattr(item, key)

        elif role == QtCore.Qt.ForegroundRole:
            return self.get_item_color(self.original_items[idx], key)

        elif role == QtCore.Qt.ToolTipRole:
            if isinstance(item, dict) and key in item:
                return item[key]

            if hasattr(item, key):
                return getattr(item, key)

        return None

    def setData(self, index: QtCore.QModelIndex, value: str, role=QtCore.Qt.EditRole):
        """Overrides Qt method, dispatch for settable properties."""
        if role == QtCore.Qt.EditRole:
            item, key = self.get_from_idx(index)

            # If nothing changed of the item, return true. (Issue #1013)
            if isinstance(item, dict):
                item_value = item.get(key, None)
            elif hasattr(item, key):
                item_value = getattr(item, key)
            else:
                item_value = None

            if (item_value is not None) and (item_value == value):
                return True

            # Otherwise set the item
            if self.can_set(item, key):
                self.set_item(item, key, value)
                self.dataChanged.emit(index, index)
                return True

        return False

    def rowCount(self, parent=None):
        """Overrides Qt method, returns number of rows (items)."""
        return len(self._data)

    def columnCount(self, parent=None):
        """Overrides Qt method, returns number of columns (attributes)."""
        return len(self.properties)

    def headerData(
        self, idx: int, orientation: QtCore.Qt.Orientation, role=QtCore.Qt.DisplayRole
    ):
        """Overrides Qt method, returns column (attribute) names."""
        if role == QtCore.Qt.DisplayRole:
            if orientation == QtCore.Qt.Horizontal:
                col_str = str(self.properties[idx])
                # use title case if key is lowercase
                if col_str == col_str.lower():
                    return col_str.title()
                # otherwise leave case as is
                return col_str
            elif orientation == QtCore.Qt.Vertical:
                # Add 1 to the row index so that we index from 1 instead of 0
                if self.show_row_numbers:
                    return str(idx + 1)
                return None

        return None

    def sort(
        self,
        column_idx: int,
        order: QtCore.Qt.SortOrder = QtCore.Qt.SortOrder.AscendingOrder,
    ):
        """
        Sorts table by given column and order.

        Correctly sorts numeric string (i.e., "123.45") numerically rather
        than alphabetically. Has logic for correctly sorting video frames by
        video then frame index.
        """
        prop = self.properties[column_idx]
        reverse = order == QtCore.Qt.SortOrder.DescendingOrder

        sort_function = itemgetter(prop)
        if prop in ("video", "frame"):
            if "video" in self.properties and "frame" in self.properties:
                sort_function = itemgetter("video", "frame")

        def string_safe_sort(x):
            sort_val = sort_function(x)
            try:
                return float(sort_val)
            except ValueError:
                return -np.inf
            except TypeError:
                return sort_val

        self.beginResetModel()
        self._data.sort(key=string_safe_sort, reverse=reverse)
        self.endResetModel()

    def get_from_idx(self, index: QtCore.QModelIndex):
        """Gets item from QModelIndex."""
        if not index.isValid():
            return None, None
        item = self.original_items[index.row()]
        key = self.properties[index.column()]
        return item, key

    def can_set(self, item, key):
        """Virtual method, returns whether table cell is editable."""
        return False

    def set_item(self, item, key, value):
        """Virtual method, used to set value for item in table cell."""
        pass

    def flags(self, index: QtCore.QModelIndex):
        """Overrides Qt method, returns whether item is selectable etc."""
        flags = QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsSelectable

        item, key = self.get_from_idx(index)
        if self.can_set(item, key):
            flags |= QtCore.Qt.ItemIsEditable
        return flags


class GenericTableView(QtWidgets.QTableView):
    """
    Qt table view for use with `GenericTableModel` (and subclasses).

    Uses the :py:class:`GuiState` object to keep track of which row/item is
    selected. If the `row_name` attribute is "foo", then a "foo_selected"
    state will be item corresponding to the currently selected row in table
    (and the table will select the row if this state is updated by something
    else). When `is_activatable` is True, then a "foo" state will also be
    set to the item when a row is activated--typically by being double-clicked.
    This state can then be used to trigger something else outside the table.

    Note that by default "selected_" is used for the state key, e.g.,
    "selected_foo", but you can set the `name_prefix` attribute/init arg if
    for some reason you need this to be different. For instance, the table
    of instances in the GUI sets this to "" so that the row for an instance
    is automatically selected when `state["instance"]` is set outside the table.

    "ellipsis_left" can be used to make the TableView truncate cell content on
    the left instead of the right side. By default, the argument is set to
    False, i.e. truncation on the right side, which is also the default for
    QTableView.
    """

    row_name: Optional[str] = None
    name_prefix: str = "selected_"
    is_activatable: bool = False
    is_sortable: bool = False

    def __init__(
        self,
        model: QtCore.QAbstractTableModel,
        state: GuiState = None,
        row_name: Optional[str] = None,
        name_prefix: Optional[str] = None,
        is_sortable: bool = False,
        is_activatable: bool = False,
        ellipsis_left: bool = False,
        multiple_selection: bool = False,
    ):
        super(GenericTableView, self).__init__()

        self.state = state or GuiState()
        self.row_name = row_name or self.row_name
        self.name_prefix = name_prefix if name_prefix is not None else self.name_prefix
        self.is_sortable = is_sortable or self.is_sortable
        self.is_activatable = is_activatable or self.is_activatable
        self.multiple_selection = multiple_selection

        self.setModel(model)

        if ellipsis_left:
            self.setTextElideMode(QtCore.Qt.ElideLeft)
            self.setWordWrap(False)
        self.horizontalHeader().setStretchLastSection(True)
        self.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        if self.multiple_selection:
            self.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        else:
            self.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.setSortingEnabled(self.is_sortable)

        self.doubleClicked.connect(self.activateSelected)
        if self.row_name:
            self.state.connect(self.name_prefix + self.row_name, self.selectRowItem)

    def selectionChanged(self, new, old):
        """Custom event handler."""
        super(GenericTableView, self).selectionChanged(new, old)

        if self.row_name:
            item = self.getSelectedRowItem()
            self.state[self.name_prefix + self.row_name] = item

    def activateSelected(self, *args):
        """Activate item currently selected in table.

        "Activate" means that the relevant :py:class:`GuiState` state variable
        is set to the currently selected item.
        """
        if self.is_activatable:
            self.state[self.row_name] = self.getSelectedRowItem()

    def selectRowItem(self, item: Any):
        """Select row corresponding to item.

        If the table model converts items to dictionaries (using `item_to_data`
        method), then `item` argument should be the original item, not the
        converted dict.
        """
        if not item:
            return

        idx = self.model().original_items.index(item)
        table_row_idx = self.model().createIndex(idx, 0)
        self.setCurrentIndex(table_row_idx)

        if self.row_name:
            self.state[self.name_prefix + self.row_name] = item

    def selectRow(self, idx: int):
        """Select row corresponding to index."""
        self.selectRowItem(self.model().original_items[idx])

    def getSelectedRowItem(self) -> Any:
        """Return item corresponding to currently selected row.

        Note that if the table model converts items to dictionaries (using
        `item_to_data` method), then returned item will be the original item,
        not the converted dict.
        """
        idx = self.currentIndex()

        if self.multiple_selection:
            idx_temp = set([x.row() for x in self.selectedIndexes()])
            self.state[f"selected_batch_{self.row_name}"] = idx_temp

        if not idx.isValid():
            return None
        return self.model().original_items[idx.row()]


class VideosTableModel(GenericTableModel):
    properties = (
        "name",
        "filepath",
        "frames",
        "height",
        "width",
        "channels",
    )

    def item_to_data(self, obj, item: "VideoBackend"):
        data = {}
        if isinstance(item, Video):
            item = item.backend

        for property in self.properties:
            if property == "name":
                data[property] = (
                    Path(item.filename).name
                    if isinstance(item.filename, str)
                    else item.filename[0]
                )
            elif property == "filepath":
                data[property] = (
                    str(Path(item.filename).parent)
                    if isinstance(item.filename, str)
                    else item.filename[0]
                )
            elif property == "height":
                data[property] = item.img_shape[0]
            elif property == "width":
                data[property] = item.img_shape[1]
            elif property == "channels":
                data[property] = item.img_shape[2]
            else:
                data[property] = getattr(item, property)
        return data


class SkeletonNodesTableModel(GenericTableModel):
    properties = ("name", "symmetry")

    def object_to_items(self, skeleton: Skeleton):
        """Converts given skeleton to list of nodes to show in table."""
        items = skeleton.nodes
        self.skeleton = skeleton
        return items

    def item_to_data(self, obj, item):
        return dict(name=item.name, symmetry=get_symmetry_node(obj, item.name))

    def can_set(self, item, key):
        return True

    def set_item(self, item, key, value):
        if key == "name" and value:
            self.context.setNodeName(skeleton=self.obj, node=item, name=value)
        elif key == "symmetry":
            self.context.setNodeSymmetry(skeleton=self.obj, node=item, symmetry=value)


class SkeletonEdgesTableModel(GenericTableModel):
    """Table model for skeleton edges."""

    properties = ("source", "destination")

    def object_to_items(self, skeleton: Skeleton):
        items = []
        self.skeleton = skeleton
        if hasattr(skeleton, "edges"):
            items = [
                dict(source=edge[0].name, destination=edge[1].name)
                for edge in skeleton.edges
            ]
        return items


class LabeledFrameTableModel(GenericTableModel):
    """Table model for listing instances in labeled frame.

    Allows editing track names.

    Args:
        labeled_frame: `LabeledFrame` to show
        labels: `Labels` datasource
    """

    properties = ("points", "track", "score", "skeleton")

    def object_to_items(self, labeled_frame: LabeledFrame):
        if not labeled_frame:
            return []
        return get_instances_to_show(labeled_frame)

    def item_to_data(self, obj, item):
        instance = item

        points = (
            f"{len(get_nodes_from_instance(instance))}/{len(instance.skeleton.nodes)}"
        )
        track_name = instance.track.name if instance.track else ""
        score = ""
        if hasattr(instance, "score"):
            score = str(round(instance.score, 2))

        return dict(
            points=points,
            track=track_name,
            score=score,
            skeleton=instance.skeleton.name,
        )

    def get_item_color(self, item: Any, key: str):
        if key == "track" and item.track is not None:
            track = item.track
            return QtGui.QColor(*self.context.app.color_manager.get_track_color(track))
        return None

    def can_set(self, item, key):
        if key == "track" and item.track is not None:
            return True

    def set_item(self, item, key, value):
        if key == "track":
            self.context.setTrackName(item.track, value)


class SuggestionsTableModel(GenericTableModel):
    properties = ("video", "frame", "group", "labeled", "mean score")

    def item_to_data(self, obj, item):
        labels = self.context.labels
        item_dict = dict()

        item_dict["SuggestionFrame"] = item

        video_idx = labels.videos.index(item.video) + 1
        fn = item.video.filename
        if isinstance(fn, list):
            # ImageVideo (DLC folder-of-frames): use the parent folder name
            # since the "video" is conceptually the folder, not a single frame.
            video_name = os.path.basename(os.path.dirname(fn[0])) if fn else "(empty)"
        else:
            video_name = os.path.basename(fn)
        video_string = f"{video_idx}: {video_name}"

        item_dict["group"] = "0"
        item_dict["group_int"] = 0
        item_dict["video"] = video_string
        item_dict["frame"] = int(item.frame_idx) + 1  # start at frame 1 rather than 0

        # show how many labeled instances are in this frame
        lf = labels.find(item.video, item.frame_idx)
        lf = lf[0] if lf else None
        val = 0 if lf is None else len(lf.user_instances)
        val = str(val) if val > 0 else ""
        item_dict["labeled"] = val

        # calculate score for frame
        scores = [
            inst.score
            for lf in labels.find(item.video, item.frame_idx)
            for inst in lf
            if hasattr(inst, "score")
        ]
        val = float(sum(scores) / len(scores)) if scores else ""
        item_dict["mean score"] = val

        return item_dict

    def sort(self, column_idx: int, order: QtCore.Qt.SortOrder):
        """Sorts table by given column and order."""
        prop = self.properties[column_idx]
        reverse = order == QtCore.Qt.SortOrder.DescendingOrder

        if prop != "group":
            super(SuggestionsTableModel, self).sort(column_idx, order)
        else:
            if not reverse:
                # Use group_int (int) instead of group (str).
                self.beginResetModel()
                self._data.sort(key=itemgetter("group_int"))
                self.endResetModel()

            else:
                # Instead of a reverse sort order on groups, we'll interleave the
                # items so that we get the earliest item from each group, then the
                # second item from each group, and so on.

                # Make a decorated list of items with positions in group (plus the
                # secondary sort keys: group, video, and frame)
                self._data.sort(key=itemgetter("group_int"))
                decorated_data = []
                last_group = object()
                for item in self._data:
                    if last_group != item["group_int"]:
                        group_i = 0
                    decorated_data.append(
                        (group_i, item["group_int"], item["video"], item["frame"], item)
                    )
                    last_group = item["group_int"]
                    group_i += 1

                # Sort decorated list
                decorated_data.sort()

                # Undecorate the list and update table
                self.beginResetModel()
                self._data = [item for (*_, item) in decorated_data]
                self.endResetModel()

        # Update order in project (so order can be saved and affects what we
        # consider previous/next suggestion for navigation).
        resorted_suggestions = [item["SuggestionFrame"] for item in self._data]
        self.context.labels.suggestions = resorted_suggestions


class SkeletonNodeModel(QtCore.QStringListModel):
    """
    String list model for source/destination nodes of edges.

    Args:
        skeleton: The skeleton for which to list nodes.
        src_node: If given, then we assume that this model is being used for
            edge destination node. Otherwise, we assume that this model is
            being used for an edge source node.
            If given, then this should be function that will return the
            selected edge source node.
    """

    def __init__(self, skeleton: Skeleton, src_node: Callable = None):
        super(SkeletonNodeModel, self).__init__()
        self._src_node = src_node
        self.skeleton = skeleton

    @property
    def skeleton(self):
        """Gets or sets current skeleton."""
        return self._skeleton

    @skeleton.setter
    def skeleton(self, val):
        self.beginResetModel()

        self._skeleton = val
        # if this is a dst node, then determine list based on source node
        if self._src_node is not None:
            self._node_list = self._valid_dst()
        # otherwise, show all nodes for skeleton
        else:
            self._node_list = self.skeleton.node_names

        self.endResetModel()

    def _valid_dst(self):
        # get source node using callback
        src_node = self._src_node()

        def is_valid_dst(node):
            # node cannot be dst of itself
            if node == src_node:
                return False
            # node cannot be dst if it's already dst of this src
            if (src_node, node) in self.skeleton.edge_names:
                return False
            return True

        # Filter down to valid destination nodes
        valid_dst_nodes = list(filter(is_valid_dst, self.skeleton.node_names))

        return valid_dst_nodes

    def data(self, index: QtCore.QModelIndex, role=QtCore.Qt.DisplayRole):
        """Overrides Qt method, returns data for given row."""
        if role == QtCore.Qt.DisplayRole and index.isValid():
            idx = index.row()
            return self._node_list[idx]

        return None

    def rowCount(self, parent):
        """Overrides Qt method, returns number of rows."""
        return len(self._node_list)

    def columnCount(self, parent):
        """Overrides Qt method, returns number of columns (1)."""
        return 1

    def flags(self, index: QtCore.QModelIndex):
        """Overrides Qt method, returns flags (editable etc)."""
        return QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsSelectable


# T6c: a frame counts as "labeled" once the user has placed at least this many
# visible keypoints. Matches the spec wording "have >1 body points labeled"
# (>1 → ≥2). "Walked through" is implied by "has labeled points" since placing
# a keypoint requires navigating to the frame first.
DLC_LABELED_THRESHOLD = 2

# T15: column layouts for single-config vs dual-config DLC projects.
# T19: the three frame-level environment-label columns slot in before "labeled".
_DLC_SINGLE_COLUMNS = (
    "frame", "image", "points", "lying", "heat_lamp", "food", "labeled"
)
_DLC_DUAL_COLUMNS = (
    "frame", "image", "sow_pts", "piglet_pts", "lying", "heat_lamp", "food",
    "labeled",
)

# T19: frame-level environment labels (see Phase 7 in docs/TASKS.md). These are
# per-image scalar observations independent of any keypoint/skeleton, stored in
# `labels.provenance["frame_labels"]` keyed by str(frame_idx) and round-tripped
# through the .slp via provenance JSON (same store the keypoints live in).
FRAME_LABEL_FIELDS = ("lying", "heat_lamp", "food")

# (stored/CSV token, dropdown display) per field; token "" is the unset default.
# Tokens are space-free (user requirement); the friendly text is display-only.
FRAME_LABEL_OPTIONS = {
    "lying": [("", "—"), ("up", "up"), ("down", "down"), ("none", "none")],
    "heat_lamp": [
        ("", "—"), ("on", "on"), ("off", "off"), ("not_clear", "not clear")
    ],
    "food": [
        ("", "—"),
        ("3", "3 — very much"),
        ("2", "2 — middle"),
        ("1", "1 — almost done"),
        ("0", "0 — none"),
    ],
}

# Column header overrides (GenericTableModel title-cases lowercase keys, which
# would turn "heat_lamp" into "Heat_Lamp").
_FRAME_LABEL_HEADERS = {"heat_lamp": "Heat Lamp"}


def _frame_label_cell_text(field: str, token: str) -> str:
    """Compact text shown in a frame-label table cell (unset → ``—``).

    `food` cells stay numeric (3/2/1/0); other fields show their friendly text
    (e.g. ``not_clear`` → "not clear").
    """
    if not token:
        return "—"
    if field == "food":
        return token
    for tok, disp in FRAME_LABEL_OPTIONS[field]:
        if tok == token:
            return disp
    return token


def _dlc_denominator_parts(labels):
    """Return (n_nodes, n_expected_instances) for the DLC points column.

    Denominator policy (a) from TASKS.md T6b: fixed labeling budget per frame —
    `len(skeleton.nodes) * max(1, len(labels.tracks))`. Single-animal projects
    have zero tracks, so `n_expected` falls back to 1.
    """
    if labels is None or not labels.skeletons:
        return 0, 1
    n_nodes = len(labels.skeletons[0].nodes)
    n_expected = max(1, len(labels.tracks))
    return n_nodes, n_expected


def _is_dual_mode(labels) -> bool:
    """True if the project is a dual-skeleton DLC project (T13)."""
    if labels is None:
        return False
    if labels.provenance.get("mode") != "dlc_dual":
        return False
    return len(labels.skeletons) >= 2


def _dlc_dual_denominators(labels):
    """Return (n_sow, n_piglet_total) point budgets for the dual columns.

    `n_sow` = nodes on the sow skeleton (cap-1 instance).
    `n_piglet_total` = piglet_nodes × len(tracks), the full piglet budget.
    """
    sow_nodes = len(labels.skeletons[0].nodes)
    piglet_nodes = len(labels.skeletons[1].nodes)
    n_piglet_total = piglet_nodes * len(labels.tracks)
    return sow_nodes, n_piglet_total


def _count_labeled_points(labeled_frame) -> int:
    """Return the count of labeled keypoints on a frame for the DLC progress column.

    Drives the "labeled" numerator in the DLC Image Frames `points` column.

    Semantics (MUST_KNOW.md §4): a keypoint only ends up in the exported DLC
    CSV if it is *visible* (occluded/un-placed keypoints become empty cells).
    PredictedInstance points are model output, not human labeling, so they
    should not count toward labeling progress.

    Counts user-placed, visible keypoints: skip `PredictedInstance` (model
    output, not labels) and skip points the human flagged occluded.
    """
    total = 0
    for instance in labeled_frame.user_instances:
        total += instance.n_visible
    return total


def _dlc_dual_counts(labeled_frame):
    """Return (sow_labeled, piglet_labeled) for the dual-mode columns.

    `sow_labeled` is ``None`` if no sow instance (1st user instance) exists
    on the frame yet — surfaced as ``"—/4"`` so the labeler can see the
    sow placeholder is still missing. Otherwise it's the visible-point
    count on the 1st user instance.

    `piglet_labeled` is the sum of visible points across user instances
    2..N. T6e (extended by T14) caps this at len(tracks).
    """
    if labeled_frame is None:
        return None, 0
    user_insts = labeled_frame.user_instances
    if not user_insts:
        return None, 0
    sow_lab = user_insts[0].n_visible
    pig_lab = sum(inst.n_visible for inst in user_insts[1:])
    return sow_lab, pig_lab


class DLCFramesTableModel(GenericTableModel):
    """One row per image file in an ImageVideo-backed video.

    Populated from a `Video` (not a list): when its `filename` is a
    `list[str]` (ImageVideo backend), each entry becomes a row. For
    MediaVideo/HDF5Video backends, the table is empty — non-applicable.

    Columns adapt to the project mode at items-set time:
      - Single-config (legacy): ``frame | image | points | labeled``
      - Dual (T13 `mode == "dlc_dual"`): ``frame | image | sow_pts |
        piglet_pts | labeled``
    The column swap relies on the `items` setter's `beginResetModel` /
    `endResetModel` calls (`GenericTableModel.items.setter`).
    """

    properties = _DLC_SINGLE_COLUMNS

    def object_to_items(self, video):
        fn = getattr(video, "filename", None)
        if not isinstance(fn, list):
            return []

        labels = self.context.labels if self.context is not None else None
        is_dual = _is_dual_mode(labels)

        # Adapt the column layout to the project mode. The surrounding
        # `items` setter wraps this call in begin/endResetModel, so the
        # column count change is picked up by the view automatically.
        self.properties = _DLC_DUAL_COLUMNS if is_dual else _DLC_SINGLE_COLUMNS

        if is_dual:
            n_sow, n_piglet_total = _dlc_dual_denominators(labels)
        else:
            n_nodes, n_expected = _dlc_denominator_parts(labels)
            total = n_nodes * n_expected

        # T19: per-frame environment labels stored in provenance.
        frame_labels = (
            labels.provenance.get("frame_labels", {}) if labels is not None else {}
        )

        items = []
        for i, f in enumerate(fn):
            lf = None
            if labels is not None:
                lfs = labels.find(video=video, frame_idx=i, return_new=False)
                if lfs:
                    lf = lfs[0]

            entry = frame_labels.get(str(i), {})
            row = {
                "frame": i + 1,
                "image": Path(f).name,
                "_frame_idx": i,
                "_video": video,
                "lying": entry.get("lying", ""),
                "heat_lamp": entry.get("heat_lamp", ""),
                "food": entry.get("food", ""),
            }
            if is_dual:
                sow_lab, pig_lab = _dlc_dual_counts(lf)
                row["sow_pts"] = (
                    f"{sow_lab}/{n_sow}"
                    if sow_lab is not None
                    else f"—/{n_sow}"
                )
                row["piglet_pts"] = f"{pig_lab}/{n_piglet_total}"
                # Strict rule (T15): a row counts as labeled only when BOTH
                # skeletons meet the threshold. Re-evaluate during T18.
                row["labeled"] = (
                    1
                    if (
                        sow_lab is not None
                        and sow_lab >= DLC_LABELED_THRESHOLD
                        and pig_lab >= DLC_LABELED_THRESHOLD
                    )
                    else 0
                )
            else:
                labeled = _count_labeled_points(lf) if lf is not None else 0
                row["points"] = f"{labeled}/{total}"
                row["labeled"] = (
                    1 if labeled >= DLC_LABELED_THRESHOLD else 0
                )
            items.append(row)
        return items

    def update_row_for_frame(self, frame_idx: int, labeled_frame) -> None:
        """Recompute the derived cells for a single row.

        Called from `on_data_update` when a user command mutates the current
        frame. Updates only the affected row so scroll position and row
        selection are preserved. Emits one `dataChanged` spanning the derived
        columns to avoid redundant repaints.
        """
        if not (0 <= frame_idx < len(self._data)):
            return
        labels = self.context.labels if self.context is not None else None
        is_dual = _is_dual_mode(labels)

        if is_dual:
            n_sow, n_piglet_total = _dlc_dual_denominators(labels)
            sow_lab, pig_lab = _dlc_dual_counts(labeled_frame)
            self._data[frame_idx]["sow_pts"] = (
                f"{sow_lab}/{n_sow}"
                if sow_lab is not None
                else f"—/{n_sow}"
            )
            self._data[frame_idx]["piglet_pts"] = (
                f"{pig_lab}/{n_piglet_total}"
            )
            self._data[frame_idx]["labeled"] = (
                1
                if (
                    sow_lab is not None
                    and sow_lab >= DLC_LABELED_THRESHOLD
                    and pig_lab >= DLC_LABELED_THRESHOLD
                )
                else 0
            )
            first_col_name = "sow_pts"
        else:
            n_nodes, n_expected = _dlc_denominator_parts(labels)
            total = n_nodes * n_expected
            labeled = (
                _count_labeled_points(labeled_frame)
                if labeled_frame is not None
                else 0
            )
            self._data[frame_idx]["points"] = f"{labeled}/{total}"
            self._data[frame_idx]["labeled"] = (
                1 if labeled >= DLC_LABELED_THRESHOLD else 0
            )
            first_col_name = "points"

        if first_col_name not in self.properties or "labeled" not in self.properties:
            return
        first = self.properties.index(first_col_name)
        last = self.properties.index("labeled")
        self.dataChanged.emit(
            self.index(frame_idx, first), self.index(frame_idx, last)
        )

    # ---- T19: frame-level environment labels (lying / heat_lamp / food) ----

    def data(self, index: QtCore.QModelIndex, role=QtCore.Qt.DisplayRole):
        """Frame-label cells display friendly text but edit/store the token."""
        if index.isValid():
            key = self.properties[index.column()]
            if key in FRAME_LABEL_FIELDS:
                token = self.items[index.row()].get(key, "")
                if role == QtCore.Qt.EditRole:
                    return token
                if role in (QtCore.Qt.DisplayRole, QtCore.Qt.ToolTipRole):
                    return _frame_label_cell_text(key, token)
        return super().data(index, role)

    def headerData(
        self, idx: int, orientation: QtCore.Qt.Orientation, role=QtCore.Qt.DisplayRole
    ):
        """Override the displayed header for keys that title-case poorly."""
        if role == QtCore.Qt.DisplayRole and orientation == QtCore.Qt.Horizontal:
            key = self.properties[idx]
            if key in _FRAME_LABEL_HEADERS:
                return _FRAME_LABEL_HEADERS[key]
        return super().headerData(idx, orientation, role)

    def can_set(self, item, key):
        """Only the three environment-label columns are editable."""
        return key in FRAME_LABEL_FIELDS

    def set_item(self, item, key, value):
        """Persist a dropdown change via `SetFrameLabel` and update the row."""
        if key not in FRAME_LABEL_FIELDS or self.context is None:
            return
        frame_idx = item.get("_frame_idx") if isinstance(item, dict) else None
        if frame_idx is None:
            return
        self.context.setFrameLabel(frame_idx=frame_idx, field=key, value=value)
        item[key] = value

    def refresh_frame_label_cells(self, frame_idx: int) -> None:
        """Re-read a frame's environment labels from provenance into its row.

        Used after a programmatic change (e.g. copy-prior-frame, T20) that did
        not go through this model's `setData`.
        """
        if not (0 <= frame_idx < len(self._data)):
            return
        labels = self.context.labels if self.context is not None else None
        frame_labels = (
            labels.provenance.get("frame_labels", {}) if labels is not None else {}
        )
        entry = frame_labels.get(str(frame_idx), {})
        for field in FRAME_LABEL_FIELDS:
            self._data[frame_idx][field] = entry.get(field, "")
        cols = [
            self.properties.index(field)
            for field in FRAME_LABEL_FIELDS
            if field in self.properties
        ]
        if cols:
            self.dataChanged.emit(
                self.index(frame_idx, min(cols)),
                self.index(frame_idx, max(cols)),
            )
