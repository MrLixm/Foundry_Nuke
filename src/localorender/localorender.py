"""
author: liam collod
requirement: nuke,python-2.7+
"""
import contextlib
import os
import re
import sys
import tempfile
import uuid
import webbrowser
from functools import partial

import nuke
import nukescripts

import logging

from PySide2 import QtWidgets
from PySide2 import QtCore
from PySide2 import QtGui

APPNAME = "localorender"
LOGGER = logging.getLogger(APPNAME)

__version__ = "0.2.0"


@contextlib.contextmanager
def create_temp_knob(node, knob_class, *args, **kwargs):
    """
    Context to create a knob and delete it on exit.
    """
    knob = knob_class(*args, **kwargs)
    node.addKnob(knob)
    try:
        yield knob
    finally:
        node.removeKnob(knob)


def get_write_node_paths_by_frame(write_node, frames, views):
    """
    Get all the paths the write node will create for the given frames and views.

    Args:
        write_node(nuke.Node):
        frames(list[int]):
        views(list[str]):

    Returns:
        dict[str, tuple[int, str]]:
    """
    # noinspection PyTypeChecker
    file_knob = write_node.knob("file")  # type: nuke.File_Knob
    src_path = file_knob.toScript()
    paths = {}  # type: dict[str, tuple[int, str]]

    original_views = write_node.knob("views").value().split(" ")  # type: list[str]
    # we cannot render more views than defined on the Write node
    views = [view for view in views if view in original_views]

    # XXX: because file_knob.evaluate() would resolve the Tcl AND the frame token we need
    #   to process it in 2 parts. We resolve ourselves the frames token and create a new
    #   temp knob to resolve the potential tcl.
    with create_temp_knob(write_node, nuke.File_Knob, "__tmprender") as tmp_knob:
        for view in views:
            for frame in frames:
                iteration_path = src_path

                # see : https://learn.foundry.com/nuke/11.2/content/comp_environment/stereoscopic_films/rendering_stereo_images.html
                if "%V" in iteration_path:
                    iteration_path = iteration_path.replace("%V", view)
                if "%v" in iteration_path:
                    iteration_path = iteration_path.replace("%v", view[0])

                has_frames = re.search(r"(#+)", iteration_path)
                if has_frames:
                    iteration_path = nukescripts.replaceHashes(iteration_path) % frame

                tmp_knob.setValue(iteration_path)
                path = tmp_knob.evaluate()
                if path not in paths:
                    paths[path] = (frame, view)

    return paths


