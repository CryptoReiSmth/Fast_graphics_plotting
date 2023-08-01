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
    from PyQt5.QtGui import QColor, QFont, QVector3D
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
    """ Определяет имя файла.
    :param file_path: Абсолютный путь к файлу.
    :return: Имя файла с расширением."""
    last_sep = file_path.rfind("/")
    last_dot = file_path.rfind(".")
    return f"{file_path[last_sep + 1:last_dot]}"


# Effort of converting into list
#
# def parse_file_data(file_data):
#     return file_data
#
# def parse_file_path(file_path):
#     _, file_extension = os.path.splitext(file_path)
#     data = None
#     if file_extension == '.csv':
#         data = pd.read_csv(filepath_or_buffer=file_path, sep=';', header=None)
#     elif file_extension == '.xlsx':
#         data = pd.read_excel(io=file_path)
#
#     channels = data.columns.tolist()[-1] + 1
#     values_number = data.index.tolist()[-1] + 1
#     parsed_data = []
#
#     for line in range(channels):
#         parsed_data.append([])
#         for value in range(values_number):
#             parsed_data[line].append(data[line][value])
#     return parsed_data


class AxisValuesItem:
    """ Класс, хранящий и создающий подписи для координатных осей. """
    def __init__(self, axis_length, experiment_time = 1):
        """ :param axis_length: длина оси
        :param experiment_time: длительность эксперимента в секундах (aka максимальное значение по оси x) """
        super().__init__()
        self.font = QFont('Helvetica', 10)
        # Задаём начальные значения размера и масштаба
        self.coordinate_dots = []
        self.current_width = axis_length // 4
        self.current_spacing = self.current_width // 20

        # Задаём максимальное значение осей и длину максимального числа
        self.max_x_value = experiment_time
        self.max_y_value = self.current_width
        self.max_digits_number = len(str(self.max_y_value))

        self.setUpTextItems()

    def setUpTextItems(self):
        """ Заполняет массив точек self.coordinate_dots текстовыми объектами
        gl.GLTextItem с текстом и расположением соответствующими точке
        координатной оси. Отсчет начинается с 0 и идёт с шагом step. """
        self.coordinate_dots = []
        current_x_value = 0
        step = self.max_x_value / 20
        for dot in range(1, self.current_width + 1, self.current_spacing):
            current_x_value += step
            current_y_value = dot

            x_dot_pos = gl.GLTextItem(color="black", pos=(-3.0, dot, 0), text=f"{current_x_value:.2f}", font=self.font)
            y_dot_pos = gl.GLTextItem(color="black", pos=(current_y_value, -2.0 * self.max_digits_number, 0), text=f"{current_y_value}", font=self.font)

            #print(f"dot = {dot}, current_x_value = {current_x_value}")

            self.coordinate_dots.append(x_dot_pos)
            self.coordinate_dots.append(y_dot_pos)

    def doubleUpTextSpacing(self):
        """ Увеличивает масштаб в 2 раза. """
        self.current_spacing *= 2
        self.setUpTextItems()

    def doubleDownTextSpacing(self):
        """ Уменьшает масштаб в 2 раза, если после уменьшения он не станет меньше 1. """
        self.current_spacing //= 2
        if self.current_spacing == 0:
            self.current_spacing = 1
        self.setUpTextItems()

