from amqtt.broker import Broker

import threading
import asyncio
import time
import logging


class MQTT_Broker(threading.Thread):
    def __init__(self, level=logging.WARNING):
        super().__init__(daemon=True)

        self.logger = logging.getLogger("Broker")
        self.logger.setLevel(level)

    def run(self):
        self.logger.info("Broker线程启动")
        asyncio.run(self._main_async_loop())

    async def _main_async_loop(self):
        broker = Broker()
        await broker.start()
        while True:
            await asyncio.sleep(1)


if __name__ == "__main__":
    logging.basicConfig(format="%(asctime)s | %(levelname)s | %(name)s | %(message)s")

    mqtt_broker = MQTT_Broker(logging.DEBUG)
    mqtt_broker.start()

    while True:
        time.sleep(1)