class SvgIcons:
    """
    We create a "hacky" system to have custom QIcon with no file dependency before the runtime.
    """

    def __init__(self):
        # note: we cannot use a context manager as QIcon are loaded on demand from disk.
        self._tmpdir = tempfile.mkdtemp(prefix="nuke-{}-".format(APPNAME))

        # ref: https://pictogrammers.com/library/mdi/icon/file-hidden/
        tmpfile = self._write_svg(
            '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><title>file-hidden</title><path fill="#D34A44" d="M13,9H14V11H11V7H13V9M18.5,9L16.38,6.88L17.63,5.63L20,8V10H18V11H15V9H18.5M13,3.5V2H12V4H13V6H11V4H9V2H8V4H6V5H4V4C4,2.89 4.89,2 6,2H14L16.36,4.36L15.11,5.61L13,3.5M20,20A2,2 0 0,1 18,22H16V20H18V19H20V20M18,15H20V18H18V15M12,22V20H15V22H12M8,22V20H11V22H8M6,22C4.89,22 4,21.1 4,20V18H6V20H7V22H6M4,14H6V17H4V14M4,10H6V13H4V10M18,11H20V14H18V11M4,6H6V9H4V6Z" /></svg>',
        )
        self.filedontexist = QtGui.QIcon(tmpfile)

        # ref: https://pictogrammers.com/library/mdi/icon/file-check-outline/
        tmpfile = self._write_svg(
            '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><title>file-check-outline</title><path fill="#58CE53" d="M23.5 17L18.5 22L15 18.5L16.5 17L18.5 19L22 15.5L23.5 17M13.09 20H6V4H13V9H18V13.09C18.33 13.04 18.66 13 19 13S19.67 13.04 20 13.09V8L14 2H6C4.89 2 4 2.9 4 4V20C4 21.11 4.89 22 6 22H13.81C13.46 21.39 13.21 20.72 13.09 20Z" /></svg>',
        )
        self.fileexist = QtGui.QIcon(tmpfile)

        # ref: https://pictogrammers.com/library/mdi/icon/sync/
        tmpfile = self._write_svg(
            '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><title>sync</title><path fill="#D2D9EC" d="M12,18A6,6 0 0,1 6,12C6,11 6.25,10.03 6.7,9.2L5.24,7.74C4.46,8.97 4,10.43 4,12A8,8 0 0,0 12,20V23L16,19L12,15M12,4V1L8,5L12,9V6A6,6 0 0,1 18,12C18,13 17.75,13.97 17.3,14.8L18.76,16.26C19.54,15.03 20,13.57 20,12A8,8 0 0,0 12,4Z" /></svg>',
        )
        self.reload = QtGui.QIcon(tmpfile)

        # ref: https://pictogrammers.com/library/mdi/icon/help/
        tmpfile = self._write_svg(
            '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><title>help</title><path fill="#D2D9EC" d="M10,19H13V22H10V19M12,2C17.35,2.22 19.68,7.62 16.5,11.67C15.67,12.67 14.33,13.33 13.67,14.17C13,15 13,16 13,17H10C10,15.33 10,13.92 10.67,12.92C11.33,11.92 12.67,11.33 13.5,10.67C15.92,8.43 15.32,5.26 12,5A3,3 0 0,0 9,8H6A6,6 0 0,1 12,2Z" /></svg>',
        )
        self.help = QtGui.QIcon(tmpfile)

    def __del__(self):
        """
        Remove the temporary directory when the instance is deleted.
        """
        LOGGER.debug("removing temp dir '{}'".format(self._tmpdir))
        # noinspection PyProtectedMember,PyUnresolvedReferences
        tempfile.TemporaryDirectory._rmtree(self._tmpdir)

    def _write_svg(self, content):
        filename = uuid.uuid4().hex
        filepath = os.path.join(self._tmpdir, filename + ".svg")
        LOGGER.debug("writing temp icon to '{}'".format(filepath))
        with open(filepath, "w") as f:
            f.write(content)
        return filepath


class WriteNodeTreeWidgetItem(QtWidgets.QTreeWidgetItem):
    """
    QTreeWidgetItem that represent a path that will be written to disk when rendering.

    Each path correspond to a frame and a parent Write node.


    Args:
        node(nuke.Node):
        path(str):
        frame(int):
        view(str):
        parent(QtWidgets.QTreeWidget):
        icons(SvgIcons):
    """

    columns = {
        "frame": {"index": 0, "label": "Frame"},
        "node": {"index": 1, "label": "Node"},
        "path": {"index": 2, "label": "Path"},
        "status": {"index": 3, "label": "Status"},
        "view": {"index": 4, "label": "View"},
    }

    def __init__(self, node, path, frame, view, parent, icons):
        super(WriteNodeTreeWidgetItem, self).__init__(parent)
        self.node = node
        self.frame = frame
        self.path = path
        self.view = view
        self._icons = icons
        self.populate()

    @property
    def path_exists(self) -> bool:
        return os.path.exists(self.path)

    def populate(self):
        self.setText(self.columns["node"]["index"], self.node.name())
        self.setText(self.columns["frame"]["index"], str(self.frame).zfill(4))
        self.setText(self.columns["path"]["index"], str(self.path))
        if self.path_exists:
            icon = self._icons.fileexist
            tooltip = "Frame already exist on disk."
        else:
            icon = self._icons.filedontexist
            tooltip = "Frame not written to disk yet."

        self.setIcon(self.columns["status"]["index"], icon)
        self.setToolTip(self.columns["status"]["index"], tooltip)
        self.setText(self.columns["view"]["index"], self.view)

    def set_node_selected(self):
        self.node.setSelected(True)

    def copy_path_to_clipboard(self):
        clipboard = QtWidgets.QApplication.clipboard()
        clipboard.clear(mode=clipboard.Clipboard)
        clipboard.setText(self.path, mode=clipboard.Clipboard)

    def open_path_in_file_explorer(self):
        directory = os.path.dirname(self.path)
        if not os.path.exists(directory):
            LOGGER.warning("cannot open non-existing directory '{}'".format(directory))
            return
        webbrowser.open(directory)


