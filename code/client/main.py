from PySide6 import QtCore, QtGui
import time
import logging

from uart import UART
from video import Video
from mqtt import MQTT
from ui import UI

FULL_SCREEN = True


class Watch:

    def __init__(self):
        self.data = None

    def update(self, data) -> bool:
        if data != self.data:  # 跳变
            if data is not None: # 不是断联跳变
                if self.data is not None:  # 不是第一次跳变
                    self.data = data
                    return True
        self.data = data
        return False

    def reset(self):
        self.data = None


class Game:
    def __init__(self):
        self.uart = UART()
        self.video = Video()
        self.mqtt = MQTT()
        self.ui = UI()

        # 状态变量
        self.hp = 100
        self.watch_hit_cnt = Watch()
        self.watch_color = Watch()
        self.watch_reset_hp_ms = Watch()
        self.watch_yellow_card_ms = Watch()
        self.yellow_card_start_time = None

    def start_and_loop(self):
        # 启动各模块的线程
        self.uart.start()
        self.video.start()
        self.mqtt.start()

        # 创建定时任务
        timer = QtCore.QTimer()
        timer.timeout.connect(self._update)
        timer.start(10)  # 100Hz

        # UI主循环
        if FULL_SCREEN:
            self.ui.loop()
        else:
            self.ui.loop((1280, 720))

    def _update(self):
        self._update_ui()
        self._update_com()
        self._update_video()
        self._update_mqtt()

    def _update_ui(self):
        # 1. 从串口更新数据
        
        # 串口连接状态
        self.ui.set_uart_connect_state(self.uart.connect_state)
        
        # RSSI
        self.ui.set_rssi(self.uart.tx_rssi, self.uart.rx_rssi)
        
        # 颜色
        color = self.uart.color
        self.ui.set_color(color)
        
        # 击打检测
        if self.watch_hit_cnt.update(self.uart.hit_cnt):
            if self.uart.hit_cnt != 0: # 防止装甲板重启后扣血
                self.hp -= 1
                self.ui.trigger_hit()
        
        # 设置血量
        if color == 'red':
            self.ui.set_red_hp(self.hp)
        elif color == 'blue':
            self.ui.set_blue_hp(self.hp)

        # 2. 从图传更新数据
        self.ui.set_frame(self.video.frame)
        self.ui.set_video_fps(self.video.fps)

        # 3. 从MQTT更新数据
        # MQTT频率
        self.ui.set_mqtt_freq(self.mqtt.freq)

        # 顶部比赛信息
        if self.mqtt.referee_msg["countdown_ms"] is not None:
            countdown = self.mqtt.referee_msg["countdown_ms"] / 1000
        else:
            countdown = None
        self.ui.set_countdown(countdown)
        self.ui.set_red_name(self.mqtt.referee_msg["red"]["name"])
        self.ui.set_blue_name(self.mqtt.referee_msg["blue"]["name"])
        self.ui.set_red_hp(self.mqtt.referee_msg["red"]["hp"])
        self.ui.set_blue_hp(self.mqtt.referee_msg["blue"]["hp"])

        # 颜色变化时，防止额外的重置血量和黄牌警告
        if self.watch_color.update(color):
            self.watch_reset_hp_ms.reset()
            self.watch_yellow_card_ms.reset()

        # 重置血量
        if color:  # 串口连上了，能获取到颜色
            reset_hp_ms = self.mqtt.referee_msg[color]["reset_hp_ms"]
            if self.watch_reset_hp_ms.update(reset_hp_ms):
                self.hp = 100

        # 黄牌警告
        if color:  # 串口连上了，能获取到颜色
            yellow_card_ms = self.mqtt.referee_msg[color]["yellow_card_ms"]
            if self.watch_yellow_card_ms.update(yellow_card_ms):
                self.hp -= 10  # 扣血10%
                self.yellow_card_start_time = time.time()

        # 中心文字
        state = self.mqtt.referee_msg["state"]
        txt = self.mqtt.referee_msg["txt"]
        if state == 1:  # 红方胜
            if self.uart.color == "red":
                RED = QtGui.QColor(255, 84, 84)
                self.ui.set_center_txt("胜利", txt, RED)
            elif self.uart.color == "blue":
                self.ui.set_center_txt("失败", txt, "white")
        elif state == 2:  # 蓝方胜
            if self.uart.color == "red":
                self.ui.set_center_txt("失败", txt, "white")
            elif self.uart.color == "blue":
                BLUE = QtGui.QColor(88, 140, 255)
                self.ui.set_center_txt("胜利", txt, BLUE)
        elif state == 3:  # 平局
            self.ui.set_center_txt("平局", txt, "white")
        elif self.yellow_card_start_time is not None:  # 黄牌警告未结束
            remaining = int(round(self.yellow_card_start_time + 5 - time.time()))
            if remaining <= 0:
                self.yellow_card_start_time = None
            self.ui.set_center_txt("黄牌", f"扣血10点，{remaining}秒后消失", "yellow")
        elif countdown and countdown >= -5 and countdown <= 0:
            self.ui.set_center_txt(str(int(round(-countdown))), "比赛即将开始", "white")
        else:
            self.ui.set_center_txt("", "")

    def _update_com(self):
        # 设置串口号
        self.uart.set_port(self.ui.get_serial_port())
        
        # 设置键鼠报文
        self.uart.dbus_packet = self.ui.get_dbus_packet()

    def _update_video(self):
        # 设置视频源
        self.video.set_source(self.ui.get_video_source())

    def _update_mqtt(self):
        # 设置MQTT地址
        self.mqtt.set_broker_url(self.ui.get_mqtt_url())

        # 设置MQTT颜色
        self.mqtt.color = self.uart.color

        # 设置MQTT消息
        self.mqtt.client_msg = {"hp": self.hp,
                                "uart_connect_state": self.uart.connect_state,
                                "video_fps": self.video.fps,
                                "tx_rssi": self.uart.tx_rssi,
                                "rx_rssi": self.uart.rx_rssi
                                }


def main():
    logging.basicConfig(level=logging.ERROR, format='%(asctime)s | %(levelname)s | %(name)s | %(message)s')

    game = Game()
    game.start_and_loop()


if __name__ == "__main__":
    main()
