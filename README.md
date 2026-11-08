# PGSparkLite - Web Interface for the Spark 40 Amp

## Overview

This is a Python based project that allows the user to send and receive configuration changes to and from a Positive Grid Spark 40 Amp (https://www.positivegrid.com/spark/) via a web browser. 

![PGSparkLite Interface](https://richtamblyn.co.uk/wp-content/uploads/2021/05/DAW_Example.jpg)

Written using the Flask framework and SocketIO, the intended target for this code is a Raspberry Pi Zero W that can host the interface, allowing other networked computers remote control of the connected Spark. It can also be setup on a Windows PC and accessed locally.

The realistic knobs and switch controls are possible thanks to the awesome G200KG Input Knobs library - https://g200kg.github.io/input-knobs/

## What can it do?
The PGSparkLite web interface offers the current functionality:

#### 4 preset selection buttons
These mirror the functionality of the buttons on the amp. Long pressing the preset button to save changes to the amp is also supported.

#### Set BPM tempo
The user can enter and set the BPM tempo for the delay effect.

#### Create/update/delete Chain Presets
The user can create their own Chain Presets. Chain Presets store the parameters for all the selected Pedals in the chain, their On/Off status and their visibility.

#### Create/update/delete Pedal Presets
The user can create their own Pedal Presets. Pedal Presets are associated with individual Pedals in the chain and recall parameters and On/Off status.

#### On/Off Switches
Each pedal in the chain can be switched on or off (even the amp!) via buttons on each Pedal section. Pedals that are switched off are grayed out to make it clear it is inactive. The On/Off state is maintained when stored in a Chain or Pedal preset.

#### Collapsible Pedal Sections
The pedal sections (gate, comp, drive, amp, mod, delay and reverb) can be minimised to reduce distractions and increase the space available in the browser window to reduce scrolling. Sections can be minimised regardless of whether they are on or off and their state is maintained when stored in a Chain Preset.

## Docker (Raspberry Pi)

PGSparkLite can run in Docker on a Raspberry Pi (64-bit or 32-bit OS) with
Bluetooth enabled on the host (`bluetoothd` running).

    git clone <this repo> && cd PGSparkLite
    AMP_BT_ADDRESS=08:EB:ED:XX:XX:XX docker compose up -d --build

Then open `http://<pi-address>:5000`. The app connects to the amp
automatically as soon as it is reachable.

- The container uses host networking: Bluetooth sockets are only available
  in the host network namespace.
- The database lives in `./data/pgsparklite.db`. To keep an existing one, copy
  it there before the first start.
- Import the bundled community presets:
  `docker compose exec pgsparklite python3 -m utils.import_presets presets/community`
- `AMP_BT_ADDRESS` is optional; without it the amp is found by Bluetooth
  discovery (slower).

### Use the official Spark app at the same time

PGSparkLite can also act as an amp for the official Spark app (Android):
connect the app to the Pi instead of the amp, and PGSparkLite relays it to
the amp over its own Bluetooth link. Both stay usable at once, the web UI
follows the changes made in the app, and Bluetooth audio to the Pi (e.g.
Kodi on LibreELEC) keeps working: the relay is just one more Bluetooth
service next to audio.

Set it up in **Settings → Spark app**:

1. Tick *Relay the Spark app* and save.
2. *Pair a new phone (2 min)*: the Pi becomes visible and accepts pairing
   without a PIN for two minutes. Pair the phone from its Bluetooth settings.
3. On the phone, forget the amp's own Bluetooth entry so the app picks the
   Pi, then open the Spark app and connect.

Only paired devices can connect, and outside the pairing window the Pi is
not discoverable. Tick devices under *Allowed devices* to restrict the relay
to them (a phone paired from Settings is added automatically).

The settings are stored in `spark_app_proxy.json` next to the database
(`/data` in Docker) and can be edited by hand:

    {
      "enabled": true,
      "name": "",
      "allowed_devices": ["FC:41:16:CE:C3:2C"]
    }

`name` is the Pi's Bluetooth name while the relay is on. It defaults to
`Spark 40 Audio` (empty), which the Android Spark app requires to list the
device; Bluetooth audio to the Pi keeps working under that name. Until the
file exists, `SPARK_APP_PROXY`, `SPARK_APP_PROXY_NAME` and
`SPARK_APP_PROXY_DEVICES` give the initial values. The container needs the
host D-Bus socket (`/run/dbus`), already mounted in `docker-compose.yml` and
`deploy/pgsparklite.service`.

Tests: `python3 -m unittest discover tests`.

## User Instructions
Guides to setting up PGSparkLite can be found in the Wiki: 

* Raspberry Pi - https://github.com/richtamblyn/PGSparkLite/wiki/How-to-setup-a-Raspberry-Pi-Zero-W-and-PGSparkLite-from-scratch
* Windows 10 - https://github.com/richtamblyn/PGSparkLite/wiki/How-to-setup-PGSparkLite-on-Windows-10

## Development Environment
This project was developed on a Raspberry Pi 4 (4GB RAM version) using the awesome Microsoft Visual Studio Code IDE. Launch configuration is included within the repository to allow you to run and debug the project locally. 

### Dependencies
- Python 3.x
- Flask 1.0.2 
- Flask-SocketIO 5.0.1
- PySerial 3.4
- Python3-bluez

### External Dependencies
This project uses CDN servers to retrieve JQuery 3.5.1 and SocketIO 3.0.4 JavaScript libraries. If you wish to download the libraries separately to remove the requirement for an external internet connection, the references can then be modified in the /templates/layout.html file.

## Future Development Ideas
- Allow user to backup / restore Preset database
- Allow user to import / export single ChainPresets / PedalPresets

## Thanks

This project was inspired by the amazing work of:

- Paul Hamshere https://github.com/paulhamsh/Spark-Parser
- Justin Nelson https://github.com/jrnelson90/tinderboxpedal
- Yuriy Tsibizov https://github.com/ytsibizov/midibox,
