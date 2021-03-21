# -*- coding: utf-8 -*-

# Copyright 2021 Graham Benton
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import paho.mqtt.client as mqtt
import yaml
import json

import asyncio
import logging
from pprint import pprint
import sys

from eufy_robovac.robovac import Robovac, WorkStatus, CleanSpeed

_LOGGER = logging.getLogger(__name__)

class EufyMqtt:
    def __init__(self, config):
        self.mqtt_address = config["address"]
        self.mqtt_port = config["port"]
        self.mqtt_prefix = config["prefix"]
        self.will_topic = self.mqtt_prefix + "available"
        self.state_topic = self.mqtt_prefix + "state"
        self.command_topic = self.mqtt_prefix + "command"
        self.fan_speed_topic = self.mqtt_prefix + "set_fan_speed"
        self.mqtt_client = mqtt.Client()
        self.mqtt_client.username_pw_set(config["user"], config["pwd"])
        self.mqtt_client.on_connect = self.on_mqtt_connect
        self.mqtt_client.on_message = self.on_mqtt_message
        self.mqtt_client.will_set(self.will_topic, payload="offline", retain=True)
        self.mqtt_client.loop_start()

    def disconnect(self):
        self.publish(self.will_topic, "offline")
        self.mqtt_client.disconnect()

    def publish(self, topic, payload):
        self.mqtt_client.publish(topic, payload)

    def publish_online(self):
        self.mqtt_client.publish(self.will_topic, "online", retain=True)

    def publish_offline(self):
        self.mqtt_client.publish(self.will_topic, "offline", retain=True)

    def publish_state(self, state):
        self.mqtt_client.publish(self.state_topic, state)


    def user_data_set(self, eufy_instance):
        self.mqtt_client.user_data_set(eufy_instance)
        self.mqtt_client.connect_async(self.mqtt_address, self.mqtt_port, 60)

    # The callback for when the mqtt client receives a CONNACK response from the broker.
    def on_mqtt_connect(self, client, eufy_instance, flags, rc):
        _LOGGER.info("Connected to mqtt broker with result code "+str(rc))
        self.mqtt_client.subscribe([(self.command_topic, 0),
                                    (self.fan_speed_topic, 0)])
        if eufy_instance.connected:
            self.publish_online()
            eufy_instance.get_state()
        else:
            self.publish_offline()

    # The callback for when a PUBLISH message is received from the mqtt broker.
    def on_mqtt_message(self, client, eufy_client, msg):
        _LOGGER.debug(msg.topic+" "+str(msg.payload))

        if mqtt.topic_matches_sub(msg.topic, self.command_topic):
            if msg.payload == b"locate":
                _LOGGER.debug("locate")
                eufy_client.find_robot()
            elif msg.payload == b"clean_spot":
                _LOGGER.debug("clean_spot")
                eufy_client.clean_spot()
            elif msg.payload == b"return_to_base":
                _LOGGER.debug("go_home")
                eufy_client.go_home()
            elif msg.payload == b"start":
                _LOGGER.debug("start")
                eufy_client.play()
            elif msg.payload == b"stop":
                _LOGGER.debug("stop")
                eufy_client.stop()
            elif msg.payload == b"status":
                _LOGGER.debug("status")
                eufy_client.get_state()

        elif mqtt.topic_matches_sub(msg.topic, self.fan_speed_topic):
            _LOGGER.debug("mqtt message " + str(msg.topic) + " : " + str(msg.payload))
            eufy_client.set_clean_speed(str(msg.payload))

