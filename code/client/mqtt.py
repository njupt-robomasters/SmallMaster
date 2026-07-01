from amqtt.client import MQTTClient
from amqtt.mqtt.constants import *

import threading
import asyncio
import json
from collections import deque
import time
import logging
from typing import Optional

PUBLISH_FREQ = 10


class MQTT(threading.Thread):

    DEFAULT_REFEREE_MSG = {
        "countdown_ms": None, "state": None, "txt": None,
        "red": {"name": None, "hp": None, "yellow_card_ms": None, "reset_hp_ms": None},
        "blue": {"name": None, "hp": None, "yellow_card_ms": None, "reset_hp_ms": None}
    }

    def __init__(self, level=logging.WARNING):
        super().__init__(daemon=True)

        self.logger = logging.getLogger("MQTT")
        self.logger.setLevel(level)

        # 可读取
        self.referee_msg = self.DEFAULT_REFEREE_MSG

        # 可写入
        self.color: Optional[str] = None # 为None时不发送MQTT消息
        self.client_msg = {"hp": 100, "com_is_connected": False, "video_fps": 0, "tx_rssi": None, "rx_rssi": None}

        self._broker_url: str = None
        self._client: MQTTClient = None
        self._timestamps = deque()

    def set_broker_url(self, broker_url: str):
        if self._broker_url == broker_url:
            return

        self.logger.info(f"MQTT Broker URL变更: {self._broker_url} -> {broker_url}")
        self._broker_url = broker_url

        asyncio.run(self._reset())

    @property
    def freq(self) -> float | None:
        timestamps = self._timestamps
        while timestamps and time.time() - timestamps[0] > 1.0:
            timestamps.popleft()

        if len(timestamps) == 0:
            self.referee_msg = self.DEFAULT_REFEREE_MSG
            return None
        else:
            return len(timestamps)

    def run(self):
        self.logger.info("MQTT线程启动")
        asyncio.run(self._main_async_loop())

    async def _main_async_loop(self):
        while True:
            if self._broker_url is None:
                await asyncio.sleep(0.1)
                continue

            self.logger.info(f"MQTT正在连接: {self._broker_url}")
            self._client = MQTTClient(config={"connection_timeout": 1, "auto_reconnect": False})
            try:
                await self._client.connect(self._broker_url)
            except Exception as e:
                self.logger.info(f"MQTT连接失败: {e}")
                await asyncio.sleep(0.1)
                continue

            self.logger.info("MQTT连接成功")

            # 订阅和发布
            await asyncio.gather(self._publish_loop(), self._subscribe_loop())

    async def _publish_loop(self):
        while True:
            if self.color is None:
                await asyncio.sleep(1 / PUBLISH_FREQ)
                continue

            msg = json.dumps(self.client_msg, ensure_ascii=False)
            try:
                await self._client.publish("/" + self.color, msg.encode("utf-8"), qos=QOS_1)
            except Exception as e:
                self.logger.error(f"MQTT发布错误: {e}")
                await self._reset()
                return

            await asyncio.sleep(1 / PUBLISH_FREQ)

    async def _subscribe_loop(self):
        await self._client.subscribe([("/referee", QOS_1)])
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

            if topic == "/referee":
                self.referee_msg = msg
                self.logger.debug(f"referee_message: {msg}")
                self._timestamps.append(time.time())
                self.freq  # 防止时间戳堆积
                self.logger.debug(f"freq: {self.freq}")

    async def _reset(self):
        if self._client:
            await self._client.disconnect()
            self._client = None
        self.referee_msg = self.DEFAULT_REFEREE_MSG
        self._timestamps.clear()


if __name__ == "__main__":
    logging.basicConfig(format="%(asctime)s | %(levelname)s | %(name)s | %(message)s")

    mqtt = MQTT(logging.INFO)
    mqtt.start()

    mqtt.set_broker_url("mqtt://127.0.0.1:1883")
    mqtt.color = "red"

    while True:
        time.sleep(1)
