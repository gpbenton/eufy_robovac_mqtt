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


class EufyMqtt:
    def __init__(self, config):
        self.mqtt_address = config["mqtt"]["address"]
        self.mqtt_port = config["mqtt"]["port"]
        self.mqtt_prefix = config["mqtt"]["prefix"]
        self.will_topic = self.mqtt_prefix + "available"
        self.state_topic = self.mqtt_prefix + "state"
        self.command_topic = self.mqtt_prefix + "command"
        self.fan_speed_topic = self.mqtt_prefix + "fan_speed"
        self.mqtt_client = mqtt.Client()
        self.mqtt_client.username_pw_set(config["mqtt"]["user"], config["mqtt"]["pwd"])
        self.mqtt_client.on_connect = self.on_mqtt_connect
        self.mqtt_client.on_message = self.on_mqtt_message
        self.mqtt_client.will_set(self.will_topic, payload="offline")
        self.mqtt_client.loop_start()

    def disconnect(self):
        self.publish(self.will_topic, "offline")
        self.mqtt_client.disconnect()

    def publish(self, topic, payload):
        self.mqtt_client.publish(topic, payload)

    def publish_online(self):
        self.mqtt_client.publish(self.will_topic, "online")

    def publish_state(self, state):
        self.mqtt_client.publish(self.state_topic, state)


    def user_data_set(self, eufy_instance):
        self.mqtt_client.user_data_set(eufy_instance)
        self.mqtt_client.connect_async(self.mqtt_address, self.mqtt_port, 60)

    # The callback for when the mqtt client receives a CONNACK response from the broker.
    def on_mqtt_connect(self, client, eufy_instance, flags, rc):
        pprint("Connected to mqtt broker with result code "+str(rc))
        self.mqtt_client.subscribe((self.command_topic, 0),
                                   (self.fan_speed_topic, 0))
        eufy_instance.connect()

    # The callback for when a PUBLISH message is received from the mqtt broker.
    def on_mqtt_message(self, client, eufy_client, msg):
        pprint(msg.topic+" "+str(msg.payload))

        if self.mqtt_client.topic_matches_sub(msg.topic, self.command_topic):
            if msg.payload == "locate":
                eufy_client.find_robot()
            elif msg.payload == "clean_spot":
                eufy_client.clean_spot()
            elif msg.payload == "return_to_base":
                eufy_client.go_home()
            elif msg.payload == "start_pause":
                eufy_client.play()
            elif msg.payload == "stop":
                eufy_client.stop()

        elif self.mqtt_client.topic_matches_sub(msg.topic, self.fan_speed_topic):
            pass


class EufyRobovacMqtt:
    def __init__(self, config, mqtt):
        self.asyncio_loop = asyncio.get_event_loop()
        self.eufy_mqtt = mqtt
        self.rbv = Robovac(config["eufy"]["devId"],
                config["eufy"]["ip"],
                local_key=config["eufy"]["localKey"])
        self.eufy_mqtt.user_data_set(self)

    def connect(self):
        asyncio.run_coroutine_threadsafe(
                self.rbv.async_connect(self.eufy_connected_callback),
                self.asyncio_loop)

    def find_robot(self):
        asyncio.run_coroutine_threadsafe(
                self.rbv.async_find_robot(self.eufy_find_robot_callback),
                self.asyncio_loop)

    def clean_spot(self):
        asyncio.run_coroutine_threadsafe(
                self.rbv.async_set_work_mode(Robovac.work_mode.SPOT,
                                            self.eufy_set_work_mode_callback),
                self.asyncio_loop)

    def go_home(self):
        asyncio.run_coroutine_threadsafe(
                self.rbv.async_go_home(self.eufy_go_home_callback),
                self.asyncio_loop)

    def play(self):
        asyncio.run_coroutine_threadsafe(
                self.rbv.async_play(self.eufy_play_callback),
                self.asyncio_loop)

    def stop(self):
        asyncio.run_coroutine_threadsafe(
                self.rbv.async_pause(self.eufy_pause_callback),
                self.asyncio_loop)

    async def eufy_connected_callback(self, message, device):
        pprint(device.state)
        eufy_state = device.state
        self.eufy_mqtt.publish_online()
        self.eufy_mqtt.publish_state(self.ha_state(eufy_state))

    async def eufy_play_callback(self, message, device):
        pprint(device.state)
        eufy_state = device.state
        self.eufy_mqtt.publish_state(self.ha_state(eufy_state))

    async def eufy_pause_callback(self, message, device):
        pprint(device.state)
        eufy_state = device.state
        self.eufy_mqtt.publish_state(self.ha_state(eufy_state))

    async def eufy_go_home_callback(self, message, device):
        pprint(device.state)
        eufy_state = device.state
        self.eufy_mqtt.publish_state(self.ha_state(eufy_state))

    async def eufy_find_robot_callback(self, message, device):
        pprint(device.state)
        eufy_state = device.state
        self.eufy_mqtt.publish_state(self.ha_state(eufy_state))

    async def eufy_set_work_mode_callback(self, message, device):
        pprint(device.state)
        eufy_state = device.state
        self.eufy_mqtt.publish_state(self.ha_state(eufy_state))

    def ha_state(self, eufy_state):
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


def main(*args, **kwargs):
    if not args:
        args = sys.argv[1:]
    eufy_mqtt = None
    try:
        with open(".env", "r") as f:
            config = yaml.load(f, Loader=yaml.SafeLoader)
            eufy_mqtt = EufyMqtt(config)
            eufy_instance = EufyRobovacMqtt(config, eufy_mqtt)

        eufy_instance.asyncio_loop.run_forever()
    except Exception as e:
        pprint(e)
        eufy_mqtt.disconnect()

if __name__ == '__main__':
    main(*sys.argv[1:])
