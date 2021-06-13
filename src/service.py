#!/usr/bin/env python3

import ssl
import sys
import re
import json
import os.path
import argparse
from time import time, sleep, localtime, strftime
from collections import OrderedDict
from colorama import init as colorama_init
from colorama import Fore, Back, Style
from configparser import ConfigParser
from unidecode import unidecode
import paho.mqtt.client as mqtt
import sdnotify
import requests


project_name = "RRF WebGUI MQTT Client/Daemon"
project_url = "https://github.com/Nightreaver/RRF_WebIF_MQTT"


if False:
    # will be caught by python 2.7 to be illegal syntax
    print("Sorry, this script requires a python3 runtime environemt.", file=sys.stderr)


# Argparse
parser = argparse.ArgumentParser(description=project_name, epilog="For further details see: " + project_url)
parser.add_argument(
    "--gen-openhab",
    help="generate openHAB items based on configured sensors",
    action="store_true",
)
parser.add_argument(
    "--config_dir",
    help="set directory where config.ini is located",
    default=sys.path[0],
)
parse_args = parser.parse_args()


# Intro
colorama_init()
print(Fore.GREEN + Style.BRIGHT)
print(project_name)
print("Source:", project_url)
print(Style.RESET_ALL)

# Systemd Service Notifications - https://github.com/bb4242/sdnotify
sd_notifier = sdnotify.SystemdNotifier()

# Identifier cleanup
def clean_identifier(name):
    clean = name.strip()
    for this, that in [
        [" ", "-"],
        ["ä", "ae"],
        ["Ä", "Ae"],
        ["ö", "oe"],
        ["Ö", "Oe"],
        ["ü", "ue"],
        ["Ü", "Ue"],
        ["ß", "ss"],
    ]:
        clean = clean.replace(this, that)
    clean = unidecode(clean)
    return clean


# Eclipse Paho callbacks - http://www.eclipse.org/paho/clients/python/docs/#callbacks
def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print_line("MQTT connection established", console=True, sd_notify=True)
        print()
    else:
        print_line(
            "Connection error with result code {} - {}".format(str(rc), mqtt.connack_string(rc)),
            error=True,
        )
        # kill main thread
        os._exit(1)


def on_publish(client, userdata, mid):
    # print_line('Data successfully published.')
    pass


# Logging function
def print_line(text, error=False, warning=False, sd_notify=False, console=True):
    timestamp = strftime("%Y-%m-%d %H:%M:%S", localtime())
    if console:
        if error:
            print(
                Fore.RED
                + Style.BRIGHT
                + "[{}] ".format(timestamp)
                + Style.RESET_ALL
                + "{}".format(text)
                + Style.RESET_ALL,
                file=sys.stderr,
            )
        elif warning:
            print(Fore.YELLOW + "[{}] ".format(timestamp) + Style.RESET_ALL + "{}".format(text) + Style.RESET_ALL)
        else:
            print(Fore.GREEN + "[{}] ".format(timestamp) + Style.RESET_ALL + "{}".format(text) + Style.RESET_ALL)
    timestamp_sd = strftime("%b %d %H:%M:%S", localtime())
    if sd_notify:
        sd_notifier.notify("STATUS={} - {}.".format(timestamp_sd, unidecode(text)))


def get_printer_data(printer, type=3):  # 3 for printing info #2 for device info
    URL = "http://{}/rr_status?type={}".format(printer, type)

    try:
        r = requests.get(url=URL, timeout=2)
        if r.status_code == 200:
            data = r.json()
        else:
            return None
    except requests.exceptions.ConnectionError:
        pass
    except:
        raise
    else:
        return data


# Load configuration file
config_dir = parse_args.config_dir

config = ConfigParser(delimiters=("=",), inline_comment_prefixes=("#"))
config.optionxform = str
config.read(
    [
        os.path.join(config_dir, "config.ini.dist"),
        os.path.join(config_dir, "config.ini"),
    ]
)

reporting_mode = config["General"].get("reporting_method", "mqtt-json")
daemon_enabled = config["Daemon"].getboolean("enabled", True)
sleep_period = int(config["Daemon"].get("period", 10))

#  I have none of these so cannot test
# if reporting_mode == 'mqtt-homie':
#     default_base_topic = 'homie'
# elif reporting_mode == 'homeassistant-mqtt':
#     default_base_topic = 'homeassistant'
# elif reporting_mode == 'thingsboard-json':
#     default_base_topic = 'v1/devices/me/telemetry'
# elif reporting_mode == 'wirenboard-mqtt':
#     default_base_topic = ''
# else:
#     default_base_topic = 'mqtt-json'

default_base_topic = "reprap"

base_topic = config["MQTT"].get("base_topic", default_base_topic).lower()
device_id = config["MQTT"].get("homie_device_id", "reprap-mqtt-daemon").lower()

# Check configuration
if reporting_mode not in [
    "mqtt-json",
    "mqtt-homie",
    "json",
    "mqtt-smarthome",
    "homeassistant-mqtt",
    "thingsboard-json",
    "wirenboard-mqtt",
]:
    print_line(
        "Configuration parameter reporting_mode set to an invalid value",
        error=True,
        sd_notify=True,
    )
    sys.exit(1)
if not config["Printers"]:
    print_line(
        'No sensors found in configuration file "config.ini"',
        error=True,
        sd_notify=True,
    )
    sys.exit(1)
