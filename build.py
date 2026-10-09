"""Build the current platform's HoloNet executable with PyInstaller."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
SEPARATOR = ";" if os.name == "nt" else ":"


def build_cache() -> Path:
    if os.name == "nt":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home()))
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Caches"
    else:
        base = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))
    return base / "HoloNet" / "pyinstaller"


def main() -> int:
    if sys.version_info < (3, 12):
        print("Python 3.12 or newer is required to build HoloNet.", file=sys.stderr)
        return 2
    broker = ROOT / "broker"
    cache = build_cache()
    command = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--onefile",
        "--windowed",
        "--name",
        "HoloNet",
        "--distpath",
        str(ROOT / "dist"),
        "--workpath",
        str(cache / "work"),
        "--specpath",
        str(cache / "spec"),
        "--add-data",
        f"{broker}{SEPARATOR}broker",
    ]

    z2m_archive = ROOT / "downloads" / "zigbee2mqtt-2.14.2.zip"
    if z2m_archive.is_file():
        command.extend(["--add-data", f"{z2m_archive}{SEPARATOR}downloads"])

    if os.name == "nt":
        driver_dir = ROOT / "downloads" / "cp210x-driver"
        driver_script = ROOT / "install_driver.ps1"
        if driver_dir.is_dir() and driver_script.is_file():
            command.extend(["--add-data", f"{driver_dir}{SEPARATOR}downloads/cp210x-driver"])
            command.extend(["--add-data", f"{driver_script}{SEPARATOR}."])

    command.append(str(ROOT / "app.py"))
    print("Building a native executable for", sys.platform, "using:")
    print(" ".join(f'"{part}"' if " " in part else part for part in command))
    return subprocess.run(command, cwd=ROOT, check=False).returncode


if __name__ == "__main__":
    raise SystemExit(main())
