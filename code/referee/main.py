import logging

from mqtt_broker import MQTT_Broker
from mqtt import MQTT
from ui import UI

if __name__ == "__main__":
    logging.basicConfig(level=logging.ERROR, format='%(asctime)s | %(levelname)s | %(name)s | %(message)s')

    mqtt_broker = MQTT_Broker()
    mqtt_broker.start()

    mqtt = MQTT()
    mqtt.start()

    ui = UI(mqtt)
    ui.loop()
