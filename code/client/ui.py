from PySide6 import QtCore, QtGui, QtWidgets
from PySide6.QtCore import QUrl
from PySide6.QtGui import QIcon
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
from serial.tools import list_ports

import numpy as np
import re
import os
import sys
import time
import logging

DEFAULT_BROKER_URL = "mqtt://192.168.10.2:1883"

INPUT_MAX_DX = 32768   # 每秒允许的最大鼠标X位移（像素），映射到±32768
INPUT_MAX_DY = 32768   # 每秒允许的最大鼠标Y位移（像素），映射到±32768
INPUT_MAX_DZ = 32768   # 每秒允许的最大滚轮步数（每步=一格=delta/120），映射到±32768


def get_resource(path):
    if getattr(sys, 'frozen', False):
        # 打包后的情况
        base_path = sys._MEIPASS
        return os.path.join(base_path, path)
    else:
        # 开发环境
        return path


class Overlay(QtWidgets.QWidget):  # 叠加层（准星 + 受击晕影 + 居中大字）

    hitProgressChanged = QtCore.Signal(float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents, True)
        self.setAttribute(QtCore.Qt.WA_NoSystemBackground, True)
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground, True)
        self.hit_progress = 0.0
        self.crosshair_visible = True  # <-- 新增：准星可见性状态，默认为True

        # 用于居中大字的状态变量
        self.center_text_line1 = ""
        self.center_text_line2 = ""
        self.center_text_color = QtGui.QColor(255, 255, 255)

    # <-- 新增：控制准星可见性的方法 -->
    def setCrosshairVisible(self, visible: bool):
        """设置准星是否可见"""
        if self.crosshair_visible != visible:
            self.crosshair_visible = visible
            self.update()  # 请求重绘

    def set_center_text(self, line1: str, line2: str, color="white"):  # 如果未提供颜色，则默认为白色
        """设置居中大字的内容和颜色"""
        self.center_text_line1 = line1
        self.center_text_line2 = line2
        self.center_text_color = QtGui.QColor(color)
        self.update()

    def setHitProgress(self, value: float):
        self.hit_progress = value
        self.hitProgressChanged.emit(self.hit_progress)
        self.update()

    def getHitProgress(self) -> float:
        return self.hit_progress

    hitProgress = QtCore.Property(float, fget=getHitProgress, fset=setHitProgress, notify=hitProgressChanged)

    def paintEvent(self, e):
        w, h = self.width(), self.height()
        p = QtGui.QPainter(self)
        p.setRenderHints(QtGui.QPainter.Antialiasing | QtGui.QPainter.SmoothPixmapTransform)

        # 准星
        # <-- 修改：仅在 crosshair_visible 为 True 时绘制 -->
        if self.crosshair_visible:
            cx, cy = w // 2, h // 2
            size = int(min(w, h) * 0.03)
            gap = int(size * 0.25)
            p.setPen(QtGui.QPen(QtGui.QColor(250, 250, 250, 230), 2))
            p.drawLine(cx - size, cy, cx - gap, cy)
            p.drawLine(cx + gap, cy, cx + size, cy)
            p.drawLine(cx, cy - size, cx, cy - gap)
            p.drawLine(cx, cy + gap, cx, cy + size)
            p.drawEllipse(QtCore.QPoint(cx, cy), int(size * 0.18), int(size * 0.18))

        # 受击晕影
        if self.hit_progress > 0:
            # 即使准星隐藏，中心点坐标也需要计算
            cx, cy = w // 2, h // 2
            edge_alpha = int(180 * (1.0 - self.hit_progress))
            radius = int((w ** 2 + h ** 2) ** 0.5 / 2)
            grad = QtGui.QRadialGradient(QtCore.QPointF(cx, cy), radius)
            grad.setColorAt(0.0, QtGui.QColor(255, 50, 50, 0))
            grad.setColorAt(0.6, QtGui.QColor(255, 50, 50, int(edge_alpha * 0.5)))
            grad.setColorAt(1.0, QtGui.QColor(255, 50, 50, edge_alpha))
            p.setBrush(QtGui.QBrush(grad))
            p.setPen(QtCore.Qt.NoPen)
            p.drawRect(0, 0, w, h)

        # 居中大字 (此部分逻辑不受准星可见性影响)
        if self.center_text_line1 or self.center_text_line2:
            p.save()  # 保存当前painter状态

            # 1. 设置字体
            font1 = QtGui.QFont(self.font().family(), int(h * 0.08), QtGui.QFont.Bold)
            font2 = QtGui.QFont(self.font().family(), int(h * 0.05), QtGui.QFont.Bold)

            # 2. 计算文本尺寸以确定背景大小
            fm1 = QtGui.QFontMetrics(font1)
            rect1 = fm1.boundingRect(self.center_text_line1)
            fm2 = QtGui.QFontMetrics(font2)
            rect2 = fm2.boundingRect(self.center_text_line2)

            # 计算总宽度和高度
            text_w = max(rect1.width(), rect2.width())
            spacing = int(h * 0.02)
            text_h = rect1.height() + rect2.height() + spacing

            # 3. 绘制半透明背景
            padding_x = int(w * 0.05)
            padding_y = int(h * 0.03)
            bg_w = text_w + padding_x * 2
            bg_h = text_h + padding_y * 2

            bg_rect = QtCore.QRectF(
                (w - bg_w) / 2,
                (h - bg_h) / 2,
                bg_w,
                bg_h
            )
            p.setPen(QtCore.Qt.NoPen)
            p.setBrush(QtGui.QColor(0, 0, 0, 100))  # 半透明黑色背景
            p.drawRoundedRect(bg_rect, 20.0, 20.0)  # 圆角

            # 4. 绘制两行文字
            p.setPen(QtGui.QPen(self.center_text_color))

            # 定义每行文本的绘制区域
            line1_rect = QtCore.QRectF(
                bg_rect.x(),
                bg_rect.y() + padding_y,
                bg_rect.width(),
                rect1.height()
            )
            line2_rect = QtCore.QRectF(
                bg_rect.x(),
                line1_rect.y() + line1_rect.height() + spacing,
                bg_rect.width(),
                rect2.height()
            )

            # 绘制第一行
            if self.center_text_line1:
                p.setFont(font1)
                p.drawText(line1_rect, QtCore.Qt.AlignCenter, self.center_text_line1)

            # 绘制第二行
            if self.center_text_line2:
                p.setFont(font2)
                p.drawText(line2_rect, QtCore.Qt.AlignCenter, self.center_text_line2)

            p.restore()  # 恢复painter状态

        p.end()


