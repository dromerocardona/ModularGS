import sys
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QLabel, QVBoxLayout,
    QHBoxLayout, QPushButton, QComboBox, QGroupBox, QGridLayout, QSpacerItem,
    QSizePolicy, QToolBar, QAction, QFileDialog, QInputDialog, QMessageBox,
    QDialog, QListWidget, QAbstractItemView)
from PyQt5.QtGui import QIcon
from PyQt5.QtGui import QFont, QPixmap
from PyQt5.QtCore import Qt, QObject, pyqtSignal
from communication import Communication
from serial.tools import list_ports
from typing import Iterable
from map import GPSMap
from data import Data
from graph import Graph, rpyGraph
import serial

def get_available_serial_ports() -> Iterable[str]:
    return map(lambda c: c.device, list_ports.comports())

# Used for updating graphs, telemetry, etc.
class SignalEmitter(QObject):
    update_signal = pyqtSignal()

    def emit_signal(self) -> None:
        self.update_signal.emit()

# Main GCS window
class GroundStation(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("GS")
        self.setGeometry(100, 100, 1200, 800)
        self.setStyleSheet("background-color: #070B57;")
        self.showMaximized()
        screen_geometry = QApplication.desktop().screenGeometry()

        self.data = Data() # Get preferences and other data
        self.comm = Communication(self.data.getPreference("port")) # Initialize communication
        # connect Communication's telemetry dict signal to handler
        try:
            self.comm.telemetry_received.connect(self.handle_telemetry)
        except Exception:
            pass

        self.central_widget = QWidget(self)
        self.setCentralWidget(self.central_widget)
        main_layout = QVBoxLayout(self.central_widget)
        
        ### Header Layout ###

        header_widget = QWidget()
        header_layout = QHBoxLayout()
        header_widget.setLayout(header_layout)
        header_height = screen_geometry.height() // 15
        header_widget.setFixedHeight(header_height)
        header_widget.setStyleSheet("background-color: #545454;")

        header_text = QLabel("SHC GROUND STATION")
        header_text.setAlignment(Qt.AlignCenter)
        header_text.setFont(QFont("Arial", 15, QFont.Bold))
        header_text.setStyleSheet("color: white;")

        header_layout.addWidget(header_text)

        main_layout.addWidget(header_widget)

        content_layout = QHBoxLayout()

        ### Sidebar Layout ###

        sidebar_layout = QVBoxLayout()
        sidebar_layout.setAlignment(Qt.AlignTop)
        sidebar_layout.setSpacing(10)
        sidebar_layout.addItem(QSpacerItem(10, 10))
        sidebar_groupbox = QGroupBox("")
        sidebar_groupbox.setStyleSheet("background-color: #d1d1f0;")
        sidebar_groupbox.setStyleSheet("QGroupBox { background-color: #d1d1f0; }")
        sidebar_groupbox_layout = QVBoxLayout()
        sidebar_groupbox.setLayout(sidebar_groupbox_layout)
        buttons_grid = QGridLayout()
        buttons_grid.setAlignment(Qt.AlignCenter)
        sidebar_layout.addWidget(sidebar_groupbox)
        buttons_widget = QWidget()
        buttons_widget.setLayout(buttons_grid)
        sidebar_layout.addWidget(buttons_widget)
        # store a reference to the buttons grid for command buttons
        self.buttons_grid = buttons_grid
        self.sidebar_widget = QWidget()
        self.sidebar_widget.setLayout(sidebar_layout)
        self.sidebar_widget.setStyleSheet("background-color: #8183A3;")
        sidebar_width = screen_geometry.width() // 5
        self.sidebar_widget.setFixedWidth(sidebar_width)
        # Ensure child elements handle overflow
        for label in self.sidebar_widget.findChildren(QLabel):
            label.setWordWrap(True)
            label.setStyleSheet("color: black; font-weight: bold; overflow: hidden; text-overflow: ellipsis;")
        content_layout.addWidget(self.sidebar_widget)

        # load command buttons into the sidebar
        self.command_buttons = {}
        try:
            self.load_command_buttons()
        except Exception:
            pass

        ### Footer Layout ###

        footer_layout = QVBoxLayout()
        self.footer_widget = QWidget()
        self.footer_widget.setLayout(footer_layout)
        self.footer_widget.setStyleSheet("background-color: #545780;")
        footer_height = screen_geometry.height() // 20
        self.footer_widget.setFixedHeight(footer_height)

        # Graphs layout

        self.graphs_widget = QWidget()
        graphs_layout = QVBoxLayout()
        self.graphs_widget.setLayout(graphs_layout)
        # GPS map may be optional; keep reference on self
        self.gps_map = None

        graphs_grid = QGridLayout()
        graphs_grid.setSpacing(2)
        graphs_grid.setContentsMargins(0, 0, 0, 0)
        graphs_layout.addLayout(graphs_grid)
        self.graphs_layout = graphs_layout
        self.graphs_layout.setSpacing(0)
        self.graphs_layout.setContentsMargins(0, 0, 0, 0)
        self.graphs_grid = graphs_grid
        self.graphs = {}  # name -> (graph_obj, container)
        self._graph_grid_pos = 0

        # If GPS preference enabled, create map and add its container into the grid
        if (self.data.getPreference("GPS")):
            self.graphs_widget.setStyleSheet("background-color: #e6e6e6;")
            self.gps_map = GPSMap()
            self.gps_map.location_updated.connect(self.gps_map.update_map)
            gps_container = QWidget()
            gps_layout = QVBoxLayout()
            gps_layout.setSpacing(0)
            gps_layout.setContentsMargins(0, 0, 0, 0)
            gps_container.setLayout(gps_layout)
            gps_layout.addWidget(self.gps_map.win)
            gps_container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            # store GPS as special entry so it will be laid out with equal spacing
            self.graphs['__GPS_MAP__'] = (None, gps_container)
            self._graph_grid_pos += 1
            try:
                self.rebuild_graph_grid()
                try:
                    self.gps_map.win.show()
                except Exception:
                    pass
            except Exception:
                pass
        content_layout.addWidget(self.graphs_widget)
        
        ### Main Content Layout ###

        main_layout.addLayout(content_layout)
        main_layout.addWidget(self.footer_widget)
        self.createMenubar()
    
    def change_serial_port(self):
        selected_port = self.serial_port_dropdown.currentText()
        if selected_port != self.comm.serial_port:
            self.comm.stop_communication()
            self.comm.serial_port = selected_port
            try:
                self.comm.ser = serial.Serial(selected_port, self.comm.baud_rate, timeout=self.comm.timeout)
                print(f"Serial port changed to {selected_port}")
                if self.reading_data:
                    self.comm.start_communication(None)
            except serial.SerialException as e:
                print(f"Failed to open serial port {selected_port}: {e}")
                self.comm.ser = None

    def update_serial_ports(self):
        current_port = self.serial_port_dropdown.currentText()
        available_ports = set(get_available_serial_ports())
        self.serial_port_dropdown.clear()
        self.serial_port_dropdown.addItems(available_ports)
        if current_port in available_ports:
            self.serial_port_dropdown.setCurrentText(current_port)
        else:
            self.comm.stop_communication()
            self.reading_data = False
            self.start_stop_button.setText("CXON")
        print("Serial ports updated.")

    def change_baud_rate(self):
        selected_baud_rate = int(self.baud_rate_dropdown.currentText())
        self.comm.change_baud_rate(selected_baud_rate)
        print(f"Baud rate changed to {selected_baud_rate}")

    def change_serial_port_dialog(self):
        """Open a dialog to let the user pick from available serial ports."""
        ports = list(get_available_serial_ports())
        if not ports:
            QMessageBox.information(self, "No ports", "No serial ports found.")
            return
        port, valid = QInputDialog.getItem(self, "Select serial port", "Serial port:", ports, 0, False)
        if valid and port:
            if port != self.comm.serial_port:
                self.comm.stop_communication()
                self.comm.serial_port = port
                try:
                    self.comm.ser = serial.Serial(port, self.comm.baud_rate, timeout=self.comm.timeout)
                    print(f"Serial port changed to {port}")
                    if getattr(self, 'reading_data', False):
                        self.comm.start_communication(None)
                except serial.SerialException as e:
                    QMessageBox.warning(self, "Serial Error", f"Failed to open serial port {port}: {e}")
                    self.comm.ser = None

    def change_baud_rate_dialog(self):
        """Open a dialog to let the user pick a baud rate."""
        baudrates = ["110", "300", "600", "1200", "2400", "4800", "9600", "19200", "38400", "57600", "115200"]
        current = str(self.comm.baud_rate) if hasattr(self, 'comm') else "115200"
        if current in baudrates:
            default_idx = baudrates.index(current)
        else:
            default_idx = 4
        baud, valid = QInputDialog.getItem(self, "Select baud rate", "Baud rate:", baudrates, default_idx, False)
        if valid and baud:
            selected_baud_rate = int(baud)
            self.comm.change_baud_rate(selected_baud_rate)
            print(f"Baud rate changed to {selected_baud_rate}")

    # Close Ground Station
    def closeEvent(self, event):
        event.accept()
    
    def createMenubar(self):
        menubar = self.menuBar()
        menubar.setStyleSheet(
            "QMenuBar { background-color: #545454; color: white; }"
            "QMenuBar::item { background-color: transparent; color: white; }"
            "QMenu { background-color: #545454; color: white; }"
            "QMenu::item:selected { background-color: #555555; }"
        )
        window_menu = menubar.addMenu("&Window")
        edit_menu = menubar.addMenu("&Edit")

        # Window menu actions
        fullscreen_action = QAction("Toggle Fullscreen", self)
        fullscreen_action.setShortcut("F11")
        fullscreen_action.triggered.connect(self.toggle_fullscreen)
        window_menu.addAction(fullscreen_action)

        exit_action = QAction("Exit", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        window_menu.addAction(exit_action)

        # Edit menu actions
        change_serial_action = QAction("Change Serial Port", self)
        change_serial_action.setShortcut("Ctrl+P")
        change_serial_action.triggered.connect(self.change_serial_port_dialog)
        edit_menu.addAction(change_serial_action)

        change_baud_action = QAction("Change Baud Rate", self)
        change_baud_action.setShortcut("Ctrl+B")
        change_baud_action.triggered.connect(self.change_baud_rate_dialog)
        edit_menu.addAction(change_baud_action)

        # View menu
        view_menu = menubar.addMenu("&View")

        manage_graphs_action = QAction("Manage Graphs...", self)
        manage_graphs_action.setShortcut("Ctrl+G")
        manage_graphs_action.triggered.connect(self.open_manage_graphs_dialog)
        view_menu.addAction(manage_graphs_action)

        toggle_gps_action = QAction("Toggle GPS Map", self)
        toggle_gps_action.setShortcut("Ctrl+M")
        toggle_gps_action.setCheckable(True)
        toggle_gps_action.setChecked(bool(self.gps_map))
        toggle_gps_action.triggered.connect(self.toggle_gps_map)
        view_menu.addAction(toggle_gps_action)
        
        # previously separate create/remove actions; merged into Manage Graphs

    def toggle_gps_map(self, checked: bool):
        if checked and self.gps_map is None:
            # create and add GPS map container into grid
            self.gps_map = GPSMap()
            self.gps_map.location_updated.connect(self.gps_map.update_map)
            gps_container = QWidget()
            gps_layout = QVBoxLayout()
            gps_layout.setSpacing(0)
            gps_layout.setContentsMargins(0, 0, 0, 0)
            gps_container.setLayout(gps_layout)
            gps_layout.addWidget(self.gps_map.win)
            gps_container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            self.graphs['__GPS_MAP__'] = (None, gps_container)
            self.rebuild_graph_grid()
            self.data.setPreference("GPS", True)
        elif not checked and self.gps_map is not None:
            # remove GPS map from grid and dict
            try:
                if '__GPS_MAP__' in self.graphs:
                    _, container = self.graphs['__GPS_MAP__']
                    self.remove_widget_from_layout(container, self.graphs_grid)
                    container.setParent(None)
                    del self.graphs['__GPS_MAP__']
                    self.rebuild_graph_grid()
            except Exception:
                pass
            try:
                self.gps_map.win.hide()
            except Exception:
                pass
            self.gps_map = None
            self.data.setPreference("GPS", False)

    def open_graph_selector(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Select telemetry fields to graph")
        # Dark dialog styling
        dialog.setStyleSheet("background-color: #2e2e2e; color: white;")
        layout = QVBoxLayout()

        list_widget = QListWidget()
        list_widget.setSelectionMode(QAbstractItemView.MultiSelection)
        list_widget.setStyleSheet("background-color: #3a3a3a; color: white; selection-background-color: #505050;")
        # Load telemetry fields via Data interface
        try:
            fields = self.data.getTelemetryFields() or {}
            # Only allow numeric fields (those with non-empty units)
            numeric_field_keys = [k for k, u in fields.items() if u]
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to load telemetry fields: {e}")
            return

        for k in sorted(numeric_field_keys):
            list_widget.addItem(k)

        layout.addWidget(list_widget)

        buttons_layout = QHBoxLayout()
        ok_btn = QPushButton("OK")
        cancel_btn = QPushButton("Cancel")
        ok_btn.setStyleSheet("background-color:#505050; color:white; padding:6px;")
        cancel_btn.setStyleSheet("background-color:#505050; color:white; padding:6px;")
        buttons_layout.addWidget(ok_btn)
        buttons_layout.addWidget(cancel_btn)
        layout.addLayout(buttons_layout)

        def on_ok():
            selected = [it.text() for it in list_widget.selectedItems()]
            dialog.accept()
            self.create_graphs_for_fields(selected, fields)

        ok_btn.clicked.connect(on_ok)
        cancel_btn.clicked.connect(dialog.reject)
        dialog.setLayout(layout)
        dialog.exec_()

    def open_remove_graph_dialog(self):
        if not self.graphs:
            msg = QMessageBox(self)
            msg.setIcon(QMessageBox.Information)
            msg.setWindowTitle("No graphs")
            msg.setText("There are no graphs to remove.")
            msg.setStyleSheet("background-color: #2e2e2e; color: white;")
            msg.exec_()
            return
        dialog = QDialog(self)
        dialog.setWindowTitle("Remove graphs")
        dialog.setStyleSheet("background-color: #2e2e2e; color: white;")
        layout = QVBoxLayout()

        list_widget = QListWidget()
        list_widget.setSelectionMode(QAbstractItemView.MultiSelection)
        list_widget.setStyleSheet("background-color: #3a3a3a; color: white; selection-background-color: #505050;")
        for name in sorted(self.graphs.keys()):
            list_widget.addItem(name)

        layout.addWidget(list_widget)

        buttons_layout = QHBoxLayout()
        ok_btn = QPushButton("Remove")
        cancel_btn = QPushButton("Cancel")
        ok_btn.setStyleSheet("background-color:#505050; color:white; padding:6px;")
        cancel_btn.setStyleSheet("background-color:#505050; color:white; padding:6px;")
        buttons_layout.addWidget(ok_btn)
        buttons_layout.addWidget(cancel_btn)
        layout.addLayout(buttons_layout)

        def on_remove():
            selected = [it.text() for it in list_widget.selectedItems()]
            dialog.accept()
            for n in selected:
                self.remove_graph(n)

        ok_btn.clicked.connect(on_remove)
        cancel_btn.clicked.connect(dialog.reject)
        dialog.setLayout(layout)
        dialog.exec_()

    def open_manage_graphs_dialog(self):
        """Merged create/remove dialog: checkbox list of telemetry fields."""
        dialog = QDialog(self)
        dialog.setWindowTitle("Manage telemetry graphs")
        dialog.setStyleSheet("background-color: #2e2e2e; color: white;")
        layout = QVBoxLayout()

        list_widget = QListWidget()
        list_widget.setStyleSheet("background-color: #3a3a3a; color: white; selection-background-color: #505050;")

        try:
            fields = self.data.getTelemetryFields() or {}
            numeric_field_keys = [k for k, u in fields.items() if u]
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to load telemetry fields: {e}")
            return

        # build a set representing currently selected field-names (expanding R/P/Y groups)
        current_selected = set()
        for gname, (gobj, _) in list(self.graphs.items()):
            if gname == '__GPS_MAP__':
                continue
            if isinstance(gobj, rpyGraph):
                current_selected.update({f"{gname}_R", f"{gname}_P", f"{gname}_Y"})
            else:
                current_selected.add(gname)

        # populate list with checkable items
        for k in sorted(numeric_field_keys):
            # create standard QListWidgetItem via addItem then fetch
            list_widget.addItem(k)
            it = list_widget.item(list_widget.count() - 1)
            it.setFlags(it.flags() | Qt.ItemIsUserCheckable)
            it.setCheckState(Qt.Checked if k in current_selected else Qt.Unchecked)

        layout.addWidget(list_widget)

        buttons_layout = QHBoxLayout()
        ok_btn = QPushButton("Apply")
        cancel_btn = QPushButton("Cancel")
        ok_btn.setStyleSheet("background-color:#505050; color:white; padding:6px;")
        cancel_btn.setStyleSheet("background-color:#505050; color:white; padding:6px;")
        buttons_layout.addWidget(ok_btn)
        buttons_layout.addWidget(cancel_btn)
        layout.addLayout(buttons_layout)

        def on_apply():
            # determine checked set
            checked = set()
            for i in range(list_widget.count()):
                it = list_widget.item(i)
                if it.checkState() == Qt.Checked:
                    checked.add(it.text())

            # compute current_selected again (fresh)
            current_selected_now = set()
            for gname, (gobj, _) in list(self.graphs.items()):
                if gname == '__GPS_MAP__':
                    continue
                if isinstance(gobj, rpyGraph):
                    current_selected_now.update({f"{gname}_R", f"{gname}_P", f"{gname}_Y"})
                else:
                    current_selected_now.add(gname)

            to_remove_fields = current_selected_now - checked
            to_create = checked - current_selected_now

            # translate to concrete graph names to remove
            remove_names = set()
            for f in to_remove_fields:
                if '_' in f:
                    prefix, suf = f.rsplit('_', 1)
                    if prefix in self.graphs and isinstance(self.graphs[prefix][0], rpyGraph):
                        remove_names.add(prefix)
                        continue
                if f in self.graphs:
                    remove_names.add(f)

            # perform removals first
            for name in list(remove_names):
                try:
                    self.remove_graph(name)
                except Exception:
                    pass

            # create new graphs for remaining checked fields
            if to_create:
                try:
                    self.create_graphs_for_fields(list(to_create), fields)
                except Exception:
                    pass

            dialog.accept()

        ok_btn.clicked.connect(on_apply)
        cancel_btn.clicked.connect(dialog.reject)
        dialog.setLayout(layout)
        dialog.exec_()

    def create_graphs_for_fields(self, selected_fields, fields_units):
        # Only consider numeric fields (those with units)
        numeric_keys = {k for k, u in (fields_units or {}).items() if u}
        selected = set(f for f in selected_fields if f in numeric_keys)
        # detect RPY groups (e.g., GYRO_R, GYRO_P, GYRO_Y)
        used = set()
        # simple grouping by prefix before last underscore
        prefixes = {}
        for name in list(selected):
            if '_' in name:
                prefix, suffix = name.rsplit('_', 1)
                prefixes.setdefault(prefix, set()).add(suffix)

        # create rpyGraph where R,P,Y all present
        for prefix, sufset in prefixes.items():
            if {'R', 'P', 'Y'}.issubset(sufset):
                # ensure the components are numeric
                if not (f"{prefix}_R" in numeric_keys and f"{prefix}_P" in numeric_keys and f"{prefix}_Y" in numeric_keys):
                    continue
                graph_name = prefix
                if graph_name in self.graphs:
                    used.update({f"{prefix}_R", f"{prefix}_P", f"{prefix}_Y"})
                    continue
                units = fields_units.get(prefix + '_R', '')
                if not units:
                    continue
                g = rpyGraph(graph_name, units)
                container = self.create_graph_container(graph_name, g)
                self.graphs[graph_name] = (g, container)
                self._graph_grid_pos += 1
                used.update({f"{prefix}_R", f"{prefix}_P", f"{prefix}_Y"})

        # remaining individual fields
        for name in selected_fields:
            if name in used:
                continue
            # skip if a graph with this key (or same name) already exists
            if name in self.graphs:
                continue
            units = fields_units.get(name, '')
            if not units:
                continue
            g = Graph(name, units)
            container = self.create_graph_container(name, g)
            self.graphs[name] = (g, container)
            self._graph_grid_pos += 1

        # rebuild grid to place new containers
        self.rebuild_graph_grid()

    def handle_telemetry(self, packet: dict):
        """Route a parsed telemetry `packet` (dict) into graphs and map."""
        if not isinstance(packet, dict):
            return

        # GPS
        try:
            lat = packet.get('GPS_LATITUDE')
            lon = packet.get('GPS_LONGITUDE')
            if lat is not None and lon is not None and self.gps_map:
                try:
                    self.gps_map.location_updated.emit(float(lat), float(lon))
                except Exception:
                    pass
        except Exception:
            pass

        # Route values to individual graphs or grouped RPY graphs
        for key, (gobj, container) in list(self.graphs.items()):
            try:
                if isinstance(gobj, rpyGraph):
                    r = packet.get(f"{key}_R")
                    p = packet.get(f"{key}_P")
                    y = packet.get(f"{key}_Y")
                    if r is None and p is None and y is None:
                        continue
                    try:
                        rr = float(r) if r is not None else 0.0
                        pp = float(p) if p is not None else 0.0
                        yy = float(y) if y is not None else 0.0
                        gobj.update(rr, pp, yy)
                    except Exception:
                        pass
                else:
                    val = packet.get(key)
                    if val is None:
                        continue
                    try:
                        gobj.update(float(val))
                    except Exception:
                        pass
            except Exception:
                continue

    def toggle_fullscreen(self):
        if self.isFullScreen():
            self.showNormal()
        else:
            self.showFullScreen()

    def reset_csv_action(self):
        """Reset the CSV file by clearing all data and writing headers only."""
        self.comm.reset_csv()
        print("CSV file has been reset.")

    def download_csv_action(self):
        """Open a file dialog and save the CSV file to the selected location."""
        destination_folder = QFileDialog.getExistingDirectory(self, "Select Destination Folder")
        if self.comm.copy_csv(destination_folder):
            print(f"CSV file has been downloaded to {destination_folder}")
        else:
            print("Failed to download CSV file.")

    def load_command_buttons(self):
        """Load commands from commands.json and create buttons in the sidebar."""
        # load commands via Data interface
        commands = self.data.getCommands() or {}

        # clear any existing buttons in the grid
        grid = self.buttons_grid
        # remove old widgets
        while grid.count():
            item = grid.takeAt(0)
            w = item.widget()
            if w is not None:
                w.setParent(None)

        # create buttons in a 3-column grid
        cols = 3
        idx = 0
        
        # Add default buttons
        default_buttons = {
            "Reset CSV": self.reset_csv_action,
            "Download CSV": self.download_csv_action
        }
        
        for name, action in default_buttons.items():
            btn = QPushButton(name)
            btn.setStyleSheet('background-color:#505050; color:white; padding:6px;')
            btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
            btn.clicked.connect(action)
            row = idx // cols
            col = idx % cols
            grid.addWidget(btn, row, col)
            grid.setColumnStretch(col, 1)
            self.command_buttons[name] = btn
            idx += 1
        
        for name, cmd in commands.items():
            btn = QPushButton(name)
            btn.setStyleSheet('background-color:#505050; color:white; padding:6px;')
            btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
            def make_send(c):
                return lambda: self.comm.send_command(c)
            btn.clicked.connect(make_send(cmd))
            row = idx // cols
            col = idx % cols
            grid.addWidget(btn, row, col)
            # set column stretch so buttons expand evenly
            grid.setColumnStretch(col, 1)
            self.command_buttons[name] = btn
            idx += 1

    def create_graph_container(self, name: str, graph_obj):
        """Create a container widget that holds only the graph widget."""
        container = QWidget()
        v = QVBoxLayout()
        v.setSpacing(0)
        v.setContentsMargins(0, 0, 0, 0)
        container.setLayout(v)

        # ensure graph widget and container expand to fill grid cell
        try:
            graph_obj.win.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        except Exception:
            pass

        # add only the graph widget (no header)
        v.addWidget(graph_obj.win)
        return container

    def remove_graph(self, name: str):
        entry = self.graphs.get(name)
        if not entry:
            return
        graph_obj, container = entry
        try:
            graph_obj.close()
        except Exception:
            pass
        # remove container from grid layout
        self.remove_widget_from_layout(container, self.graphs_grid)
        # delete container
        container.setParent(None)
        # remove from dict
        del self.graphs[name]
        # rebuild grid to compact layout
        self.rebuild_graph_grid()

    def remove_widget_from_layout(self, widget, layout):
        for i in range(layout.count()):
            item = layout.itemAt(i)
            if item is None:
                continue
            w = item.widget()
            if w is widget:
                # remove and delete
                item.widget().setParent(None)
                return

    def rebuild_graph_grid(self):
        # clear all items from the grid
        layout = self.graphs_grid
        # remove widgets
        while layout.count():
            item = layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.setParent(None)

        # re-add containers from self.graphs in insertion order
        idx = 0
        total = len(self.graphs)
        
        # Dynamic column layout: 1 item = 1 col (full width), 2+ items = 2 cols
        cols = 1 if total == 1 else 2
        rows = (total + cols - 1) // cols if total > 0 else 0

        # clear old column/row stretches first
        for c in range(10):
            layout.setColumnStretch(c, 0)
        for r in range(10):
            layout.setRowStretch(r, 0)

        # set equal stretch for rows and columns
        for c in range(cols):
            layout.setColumnStretch(c, 1)
        for r in range(rows):
            layout.setRowStretch(r, 1)

        for name, (g, container) in list(self.graphs.items()):
            row = idx // cols
            col = idx % cols
            try:
                container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            except Exception:
                pass
            layout.addWidget(container, row, col)
            idx += 1
        self._graph_grid_pos = idx

# Run the application
if __name__ == "__main__":
    app = QApplication(sys.argv)

    main_window = GroundStation()
    main_window.show()

    sys.exit(app.exec_())