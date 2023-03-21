from functools import partial
from typing import List
import numpy as np
import os
import pandas as pd
import sys
try:
    from OpenGL.GL import *
    import pyqtgraph.opengl as gl
    from pyqtgraph import PlotDataItem, PlotWidget, mkPen, Vector
    from pyqtgraph.opengl.GLGraphicsItem import GLGraphicsItem
    from PyQt5 import QtWidgets, QtCore, QtGui
    from PyQt5.QtGui import QColor
    from PyQt5.QtCore import QUrl, pyqtSlot, pyqtSignal
    from PyQt5.QtQuick import QQuickView
    from PyQt5.QtWidgets import QCheckBox, QDialog, QVBoxLayout, QHBoxLayout, QPushButton

    qt_imported = True
except ModuleNotFoundError:
    qt_imported = False

from dataclasses import dataclass, field

@dataclass
class Points:
    x: List[float] = field(default_factory=lambda: [])
    y: List = field(default_factory=lambda: [])

@dataclass
class Figure:
    check_box: QCheckBox
    line: gl.GLLinePlotItem
    data: Points = Points()

COLORS = ["orange", "green", "blue", "red", "aqua", "orange", "hotpink", "springgreen",
          "blueviolet", "orangered", "royalblue", "green", "plum", "paleturquoise", "palegreen", "navy", "turquoise",
          "mediumvioletred", "darkgoldenrod", "fuchsia", "steelblue", "lightcoral", "thistle", "khaki", "chartreuse",
          "teal", "saddlebrown", "violet", "lemonchiffon", "olive", "yellow", "lightslategray"]

def find_file_name(file_path):
    last_sep = file_path.rfind("/")
    last_dot = file_path.rfind(".")
    return f"{file_path[last_sep + 1:last_dot]}"


class MyGLGridItem(gl.GLGridItem):
    def __init__(self, high = None):
        super().__init__()
        self.setGLOptions('translucent')
        self.setColor((195, 195, 195))
        self.high = high
        self.current_scale = 5.0
        self.setSize(self.high, self.high, 0)
        self.antialias = True
        self.scale(self.current_scale, self.current_scale, 0)

    def setScale(self, scale = 1.0):
        self.current_scale = scale
        self.high = self.high // self.current_scale
        if (self.high % 2) != 0:
            self.high += 1
        self.setSize(self.high, self.high, 0)
        self.scale(self.current_scale, self.current_scale, 0)
        self.update()

    def doubleUpSpacing(self):
        self.setScale(2)

    def doubleDownSpacing(self):
        self.setScale(0.5)


class MyGLViewWidget(gl.GLViewWidget):
    def __init__(self, axis_length):
        super().__init__()
        self._down_pos = None
        self._prev_zoom_pos = None
        self._prev_pan_pos = None
        self.scale_iterator = 0

        self.grid = MyGLGridItem(4 * axis_length)

    def mousePressEvent(self, ev):
        super(MyGLViewWidget, self).mousePressEvent(ev)
        self._down_pos = self.mousePos

    def mouseReleaseEvent(self, ev):
        super(MyGLViewWidget, self).mouseReleaseEvent(ev)
        if self._down_pos == ev.pos():
            if ev.button() == 1:
                x = ev.pos().x() - self.width() / 2
                y = ev.pos().y() - self.height() / 2
                self.pan(-x, -y, 0, relative=True)
        self._prev_zoom_pos = None
        self._prev_pan_pos = None

    def mouseMoveEvent(self, ev):
        pos = ev.pos().x(), ev.pos().y()
        if not hasattr(self, '_prev_pan_pos') or not self._prev_pan_pos:
            self._prev_pan_pos = pos
            return
        dx = pos[0] - self._prev_pan_pos[0]
        dy = pos[1] - self._prev_pan_pos[1]
        self.pan(dx, dy, 0, relative="view")
        self._prev_pan_pos = pos

    def wheelEvent(self, ev):
        delta = ev.angleDelta().x()
        if delta == 0:
            delta = ev.angleDelta().y()
        if ev.modifiers() & QtCore.Qt.KeyboardModifier.ControlModifier:
            self.opts['fov'] *= 0.999**delta
        else:
            if delta > 0:
                self.scale_iterator += 1
            else:
                self.scale_iterator -= 1

            if self.scale_iterator == 5:
                self.grid.doubleDownSpacing()
                self.scale_iterator = 0
            elif self.scale_iterator == -5:
                self.grid.doubleUpSpacing()
                self.scale_iterator = 0

            self.opts['distance'] *= 0.999**delta
        self.update()


