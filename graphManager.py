import sys
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QGridLayout, QSizePolicy
from PyQt5.QtCore import QObject, pyqtSignal
from graph import Graph, rpyGraph
from collections import deque
import logging

# Configure logging for the module
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class GraphManager(QObject):
    graphs_changed = pyqtSignal()  # Emitted when graphs are added/removed/relaid out

    def __init__(self, grid_layout, telemetry_fields):
        super().__init__()
        self.grid = grid_layout
        self.telemetry_fields = telemetry_fields  # Dict of field: units for graph creation
        self.graphs = {}  # name: (graph_obj, container)
        self._max_data_points = 1000  # Configurable buffer size for graphs

    def create_graphs_for_fields(self, fields: list[str]):
        for field in fields:
            if field in self.graphs:
                logging.warning(f"Graph for {field} already exists; skipping.")
                continue

            units = self.telemetry_fields.get(field, "")
            is_rpy = self._is_rpy_field(field)
            if is_rpy:
                # Create rpyGraph for roll/pitch/yaw triplet
                graph_obj = rpyGraph(field, units)
                # Update with triplet
                graph_obj.update = lambda r, p, y: graph_obj.update(r, p, y)  # Bind for main.py calls
            else:
                graph_obj = Graph(field, units)

            # Limit data buffer
            self._configure_buffer(graph_obj)

            container = self._create_graph_container(graph_obj)
            self.graphs[field] = (graph_obj, container)
            self._add_to_grid(container)

        self.rebuild_layout()
        self.graphs_changed.emit()
        logging.info(f"Created {len(fields)} graphs.")

    def is_rpy_field(self, field: str) -> bool:
        return any(axis in field for axis in ['_R', '_P', '_Y']) and field in self.telemetry_fields

    def configure_buffer(self, graph_obj):
        if hasattr(graph_obj, 'data'):
            graph_obj.data = deque(maxlen=self._max_data_points)
        if hasattr(graph_obj, 'timestamps'):
            graph_obj.timestamps = deque(maxlen=self._max_data_points)
        if hasattr(graph_obj, 'data_r'):
            graph_obj.data_r = deque(maxlen=self._max_data_points)
            graph_obj.data_p = deque(maxlen=self._max_data_points)
            graph_obj.data_y = deque(maxlen=self._max_data_points)

    def create_graph_container(self, graph_obj):
        container = QWidget()
        layout = QVBoxLayout()
        layout.setSpacing(0)
        layout.setContentsMargins(0, 0, 0, 0)
        container.setLayout(layout)
        graph_obj.win.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        layout.addWidget(graph_obj.win)
        return container

    def remove_graph(self, name: str):
        if name not in self.graphs:
            logging.warning(f"No graph named {name} to remove.")
            return
        graph_obj, container = self.graphs.pop(name)
        try:
            graph_obj.close()
        except Exception as e:
            logging.error(f"Error closing graph {name}: {e}")
        self._remove_from_grid(container)
        self.rebuild_layout()
        self.graphs_changed.emit()
        logging.info(f"Removed graph: {name}")

    def clear_all_graphs(self):
        for name in list(self.graphs.keys()):
            self.remove_graph(name)

    def add_to_grid(self, container):
        # For incremental adds, but we rebuild anyway
        pass

    def remove_from_grid(self, widget):
        for i in range(self.grid.count()):
            item = self.grid.itemAt(i)
            if item and item.widget() == widget:
                widget.setParent(None)
                break

    def rebuild_layout(self):
        # Clear grid
        while self.grid.count():
            item = self.grid.takeAt(0)
            if item.widget():
                item.widget().setParent(None)

        total = len(self.graphs)
        if total == 0:
            return

        # Dynamic cols: 1 for single, 2 for multiples
        cols = 1 if total == 1 else 2
        rows = (total + cols - 1) // cols

        # Reset stretches
        for i in range(10):
            self.grid.setColumnStretch(i, 0)
            self.grid.setRowStretch(i, 0)

        # Set equal stretches
        for c in range(cols):
            self.grid.setColumnStretch(c, 1)
        for r in range(rows):
            self.grid.setRowStretch(r, 1)

        # Repopulate in insertion order
        idx = 0
        for name, (g, container) in self.graphs.items():
            row = idx // cols
            col = idx % cols
            self.grid.addWidget(container, row, col)
            idx += 1