class GridItem:
    """ Класс, представляющий квадратную координатную сетку."""
    def __init__(self, length = 0):
        """Задаёт начальные данные сетки.
        :param length: длина ребра квадрата сетки."""
        self.color = QColor(195, 195, 195)
        self.grid_lines = None
        self.x_lines_list = []
        self.y_lines_list = []
        self.length = length + 1
        print(f"grid: self.length = {self.length}")

        #TODO: потенциально улучшить
        self.starting_spacing = length // 40
        self.spacing = length // 40
        # Переменная, необходимая в функции wheelEvent() класса MyGLViewWidget
        self.set_minimum_spacing = False

        self.setSpacing(self.spacing)

    def setSpacing(self, spacing = 1):
        """ Изменяет масштаб сетки.
        :param spacing: необходимый масштаб"""
        self.x_lines_list = []
        self.y_lines_list = []
        for current_y in range(spacing, self.length, spacing):
            x_line_dots = np.array([(0, current_y, 0), (self.length, current_y, 0)])
            line = gl.GLLinePlotItem(pos=x_line_dots, width=1, antialias=False, glOptions='translucent', color=self.color)
            self.x_lines_list.append(line)

        for current_x in range(spacing, self.length, spacing):
            y_line_dots = np.array([(current_x, 0, 0), (current_x, self.length, 0)])
            line = gl.GLLinePlotItem(pos=y_line_dots, width=1, antialias=False, glOptions='translucent', color=self.color)
            self.y_lines_list.append(line)
        self.grid_lines = self.x_lines_list + self.y_lines_list

    def doubleUpGridSpacing(self):
        """ Увеличивает масштаб сетки в 2 раза, если он не превысит первоначальный
        (при котором полностью виден весь график)."""
        if self.spacing > self.starting_spacing:
            self.spacing = self.starting_spacing
        self.spacing *= 2
        self.setSpacing(self.spacing)
        # print("UP")

    def doubleDownGridSpacing(self):
        """Уменьшает масштаб сетки в 2 раза, если он не станет меньше 1."""
        self.spacing //= 2
        if self.spacing == 0:
            self.spacing = 1
        if self.spacing == 1:
            self.set_minimum_spacing = True
        self.setSpacing(self.spacing)
        # print("DOWN")
    def getGrid(self):
        """Возвращает сетку.
        :return: массив линий, образующих сетку."""
        return self.grid_lines


