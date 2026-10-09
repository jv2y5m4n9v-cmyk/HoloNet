"""HoloNet: a cross-platform desktop launcher for a local Zigbee2MQTT setup."""

from __future__ import annotations

import json
import glob
import os
import signal
import shutil
import socket
import subprocess
import sys
import webbrowser
from pathlib import Path
import tkinter as tk
from tkinter import messagebox, ttk
import runtime_setup


# Keep the existing data-folder name so existing Zigbee network credentials survive rebranding.
APP_NAME = "HoloNet"
if os.name == "nt":
    ROOT = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "ZigbeeDesk"
elif sys.platform == "darwin":
    ROOT = Path.home() / "Library" / "Application Support" / "ZigbeeDesk"
else:
    ROOT = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")) / "zigbee-desk"
RESOURCE_ROOT = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
RUNTIME = ROOT / "runtime"
NODE_DIR = RUNTIME / "node"
Z2M_DIR = RUNTIME / "zigbee2mqtt"
DATA_DIR = Z2M_DIR / "data"
CONFIG_FILE = ROOT / "settings.json"
BROKER_SCRIPT = RUNTIME / "broker" / "broker.mjs"
Z2M_URL = "http://127.0.0.1:8080"
DRIVER_URL = "https://www.silabs.com/developers/usb-to-uart-bridge-vcp-drivers"

BG = "#111827"
PANEL = "#1f2937"
PANEL_ALT = "#263449"
TEXT = "#f3f4f6"
MUTED = "#9ca3af"
ACCENT = "#38bdf8"
GREEN = "#34d399"
AMBER = "#fbbf24"
RED = "#fb7185"
FONT_FAMILY = "Segoe UI" if os.name == "nt" else "TkDefaultFont"


def load_settings() -> dict:
    defaults = {"serial_port": "", "z2m_url": Z2M_URL}
    try:
        if CONFIG_FILE.exists():
            defaults.update(json.loads(CONFIG_FILE.read_text(encoding="utf-8")))
    except (OSError, json.JSONDecodeError):
        pass
    return defaults


def save_settings(settings: dict) -> None:
    ROOT.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(json.dumps(settings, indent=2), encoding="utf-8")


def serial_ports() -> list[str]:
    ports: set[str] = set()
    if os.name == "nt":
        try:
            import winreg

            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"HARDWARE\DEVICEMAP\SERIALCOMM") as key:
                for i in range(winreg.QueryInfoKey(key)[1]):
                    _, port, _ = winreg.EnumValue(key, i)
                    if isinstance(port, str) and port.upper().startswith("COM"):
                        ports.add(port.upper())
        except OSError:
            pass
        return sorted(ports, key=lambda item: int(item[3:]) if item[3:].isdigit() else 9999)

    candidates: list[str] = []
    if sys.platform == "darwin":
        candidates.extend(glob.glob("/dev/cu.*"))
        candidates.extend(glob.glob("/dev/tty.usb*"))
        candidates = [p for p in candidates if "Bluetooth" not in p]
    else:
        candidates.extend(glob.glob("/dev/serial/by-id/*"))
        candidates.extend(glob.glob("/dev/ttyUSB*"))
        candidates.extend(glob.glob("/dev/ttyACM*"))
    return sorted(set(candidates))


def node_executable() -> Path | None:
    local = NODE_DIR / "node.exe" if os.name == "nt" else NODE_DIR / "bin" / "node"
    if local.exists():
        return local
    if os.name == "nt":
        winget_dir = Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "WinGet" / "Packages"
        matches = list(winget_dir.glob("OpenJS.NodeJS.22_*/node-v22*-win-*/node.exe"))
        if matches:
            return matches[0]
    found = shutil.which("node.exe" if os.name == "nt" else "node")
    return Path(found) if found else None


def pnpm_script() -> Path | None:
    possible = [
        RUNTIME / "pnpm" / "node_modules" / "pnpm" / "bin" / "pnpm.cjs",
        RUNTIME / "node_modules" / "pnpm" / "bin" / "pnpm.cjs",
    ]
    return next((p for p in possible if p.exists()), None)


