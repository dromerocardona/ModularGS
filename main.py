import sys
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QLabel, QVBoxLayout,
    QHBoxLayout, QPushButton, QComboBox, QGroupBox, QGridLayout, QSpacerItem,
    QSizePolicy, QToolBar, QAction, QFileDialog, QInputDialog, QMessageBox)
from PyQt5.QtGui import QIcon
from PyQt5.QtGui import QFont, QPixmap
from PyQt5.QtCore import Qt, QObject, pyqtSignal
from communication import Communication
from serial.tools import list_ports
from typing import Iterable
from map import GPSMap
from data import Data
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
        self.setStyleSheet("background-color: #b0aee7;")
        self.showMaximized()
        screen_geometry = QApplication.desktop().screenGeometry()

        self.data = Data() # Get preferences and other data
        self.comm = Communication(self.data.getPreference("port")) # Initialize communication

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
        main_layout.addWidget(header_widget)

        content_layout = QHBoxLayout()

        ### Sidebar Layout ###

        sidebar_layout = QVBoxLayout()
        sidebar_layout.setAlignment(Qt.AlignTop)
        sidebar_layout.setSpacing(10)
        sidebar_layout.addItem(QSpacerItem(10, 10))
        sidebar_groupbox = QGroupBox("")
        sidebar_groupbox.setStyleSheet("background-color: #d1d1f0;")
        sidebar_groupbox.setStyleSheet("QGroupBox { background-color: #d1d1f0; border: 1px solid black; }")
        sidebar_groupbox_layout = QVBoxLayout()
        sidebar_groupbox.setLayout(sidebar_groupbox_layout)
        buttons_grid = QGridLayout()
        buttons_grid.setAlignment(Qt.AlignCenter)
        sidebar_layout.addWidget(sidebar_groupbox)
        buttons_widget = QWidget()
        buttons_widget.setLayout(buttons_grid)
        sidebar_layout.addWidget(buttons_widget)
        self.sidebar_widget = QWidget()
        self.sidebar_widget.setLayout(sidebar_layout)
        self.sidebar_widget.setStyleSheet("background-color: #e9eeff;")
        sidebar_width = screen_geometry.width() // 5
        self.sidebar_widget.setFixedWidth(sidebar_width)
        # Ensure child elements handle overflow
        for label in self.sidebar_widget.findChildren(QLabel):
            label.setWordWrap(True)
            label.setStyleSheet("color: black; font-weight: bold; overflow: hidden; text-overflow: ellipsis;")
        content_layout.addWidget(self.sidebar_widget)

        ### Footer Layout ###

        footer_layout = QVBoxLayout()
        self.footer_widget = QWidget()
        self.footer_widget.setLayout(footer_layout)
        self.footer_widget.setStyleSheet("background-color: #a7cbf5;")
        footer_height = screen_geometry.height() // 20
        self.footer_widget.setFixedHeight(footer_height)

        # Graphs layout

        self.graphs_widget = QWidget()
        graphs_layout = QVBoxLayout()
        self.graphs_widget.setLayout(graphs_layout)
        if (self.data.getPreference("GPS")):
            self.graphs_widget.setStyleSheet("background-color: #e6e6e6;")
            map = GPSMap()
            map.location_updated.connect(map.update_map)
        graphs_layout.addWidget(map.win)
        graphs_grid = QGridLayout()
        graphs_layout.addLayout(graphs_grid)
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
                    self.comm.start_communication(self.signal_emitter)
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
                        self.comm.start_communication(self.signal_emitter)
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
            "QMenuBar { background-color: #777777; color: white; }"
            "QMenuBar::item { background-color: transparent; color: white; }"
            "QMenu { background-color: #777777; color: white; }"
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
    
    def setupShortcuts(self):
        pass

    def toggle_fullscreen(self):
        if self.isFullScreen():
            self.showNormal()
        else:
            self.showFullScreen()

# Run the application
if __name__ == "__main__":
    app = QApplication(sys.argv)

    main_window = GroundStation()
    main_window.show()

    sys.exit(app.exec_())