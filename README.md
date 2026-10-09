# HoloNet

A Star Wars-themed, cross-platform desktop launcher for a local Zigbee network powered by Zigbee2MQTT. It does not use Home Assistant. The SONOFF ZBDongle-P is accessed by Zigbee2MQTT (`zstack`), with a loopback-only Aedes MQTT broker included in the local runtime. The Zigbee2MQTT web interface is the device dashboard and pairing UI.

The Python desktop app runs from the project-local `venv` virtual environment (Python 3.12 or newer). Its current Python code uses only the standard library. Zigbee2MQTT and the Aedes MQTT broker are separate Node.js processes managed by the app. The executable build bootstraps those runtimes on first setup under the current user's application-data directory.

## Current setup

- Python 3 with Tkinter is available on this PC.
- The Silicon Labs CP210x driver is installed. When attached, the SONOFF dongle enumerates as **COM3**.
- Node.js 22, the local Aedes MQTT broker, and Zigbee2MQTT 2.14.2 are installed. Zigbee network data is stored locally and resumes when the coordinator is connected and the app is started.
- The signed Silicon Labs CP210x 11.5.0.417 driver matching `VID_10C4&PID_EA60` is staged in `downloads\cp210x-driver`. Its package came from [Microsoft Update Catalog](https://www.catalog.update.microsoft.com/ScopedViewInline.aspx?updateid=32293688-4758-4334-98c0-7d634cf3c59e).

## Run

1. In a source checkout, run `setup.ps1` on Windows or `sh launch.sh` on Linux/macOS; the launcher creates `venv` and opens the app. In a packaged build, open the executable and choose **Install / repair setup**.
2. On Windows, the dongle driver needs administrator approval. On Linux/macOS, the USB serial device should appear in the port list; Linux may require serial-device group permissions.
3. Run `launch.bat` on Windows or `sh launch.sh` on Linux/macOS. Select the coordinator port and choose **Start Zigbee network**.
4. Use the Zigbee2MQTT dashboard at <http://127.0.0.1:8080> to permit joining and pair devices.

The app writes a local Zigbee2MQTT configuration using the selected COM port, `zstack`, and a localhost-only MQTT broker. The network is local to this PC. Keep the PC awake while you want the coordinator and app available.

## Shelly 1 Gen4

Zigbee2MQTT supports model `S4SW-001X16EU`. Update the Shelly firmware while it is connected over Wi-Fi, switch it from its default Matter profile to Zigbee using the Shelly web interface, enable Permit join in Zigbee2MQTT, and follow the [model-specific pairing instructions](https://www.zigbee2mqtt.io/devices/S4SW-001X16EU.html).

## Logs and runtime

- Runtime and network data stay in the original `ZigbeeDesk` data folder so rebranding does not reset an existing Zigbee network: `%LOCALAPPDATA%\ZigbeeDesk\runtime` (Windows), `~/Library/Application Support/ZigbeeDesk/runtime` (macOS), or `$XDG_DATA_HOME/zigbee-desk/runtime` (Linux; defaults to `~/.local/share/zigbee-desk/runtime`).
- MQTT broker and Zigbee2MQTT logs are saved beside the runtime directory.
- The Zigbee2MQTT network key and pairing data are stored in its `data` directory. Back up that directory before upgrading or changing the coordinator.

## Build/export

Build a native executable on each operating system; one binary cannot run on Windows, Linux, and macOS simultaneously. From the project directory, create/activate `venv`, install `requirements-build.txt`, then run `python build.py`. The local Windows result is `dist\HoloNet.exe`; Linux and macOS builds use their native executable/app formats.

The GitHub Actions matrix builds Windows x64, Linux x64/ARM64, and macOS Intel/Apple Silicon artifacts. The Windows x64 build can also run under Windows-on-ARM emulation. Push this project to a GitHub repository and run **Build HoloNet** from Actions (or push a `v*` tag) to download those artifacts. First launch downloads the OS-matching Node.js runtime and installs Zigbee2MQTT/Aedes under that user's application-data directory. macOS builds from this workflow are not code-signed or notarized.