class HoloNetApp:
    def __init__(self, root: tk.Tk, auto_start: bool = False) -> None:
        self.root = root
        self.settings = load_settings()
        self.broker: subprocess.Popen | None = None
        self.z2m: subprocess.Popen | None = None
        self.log_handles = []
        self.port_var = tk.StringVar(value=self.settings.get("serial_port", ""))
        self.status_var = tk.StringVar(value="Checking local setup…")
        self._build_ui()
        self.refresh_ports()
        self.refresh_status()
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        if auto_start:
            self.root.after(500, self.start_network)

    def _build_ui(self) -> None:
        self.root.title(APP_NAME)
        self.root.geometry("790x610")
        self.root.minsize(690, 540)
        self.root.configure(bg=BG)

        style = ttk.Style()
        style.theme_use("clam")
        style.configure("TCombobox", fieldbackground=PANEL, background=PANEL_ALT,
                        foreground=TEXT, arrowcolor=TEXT, padding=8, font=(FONT_FAMILY, 10))
        style.map("TCombobox", fieldbackground=[("readonly", PANEL)])

        page = tk.Frame(self.root, bg=BG, padx=30, pady=24)
        page.pack(fill="both", expand=True)

        header = tk.Frame(page, bg=BG)
        header.pack(fill="x")
        tk.Label(header, text="HOLONET", bg=BG, fg=ACCENT,
                 font=(FONT_FAMILY, 10, "bold")).pack(anchor="w")
        tk.Label(header, text="Your local Zigbee network", bg=BG, fg=TEXT,
                 font=(FONT_FAMILY, 25, "bold")).pack(anchor="w", pady=(4, 1))
        tk.Label(header, text="SONOFF coordinator · Zigbee2MQTT · no Home Assistant required",
                 bg=BG, fg=MUTED, font=(FONT_FAMILY, 10)).pack(anchor="w")

        card = tk.Frame(page, bg=PANEL, padx=20, pady=18)
        card.pack(fill="x", pady=(24, 16))
        tk.Label(card, text="COORDINATOR PORT", bg=PANEL, fg=MUTED,
                 font=(FONT_FAMILY, 9, "bold")).pack(anchor="w")
        port_row = tk.Frame(card, bg=PANEL)
        port_row.pack(fill="x", pady=(8, 12))
        self.port_box = ttk.Combobox(port_row, textvariable=self.port_var, state="readonly", width=18)
        self.port_box.pack(side="left", ipady=3)
        tk.Button(port_row, text="Refresh", command=self.refresh_ports, bg=PANEL_ALT, fg=TEXT,
                  activebackground="#334155", activeforeground=TEXT, relief="flat",
                  padx=14, pady=8, cursor="hand2").pack(side="left", padx=8)
        tk.Label(card, textvariable=self.status_var, bg=PANEL, fg=TEXT,
                 font=(FONT_FAMILY, 10), wraplength=690, justify="left").pack(anchor="w")

        actions = tk.Frame(page, bg=BG)
        actions.pack(fill="x", pady=(0, 16))
        self.start_button = tk.Button(actions, text="Start Zigbee network", command=self.start_network,
                                      bg=ACCENT, fg="#082f49", activebackground="#7dd3fc",
                                       activeforeground="#082f49", relief="flat", padx=18, pady=12,
                                       font=(FONT_FAMILY, 10, "bold"), cursor="hand2")
        self.start_button.pack(side="left")
        self.open_button = tk.Button(actions, text="Open device dashboard", command=self.open_dashboard,
                                     bg=PANEL_ALT, fg=TEXT, activebackground="#334155",
                                     activeforeground=TEXT, relief="flat", padx=16, pady=12,
                                     font=(FONT_FAMILY, 10), cursor="hand2")
        self.open_button.pack(side="left", padx=9)
        tk.Button(actions, text="Install / repair setup", command=self.run_setup,
                  bg=PANEL_ALT, fg=TEXT, activebackground="#334155", activeforeground=TEXT,
                  relief="flat", padx=13, pady=12, font=(FONT_FAMILY, 10),
                  cursor="hand2").pack(side="left", padx=(0, 9))
        self.stop_button = tk.Button(actions, text="Stop", command=self.stop_network,
                                     bg=PANEL, fg=TEXT, activebackground="#374151",
                                      activeforeground=TEXT, relief="flat", padx=16, pady=12,
                                      font=(FONT_FAMILY, 10), cursor="hand2")
        self.stop_button.pack(side="left")

        info = tk.Frame(page, bg=PANEL, padx=20, pady=17)
        info.pack(fill="both", expand=True)
        tk.Label(info, text="GETTING STARTED", bg=PANEL, fg=TEXT,
                 font=(FONT_FAMILY, 11, "bold")).pack(anchor="w")
        first_step = (
            "Install the Silicon Labs CP210x driver if the dongle has no COM port."
            if os.name == "nt"
            else "Connect the dongle and select its serial device. Linux may require serial-device group access."
        )
        steps = [
            ("1", first_step),
            ("2", "Choose its COM port above, then start the Zigbee network."),
            ("3", "Open the dashboard at localhost:8080 and permit joining."),
            ("4", "Put a device into Zigbee pairing mode. For the Shelly 1 Gen4, update it over Wi-Fi first, switch it to Zigbee, then join it."),
        ]
        for number, text in steps:
            line = tk.Frame(info, bg=PANEL)
            line.pack(fill="x", pady=(10, 0))
            tk.Label(line, text=number, bg=PANEL_ALT, fg=ACCENT, width=3, pady=4,
                     font=(FONT_FAMILY, 9, "bold")).pack(side="left", anchor="n")
            tk.Label(line, text=text, bg=PANEL, fg="#d1d5db", wraplength=625,
                     justify="left", font=(FONT_FAMILY, 10)).pack(side="left", padx=11, fill="x", expand=True)

        footer = tk.Frame(page, bg=BG)
        footer.pack(fill="x", pady=(12, 0))
        tk.Button(footer, text="Serial-port help", command=self.serial_help,
                  bg=BG, fg=ACCENT, activebackground=BG, activeforeground="#7dd3fc",
                  relief="flat", cursor="hand2").pack(side="left")
        if os.name == "nt":
            tk.Button(footer, text="Open Device Manager", command=lambda: subprocess.Popen(["mmc.exe", "devmgmt.msc"]),
                      bg=BG, fg=ACCENT, activebackground=BG, activeforeground="#7dd3fc",
                      relief="flat", cursor="hand2").pack(side="left", padx=(12, 0))
            tk.Button(footer, text="Install downloaded driver", command=self.install_driver,
                      bg=BG, fg=ACCENT, activebackground=BG, activeforeground="#7dd3fc",
                      relief="flat", cursor="hand2").pack(side="left", padx=(12, 0))
        tk.Label(footer, text="Runs locally on this PC", bg=BG, fg=MUTED,
                 font=(FONT_FAMILY, 9)).pack(side="right")

    def refresh_ports(self) -> None:
        ports = serial_ports()
        self.port_box["values"] = ports
        current = self.port_var.get()
        if current not in ports:
            self.port_var.set(ports[0] if ports else "")
        self._save_port()
        self.refresh_status()

    def _save_port(self) -> None:
        self.settings["serial_port"] = self.port_var.get()
        save_settings(self.settings)

    def _dependencies(self) -> tuple[Path | None, Path | None, Path | None]:
        broker = BROKER_SCRIPT if (BROKER_SCRIPT.parent / "node_modules" / "aedes").exists() else None
        return node_executable(), pnpm_script(), broker

    def refresh_status(self) -> None:
        node, pnpm, broker = self._dependencies()
        ports = serial_ports()
        if not ports:
            line = "SONOFF dongle: no serial/COM port detected. Install the CP210x VCP driver, then refresh."
            color = AMBER
        else:
            line = f"SONOFF dongle: {', '.join(ports)} detected."
            color = GREEN
        missing = []
        if node is None:
            missing.append("Node.js 22")
        if pnpm is None:
            missing.append("pnpm")
        if broker is None:
            missing.append("local MQTT broker")
        if not (Z2M_DIR / "package.json").exists():
            missing.append("Zigbee2MQTT")
        elif not (Z2M_DIR / "node_modules" / "zigbee-herdsman").exists():
            missing.append("Zigbee2MQTT dependencies")
        if missing:
            line += "\nRuntime setup still needed: " + ", ".join(missing) + ". Choose Install / repair setup."
            color = AMBER if color != AMBER else AMBER
        else:
            line += "\nLocal runtime: ready."
        if self._tcp_open(8080):
            line += "\nZigbee2MQTT is running at localhost:8080."
            color = GREEN
        self.status_var.set(line)
        self._status_color = color

    def start_network(self) -> None:
        self._save_port()
        if not self.port_var.get():
            if os.name == "nt":
                messagebox.showwarning(APP_NAME, "No COM port is available. Install the CP210x VCP driver, reconnect the SONOFF dongle, and refresh ports.")
                webbrowser.open(DRIVER_URL)
            elif sys.platform == "darwin":
                messagebox.showwarning(APP_NAME, "No USB serial device was found. Reconnect the coordinator and check System Information → USB.")
            else:
                messagebox.showwarning(APP_NAME, "No USB serial device was found. Reconnect it and check /dev/serial/by-id or /dev/ttyUSB*. Your user may need serial-device permissions.")
            return
        if self._tcp_open(8080):
            self.status_var.set("Zigbee2MQTT is already running. Opening the device dashboard.")
            webbrowser.open(self.settings.get("z2m_url", Z2M_URL))
            return
        node, pnpm, broker = self._dependencies()
        if (
            not node
            or not pnpm
            or not broker
            or not (Z2M_DIR / "package.json").exists()
            or not (Z2M_DIR / "node_modules" / "zigbee-herdsman").exists()
        ):
            if messagebox.askyesno(APP_NAME, "Some runtime tools are missing. Run the setup script now?"):
                self.run_setup()
            return
        try:
            self._write_runtime_config()
            self._launch_broker(node, broker)
            self._launch_z2m(node, pnpm)
            self.start_button.configure(state="disabled")
            self.status_var.set("Starting the local MQTT broker and Zigbee2MQTT… The dashboard will be available at localhost:8080.")
            self.root.after(5000, self._finish_start)
        except (OSError, subprocess.SubprocessError) as exc:
            messagebox.showerror(APP_NAME, f"Could not start the Zigbee services:\n\n{exc}")
            self.refresh_status()

    def _write_runtime_config(self) -> None:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        port = self.port_var.get()
        config = DATA_DIR / "configuration.yaml"
        if config.exists():
            lines = config.read_text(encoding="utf-8").splitlines()
            in_serial = False
            port_written = False
            adapter_written = False
            updated: list[str] = []
            for line in lines:
                if line and not line[0].isspace():
                    in_serial = line.strip() == "serial:"
                if in_serial and line.lstrip().startswith("port:"):
                    updated.append(f"  port: {port}")
                    port_written = True
                elif in_serial and line.lstrip().startswith("adapter:"):
                    updated.append("  adapter: zstack")
                    adapter_written = True
                else:
                    updated.append(line)
            if not any(line.strip() == "serial:" for line in updated):
                updated.extend(["serial:", f"  port: {port}", "  adapter: zstack"])
            else:
                serial_index = next(i for i, line in enumerate(updated) if line.strip() == "serial:")
                insert_at = serial_index + 1
                if not port_written:
                    updated.insert(insert_at, f"  port: {port}")
                    insert_at += 1
                if not adapter_written:
                    updated.insert(insert_at, "  adapter: zstack")
            config.write_text("\n".join(updated) + "\n", encoding="utf-8")
        else:
            config.write_text(
                "version: 5\n"
                "mqtt:\n"
                "  base_topic: zigbee2mqtt\n"
                "  server: mqtt://127.0.0.1:1884\n"
                "serial:\n"
                f"  port: {port}\n"
                "  adapter: zstack\n"
                "frontend:\n"
                "  enabled: true\n"
                "  port: 8080\n"
                "advanced:\n"
                "  network_key: GENERATE\n"
                "  pan_id: GENERATE\n"
                "  ext_pan_id: GENERATE\n"
                "homeassistant:\n"
                "  enabled: false\n",
                encoding="utf-8",
            )
    def _launch_broker(self, node: Path, broker_script: Path) -> None:
        if self.broker and self.broker.poll() is None:
            return
        if self._tcp_open(1884):
            return
        self.log_handles.append((ROOT / "mqtt.log").open("a", encoding="utf-8"))
        env = os.environ.copy()
        env["PATH"] = str(node.parent) + os.pathsep + env.get("PATH", "")
        options = {"creationflags": getattr(subprocess, "CREATE_NO_WINDOW", 0)} if os.name == "nt" else {"start_new_session": True}
        self.broker = subprocess.Popen(
            [str(node), str(broker_script)],
            cwd=str(ROOT), stdout=self.log_handles[-1], stderr=subprocess.STDOUT,
            env=env, **options,
        )

    def _launch_z2m(self, node: Path, pnpm: Path) -> None:
        if self.z2m and self.z2m.poll() is None:
            return
        self.log_handles.append((ROOT / "zigbee2mqtt.log").open("a", encoding="utf-8"))
        env = os.environ.copy()
        env["PATH"] = str(node.parent) + os.pathsep + env.get("PATH", "")
        options = {"creationflags": getattr(subprocess, "CREATE_NO_WINDOW", 0)} if os.name == "nt" else {"start_new_session": True}
        self.z2m = subprocess.Popen(
            [str(node), str(pnpm), "start"], cwd=str(Z2M_DIR), stdout=self.log_handles[-1],
            stderr=subprocess.STDOUT, env=env, **options,
        )

    @staticmethod
    def _tcp_open(port: int) -> bool:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=1):
                return True
        except OSError:
            return False

    def _finish_start(self) -> None:
        self.start_button.configure(state="normal")
        self.refresh_status()
        if self.z2m and self.z2m.poll() is not None:
            messagebox.showerror(APP_NAME, f"Zigbee2MQTT exited during startup. See:\n{ROOT / 'zigbee2mqtt.log'}")
            return
        if self._tcp_open(8080):
            webbrowser.open(self.settings.get("z2m_url", Z2M_URL))
        self.root.after(500, self._watch_processes)

    def _watch_processes(self) -> None:
        if self.z2m and self.z2m.poll() is not None:
            self.status_var.set(f"Zigbee2MQTT stopped. Check {ROOT / 'zigbee2mqtt.log'}")
            self.start_button.configure(state="normal")
            return
        if self.z2m or self.broker:
            self.root.after(2000, self._watch_processes)

    def open_dashboard(self) -> None:
        webbrowser.open(self.settings.get("z2m_url", Z2M_URL))

    def run_setup(self) -> None:
        command = [sys.executable, "--setup-runtime"] if getattr(sys, "frozen", False) else [sys.executable, str(RESOURCE_ROOT / "runtime_setup.py")]
        ROOT.mkdir(parents=True, exist_ok=True)
        log = (ROOT / "setup.log").open("a", encoding="utf-8")
        try:
            options = {"stdout": log, "stderr": subprocess.STDOUT, "cwd": str(RESOURCE_ROOT)}
            if os.name == "nt":
                options["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            else:
                options["start_new_session"] = True
            subprocess.Popen(command, **options)
        finally:
            log.close()
        messagebox.showinfo(APP_NAME, f"Runtime setup is running. Progress is in {ROOT / 'setup.log'}.")

    def install_driver(self) -> None:
        if os.name != "nt":
            self.serial_help()
            return
        script = RESOURCE_ROOT / "install_driver.ps1"
        if not script.exists():
            messagebox.showerror(APP_NAME, f"Driver installer script not found: {script}")
            return
        subprocess.Popen(["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script)])

    def serial_help(self) -> None:
        if os.name == "nt":
            webbrowser.open(DRIVER_URL)
            return
        if sys.platform == "darwin":
            details = "USB serial adapters normally appear under /dev/cu.*. Check System Information → USB if the adapter is not listed."
        else:
            details = "Look for the adapter under /dev/serial/by-id, /dev/ttyUSB*, or /dev/ttyACM*. Your user may need permission to access its serial device."
        messagebox.showinfo("Serial adapter help", details)

    def stop_network(self) -> None:
        for process in (self.z2m, self.broker):
            if process and process.poll() is None:
                try:
                    if os.name == "nt":
                        subprocess.run(["taskkill.exe", "/PID", str(process.pid), "/T", "/F"],
                                       capture_output=True, check=False, timeout=10)
                    else:
                        os.killpg(process.pid, signal.SIGTERM)
                        process.wait(timeout=5)
                except (OSError, subprocess.TimeoutExpired):
                    if os.name != "nt" and process.poll() is None:
                        try:
                            os.killpg(process.pid, signal.SIGKILL)
                        except OSError:
                            pass
                    pass
        self.z2m = None
        self.broker = None
        for handle in self.log_handles:
            try:
                handle.close()
            except OSError:
                pass
        self.log_handles.clear()
        self.start_button.configure(state="normal")
        self.status_var.set("Local Zigbee services stopped.")

    def close(self) -> None:
        active = any(p and p.poll() is None for p in (self.z2m, self.broker))
        if active and not messagebox.askyesno(APP_NAME, "Stop the Zigbee network before closing?"):
            self.root.destroy()
            return
        if active:
            self.stop_network()
        self.root.destroy()


def main() -> None:
    if "--setup-runtime" in sys.argv:
        raise SystemExit(runtime_setup.main())
    ROOT.mkdir(parents=True, exist_ok=True)
    root = tk.Tk()
    HoloNetApp(root, auto_start="--start-network" in sys.argv)
    root.mainloop()


if __name__ == "__main__":
    main()
