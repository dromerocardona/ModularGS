import sys
import time
from PyQt5 import QtCore, QtWidgets
import pyqtgraph as pg

class Graph(QtCore.QObject):
    newData = QtCore.pyqtSignal(float, float) # value, timestamp

    def __init__(self, name: str, units: str):
        super().__init__()
        self.name = name
        self.units = units
        pg.setConfigOption('background', 'w')
        pg.setConfigOption('foreground', 'k')
        self.app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)
        self.win = pg.PlotWidget(title=name)
        self.win.setStyleSheet("border: 1px solid black;")
        self.plot = self.win

        self._pen_light = pg.mkPen(color='#1e8d12', width=3)
        self._pen_dark  = pg.mkPen(color='#00ff00', width=3)
        self.curve = self.plot.plot(
            pen=self._pen_light,
            symbol='o', symbolSize=8, symbolBrush='#1e8d12'
        )

        self.data = []
        self.timestamps = []
        self.start_time = time.time()

        self.plot.setLabel('left', name, units)
        self.plot.setLabel('bottom', 'Time (s)')
        self.plot.setYRange(0, 600)

        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self._update_gui)
        self.timer.start(50)

        self.newData.connect(self._handle_data)

    def update(self, value: float, timestamp: float | None = None):
        if timestamp is None:
            timestamp = time.time()
        self.newData.emit(value, timestamp)

    def show(self):
        self.win.show()

    def close(self):
        self.timer.stop()
        self.win.close()

    def reset(self):
        self.data.clear()
        self.timestamps.clear()
        self.start_time = time.time()

    def toggle_dark_mode(self, enabled: bool):
        if enabled:
            self.win.setBackground('#2e2f30')
            fg = 'w'
            curve_pen = self._pen_dark
            curve_brush = '#00ff00'
        else:
            self.win.setBackground('w')
            fg = 'k'
            curve_pen = self._pen_light
            curve_brush = '#1e8d12'

        pg.setConfigOption('foreground', fg)
        self.curve.setPen(curve_pen)
        self.curve.setSymbolBrush(curve_brush)

        for axis in ('left', 'bottom'):
            a = self.plot.getAxis(axis)
            a.setPen(fg)
            a.setTextPen(fg)

        self.plot.setTitle(self.name, color=fg)

    @QtCore.pyqtSlot(float, float)
    def _handle_data(self, value: float, timestamp: float):
        elapsed = timestamp - self.start_time
        self.data.append(value)
        self.timestamps.append(elapsed)

        self.data = self.data[-100:]
        self.timestamps = self.timestamps[-100:]

    def _update_gui(self):
        if not self.timestamps:
            return
        self.curve.setData(self.timestamps, self.data)
        if len(self.timestamps) > 1:
            self.plot.setXRange(self.timestamps[0], self.timestamps[-1], padding=0.05)

class rpyGraph(Graph):
    newRPY = QtCore.pyqtSignal(float, float, float, float) # r, p, y, timestamp

    def __init__(self, name: str, units: str):
        super().__init__(name, units)

        self.plot.removeItem(self.curve)
        self.plot.addLegend()

        self.curve_r = self.plot.plot(
            pen=pg.mkPen('r', width=3), name=f"{name}_R",
            symbol='o', symbolSize=8, symbolBrush='r'
        )
        self.curve_p = self.plot.plot(
            pen=pg.mkPen('#1e8d12', width=3), name=f"{name}_P",
            symbol='o', symbolSize=8, symbolBrush='#1e8d12'
        )
        self.curve_y = self.plot.plot(
            pen=pg.mkPen('b', width=3), name=f"{name}_Y",
            symbol='o', symbolSize=8, symbolBrush='b'
        )

        # Dark mode pens/brushes
        self._pen_r_dark = pg.mkPen('#ff5555', width=3)
        self._pen_p_dark = pg.mkPen('#55ff55', width=3)
        self._pen_y_dark = pg.mkPen('#5555ff', width=3)

        self.data_r = []
        self.data_p = []
        self.data_y = []

        self.plot.setYRange(-30, 30)
        self.newRPY.connect(self._handle_rpy)

    def update(self, r: float, p: float, y: float, timestamp: float | None = None):
        """Push a new (R, P, Y) sample."""
        if timestamp is None:
            timestamp = time.time()
        self.newRPY.emit(r, p, y, timestamp)

    def reset(self):
        super().reset()
        self.data_r.clear()
        self.data_p.clear()
        self.data_y.clear()

    def toggle_dark_mode(self, enabled: bool):
        super().toggle_dark_mode(enabled)

        if enabled:
            self.curve_r.setPen(self._pen_r_dark)
            self.curve_r.setSymbolBrush('#ff5555')
            self.curve_p.setPen(self._pen_p_dark)
            self.curve_p.setSymbolBrush('#55ff55')
            self.curve_y.setPen(self._pen_y_dark)
            self.curve_y.setSymbolBrush('#5555ff')
        else:
            self.curve_r.setPen(pg.mkPen('r', width=3))
            self.curve_r.setSymbolBrush('r')
            self.curve_p.setPen(pg.mkPen('#1e8d12', width=3))
            self.curve_p.setSymbolBrush('#1e8d12')
            self.curve_y.setPen(pg.mkPen('b', width=3))
            self.curve_y.setSymbolBrush('b')

    @QtCore.pyqtSlot(float, float, float, float)
    def _handle_rpy(self, r: float, p: float, y: float, ts: float):
        elapsed = ts - self.start_time
        self.data_r.append(r)
        self.data_p.append(p)
        self.data_y.append(y)
        self.timestamps.append(elapsed)

        self.data_r = self.data_r[-100:]
        self.data_p = self.data_p[-100:]
        self.data_y = self.data_y[-100:]
        self.timestamps = self.timestamps[-100:]

    def _update_gui(self):
        if not self.timestamps:
            return
        self.curve_r.setData(self.timestamps, self.data_r)
        self.curve_p.setData(self.timestamps, self.data_p)
        self.curve_y.setData(self.timestamps, self.data_y)
        if len(self.timestamps) > 1:
            self.plot.setXRange(self.timestamps[0], self.timestamps[-1], padding=0.05)