class WriteNodesTreeWidget(QtWidgets.QTreeWidget):
    """
    A collection of paths that will be created by the associated Write nodes.

    Args:
        icons(SvgIcons):
    """

    child_type = WriteNodeTreeWidgetItem

    def __init__(self, icons, parent=None):
        super(WriteNodesTreeWidget, self).__init__(parent)

        self._icons = icons

        self.setColumnCount(len(self.child_type.columns))
        self.setAlternatingRowColors(False)
        self.setSortingEnabled(True)
        self.setUniformRowHeights(True)
        self.setRootIsDecorated(False)
        self.setItemsExpandable(False)
        # select only one row at a time
        self.setSelectionMode(self.SingleSelection)
        # select only rows
        self.setSelectionBehavior(self.SelectRows)
        # remove dotted border on columns
        self.setFocusPolicy(QtCore.Qt.NoFocus)

        header = self.header()
        model = self.model()  # type: QtCore.QAbstractItemModel
        header.setSectionResizeMode(header.Interactive)
        header.setSortIndicator(0, QtCore.Qt.AscendingOrder)

        for columnId, columnConfig in self.child_type.columns.items():
            columnIndex = columnConfig["index"]
            columnName = columnConfig.get("label", columnId)
            model.setHeaderData(columnIndex, QtCore.Qt.Horizontal, columnName)

        self.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)

        self.customContextMenuRequested[QtCore.QPoint].connect(self._context_menu)

    def populate(self, write_nodes, frames, views):
        """
        Clean and fill the tree with new items.

        Args:
            write_nodes(list[nuke.Node]):
            frames(list[int]):
            views(list[str]):
        """
        self.clear()
        if not frames or not write_nodes:
            return

        for write_node in write_nodes:
            paths = get_write_node_paths_by_frame(write_node, frames, views)
            for path, context in paths.items():
                self.child_type(
                    node=write_node,
                    path=path,
                    frame=context[0],
                    view=context[1],
                    parent=self,
                    icons=self._icons,
                )

        for columnIndex in range(len(self.child_type.columns)):
            self.resizeColumnToContents(columnIndex)

    def get_all_nodes_tree_items(self):
        """
        Iterate trhough the tree to return all child items.

        Returns:
            list[WriteNodeTreeWidgetItem]:
        """
        itemList = []
        root = self.invisibleRootItem()
        childCount = root.childCount()
        for index in range(childCount):
            itemList.append(root.child(index))

        return itemList

    def _context_menu(self, point):
        """
        Open a context menu at the given point.
        """
        current_tree_item = self.itemAt(point)  # type: WriteNodeTreeWidgetItem
        if not current_tree_item:
            return

        qmenu = QtWidgets.QMenu()
        action1 = QtWidgets.QAction("Select Node in Nodegraph")
        action1.triggered.connect(current_tree_item.set_node_selected)
        qmenu.addAction(action1)
        action2 = QtWidgets.QAction("Copy Path")
        action2.triggered.connect(current_tree_item.copy_path_to_clipboard)
        qmenu.addAction(action2)
        action3 = QtWidgets.QAction("Open Path in File Explorer")
        action3.triggered.connect(current_tree_item.open_path_in_file_explorer)
        qmenu.addAction(action3)

        qmenu.exec_(QtGui.QCursor.pos())