class HealthBar(QtWidgets.QFrame):  # 血条
    def __init__(self, parent=None, label_text="HP", team=None, height=64):
        super().__init__(parent)
        self.setObjectName("healthBar")
        self.value = 100
        self.team = team
        self.label_text = label_text
        self.setFixedHeight(height)
        self.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)

    def set_value(self, value: int):
        self.value = value
        self.update()

    def set_color(self, team: str | None):
        self.team = team if team in ("red", "blue") else None
        self.update()

    def paintEvent(self, e):
        w, h = self.width(), self.height()
        p = QtGui.QPainter(self)
        p.setRenderHints(QtGui.QPainter.Antialiasing | QtGui.QPainter.SmoothPixmapTransform)
        bg = QtGui.QColor(15, 17, 20, 210)
        p.setPen(QtGui.QPen(QtGui.QColor(0, 0, 0, 150), 1))
        p.setBrush(bg)
        rect = QtCore.QRectF(1.0, 1.0, w - 2.0, h - 2.0)
        r = h / 2.0
        p.drawRoundedRect(rect, r, r)
        ratio = self.value / 100.0
        fill_w = max(0.0, (w - 2.0) * ratio)
        if self.team == "red":
            c1, c2, txt = QtGui.QColor(255, 84, 84), QtGui.QColor(210, 50, 50), QtGui.QColor(255, 240, 240)
        elif self.team == "blue":
            c1, c2, txt = QtGui.QColor(88, 140, 255), QtGui.QColor(48, 90, 210), QtGui.QColor(235, 245, 255)
        else:
            c1, c2, txt = QtGui.QColor(180, 180, 180), QtGui.QColor(140, 140, 140), QtGui.QColor(240, 240, 240)
        grad = QtGui.QLinearGradient(0, 0, w, 0)
        grad.setColorAt(0.0, QtGui.QColor(c1.red(), c1.green(), c1.blue(), 240))
        grad.setColorAt(1.0, QtGui.QColor(c2.red(), c2.green(), c2.blue(), 240))
        p.setPen(QtCore.Qt.NoPen)
        p.setBrush(QtGui.QBrush(grad))
        p.drawRoundedRect(QtCore.QRectF(1.0, 1.0, fill_w, h - 2.0), r, r)
        base_font = QtGui.QFont(self.window().font())
        base_font.setBold(True)
        base_font.setPointSize(max(14, int(h * 0.50)))
        p.setFont(base_font)
        p.setPen(QtGui.QPen(txt, 1))
        p.drawText(rect, QtCore.Qt.AlignCenter, f"{self.label_text} {self.value:3d}")
        p.end()


class CountdownBanner(QtWidgets.QFrame):  # 倒计时
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("countdownBanner")
        lay = QtWidgets.QHBoxLayout(self)
        lay.setContentsMargins(26, 14, 26, 14)
        lay.setSpacing(8)
        self.label = QtWidgets.QLabel("0:00")
        self.label.setAlignment(QtCore.Qt.AlignCenter)
        f = QtGui.QFont(self.window().font())
        f.setBold(True)
        f.setPointSize(28)
        self.label.setFont(f)
        self.label.setStyleSheet("color: rgb(255,100,100); letter-spacing: 1px; margin:0px;")
        lay.addWidget(self.label)

        font_metrics = QtGui.QFontMetrics(self.label.font())
        max_text_width = font_metrics.horizontalAdvance("-00:00")
        self.label.setFixedWidth(max_text_width + 10)

    def set_text(self, txt):
        self.label.setText(txt)

    def set_warning(self, warn: bool):
        self.label.setStyleSheet(
            "color: rgb(255,100,100); letter-spacing: 1px; margin:0px;"
            if warn
            else "color: #f5f7fa; letter-spacing: 1px; margin:0px;"
        )


class ToggleSwitch(QtWidgets.QCheckBox):
    def __init__(self, parent=None, bg_color="#777", circle_color="#FFF", active_color="#3478F6"):
        super().__init__(parent)
        self.setFixedSize(52, 28)
        self.setCursor(QtCore.Qt.PointingHandCursor)

        self._bg_color = QtGui.QColor(bg_color)
        self._circle_color = QtGui.QColor(circle_color)
        self._active_color = QtGui.QColor(active_color)

        self._circle_position = 3
        self.animation = QtCore.QPropertyAnimation(self, b"circle_position", self)
        self.animation.setEasingCurve(QtCore.QEasingCurve.OutCubic)
        self.animation.setDuration(200)

        self.stateChanged.connect(self.start_animation)

    @QtCore.Property(int)
    def circle_position(self):
        return self._circle_position

    @circle_position.setter
    def circle_position(self, pos):
        self._circle_position = pos
        self.update()

    def start_animation(self, value):
        self.animation.stop()
        if value:
            self.animation.setEndValue(self.width() - self.height() + 3)
        else:
            self.animation.setEndValue(3)
        self.animation.start()

    def paintEvent(self, e):
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.Antialiasing)
        p.setPen(QtCore.Qt.NoPen)

        rect = QtCore.QRect(0, 0, self.width(), self.height())
        if self.isChecked():
            p.setBrush(self._active_color)
        else:
            p.setBrush(self._bg_color)
        p.drawRoundedRect(rect, self.height() / 2, self.height() / 2)

        p.setBrush(self._circle_color)
        p.drawEllipse(
            self._circle_position, 3, self.height() - 6, self.height() - 6
        )

    def mousePressEvent(self, e):
        self.toggle()
        return super().mousePressEvent(e)


