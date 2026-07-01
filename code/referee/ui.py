import tkinter as tk
from tkinter import ttk, font, PhotoImage
import time
import logging
import sys
import os

from mqtt import MQTT, PUBLISH_FREQ

MATCH_SECONDS = 180

# UI 颜色常量
COLOR_RED = "#E74C3C"
COLOR_RED_A = "#C0392B"
COLOR_BLUE = "#3498DB"
COLOR_BLUE_A = "#2980B9"
COLOR_YELLOW = "#F1C40F"
COLOR_YELLOW_A = "#F39C12"
COLOR_GREEN = "#2ECC71"
COLOR_GREEN_A = "#27AE60"
COLOR_BG = "#ECF0F1"
COLOR_TEXT = "#2C3E50"
COLOR_DISCONNECTED = "#E74C3C"
COLOR_TROUGH = "#BDC3C7"


def get_resource(path):
    if getattr(sys, 'frozen', False):
        # 打包后的情况
        base_path = sys._MEIPASS
        return os.path.join(base_path, path)
    else:
        # 开发环境
        return path


class UI():
    def __init__(self, mqtt: MQTT, level=logging.WARNING):
        self.logger = logging.getLogger("UI")
        self.logger.setLevel(level)

        self._mqtt = mqtt

        self._match_end_time = None

        self._root = tk.Tk()
        self._root.title("RoboMaster校内赛裁判端")
        img = PhotoImage(file=get_resource("./assets/logo.png"))
        self._root.tk.call('wm', 'iconphoto', self._root._w, img)
        # self._root.iconbitmap(get_resource("./assets/logo.png"))
        self._root.configure(bg=COLOR_BG)

        self._create_styles_and_fonts()
        self._create_widgets()
        self._update_loop()

    def _create_styles_and_fonts(self):
        self.fonts = {
            "countdown": font.Font(family="Arial", size=48, weight="bold"),
            "status_txt": font.Font(family="Arial", size=14),
            "title": font.Font(family="Arial", size=14, weight="bold"),
            "status": font.Font(family="Consolas", size=10),
            "status_bold": font.Font(family="Consolas", size=10, weight="bold"),
            "button": font.Font(family="Arial", size=10, weight="bold"),
            "entry": font.Font(family="Arial", size=11),
            "hp": font.Font(family="Arial", size=12, weight="bold")
        }
        s = ttk.Style()
        s.theme_use("clam")
        s.configure(".", background=COLOR_BG, foreground=COLOR_TEXT)
        s.configure("TFrame", background=COLOR_BG)
        s.configure("TLabel", background=COLOR_BG, foreground=COLOR_TEXT)
        s.configure("TButton", font=self.fonts["button"], padding=(10, 6))
        s.configure("TLabelframe", background=COLOR_BG, borderwidth=1, relief="solid")
        s.configure("TLabelframe.Label", background=COLOR_BG, foreground=COLOR_TEXT, font=self.fonts["title"])
        s.configure("red.Horizontal.TProgressbar", foreground=COLOR_RED, background=COLOR_RED, troughcolor=COLOR_TROUGH)
        s.configure("blue.Horizontal.TProgressbar", foreground=COLOR_BLUE, background=COLOR_BLUE, troughcolor=COLOR_TROUGH)
        s.configure("yellow.TButton", background=COLOR_YELLOW, foreground=COLOR_TEXT)
        s.map("yellow.TButton", background=[("active", COLOR_YELLOW_A)])
        s.configure("red.TButton", background=COLOR_RED, foreground="white")
        s.map("red.TButton", background=[("active", COLOR_RED_A)])
        s.configure("green.TButton", background=COLOR_GREEN, foreground="white")
        s.map("green.TButton", background=[("active", COLOR_GREEN_A)])

    def _create_widgets(self):
        self.countdown_label = ttk.Label(self._root, text="0", font=self.fonts["countdown"])
        self.countdown_label.pack(pady=(10, 0))
        self.text_label = ttk.Label(self._root, text="", font=self.fonts["status_txt"])
        self.text_label.pack(pady=(0, 5))

        main_frame = ttk.Frame(self._root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=0)
        main_frame.grid_columnconfigure(0, weight=1)
        main_frame.grid_columnconfigure(1, weight=1)

        self.red_widgets = self._create_team_panel(main_frame, "red", 0)
        self.blue_widgets = self._create_team_panel(main_frame, "blue", 1)

        control_frame = ttk.Frame(self._root)
        control_frame.pack(pady=15)
        buttons = [
            ("重置比赛", self.reset_match),
            ("赛前2分钟", lambda: self.start_pre_match_countdown(120)),
            ("赛前30秒", lambda: self.start_pre_match_countdown(30)),
            ("赛前5秒", lambda: self.start_pre_match_countdown(5)),
            ("平局", self.set_draw)
        ]
        for text, command in buttons:
            ttk.Button(control_frame, text=text, command=command).pack(side=tk.LEFT, padx=8)

    def _create_team_panel(self, parent, color, column):
        widgets = {}
        frame = ttk.LabelFrame(parent, text="红方" if color == "red" else "蓝方")
        frame.grid(row=0, column=column, padx=10, pady=5, sticky="nsew")

        name_frame = ttk.Frame(frame)
        name_frame.pack(fill=tk.X, padx=5, pady=(5, 8))
        widgets["name_var"] = tk.StringVar(value=self._mqtt.referee_msg[color]["name"])
        ttk.Entry(name_frame, textvariable=widgets["name_var"], font=self.fonts["entry"]).pack(side=tk.LEFT, expand=True, fill=tk.X)
        ttk.Button(name_frame, text="应用", command=lambda: self.set_team_name(color)).pack(side=tk.LEFT, padx=(5, 0))

        hp_container = tk.Frame(frame, height=28)
        hp_container.pack(fill=tk.X, padx=5, pady=5)
        hp_container.pack_propagate(False)
        widgets["hp_var"] = tk.IntVar(value=100)
        ttk.Progressbar(hp_container, variable=widgets["hp_var"], style=f"{color}.Horizontal.TProgressbar").pack(fill=tk.BOTH, expand=True)
        widgets["hp_label"] = tk.Label(hp_container, text="100", font=self.fonts["hp"], fg="white",
                                       bg=COLOR_RED if color == "red" else COLOR_BLUE)
        widgets["hp_label"].place(relx=0.5, rely=0.5, anchor="center")

        status_grid = ttk.Frame(frame, padding=(0, 8))
        status_grid.pack()
        status_labels = [[("客户端:", 0, "client_hz"), ("图传:", 3, "fps")], [("装甲板:", 0, "uart_state"), ("TX:", 3, "tx"), ("RX:", 6, "rx")]]
        for r, row in enumerate(status_labels):
            for i, (text, col, key) in enumerate(row):
                ttk.Label(status_grid, text=text, font=self.fonts["status_bold"]).grid(row=r, column=col, sticky="e")
                widgets[f"{key}_label"] = ttk.Label(status_grid, text="N/A", font=self.fonts["status"])
                widgets[f"{key}_label"].grid(row=r, column=col+1, sticky="w", padx=(2, 0))
                if i < len(row) - 1:
                    ttk.Label(status_grid, text="|").grid(row=r, column=col+2, padx=5)

        btn_frame = ttk.Frame(frame)
        btn_frame.pack(pady=8)
        team_buttons = [("黄牌警告", "yellow.TButton", lambda: self.give_yellow_card(color)), ("红牌判罚", "red.TButton",
                                                                                           lambda: self.give_red_card(color)), ("血量重置", "green.TButton", lambda: self.reset_hp(color))]
        for text, style, cmd in team_buttons:
            ttk.Button(btn_frame, text=text, style=style, command=cmd).pack(side=tk.LEFT, padx=5)
        return widgets

    def _update_loop(self):
        self._update_referee_msg()

        self._update_title()
        self._update_team_ui("red")
        self._update_team_ui("blue")

        self._root.after(int(1000 / PUBLISH_FREQ), self._update_loop)

    def _update_referee_msg(self):
        # 从客户端同步血量
        red_hp = self._mqtt.red_msg["hp"]
        if red_hp is not None:
            self._mqtt.referee_msg["red"]["hp"] = red_hp
        blue_hp = self._mqtt.blue_msg["hp"]
        if blue_hp is not None:
            self._mqtt.referee_msg["blue"]["hp"] = blue_hp

        # 比赛未开始
        if self._match_end_time is None:
            return

        remaining = self._match_end_time - time.time()

        # 倒计时更新
        if round(MATCH_SECONDS - remaining) < 0:  # 准备阶段
            self._mqtt.referee_msg["countdown_ms"] = int(round((MATCH_SECONDS - remaining)*1000))
        elif round(remaining) > 0:  # 比赛进行中
            self._mqtt.referee_msg["countdown_ms"] = int(round(remaining*1000))

        # 比赛结束判定
        new_state, new_txt = None, None
        # 血量判定
        red_hp, blue_hp = self._mqtt.referee_msg["red"]["hp"], self._mqtt.referee_msg["blue"]["hp"]
        if red_hp <= 0 and blue_hp <= 0:
            new_state, new_txt = 3, "双方血量均耗尽"
        elif red_hp <= 0:
            new_state, new_txt = 2, "红方血量耗尽"
        elif blue_hp <= 0:
            new_state, new_txt = 1, "蓝方血量耗尽"
        # 时间到
        elif remaining <= 0:
            if red_hp > blue_hp:
                new_state, new_txt = 1, "时间到，红方血量占优"
            elif blue_hp > red_hp:
                new_state, new_txt = 2, "时间到，蓝方血量占优"
            else:
                new_state, new_txt = 3, "时间到，双方血量相同"

        if new_state is not None:
            self._mqtt.referee_msg.update({"countdown_ms": 0, "state": new_state, "txt": new_txt})
            self._match_end_time = None

    def _update_title(self):
        """刷新标题栏"""
        seconds_int = int(round(self._mqtt.referee_msg["countdown_ms"] / 1000))
        if seconds_int >= 0:
            m, s = seconds_int // 60, seconds_int % 60
            self.countdown_label.config(text=f"{m}:{s:02d}")
        else:
            abs_seconds = abs(seconds_int)
            m, s = abs_seconds // 60, abs_seconds % 60
            self.countdown_label.config(text=f"-{m}:{s:02d}")
        self.text_label.config(text=self._mqtt.referee_msg["txt"])

    def _update_team_ui(self, color):
        """根据内部状态刷新单个队伍的UI面板"""
        widgets = self.red_widgets if color == "red" else self.blue_widgets
        team_msg = self._mqtt.red_msg if color == "red" else self._mqtt.blue_msg

        # 血量
        hp = self._mqtt.referee_msg[color]["hp"]
        if hp is not None:
            widgets["hp_var"].set(hp)
            widgets["hp_label"].config(text=str(hp), fg="white")

        # 客户端报文频率
        freq = self._mqtt.red_freq if color == "red" else self._mqtt.blue_freq
        if freq is None:
            widgets["client_hz_label"].config(text="未连接", foreground=COLOR_DISCONNECTED)
        else:
            text = f"{freq:2.0f}Hz"
            widgets["client_hz_label"].config(text=text, foreground=COLOR_TEXT)

        # 图传帧率
        video_fps = team_msg.get("video_fps")
        if video_fps is None:
            widgets["fps_label"].config(text="未连接", foreground=COLOR_DISCONNECTED)
        else:
            text = f"{video_fps:.0f}fps"
            widgets["fps_label"].config(text=text, foreground=COLOR_TEXT)

        # 串口连接状态
        uart_connect_state = team_msg.get("uart_connect_state")
        if uart_connect_state == 0:
            widgets["uart_state_label"].config(text="串口未连接", foreground=COLOR_DISCONNECTED)
        elif uart_connect_state == 1:
            widgets["uart_state_label"].config(text="无线未连接", foreground=COLOR_DISCONNECTED)
        elif uart_connect_state == 2:
            widgets["uart_state_label"].config(text="无线已连接", foreground=COLOR_TEXT)

        # 发射信号强度
        tx_rssi = team_msg.get("tx_rssi")
        if uart_connect_state != 2 or tx_rssi is None:
            widgets["tx_label"].config(text="未连接", foreground=COLOR_DISCONNECTED)
        else:
            text = f"{tx_rssi:.0f}dBm"
            widgets["tx_label"].config(text=text, foreground=COLOR_TEXT)

        # 接收信号强度
        rx_rssi = team_msg.get("rx_rssi")
        if uart_connect_state != 2 or rx_rssi is None:
            widgets["rx_label"].config(text="未连接", foreground=COLOR_DISCONNECTED)
        else:
            text = f"{rx_rssi:.0f}dBm"
            widgets["rx_label"].config(text=text, foreground=COLOR_TEXT)

    def reset_match(self):
        self._mqtt.referee_msg.update({"countdown_ms": 0, "state": 0, "txt": ""})
        self._mqtt.referee_msg["red"]["reset_hp_ms"] = int(time.time() * 1000)
        self._mqtt.referee_msg["blue"]["reset_hp_ms"] = int(time.time() * 1000)
        self._match_end_time = None

    def start_pre_match_countdown(self, seconds):
        self._mqtt.referee_msg.update({"countdown_ms": -seconds, "state": 0, "txt": ""})
        self._match_end_time = time.time() + seconds + MATCH_SECONDS

    def set_draw(self):
        self._mqtt.referee_msg.update({"countdown_ms": 0, "state": 3, "txt": "主裁判判定平局"})
        self._match_end_time = None

    def give_red_card(self, color):
        winner_state = 2 if color == "red" else 1
        winner_name = "蓝方" if color == "red" else "红方"
        self._mqtt.referee_msg.update({"countdown_ms": 0, "state": winner_state, "txt": f"主裁判判罚，{winner_name}获胜"})
        self._match_end_time = None

    def give_yellow_card(self, color):
        self._mqtt.referee_msg[color]["yellow_card_ms"] = int(time.time() * 1000)

    def reset_hp(self, color):
        self._mqtt.referee_msg[color]["reset_hp_ms"] = int(time.time() * 1000)

    def set_team_name(self, color):
        widgets = self.red_widgets if color == "red" else self.blue_widgets
        self._mqtt.referee_msg[color]["name"] = widgets["name_var"].get()

    def loop(self):
        self._root.mainloop()


if __name__ == "__main__":
    logging.basicConfig(format="%(asctime)s | %(levelname)s | %(name)s | %(message)s")

    mqtt = MQTT(logging.DEBUG)
    mqtt.start()

    ui = UI(mqtt, logging.DEBUG)
    ui.loop()
