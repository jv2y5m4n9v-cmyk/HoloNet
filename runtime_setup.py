"""Install the Node.js/Zigbee2MQTT runtime for the current operating system."""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
import sys
import tarfile
import time
import urllib.error
import urllib.request
import zipfile
from pathlib import Path


NODE_VERSION = "22.23.2"
PNPM_VERSION = "11.26.0"
Z2M_VERSION = "2.14.2"


def data_root() -> Path:
    if os.name == "nt":
        return Path(os.environ.get("LOCALAPPDATA", Path.home())) / "ZigbeeDesk"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "ZigbeeDesk"
    return Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")) / "zigbee-desk"


def resource_root() -> Path:
    return Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))


def node_path(node_home: Path) -> Path:
    return node_home / "node.exe" if os.name == "nt" else node_home / "bin" / "node"


def log(message: str) -> None:
    line = f"{message}\n"
    stream = getattr(sys, "stdout", None)
    if stream is not None:
        stream.write(line)
        stream.flush()
    else:
        path = data_root() / "setup.log"
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(line)


def node_asset() -> tuple[str, str]:
    machine = platform.machine().lower()
    if os.name == "nt":
        arch = "arm64" if machine in {"arm64", "aarch64"} else "x64"
        return f"node-v{NODE_VERSION}-win-{arch}.zip", "zip"
    if sys.platform == "darwin":
        arch = "arm64" if machine in {"arm64", "aarch64"} else "x64"
        return f"node-v{NODE_VERSION}-darwin-{arch}.tar.gz", "tar"
    if sys.platform.startswith("linux"):
        arch_map = {"x86_64": "x64", "amd64": "x64", "aarch64": "arm64", "arm64": "arm64"}
        arch = arch_map.get(machine)
        if arch:
            return f"node-v{NODE_VERSION}-linux-{arch}.tar.xz", "tar"
    raise RuntimeError(f"Node.js {NODE_VERSION} does not have a bundled archive for {sys.platform}/{machine}.")


def find_winget_node() -> Path | None:
    if os.name != "nt":
        return None
    packages = Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "WinGet" / "Packages"
    for package in packages.glob("OpenJS.NodeJS.22_*/node-v22*-win-*/node.exe"):
        if package.is_file():
            return package
    return None


def current_node() -> Path | None:
    local = node_path(data_root() / "runtime" / "node")
    if local.is_file():
        return local
    system = find_winget_node()
    if system:
        return system
    found = shutil.which("node.exe" if os.name == "nt" else "node")
    return Path(found) if found else None