class Graphic3D(QDialog):
    def __init__(self, path: str):
        super().__init__()
        QDialog.__init__(self)
        self.window_width = 1500
        self.window_height = 1000
        self.caption = f"{find_file_name(path)} осциллограмма"
        self.resize(self.window_width, self.window_height)
        self.setWindowTitle(self.caption)

        self.figures = {}
        layout_v = QVBoxLayout()

        # Import data from .csv
        _, file_extension = os.path.splitext(path)
        data = None
        if file_extension == '.csv':
            data = pd.read_csv(filepath_or_buffer=path, sep=';', header=None)
        elif file_extension == '.xlsx':
            data = pd.read_excel(io=path)

        channels = data.columns.tolist()[-1] + 1
        values_number = data.index.tolist()[-1] + 1
        x_max = max(data.iloc[:, 0].values.tolist())
        y_max = values_number
        self.lines = []

        # Add lines and buttons
        for i in range(channels):
            key = f'channel_{i + 1}'
            color = COLORS[i]

            # Setting up buttons
            current_button = QCheckBox(f"{key}")
            current_button.setChecked(True)
            current_style = "QCheckBox::indicator:checked {background-color: " + color + ";}"
            current_button.setStyleSheet(current_style)
            current_button.clicked.connect(partial(self.press_check_box, key))

            # Getting channel data
            channel_data = data.iloc[:, i].values.tolist()
            channel_x_max = max(channel_data)
            x_max = max(x_max, channel_x_max)
            dots = []
            for dot in range(len(channel_data)):
                dots.append((channel_data[dot], dot, 0))

            # Adding points
            dots_array = np.array(dots)
            line = gl.GLLinePlotItem(pos = dots_array, width = 3, antialias = False, glOptions='translucent', color = color)
            self.lines.append(line)
            self.figures[key] = Figure(check_box=current_button, line=line, data=Points())

            layout_v.addWidget(current_button)

        # Setting up axis
        axis_length = 2 * max(x_max, y_max)
        axis_y_values = np.array([[-axis_length, 0, 0], [axis_length, 0, 0]])
        axis_x_values = np.array([[0, -axis_length, 0], [0, axis_length, 0]])
        axis_y = gl.GLLinePlotItem(pos=axis_y_values, width=1, antialias=False, glOptions='translucent', color="black")
        axis_x = gl.GLLinePlotItem(pos=axis_x_values, width=1, antialias=False, glOptions='translucent', color="black")

        self.graphic_widget = MyGLViewWidget(axis_length = 4 * axis_length)
        self.graphic_widget.setBackgroundColor("w")

        for l in  self.lines:
            self.graphic_widget.addItem(l)

        # Setting up view point
        self.graphic_widget.opts["center"] = Vector(x_max / 2, y_max / 2, 0)
        distance = max(x_max * 2, y_max * 2)
        self.graphic_widget.setCameraPosition(distance = distance, elevation = -90, azimuth = 0)

        # Add axis
        self.graphic_widget.addItem(axis_x)
        self.graphic_widget.addItem(axis_y)

        self.graphic_widget.addItem(self.graphic_widget.grid)


        false_all = QPushButton('Снять все')
        false_all.clicked.connect(self.change_all_check_boxes_false)
        true_all = QPushButton('Поставить все')
        true_all.clicked.connect(self.change_all_check_boxes_true)
        layout_v.addWidget(true_all)
        layout_v.addWidget(false_all)

        layout_h = QHBoxLayout()
        layout_h.addWidget(self.graphic_widget, 9)
        layout_h.addLayout(layout_v, 1)
        self.setLayout(layout_h)
        self.show()

    def press_check_box(self, name):
        if self.figures[name].check_box.isChecked():
            self.graphic_widget.addItem(self.figures[name].line)
        else:
            self.graphic_widget.removeItem(self.figures[name].line)


    def change_all_check_boxes_true(self):
        self.change_all_check_boxes(True)

    def change_all_check_boxes_false(self):
        self.change_all_check_boxes(False)

    def change_all_check_boxes(self, is_check: bool):
        for name in self.figures.keys():
            state = self.figures[name].check_box.isChecked()
            if state != is_check:
                self.figures[name].check_box.click()



if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)
    g = Graphic3D(path='small_test.csv')
    sys.exit(app.exec_())
