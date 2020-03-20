## Installation

On a modern Linux system just a few steps are needed to get the daemon working.
The following example shows the installation under Debian/Raspbian below the `/opt` directory:

```shell
sudo apt install git python3 python3-pip bluetooth bluez

git clone https://github.com/Nightreaver/RRF_WebIF_MQTT.git /opt/rrf-mqtt-daemon

cd /opt/rrf-mqtt-daemon
sudo pip3 install -r requirements.txt
```

## Configuration

To match personal needs, all operation details can be configured using the file [`config.ini`](config.ini.dist).
The file needs to be created first:

```shell
cp /opt/rrf-mqtt-daemon/src/config.{ini.dist,ini}
vim /opt/rrf-mqtt-daemon/src/config.ini
```

**Attention:**
You need to add at least one RRF printer to the configuration.


## Execution

A first test run is as easy as:

```shell
python3 /opt/rrf-mqtt-daemon/src/service.py
```

With a correct configuration the result should look similar to the the screencap above.

Using the command line argument `--config`, a directory where to read the config.ini file from can be specified, e.g.

```shell
python3 /opt/rrf-mqtt-daemon/src/service.py --config /opt/rrf-mqtt-daemon
```

The extensive output can be reduced to error messages:

```shell
python3 /opt/rrf-mqtt-daemon/src/service.py > /dev/null
```

### Continuous Daemon/Service

You most probably want to execute the program **continuously in the background**.
This can be done either by using the internal daemon or cron.

**Attention:** Daemon mode must be enabled in the configuration file (default).

1. Systemd service - on systemd powered systems the **recommended** option
   
   ```shell
   sudo cp /opt/rrf-mqtt-daemon/template.service /etc/systemd/system/rrfd.service

   sudo systemctl daemon-reload

   sudo systemctl start rrfd.service
   sudo systemctl status rrfd.service

   sudo systemctl enable rrfd.service
   ```

1. Screen Shell - Run the program inside a [screen shell](https://www.howtoforge.com/linux_screen):
   
   ```shell
   screen -S rrf-mqtt-daemon -d -m python3 /path/to/rrf-mqtt-daemon/src/service.py
   ```