class UIBase(QtWidgets.QMainWindow):
    def __init__(self, level=logging.WARNING):
        self.app = QtWidgets.QApplication(sys.argv)
        self.app.setWindowIcon(QIcon(get_resource("./assets/logo.png")))

        super().__init__()

        self.logger = logging.getLogger("UI")
        self.logger.setLevel(level)

        self.setWindowTitle("RoboMaster校内赛选手端")

        scr = QtWidgets.QApplication.primaryScreen().availableGeometry()
        self.screen_size = QtCore.QSize(scr.width(), scr.height())
        self.font_main = QtGui.QFont()
        self.font_main.setFamily(self._pick_ui_font())
        self.font_main.setWeight(QtGui.QFont.Medium)
        self.setFont(self.font_main)
        self.setStyleSheet(self._qss())

        central = QtWidgets.QWidget(objectName="central")
        self.setCentralWidget(central)
        lay = QtWidgets.QVBoxLayout(central)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        self.bg_label = QtWidgets.QLabel(objectName="bgLabel")
        self.bg_label.setAlignment(QtCore.Qt.AlignCenter)
        self.bg_label.setScaledContents(False)
        lay.addWidget(self.bg_label)

        self.overlay = Overlay(self.bg_label)
        self.overlay.setGeometry(0, 0, self.screen_size.width(), self.screen_size.height())
        self.overlay.raise_()

        self.top_hud = QtWidgets.QWidget(self, objectName="topHud")
        self.top_layout = QtWidgets.QHBoxLayout(self.top_hud)
        self.top_layout.setContentsMargins(0, 0, 0, 0)
        self.top_layout.setSpacing(20)

        self.red_team_widget = QtWidgets.QWidget(self.top_hud)
        red_layout = QtWidgets.QVBoxLayout(self.red_team_widget)
        red_layout.setContentsMargins(0, 0, 0, 0)
        red_layout.setSpacing(2)
        self.red_name_label = QtWidgets.QLabel("红方队伍", objectName="redNameLabel")
        self.red_name_label.setAlignment(QtCore.Qt.AlignCenter)
        f_team = QtGui.QFont(self.font_main)
        f_team.setBold(True)
        f_team.setPointSize(20)
        self.red_name_label.setFont(f_team)
        self.red_bar_top = HealthBar(self.red_team_widget, label_text="红方", team="red", height=48)
        red_layout.addWidget(self.red_name_label)
        red_layout.addWidget(self.red_bar_top)
        red_layout.addStretch(1)

        self.blue_team_widget = QtWidgets.QWidget(self.top_hud)
        blue_layout = QtWidgets.QVBoxLayout(self.blue_team_widget)
        blue_layout.setContentsMargins(0, 0, 0, 0)
        blue_layout.setSpacing(2)
        self.blue_name_label = QtWidgets.QLabel("蓝方队伍", objectName="blueNameLabel")
        self.blue_name_label.setAlignment(QtCore.Qt.AlignCenter)
        self.blue_name_label.setFont(f_team)
        self.blue_bar_top = HealthBar(self.blue_team_widget, label_text="蓝方", team="blue", height=48)
        blue_layout.addWidget(self.blue_name_label)
        blue_layout.addWidget(self.blue_bar_top)
        blue_layout.addStretch(1)

        self.countdown_banner = CountdownBanner(self.top_hud)

        self.top_layout.addStretch(1)
        self.top_layout.addWidget(self.red_team_widget, 2)
        self.top_layout.addSpacing(12)
        self.top_layout.addWidget(self.countdown_banner, 0, QtCore.Qt.AlignVCenter)
        self.top_layout.addSpacing(12)
        self.top_layout.addWidget(self.blue_team_widget, 2)
        self.top_layout.addStretch(1)

        self.exit_btn = QtWidgets.QPushButton("退出", parent=self, objectName="exitBtn")
        self.exit_btn.clicked.connect(self.close)
        self.settings_btn = QtWidgets.QPushButton("设置", parent=self, objectName="settingsBtn")
        self.settings_btn.clicked.connect(self._open_menu)
        self._style_buttons_font()

        self.bottom_left_panel = QtWidgets.QFrame(self, objectName="bottomPanel")
        bl = QtWidgets.QVBoxLayout(self.bottom_left_panel)
        bl.setContentsMargins(10, 6, 10, 6)
        bl.setSpacing(4)
        self.self_bar = HealthBar(self.bottom_left_panel, label_text="我方", team=None, height=26)
        self.self_bar.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
        bl.addWidget(self.self_bar)

        self.status_label1 = QtWidgets.QLabel("", objectName="statusBar")
        f2 = QtGui.QFont(self.font_main)
        f2.setPointSize(13)
        self.status_label1.setFont(f2)
        self.status_label1.setTextFormat(QtCore.Qt.RichText)
        self.status_label1.setStyleSheet("margin:0px; padding:0px;")
        self.status_label1.setWordWrap(False)
        self.status_label1.setAlignment(QtCore.Qt.AlignCenter)
        self.status_label1.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
        bl.addWidget(self.status_label1)

        self.status_label2 = QtWidgets.QLabel("", objectName="armorBar")
        f3 = QtGui.QFont(self.font_main)
        f3.setPointSize(13)
        self.status_label2.setFont(f3)
        self.status_label2.setTextFormat(QtCore.Qt.RichText)
        self.status_label2.setStyleSheet("margin:0px; padding:0px;")
        self.status_label2.setWordWrap(False)
        self.status_label2.setAlignment(QtCore.Qt.AlignCenter)
        self.status_label2.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
        bl.addWidget(self.status_label2)

        self.menu_mask = QtWidgets.QWidget(self, objectName="menuMask")
        self.menu_mask.hide()
        self.menu_mask.mousePressEvent = lambda e: self._cancel_menu()
        self.menu_panel = QtWidgets.QWidget(self, objectName="menuPanel")
        self.menu_panel.hide()
        self._build_menu_panel(self.menu_panel)
        self._menu_snapshot = None

        self.hit_anim = QtCore.QPropertyAnimation(self.overlay, b"hitProgress")
        self.hit_anim.setDuration(700)
        self.hit_anim.setStartValue(0.0)
        self.hit_anim.setEndValue(1.0)
        self.hit_anim.setEasingCurve(QtCore.QEasingCurve.OutCubic)

        self.uart_connect_state = False
        self.video_fps = None
        self.mqtt_freq = None
        self.tx_rssi = None
        self.rx_rssi = None

        self.serial_port = None
        self.video_source = self.video_edit.text().strip()
        self.mqtt_url = self.server_edit.text().strip()
        self.big_screen_mode = False

        self._update_status()
        self._update_ui_for_big_screen_mode()
        self._auto_select_first_serial()

    def _refresh_serial_ports(self):
        prev = None
        if hasattr(self, "serial_combo") and isinstance(self.serial_combo, QtWidgets.QComboBox):
            try:
                prev = self.serial_combo.currentData()
            except Exception:
                prev = None

        ports = list_ports.comports()
        self.serial_combo.clear()
        seen_devices = set()

        for p in ports:
            device = (getattr(p, "device", "") or "").strip()
            if not device:
                continue
            desc_raw = (getattr(p, "description", "") or "").strip()
            label = self._format_serial_label(device, desc_raw)
            key_dev = device.lower()
            if key_dev in seen_devices:
                continue
            seen_devices.add(key_dev)
            self.serial_combo.addItem(label, device)

        if self.serial_combo.count() == 0:
            self.serial_combo.addItem("无可用串口", "NA")

        if prev:
            idx_prev = self.serial_combo.findData(prev)
            if idx_prev >= 0:
                self.serial_combo.setCurrentIndex(idx_prev)
                return
        if self.serial_port:
            idx_applied = self.serial_combo.findData(self.serial_port)
            if idx_applied >= 0:
                self.serial_combo.setCurrentIndex(idx_applied)

    def _open_menu(self):
        self._refresh_serial_ports()

        self.video_edit.setText(self.video_source or "")
        self.server_edit.setText(self.mqtt_url or "")
        if self.serial_port:
            idx = self.serial_combo.findData(self.serial_port)
            if idx >= 0:
                self.serial_combo.setCurrentIndex(idx)
        self.big_screen_mode_check.setChecked(self.big_screen_mode)

        self._menu_snapshot = {
            "serial_index": self.serial_combo.currentIndex() if hasattr(self, "serial_combo") else 0,
            "video": self.video_edit.text() if hasattr(self, "video_edit") else "",
            "server": self.server_edit.text() if hasattr(self, "server_edit") else "",
            "big_screen_mode": self.big_screen_mode_check.isChecked(),
        }
        self._center_menu()
        self.menu_mask.setGeometry(0, 0, self.width(), self.height())
        self.menu_mask.show()
        self.menu_mask.raise_()
        self.menu_panel.show()
        self.menu_panel.raise_()

    def _apply_menu(self):
        data = self.serial_combo.currentData() if hasattr(self, "serial_combo") else None
        self.serial_port = (str(data).strip()
                            if data and str(data).strip().upper() != "NA"
                            else None)
        self.video_source = self.video_edit.text().strip()
        self.mqtt_url = self.server_edit.text().strip()
        self.big_screen_mode = self.big_screen_mode_check.isChecked()

        self._update_ui_for_big_screen_mode()

        self._menu_snapshot = None
        self.menu_panel.hide()
        self.menu_mask.hide()

    def _cancel_menu(self):
        snap = self._menu_snapshot
        if snap is not None:
            try:
                self.serial_combo.setCurrentIndex(snap["serial_index"])
            except Exception:
                pass
            self.video_edit.setText(snap["video"])
            self.server_edit.setText(snap["server"])
            self.big_screen_mode_check.setChecked(snap["big_screen_mode"])
        self._menu_snapshot = None
        self.menu_panel.hide()
        self.menu_mask.hide()

    def _build_menu_panel(self, panel):
        layout = QtWidgets.QVBoxLayout(panel)
        layout.setContentsMargins(28, 28, 28, 28)
        layout.setSpacing(18)

        title = QtWidgets.QLabel("设置", objectName="menuTitle")
        ft = QtGui.QFont(self.font_main)
        ft.setPointSize(18)
        ft.setBold(True)
        title.setFont(ft)
        layout.addWidget(title)

        label_w = 90

        row1 = QtWidgets.QWidget()
        r1 = QtWidgets.QHBoxLayout(row1)
        r1.setContentsMargins(0, 0, 0, 0)
        r1.setSpacing(10)
        l1 = QtWidgets.QLabel("串口设备")
        l1.setFixedWidth(label_w)
        l1.setFont(self._font_scaled(0.022))
        self.serial_combo = QtWidgets.QComboBox(objectName="serialCombo")
        self.serial_combo.setFont(self._font_scaled(0.022))

        orig_show = self.serial_combo.showPopup

        def _showPopup_refresh():
            try:
                self._refresh_serial_ports()
            except Exception:
                pass
            orig_show()
        self.serial_combo.showPopup = _showPopup_refresh

        r1.addWidget(l1)
        r1.addWidget(self.serial_combo, 1)
        layout.addWidget(row1)

        row2 = QtWidgets.QWidget()
        r2 = QtWidgets.QHBoxLayout(row2)
        r2.setContentsMargins(0, 0, 0, 0)
        r2.setSpacing(10)
        l2 = QtWidgets.QLabel("视频流地址")
        l2.setFixedWidth(label_w)
        l2.setFont(self._font_scaled(0.022))
        self.video_edit = QtWidgets.QLineEdit(objectName="videoEdit")
        self.video_edit.setFont(self._font_scaled(0.022))
        self.video_edit.setText("rtsp://192.168.1.1:7070/webcam")
        r2.addWidget(l2)
        r2.addWidget(self.video_edit, 1)
        layout.addWidget(row2)

        row3 = QtWidgets.QWidget()
        r3 = QtWidgets.QHBoxLayout(row3)
        r3.setContentsMargins(0, 0, 0, 0)
        r3.setSpacing(10)
        l3 = QtWidgets.QLabel("MQTT地址")
        l3.setFixedWidth(label_w)
        l3.setFont(self._font_scaled(0.022))
        self.server_edit = QtWidgets.QLineEdit(objectName="serverEdit")
        self.server_edit.setFont(self._font_scaled(0.022))
        self.server_edit.setText(DEFAULT_BROKER_URL)
        r3.addWidget(l3)
        r3.addWidget(self.server_edit, 1)
        layout.addWidget(row3)

        row4 = QtWidgets.QWidget()
        r4 = QtWidgets.QHBoxLayout(row4)
        r4.setContentsMargins(0, 0, 0, 0)
        r4.setSpacing(10)
        l4 = QtWidgets.QLabel("大屏模式")
        l4.setFixedWidth(label_w)
        l4.setFont(self._font_scaled(0.022))
        self.big_screen_mode_check = ToggleSwitch(self)
        r4.addWidget(l4)
        r4.addWidget(self.big_screen_mode_check)
        r4.addStretch(1)
        layout.addWidget(row4)

        layout.addStretch(1)

        btns = QtWidgets.QWidget()
        rb = QtWidgets.QHBoxLayout(btns)
        rb.setContentsMargins(0, 0, 0, 0)
        rb.setSpacing(12)
        ok = QtWidgets.QPushButton("确定", objectName="okBtn")
        ok.setFont(self._font_scaled(0.022))
        cancel = QtWidgets.QPushButton("取消", objectName="cancelBtn")
        cancel.setFont(self._font_scaled(0.022))
        rb.addStretch(1)
        rb.addWidget(cancel)
        rb.addWidget(ok)
        layout.addWidget(btns)

        cancel.clicked.connect(self._cancel_menu)
        ok.clicked.connect(self._apply_menu)

    def _plain_text(self, html: str) -> str:
        return re.sub(r"<[^>]+>", "", html or "").strip()

    def _update_bottom_panel_layout(self):
        W, H = self.width(), self.height()

        text_status = self._plain_text(self.status_label1.text())
        text_armor = self._plain_text(self.status_label2.text())
        fm_status = QtGui.QFontMetrics(self.status_label1.font())
        fm_armor = QtGui.QFontMetrics(self.status_label2.font())
        text_w_status = fm_status.horizontalAdvance(text_status) + 18
        text_w_armor = fm_armor.horizontalAdvance(text_armor) + 18
        text_w = max(text_w_status, text_w_armor)

        min_inner = 360
        max_inner = int(W * 0.40)
        target_inner_w = max(min_inner, min(max_inner, text_w))
        panel_margin_lr = 20
        bl_w = target_inner_w + panel_margin_lr

        base_h = int(H * 0.11)
        bl_h = max(base_h, 86)

        bl_x = int(W * 0.028)

        line_h = fm_status.height()
        bl_y = H - bl_h - int(H * 0.060) - line_h
        bl_y = max(0, bl_y)

        self.bottom_left_panel.setGeometry(bl_x, bl_y, bl_w, bl_h)

        inner_w = self.bottom_left_panel.width() - panel_margin_lr
        self.self_bar.setFixedWidth(inner_w)
        self.status_label1.setFixedWidth(inner_w)
        self.status_label2.setFixedWidth(inner_w)

    def _auto_select_first_serial(self):
        self.logger.info("Auto-detecting serial ports on startup...")
        self._refresh_serial_ports()

        if self.serial_combo.count() > 0:
            first_port_device = self.serial_combo.itemData(0)
            if first_port_device and str(first_port_device).upper() != "NA":
                self.serial_port = first_port_device
                self.logger.info(f"Automatically selected first available serial port: {self.serial_port}")
            else:
                self.logger.warning("No valid serial ports found on startup.")
        else:
            self.logger.warning("No serial ports found on startup.")

    def _update_status(self):
        if self.video_fps is None:
            video_txt = "图传: <span style='color:#ff5a5a;'>未连接</span>"
        else:
            video_txt = f"图传: <span style='color:#eaeaea;'>{self.video_fps:.0f} fps</span>"

        if self.mqtt_freq is None:
            mqtt_txt = "裁判端: <span style='color:#ff5a5a;'>未连接</span>"
        else:
            mqtt_txt = f"裁判端: <span style='color:#eaeaea;'>{self.mqtt_freq:02.0f} Hz</span>"

        self.status_label1.setText(f"<div style='text-align:center'>{mqtt_txt} | {video_txt}</div>")

        if self.uart_connect_state == 0:
            uart_txt = "装甲板: <span style='color:#ff5a5a;'>串口未连接</span>"
        elif self.uart_connect_state == 1:
            uart_txt = "装甲板: <span style='color:#ff5a5a;'>无线未连接</span>"
        elif self.uart_connect_state == 2:
            uart_txt = "装甲板: <span style='color:#eaeaea;'>无线已连接</span>"

        if self.uart_connect_state != 2 or self.tx_rssi is None or self.rx_rssi is None:
            rssi_tx_txt = f"TX: <span style='color:#ff5a5a;'>未连接</span>"
            rssi_rx_txt = f"RX: <span style='color:#ff5a5a;'>未连接</span>"
        else:
            rssi_tx_txt = f"TX: <span style='color:#eaeaea;'>{self.tx_rssi:.0f} dBm</span>"
            rssi_rx_txt = f"RX: <span style='color:#eaeaea;'>{self.rx_rssi:.0f} dBm</span>"

        self.status_label2.setText(f"<div style='text-align:center'>{uart_txt} | {rssi_tx_txt} | {rssi_rx_txt}</div>")

        self._update_bottom_panel_layout()

    def _update_ui_for_big_screen_mode(self):
        """根据大屏模式的设置，显示或隐藏UI元素"""
        is_big_screen = self.big_screen_mode
        self.bottom_left_panel.setHidden(is_big_screen)
        self.overlay.setCrosshairVisible(not is_big_screen)

    def _format_serial_label(self, device: str, desc: str) -> str:
        com = (device or "").strip()
        d = (desc or "").strip()
        if not d:
            return com or "NA"
        if re.search(r"COM\s*\d+", d, flags=re.IGNORECASE):
            return d
        return f"{d} ({com})" if com else d

    def resizeEvent(self, e):
        W, H = self.width(), self.height()
        self.overlay.setGeometry(0, 0, W, H)

        top_y = int(H * 0.020)
        top_h = int(H * 0.12)
        side_margin = int(W * 0.035)
        self.top_hud.setGeometry(
            side_margin, top_y, W - side_margin * 2, top_h)
        self.top_layout.setContentsMargins(
            int(W * 0.010), 0, int(W * 0.010), 0)

        max_bar_w = int(W * 0.22)
        min_bar_w = 260
        for w in (self.red_team_widget, self.blue_team_widget):
            w.setMaximumWidth(max_bar_w)
            w.setMinimumWidth(min_bar_w)

        btn_w, btn_h, gap = 114, 42, 10
        right_margin = int(W * 0.035)
        btn_x = W - right_margin - btn_w
        exit_btn_y = top_y
        self.exit_btn.setGeometry(btn_x, exit_btn_y, btn_w, btn_h)
        settings_btn_y = exit_btn_y + btn_h + gap
        self.settings_btn.setGeometry(btn_x, settings_btn_y, btn_w, btn_h)

        self._update_bottom_panel_layout()

        self._center_menu()
        self.menu_mask.setGeometry(0, 0, W, H)

        super().resizeEvent(e)

    def _center_menu(self):
        W, H = self.width(), self.height()
        panel_w = int(W * 0.40)
        panel_h = int(H * 0.62)
        self.menu_panel.setGeometry(
            (W - panel_w) // 2, (H - panel_h) // 2, panel_w, panel_h)

    def _font_scaled(self, ratio):
        f = QtGui.QFont(self.font_main)
        f.setPointSizeF(max(11.0, self.screen_size.height() * ratio / 2.0))
        f.setBold(False)
        return f

    def _pick_ui_font(self):
        fams = QtGui.QFontDatabase.families()
        prefer = [
            "Microsoft YaHei UI", "Segoe UI", "PingFang SC", "苹方-简",
            "HarmonyOS Sans SC", "思源黑体", "Source Han Sans SC",
            "Microsoft YaHei", "微软雅黑",
        ]
        for p in prefer:
            if p in fams:
                return p
        return QtGui.QFont().defaultFamily()

    def _qss(self):
        return """
        #central { background: #0f1216; }
        #bgLabel { background: #0f1216; }
        #topHud { background: transparent; }
        #countdownBanner { background: rgba(0,0,0,0.35); border-radius: 14px; }
        #bottomPanel { background: rgba(0,0,0,0.30); border-radius: 10px; }
        #settingsBtn, #exitBtn, #okBtn, #cancelBtn {
            background: rgba(32,36,42,0.95);
            color: #f2f2f2; border: 1px solid rgba(255,255,255,0.14);
            border-radius: 10px; padding: 6px 12px;
        }
        #settingsBtn:disabled, #exitBtn:disabled { background: rgba(32,36,42,0.55); color: rgba(240,240,240,0.55); }
        #settingsBtn:hover, #exitBtn:hover, #okBtn:hover, #cancelBtn:hover { background: rgba(45,50,58,0.98); }
        #menuMask { background: rgba(0,0,0,0.55); }
        #menuPanel { background: rgba(25,28,34,0.98); border: 1px solid rgba(255,255,255,0.12); border-radius: 16px; }
        #menuTitle { color: #f0f0f0; }
        #serialCombo, #videoEdit, #serverEdit {
            background: rgba(255,255,255,0.10); color: #ffffff; border: 1px solid rgba(255,255,255,0.22);
            border-radius: 8px; padding: 8px 10px;
        }
        #redNameLabel { color: #ff6b6b; }
        #blueNameLabel { color: #6ea8ff; }
        QLabel { color: #ffffff; }
        """

    def _style_buttons_font(self):
        for b in (self.exit_btn, self.settings_btn):
            fbtn = QtGui.QFont(self.font_main)
            fbtn.setBold(False)
            fbtn.setPointSize(12)
            b.setFont(fbtn)

    def move_to_current_screen(self):
        cursor_pos = QtGui.QCursor.pos()
        screen = QtWidgets.QApplication.screenAt(cursor_pos)
        screen_geometry = screen.availableGeometry()
        x = screen_geometry.x() + (screen_geometry.width() - self.width()) // 2
        y = screen_geometry.y() + (screen_geometry.height() - self.height()) // 2
        self.move(x, y)

    def loop(self, resize=None):
        if resize is None:
            self.move_to_current_screen()
            self.showFullScreen()
        else:
            self.resize(*resize)
            self.move_to_current_screen()
            self.showNormal()
        self.app.exec()


class UI(UIBase):
    def __init__(self, level=logging.WARNING):
        super().__init__(level)

        self.media_player = QMediaPlayer()
        self.audio_output = QAudioOutput()
        self.media_player.setAudioOutput(self.audio_output)
        self.media_player.setSource(QUrl.fromLocalFile(get_resource("./assets/bgm.mp3")))
        self.audio_output.setVolume(1.0)
        self.bgm_start_time = None

        self._last_mouse_time = time.perf_counter()
        self._wheel_accum = 0.0
        self._key_state = {
            "w": False, "s": False, "a": False, "d": False,
            "q": False, "e": False, "shift": False, "ctrl": False
        }
        self._dbus_packet = bytes(10)

        self._cursor_shown = False
        self.setCursor(QtCore.Qt.BlankCursor)

        QtWidgets.QApplication.instance().installEventFilter(self)
        self._input_timer = QtCore.QTimer(self)
        self._input_timer.setInterval(10)
        self._input_timer.timeout.connect(self._sample_input)
        self._input_timer.start()

    def set_red_name(self, name: str):
        if name is None:
            return
        self.red_name_label.setText(name)
        self.red_name_label.setAlignment(QtCore.Qt.AlignCenter)

    def set_blue_name(self, name: str):
        if name is None:
            return
        self.blue_name_label.setText(name)
        self.blue_name_label.setAlignment(QtCore.Qt.AlignCenter)

    def set_frame(self, frame_bgr: np.ndarray):
        if frame_bgr is None:
            return
        h, w = frame_bgr.shape[:2]
        qimg = QtGui.QImage(frame_bgr.data, w, h, 3 * w, QtGui.QImage.Format_BGR888)
        target = self.bg_label.size()
        if target.width() == 0 or target.height() == 0:
            return
        qimg_scaled = qimg.scaled(target, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation)
        final_image = QtGui.QImage(target.width(), target.height(), QtGui.QImage.Format_RGB888)
        final_image.fill(QtCore.Qt.black)
        x_offset = (target.width() - qimg_scaled.width()) // 2
        y_offset = (target.height() - qimg_scaled.height()) // 2
        painter = QtGui.QPainter(final_image)
        painter.drawImage(x_offset, y_offset, qimg_scaled)
        painter.end()
        self.bg_label.setPixmap(QtGui.QPixmap.fromImage(final_image))

    def set_video_fps(self, fps):
        self.video_fps = fps
        self._update_status()

    def set_countdown(self, seconds: float | None):
        if seconds is None:
            self.media_player.stop()
            self.bgm_start_time = None
            return

        seconds_int = int(round(seconds))
        bgm_start_time = self.bgm_start_time
        if seconds_int >= 0:
            m, s = seconds_int // 60, seconds_int % 60
            self.countdown_banner.set_text(f"{m}:{s:02d}")
            self.countdown_banner.set_warning(seconds <= 10)
            if seconds == 0:
                self.media_player.stop()
                self.bgm_start_time = None
                return
            else:
                bgm_start_time = time.time() - 120 - (180 - seconds)
        else:
            abs_seconds = abs(seconds_int)
            m, s = abs_seconds // 60, abs_seconds % 60
            self.countdown_banner.set_text(f"-{m}:{s:02d}")
            self.countdown_banner.set_warning(False)
            bgm_start_time = time.time() - (120 - -seconds)

        if self.bgm_start_time is None or abs(bgm_start_time - self.bgm_start_time) > 0.5:
            position = time.time() - bgm_start_time
            if position < 300:
                self.media_player.setPosition(int(round(position * 1000)))
                self.media_player.play()
                self.bgm_start_time = bgm_start_time

    def set_color(self, color: str | None):
        self.color = color if color in ("red", "blue") else None
        self.self_bar.set_color(self.color)

    def set_red_hp(self, hp: int | None):
        if hp is None:
            return
        self.red_bar_top.set_value(hp)
        if self.color == "red":
            self.self_bar.set_value(hp)

    def set_blue_hp(self, hp: int | None):
        if hp is None:
            return
        self.blue_bar_top.set_value(hp)
        if self.color == "blue":
            self.self_bar.set_value(hp)

    def set_uart_connect_state(self, state):
        self.uart_connect_state = state
        self._update_status()

    def set_rssi(self, tx_rssi, rx_rssi):
        self.tx_rssi = tx_rssi
        self.rx_rssi = rx_rssi
        self._update_status()

    def set_mqtt_freq(self, freq):
        self.mqtt_freq = freq
        self._update_status()

    def set_center_txt(self, line1: str, line2: str, color="white"):
        self.overlay.set_center_text(line1, line2, color)

    def get_serial_port(self) -> str | None: return self.serial_port
    def get_video_source(self) -> str | None: return self.video_source
    def get_mqtt_url(self) -> str | None: return self.mqtt_url
    def get_dbus_packet(self) -> bytes: return self._dbus_packet

    def trigger_hit(self):
        if self.hit_anim.state() == QtCore.QAbstractAnimation.Running:
            self.hit_anim.stop()
        self.overlay.setHitProgress(0.0)
        self.hit_anim.start()

    def _set_key_state(self, key, down: bool):
        m = {
            QtCore.Qt.Key_W: "w", QtCore.Qt.Key_S: "s", QtCore.Qt.Key_A: "a",
            QtCore.Qt.Key_D: "d", QtCore.Qt.Key_Q: "q", QtCore.Qt.Key_E: "e",
            QtCore.Qt.Key_Shift: "shift", QtCore.Qt.Key_Control: "ctrl",
        }
        name = m.get(key)
        if name:
            self._key_state[name] = down

    @classmethod
    def _map_to_i16(cls, val: float, max_val: float) -> int:
        if val > max_val:
            return 32767
        if val < -max_val:
            return -32768
        return int(round(val / max_val * 32767.0))

    @classmethod
    def _build_dbus_packet(cls, dx: float, dy: float, dz: float, left_pressed: bool, right_pressed: bool, key_state) -> bytes:
        x16 = cls._map_to_i16(dx, INPUT_MAX_DX)
        y16 = cls._map_to_i16(dy, INPUT_MAX_DY)
        z16 = cls._map_to_i16(dz, INPUT_MAX_DZ)
        key_byte = (
            (1 if key_state["w"] else 0) << 0 | (1 if key_state["s"] else 0) << 1 |
            (1 if key_state["a"] else 0) << 2 | (1 if key_state["d"] else 0) << 3 |
            (1 if key_state["q"] else 0) << 4 | (1 if key_state["e"] else 0) << 5 |
            (1 if key_state["shift"] else 0) << 6 | (1 if key_state["ctrl"] else 0) << 7
        )
        packet = bytearray(10)
        packet[0] = x16 & 0xFF
        packet[1] = (x16 >> 8) & 0xFF
        packet[2] = y16 & 0xFF
        packet[3] = (y16 >> 8) & 0xFF
        packet[4] = z16 & 0xFF
        packet[5] = (z16 >> 8) & 0xFF
        packet[6] = 0x01 if left_pressed else 0x00
        packet[7] = 0x01 if right_pressed else 0x00
        packet[8] = key_byte & 0xFF
        packet[9] = 0x01
        return bytes(packet)

    def _sample_input(self):
        if not self.isActiveWindow():
            if not self._cursor_shown:
                self._cursor_shown = True
                self.setCursor(QtCore.Qt.ArrowCursor)
                self.exit_btn.setEnabled(True)
                self.settings_btn.setEnabled(True)

        if self._cursor_shown:
            self._last_mouse_time = time.perf_counter()
            self._wheel_accum = 0.0
            self._dbus_packet = bytes(10)
            return

        now_time = time.perf_counter()
        dt = now_time - self._last_mouse_time
        if dt <= 0:
            return

        center = self.mapToGlobal(QtCore.QPoint(self.width() // 2, self.height() // 2))
        pos = QtGui.QCursor.pos()
        vx = (pos.x() - center.x()) / dt
        vy = (pos.y() - center.y()) / dt
        vz = self._wheel_accum / dt
        QtGui.QCursor.setPos(center)

        buttons = QtWidgets.QApplication.mouseButtons()
        left_pressed = bool(buttons & QtCore.Qt.LeftButton)
        right_pressed = bool(buttons & QtCore.Qt.RightButton)

        self._dbus_packet = self._build_dbus_packet(
            vx, vy, vz, left_pressed, right_pressed, self._key_state)

        self._last_mouse_time = now_time
        self._wheel_accum = 0.0

    def eventFilter(self, obj, event):
        if event.type() == QtCore.QEvent.Wheel:
            self._wheel_accum += event.angleDelta().y() / 120.0
        elif event.type() == QtCore.QEvent.KeyPress and not event.isAutoRepeat():
            self._set_key_state(event.key(), True)
        elif event.type() == QtCore.QEvent.KeyRelease and not event.isAutoRepeat():
            self._set_key_state(event.key(), False)
        return super().eventFilter(obj, event)

    def keyPressEvent(self, e):
        if e.key() == QtCore.Qt.Key_Escape:
            if not self._cursor_shown:
                self._cursor_shown = True
                self.setCursor(QtCore.Qt.ArrowCursor)
                self.exit_btn.setEnabled(True)
                self.settings_btn.setEnabled(True)
        super().keyPressEvent(e)

    def changeEvent(self, event):
        if event.type() == event.Type.ActivationChange and not self.isActiveWindow():
            if not self._cursor_shown:
                self._cursor_shown = True
                self.setCursor(QtCore.Qt.ArrowCursor)
                self.exit_btn.setEnabled(True)
                self.settings_btn.setEnabled(True)
        super().changeEvent(event)

    def mousePressEvent(self, e):
        if not self.menu_panel.isVisible():
            if self._cursor_shown:
                self._cursor_shown = False
                self.setCursor(QtCore.Qt.BlankCursor)
                center = self.mapToGlobal(QtCore.QPoint(self.width() // 2, self.height() // 2))
                QtGui.QCursor.setPos(center)
                self.exit_btn.setEnabled(False)
                self.settings_btn.setEnabled(False)
        super().mousePressEvent(e)

# ================== 测试代码（main） ==================


def test_UIBase():
    ui = UIBase(logging.INFO)
    ui.loop((1280, 720))


def test_UI():
    ui = UI(logging.INFO)

    # 视频流
    # cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
    # cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    # cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

    # last_time = time.time()
    # frame_count = 0

    # def update_frame():
    #     nonlocal last_time, frame_count
    #     ret, frame = cap.read()
    #     if ret:
    #         ui.set_frame(frame)
    #         frame_count += 1
    #         now = time.time()
    #         if now - last_time >= 1.0:
    #             ui.set_fps(frame_count)
    #             frame_count = 0
    #             last_time = now

    # frame_timer = QtCore.QTimer()
    # frame_timer.timeout.connect(update_frame)
    # frame_timer.start(33)

    # 倒计时演示
    countdown = 15
    ui.set_countdown(countdown)

    def update_countdown():
        nonlocal countdown
        countdown = countdown - 1 if countdown > 0 else 15
        ui.set_countdown(countdown)

    timer_countdown = QtCore.QTimer()
    timer_countdown.timeout.connect(update_countdown)
    timer_countdown.start(1000)

    # 颜色切换演示
    colors = ["red", "blue", None]
    color_idx = 0
    ui.set_color(colors[color_idx])

    def update_color():
        nonlocal color_idx
        color_idx = (color_idx + 1) % len(colors)
        ui.set_color(colors[color_idx])

    timer_color = QtCore.QTimer()
    timer_color.timeout.connect(update_color)
    timer_color.start(5000)

    # 血量更新演示
    red_hp, blue_hp = 100, 100
    ui.set_red_hp(red_hp)
    ui.set_blue_hp(blue_hp)
    red_dir, blue_dir = -1, -1

    def update_hp():
        nonlocal red_hp, blue_hp, red_dir, blue_dir
        red_hp += red_dir
        blue_hp += blue_dir
        if red_hp <= 0:
            red_hp, red_dir = 0, +1
        if red_hp >= 100:
            red_hp, red_dir = 100, -1
        if blue_hp <= 0:
            blue_hp, blue_dir = 0, +1
        if blue_hp >= 100:
            blue_hp, blue_dir = 100, -1
        ui.set_red_hp(red_hp)
        ui.set_blue_hp(blue_hp)

    timer_hp = QtCore.QTimer()
    timer_hp.timeout.connect(update_hp)
    timer_hp.start(500)

    # 状态切换演示
    status = [
        {"video_fps": None, "uart_connect_state": 0, "tx_rssi": None, "rx_rssi": None, "mqtt_freq": None},
        {"video_fps": 14, "uart_connect_state": 1, "tx_rssi": -20, "rx_rssi": -21, "mqtt_freq": 10},
        {"video_fps": 15, "uart_connect_state": 2, "tx_rssi": -21, "rx_rssi": -20, "mqtt_freq": 9}
    ]
    status_idx = 0

    def update_status():
        nonlocal status_idx
        s = status[status_idx]
        ui.set_video_fps(s["video_fps"])
        ui.set_uart_connect_state(s["uart_connect_state"])
        ui.set_rssi(s["tx_rssi"], s["rx_rssi"])
        ui.set_mqtt_freq(s["mqtt_freq"])
        status_idx = (status_idx + 1) % len(status)

    timer_status = QtCore.QTimer()
    timer_status.timeout.connect(update_status)
    timer_status.start(1000)

    # 队伍名称切换演示
    team_names = [
        ("Red Team Alpha", "Blue Team Beta"),
        ("Crimson Vanguard", "Cobalt Sentinels"),
        ("红方队伍", "蓝方队伍")
    ]
    name_idx = 0
    # 初始设置
    ui.set_red_name(team_names[name_idx][0])
    ui.set_blue_name(team_names[name_idx][1])

    def update_name():
        nonlocal name_idx
        name_idx = (name_idx + 1) % len(team_names)
        ui.set_red_name(team_names[name_idx][0])
        ui.set_blue_name(team_names[name_idx][1])

    timer_names = QtCore.QTimer()
    timer_names.timeout.connect(update_name)
    timer_names.start(4000)

    # 受击打演示
    def update_hit():
        ui.trigger_hit()

    timer_hit = QtCore.QTimer()
    timer_hit.timeout.connect(update_hit)
    timer_hit.start(3000)

    def show_center_text_demo():
        # 演示不同内容和颜色
        ui.set_center_txt("比赛即将开始", "5", "yellow")
        QtCore.QTimer.singleShot(1000, lambda: ui.set_center_txt("比赛即将开始", "4", "yellow"))
        QtCore.QTimer.singleShot(2000, lambda: ui.set_center_txt("比赛即将开始", "3", QtGui.QColor(255, 165, 0)))  # 橙色
        QtCore.QTimer.singleShot(3000, lambda: ui.set_center_txt("比赛即将开始", "2", "red"))
        QtCore.QTimer.singleShot(4000, lambda: ui.set_center_txt("比赛即将开始", "1", "red"))
        QtCore.QTimer.singleShot(5000, lambda: ui.set_center_txt("FIGHT!", "", "#FFFFFF"))  # 白色
        # 6.5秒后清空文本，背景和文字会一起消失
        QtCore.QTimer.singleShot(6500, lambda: ui.set_center_txt(None, None))

    # 延迟1秒后开始演示
    QtCore.QTimer.singleShot(1000, show_center_text_demo)

    # 定时打印
    # def update_print():
    #     print(ui.get_serial_port(), ui.get_video_source(), ui.get_mqtt_url())

    # timer_print = QtCore.QTimer()
    # # timer_print.timeout.connect(update_print)
    # timer_print.start(500)

    ui.loop((1280, 720))


def main():
    logging.basicConfig(format="%(asctime)s | %(levelname)s | %(name)s | %(message)s")

    # test_UIBase()
    test_UI()


if __name__ == "__main__":
    main()
