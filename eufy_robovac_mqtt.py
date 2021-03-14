import paho.mqtt.client as mqtt
import yaml

import asyncio
import logging
from pprint import pprint
import sys

from eufy_robovac.robovac import Robovac

with open(".env", "r") as f:
    config = yaml.load(f, Loader=yaml.SafeLoader)

mqtt_address = config["mqtt"]["address"]
mqtt_port = config["mqtt"]["port"]
mqtt_user = config["mqtt"]["user"]
mqtt_pwd = config["mqtt"]["pwd"]
mqtt_prefix = config["mqtt"]["prefix"]
localKey = config["eufy"]["localKey"]
devId = config["eufy"]["devId"]
ip = config["eufy"]["ip"]

asyncio_loop = asyncio.get_event_loop()
rbv = Robovac(devId, ip, local_key=localKey)

# The callback for when the mqtt client receives a CONNACK response from the broker.
def on_mqtt_connect(client, userdata, flags, rc):
    print("Connected with result code "+str(rc))

    # Subscribing in on_mqtt_connect() means that if we lose the connection and
    # reconnect then subscriptions will be renewed.
    client.subscribe((mqtt_prefix + "command", 0), (mqtt_prefix + "set_fan_speed", 0))
    #TODO publish unavailable and attempt to connect to the robovac
    # await r.async_connect(connected_callback)
    asyncio.run_coroutine_threadsafe(rbv.async_connect(eufy_connected_callback), asyncio_loop)

# The callback for when a PUBLISH message is received from the mqtt broker.
def on_mqtt_message(client, userdata, msg):
    pprint(msg.topic+" "+str(msg.payload))
    # To call client need
    # asyncio.run_coroutine_threadsafe(coro, asyncio_loop)

mqtt_client = mqtt.Client()
mqtt_client.on_connect = on_mqtt_connect
mqtt_client.on_message = on_mqtt_message
mqtt_client.connect_async(mqtt_address, mqtt_port, 60)
mqtt_client.will_set(mqtt_prefix + "available", payload="offline")
mqtt_client.loop_start()

async def connected_callback(message, device):
    pprint(device.state)

async def eufy_connected_callback(message, device):
    pprint(device.state)
    mqtt_client.publish(mqtt_prefix + "available", "online")
    mqtt_client.publish(mqtt_prefix + "state", device.state)

async def async_main(device_id, ip, local_key=None, *args, **kwargs):
    r = Robovac(device_id, ip, local_key, *args, **kwargs)
    await r.async_connect(connected_callback)
    await r.async_disconnect()

def ha_state(eufy_state):
    """ Converts eufy state into homeassistant state"""
    convert_state = {WorkStatus.RUNNING:"cleaning",
              WorkStatus.CHARGING:"docked",
              WorkStatus.STAND_BY:"paused",
              WorkStatus.SLEEPING:"idle",
              WorkStatus.RECHARGE_NEEDED:"returning",
              WorkStatus.COMPLETED:"docked"}
     # Cleaning
     # docked,
     # paused,
     # idle,
     # returning,
     # error
     convert_fan = {CleanSpeed.NO_SUCTION:"min",
                 CleanSpeed.STANDARD:"medium",
                 CleanSpeed.BOOST_IQ:"high",
                 CleanSpeed.MAX:"max"}
     ha_state = convert_state[eufy_state[Robovac.WORK_MODE]]
     fan_speed = convert_fan[eufy_state[Robovac.CLEAN_SPEED]]
     return json.dumps("state",  ha_state, "battery_level", eufy_state[Robovac.BATTERY_LEVEL], "fan_speed": fan_speed)

def main(*args, **kwargs):
    if not args:
        args = sys.argv[1:]
    #asyncio.run(async_main(*args, **kwargs))
    try:
        asyncio_loop.run_forever()
    except:
        mqtt_client.publish(mqtt_prefix + "available", "offline")
        mqtt_client.disconnect()

if __name__ == '__main__':
    main(*sys.argv[1:])
