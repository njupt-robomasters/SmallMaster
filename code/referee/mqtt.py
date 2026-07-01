from amqtt.client import MQTTClient
from amqtt.mqtt.constants import *

import threading
import asyncio
import json
from collections import deque
import time
import logging


BROKER_URL = "mqtt://127.0.0.1:1883"
PUBLISH_FREQ = 10


class MQTT(threading.Thread):

    DEFAULT_CLIENT_MSG = {"hp": None, "uart_connect_state": 0, "video_fps": None, "tx_rssi": None, "rx_rssi": None}

    def __init__(self, level=logging.WARNING):
        super().__init__(daemon=True)

        self.logger = logging.getLogger("MQTT")
        self.logger.setLevel(level)

        # 可读取
        self.red_msg = self.DEFAULT_CLIENT_MSG
        self.blue_msg = self.DEFAULT_CLIENT_MSG

        # 可写入
        self.referee_msg = {
            "countdown_ms": 0, "state": 0, "txt": "",
            "red": {"name": "红方队伍", "hp": 100, "yellow_card_ms": 0, "reset_hp_ms": 0},
            "blue": {"name": "蓝方队伍", "hp": 100, "yellow_card_ms": 0, "reset_hp_ms": 0}
        }

        self._client: MQTTClient = None
        self._red_timestamps = deque()
        self._blue_timestamps = deque()

    @property
    def red_freq(self) -> float | None:
        timestamps = self._red_timestamps
        while timestamps and time.time() - timestamps[0] > 1.0:
            timestamps.popleft()

        if len(timestamps) == 0:
            self.red_msg = self.DEFAULT_CLIENT_MSG
            return None
        else:
            return len(timestamps)

    @property
    def blue_freq(self) -> float | None:
        timestamps = self._blue_timestamps
        while timestamps and time.time() - timestamps[0] > 1.0:
            timestamps.popleft()

        if len(timestamps) == 0:
            self.blue_msg = self.DEFAULT_CLIENT_MSG
            return None
        else:
            return len(timestamps)

    def run(self):
        self.logger.info("MQTT线程启动")
        asyncio.run(self._main_async_loop())

    async def _main_async_loop(self):
        while True:
            self.logger.info(f"MQTT正在连接: {BROKER_URL}")
            self._client = MQTTClient(config={"connection_timeout": 1, "auto_reconnect": False})
            try:
                await self._client.connect(BROKER_URL)
            except Exception as e:
                self.logger.info(f"MQTT连接失败: {e}")
                await asyncio.sleep(0.1)
                continue

            self.logger.info("MQTT连接成功")
            self._is_connected = True

            # 订阅和发布
            await asyncio.gather(self._publish_loop(), self._subscribe_loop())

    async def _publish_loop(self):
        while True:
            payload_str = json.dumps(self.referee_msg, ensure_ascii=False)
            try:
                await self._client.publish("/referee", payload_str.encode("utf-8"), qos=QOS_1)
            except Exception as e:
                self.logger.error(f"MQTT发布错误: {e}")
                await self._reset()
                return

            await asyncio.sleep(1 / PUBLISH_FREQ)

    async def _subscribe_loop(self):
        await self._client.subscribe([("/red", QOS_1), ("/blue", QOS_1)])
        while True:
            try:
                mqtt_msg = await self._client.deliver_message()
                topic = mqtt_msg.topic
                data = mqtt_msg.data
            except Exception as e:
                self.logger.error(f"MQTT订阅错误: {e}")
                await self._reset()
                return

            try:
                msg = json.loads(data)
            except Exception as e:
                self.logger.warning(f"JSON反序列化报错: {e}, data: {data}")

            if topic == "/red":
                self.red_msg = msg
                self.logger.debug(f"red_message: {msg}")
                self._red_timestamps.append(time.time())
                self.red_freq  # 防止时间戳堆积
                self.logger.debug(f"red_freq: {self.red_freq}")
            elif topic == "/blue":
                self.blue_msg = msg
                self.logger.debug(f"blue_message: {msg}")
                self._blue_timestamps.append(time.time())
                self.blue_freq  # 防止时间戳堆积
                self.logger.debug(f"blue_freq: {self.blue_freq}")

    async def _reset(self):
        if self._client:
            await self._client.disconnect()
            self._client = None
        self.red_msg = self.DEFAULT_CLIENT_MSG
        self.blue_msg = self.DEFAULT_CLIENT_MSG
        self._red_timestamps.clear()
        self._blue_timestamps.clear()


if __name__ == "__main__":
    logging.basicConfig(format="%(asctime)s | %(levelname)s | %(name)s | %(message)s")

    mqtt = MQTT()
    mqtt.logger.setLevel(logging.DEBUG)
    mqtt.start()

    while True:
        time.sleep(1)