class EufyRobovacMqtt:
    def __init__(self, config, mqtt):
        self.asyncio_loop = asyncio.get_event_loop()
        self.eufy_mqtt = mqtt
        self.eufy_state = None
        self.rbv = Robovac(config["devId"],
                config["ip"],
                local_key=config["localKey"])
        self.eufy_mqtt.user_data_set(self)
        # There doesn't seem to be a way to get notified
        # of robovac's state, so check back every 1s
        self.connected = False
        self.state_check_handle = self.asyncio_loop.create_task(
                self.periodic_state_check())


    def connect(self):
        asyncio.run_coroutine_threadsafe(
                self.rbv.async_connect(self.connected_callback),
                self.asyncio_loop)

    def find_robot(self):
        asyncio.run_coroutine_threadsafe(
                self.rbv.async_find_robot(self.find_robot_callback),
                self.asyncio_loop)

    def clean_spot(self):
        asyncio.run_coroutine_threadsafe(
                self.rbv.async_set_work_mode(Robovac.work_mode.SPOT,
                                            self.set_work_mode_callback),
                self.asyncio_loop)

    def go_home(self):
        asyncio.run_coroutine_threadsafe(
                self.rbv.async_go_home(self.go_home_callback),
                self.asyncio_loop)

    def play(self):
        asyncio.run_coroutine_threadsafe(
                self.rbv.async_play(self.play_callback),
                self.asyncio_loop)

    def stop(self):
        asyncio.run_coroutine_threadsafe(
                self.rbv.async_pause(self.pause_callback),
                self.asyncio_loop)

    def set_clean_speed(self, speed):
        _LOGGER.debug("set clean speed to: " + speed)
        asyncio.run_coroutine_threadsafe(
                self.rbv.async_set_clean_speed(speed,
                                               self.set_clean_speed_callback),
                self.asyncio_loop)

    def get_state(self):
        asyncio.run_coroutine_threadsafe(
                self.rbv.async_get(self.get_callback),
                self.asyncio_loop)

    async def connected_callback(self, message, device):
        _LOGGER.debug(device.state)
        self.eufy_state = device.state
        self.eufy_mqtt.publish_online()
        self.eufy_mqtt.publish_state(self.ha_state(self.eufy_state))
        self.connected = True

    async def play_callback(self, message, device):
        _LOGGER.debug(device.state)
        await asyncio.sleep(1)
        asyncio.create_task(self.rbv.async_get(self.get_callback))

    async def pause_callback(self, message, device):
        _LOGGER.debug(device.state)
        await asyncio.sleep(1)
        asyncio.create_task(self.rbv.async_get(self.get_callback))

    async def go_home_callback(self, message, device):
        _LOGGER.debug(device.state)
        await asyncio.sleep(1)
        asyncio.create_task(self.rbv.async_get(self.get_callback))

    async def find_robot_callback(self, message, device):
        _LOGGER.debug(device.state)
        self.eufy_state = device.state
        self.eufy_mqtt.publish_state(self.ha_state(self.eufy_state))

    async def set_work_mode_callback(self, message, device):
        _LOGGER.debug(device.state)
        await asyncio.sleep(1)
        asyncio.create_task(self.rbv.async_get(self.get_callback))

    async def set_clean_speed_callback(self, message, device):
        _LOGGER.debug(device.state)
        await asyncio.sleep(1)
        asyncio.create_task(self.rbv.async_get(self.get_callback))

    async def get_callback(self, message, device):
        _LOGGER.debug(device.state)
        self.eufy_state = device.state
        self.eufy_mqtt.publish_state(self.ha_state(self.eufy_state))

    async def periodic_state_check(self):
        while True:
            if self.connected:
                if self.rbv._connected:
                    await asyncio.sleep(1)
                else:
                    _LOGGER.warning("Eufy disconnected from " + str(rbv.host))
                    self.connected = False
                    self.publish_offline()
                    self.connect()
                    await asyncio.sleep(10)

            else:
                if not self.rbv._connected:
                    self.connect()
                    await asyncio.sleep(10)
                else:
                    _LOGGER.warning("Eufy connected to " + str(rbv.host))
                    self.connected = True
                    self.mqtt.publish_online()
                    asyncio.create_task(self.rbv.async_get(self.get_callback))
                    await asyncio.sleep(1)

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
        fan_speed = eufy_state[Robovac.CLEAN_SPEED]
        return json.dumps({"state":  ha_state,
                           "battery_level": eufy_state[Robovac.BATTERY_LEVEL],
                           "fan_speed": fan_speed})


def main(*args, **kwargs):
    if not args:
        args = sys.argv[1:]
    eufy_mqtt = None
    try:
        with open(".env", "r") as f:
            config = yaml.load(f, Loader=yaml.SafeLoader)
            eufy_mqtt = EufyMqtt(config["mqtt"])
            eufy_instance = EufyRobovacMqtt(config["eufy"], eufy_mqtt)

        eufy_instance.asyncio_loop.run_forever()
    except Exception as e:
        _LOGGER.debug(e)
        eufy_mqtt.disconnect()

if __name__ == '__main__':
    main(*sys.argv[1:])
