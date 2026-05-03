"""
core/config.py - Configuration management untuk Dockman
"""

import configparser
import socket
import getpass
import shutil
import subprocess
from pathlib import Path

VERSION    = "2.2.0"
APP_NAME   = "DOCKMAN"
CONFIG_DIR  = Path.home() / ".config" / "dockman"
CONFIG_FILE = CONFIG_DIR / "config.ini"

DEFAULT_CONFIG = {
    "general": {
        "editor":          "nano",
        "hostname":        socket.gethostname(),
        "fetch_interval":  "10",
        "doc_output_dir":  str(Path.home()),
    },
    "docker": {
        "compose_file": "",
        "compose_dir":  "",
        "compose_cmd":  "auto",
    },
    "rclone": {
        "remote_name":  "mega",
        "remote_path":  "film",
        "dest_radarr":  "/mnt/media/downloads/complete/radarr",
        "dest_sonarr":  "/mnt/media/downloads/complete/sonarr",
    },
    "alias": {
        "file": str(Path.home() / ".bashrc"),
    },
}

_cfg = configparser.ConfigParser()


def load() -> configparser.ConfigParser:
    global _cfg
    _cfg = configparser.ConfigParser()
    for section, values in DEFAULT_CONFIG.items():
        _cfg[section] = dict(values)
    if CONFIG_FILE.exists():
        _cfg.read(CONFIG_FILE)
    return _cfg


def save(cfg: configparser.ConfigParser = None):
    target = cfg or _cfg
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_FILE, "w") as f:
        target.write(f)


def get(section: str, key: str, fallback: str = "") -> str:
    try:
        return _cfg.get(section, key, fallback=fallback)
    except Exception:
        return fallback


def set_value(section: str, key: str, value: str):
    if section not in _cfg:
        _cfg[section] = {}
    _cfg[section][key] = value
    save()


def get_hostname() -> str:
    return get("general", "hostname") or socket.gethostname()

def get_editor() -> str:
    return get("general", "editor", "nano")

def get_compose_file() -> str:
    return get("docker", "compose_file", "")

def get_compose_dir() -> str:
    return get("docker", "compose_dir", "")

def get_compose_cmd() -> str:
    cmd = get("docker", "compose_cmd", "auto")
    if cmd != "auto":
        return cmd
    return detect_compose_cmd()

def get_doc_output_dir() -> str:
    return get("general", "doc_output_dir", str(Path.home()))

def get_current_user() -> str:
    try:
        return getpass.getuser()
    except Exception:
        import os
        return os.environ.get("USER", os.environ.get("LOGNAME", "unknown"))

def detect_compose_cmd() -> str:
    r = subprocess.run(["docker", "compose", "version"], capture_output=True, text=True)
    if r.returncode == 0:
        return "docker compose"
    if shutil.which("docker-compose"):
        return "docker-compose"
    return "docker compose"

def find_compose_files() -> list:
    SKIP_PREFIXES = ("/sys", "/proc", "/dev", "/run/user", "/snap")
    candidates = []
    search_dirs = [
        Path.home(), Path("/opt"), Path("/srv"),
        Path("/data"), Path("/mnt"), Path("/etc/docker"),
    ]
    try:
        with open("/proc/mounts") as f:
            for line in f:
                parts = line.split()
                if len(parts) >= 2:
                    mp = Path(parts[1])
                    mp_str = str(mp)
                    if (mp not in search_dirs and mp != Path("/")
                            and not any(mp_str.startswith(s) for s in SKIP_PREFIXES)):
                        search_dirs.append(mp)
    except Exception:
        pass
    names = ["docker-compose.yml", "docker-compose.yaml", "compose.yml", "compose.yaml"]
    seen = set()
    for d in search_dirs:
        d_str = str(d)
        if any(d_str.startswith(s) for s in SKIP_PREFIXES):
            continue
        for name in names:
            p = d / name
            try:
                if p.exists() and str(p) not in seen:
                    candidates.append(str(p))
                    seen.add(str(p))
            except (PermissionError, OSError):
                continue
        try:
            for sub in d.iterdir():
                try:
                    if not sub.is_dir():
                        continue
                except (PermissionError, OSError):
                    continue
                sub_str = str(sub)
                if any(sub_str.startswith(s) for s in SKIP_PREFIXES):
                    continue
                for name in names:
                    pp = sub / name
                    try:
                        if pp.exists() and str(pp) not in seen:
                            candidates.append(str(pp))
                            seen.add(str(pp))
                    except (PermissionError, OSError):
                        continue
        except (PermissionError, OSError):
            pass
    return candidates[:10]

def is_first_run() -> bool:
    return not CONFIG_FILE.exists() or get_compose_file() == ""
