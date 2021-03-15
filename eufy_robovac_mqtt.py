import paho.mqtt.client as mqtt
import yaml
import json

import asyncio
import logging
from pprint import pprint
import sys

from eufy_robovac.robovac import Robovac
from eufy_robovac.robovac import WorkStatus
from eufy_robovac.robovac import CleanSpeed


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
eufy_state = None

# The callback for when the mqtt client receives a CONNACK response from the broker.
def on_mqtt_connect(client, userdata, flags, rc):
    print("Connected with result code "+str(rc))

    # Subscribing in on_mqtt_connect() means that if we lose the connection and
    # reconnect then subscriptions will be renewed.
    client.subscribe((mqtt_prefix + "command", 0), (mqtt_prefix + "set_fan_speed", 0))
    #TODO publish unavailable and attempt to connect to the robovac
    asyncio.run_coroutine_threadsafe(rbv.async_connect(eufy_connected_callback), asyncio_loop)

# The callback for when a PUBLISH message is received from the mqtt broker.
def on_mqtt_message(client, userdata, msg):
    pprint(msg.topic+" "+str(msg.payload))
    # To call client need
    # asyncio.run_coroutine_threadsafe(coro, asyncio_loop)

    if msg.topic == mqtt_prefix + "command":
        if msg.payload == "locate":
            asyncio.run_coroutine_threadsafe(rbv.async_find_robot(eufy_find_robot_callback), asyncio_loop)
            pass
        elif msg.payload == "clean_spot":
            asyncio.run_coroutine_threadsafe(rbv.async_set_work_mode(Robovac.work_mode.SPOT, eufy_set_work_mode_callback), asyncio_loop)
        elif msg.payload == "return_to_base":
            asyncio.run_coroutine_threadsafe(rbv.async_go_home(eufy_go_home_callback), asyncio_loop)
        elif msg.payload == "start_pause":
            asyncio.run_coroutine_threadsafe(rbv.async_play(eufy_play_callback), asyncio_loop)
        elif msg.payload == "stop":
            asyncio.run_coroutine_threadsafe(rbv.async_pause(eufy_pause_callback), asyncio_loop)

    elif msg.topic == mqtt_prefix + "fan_speed":
        pass

mqtt_client = mqtt.Client()
mqtt_client.on_connect = on_mqtt_connect
mqtt_client.on_message = on_mqtt_message
mqtt_client.connect_async(mqtt_address, mqtt_port, 60)
mqtt_client.will_set(mqtt_prefix + "available", payload="offline")
mqtt_client.loop_start()

async def eufy_connected_callback(message, device):
    pprint(device.state)
    eufy_state = device.state
    mqtt_client.publish(mqtt_prefix + "available", "online")
    mqtt_client.publish(mqtt_prefix + "state", ha_state(device.state))

async def eufy_play_callback(message, device):
    pprint(device.state)
    eufy_state = device.state
    mqtt_client.publish(mqtt_prefix + "state", ha_state(device.state))

async def eufy_pause_callback(message, device):
    pprint(device.state)
    eufy_state = device.state
    mqtt_client.publish(mqtt_prefix + "state", ha_state(device.state))

async def eufy_go_home_callback(message, device):
    pprint(device.state)
    eufy_state = device.state
    mqtt_client.publish(mqtt_prefix + "state", ha_state(device.state))

async def eufy_find_robot_callback(message, device):
    pprint(device.state)
    eufy_state = device.state
    mqtt_client.publish(mqtt_prefix + "state", ha_state(device.state))

async def eufy_set_work_mode_callback(message, device):
    pprint(device.state)
    eufy_state = device.state
    mqtt_client.publish(mqtt_prefix + "state", ha_state(device.state))

def ha_state(eufy_state):
    """ Converts eufy state into homeassistant state"""
    convert_state = {WorkStatus.RUNNING.value:"cleaning",
              WorkStatus.CHARGING.value:"docked",
              WorkStatus.STAND_BY.value:"paused",
              WorkStatus.SLEEPING.value:"idle",
              WorkStatus.RECHARGE_NEEDED.value:"returning",
              WorkStatus.COMPLETED.value:"docked"}
    # Cleaning
    # docked,
    # paused,
    # idle,
    # returning,
    # error
    convert_fan = {CleanSpeed.NO_SUCTION.value:"min",
                 CleanSpeed.STANDARD.value:"medium",
                 CleanSpeed.BOOST_IQ.value:"high",
                 CleanSpeed.MAX.value:"max"}
    ha_state = convert_state[eufy_state[Robovac.WORK_STATUS]]
    fan_speed = convert_fan[eufy_state[Robovac.CLEAN_SPEED]]
    return json.dumps({"state":  ha_state, "battery_level": eufy_state[Robovac.BATTERY_LEVEL], "fan_speed": fan_speed})

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
