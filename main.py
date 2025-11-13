import sys
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QLabel, QVBoxLayout,
    QHBoxLayout, QPushButton, QComboBox, QGroupBox, QGridLayout, QSpacerItem,
    QSizePolicy, QToolBar, QAction, QFileDialog)
from PyQt5.QtGui import QIcon
from PyQt5.QtGui import QFont, QPixmap
from PyQt5.QtCore import Qt, QObject, pyqtSignal
from communication import Communication
from serial.tools import list_ports
from typing import Iterable
from map import GPSMap

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

        self.comm = Communication("COM4") # Initialize communication

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
        self.createToolbars()

    # Close Ground Station
    def closeEvent(self, event):
        event.accept()
    
    def createToolbars(self):
        main_toolbar = QToolBar("Main Toolbar")
        main_toolbar.setStyleSheet("background-color: #777777;")
        self.addToolBar(main_toolbar)
    
    def setupShortcuts(self):
        pass

# Run the application
if __name__ == "__main__":
    app = QApplication(sys.argv)

    main_window = GroundStation()
    main_window.show()

    sys.exit(app.exec_())