class FrameRangeFieldWidget(QtWidgets.QLineEdit):
    """
    A field where the user enter a frame range expression that resolve to a list of frames.
    """

    def __init__(self, parent=None):
        super(FrameRangeFieldWidget, self).__init__(parent)
        self.setContextMenuPolicy(QtCore.Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested[QtCore.QPoint].connect(self._on_contextmenu)

    def set_framerange_from_project(self):
        framerange = str(nuke.root().frameRange())
        LOGGER.debug("setting framerange '{}' from root".format(framerange))
        self.setText(framerange)

    def set_framerange_from_active_node(self):
        try:
            activeInput = nuke.activeViewer().activeInput()
            framerange = nuke.activeViewer().node().upstreamFrameRange(activeInput)
            framerange = str(framerange)
        except:
            return self.set_framerange_from_project()

        LOGGER.debug("setting framerange '{}' from active node".format(framerange))
        self.setText(framerange)

    def set_framerange_viewer_inout(self, viewer):
        """
        Args:
            viewer(nuke.Viewer):
        """
        framerange = str(viewer.playbackRange())
        self.setText(framerange)

    def set_framerange_viewer_visible(self, viewer):
        """
        Args:
            viewer(nuke.Viewer):
        """
        framerange = str(viewer.visibleRange())
        self.setText(framerange)

    def set_invalid_framerange_state(self, enabled):
        """
        Args:
            enabled(bool):
        """
        if enabled:
            self.setStyleSheet("QWidget{ background-color: #7B2E36;}")
            self.setToolTip("Invalid frame range expression.")
        else:
            self.setStyleSheet("")
            self.setToolTip("")

    def get_frames(self):
        """
        Returns:
            list[int]:
        """
        framerange_txt = self.text()
        frameranges = nuke.FrameRanges(framerange_txt.split(","))
        frames = frameranges.toFrameList()
        if not frames:
            raise ValueError("Unsupported frame range '{}'".format(framerange_txt))
        return sorted(frames)

    def _on_contextmenu(self, point):
        menu = self.createStandardContextMenu()
        menu.addSection("Presets")
        menu.addAction("project", self.set_framerange_from_project)
        menu.addAction("active viewer input", self.set_framerange_from_active_node)

        for viewer_node in nuke.allNodes("Viewer", nuke.Root()):
            viewermenu = menu.addMenu(viewer_node.name())
            viewermenu.addAction(
                "in-out", partial(self.set_framerange_viewer_inout, viewer_node)
            )
            viewermenu.addAction(
                "visible", partial(self.set_framerange_viewer_visible, viewer_node)
            )

        menu.exec_(QtGui.QCursor.pos())

    def save_settings(self, settings):
        """
        Args:
            settings(QtCore.QSettings):
        """
        settings.beginGroup("framerangeselector")
        settings.setValue("expression", self.text())
        settings.endGroup()

    def load_settings(self, settings):
        """
        Args:
            settings(QtCore.QSettings):
        """
        settings.beginGroup("framerangeselector")
        value = settings.value("expression", "", type=str)
        if value:
            self.setText(value)
        else:
            self.set_framerange_from_project()

        settings.endGroup()


class ViewSelectWidget(QtWidgets.QPushButton):
    """
    A combobox looking button that allow to check which views you want to render.
    """

    selected_views_changed = QtCore.Signal()

    def __init__(self, parent=None):
        super(ViewSelectWidget, self).__init__(parent)
        self._menu = QtWidgets.QMenu(self)
        self._selected_views = []

        self.setMenu(self._menu)
        self.setToolTip(
            "Filter out which views to render. The original list of view is determined "
            "on the Write node and this widget can only reduce the numebr of view "
            "to render but not render new ones."
        )

        for view in nuke.views():
            action = self._menu.addAction(view)  # type: QtWidgets.QAction
            action.setCheckable(True)
            action.changed.connect(self._on_action_triggerred)

    @property
    def selected_views(self):
        """
        Returns:
            list[str]:
        """
        return self._selected_views

    def set_first_view_selected(self):
        for action in self._menu.actions():
            action.setChecked(True)
            break

    def set_selected_views(self, views, selected):
        """
        Args:
            views(list[str]): list of view name
            selected(bool): state to set
        """
        for action in self._menu.actions():
            if action.text() in views:
                action.setChecked(selected)
            else:
                action.setChecked(not selected)

    def _on_action_triggerred(self, *args):
        self._selected_views = []
        for action in self._menu.actions():
            if action.isChecked():
                self._selected_views.append(action.text())

        label = ", ".join(self._selected_views)
        self.setText(label)
        self.selected_views_changed.emit()

    def save_settings(self, settings):
        """
        Args:
            settings(QtCore.QSettings):
        """
        settings.beginGroup("viewselector")
        settings.setValue("selected", ",".join(self.selected_views))
        settings.endGroup()

    def load_settings(self, settings):
        """
        Args:
            settings(QtCore.QSettings):
        """
        settings.beginGroup("viewselector")
        value = settings.value("selected", "", type=str)  # type: str | None
        if value:
            views = value.split(",")
            self.set_selected_views(views, selected=True)
        else:
            self.set_first_view_selected()
        settings.endGroup()


class WriteNodeSelectorWidget(QtWidgets.QComboBox):
    option_selection = "Selected Write Nodes"
    option_all = "All Write Nodes"
    option_this = "This current Write Node"
    options = [option_selection, option_all, option_this]

    def __init__(self, parent=None):
        super(WriteNodeSelectorWidget, self).__init__(parent)
        self.addItems(self.options)
        self.setCurrentIndex(-1)

    def set_current_option(self, option_name):
        """
        Args:
            option_name(str):
        """
        option_index = self.options.index(option_name)
        self.setCurrentIndex(option_index)

    def get_selected_nodes(self):
        """
        Returns:
            list[nuke.Node]:
        """
        option = self.currentText()
        if option == self.option_selection:
            return nuke.selectedNodes("Write")
        elif option == self.option_all:
            return nuke.allNodes("Write", nuke.Root())
        else:
            node = nuke.thisNode()
            return [node] if node.Class() == "Write" else []

    def save_settings(self, settings):
        """
        Args:
            settings(QtCore.QSettings):
        """
        settings.beginGroup("writenodeselector")
        settings.setValue("selected", self.currentText())
        settings.endGroup()

    def load_settings(self, settings):
        """
        Args:
            settings(QtCore.QSettings):
        """
        settings.beginGroup("writenodeselector")
        value = settings.value("selected", None, type=str)
        if value:
            self.set_current_option(value)
        else:
            self.set_current_option(self.option_selection)
        settings.endGroup()


class LocaloRenderDialog(QtWidgets.QDialog):
    """
    Args:
        node_selection_mode(str or None):
    """

    def __init__(self, node_selection_mode=None):
        super(LocaloRenderDialog, self).__init__()

        # we instance once at tree level to avoid to many IO calls
        self._icons = SvgIcons()
        self._app_settings = QtCore.QSettings("liamcollod.nuke", APPNAME)

        self._write_nodes = []  # type: list[nuke.Node]
        self._frames = []  # type: list[int]
        self._views = []  # type: list[str]

        self._layout = QtWidgets.QVBoxLayout()
        self._layout_header = QtWidgets.QHBoxLayout()
        self._layout_footer = QtWidgets.QHBoxLayout()

        self._tree = WriteNodesTreeWidget(icons=self._icons)
        self._menubar = QtWidgets.QMenuBar()
        self._label_title = QtWidgets.QLabel(
            "<b>{} <sub>v{}</sub></b>".format(APPNAME, __version__)
        )
        self._label_frames = QtWidgets.QLabel("Frame Range")
        self._field_frames = FrameRangeFieldWidget()
        self._button_help = QtWidgets.QToolButton()
        self._label_nodes = QtWidgets.QLabel("Nodes")
        self._node_selector = WriteNodeSelectorWidget()
        self._button_refresh = QtWidgets.QToolButton()
        self._button_render = QtWidgets.QPushButton("Render")
        self._views_selector = ViewSelectWidget()
        self._option_proxy = QtWidgets.QCheckBox("Use Proxy")
        self._option_continue_error = QtWidgets.QCheckBox("Continue On Error")
        self._option_skip_existing = QtWidgets.QCheckBox("Skip Existing Frames")

        self._menubar.setCornerWidget(self._label_title, QtCore.Qt.Corner.TopLeftCorner)
        menu = self._menubar.addMenu("Settings")
        menu.addAction("Reset Default Settings", self.reset_settings)
        menu.addAction("Save Current Settings", self.save_settings)
        menu = self._menubar.addMenu("Help")
        menu.addAction("Open Reference", self._on_open_ref)
        menu.addAction("Open Documentation", self._on_open_doc)
        menu.addAction("Report An Issue", self._on_report_issue)

        self.setLayout(self._layout)
        self._layout.addWidget(self._menubar)
        self._layout.addSpacing(10)
        self._layout.addLayout(self._layout_header)
        self._layout.addWidget(self._tree)
        self._layout.addLayout(self._layout_footer)
        self._layout.addWidget(self._button_render)
        self._layout_header.addWidget(self._label_frames)
        self._layout_header.addWidget(self._field_frames)
        self._layout_header.addWidget(self._button_help)
        self._layout_header.addWidget(self._label_nodes)
        self._layout_header.addWidget(self._node_selector)
        self._layout_header.addStretch(1)
        self._layout_header.addWidget(self._button_refresh)
        self._layout_footer.addWidget(self._views_selector)
        self._layout_footer.addStretch(1)
        self._layout_footer.addWidget(self._option_proxy)
        self._layout_footer.addWidget(self._option_continue_error)
        self._layout_footer.addWidget(self._option_skip_existing)

        self.setWindowTitle("local render from Write node")
        self._layout.setContentsMargins(15, 5, 15, 15)
        self._button_refresh.setIcon(self._icons.reload)
        self._button_refresh.setToolTip("Reload the below list of paths.")
        self._option_skip_existing.setToolTip(
            "Frames that are already existing on disk will not be rendered again."
        )
        self._button_help.setIcon(self._icons.help)
        self._button_help.setToolTip(
            "Nuke syntax for frame-ranges. Examples:<ul><li>3</li><li>1 3 4 8</li><li>1-10</li><li>1-10×2</li><li>1-10×2 10-30x3</li></ul>"
            "You can right click the field to show presets."
        )

        self._field_frames.textChanged.connect(self._on_framerange_modified)
        self._button_render.clicked.connect(self.launch_render)
        self._button_refresh.clicked.connect(self.update_internals)
        self._button_help.clicked.connect(self._on_framerange_help)
        self._views_selector.selected_views_changed.connect(self._on_views_modified)
        self._node_selector.currentIndexChanged.connect(
            self._on_node_selection_mode_modified
        )

        # those functions are last cause need to trigger signals we just connected:

        if not os.getenv("LOCALORENDER_DISABLE_QSETTINGS"):
            self.load_settings()

        if node_selection_mode:
            if node_selection_mode not in self._node_selector.options:
                raise ValueError(
                    "Unsuported node selection mode '{}', expected one of {}"
                    "".format(node_selection_mode, self._node_selector.options)
                )
            self._node_selector.set_current_option(node_selection_mode)

    def closeEvent(self, event):
        self.save_settings()
        super(LocaloRenderDialog, self).closeEvent(event)

    def populate(self):
        LOGGER.info(
            "_write_nodes={} _frames={} _views={}"
            "".format(self._write_nodes, self._frames, self._views)
        )
        self._tree.populate(
            write_nodes=self._write_nodes,
            frames=self._frames,
            views=self._views,
        )

    def update_internals(self):
        self._write_nodes = self._node_selector.get_selected_nodes()
        self._views = self._views_selector.selected_views
        self._update_internal_framerange()
        self.populate()

    def launch_render(self):
        self.save_settings()
        skip_existing = self._option_skip_existing.isChecked()
        continue_error = self._option_continue_error.isChecked()
        use_proxy = self._option_proxy.isChecked()

        tree_items = self._tree.get_all_nodes_tree_items()
        if skip_existing:
            before_len = len(tree_items)
            tree_items = [item for item in tree_items if not item.path_exists]
            LOGGER.info(
                "skipping {} existing frames".format(before_len - len(tree_items))
            )

        treeitems_by_node = {}  # type: dict[nuke.Node, list[WriteNodeTreeWidgetItem]]
        for tree_item in tree_items:
            treeitems_by_node.setdefault(tree_item.node, []).append(tree_item)

        proxy_backup = nuke.root().proxy()
        nuke.Undo().disable()
        nuke.root().setProxy(use_proxy)
        nuke.callbacks.addAfterRender(self.populate)
        errors = []
        try:
            for node, treeitems in treeitems_by_node.items():
                frames = []
                views = []
                for treeitem in treeitems:
                    if treeitem.view not in views:
                        views.append(treeitem.view)

                    frame = str(treeitem.frame)
                    if frame not in frames:
                        frames.append(frame)

                framerange = nuke.FrameRanges(" ".join(frames))
                framerange_str = ",".join(map(str, framerange.toFrameList()))
                views_str = ",".join(views)
                LOGGER.info(
                    "executing node '{}' with frames '{}' and views '{}'"
                    "".format(node.name(), framerange_str, views_str)
                )
                try:
                    nuke.executeMultiple(
                        [node],
                        framerange,
                        views=views,
                        continueOnError=continue_error,
                    )
                except Exception as error:
                    new_error = "Error while rendering node={};views={};framerange={}: {}".format(
                        node.name(), views_str, framerange_str, error
                    )
                    errors.append(new_error)

        finally:
            nuke.Undo().enable()
            nuke.root().setProxy(proxy_backup)
            nuke.callbacks.removeAfterRender(self.populate)

        if errors:
            message = "The following errors happens during rendering:"
            message += "\n- ".join([""] + errors)
            nuke.critical(message)

    def save_settings(self):
        settings = self._app_settings
        self._node_selector.save_settings(settings)
        self._field_frames.save_settings(settings)
        self._views_selector.save_settings(settings)

        settings.beginGroup("dialog")
        settings.setValue("use_proxy", self._option_proxy.isChecked())
        settings.setValue("continue_error", self._option_continue_error.isChecked())
        settings.setValue("skip_existing", self._option_skip_existing.isChecked())
        settings.endGroup()

    def load_settings(self):
        settings = self._app_settings
        self._node_selector.load_settings(settings)
        self._field_frames.load_settings(settings)
        self._views_selector.load_settings(settings)

        settings.beginGroup("dialog")
        for option_key, option in [
            ("use_proxy", self._option_proxy),
            ("continue_error", self._option_continue_error),
            ("skip_existing", self._option_skip_existing),
        ]:
            value = settings.value(option_key, False, type=bool)
            option.setChecked(value)
        settings.endGroup()

    def reset_settings(self):
        self._app_settings.clear()
        self.load_settings()

    def _update_internal_framerange(self):
        try:
            self._frames = self._field_frames.get_frames()
        except ValueError:
            self._frames = []
            self._field_frames.set_invalid_framerange_state(enabled=True)
        else:
            self._field_frames.set_invalid_framerange_state(enabled=False)

    @QtCore.Slot()
    def _on_framerange_modified(self):
        self._update_internal_framerange()
        self.populate()

    @QtCore.Slot()
    def _on_views_modified(self):
        self._views = self._views_selector.selected_views
        self.populate()

    @QtCore.Slot()
    def _on_framerange_help(self):
        webbrowser.open(
            "https://learn.foundry.com/nuke/content/getting_started/managing_scripts/defining_frame_ranges.html"
        )

    @QtCore.Slot()
    def _on_open_ref(self):
        webbrowser.open("https://github.com/MrLixm/Foundry_Nuke")

    @QtCore.Slot()
    def _on_open_doc(self):
        webbrowser.open(
            "https://github.com/MrLixm/Foundry_Nuke/tree/main/src/localorender"
        )

    @QtCore.Slot()
    def _on_report_issue(self):
        webbrowser.open("https://github.com/MrLixm/Foundry_Nuke/issues")

    @QtCore.Slot()
    def _on_node_selection_mode_modified(self):
        selection = self._node_selector.get_selected_nodes()
        self._write_nodes = selection
        self.populate()


def open_as_dialog():
    if nuke.thisNode() and nuke.thisNode().Class() == "Write":
        dialog = LocaloRenderDialog(WriteNodeSelectorWidget.option_this)
    else:
        dialog = LocaloRenderDialog()

    dialog.exec_()


def open_as_panel(modal=False):
    panel = nukescripts.registerWidgetAsPanel(
        widget="LocaloRenderDialog",
        name="Localorender",
        id="liamcollod.localorender",
        create=True,
    )
    if modal:
        panel.showModalDialog()
    else:
        panel.show()


def configure_logging():
    """
    Configure nuke logging if it was never done by another process.
    """
    if not len(logging.root.handlers) == 1:
        return
    # try to check if nuke default handler that have never been set
    handler = logging.root.handlers[0]
    if handler.level != logging.NOTSET:
        return

    print("configuring python logging")
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter(
        "%(levelname)-7s | %(asctime)s [%(name)s] %(message)s"
    )
    handler.setFormatter(formatter)
    logging.root.addHandler(handler)
    logging.root.setLevel(logging.INFO)


if __name__ == "__main__":
    configure_logging()
    open_as_panel()