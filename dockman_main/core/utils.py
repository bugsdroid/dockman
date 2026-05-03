"""
core/utils.py - Utility functions untuk Dockman
"""

import subprocess
import os
import re
import shutil
from typing import Tuple, Optional


class DockerError(Exception):
    """Docker-related errors dengan pesan yang informatif."""
    pass


def run_cmd(cmd: str, timeout: int = 30) -> Tuple[str, str, int]:
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
        return r.stdout.strip(), r.stderr.strip(), r.returncode
    except subprocess.TimeoutExpired:
        return "", f"Timeout setelah {timeout}s", 1
    except FileNotFoundError as e:
        return "", f"Perintah tidak ditemukan: {e}", 127
    except Exception as e:
        return "", str(e), 1


def run_interactive(cmd: str) -> int:
    try:
        return subprocess.run(cmd, shell=True).returncode
    except KeyboardInterrupt:
        return 130
    except Exception as e:
        print(f"  Error: {e}")
        return 1


def run_stream(cmd: str):
    try:
        proc = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, text=True, bufsize=1)
        for line in proc.stdout:
            yield line.rstrip()
        proc.wait()
        yield f"__EXIT__{proc.returncode}"
    except Exception as e:
        yield f"__ERROR__{e}"


def sanitize_input(s: str) -> str:
    if not s:
        return ""
    dangerous = [";", "&", "|", "`", "$", "(", ")", "<", ">", "\\", "\n", "\r", "'", '"']
    result = s
    for ch in dangerous:
        result = result.replace(ch, "")
    return result.strip()


def check_docker() -> str:
    from core.config import get_current_user
    docker_bin = shutil.which("docker") or "/usr/bin/docker"
    if not os.path.exists(docker_bin):
        raise DockerError("Docker tidak ditemukan di sistem.\nInstall Docker: https://docs.docker.com/engine/install/")
    out, err, code = run_cmd(f"{docker_bin} info --format '{{{{.ServerVersion}}}}'")
    if code != 0:
        if "permission denied" in err.lower():
            user = get_current_user()
            raise DockerError(f"Tidak punya akses ke Docker socket.\nJalankan:\n  sudo usermod -aG docker {user}\nLalu logout & login ulang, atau:\n  newgrp docker")
        raise DockerError(f"Docker daemon tidak bisa diakses.\nPastikan Docker service berjalan:\n  sudo systemctl start docker\nDetail: {err}")
    return out.strip()


def format_bytes(num_bytes: int) -> str:
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if num_bytes < 1024.0:
            return f"{num_bytes:.1f} {unit}"
        num_bytes /= 1024.0
    return f"{num_bytes:.1f} PB"


def check_tool(name: str) -> Optional[str]:
    return shutil.which(name)