class MyGLViewWidget(gl.GLViewWidget):
    def __init__(self, axis_length, experiment_time):
        print(f"Graphic axis_length = {axis_length}")
        super().__init__()
        self._down_pos = None
        self._prev_zoom_pos = None
        self._prev_pan_pos = None
        self.scale_iterator = 0
        self.grid = GridItem(length=axis_length//4)
        self.addGrid()
        self.axis_values = AxisValuesItem(axis_length=axis_length, experiment_time=experiment_time)
        self.addAxisValues()

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

            #print(f"spacing = {self.grid.spacing}, scale_iterator = {self.scale_iterator}, set_minimum = {self.grid.set_minimum_spacing}")

            if self.scale_iterator == 5:
                self.doubleDownGrid()
                self.doubleDownTextValues()
                self.scale_iterator = -4

            elif self.scale_iterator == -5:
                self.doubleUpGrid()
                self.doubleUpTextValues()
                self.scale_iterator = 4

            if delta > 0:
                self.scale_iterator += 1
            else:
                self.scale_iterator -= 1

            if self.grid.set_minimum_spacing:
                self.scale_iterator = -5
                self.grid.set_minimum_spacing = False

            #
            # if delta > 0:
            #     if self.scale_iterator == 5:
            #         self.doubleDownGrid()
            #         self.doubleDownTextValues()
            #         self.scale_iterator = 0
            #     else:
            #         self.scale_iterator += 1
            # else:
            #     if self.scale_iterator == 0:
            #         self.doubleUpGrid()
            #         self.doubleUpTextValues()
            #         self.scale_iterator = 0
            #     else:
            #         self.scale_iterator -= 1

            self.opts['distance'] *= 0.999**delta
        self.update()

    def addGrid(self):
        for line in self.grid.getGrid():
            self.addItem(line)

    def removeGrid(self):
        for line in self.grid.getGrid():
            self.removeItem(line)
    def doubleUpGrid(self):
        self.removeGrid()
        self.grid.doubleUpGridSpacing()
        self.addGrid()
        self.scale_iterator = 0

    def doubleDownGrid(self):
        #print(f"set_minimum = {self.grid.set_minimum_spacing}")
        self.removeGrid()
        self.grid.doubleDownGridSpacing()
        self.addGrid()
        self.scale_iterator = 0

    def doubleUpTextValues(self):
        self.removeAxisValues()
        self.axis_values.doubleUpTextSpacing()
        self.addAxisValues()

    def doubleDownTextValues(self):
        self.removeAxisValues()
        self.axis_values.doubleDownTextSpacing()
        self.addAxisValues()


    def addAxisValues(self):
        for axis_value in self.axis_values.coordinate_dots:
            self.addItem(axis_value)

    def removeAxisValues(self):
        for axis_value in self.axis_values.coordinate_dots:
            self.removeItem(axis_value)


class Graphic3D(QDialog):
    """ Класс диалогового окна с графиком и кнопками отображения линий на нём."""
    def __init__(self, data_array=None, parent=None, file_path=None, window_ind=0, experiment_time=10):
        """ Создание окна с графиком.
        :param data_array: массив значений для построения, в случае передачи пути файла не используется.
        :param parent: родительский класс (при наличии).
        :param file_path: путь к файлу со значениями для построения.
        :param window_ind: номер окна, в случае, если строится несколько графиков.
        :param experiment_time: длительность эксперимента."""
        if parent is None:
            super().__init__()
        else:
            super().__init__(parent)

        # Задание начальных значений
        self.file_path = file_path
        self.data_array = data_array
        self.window_ind = window_ind
        self.experiment_time = experiment_time
        self.data = None
        self.parse_input_data()

        print("DATA DONE!")

        # Настройки внешнего вида окна
        self.window_width = 1500
        self.window_height = 1000
        self.resize(self.window_width, self.window_height)
        self.setWindowTitle(self.caption)

        self.figures = {}   # Массив фигур (пар вида линия - кнопка её отображения)
        layout_v = QVBoxLayout()

        # Импорт данных из датафрейма со значениями для построения.
        channels = self.data.columns.tolist()[-1] + 1
        values_number = self.data.index.tolist()[-1] + 1
        y_max = max(self.data.iloc[:, 0].values.tolist())
        x_max = values_number
        self.lines = []

        # Если data -- массив
        # channels = len(self.data)
        # values_number = 0
        # for array in self.data:
        #     values_number = max(values_number, len(array))
        #
        # x_max = values_number
        # y_max = self.data[0][0]
        # for array in self.data:
        #     for item in array:
        #         y_max = max(y_max, item)

        print("DATA ANALISE DONE!")

        self.lines = []
        # Добавляем линии и кнопки их отображения
        for channel in range(channels):
            key = f'channel_{channel + 1}'
            color = COLORS[channel]

            # Настройка кнопки отображения линии
            current_button = self.set_up_line_check_box(key, color)

            # Getting channel data
            # channel_data = self.data[channel]
            channel_data = self.data.iloc[:, channel].values.tolist()
            #print(f"channel_data = {channel_data}")
            channel_x_max = max(channel_data)
            y_max = max(y_max, channel_x_max)
            dots = []
            for dot in range(len(channel_data)):
                dots.append((channel_data[dot], dot, 0))

            # Adding points
            dots_array = np.array(dots)
            #print(f"dots_array = {dots_array}")
            line = gl.GLLinePlotItem(pos = dots_array, width = 3, antialias = False, glOptions='translucent', color = color)
            self.lines.append(line)
            self.figures[key] = Figure(check_box=current_button, line=line, data=Points())

            layout_v.addWidget(current_button)
        print("ADD LINES DONE!")

        # Setting up axis
        axis_length = 8 * max(y_max, x_max)
        axis_y_values = np.array([[-axis_length // 4, 0, 0], [axis_length // 4, 0, 0]])
        axis_x_values = np.array([[0, -axis_length // 4, 0], [0, axis_length // 4, 0]])
        axis_y = gl.GLLinePlotItem(pos=axis_y_values, width=1, antialias=False, glOptions='translucent', color="black")
        axis_x = gl.GLLinePlotItem(pos=axis_x_values, width=1, antialias=False, glOptions='translucent', color="black")

        self.graphic_widget = MyGLViewWidget(axis_length = axis_length, experiment_time=self.experiment_time)
        self.graphic_widget.setBackgroundColor("w")

        # Setting up view point
        self.graphic_widget.opts["center"] = Vector(y_max / 2, x_max / 2, 0)
        distance = max(y_max * 2, x_max * 2)
        self.graphic_widget.setCameraPosition(distance = distance, elevation = -90, azimuth = 0)

        # Добавляем линии и оси на график
        for l in  self.lines:
            self.graphic_widget.addItem(l)
        self.graphic_widget.addItem(axis_x)
        self.graphic_widget.addItem(axis_y)

        # Задаём кнопки изменения отображения всех линий
        false_all = QPushButton('Снять все')
        false_all.clicked.connect(self.change_all_check_boxes_false)
        true_all = QPushButton('Поставить все')
        true_all.clicked.connect(self.change_all_check_boxes_true)
        layout_v.addWidget(true_all)
        layout_v.addWidget(false_all)

        # Добавляем график и кнопки на окно приложения
        layout_h = QHBoxLayout()
        layout_h.addWidget(self.graphic_widget, 9)
        layout_h.addLayout(layout_v, 1)
        self.setLayout(layout_h)
        self.show()

    def parse_file_data(self):
        """ Разбирает поданный на вход файл.
        :return: датафрейм с набором значений для отображения."""
        _, file_extension = os.path.splitext(self.file_path)
        data = None
        if file_extension == '.csv':
            data = pd.read_csv(filepath_or_buffer=self.file_path, sep=';', header=None)
        elif file_extension == '.xlsx':
            data = pd.read_excel(io=self.file_path)
        print(f"parse_file_data: \n\t data = {data}")
        return data

    def  parse_input_data(self):
        """ Обрабатывает входные данные в зависимости от их вида (массив/путь файла)."""
        if self.file_path is not None:
            self.data = self.parse_file_data()
            self.caption = f"{find_file_name(self.file_path)} осциллограмма"
            print("PATH CHECK")
        elif self.data_array is not None:
            self.data = pd.DataFrame(self.data_array)
            print(f"array_values = {self.data.values.tolist()}")
            self.caption = f"Осциллограмма №{self.window_ind + 1}"
        #print(f"array_values = {self.data.values.tolist()}")

    def press_check_box(self, figure_name):
        """ Событие нажатие на кнопку отображения линии.
        Скрывает или показывает соответствующую линию."""
        if self.figures[figure_name].check_box.isChecked():
            self.graphic_widget.addItem(self.figures[figure_name].line)
        else:
            self.graphic_widget.removeItem(self.figures[figure_name].line)

    def change_all_check_boxes(self, is_check: bool):
        """ Изменение отображения всех линий на графике.
        :param is_check: true - для отображения всех линий, false - для скрытия всех линий."""
        for name in self.figures.keys():
            state = self.figures[name].check_box.isChecked()
            if state != is_check:
                self.figures[name].check_box.click()

    def change_all_check_boxes_true(self):
        """ Сменяет значение всех кнопок для линий. Отображает все линии на графике."""
        self.change_all_check_boxes(True)

    def change_all_check_boxes_false(self):
        """ Сменяет значение всех кнопок для линий. Скрывает все линии на графике."""
        self.change_all_check_boxes(False)

    def set_up_line_check_box(self, key, color):
        """ Настраивает кнопку отображения линии.
        :param key: название линии.
        :param color: цвет линии и кнопки для неё.
        :return: кнопка отображения"""
        current_button = QCheckBox(f"{key}")
        current_button.setChecked(True)
        current_style = "QCheckBox::indicator:checked {background-color: " + color + ";}"
        current_button.setStyleSheet(current_style)
        current_button.clicked.connect(partial(self.press_check_box, key))

        return current_button






if __name__ == '__main__':
    data_array = [[68, 70, 69, 67, 68, 67, 67, 68, 70, 70, 69, 71, 69, 71, 68, 70, 69, 69], [18, 20, 19, 17, 18, 17, 17, 18, 20, 20, 19, 21, 19, 21, 18, 20, 19, 19], [28, 30, 29, 27, 28, 27, 27, 28, 30, 30, 29, 31, 29, 31, 28, 30, 29, 29], [38, 40, 39, 37, 38, 37, 37, 38, 40, 40, 39, 41, 39, 41, 38, 40, 39, 39], [48, 50, 49, 47, 48, 47, 47, 48, 50, 50, 49, 51, 49, 51, 48, 50, 49, 49], [58, 60, 59, 57, 58, 57, 57, 58, 60, 60, 59, 61, 59, 61, 58, 60, 59, 59], [68, 70, 69, 67, 68, 67, 67, 68, 70, 70, 69, 71, 69, 71, 68, 70, 69, 69], [78, 80, 79, 77, 78, 77, 77, 78, 80, 80, 79, 81, 79, 81, 78, 80, 79, 79], [88, 90, 89, 87, 88, 87, 87, 88, 90, 90, 89, 91, 89, 91, 88, 90, 89, 89], [98, 100, 99, 97, 98, 97, 97, 98, 100, 100, 99, 101, 99, 101, 98, 100, 99, 99], [108, 110, 109, 107, 108, 107, 107, 108, 110, 110, 109, 111, 109, 111, 108, 110, 109, 109], [118, 120, 119, 117, 118, 117, 117, 118, 120, 120, 119, 121, 119, 121, 118, 120, 119, 119]]
    file_path = "test.csv"
    experiment_time = 5
    if len(sys.argv) > 2:
        file_path = sys.argv[1]
        experiment_time = sys.argv[2]
    app = QtWidgets.QApplication(sys.argv)
    g = Graphic3D(data_array=data_array, experiment_time=experiment_time)
    sys.exit(app.exec_())