# if reporting_mode == 'wirenboard-mqtt' and base_topic:
#    print_line('Parameter "base_topic" ignored for "reporting_method = wirenboard-mqtt"', warning=True, sd_notify=True)

print_line("Configuration accepted", console=False, sd_notify=True)

# MQTT connection
if reporting_mode in [
    "mqtt-json",
    "mqtt-homie",
    "mqtt-smarthome",
    "homeassistant-mqtt",
    "thingsboard-json",
    "wirenboard-mqtt",
]:
    print_line("Connecting to MQTT broker ...")
    mqtt_client = mqtt.Client()
    mqtt_client.on_connect = on_connect
    mqtt_client.on_publish = on_publish
    if reporting_mode == "mqtt-json":
        mqtt_client.will_set("{}/$announce".format(base_topic), payload="{}", retain=True)
    elif reporting_mode == "mqtt-homie":
        mqtt_client.will_set("{}/{}/$online".format(base_topic, device_id), payload="false", retain=True)
    elif reporting_mode == "mqtt-smarthome":
        mqtt_client.will_set("{}/connected".format(base_topic), payload="0", retain=True)

    if config["MQTT"].getboolean("tls", False):
        # According to the docs, setting PROTOCOL_SSLv23 "Selects the highest protocol version
        # that both the client and server support. Despite the name, this option can select
        # “TLS” protocols as well as “SSL”" - so this seems like a resonable default
        mqtt_client.tls_set(
            ca_certs=config["MQTT"].get("tls_ca_cert", None),
            keyfile=config["MQTT"].get("tls_keyfile", None),
            certfile=config["MQTT"].get("tls_certfile", None),
            tls_version=ssl.PROTOCOL_SSLv23,
        )

    if config["MQTT"].get("username"):
        mqtt_client.username_pw_set(config["MQTT"].get("username"), config["MQTT"].get("password", None))
    try:
        mqtt_client.connect(
            config["MQTT"].get("hostname", "localhost"),
            port=config["MQTT"].getint("port", 1883),
            keepalive=config["MQTT"].getint("keepalive", 60),
        )
    except:
        print_line(
            'MQTT connection error. Please check your settings in the configuration file "config.ini"',
            error=True,
            sd_notify=True,
        )
        sys.exit(1)
    else:
        if reporting_mode == "mqtt-smarthome":
            mqtt_client.publish("{}/connected".format(base_topic), payload="1", retain=True)
        if reporting_mode != "thingsboard-json":
            mqtt_client.loop_start()
            sleep(1.0)  # some slack to establish the connection

sd_notifier.notify("READY=1")

printers = OrderedDict()
for [name, ip] in config["Printers"].items():
    if not re.match(r"[\d]{1,3}\.[\d]{1,3}\.[\d]{1,3}\.[\d]{1,3}", ip):
        print_line(
            "IP for {} is not properly formatted".format(name),
            error=True,
            sd_notify=True,
        )
        sys.exit(1)

    if "@" in name:
        name_pretty, location_pretty = name.split("@")
    else:
        name_pretty, location_pretty = name, ""
    name_clean = clean_identifier(name_pretty)
    location_clean = clean_identifier(location_pretty)

    _printer = dict()
    print_line("Adding Printer to device list and testing connection ...")
    print_line('Name: "{}"'.format(name_pretty))

    _printer["name"] = name_clean
    _printer["location"] = location_clean
    _printer["ip"] = ip

    printers[name_clean] = _printer

# Discovery Announcement
if reporting_mode == "mqtt-json":
    print_line("Announcing devices to MQTT broker for auto-discovery ...")

    printer_info = dict()
    for [printer_name, printer] in printers.items():
        printer_ip = printer.get("ip")
    sleep(0.5)
    print()

while True:
    for [printer_name, printer] in printers.items():
        printer_ip = printer.get("ip")
        data = get_printer_data(printer_ip)

        if reporting_mode == "mqtt-homie":
            topic_path = "{}/{}/{}".format(base_topic, device_id, printer_name)
        else:
            topic_path = "{}/{}".format(base_topic, printer_name)

        if data is None:
            status = "Offline"
        else:
            status = "Online"
        mqtt_client.publish("{}/status".format(topic_path), payload=status, qos=0, retain=True)
        mqtt_client.will_set("{}/status".format(topic_path), payload="Offline", qos=0, retain=True)

        #print(data)

        if reporting_mode == "mqtt-json":
            if not data is None:
                print_line('Publishing json to MQTT topic "{}/{}"'.format(topic_path, "data"))
                mqtt_client.publish("{}/{}".format(topic_path, "data"), json.dumps(data))
            sleep(0.5)  # some slack for the publish roundtrip and callback function
        elif reporting_mode == "thingsboard-json":
            pass
        elif reporting_mode == "homeassistant-mqtt":
            pass
        elif reporting_mode == "mqtt-homie":
            pass
        elif reporting_mode == "mqtt-smarthome":
            pass
        elif reporting_mode == "wirenboard-mqtt":
            pass
        elif reporting_mode == "json":
            pass
        else:
            raise NameError("Unexpected reporting_mode.")

    if daemon_enabled:
        print_line("Sleeping ({} seconds) ...".format(sleep_period))
        sleep(sleep_period)
        print()
    else:
        print_line("Execution finished in non-daemon-mode", sd_notify=True)
        if reporting_mode == "mqtt-json":
            mqtt_client.disconnect()
        break