def download(url: str, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    partial = destination.with_suffix(destination.suffix + ".part")
    for attempt in range(1, 6):
        try:
            log(f"Downloading {url} (attempt {attempt}/5)")
            request = urllib.request.Request(url, headers={"User-Agent": "HoloNet/1.0"})
            with urllib.request.urlopen(request, timeout=300) as response, partial.open("wb") as output:
                shutil.copyfileobj(response, output, length=1024 * 1024)
            partial.replace(destination)
            return
        except (OSError, urllib.error.URLError) as error:
            partial.unlink(missing_ok=True)
            if attempt == 5:
                raise RuntimeError(f"Could not download {url}: {error}") from error
            time.sleep(attempt * 3)


def safe_extract_tar(archive: Path, target: Path) -> None:
    target_resolved = target.resolve()
    with tarfile.open(archive, "r:*") as handle:
        for member in handle.getmembers():
            member_path = (target / member.name).resolve()
            if member_path != target_resolved and target_resolved not in member_path.parents:
                raise RuntimeError(f"Unsafe path in archive: {member.name}")
        handle.extractall(target, filter="data")


def safe_extract_zip(archive: Path, target: Path) -> None:
    target_resolved = target.resolve()
    with zipfile.ZipFile(archive) as handle:
        for member in handle.infolist():
            member_path = (target / member.filename).resolve()
            if member_path != target_resolved and target_resolved not in member_path.parents:
                raise RuntimeError(f"Unsafe path in archive: {member.filename}")
        handle.extractall(target)


def install_node(runtime: Path) -> Path:
    node = current_node()
    if node:
        version = subprocess.run([str(node), "--version"], check=True, capture_output=True, text=True).stdout.strip()
        if version.startswith("v22."):
            try:
                npm_cli(node)
                log(f"Using Node.js {version}")
                return node
            except RuntimeError:
                log("The system Node.js installation has no discoverable npm CLI; using the bundled runtime.")
        else:
            log(f"Found {version}; Zigbee2MQTT setup requires Node.js 22, installing the bundled runtime.")

    filename, archive_type = node_asset()
    archive = data_root() / "downloads" / filename
    if not archive.exists():
        download(f"https://nodejs.org/dist/v{NODE_VERSION}/{filename}", archive)

    temporary = runtime / "node-extract"
    shutil.rmtree(temporary, ignore_errors=True)
    temporary.mkdir(parents=True, exist_ok=True)
    if archive_type == "zip":
        safe_extract_zip(archive, temporary)
    else:
        safe_extract_tar(archive, temporary)

    extracted = next((path for path in temporary.iterdir() if path.is_dir()), None)
    if not extracted:
        raise RuntimeError("The Node.js archive contained no runtime directory.")
    node_home = runtime / "node"
    shutil.rmtree(node_home, ignore_errors=True)
    shutil.move(str(extracted), node_home)
    shutil.rmtree(temporary, ignore_errors=True)
    node = node_path(node_home)
    if not node.is_file():
        raise RuntimeError(f"Node.js executable not found in {node_home}.")
    log(f"Installed Node.js {NODE_VERSION} at {node}")
    return node


def npm_cli(node: Path) -> Path:
    candidates = [node.parent / "node_modules" / "npm" / "bin" / "npm-cli.js"]
    npm_command = shutil.which("npm.cmd" if os.name == "nt" else "npm")
    if npm_command:
        npm_path = Path(npm_command).resolve()
        if npm_path.name == "npm-cli.js":
            candidates.append(npm_path)
        candidates.extend([
            npm_path.parent / "node_modules" / "npm" / "bin" / "npm-cli.js",
            npm_path.parent.parent / "lib" / "node_modules" / "npm" / "bin" / "npm-cli.js",
            npm_path.parent.parent / "share" / "nodejs" / "npm" / "bin" / "npm-cli.js",
        ])
    for candidate in candidates:
        if candidate and candidate.is_file():
            return candidate
    raise RuntimeError(f"npm CLI was not found beside Node.js {node}.")


def run(command: list[str], cwd: Path, env: dict[str, str]) -> None:
    log("Running: " + " ".join(command))
    log_path = data_root() / "setup.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    options: dict[str, object] = {}
    if os.name == "nt":
        options["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    with log_path.open("a", encoding="utf-8") as output:
        result = subprocess.run(command, cwd=cwd, env=env, stdout=output, stderr=subprocess.STDOUT, **options)
    if result.returncode != 0:
        raise RuntimeError(f"Command failed with exit code {result.returncode}: {command[0]}")


def install() -> None:
    root = data_root()
    runtime = root / "runtime"
    downloads = root / "downloads"
    node = install_node(runtime)
    node_dir = node.parent
    env = os.environ.copy()
    env["PATH"] = str(node_dir) + os.pathsep + env.get("PATH", "")

    pnpm_home = runtime / "pnpm"
    pnpm = pnpm_home / "node_modules" / "pnpm" / "bin" / "pnpm.cjs"
    if not pnpm.is_file():
        pnpm_home.mkdir(parents=True, exist_ok=True)
        run([str(node), str(npm_cli(node)), "install", "--prefix", str(pnpm_home), f"pnpm@{PNPM_VERSION}"], root, env)

    broker_home = runtime / "broker"
    broker_home.mkdir(parents=True, exist_ok=True)
    bundled_broker = resource_root() / "broker"
    for filename in ("package.json", "broker.mjs"):
        source = bundled_broker / filename
        if not source.is_file():
            raise RuntimeError(f"Bundled broker file is missing: {source}")
        shutil.copy2(source, broker_home / filename)
    if not (broker_home / "node_modules" / "aedes").is_dir():
        run([str(node), str(npm_cli(node)), "install", "--omit=dev"], broker_home, env)

    z2m_home = runtime / "zigbee2mqtt"
    z2m_archive = downloads / f"zigbee2mqtt-{Z2M_VERSION}.zip"
    if not (z2m_home / "package.json").is_file():
        bundled_archive = resource_root() / "downloads" / z2m_archive.name
        if bundled_archive.is_file() and not z2m_archive.is_file():
            z2m_archive.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(bundled_archive, z2m_archive)
        if not z2m_archive.exists():
            download(f"https://codeload.github.com/Koenkk/zigbee2mqtt/zip/refs/tags/{Z2M_VERSION}", z2m_archive)
        extraction = runtime / "z2m-extract"
        shutil.rmtree(extraction, ignore_errors=True)
        extraction.mkdir(parents=True, exist_ok=True)
        safe_extract_zip(z2m_archive, extraction)
        source_dir = next((path for path in extraction.iterdir() if path.is_dir()), None)
        if not source_dir:
            raise RuntimeError("The Zigbee2MQTT archive contained no project directory.")
        shutil.rmtree(z2m_home, ignore_errors=True)
        shutil.move(str(source_dir), z2m_home)
        shutil.rmtree(extraction, ignore_errors=True)

    log(f"Installing Zigbee2MQTT {Z2M_VERSION} dependencies; this may take several minutes.")
    run(
        [str(node), str(pnpm), "install", "--frozen-lockfile", "--fetch-timeout", "300000", "--network-concurrency", "4"],
        z2m_home,
        env,
    )
    log("Runtime setup completed successfully.")


def main() -> int:
    try:
        install()
        return 0
    except Exception as error:
        log(f"Runtime setup failed: {error}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
