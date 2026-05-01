#!/usr/bin/env python3
"""
dockman - Docker Manager TUI (compiled single-file)
Version : 2.2.0
Built   : 2026-05-01 00:40:07
License : MIT
Repo    : https://github.com/USERNAME/dockman

File ini di-generate otomatis oleh build.py.
Jangan edit langsung - edit source di folder dockman/ lalu build ulang.
"""

import configparser
import socket
import getpass
import shutil
import subprocess
from pathlib import Path
import os
import re
from typing import Tuple, Optional
from typing import List, Dict, Optional
from datetime import datetime
from typing import Callable, Optional
import sys
import time
import curses
from typing import List, Dict, Callable, Optional
import traceback

# ======================================================================
# SOURCE: core/config.py
# ======================================================================


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
    r = subprocess.run(
        ["docker", "compose", "version"],
        capture_output=True, text=True
    )
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
                    if (mp not in search_dirs
                            and mp != Path("/")
                            and not any(mp_str.startswith(s) for s in SKIP_PREFIXES)):
                        search_dirs.append(mp)
    except Exception:
        pass

    names = ["docker-compose.yml", "docker-compose.yaml",
             "compose.yml", "compose.yaml"]
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

# ======================================================================
# SOURCE: core/utils.py
# ======================================================================



class DockerError(Exception):
    """Docker-related errors dengan pesan yang informatif."""
    pass


def run_cmd(cmd: str, timeout: int = 30) -> Tuple[str, str, int]:
    """
    Jalankan shell command, return (stdout, stderr, returncode).
    Tidak pernah raise exception - semua error dikembalikan sebagai tuple.
    """
    try:
        r = subprocess.run(
            cmd, shell=True,
            capture_output=True,
            text=True,
            timeout=timeout
        )
        return r.stdout.strip(), r.stderr.strip(), r.returncode
    except subprocess.TimeoutExpired:
        return "", f"Timeout setelah {timeout}s", 1
    except FileNotFoundError as e:
        return "", f"Perintah tidak ditemukan: {e}", 127
    except Exception as e:
        return "", str(e), 1


def run_interactive(cmd: str) -> int:
    """
    Jalankan command interaktif (dengan TTY).
    Return exit code.
    """
    try:
        return subprocess.run(cmd, shell=True).returncode
    except KeyboardInterrupt:
        return 130
    except Exception as e:
        print(f"  Error: {e}")
        return 1


def run_stream(cmd: str):
    """
    Generator: jalankan command dan yield output line by line.
    Berguna untuk Rich progress display.
    """
    try:
        proc = subprocess.Popen(
            cmd, shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )
        for line in proc.stdout:
            yield line.rstrip()
        proc.wait()
        yield f"__EXIT__{proc.returncode}"
    except Exception as e:
        yield f"__ERROR__{e}"


def sanitize_input(s: str) -> str:
    """
    Sanitasi input user - hapus karakter berbahaya untuk shell.
    Untuk nama session, nama file, dll.
    """
    if not s:
        return ""
    dangerous = [";", "&", "|", "`", "$", "(", ")", "<", ">",
                 "\\", "\n", "\r", "'", '"']
    result = s
    for ch in dangerous:
        result = result.replace(ch, "")
    return result.strip()


def check_docker() -> str:
    """
    Cek apakah docker daemon bisa diakses.
    Return versi docker kalau OK.
    Raise DockerError kalau gagal.
    """
    # (inline import stripped by build.py: from core.config import get_current_user)
    docker_bin = shutil.which("docker") or "/usr/bin/docker"

    if not os.path.exists(docker_bin):
        raise DockerError(
            "Docker tidak ditemukan di sistem.\n"
            "Install Docker: https://docs.docker.com/engine/install/"
        )

    out, err, code = run_cmd(f"{docker_bin} info --format '{{{{.ServerVersion}}}}'")
    if code != 0:
        if "permission denied" in err.lower():
            user = get_current_user()
            raise DockerError(
                f"Tidak punya akses ke Docker socket.\n"
                f"Jalankan:\n"
                f"  sudo usermod -aG docker {user}\n"
                f"Lalu logout & login ulang, atau:\n"
                f"  newgrp docker"
            )
        raise DockerError(
            f"Docker daemon tidak bisa diakses.\n"
            f"Pastikan Docker service berjalan:\n"
            f"  sudo systemctl start docker\n"
            f"Detail: {err}"
        )
    return out.strip()


def format_bytes(num_bytes: int) -> str:
    """Format bytes ke human readable."""
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if num_bytes < 1024.0:
            return f"{num_bytes:.1f} {unit}"
        num_bytes /= 1024.0
    return f"{num_bytes:.1f} PB"


def check_tool(name: str) -> Optional[str]:
    """Cek apakah tool tersedia. Return path atau None."""
    return shutil.which(name)

# ======================================================================
# SOURCE: core/docker.py
# ======================================================================



# ── Container ──────────────────────────────────────────────────────────────────

def get_containers() -> List[Dict]:
    """Ambil semua container (running & stopped)."""
    out, err, code = run_cmd(
        'docker ps -a --format "{{.Names}}|{{.Status}}|{{.Image}}|{{.Ports}}"'
    )
    if code != 0:
        return []
    containers = []
    for line in out.splitlines():
        if not line.strip():
            continue
        parts = line.split("|")
        name    = parts[0] if len(parts) > 0 else "?"
        status  = parts[1] if len(parts) > 1 else "?"
        image   = parts[2] if len(parts) > 2 else "?"
        ports   = parts[3] if len(parts) > 3 else ""
        running = status.lower().startswith("up")
        healthy = "(healthy)" in status.lower()
        containers.append({
            "name":    name,
            "status":  status,
            "image":   image,
            "ports":   ports,
            "running": running,
            "healthy": healthy,
        })
    return containers


def get_container_logs(name: str, tail: int = 50) -> str:
    """Ambil logs container."""
    out, err, code = run_cmd(f"docker logs --tail={tail} {name} 2>&1")
    if code != 0:
        return err or "Tidak ada output."
    return out or "(kosong)"


def get_container_inspect(name: str) -> str:
    """Ambil inspect container sebagai JSON string."""
    out, err, code = run_cmd(f"docker inspect {name}")
    if code != 0:
        return err
    return out


def container_action(name: str, action: str) -> tuple:
    """Jalankan aksi pada container. Return (success, message)."""
    valid = {"start", "stop", "restart", "rm", "pause", "unpause"}
    if action not in valid:
        return False, f"Aksi tidak valid: {action}"
    flags = "--force" if action == "rm" else ""
    out, err, code = run_cmd(f"docker {action} {flags} {name}")
    if code == 0:
        return True, f"Container '{name}' berhasil di-{action}."
    return False, err or f"Gagal menjalankan {action} pada '{name}'."


def pull_image(image: str) -> tuple:
    """Pull image. Return (success, message)."""
    out, err, code = run_cmd(f"docker pull {image}", timeout=300)
    if code == 0:
        return True, f"Image '{image}' berhasil di-pull."
    return False, err


def get_container_image(name: str) -> str:
    """Ambil nama image dari container."""
    out, _, _ = run_cmd(
        f"docker inspect --format='{{{{.Config.Image}}}}' {name}"
    )
    return out.strip()


# ── Images ────────────────────────────────────────────────────────────────────

def get_images() -> List[Dict]:
    """Ambil semua docker images."""
    out, _, code = run_cmd(
        'docker images --format "{{.Repository}}:{{.Tag}}|{{.Size}}|{{.CreatedSince}}|{{.ID}}"'
    )
    if code != 0:
        return []
    images = []
    for line in out.splitlines():
        if not line.strip():
            continue
        parts = line.split("|")
        images.append({
            "name":    parts[0] if len(parts) > 0 else "?",
            "size":    parts[1] if len(parts) > 1 else "?",
            "created": parts[2] if len(parts) > 2 else "?",
            "id":      parts[3] if len(parts) > 3 else "?",
        })
    return images


def get_dangling_images() -> List[str]:
    """Ambil list dangling image IDs."""
    out, _, _ = run_cmd("docker images -f dangling=true -q")
    return [i for i in out.splitlines() if i.strip()]


def remove_image(name: str) -> tuple:
    out, err, code = run_cmd(f"docker rmi {name}")
    return (True, f"Image '{name}' dihapus.") if code == 0 else (False, err)


# ── Volumes ───────────────────────────────────────────────────────────────────

def get_orphan_volumes() -> List[str]:
    """Ambil list orphan volume names."""
    out, _, _ = run_cmd("docker volume ls -f dangling=true -q")
    return [v for v in out.splitlines() if v.strip()]


# ── System ────────────────────────────────────────────────────────────────────

def get_disk_usage() -> str:
    """Ambil docker system df output."""
    out, err, code = run_cmd("docker system df")
    return out if code == 0 else err


def get_stats_once() -> List[Dict]:
    """
    Ambil stats semua container satu kali (no-stream).
    Return list of dict.
    """
    out, _, code = run_cmd(
        'docker stats --no-stream --format '
        '"{{.Name}}|{{.CPUPerc}}|{{.MemUsage}}|{{.NetIO}}|{{.BlockIO}}"'
    )
    if code != 0:
        return []
    stats = []
    for line in out.splitlines():
        if not line.strip():
            continue
        parts = line.split("|")
        stats.append({
            "name":    parts[0] if len(parts) > 0 else "?",
            "cpu":     parts[1] if len(parts) > 1 else "?",
            "mem":     parts[2] if len(parts) > 2 else "?",
            "net":     parts[3] if len(parts) > 3 else "?",
            "block":   parts[4] if len(parts) > 4 else "?",
        })
    return stats


# ── Compose ───────────────────────────────────────────────────────────────────

def compose_action(action: str, flags: str = "") -> tuple:
    """
    Jalankan docker compose action.
    action: up, down, pull, ps, config
    """
    compose_dir  = get_compose_dir()
    compose_cmd  = get_compose_cmd()

    if not compose_dir:
        return False, "Compose dir belum dikonfigurasi. Jalankan wizard setup."

    cmd = f"cd '{compose_dir}' && {compose_cmd} {action} {flags}"
    out, err, code = run_cmd(cmd, timeout=300)

    if code == 0:
        return True, out
    return False, err or f"Compose {action} gagal."


def compose_validate() -> tuple:
    """Validasi docker-compose.yml."""
    compose_dir = get_compose_dir()
    compose_cmd = get_compose_cmd()
    if not compose_dir:
        return False, "Compose dir belum dikonfigurasi."
    out, err, code = run_cmd(f"cd '{compose_dir}' && {compose_cmd} config --quiet")
    if code == 0:
        return True, "Config valid!"
    return False, err


# ── GNU Screen ───────────────────────────────────────────────────────────────

def get_screens() -> List[Dict]:
    """Ambil list GNU screen sessions."""
    out, _, _ = run_cmd("screen -ls 2>&1")
    sessions = []
    for line in out.splitlines():
        line = line.strip()
        if "." in line and any(s in line for s in ("Attached", "Detached", "Dead")):
            parts = line.split()
            if not parts:
                continue
            sid    = parts[0]
            pid    = sid.split(".")[0] if "." in sid else "?"
            name   = sid.split(".", 1)[1] if "." in sid else sid
            status = next(
                (p.strip("()") for p in parts
                 if any(s in p for s in ("Attached", "Detached", "Dead"))),
                "Unknown"
            )
            sessions.append({
                "sid": sid, "pid": pid,
                "name": name, "status": status
            })
    return sessions


def screen_kill(sid: str) -> tuple:
    out, err, code = run_cmd(f"screen -S {sid} -X quit")
    return (True, "Session dimatikan.") if code == 0 else (False, err)

# ======================================================================
# SOURCE: core/serverdocs.py
# ======================================================================




def _run(cmd: str) -> str:
    """Jalankan command, return output atau string error."""
    out, err, code = run_cmd(cmd, timeout=15)
    if code == 0 and out:
        return out
    return err or "(tidak ada output)"


def _section(title: str) -> str:
    return f"\n{'='*60}\n {title}\n{'='*60}\n"


def _divider() -> str:
    return "-" * 60 + "\n"


class ServerDocsGenerator:
    """
    Generate dokumentasi server lengkap.
    Setiap section bisa dipanggil sendiri-sendiri,
    atau semua sekaligus via generate().
    """

    def __init__(self, output_dir: str = None, progress_cb: Callable = None):
        """
        output_dir  : folder output. Default dari config.
        progress_cb : callback(step: int, total: int, label: str)
                      dipanggil setiap section selesai.
        """
        # (inline import stripped by build.py: from core.config import get_doc_output_dir)
        self.output_dir  = Path(output_dir or get_doc_output_dir())
        self.progress_cb = progress_cb or (lambda s, t, l: None)
        self.hostname    = socket.gethostname()
        self._lines      = []

    def _w(self, text: str = ""):
        """Append line ke buffer."""
        self._lines.append(text)

    def _flush(self) -> str:
        """Ambil semua buffer sebagai string."""
        return "\n".join(self._lines)

    # ── Sections ──────────────────────────────────────────────────────────────

    def section_header(self):
        self._w("=" * 60)
        self._w(f" DOKUMENTASI SERVER: {self.hostname}")
        self._w(f" Dibuat pada: {datetime.now().strftime('%d %B %Y, %H:%M WIB')}")
        self._w("=" * 60)

    def section_system(self):
        self._w(_section("INFORMASI SISTEM"))
        self._w(f"Hostname       : {self.hostname}")
        self._w(f"OS             : {_run('lsb_release -d | cut -f2').strip()}")
        self._w(f"Kernel         : {_run('uname -r')}")
        self._w(f"Arsitektur     : {_run('uname -m')}")
        self._w(f"Uptime         : {_run('uptime -p')}")

    def section_hardware(self):
        self._w(_section("HARDWARE"))
        cpu = _run("lscpu | grep 'Model name' | sed 's/Model name:[[:space:]]*//' | xargs")
        self._w(f"CPU            : {cpu}")
        self._w(f"Core           : {_run('nproc')} Core")
        self._w(f"RAM Total      : {_run('free -h | awk \"/^Mem:/ {print $2}\"')}")
        self._w(f"RAM Terpakai   : {_run('free -h | awk \"/^Mem:/ {print $3}\"')}")
        self._w(f"RAM Bebas      : {_run('free -h | awk \"/^Mem:/ {print $4}\"')}")
        gpu = _run("lspci | grep -i vga | sed 's/.*: //'")
        self._w(f"GPU            : {gpu}")

    def section_storage(self):
        self._w(_section("STORAGE"))
        self._w(_run("lsblk -o NAME,SIZE,TYPE,FSTYPE,MOUNTPOINT,LABEL"))
        self._w("\n--- Penggunaan Disk ---")
        self._w(_run("df -h --output=target,size,used,avail,pcent | grep -E '^(/|/data|/mnt|/boot)'"))

    def section_mounts(self):
        self._w(_section("MOUNT POINTS MEDIA"))
        # Ambil semua mount di /mnt dan /data
        out = _run("df -h | grep -E '/mnt|/data'")
        self._w(out if out else "(tidak ada mount point)")

    def section_network(self):
        self._w(_section("JARINGAN"))
        self._w("--- Interface & IP ---")
        self._w(_run("ip -br addr show"))
        self._w("\n--- DNS ---")
        self._w(_run("grep nameserver /etc/resolv.conf"))
        self._w("\n--- Port Terbuka ---")
        self._w(_run("ss -tlnp | grep LISTEN"))

    def section_firewall(self):
        self._w(_section("FIREWALL (UFW)"))
        out = _run("ufw status verbose 2>/dev/null")
        self._w(out if "active" in out.lower() or "inactive" in out.lower()
                else "UFW tidak terinstall atau tidak aktif.")

    def section_software(self):
        self._w(_section("PACKAGE & SOFTWARE"))
        pkg_count = _run("dpkg -l 2>/dev/null | grep -c '^ii' || rpm -qa 2>/dev/null | wc -l")
        self._w(f"Total Package  : {pkg_count.strip()} package")
        self._w(f"Shell          : {_run('bash --version | head -1')}")
        self._w(f"Python         : {_run('python3 --version 2>/dev/null || echo Tidak terinstall')}")
        self._w(f"Docker         : {_run('docker --version 2>/dev/null || echo Tidak terinstall')}")
        self._w(f"rclone         : {_run('rclone --version 2>/dev/null | head -1 || echo Tidak terinstall')}")
        self._w(f"screen         : {_run('screen --version 2>/dev/null | head -1 || echo Tidak terinstall')}")

    def section_services(self):
        self._w(_section("SERVICES AKTIF"))
        self._w(_run(
            "systemctl list-units --type=service --state=running --no-legend "
            "| awk '{print $1, $3, $4}'"
        ))

    def section_docker(self):
        self._w(_section("DOCKER"))

        self._w("--- Versi ---")
        self._w(_run("docker version 2>/dev/null || echo 'Docker tidak terinstall'"))

        self._w("\n--- Info ---")
        self._w(_run(
            "docker info 2>/dev/null | grep -E "
            "'Containers|Running|Paused|Stopped|Images|Storage Driver|"
            "Docker Root Dir|Total Memory'"
        ))

        self._w("\n--- Semua Container ---")
        self._w(_run(
            "docker ps -a --format "
            "'table {{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}' 2>/dev/null"
        ))

        self._w("\n--- Images ---")
        self._w(_run(
            "docker images --format "
            "'table {{.Repository}}\t{{.Tag}}\t{{.Size}}\t{{.CreatedSince}}' 2>/dev/null"
        ))

        self._w("\n--- Networks ---")
        self._w(_run("docker network ls 2>/dev/null"))

        self._w("\n--- Volumes ---")
        self._w(_run("docker volume ls 2>/dev/null"))

        self._w("\n--- Disk Usage ---")
        self._w(_run("docker system df 2>/dev/null"))

    def section_compose_projects(self):
        self._w(_section("DOCKER COMPOSE PROJECTS"))

        search_base = "/home /root /opt /srv /etc /data /mnt"
        out = _run(
            f"find {search_base} -maxdepth 6 "
            r"\( -name 'docker-compose.yml' -o -name 'docker-compose.yaml' "
            r"-o -name 'compose.yml' -o -name 'compose.yaml' \) 2>/dev/null | sort"
        )
        files = [f for f in out.splitlines() if f.strip()]

        if not files:
            self._w("Tidak ada file docker-compose ditemukan.")
            return

        for i, filepath in enumerate(files, 1):
            dirpath = str(Path(filepath).parent)
            self._w(_divider())
            self._w(f" Project #{i}: {filepath}")
            self._w(_divider())
            self._w("[Status Compose]")
            compose_cmd = _run(
                f"cd '{dirpath}' && (docker compose ps 2>/dev/null || "
                f"docker-compose ps 2>/dev/null) || echo 'Tidak dapat membaca status'"
            )
            self._w(compose_cmd)
            self._w(f"\n[Isi {Path(filepath).name}]")
            try:
                with open(filepath, "r", errors="replace") as f:
                    self._w(f.read())
            except Exception as e:
                self._w(f"[Tidak bisa dibaca: {e}]")

    def section_yml_files(self):
        self._w(_section("SEMUA FILE YML / YAML"))
        search_base = "/home /root /opt /srv /etc /data /mnt"
        out = _run(
            f"find {search_base} -maxdepth 6 "
            r"\( -name '*.yml' -o -name '*.yaml' \) "
            r"! -path '*/node_modules/*' ! -path '*/.git/*' ! -path '*/vendor/*' "
            "2>/dev/null | sort"
        )
        files = [f for f in out.splitlines() if f.strip()]
        if not files:
            self._w("Tidak ada file YML ditemukan.")
            return
        for i, f in enumerate(files, 1):
            size  = _run(f"du -sh '{f}' 2>/dev/null | cut -f1")
            mtime = _run(f"stat -c '%y' '{f}' 2>/dev/null | cut -d. -f1")
            self._w(f"{i}. {f} [{size.strip()}] - {mtime.strip()}")

    def section_yml_contents(self):
        self._w(_section("ISI FILE YML (Non docker-compose)"))
        search_base = "/home /root /opt /srv /etc /data /mnt"
        out = _run(
            f"find {search_base} -maxdepth 6 "
            r"\( -name '*.yml' -o -name '*.yaml' \) "
            r"! -name 'docker-compose*' ! -name 'compose.yml' ! -name 'compose.yaml' "
            r"! -path '*/node_modules/*' ! -path '*/.git/*' ! -path '*/vendor/*' "
            "2>/dev/null | sort"
        )
        files = [f for f in out.splitlines() if f.strip()]
        if not files:
            self._w("Tidak ada file YML non-compose ditemukan.")
            return
        for filepath in files:
            self._w(_divider())
            self._w(f" {filepath}")
            self._w(_divider())
            try:
                with open(filepath, "r", errors="replace") as f:
                    self._w(f.read())
            except Exception as e:
                self._w(f"[Tidak bisa dibaca: {e}]")

    def section_cron(self):
        # (inline import stripped by build.py: from core.config import get_current_user)
        cur_user = get_current_user()

        self._w(_section("CRON JOBS"))

        self._w(f"--- Root ---")
        self._w(_run("crontab -l 2>/dev/null || echo 'Tidak ada cron job untuk root'"))

        self._w(f"\n--- User {cur_user} ---")
        self._w(_run(
            f"crontab -u {cur_user} -l 2>/dev/null || "
            f"echo 'Tidak ada cron job untuk {cur_user}'"
        ))

        self._w("\n--- /etc/cron.d/ ---")
        cron_d = Path("/etc/cron.d")
        if cron_d.exists():
            for f in sorted(cron_d.iterdir()):
                self._w(f"--- {f} ---")
                try:
                    self._w(f.read_text(errors="replace"))
                except Exception as e:
                    self._w(f"[Tidak bisa dibaca: {e}]")
        else:
            self._w("(tidak ada /etc/cron.d/)")

    def section_footer(self):
        # (inline import stripped by build.py: from core.config import get_current_user)
        self._w("")
        self._w("=" * 60)
        self._w(f" Dibuat oleh : {get_current_user()}")
        self._w(f" Waktu       : {datetime.now().strftime('%d %B %Y, %H:%M WIB')}")
        self._w("=" * 60)

    def section_netplan(self):
        """Baca konfigurasi netplan dari /etc/netplan/."""
        self._w(_section("NETPLAN NETWORK CONFIGURATION"))

        netplan_dir = Path("/etc/netplan")
        if not netplan_dir.exists():
            self._w("Netplan tidak ditemukan (/etc/netplan tidak ada).")
            self._w("Sistem mungkin menggunakan NetworkManager atau ifupdown.")
            return

        # Coba baca daftar file - mungkin butuh sudo
        try:
            files = sorted([
                f for f in netplan_dir.iterdir()
                if f.suffix in (".yaml", ".yml") and f.is_file()
            ])
        except PermissionError:
            # Coba via sudo
            out, err, code = run_cmd("sudo ls /etc/netplan/ 2>/dev/null")
            if code != 0:
                self._w("Tidak bisa membaca /etc/netplan/ (Permission denied).")
                self._w("Jalankan: sudo dockman report  atau  sudo dockman")
                return
            files = [netplan_dir / f.strip() for f in out.splitlines()
                     if f.strip().endswith(('.yaml', '.yml'))]
        except OSError as e:
            self._w(f"Error membaca /etc/netplan/: {e}")
            return

        if not files:
            self._w("Tidak ada file konfigurasi netplan ditemukan.")
            return

        self._w(f"Ditemukan {len(files)} file konfigurasi:\n")

        for filepath in files:
            self._w(_divider())
            self._w(f" File: {filepath}")
            self._w(_divider())

            # Coba baca langsung dulu
            content = None
            try:
                content = Path(filepath).read_text(errors="replace")
            except PermissionError:
                # Fallback ke sudo cat
                out, err, code = run_cmd(f"sudo cat '{filepath}' 2>/dev/null")
                if code == 0 and out:
                    content = out
                else:
                    self._w(f"[Permission denied - tidak bisa dibaca bahkan dengan sudo]")
                    self._w(f"Coba jalankan: sudo cat {filepath}")
            except OSError as e:
                self._w(f"[Error: {e}]")

            if content:
                self._w(content)
            self._w("")

        # Netplan status/info tambahan
        for cmd_try in [
            "netplan status 2>/dev/null",
            "sudo netplan status 2>/dev/null",
            "netplan ip leases 2>/dev/null",
        ]:
            out, _, code = run_cmd(cmd_try)
            if code == 0 and out and "command not found" not in out.lower():
                self._w("\n--- Netplan Status ---")
                self._w(out)
                break

    # ── Main generate ─────────────────────────────────────────────────────────

    SECTIONS = [
        ("Header",              "section_header"),
        ("Informasi Sistem",    "section_system"),
        ("Hardware",            "section_hardware"),
        ("Storage",             "section_storage"),
        ("Mount Points",        "section_mounts"),
        ("Jaringan",            "section_network"),
        ("Netplan Config",      "section_netplan"),
        ("Firewall",            "section_firewall"),
        ("Software",            "section_software"),
        ("Services",            "section_services"),
        ("Docker",              "section_docker"),
        ("Compose Projects",    "section_compose_projects"),
        ("File YML (list)",     "section_yml_files"),
        ("File YML (isi)",      "section_yml_contents"),
        ("Cron Jobs",           "section_cron"),
        ("Footer",              "section_footer"),
    ]

    def generate(self, output_path: Optional[str] = None) -> str:
        """
        Generate dokumentasi lengkap dan simpan ke file.
        Return path file yang dihasilkan.
        """
        total = len(self.SECTIONS)
        self._lines = []

        for step, (label, method_name) in enumerate(self.SECTIONS, 1):
            self.progress_cb(step, total, label)
            try:
                getattr(self, method_name)()
            except Exception as e:
                self._w(f"\n[ERROR di section {label}: {e}]\n")

        # Tentukan output path
        if output_path:
            out_path = Path(output_path)
        else:
            filename = f"server-docs-{datetime.now().strftime('%Y%m%d')}.txt"
            out_path = self.output_dir / filename

        # Pastikan folder ada
        out_path.parent.mkdir(parents=True, exist_ok=True)

        # Tulis file
        content = self._flush()
        out_path.write_text(content, encoding="utf-8", errors="replace")

        return str(out_path)

# ======================================================================
# SOURCE: ui/rich_ui.py
# ======================================================================


try:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich.text import Text
    from rich.live import Live
    from rich.progress import (
        Progress, SpinnerColumn, BarColumn,
        TextColumn, TimeElapsedColumn, TaskProgressColumn,
        MofNCompleteColumn,
    )
    from rich.syntax import Syntax
    from rich.columns import Columns
    from rich.rule import Rule
    from rich.padding import Padding
    from rich import box as rich_box
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False

console = Console() if RICH_AVAILABLE else None

# ── Unicode symbols (fallback ke ASCII kalau tidak support) ───────────────────
SYM = {
    "ok":       "[green]  [/green]",
    "err":      "[red]  [/red]",
    "warn":     "[yellow]  [/yellow]",
    "run":      "[green]  [/green]",
    "stop":     "[red]  [/red]",
    "healthy":  "[green]  [/green]",
    "docker":   "[cyan]  [/cyan]",
    "image":    "[blue]  [/blue]",
    "disk":     "[yellow]  [/yellow]",
    "net":      "[cyan]  [/cyan]",
    "cpu":      "[magenta]  [/magenta]",
    "mem":      "[blue]  [/blue]",
    "log":      "[cyan]  [/cyan]",
    "screen":   "[green]  [/green]",
    "file":     "[yellow]  [/yellow]",
    "folder":   "[yellow]  [/yellow]",
    "report":   "[cyan]  [/cyan]",
    "arrow":    "[dim]  [/dim]",
    "bullet":   "[dim]  [/dim]",
    "clock":    "[dim]  [/dim]",
    "server":   "[cyan]  [/cyan]",
    "user":     "[green]  [/green]",
    "key":      "[yellow]  [/yellow]",
    "wrench":   "[yellow]  [/yellow]",
    "star":     "[yellow]  [/yellow]",
}

def sym(name: str) -> str:
    """Return Rich markup symbol, atau ASCII fallback."""
    if not RICH_AVAILABLE:
        fallbacks = {
            "ok": "[OK]", "err": "[!!]", "warn": "[!!]",
            "run": "[>]", "stop": "[.]",
        }
        return fallbacks.get(name, "*")
    return SYM.get(name, "*")


def _fallback_print(text: str):
    import re
    clean = re.sub(r'\[/?[a-z0-9_ /]+\]', '', str(text))
    print(clean)


def richprint(text):
    if RICH_AVAILABLE:
        console.print(text)
    else:
        _fallback_print(text)


# ══════════════════════════════════════════════════════════════════════════════
#  CONTAINER VIEWS
# ══════════════════════════════════════════════════════════════════════════════

def show_containers(containers: List[Dict]):
    if not RICH_AVAILABLE:
        _show_containers_plain(containers)
        return

    running = sum(1 for c in containers if c["running"])
    stopped = len(containers) - running

    table = Table(
        title=f"{sym('docker')} Docker Containers",
        box=rich_box.ROUNDED,
        show_header=True,
        header_style="bold cyan",
        border_style="cyan",
        title_style="bold cyan",
        highlight=True,
        show_lines=True,
    )
    table.add_column("#",       style="dim",      width=3, justify="right")
    table.add_column("Nama",    style="bold",      min_width=18)
    table.add_column("Status",  min_width=26)
    table.add_column("Image",   min_width=35, overflow="fold")
    table.add_column("Ports",   overflow="fold",   min_width=12)

    for i, c in enumerate(containers, 1):
        if c["running"]:
            icon        = f"{sym('run')}"
            status_str  = f"[green]{c['status']}[/green]"
            name_str    = f"[bold green]{c['name']}[/bold green]"
        else:
            icon        = f"{sym('stop')}"
            status_str  = f"[red]{c['status']}[/red]"
            name_str    = f"[dim]{c['name']}[/dim]"

        table.add_row(
            str(i),
            f"{icon} {name_str}",
            status_str,
            f"[dim]{c['image']}[/dim]",
            c["ports"] or "[dim]-[/dim]",
        )

    console.print()
    console.print(table)
    console.print(
        f"  {sym('run')} [green]{running} running[/green]  "
        f"{sym('stop')} [red]{stopped} stopped[/red]  "
        f"{sym('bullet')} [dim]{len(containers)} total[/dim]"
    )
    console.print()


def _show_containers_plain(containers: List[Dict]):
    print(f"\n  {'#':<3} {'NAMA':<22} {'STATUS':<30} {'IMAGE':<35}")
    print("  " + "-" * 90)
    for i, c in enumerate(containers, 1):
        icon = ">" if c["running"] else "."
        print(f"  {i:<3} {icon} {c['name']:<20} {c['status']:<30} {c['image']:<35}")
    print()


def show_images(images: List[Dict]):
    if not RICH_AVAILABLE:
        for i, img in enumerate(images, 1):
            print(f"  {i:<3} {img['name']:<45} {img['size']:<12} {img['created']}")
        return

    table = Table(
        title=f"{sym('image')} Docker Images",
        box=rich_box.ROUNDED,
        header_style="bold cyan",
        border_style="cyan",
        title_style="bold cyan",
        show_lines=True,
    )
    table.add_column("#",       style="dim",  width=3, justify="right")
    table.add_column("Image",   style="bold", min_width=40)
    table.add_column("Size",    min_width=10, justify="right")
    table.add_column("Created", min_width=15)
    table.add_column("ID",      min_width=12, style="dim")

    for i, img in enumerate(images, 1):
        table.add_row(str(i), img["name"], img["size"], img["created"], img["id"][:12])

    console.print()
    console.print(table)
    console.print(f"  {sym('bullet')} [dim]{len(images)} images[/dim]\n")


def show_stats(stats: List[Dict]):
    if not RICH_AVAILABLE:
        for s in stats:
            print(f"  {s['name']:<22} CPU:{s['cpu']:<8} MEM:{s['mem']:<20} "
                  f"NET:{s['net']:<20} BLK:{s['block']}")
        return

    table = Table(
        title=f"{sym('cpu')} Docker Stats  [dim]{sym('clock')} {time.strftime('%H:%M:%S')}[/dim]",
        box=rich_box.ROUNDED,
        header_style="bold cyan",
        border_style="cyan",
        title_style="bold cyan",
        show_lines=True,
    )
    table.add_column("Container",  style="bold", min_width=18)
    table.add_column("CPU %",      min_width=8,  justify="right")
    table.add_column("Memory",     min_width=22, justify="right")
    table.add_column("Net I/O",    min_width=20, justify="right")
    table.add_column("Block I/O",  min_width=20, justify="right")

    for s in stats:
        try:
            cpu_val = float(s["cpu"].replace("%", "") or "0")
        except ValueError:
            cpu_val = 0.0

        if cpu_val > 80:
            cpu_style = "bold red"
            cpu_icon  = sym("err")
        elif cpu_val > 50:
            cpu_style = "yellow"
            cpu_icon  = sym("warn")
        else:
            cpu_style = "green"
            cpu_icon  = sym("ok")

        table.add_row(
            f"{sym('run')} {s['name']}",
            f"[{cpu_style}]{cpu_icon} {s['cpu']}[/{cpu_style}]",
            f"{sym('mem')} {s['mem']}",
            f"{sym('net')} {s['net']}",
            f"{sym('disk')} {s['block']}",
        )

    console.print()
    console.print(table)
    console.print()


def show_disk_usage(raw_output: str):
    if not RICH_AVAILABLE:
        print(raw_output)
        return
    console.print()
    console.print(Panel(
        raw_output,
        title=f"{sym('disk')} Docker Disk Usage",
        border_style="cyan",
        expand=False,
        padding=(0, 1),
    ))
    console.print()


# ══════════════════════════════════════════════════════════════════════════════
#  LOGS VIEW
# ══════════════════════════════════════════════════════════════════════════════

def show_logs(name: str, log_content: str):
    if not RICH_AVAILABLE:
        print(f"\n--- Logs: {name} ---\n{log_content}\n--- End ---\n")
        return

    # Color-code log lines
    colored = []
    for line in log_content.splitlines():
        ll = line.lower()
        if any(k in ll for k in ("error", "err", "fatal", "fail", "exception")):
            colored.append(f"[red]{sym('err')} {line}[/red]")
        elif any(k in ll for k in ("warn", "warning")):
            colored.append(f"[yellow]{sym('warn')} {line}[/yellow]")
        elif any(k in ll for k in ("info", "ok", "success", "start", "ready")):
            colored.append(f"[green]{sym('ok')} {line}[/green]")
        else:
            colored.append(f"[dim]{line}[/dim]")

    console.print()
    console.print(Panel(
        "\n".join(colored) or "[dim](kosong)[/dim]",
        title=f"{sym('log')} Logs: [bold cyan]{name}[/bold cyan]",
        border_style="cyan",
        subtitle=f"[dim]{sym('clock')} {time.strftime('%H:%M:%S')}[/dim]",
        padding=(0, 1),
    ))
    console.print()


def stream_logs(name: str, tail: int = 50):
    import subprocess

    if not RICH_AVAILABLE:
        print(f"\n  Live logs '{name}' -- Ctrl+C untuk stop\n" + "-"*55 + "\n")
        try:
            subprocess.run(f"docker logs -f --tail={tail} {name}", shell=True)
        except KeyboardInterrupt:
            pass
        return

    console.print()
    console.print(Rule(
        f"{sym('log')} Live Logs: [bold cyan]{name}[/bold cyan]  "
        f"[dim]Ctrl+C untuk stop[/dim]",
        style="cyan",
    ))
    console.print()

    try:
        proc = subprocess.Popen(
            f"docker logs -f --tail={tail} {name}",
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        for line in proc.stdout:
            line = line.rstrip()
            ll   = line.lower()
            if any(k in ll for k in ("error", "err", "fatal", "fail")):
                console.print(f"[red]{sym('err')} {line}[/red]")
            elif any(k in ll for k in ("warn", "warning")):
                console.print(f"[yellow]{sym('warn')} {line}[/yellow]")
            elif any(k in ll for k in ("info", "ok", "success", "start", "ready")):
                console.print(f"[green]{sym('ok')} {line}[/green]")
            else:
                console.print(f"[dim]{line}[/dim]")
        proc.wait()
    except KeyboardInterrupt:
        console.print(f"\n[dim]{sym('stop')} Stream dihentikan.[/dim]")


# ══════════════════════════════════════════════════════════════════════════════
#  INSPECT VIEW
# ══════════════════════════════════════════════════════════════════════════════

def show_inspect(name: str, json_str: str):
    if not RICH_AVAILABLE:
        print(json_str)
        return
    syntax = Syntax(json_str, "json", theme="monokai", line_numbers=True,
                    background_color="default")
    console.print()
    console.print(Panel(
        syntax,
        title=f"{sym('docker')} Inspect: [bold cyan]{name}[/bold cyan]",
        border_style="cyan",
        padding=(0, 1),
    ))
    console.print()


# ══════════════════════════════════════════════════════════════════════════════
#  SERVER DOCS PROGRESS
# ══════════════════════════════════════════════════════════════════════════════

def generate_server_docs_with_progress(output_dir: str = None,
                                        output_path: str = None) -> str:
    # (inline import stripped by build.py: from core.serverdocs import ServerDocsGenerator)

    if not RICH_AVAILABLE:
        return _generate_server_docs_plain(output_dir, output_path)

    result_path = [None]
    error       = [None]

    console.print()
    console.print(Rule(
        f"{sym('report')} [bold cyan]Generating Server Report[/bold cyan]",
        style="cyan",
    ))
    console.print()

    with Progress(
        SpinnerColumn(spinner_name="dots"),
        TextColumn("{task.description}"),
        BarColumn(bar_width=36, complete_style="cyan", finished_style="green"),
        MofNCompleteColumn(),
        TaskProgressColumn(),
        TimeElapsedColumn(),
        console=console,
        transient=False,
        expand=False,
    ) as progress:
        gen  = ServerDocsGenerator(output_dir=output_dir, progress_cb=None)
        total = len(gen.SECTIONS)
        task = progress.add_task(
            f"[cyan]{sym('arrow')} Memulai...[/cyan]", total=total
        )

        def progress_cb(step: int, total: int, label: str):
            progress.update(
                task,
                completed=step,
                description=f"[cyan]{sym('arrow')} {label}...[/cyan]",
            )

        gen.progress_cb = progress_cb
        try:
            result_path[0] = gen.generate(output_path=output_path)
        except Exception as e:
            error[0] = str(e)

    if error[0]:
        console.print(f"\n[red]{sym('err')} ERROR: {error[0]}[/red]")
        return ""

    return result_path[0]


def _generate_server_docs_plain(output_dir=None, output_path=None) -> str:
    # (inline import stripped by build.py: from core.serverdocs import ServerDocsGenerator)

    def progress_cb(step, total, label):
        print(f"  [{step:2d}/{total}] {label}...")

    gen = ServerDocsGenerator(output_dir=output_dir, progress_cb=progress_cb)
    return gen.generate(output_path=output_path)


# ══════════════════════════════════════════════════════════════════════════════
#  COMPOSE VIEW
# ══════════════════════════════════════════════════════════════════════════════

def show_compose_file(filepath: str):
    if not RICH_AVAILABLE:
        try:
            print(open(filepath).read())
        except Exception as e:
            print(f"Error: {e}")
        return
    try:
        content = open(filepath).read()
        syntax  = Syntax(content, "yaml", theme="monokai",
                         line_numbers=True, background_color="default")
        console.print()
        console.print(Panel(
            syntax,
            title=f"{sym('file')} [bold cyan]{filepath}[/bold cyan]",
            border_style="cyan",
            padding=(0, 1),
        ))
        console.print()
    except Exception as e:
        console.print(f"[red]{sym('err')} Error: {e}[/red]")


def show_screen_sessions(sessions: List[Dict]):
    if not RICH_AVAILABLE:
        for s in sessions:
            print(f"  {s['pid']:<8} {s['name']:<22} {s['status']}")
        return

    if not sessions:
        console.print(f"\n[dim]{sym('stop')} Tidak ada screen session aktif.[/dim]\n")
        return

    table = Table(
        title=f"{sym('screen')} GNU Screen Sessions",
        box=rich_box.ROUNDED,
        header_style="bold cyan",
        border_style="cyan",
        title_style="bold cyan",
        show_lines=True,
    )
    table.add_column("PID",    min_width=8,  style="dim")
    table.add_column("Nama",   min_width=22, style="bold")
    table.add_column("Status", min_width=12)

    for s in sessions:
        if s["status"] == "Attached":
            status_str = f"[green]{sym('run')} Attached[/green]"
        elif s["status"] == "Detached":
            status_str = f"[yellow]{sym('warn')} Detached[/yellow]"
        else:
            status_str = f"[red]{sym('stop')} {s['status']}[/red]"

        table.add_row(s["pid"], s["name"], status_str)

    console.print()
    console.print(table)
    console.print(f"  {sym('bullet')} [dim]{len(sessions)} session aktif[/dim]\n")


# ══════════════════════════════════════════════════════════════════════════════
#  CLI MODE
# ══════════════════════════════════════════════════════════════════════════════

def cli_header(hostname: str, version: str):
    if not RICH_AVAILABLE:
        print(f"\n  DOCKMAN v{version} -- {hostname}\n")
        return
    console.print()
    console.print(Panel(
        f"{sym('docker')} [bold cyan]DOCKMAN[/bold cyan] [dim]v{version}[/dim]"
        f"  {sym('arrow')}  {sym('server')} [bold]{hostname}[/bold]",
        border_style="cyan",
        expand=False,
        padding=(0, 2),
    ))
    console.print()


def cli_error(message: str):
    if RICH_AVAILABLE:
        console.print(f"\n[bold red]{sym('err')} ERROR:[/bold red] {message}\n")
    else:
        print(f"\n  ERROR: {message}\n")


def cli_success(message: str):
    if RICH_AVAILABLE:
        console.print(f"\n[bold green]{sym('ok')} OK:[/bold green] {message}\n")
    else:
        print(f"\n  OK: {message}\n")


def cli_info(message: str):
    if RICH_AVAILABLE:
        console.print(f"[cyan]{sym('bullet')} {message}[/cyan]")
    else:
        print(f"  {message}")


def confirm_cli(message: str) -> bool:
    try:
        ans = input(f"\n  {message} [y/N]: ").strip().lower()
        return ans == "y"
    except (EOFError, KeyboardInterrupt):
        return False


def wait_key(msg: str = "Tekan Enter untuk kembali..."):
    if RICH_AVAILABLE:
        console.print(f"\n[dim]{sym('arrow')} {msg}[/dim]")
    try:
        input()
    except (EOFError, KeyboardInterrupt):
        pass

# ======================================================================
# SOURCE: ui/wizard.py
# ======================================================================




def _banner(title: str):
    W = 58
    print(f"\n{'='*W}")
    print(f"  {title}")
    print(f"{'='*W}")


def _step(n: int, total: int, title: str):
    print(f"\n  [{n}/{total}] {title}")
    print("  " + "-" * 40)


def run_wizard():
    """
    Interactive first-run wizard.
    Tanya semua config penting dan simpan ke config file.
    """
    import configparser

    _banner(f"{config.APP_NAME} v{config.VERSION} - Setup Wizard")
    print("  Konfigurasi akan disimpan di:")
    print(f"  {config.CONFIG_FILE}")
    print()

    # Load existing config sebagai base
    cfg = config.load()
    TOTAL = 7

    # ── [1] Hostname ──────────────────────────────────────────────────────────
    _step(1, TOTAL, "Hostname Server")
    default = socket.gethostname()
    current = config.get("general", "hostname") or default
    val = input(f"  Hostname [{current}]: ").strip()
    cfg["general"]["hostname"] = val or current

    # ── [2] Docker Compose File ───────────────────────────────────────────────
    _step(2, TOTAL, "Lokasi docker-compose.yml")
    current_compose = config.get_compose_file()
    if current_compose:
        print(f"  Saat ini: {current_compose}")

    print("  Mencari file...", end="", flush=True)
    found = config.find_compose_files()
    print(f" {len(found)} ditemukan\n")

    if found:
        for i, f in enumerate(found):
            print(f"    {i+1}. {f}")
        print(f"    {len(found)+1}. Ketik manual")
        print(f"    0.  Skip (atur nanti)")
        print()
        val = input(f"  Pilih [0-{len(found)+1}]: ").strip()
        if val == "0":
            compose_file = current_compose or ""
        elif val.isdigit() and 1 <= int(val) <= len(found):
            compose_file = found[int(val) - 1]
        else:
            compose_file = val.strip() if val else (current_compose or "")
    else:
        print("  Tidak ada file ditemukan otomatis.")
        compose_file = input("  Path lengkap (Enter untuk skip): ").strip() or current_compose or ""

    if compose_file:
        cfg["docker"]["compose_file"] = compose_file
        cfg["docker"]["compose_dir"]  = str(Path(compose_file).parent)
        print(f"  OK: {compose_file}")
    else:
        print("  Skip - bisa diset nanti di Settings (t)")

    # ── [3] Docker Compose Command ────────────────────────────────────────────
    _step(3, TOTAL, "Docker Compose Command")
    print("  Mendeteksi...", end="", flush=True)
    detected = config.detect_compose_cmd()
    print(f" {detected}")

    current_cmd = config.get("docker", "compose_cmd", "auto")
    print(f"  Pilihan: auto / docker compose / docker-compose")
    val = input(f"  Command [{current_cmd}]: ").strip()
    cfg["docker"]["compose_cmd"] = val or current_cmd

    # ── [4] Editor ────────────────────────────────────────────────────────────
    _step(4, TOTAL, "Editor Teks Default")
    default_editor = (
        shutil.which("nano") and "nano" or
        shutil.which("vim")  and "vim"  or
        shutil.which("vi")   and "vi"   or "nano"
    )
    current_editor = config.get_editor() or default_editor
    val = input(f"  Editor [{current_editor}]: ").strip()
    cfg["general"]["editor"] = val or current_editor

    # ── [5] Server Report Output Dir ─────────────────────────────────────────
    _step(5, TOTAL, "Folder Output Server Report")
    current_doc = config.get_doc_output_dir() or str(Path.home())
    print(f"  Laporan server akan disimpan ke folder ini.")
    val = input(f"  Folder output [{current_doc}]: ").strip()
    if val:
        # Pastikan folder valid
        try:
            Path(val).mkdir(parents=True, exist_ok=True)
            cfg["general"]["doc_output_dir"] = val
            print(f"  OK: {val}")
        except Exception as e:
            print(f"  Folder tidak bisa dibuat: {e}. Pakai default.")
            cfg["general"]["doc_output_dir"] = current_doc
    else:
        cfg["general"]["doc_output_dir"] = current_doc

    # ── [6] Rclone ────────────────────────────────────────────────────────────
    _step(6, TOTAL, "Rclone Cloud Storage (Opsional)")
    if shutil.which("rclone"):
        # List remotes yang ada
        try:
            r = subprocess.run(["rclone", "listremotes"],
                               capture_output=True, text=True, timeout=5)
            remotes = [x.rstrip(":") for x in r.stdout.splitlines() if x.strip()]
        except Exception:
            remotes = []

        if remotes:
            print(f"  Remote tersedia: {', '.join(remotes)}")
        else:
            print("  Belum ada remote. Jalankan: rclone config")

        current_remote = config.get("rclone", "remote_name", "mega")
        val = input(f"  Nama remote [{current_remote}]: ").strip()
        if val:
            cfg["rclone"]["remote_name"] = val

        current_path = config.get("rclone", "remote_path", "film")
        val = input(f"  Path di remote [{current_path}]: ").strip()
        if val:
            cfg["rclone"]["remote_path"] = val

        current_radarr = config.get("rclone", "dest_radarr",
                                    "/mnt/media/downloads/complete/radarr")
        val = input(f"  Dest Radarr [{current_radarr}]: ").strip()
        if val:
            cfg["rclone"]["dest_radarr"] = val

        current_sonarr = config.get("rclone", "dest_sonarr",
                                    "/mnt/media/downloads/complete/sonarr")
        val = input(f"  Dest Sonarr [{current_sonarr}]: ").strip()
        if val:
            cfg["rclone"]["dest_sonarr"] = val
    else:
        print("  rclone tidak terinstall.")
        print("  Install: curl https://rclone.org/install.sh | sudo bash")
        print("  Skip - bisa dikonfigurasi nanti di Settings.")

    # ── [7] Alias file ────────────────────────────────────────────────────────
    _step(7, TOTAL, "File Alias / Bashrc")
    default_alias = str(Path.home() / ".bashrc")
    current_alias = config.get("alias", "file", default_alias)
    print(f"  File yang berisi alias shell kamu.")
    val = input(f"  Path [{current_alias}]: ").strip()
    if val:
        cfg["alias"]["file"] = val
    else:
        cfg["alias"]["file"] = current_alias

    # ── Simpan ────────────────────────────────────────────────────────────────
    print()
    _banner("Ringkasan Konfigurasi")
    print(f"  Hostname        : {cfg['general']['hostname']}")
    print(f"  Compose file    : {cfg['docker']['compose_file'] or '(belum diset)'}")
    print(f"  Compose command : {cfg['docker']['compose_cmd']}")
    print(f"  Editor          : {cfg['general']['editor']}")
    print(f"  Doc output dir  : {cfg['general']['doc_output_dir']}")
    print(f"  Rclone remote   : {cfg['rclone']['remote_name']}:{cfg['rclone']['remote_path']}")
    print(f"  Alias file      : {cfg['alias']['file']}")
    print(f"  Config file     : {config.CONFIG_FILE}")
    print()

    val = input("  Simpan konfigurasi? [Y/n]: ").strip()
    if val.lower() != "n":
        config.save(cfg)
        config.load()  # reload global config
        print(f"\n  OK: Config disimpan di {config.CONFIG_FILE}")
    else:
        print("  Config tidak disimpan.")
    print()

# ======================================================================
# SOURCE: ui/curses_ui.py
# ======================================================================



# ── Color pairs ───────────────────────────────────────────────────────────────

def init_colors():
    curses.start_color()
    curses.use_default_colors()
    curses.init_pair(1, curses.COLOR_CYAN,    -1)  # header
    curses.init_pair(2, curses.COLOR_GREEN,   -1)  # ok / running
    curses.init_pair(3, curses.COLOR_RED,     -1)  # error / stopped
    curses.init_pair(4, curses.COLOR_YELLOW,  -1)  # warning / subtitle
    curses.init_pair(5, curses.COLOR_BLACK,   curses.COLOR_CYAN)  # selected
    curses.init_pair(6, curses.COLOR_WHITE,   -1)  # normal
    curses.init_pair(7, curses.COLOR_MAGENTA, -1)  # accent

C_HEADER = lambda: curses.color_pair(1) | curses.A_BOLD
C_OK     = lambda: curses.color_pair(2)
C_ERR    = lambda: curses.color_pair(3)
C_WARN   = lambda: curses.color_pair(4)
C_SEL    = lambda: curses.color_pair(5) | curses.A_BOLD
C_NORMAL = lambda: curses.color_pair(6)
C_ACCENT = lambda: curses.color_pair(7) | curses.A_BOLD

# ── Safe render helpers ───────────────────────────────────────────────────────

def safe_addstr(win, y: int, x: int, text: str, attr: int = 0):
    try:
        h, w = win.getmaxyx()
        if y < 0 or y >= h or x < 0:
            return
        text = str(text)[:max(0, w - x - 1)]
        if text:
            win.addstr(y, x, text, attr)
    except curses.error:
        pass


def exit_tui_for_rich(stdscr):
    """Keluar dari curses mode -> tampilkan Rich output."""
    curses.endwin()


def restore_tui(stdscr):
    """Restore curses setelah Rich selesai."""
    # Wajib: refresh terminal state setelah endwin
    stdscr.keypad(True)        # arrow key harus di-enable ulang
    curses.curs_set(0)         # sembunyikan cursor
    stdscr.touchwin()          # mark semua char perlu di-redraw
    stdscr.clearok(True)       # force full redraw
    stdscr.refresh()
    curses.doupdate()

# ══════════════════════════════════════════════════════════════════════════════
#  HEADER & FOOTER
# ══════════════════════════════════════════════════════════════════════════════

def draw_header(stdscr, subtitle: str = ""):
    curses.update_lines_cols()
    h, w  = stdscr.getmaxyx()
    host  = config.get_hostname()
    ver   = config.VERSION
    ts    = datetime.now().strftime("%H:%M:%S")
    title = f"  [{config.APP_NAME} v{ver}] {host}"

    try:
        stdscr.attron(C_HEADER())
        stdscr.addstr(0, 0, "=" * (w - 1))
        stdscr.addstr(1, 0, title.ljust(w - len(ts) - 2) + ts + "  ")
        stdscr.addstr(2, 0, "=" * (w - 1))
        stdscr.attroff(C_HEADER())
        if subtitle:
            safe_addstr(stdscr, 3, 2, subtitle[:w - 4], C_WARN())
    except curses.error:
        pass


def draw_footer(stdscr, hints: str = ""):
    curses.update_lines_cols()
    h, w = stdscr.getmaxyx()

    try:
        stdscr.attron(C_HEADER())
        stdscr.addstr(h - 1, 0, "-" * (w - 1))
        stdscr.attroff(C_HEADER())
    except curses.error:
        pass

    levels = [
        (165, "↑↓=nav  Enter=menu  r=refresh  a=aksi  i=img  "
              "s=stats  d=disk  c=compose  x=extras  w=screen  t=settings  q=keluar"),
        (100, "↑↓=nav  Enter=menu  r=ref  a=aksi  s=stat  "
              "c=comp  x=ext  w=scr  t=cfg  q=quit"),
        (60,  "↑↓=nav  Enter  r=ref  c=comp  x=ext  q=quit"),
        (0,   "↑↓  Enter  q"),
    ]
    text = levels[-1][1]
    for min_w, hint in levels:
        if w >= min_w:
            text = hint
            break

    safe_addstr(stdscr, h - 2, 2, text[:w - 3], C_ACCENT())

# ══════════════════════════════════════════════════════════════════════════════
#  WIDGETS
# ══════════════════════════════════════════════════════════════════════════════

def popup(stdscr, title: str, lines: List[str], wait_key: bool = True):
    """Dialog popup dengan scrolling."""
    curses.update_lines_cols()
    h, w     = stdscr.getmaxyx()
    max_line = max((len(l) for l in lines), default=40)
    box_w    = min(w - 4, max(60, max_line + 6))
    box_h    = min(h - 4, len(lines) + 6)
    inner_h  = box_h - 4
    y0       = max(0, (h - box_h) // 2)
    x0       = max(0, (w - box_w) // 2)
    scroll   = 0

    while True:
        win = curses.newwin(box_h, box_w, y0, x0)
        win.keypad(True)
        win.bkgd(" ", C_NORMAL())
        win.box()
        safe_addstr(win, 0, max(0, (box_w - len(title) - 2) // 2),
                    f" {title} ", C_HEADER())

        for i, line in enumerate(lines[scroll:scroll + inner_h]):
            safe_addstr(win, i + 2, 2, line[:box_w - 4], C_NORMAL())

        total = len(lines)
        if total > inner_h:
            pct = int((scroll / max(1, total - inner_h)) * 100)
            safe_addstr(win, box_h - 2, box_w - 8, f"{pct:3d}% ", C_WARN())

        if wait_key:
            safe_addstr(win, box_h - 1,
                        max(0, (box_w - 30) // 2),
                        " [Enter/q] tutup  [↑↓] scroll ", C_ACCENT())

        win.noutrefresh()
        curses.doupdate()

        if not wait_key:
            break

        k = win.getch()
        if k in (ord('q'), ord('Q'), 10, 27):
            break
        elif k in (curses.KEY_DOWN, ord('j')):
            if scroll < max(0, len(lines) - inner_h):
                scroll += 1
        elif k in (curses.KEY_UP, ord('k')):
            if scroll > 0:
                scroll -= 1


def confirm(stdscr, message: str) -> bool:
    """Dialog konfirmasi y/n."""
    curses.update_lines_cols()
    h, w      = stdscr.getmaxyx()
    msg_lines = message.splitlines()
    lines     = msg_lines + ["", "  [y] Ya      [n] Tidak"]
    box_w     = min(w - 4, max((len(l) for l in lines), default=40) + 8)
    box_h     = len(lines) + 4
    y0        = max(0, (h - box_h) // 2)
    x0        = max(0, (w - box_w) // 2)

    win = curses.newwin(box_h, box_w, y0, x0)
    win.keypad(True)
    win.bkgd(" ", C_NORMAL())
    win.box()
    safe_addstr(win, 0, 2, " Konfirmasi ", C_WARN())
    for i, l in enumerate(lines):
        safe_addstr(win, i + 2, 2, l[:box_w - 4], C_NORMAL())
    win.noutrefresh()
    curses.doupdate()

    while True:
        k = win.getch()
        if k in (ord('y'), ord('Y')):
            return True
        if k in (ord('n'), ord('N'), ord('q'), 27, 10):
            return False


def list_select(stdscr, title: str, items: List,
                label_fn: Callable = None) -> int:
    """
    List selector dengan navigasi + shortcut huruf [X].
    Return index dipilih atau -1 jika cancel.
    """
    if not items:
        popup(stdscr, title, ["Tidak ada item."])
        return -1

    label_fn = label_fn or str

    # Parse shortcut dari label [X]
    shortcuts = {}
    for i, item in enumerate(items):
        m = re.match(r'^\[([A-Za-z0-9])\]', label_fn(item).strip())
        if m:
            ch = m.group(1)
            shortcuts[ord(ch.lower())] = i
            shortcuts[ord(ch.upper())] = i

    curses.update_lines_cols()
    h, w    = stdscr.getmaxyx()
    box_h   = min(h - 4, len(items) + 6)
    box_w   = min(w - 4, 72)
    y0      = max(0, (h - box_h) // 2)
    x0      = max(0, (w - box_w) // 2)
    inner_h = box_h - 4
    sel     = 0
    scroll  = 0

    while True:
        win = curses.newwin(box_h, box_w, y0, x0)
        win.keypad(True)
        win.bkgd(" ", C_NORMAL())
        win.box()
        safe_addstr(win, 0, 2, f" {title} ", C_HEADER())
        safe_addstr(win, box_h - 1, 2,
                    " Enter=pilih  q=batal  ↑↓=scroll ", C_ACCENT())

        for i, item in enumerate(items[scroll:scroll + inner_h]):
            idx   = scroll + i
            label = label_fn(item)[:box_w - 4]
            attr  = C_SEL() if idx == sel else C_NORMAL()
            safe_addstr(win, i + 2, 2, label.ljust(box_w - 4), attr)

        win.noutrefresh()
        curses.doupdate()
        k = win.getch()

        if k in (ord('q'), ord('Q'), 27):
            return -1
        elif k in (curses.KEY_UP, ord('k')):
            if sel > 0:
                sel -= 1
                if sel < scroll:
                    scroll = sel
        elif k in (curses.KEY_DOWN, ord('j')):
            if sel < len(items) - 1:
                sel += 1
                if sel >= scroll + inner_h:
                    scroll += 1
        elif k in (10, curses.KEY_ENTER):
            return sel
        elif k in shortcuts:
            return shortcuts[k]

# ══════════════════════════════════════════════════════════════════════════════
#  MAIN CONTAINER SCREEN
# ══════════════════════════════════════════════════════════════════════════════

def draw_containers_frame(stdscr, containers: List[Dict],
                           sel: int, scroll: int,
                           msg: str, msg_time: float):
    """Render satu frame container list. Tidak ada I/O docker di sini."""
    curses.update_lines_cols()
    h, w = stdscr.getmaxyx()

    CONTENT_START = 6
    FOOTER_ROWS   = 3
    inner_h       = h - CONTENT_START - FOOTER_ROWS

    stdscr.erase()
    draw_header(stdscr, "  Daftar Container")

    try:
        col = f"  {'NAMA':<25} {'STATUS':<32} {'IMAGE':<30}"
        safe_addstr(stdscr, 4, 0, col[:w], C_WARN())
        stdscr.addstr(5, 0, "-" * (w - 1), C_HEADER())
    except curses.error:
        pass

    if not containers:
        safe_addstr(stdscr, CONTENT_START, 2,
                    "Tidak ada container. Docker daemon aktif?", C_ERR())
    else:
        for i, c in enumerate(containers[scroll:scroll + inner_h]):
            idx  = scroll + i
            row  = CONTENT_START + i
            icon = ">" if c["running"] else "."
            s_attr = C_OK() if c["running"] else C_ERR()
            name   = c["name"][:24].ljust(25)
            status = c["status"][:31].ljust(32)
            image  = c["image"][:28]
            try:
                if idx == sel:
                    line = f"  {icon} {name} {status} {image}"
                    stdscr.addstr(row, 0, line[:w - 1].ljust(w - 1), C_SEL())
                else:
                    safe_addstr(stdscr, row, 0, "  ", C_NORMAL())
                    safe_addstr(stdscr, row, 2, icon + " ", s_attr)
                    safe_addstr(stdscr, row, 4,
                                (name + " " + status + " " + image)[:w - 6],
                                C_NORMAL())
            except curses.error:
                pass

    if msg and (time.time() - msg_time < 3):
        safe_addstr(stdscr, h - 3, 2, msg[:w - 4], C_OK())

    draw_footer(stdscr)
    stdscr.noutrefresh()
    curses.doupdate()


# ══════════════════════════════════════════════════════════════════════════════
#  HOME SCREEN - Neofetch-style dashboard
# ══════════════════════════════════════════════════════════════════════════════

def _home_sysinfo() -> dict:
    """Kumpulkan info sistem untuk home screen."""
    def q(cmd, fallback="?"):
        out, _, code = run_cmd(cmd, timeout=5)
        return out.strip() if code == 0 and out.strip() else fallback
    return {
        "hostname":  q("hostname"),
        "os":        q("lsb_release -ds 2>/dev/null", "Linux"),
        "kernel":    q("uname -r"),
        "arch":      q("uname -m"),
        "uptime":    q("uptime -p"),
        "cpu":       q("lscpu | grep 'Model name' | sed 's/.*: *//' | xargs"),
        "cores":     q("nproc"),
        "ram_used":  q("free -h | awk '/^Mem:/{print $3}'"),
        "ram_total": q("free -h | awk '/^Mem:/{print $2}'"),
        "ram_pct":   q("free | awk '/^Mem:/{printf \"%.0f\", $3/$2*100}'", "0"),
        "load":      q("cat /proc/loadavg | awk '{print $1, $2, $3}'"),
        "gpu":       q("lspci 2>/dev/null | grep -iE 'vga|3d' | sed 's/.*: //' | head -1", ""),
        "nets":      q("ip -br addr show | grep -v '^lo' | awk '{print $1, $3}'"),
    }


def _home_diskinfo() -> list:
    out, _, code = run_cmd(
        "df -h --output=target,size,used,avail,pcent 2>/dev/null"
        " | grep -E '^(/|/mnt|/data|/boot|/home)' | head -6"
    )
    result = []
    if code == 0:
        for line in out.splitlines():
            p = line.split()
            if len(p) >= 5:
                try: pct = int(p[4].replace("%", ""))
                except ValueError: pct = 0
                result.append({"mount": p[0], "size": p[1],
                                "used": p[2], "avail": p[3], "pct": pct})
    return result


def _home_blkinfo() -> list:
    out, _, code = run_cmd(
        "lsblk -o NAME,SIZE,TYPE,FSTYPE,MOUNTPOINT --noheadings 2>/dev/null"
        " | grep -v loop | head -14"
    )
    result = []
    if code == 0:
        for line in out.splitlines():
            p = line.split(None, 4)
            if len(p) >= 3:
                result.append({
                    "name":   p[0] if len(p) > 0 else "",
                    "size":   p[1] if len(p) > 1 else "",
                    "type":   p[2] if len(p) > 2 else "",
                    "fstype": p[3] if len(p) > 3 else "",
                    "mount":  p[4].strip() if len(p) > 4 else "",
                })
    return result


def _pbar_curses(pct: int, width: int = 16) -> tuple:
    """Return (filled, empty, color_pair) untuk progress bar di curses."""
    pct    = max(0, min(100, pct))
    filled = int(width * pct / 100)
    empty  = width - filled
    if pct >= 90: cp = C_ERR()
    elif pct >= 70: cp = C_WARN()
    else: cp = C_OK()
    return filled, empty, cp


def safe_add(win, y, x, text, attr=0):
    try:
        h, w = win.getmaxyx()
        if y < 0 or y >= h - 1 or x < 0: return
        text = str(text)[:max(0, w - x - 1)]
        if text: win.addstr(y, x, text, attr)
    except curses.error: pass


def screen_home(stdscr):
    """Home dashboard - neofetch style."""
    import time, curses
    curses.curs_set(0)

    # Loading screen
    stdscr.erase()
    curses.update_lines_cols()
    h, w = stdscr.getmaxyx()
    draw_header(stdscr, "  Dashboard")
    safe_add(stdscr, 5, 4, "Loading system info...", C_WARN())
    stdscr.noutrefresh(); curses.doupdate()

    # Kumpulkan data
    sys_info = _home_sysinfo()
    disks    = _home_diskinfo()
    blks     = _home_blkinfo()
    containers = get_containers()
    images     = get_images()
    run  = sum(1 for c in containers if c["running"])
    stop = len(containers) - run

    stdscr.timeout(500)

    while True:
        stdscr.erase()
        curses.update_lines_cols()
        h, w = stdscr.getmaxyx()
        draw_header(stdscr, "  Home Dashboard")

        row = 4  # baris mulai konten

        # ── Logo + Sysinfo ──────────────────────────────────────────────────
        s     = sys_info
        host  = s.get("hostname", "?")
        os_   = s.get("os", "?")[:36]
        kern  = s.get("kernel", "?")[:30]
        arch  = s.get("arch", "?")
        up    = s.get("uptime", "?")[:36]
        cpu   = s.get("cpu", "?")[:36]
        cores = s.get("cores", "?")
        rused = s.get("ram_used", "?")
        rtot  = s.get("ram_total", "?")
        rpct  = int(s.get("ram_pct", "0") or "0")
        load  = s.get("load", "?")
        gpu   = s.get("gpu", "")[:34]
        nets  = s.get("nets", "")

        # Logo dihapus - langsung tampilkan sysinfo
        left_w = 0  # tidak ada kolom kiri

        # Sysinfo full width
        info_lines = [
            (f"  {host}", C_HEADER() | curses.A_BOLD),
            (f"  {'─' * min(50, w - 6)}", C_HEADER()),
            (f"  OS      {os_}", C_NORMAL()),
            (f"  Kernel  {kern} {arch}", C_NORMAL()),
            (f"  CPU     {cpu}", C_NORMAL()),
            (f"  Cores   {cores} cores", C_NORMAL()),
            (f"  RAM     {rused} / {rtot}", C_NORMAL()),
            (f"  Uptime  {up}", C_NORMAL()),
            (f"  Load    {load}", C_NORMAL()),
        ]
        if gpu:
            info_lines.append((f"  GPU     {gpu}", C_NORMAL()))
        if nets:
            info_lines.append(("  Network", C_WARN() | curses.A_BOLD))
            for nl in nets.splitlines()[:3]:
                pp = nl.split()
                if len(pp) >= 2:
                    info_lines.append((f"    |- {pp[0]:<12} {pp[1]}", C_WARN()))

        ri = 0
        for text, attr in info_lines:
            if row + ri < h - 4:
                safe_add(stdscr, row + ri, 2, text[:w - 4], attr)
                ri += 1

        row += ri + 1

        # ── Separator ───────────────────────────────────────────────────────
        if row < h - 4:
            safe_add(stdscr, row, 2, "-" * (w - 4), C_HEADER())
            row += 1

        # ── Storage ─────────────────────────────────────────────────────────
        if row < h - 4:
            safe_add(stdscr, row, 2, "Storage", C_WARN() | curses.A_BOLD)
            row += 1

        for d in disks[:4]:
            if row >= h - 4: break
            filled, empty, cp = _pbar_curses(d["pct"], 14)
            pct_str = f"{d['pct']:3d}%"
            mount   = f"{d['mount']:<14}"
            safe_add(stdscr, row, 2, mount, C_NORMAL() | curses.A_BOLD)
            safe_add(stdscr, row, 17, "[", C_NORMAL())
            try:
                stdscr.addstr(row, 18, "#" * filled, cp)
                stdscr.addstr(row, 18+filled, "." * empty, C_NORMAL())
            except curses.error: pass
            safe_add(stdscr, row, 18+14, "] ", C_NORMAL())
            safe_add(stdscr, row, 18+14+2, pct_str, cp)
            safe_add(stdscr, row, 18+14+7,
                     f"  {d['used']}/{d['size']}  free:{d['avail']}", C_NORMAL())
            row += 1

        # ── Block Devices ────────────────────────────────────────────────────
        if row < h - 4:
            row += 0
            safe_add(stdscr, row, 2, "-" * (w - 4), C_HEADER())
            row += 1

        if row < h - 4:
            safe_add(stdscr, row, 2, "Block Devices", C_WARN() | curses.A_BOLD)
            row += 1

        hdr = f"  {'NAME':<16} {'SIZE':>6}  {'TYPE':<8} {'FS':<10} MOUNT"
        safe_add(stdscr, row, 2, hdr[:w-4], C_WARN())
        row += 1

        for b in blks[:6]:
            if row >= h - 4: break
            if b["type"] == "disk":
                attr = C_HEADER() | curses.A_BOLD
                pfx  = "  "
            elif b["type"] in ("part", "md"):
                attr = C_NORMAL()
                pfx  = "  |- "
            else:
                attr = C_ACCENT()
                pfx  = "  L  "
            line = f"{pfx}{b['name']:<14} {b['size']:>6}  {b['type']:<8} {b['fstype']:<10} {b['mount']}"
            safe_add(stdscr, row, 2, line[:w-4], attr)
            row += 1

        # ── Docker Summary ────────────────────────────────────────────────────
        if row < h - 4:
            safe_add(stdscr, row, 2, "-" * (w - 4), C_HEADER())
            row += 1
        if row < h - 4:
            safe_add(stdscr, row, 2, "Docker", C_WARN() | curses.A_BOLD)
            safe_add(stdscr, row, 12,
                     f"> {run} running", C_OK())
            safe_add(stdscr, row, 28,
                     f". {stop} stopped", C_ERR())
            safe_add(stdscr, row, 44,
                     f"* {len(images)} images", C_HEADER())
            row += 1

        # ── Footer hint ───────────────────────────────────────────────────────
        draw_footer(stdscr)
        hint = "h=home  c=containers  a=aksi  s=stats  x=extras  w=screen  t=settings  q=quit"
        try:
            safe_add(stdscr, h-2, 2, hint[:w-3], C_ACCENT())
        except curses.error: pass

        stdscr.noutrefresh()
        curses.doupdate()

        k = stdscr.getch()
        if k in (ord('q'), ord('Q'), ord('h'), ord('H'), 27):
            break
        elif k in (ord('c'), ord('C')):
            screen_containers(stdscr)
        elif k in (ord('a'), ord('A')):
            menu_all_actions(stdscr)
        elif k in (ord('s'), ord('S')):
            screen_stats(stdscr)
        elif k in (ord('x'), ord('X')):
            menu_extras(stdscr)
        elif k in (ord('w'), ord('W')):
            menu_gnu_screen(stdscr)
        elif k in (ord('t'), ord('T')):
            menu_settings(stdscr)
        elif k in (ord('?'),):
            screen_help(stdscr)
        elif k == curses.KEY_RESIZE:
            curses.update_lines_cols()
            h, w = stdscr.getmaxyx()
            curses.resizeterm(h, w)


def screen_containers(stdscr):
    """Main TUI loop - container list."""
    curses.curs_set(0)
    sel      = 0
    scroll   = 0
    msg      = ""
    msg_time = 0.0

    containers     = []
    last_fetch     = 0.0
    FETCH_INTERVAL = int(config.get("general", "fetch_interval", "10"))

    stdscr.timeout(500)

    def fetch():
        nonlocal containers, last_fetch, sel
        containers = docker.get_containers()
        last_fetch = time.time()
        if containers and sel >= len(containers):
            sel = len(containers) - 1

    fetch()

    while True:
        h, w    = stdscr.getmaxyx()
        inner_h = h - 6 - 3

        if time.time() - last_fetch >= FETCH_INTERVAL:
            fetch()

        draw_containers_frame(stdscr, containers, sel, scroll, msg, msg_time)
        k = stdscr.getch()

        if k == -1:  # timeout - hanya redraw
            continue
        elif k in (ord('q'), ord('Q')):
            break
        elif k in (curses.KEY_UP, ord('k')):
            if sel > 0:
                sel -= 1
                if sel < scroll:
                    scroll = sel
        elif k in (curses.KEY_DOWN, ord('j')):
            if containers and sel < len(containers) - 1:
                sel += 1
                if sel >= scroll + inner_h:
                    scroll += 1
        elif k in (ord('r'), ord('R')):
            fetch()
            msg      = "* Data diperbarui"
            msg_time = time.time()
        elif k in (10, curses.KEY_ENTER):
            if containers:
                menu_container(stdscr, containers[sel])
                fetch()
        elif k in (ord('a'), ord('A')):
            menu_all_actions(stdscr)
            fetch()
        elif k in (ord('i'), ord('I')):
            menu_images(stdscr)
        elif k in (ord('s'), ord('S')):
            screen_stats(stdscr)
        elif k in (ord('d'), ord('D')):
            screen_disk(stdscr)
        elif k in (ord('c'), ord('C')):
            menu_compose(stdscr)
        elif k in (ord('x'), ord('X')):
            menu_extras(stdscr)
            fetch()
        elif k in (ord('w'), ord('W')):
            menu_gnu_screen(stdscr)
        elif k in (ord('t'), ord('T')):
            menu_settings(stdscr)
        elif k in (ord('?'),):
            screen_help(stdscr)
        elif k == curses.KEY_RESIZE:
            curses.update_lines_cols()
            h, w = stdscr.getmaxyx()
            curses.resizeterm(h, w)
            stdscr.erase()
            stdscr.refresh()

# ══════════════════════════════════════════════════════════════════════════════
#  CONTAINER MENU
# ══════════════════════════════════════════════════════════════════════════════

def menu_container(stdscr, c: Dict):
    """Menu aksi per container. Exit curses -> Rich untuk output."""
    name    = c["name"]
    running = c["running"]

    menu = [
        ("[L] Lihat Logs (50 baris)",   "logs"),
        ("[F] Live Logs (tail -f)",      "live_logs"),
        ("[R] Restart Container",        "restart"),
        ("[U] Pull Update Image",        "pull"),
        ("[I] Inspect Detail",           "inspect"),
        ("[X] Exec Shell (bash/sh)",     "exec"),
        ("[.] Stop Container",  "stop") if running else
        ("[>] Start Container", "start"),
        ("[D] Remove Container",         "remove"),
    ]

    choice = list_select(stdscr, f"Container: {name}", menu,
                         label_fn=lambda x: x[0])
    if choice == -1:
        return

    action = menu[choice][1]

    # ── EXIT CURSES -> RICH ────────────────────────────────────────────────────
    if action == "logs":
        exit_tui_for_rich(stdscr)
        log_content = docker.get_container_logs(name, tail=50)
        rich_ui.show_logs(name, log_content)
        rich_ui.wait_key()
        restore_tui(stdscr)

    elif action == "live_logs":
        exit_tui_for_rich(stdscr)
        rich_ui.stream_logs(name, tail=50)
        rich_ui.wait_key()
        restore_tui(stdscr)

    elif action == "inspect":
        exit_tui_for_rich(stdscr)
        json_str = docker.get_container_inspect(name)
        rich_ui.show_inspect(name, json_str)
        rich_ui.wait_key()
        restore_tui(stdscr)

    elif action == "exec":
        exit_tui_for_rich(stdscr)
        print(f"\n  Shell container '{name}' -- ketik 'exit' untuk keluar\n")
        run_interactive(
            f"docker exec -it {name} bash 2>/dev/null || docker exec -it {name} sh"
        )
        rich_ui.wait_key()
        restore_tui(stdscr)

    # ── TETAP DI CURSES (confirm dulu) ────────────────────────────────────────
    elif action == "restart":
        if confirm(stdscr, f"Restart container '{name}'?"):
            exit_tui_for_rich(stdscr)
            ok, msg = docker.container_action(name, "restart")
            (rich_ui.cli_success if ok else rich_ui.cli_error)(msg)
            rich_ui.wait_key()
            restore_tui(stdscr)

    elif action == "pull":
        image = docker.get_container_image(name)
        if confirm(stdscr, f"Pull image terbaru?\nImage: {image}"):
            exit_tui_for_rich(stdscr)
            print(f"\n  Pulling {image}...\n")
            run_interactive(f"docker pull {image}")
            rich_ui.wait_key()
            restore_tui(stdscr)

    elif action == "stop":
        if confirm(stdscr, f"Stop container '{name}'?"):
            exit_tui_for_rich(stdscr)
            ok, msg = docker.container_action(name, "stop")
            (rich_ui.cli_success if ok else rich_ui.cli_error)(msg)
            rich_ui.wait_key()
            restore_tui(stdscr)

    elif action == "start":
        exit_tui_for_rich(stdscr)
        ok, msg = docker.container_action(name, "start")
        (rich_ui.cli_success if ok else rich_ui.cli_error)(msg)
        rich_ui.wait_key()
        restore_tui(stdscr)

    elif action == "remove":
        if confirm(stdscr, f"HAPUS container '{name}'?\n(harus sudah stop)"):
            exit_tui_for_rich(stdscr)
            ok, msg = docker.container_action(name, "rm")
            (rich_ui.cli_success if ok else rich_ui.cli_error)(msg)
            rich_ui.wait_key()
            restore_tui(stdscr)

# ══════════════════════════════════════════════════════════════════════════════
#  ALL ACTIONS MENU
# ══════════════════════════════════════════════════════════════════════════════

def menu_all_actions(stdscr):
    menu = [
        ("[U] Update SEMUA image",                 "update_all"),
        ("[R] Restart SEMUA container",            "restart_all"),
        ("[>] Docker Compose UP",                  "up"),
        ("[.] Docker Compose DOWN",                "down"),
        ("[P] Docker Compose PULL",                "pull_all"),
        ("[V] Prune volumes tidak terpakai",       "prune_vol"),
        ("[X] Prune image tidak terpakai",         "prune_img"),
        ("[!] Prune TOTAL",                        "prune_all"),
    ]
    choice = list_select(stdscr, "Aksi Semua Container", menu,
                         label_fn=lambda x: x[0])
    if choice == -1:
        return
    action = menu[choice][1]

    compose_dir = config.get_compose_dir()
    compose_cmd = config.get_compose_cmd()

    if action == "update_all":
        if confirm(stdscr, "Pull ulang semua image?\n(bisa lama)"):
            exit_tui_for_rich(stdscr)
            run_interactive(
                "docker ps --format '{{.Image}}' | sort -u | xargs -I{} docker pull {}"
            )
            rich_ui.wait_key()
            restore_tui(stdscr)

    elif action == "restart_all":
        if confirm(stdscr, "Restart SEMUA container yang running?"):
            exit_tui_for_rich(stdscr)
            run_interactive("docker ps -q | xargs -r docker restart")
            rich_ui.wait_key()
            restore_tui(stdscr)

    elif action in ("up", "down", "pull_all"):
        if not compose_dir:
            popup(stdscr, "Error", ["Compose dir belum dikonfigurasi.",
                                    "Pergi ke Settings (t)."])
            return
        act_map = {
            "up":       ("UP",   "up -d"),
            "down":     ("DOWN", "down"),
            "pull_all": ("PULL", "pull"),
        }
        label, cmd_flag = act_map[action]
        msg = f"Docker Compose {label}?\nDir: {compose_dir}"
        if action == "down":
            msg += "\n\nSemua container akan stop!"
        if confirm(stdscr, msg):
            exit_tui_for_rich(stdscr)
            run_interactive(f"cd '{compose_dir}' && {compose_cmd} {cmd_flag}")
            rich_ui.wait_key()
            restore_tui(stdscr)

    elif action == "prune_vol":
        vols = docker.get_orphan_volumes()
        if not vols:
            popup(stdscr, "Prune Volumes", [
                "Tidak ada orphan volume.", "Semua volume sedang dipakai."])
        else:
            if confirm(stdscr, f"Hapus {len(vols)} orphan volume?\nTidak bisa di-undo!"):
                exit_tui_for_rich(stdscr)
                run_interactive("docker volume prune -f")
                rich_ui.wait_key()
                restore_tui(stdscr)

    elif action == "prune_img":
        imgs = docker.get_dangling_images()
        if not imgs:
            popup(stdscr, "Prune Images", [
                "Tidak ada dangling image.",
                "Image jadi dangling setelah pull versi baru."])
        else:
            if confirm(stdscr, f"Hapus {len(imgs)} dangling image?\nTidak bisa di-undo!"):
                exit_tui_for_rich(stdscr)
                run_interactive("docker image prune -f")
                rich_ui.wait_key()
                restore_tui(stdscr)

    elif action == "prune_all":
        disk = docker.get_disk_usage()
        lines = disk.splitlines()[-5:] + [
            "", "!! SEMUA tidak terpakai akan dihapus!", "Tidak bisa di-undo!"
        ]
        if confirm(stdscr, "\n".join(lines)):
            exit_tui_for_rich(stdscr)
            run_interactive("docker system prune -af --volumes")
            rich_ui.wait_key()
            restore_tui(stdscr)

# ══════════════════════════════════════════════════════════════════════════════
#  IMAGES MENU
# ══════════════════════════════════════════════════════════════════════════════

def menu_images(stdscr):
    images = docker.get_images()
    if not images:
        popup(stdscr, "Images", ["Tidak ada image."])
        return

    exit_tui_for_rich(stdscr)
    rich_ui.show_images(images)
    restore_tui(stdscr)

    idx = list_select(stdscr, "Docker Images", images,
        label_fn=lambda x: f"{'* '+x['name']:<45} {x['size']:<12} {x['created']}")
    if idx == -1:
        return
    img = images[idx]
    actions = [
        ("[U] Pull (update) image ini", "pull"),
        ("[D] Hapus image ini",         "remove"),
    ]
    choice = list_select(stdscr, f"Image: {img['name']}", actions,
                         label_fn=lambda x: x[0])
    if choice == -1:
        return

    if actions[choice][1] == "pull":
        exit_tui_for_rich(stdscr)
        run_interactive(f"docker pull {img['name']}")
        rich_ui.wait_key()
        restore_tui(stdscr)
    elif actions[choice][1] == "remove":
        if confirm(stdscr, f"Hapus image:\n{img['name']}?"):
            exit_tui_for_rich(stdscr)
            ok, msg = docker.remove_image(img["name"])
            (rich_ui.cli_success if ok else rich_ui.cli_error)(msg)
            rich_ui.wait_key()
            restore_tui(stdscr)

# ══════════════════════════════════════════════════════════════════════════════
#  STATS & DISK
# ══════════════════════════════════════════════════════════════════════════════

def screen_stats(stdscr):
    """Tampilkan stats dengan Rich, lalu kembali ke curses."""
    exit_tui_for_rich(stdscr)
    stats = docker.get_stats_once()
    rich_ui.show_stats(stats)
    print("  (tampilan di atas adalah snapshot)\n")
    print("  Untuk live stats, tekan Enter. Ctrl+C untuk stop.")
    try:
        input()
        run_interactive("docker stats")
    except (KeyboardInterrupt, EOFError):
        pass
    rich_ui.wait_key()
    restore_tui(stdscr)


def screen_disk(stdscr):
    exit_tui_for_rich(stdscr)
    disk = docker.get_disk_usage()
    rich_ui.show_disk_usage(disk)
    rich_ui.wait_key()
    restore_tui(stdscr)

# ══════════════════════════════════════════════════════════════════════════════
#  COMPOSE MENU
# ══════════════════════════════════════════════════════════════════════════════

def menu_compose(stdscr):
    compose_file = config.get_compose_file()
    compose_dir  = config.get_compose_dir()
    compose_cmd  = config.get_compose_cmd()
    editor       = config.get_editor()

    menu = [
        ("[V] Lihat docker-compose.yml",  "view"),
        ("[E] Edit docker-compose.yml",   "edit"),
        ("[B] Backup docker-compose.yml", "backup"),
        ("[C] Validate config",           "validate"),
    ]
    choice = list_select(stdscr, "Docker Compose", menu,
                         label_fn=lambda x: x[0])
    if choice == -1:
        return

    if not compose_file and menu[choice][1] != "validate":
        popup(stdscr, "Error", [
            "Compose file belum dikonfigurasi.",
            "Pergi ke Settings (t)."
        ])
        return

    action = menu[choice][1]

    if action == "view":
        exit_tui_for_rich(stdscr)
        rich_ui.show_compose_file(compose_file)
        rich_ui.wait_key()
        restore_tui(stdscr)

    elif action == "edit":
        if confirm(stdscr, f"Edit:\n{compose_file}\n\nEditor: {editor}"):
            exit_tui_for_rich(stdscr)
            run_interactive(f"{editor} '{compose_file}'")
            rich_ui.wait_key()
            restore_tui(stdscr)

    elif action == "backup":
        from datetime import datetime
        from pathlib import Path
        ts  = datetime.now().strftime("%Y%m%d_%H%M%S")
        dst = f"{compose_file}.bak_{ts}"
        _, err, code = run_cmd(f"cp '{compose_file}' '{dst}'")
        if code == 0:
            popup(stdscr, "Backup Sukses", ["Disimpan ke:", dst])
        else:
            popup(stdscr, "Backup Gagal", [err or "Unknown error"])

    elif action == "validate":
        ok, msg = docker.compose_validate()
        lines = [msg] if msg else ["Tidak ada output."]
        popup(stdscr, "Validate Config",
              ["OK: Config valid!" if ok else "ERROR: Ada masalah!"] + [""] + lines)

# ══════════════════════════════════════════════════════════════════════════════
#  GNU SCREEN MENU
# ══════════════════════════════════════════════════════════════════════════════

def menu_gnu_screen(stdscr):
    if not check_tool("screen"):
        popup(stdscr, "GNU Screen", [
            "GNU Screen tidak terinstall.",
            "",
            "Install:",
            "  sudo apt install screen",
            "  sudo yum install screen",
            "  sudo pacman -S screen",
        ])
        return

    while True:
        sessions = docker.get_screens()

        menu = [("[L] Lihat daftar session", "list")]
        if sessions:
            menu += [
                ("[A] Attach ke session",    "attach"),
                ("[K] Kill 1 session",       "kill_one"),
                ("[!] Kill SEMUA session",   "kill_all"),
            ]
        menu += [
            ("[N] Buat session baru",                "new"),
            ("[D] Jalankan perintah di background",  "new_cmd"),
        ]

        choice = list_select(stdscr, f"GNU Screen ({len(sessions)} aktif)",
                             menu, label_fn=lambda x: x[0])
        if choice == -1:
            return
        action = menu[choice][1]

        if action == "list":
            exit_tui_for_rich(stdscr)
            rich_ui.show_screen_sessions(sessions)
            rich_ui.wait_key()
            restore_tui(stdscr)

        elif action == "attach":
            idx = list_select(stdscr, "Attach ke Session", sessions,
                label_fn=lambda s: f"{s['pid']:<8} {s['name']:<22} {s['status']}")
            if idx == -1:
                continue
            sid = sessions[idx]["sid"]
            exit_tui_for_rich(stdscr)
            print(f"\n  screen -r {sid}")
            print("  Ctrl+A lalu D = detach (keluar tanpa mematikan)\n")
            run_interactive(f"screen -r {sid}")
            rich_ui.wait_key()
            restore_tui(stdscr)

        elif action == "kill_one":
            idx = list_select(stdscr, "Kill Session", sessions,
                label_fn=lambda s: f"{s['pid']:<8} {s['name']:<22} {s['status']}")
            if idx == -1:
                continue
            s = sessions[idx]
            if confirm(stdscr, f"Matikan session?\n  {s['name']} (PID {s['pid']})"):
                ok, msg = docker.screen_kill(s["sid"])
                popup(stdscr, "Sukses" if ok else "Gagal", [msg])

        elif action == "kill_all":
            names = [s["name"] for s in sessions]
            msg   = f"Matikan SEMUA {len(sessions)} session?\n"
            msg  += "\n".join(f"  - {n}" for n in names[:8])
            if len(names) > 8:
                msg += f"\n  ... dan {len(names)-8} lainnya"
            if confirm(stdscr, msg):
                failed = [s["name"] for s in sessions
                          if not docker.screen_kill(s["sid"])[0]]
                if failed:
                    popup(stdscr, "Selesai (ada gagal)",
                          [f"Gagal: {', '.join(failed)}"])
                else:
                    popup(stdscr, "Selesai",
                          [f"Semua {len(sessions)} session dimatikan."])

        elif action == "new":
            exit_tui_for_rich(stdscr)
            nama = sanitize_input(input("  Nama session: ").strip())
            if nama:
                print(f"\n  Ctrl+A lalu D untuk detach\n")
                run_interactive(f"screen -S {nama}")
            else:
                print("  Nama kosong, dibatalkan.")
            rich_ui.wait_key()
            restore_tui(stdscr)

        elif action == "new_cmd":
            exit_tui_for_rich(stdscr)
            nama = sanitize_input(input("  Nama session: ").strip()) or "dockman-task"
            cmd  = input("  Perintah: ").strip()
            if cmd:
                ret = run_interactive(f"screen -dmS {nama} bash -c '{cmd}; exec bash'")
                if ret == 0:
                    rich_ui.cli_success(f"Session '{nama}' berjalan. Masuk: screen -r {nama}")
                else:
                    rich_ui.cli_error(f"Gagal (exit {ret})")
            else:
                rich_ui.cli_error("Perintah kosong.")
            rich_ui.wait_key()
            restore_tui(stdscr)

# ══════════════════════════════════════════════════════════════════════════════
#  EXTRAS MENU
# ══════════════════════════════════════════════════════════════════════════════

def menu_extras(stdscr):
    menu = [
        ("[A] Lihat Alias aktif",                 "alias_view"),
        ("[E] Edit file alias/bashrc",             "alias_edit"),
        ("[C] Lihat semua Cron job",               "cron_view"),
        ("[X] Edit Cron",                          "cron_edit"),
        ("[R] Rclone Copy dari Cloud",             "rclone"),
        ("[G] Generate Server Report",             "serverdocs"),
    ]
    choice = list_select(stdscr, "Extras", menu, label_fn=lambda x: x[0])
    if choice == -1:
        return

    action     = menu[choice][1]
    alias_file = config.get("alias", "file", str(__import__("pathlib").Path.home() / ".bashrc"))
    editor     = config.get_editor()
    cur_user   = config.get_current_user()

    if action == "alias_view":
        sub_menu = [
            ("[1] Alias aktif saat ini",        "active"),
            ("[2] Grep alias dari config file", "file"),
        ]
        sub = list_select(stdscr, "Alias", sub_menu, label_fn=lambda x: x[0])
        if sub == -1:
            return
        exit_tui_for_rich(stdscr)
        if sub_menu[sub][1] == "active":
            run_interactive("bash -i -c 'alias' 2>/dev/null")
        else:
            run_interactive(
                f"grep -n 'alias' '{alias_file}' | grep -v '^[[:space:]]*#' 2>/dev/null"
            )
        rich_ui.wait_key()
        restore_tui(stdscr)

    elif action == "alias_edit":
        exit_tui_for_rich(stdscr)
        run_interactive(f"{editor} '{alias_file}'")
        print(f"\n  Tip: source {alias_file}")
        rich_ui.wait_key()
        restore_tui(stdscr)

    elif action == "cron_view":
        lines = []
        out, _, _ = _run("crontab -l 2>&1")
        lines += ([f"[User {cur_user}]"] +
                  ([l for l in out.splitlines() if l.strip() and not l.startswith("#")]
                   or ["(kosong)"]) + [""])
        out, _, _ = _run("sudo crontab -l 2>&1")
        if "no crontab" not in out.lower():
            active = [l for l in out.splitlines()
                      if l.strip() and not l.startswith("#")]
            lines += ["[Root]"] + (active or ["(kosong)"]) + [""]
        out, _, code = _run("cat /etc/crontab 2>/dev/null")
        if code == 0:
            active = [l for l in out.splitlines()
                      if l.strip() and not l.startswith("#")]
            if active:
                lines += ["[/etc/crontab]"] + active + [""]
        out, _, _ = _run("ls /etc/cron.d/ 2>/dev/null")
        if out:
            lines += [f"[/etc/cron.d/] {out.replace(chr(10), ', ')}"]
        popup(stdscr, "Semua Cron Job", lines or ["Tidak ada cron job."])

    elif action == "cron_edit":
        sub_menu = [
            (f"[1] Edit cron user {cur_user}", "user"),
            ("[2] Edit cron root",             "root"),
            ("[3] Edit /etc/crontab",          "etc"),
        ]
        sub = list_select(stdscr, "Edit Cron", sub_menu, label_fn=lambda x: x[0])
        if sub == -1:
            return
        exit_tui_for_rich(stdscr)
        sub_act = sub_menu[sub][1]
        if sub_act == "user":
            run_interactive("crontab -e")
        elif sub_act == "root":
            run_interactive("sudo crontab -e")
        elif sub_act == "etc":
            run_interactive(f"sudo {editor} /etc/crontab")
        rich_ui.wait_key()
        restore_tui(stdscr)

    elif action == "rclone":
        menu_rclone(stdscr)

    elif action == "serverdocs":
        menu_serverdocs(stdscr)


def menu_rclone(stdscr):
    if not check_tool("rclone"):
        popup(stdscr, "Rclone", [
            "rclone tidak terinstall.",
            "",
            "Install: curl https://rclone.org/install.sh | sudo bash",
            "Setup  : rclone config",
        ])
        return

    remote_name = config.get("rclone", "remote_name", "mega")
    remote_path = config.get("rclone", "remote_path", "film")
    dest_radarr = config.get("rclone", "dest_radarr",
                             "/mnt/media/downloads/complete/radarr")
    dest_sonarr = config.get("rclone", "dest_sonarr",
                             "/mnt/media/downloads/complete/sonarr")

    dest_opts = [
        (f"Radarr  -> {dest_radarr}", dest_radarr),
        (f"Sonarr  -> {dest_sonarr}", dest_sonarr),
        ("Manual  -> ketik path sendiri", "__manual__"),
    ]
    idx = list_select(stdscr, "Rclone - Pilih Tujuan", dest_opts,
                      label_fn=lambda x: x[0])
    if idx == -1:
        return

    dest = dest_opts[idx][1]
    if dest == "__manual__":
        exit_tui_for_rich(stdscr)
        dest = input("  Path tujuan: ").strip()
        restore_tui(stdscr)
        if not dest:
            return

    exit_tui_for_rich(stdscr)
    print(f"\n  Rclone Copy dari {remote_name}:{remote_path}/")
    print(f"  Tujuan: {dest}\n")
    nama = input(f"  Nama file/folder di {remote_name}:{remote_path}/ : ").strip()
    if not nama:
        rich_ui.cli_error("Nama kosong, dibatalkan.")
        rich_ui.wait_key()
        restore_tui(stdscr)
        return

    ret = run_interactive(f'rclone copy {remote_name}:{remote_path}/"{nama}" "{dest}" -P')
    if ret == 0:
        rich_ui.cli_success("Selesai! File berhasil disalin.")
    elif ret == 130:
        rich_ui.cli_info("Dibatalkan.")
    else:
        rich_ui.cli_error(f"Gagal (exit {ret}). Cek: rclone listremotes")
    rich_ui.wait_key()
    restore_tui(stdscr)


def menu_serverdocs(stdscr):
    """Menu generate server documentation report."""
    doc_dir = config.get_doc_output_dir()

    menu = [
        ("[G] Generate server report (default path)", "generate"),
        ("[C] Generate ke path custom",               "custom"),
        ("[V] Lihat laporan terakhir",                "view_last"),
        ("[O] Buka folder laporan",                   "open_dir"),
    ]
    choice = list_select(stdscr, "Server Report", menu, label_fn=lambda x: x[0])
    if choice == -1:
        return

    action = menu[choice][1]

    if action in ("generate", "custom"):
        output_path = None
        if action == "custom":
            exit_tui_for_rich(stdscr)
            print(f"\n  Default dir: {doc_dir}")
            custom = input("  Path output (folder atau file lengkap): ").strip()
            restore_tui(stdscr)
            if custom:
                output_path = custom

        if confirm(stdscr,
                   f"Generate server documentation?\nOutput: {output_path or doc_dir}\n\n"
                   f"Proses ini membutuhkan beberapa menit."):
            exit_tui_for_rich(stdscr)
            print()
            result = rich_ui.generate_server_docs_with_progress(
                output_dir=doc_dir,
                output_path=output_path,
            )
            if result:
                import os
                size = os.path.getsize(result)
                rich_ui.cli_success(
                    f"Report selesai!\n"
                    f"  File: {result}\n"
                    f"  Size: {size:,} bytes"
                )
            rich_ui.wait_key()
            restore_tui(stdscr)

    elif action == "view_last":
        import glob
        from pathlib import Path
        pattern = str(Path(doc_dir) / "server-docs-*.txt")
        files   = sorted(glob.glob(pattern), reverse=True)
        if not files:
            popup(stdscr, "Server Report", [
                f"Belum ada laporan di {doc_dir}",
                "Pilih 'Generate' untuk membuat laporan."
            ])
        else:
            last = files[0]
            exit_tui_for_rich(stdscr)
            run_interactive(f"less '{last}'")
            rich_ui.wait_key()
            restore_tui(stdscr)

    elif action == "open_dir":
        popup(stdscr, "Folder Laporan", [
            f"Path: {doc_dir}",
            "",
            "Buka di terminal:",
            f"  cd {doc_dir}",
            f"  ls -la server-docs-*.txt",
        ])

# ══════════════════════════════════════════════════════════════════════════════
#  SETTINGS MENU
# ══════════════════════════════════════════════════════════════════════════════

def menu_settings(stdscr):
    menu = [
        ("[H] Hostname server",              "hostname"),
        ("[C] Compose file path",            "compose_file"),
        ("[D] Compose command",              "compose_cmd"),
        ("[E] Editor default",               "editor"),
        ("[A] File alias/bashrc",            "alias_file"),
        ("[R] Rclone remote & path",         "rclone"),
        ("[O] Output dir server report",     "doc_dir"),
        ("[F] Fetch interval (detik)",       "fetch"),
        ("[W] Wizard setup ulang",           "wizard"),
        ("[V] Lihat config saat ini",        "view"),
    ]
    choice = list_select(stdscr, f"Settings [{config.CONFIG_FILE}]",
                         menu, label_fn=lambda x: x[0])
    if choice == -1:
        return
    action = menu[choice][1]

    def update(section, key, prompt, current):
        exit_tui_for_rich(stdscr)
        print(f"\n  {prompt}")
        print(f"  Saat ini: {current or '(kosong)'}")
        val = input("  Nilai baru (Enter = tidak berubah): ").strip()
        if val:
            config.set_value(section, key, val)
            rich_ui.cli_success(f"{key} = {val}")
        else:
            rich_ui.cli_info("Tidak ada perubahan.")
        rich_ui.wait_key()
        restore_tui(stdscr)

    if action == "hostname":
        update("general", "hostname", "Hostname server", config.get_hostname())
    elif action == "compose_file":
        exit_tui_for_rich(stdscr)
        print(f"\n  Saat ini: {config.get_compose_file() or '(belum diset)'}")
        print("  Mencari file...", end="", flush=True)
        found = config.find_compose_files()
        print(f" {len(found)} ditemukan")
        for i, f in enumerate(found):
            print(f"  {i+1}. {f}")
        print(f"  {len(found)+1}. Ketik manual")
        val = input("  Pilih/ketik path: ").strip()
        if val.isdigit() and found:
            idx = int(val) - 1
            if 0 <= idx < len(found):
                val = found[idx]
        if val and not val.isdigit():
            config.set_value("docker", "compose_file", val)
            config.set_value("docker", "compose_dir",
                             str(__import__("pathlib").Path(val).parent))
            rich_ui.cli_success(val)
        rich_ui.wait_key()
        restore_tui(stdscr)
    elif action == "compose_cmd":
        update("docker", "compose_cmd", "Compose command (auto/docker compose/docker-compose)",
               config.get_compose_cmd())
    elif action == "editor":
        update("general", "editor", "Editor (nano/vim/vi)", config.get_editor())
    elif action == "alias_file":
        update("alias", "file", "Path file alias/bashrc",
               config.get("alias", "file"))
    elif action == "rclone":
        update("rclone", "remote_name", "Nama rclone remote",
               config.get("rclone", "remote_name"))
        update("rclone", "remote_path", "Path di remote",
               config.get("rclone", "remote_path"))
    elif action == "doc_dir":
        update("general", "doc_output_dir", "Folder output server report",
               config.get_doc_output_dir())
    elif action == "fetch":
        update("general", "fetch_interval", "Interval auto-refresh (detik)",
               config.get("general", "fetch_interval"))
    elif action == "wizard":
        exit_tui_for_rich(stdscr)
        run_wizard()
        rich_ui.wait_key()
        restore_tui(stdscr)
    elif action == "view":
        cfg = config.load()
        lines = [f"Config: {config.CONFIG_FILE}", ""]
        for section in cfg.sections():
            lines.append(f"[{section}]")
            for k, v in cfg.items(section):
                lines.append(f"  {k} = {v}")
            lines.append("")
        popup(stdscr, "Konfigurasi Aktif", lines)

# ══════════════════════════════════════════════════════════════════════════════
#  HELP
# ══════════════════════════════════════════════════════════════════════════════

def screen_help(stdscr):
    lines = [
        f"{config.APP_NAME} v{config.VERSION}",
        "",
        "NAVIGASI:",
        "  ^ / k         Naik",
        "  v / j         Turun",
        "  Enter         Pilih / Buka menu",
        "  q / Esc       Kembali / Keluar",
        "",
        "SHORTCUT UTAMA:",
        "  r  Refresh container",
        "  a  Aksi semua container",
        "  i  Daftar images",
        "  s  Docker stats",
        "  d  Disk usage",
        "  c  Docker Compose",
        "  x  Extras (alias, cron, rclone, server report)",
        "  w  GNU Screen manager",
        "  t  Settings / Konfigurasi",
        "  ?  Help",
        "",
        "MENU [X] = tekan huruf langsung untuk pilih cepat.",
        "",
        "HYBRID UI:",
        "  Navigasi  -> Curses (terminal interaktif)",
        "  Output    -> Rich (tabel, logs, highlight)",
        "",
        f"Config: {config.CONFIG_FILE}",
    ]
    popup(stdscr, f"{config.APP_NAME} - Help", lines)

# ======================================================================
# SOURCE: ui/cli_menu.py
# ======================================================================




def pick_container(show_all: bool = False):
    """Tampilkan list container, user pilih nomor."""
    flag       = "-a" if show_all else ""
    containers = docker.get_containers() if show_all else [
        c for c in docker.get_containers() if c["running"]
    ]
    if not containers and not show_all:
        containers = docker.get_containers()

    if not containers:
        rich_ui.cli_error("Tidak ada container.")
        return None

    rich_ui.show_containers(containers)
    try:
        idx = int(input("  Pilih nomor [0=batal]: ").strip()) - 1
        if idx == -1:
            return None
        if 0 <= idx < len(containers):
            return containers[idx]["name"]
        rich_ui.cli_error("Nomor tidak valid.")
        return None
    except (ValueError, EOFError):
        return None


def run_menu():
    """Main loop fallback menu."""
    W = 60

    while True:
        compose_file = config.get_compose_file()
        compose_dir  = config.get_compose_dir()
        compose_cmd  = config.get_compose_cmd()
        editor       = config.get_editor()
        alias_file   = config.get("alias", "file", str(Path.home() / ".bashrc"))
        remote_name  = config.get("rclone", "remote_name", "mega")
        remote_path  = config.get("rclone", "remote_path", "film")
        dest_radarr  = config.get("rclone", "dest_radarr",
                                  "/mnt/media/downloads/complete/radarr")
        cur_user     = config.get_current_user()
        doc_dir      = config.get_doc_output_dir()

        os.system("clear")
        print("=" * W)
        print(f"  {config.APP_NAME} v{config.VERSION} -- Docker Manager")
        print(f"  Host: {config.get_hostname()}  |  User: {cur_user}")
        print("=" * W)
        print("  --- CONTAINER ---")
        print("  1.  List semua container")
        print("  2.  Update image (1 container)")
        print("  3.  Update SEMUA image")
        print("  4.  Restart container tertentu")
        print("  5.  Restart SEMUA container")
        print("  6.  Docker Stats real-time")
        print("  7.  Lihat logs container")
        print("  8.  Exec shell container")
        print("  --- COMPOSE ---")
        print("  9.  Docker Compose UP")
        print("  10. Docker Compose DOWN")
        print("  11. Lihat docker-compose.yml")
        print("  12. Edit docker-compose.yml")
        print("  13. Backup docker-compose.yml")
        print("  --- MAINTENANCE ---")
        print("  14. Prune image tidak terpakai")
        print("  15. Prune volumes tidak terpakai")
        print("  16. Prune TOTAL")
        print("  17. Docker disk usage")
        print("  --- EXTRAS ---")
        print("  18. Lihat alias aktif")
        print("  19. Grep alias dari config file")
        print("  20. Edit file alias/bashrc")
        print("  21. Lihat semua cron")
        print("  22. Edit cron")
        print("  23. Rclone copy dari cloud")
        print("  24. Generate server report")
        print("  --- GNU SCREEN ---")
        print("  25. List screen session")
        print("  26. Attach ke session")
        print("  27. Kill 1 session")
        print("  28. Kill SEMUA session")
        print("  29. Buat session baru")
        print("  30. Jalankan perintah di background")
        print("  --- SETTINGS ---")
        print("  31. Lihat konfigurasi")
        print("  32. Jalankan wizard setup")
        print("  0.  Keluar")
        print("=" * W)
        choice = input("  Pilih: ").strip()

        if choice == "0":
            break

        # --- CONTAINER ---
        elif choice == "1":
            rich_ui.show_containers(docker.get_containers())

        elif choice == "2":
            name = pick_container()
            if name:
                image = docker.get_container_image(name)
                if image:
                    print(f"\n  Pull: {image}")
                    run_interactive(f"docker pull {image}")
                else:
                    rich_ui.cli_error("Gagal mendapatkan image.")

        elif choice == "3":
            run_interactive(
                "docker ps --format '{{.Image}}' | sort -u | xargs -I{} docker pull {}"
            )

        elif choice == "4":
            name = pick_container()
            if name:
                run_interactive(f"docker restart {name}")

        elif choice == "5":
            run_interactive("docker ps -q | xargs -r docker restart")

        elif choice == "6":
            stats = docker.get_stats_once()
            rich_ui.show_stats(stats)
            print("  Untuk live stats:\n")
            run_interactive("docker stats")

        elif choice == "7":
            name = pick_container(show_all=True)
            if name:
                n    = input("  Berapa baris? [50]: ").strip() or "50"
                live = input("  Live logs? (y/N): ").strip()
                if live.lower() == "y":
                    rich_ui.stream_logs(name, tail=int(n))
                else:
                    logs = docker.get_container_logs(name, tail=int(n))
                    rich_ui.show_logs(name, logs)

        elif choice == "8":
            name = pick_container()
            if name:
                run_interactive(
                    f"docker exec -it {name} bash 2>/dev/null || "
                    f"docker exec -it {name} sh"
                )

        # --- COMPOSE ---
        elif choice == "9":
            if not compose_dir:
                rich_ui.cli_error("Compose dir belum dikonfigurasi. Jalankan pilihan 32.")
            else:
                run_interactive(f"cd '{compose_dir}' && {compose_cmd} up -d")

        elif choice == "10":
            if not compose_dir:
                rich_ui.cli_error("Compose dir belum dikonfigurasi.")
            else:
                run_interactive(f"cd '{compose_dir}' && {compose_cmd} down")

        elif choice == "11":
            if not compose_file:
                rich_ui.cli_error("Compose file belum dikonfigurasi.")
            else:
                rich_ui.show_compose_file(compose_file)

        elif choice == "12":
            if not compose_file:
                rich_ui.cli_error("Compose file belum dikonfigurasi.")
            else:
                run_interactive(f"{editor} '{compose_file}'")

        elif choice == "13":
            if not compose_file:
                rich_ui.cli_error("Compose file belum dikonfigurasi.")
            else:
                ts  = datetime.now().strftime("%Y%m%d_%H%M%S")
                dst = f"{compose_file}.bak_{ts}"
                _, err, code = run_cmd(f"cp '{compose_file}' '{dst}'")
                if code == 0:
                    rich_ui.cli_success(f"Backup: {dst}")
                else:
                    rich_ui.cli_error(f"Gagal: {err}")

        # --- MAINTENANCE ---
        elif choice == "14":
            imgs = docker.get_dangling_images()
            if not imgs:
                rich_ui.cli_info("Tidak ada dangling image.")
            else:
                ok = input(f"  Hapus {len(imgs)} dangling image? (y/N): ")
                if ok.lower() == "y":
                    run_interactive("docker image prune -f")

        elif choice == "15":
            vols = docker.get_orphan_volumes()
            if not vols:
                rich_ui.cli_info("Tidak ada orphan volume.")
            else:
                ok = input(f"  Hapus {len(vols)} orphan volume? (y/N): ")
                if ok.lower() == "y":
                    run_interactive("docker volume prune -f")

        elif choice == "16":
            ok = input("  !! Prune TOTAL? Tidak bisa di-undo! (y/N): ")
            if ok.lower() == "y":
                run_interactive("docker system prune -af --volumes")

        elif choice == "17":
            disk = docker.get_disk_usage()
            rich_ui.show_disk_usage(disk)

        # --- EXTRAS ---
        elif choice == "18":
            run_interactive("bash -i -c 'alias' 2>/dev/null")

        elif choice == "19":
            run_interactive(
                f"grep -n 'alias' '{alias_file}' | "
                f"grep -v '^[[:space:]]*#' 2>/dev/null"
            )

        elif choice == "20":
            run_interactive(f"{editor} '{alias_file}'")
            rich_ui.cli_info(f"Tip: source {alias_file}")

        elif choice == "21":
            print(f"\n[User {cur_user}]")
            run_interactive("crontab -l 2>&1")
            print("\n[Root]")
            run_interactive("sudo crontab -l 2>&1")
            print("\n[/etc/crontab - baris aktif]")
            run_interactive("grep -v '^#' /etc/crontab 2>/dev/null | grep -v '^$'")

        elif choice == "22":
            print("  1. Edit cron user saya")
            print("  2. Edit cron root")
            print("  3. Edit /etc/crontab")
            sub = input("  Pilih [1/2/3]: ").strip()
            if sub == "1":
                run_interactive("crontab -e")
            elif sub == "2":
                run_interactive("sudo crontab -e")
            elif sub == "3":
                run_interactive(f"sudo {editor} /etc/crontab")

        elif choice == "23":
            if not check_tool("rclone"):
                rich_ui.cli_error("rclone tidak terinstall.")
            else:
                dest = input(f"  Tujuan [{dest_radarr}]: ").strip() or dest_radarr
                nama = input(f"  Nama file di {remote_name}:{remote_path}/ : ").strip()
                if nama:
                    run_interactive(
                        f'rclone copy {remote_name}:{remote_path}/"{nama}" "{dest}" -P'
                    )
                else:
                    rich_ui.cli_error("Nama kosong.")

        elif choice == "24":
            print(f"\n  Default output: {doc_dir}")
            custom = input("  Path custom (Enter = default): ").strip()
            output_path = custom if custom else None
            print()
            result = rich_ui.generate_server_docs_with_progress(
                output_dir=doc_dir,
                output_path=output_path,
            )
            if result:
                import os as _os
                size = _os.path.getsize(result)
                rich_ui.cli_success(f"Report: {result} ({size:,} bytes)")

        # --- GNU SCREEN ---
        elif choice == "25":
            sessions = docker.get_screens()
            rich_ui.show_screen_sessions(sessions)

        elif choice in ("26", "27"):
            sessions = docker.get_screens()
            if not sessions:
                rich_ui.cli_info("Tidak ada session aktif.")
            else:
                rich_ui.show_screen_sessions(sessions)
                try:
                    idx = int(input("  Pilih nomor: ").strip()) - 1
                    if 0 <= idx < len(sessions):
                        s = sessions[idx]
                        if choice == "26":
                            print(f"\n  Ctrl+A lalu D untuk detach")
                            run_interactive(f"screen -r {s['sid']}")
                        else:
                            ok = input(f"  Kill '{s['name']}'? (y/N): ")
                            if ok.lower() == "y":
                                ok2, msg = docker.screen_kill(s["sid"])
                                (rich_ui.cli_success if ok2 else rich_ui.cli_error)(msg)
                    else:
                        rich_ui.cli_error("Nomor tidak valid.")
                except ValueError:
                    rich_ui.cli_info("Dibatalkan.")

        elif choice == "28":
            ok = input("  Kill SEMUA session? (y/N): ")
            if ok.lower() == "y":
                sessions = docker.get_screens()
                failed = [s["name"] for s in sessions
                          if not docker.screen_kill(s["sid"])[0]]
                if failed:
                    rich_ui.cli_error(f"Gagal: {', '.join(failed)}")
                else:
                    rich_ui.cli_success(f"Semua {len(sessions)} session dimatikan.")

        elif choice == "29":
            nama = sanitize_input(input("  Nama session: ").strip())
            if nama:
                print("  Ctrl+A lalu D untuk detach")
                run_interactive(f"screen -S {nama}")
            else:
                rich_ui.cli_error("Nama kosong.")

        elif choice == "30":
            nama = sanitize_input(input("  Nama session: ").strip()) or "dockman-task"
            cmd  = input("  Perintah: ").strip()
            if cmd:
                ret = run_interactive(f"screen -dmS {nama} bash -c '{cmd}; exec bash'")
                if ret == 0:
                    rich_ui.cli_success(f"Session '{nama}' running. Masuk: screen -r {nama}")
                else:
                    rich_ui.cli_error(f"Gagal (exit {ret})")
            else:
                rich_ui.cli_error("Perintah kosong.")

        # --- SETTINGS ---
        elif choice == "31":
            cfg = config.load()
            print(f"\n  Config: {config.CONFIG_FILE}\n")
            for section in cfg.sections():
                print(f"  [{section}]")
                for k, v in cfg.items(section):
                    print(f"    {k} = {v}")
                print()

        elif choice == "32":
            # (inline import stripped by build.py: from ui.wizard import run_wizard)
            run_wizard()

        else:
            rich_ui.cli_error(f"Pilihan tidak valid: {choice}")

        try:
            input("\n  Tekan Enter untuk lanjut...")
        except (EOFError, KeyboardInterrupt):
            break

# ========================================================================
# MODULE STUBS - di-generate otomatis oleh build.py
# Memetakan module references ke fungsi inline di single-file build
# ========================================================================
import types as _types

# Stub: import core.config as config
config = _types.SimpleNamespace(
    load=load, save=save, get=get, set_value=set_value,
    get_hostname=get_hostname, get_editor=get_editor,
    get_compose_file=get_compose_file, get_compose_dir=get_compose_dir,
    get_compose_cmd=get_compose_cmd, get_doc_output_dir=get_doc_output_dir,
    get_current_user=get_current_user, detect_compose_cmd=detect_compose_cmd,
    find_compose_files=find_compose_files, is_first_run=is_first_run,
    VERSION=VERSION, APP_NAME=APP_NAME,
    CONFIG_DIR=CONFIG_DIR, CONFIG_FILE=CONFIG_FILE,
)

# Stub: import core.docker as docker
docker = _types.SimpleNamespace(
    get_containers=get_containers, get_container_logs=get_container_logs,
    get_container_inspect=get_container_inspect, container_action=container_action,
    pull_image=pull_image, get_container_image=get_container_image,
    get_images=get_images, get_dangling_images=get_dangling_images,
    remove_image=remove_image, get_orphan_volumes=get_orphan_volumes,
    get_disk_usage=get_disk_usage, get_stats_once=get_stats_once,
    compose_action=compose_action, compose_validate=compose_validate,
    get_screens=get_screens, screen_kill=screen_kill,
)

# Stub: import ui.rich_ui as rich_ui
rich_ui = _types.SimpleNamespace(
    show_containers=show_containers, show_images=show_images,
    show_stats=show_stats, show_disk_usage=show_disk_usage,
    show_logs=show_logs, stream_logs=stream_logs,
    show_inspect=show_inspect, show_compose_file=show_compose_file,
    show_screen_sessions=show_screen_sessions,
    generate_server_docs_with_progress=generate_server_docs_with_progress,
    cli_header=cli_header, cli_error=cli_error,
    cli_success=cli_success, cli_info=cli_info,
    confirm_cli=confirm_cli, wait_key=wait_key,
    RICH_AVAILABLE=RICH_AVAILABLE,
)

# Stub: from ui.tui import run_tui (fungsi sudah inline)
# run_tui didefinisikan di main.py, dipanggil dari curses_ui

# ======================================================================
# SOURCE: main.py
# ======================================================================
#!/usr/bin/env python3
"""
main.py - Entry point Dockman v2.2.0
Kembali ke Curses TUI yang stable, dengan home dashboard.
"""


# sys.path.insert - tidak diperlukan di single-file build



def dockman_banner(skip: bool = False):
    """Banner animasi dockman>_ saat startup."""
    import time as _t

    if skip or not sys.stdout.isatty():
        return

    colorterm = os.environ.get("COLORTERM", "")
    term      = os.environ.get("TERM", "")

    if colorterm in ("truecolor", "24bit"):
        dock_col = "\033[38;2;210;214;220m"
        man_col  = "\033[38;2;79;124;247m"
    elif "256" in term or "xterm" in term:
        dock_col = "\033[38;5;250m"
        man_col  = "\033[38;5;75m"
    else:
        dock_col = "\033[97m"
        man_col  = "\033[94m"
    reset = "\033[0m"

    text = "dockman"
    try:
        for i in range(1, len(text) + 1):
            dock_part = text[:min(i, 4)]
            man_part  = text[4:i] if i > 4 else ""
            sys.stdout.write(
                f"\r  {dock_col}{dock_part}{man_col}{man_part}_{reset}   "
            )
            sys.stdout.flush()
            _t.sleep(0.055)

        for _ in range(5):
            sys.stdout.write(f"\r  {dock_col}dock{man_col}man>__{reset}   ")
            sys.stdout.flush(); _t.sleep(0.35)
            sys.stdout.write(f"\r  {dock_col}dock{man_col}man>  {reset}   ")
            sys.stdout.flush(); _t.sleep(0.35)

        sys.stdout.write(
            f"\r  {dock_col}dock{man_col}man{reset}"
            f" [dim]v{config.VERSION}[/dim]"
            f"  {man_col}>_{reset}\n\n"
        )
        sys.stdout.flush()
    except (KeyboardInterrupt, Exception):
        sys.stdout.write("\n")
        sys.stdout.flush()


def run_tui():
    """Jalankan Curses TUI - home screen sebagai landing page."""
    import curses
    # (inline import stripped by build.py: from ui.curses_ui import init_colors, screen_home, screen_containers)

    def tui_main(stdscr):
        stdscr.keypad(True)
        init_colors()
        curses.curs_set(0)
        # Home dashboard dulu, user bisa navigasi dari sana
        screen_home(stdscr)
        # Setelah keluar home (q/h), lanjut ke container list
        screen_containers(stdscr)

    curses.wrapper(tui_main)


def run_cli_menu():
    """Jalankan fallback menu numbered."""
    # (inline import stripped by build.py: from ui.cli_menu import run_menu)
    run_menu()


def run_cli_command(args):
    """CLI command langsung dengan Rich output."""
    # (inline import stripped by build.py: import core.docker as docker)

    cmd = args[0] if args else ""
    rich_ui.cli_header(config.get_hostname(), config.VERSION)

    if cmd == "ps":
        rich_ui.show_containers(docker.get_containers())
    elif cmd == "images":
        rich_ui.show_images(docker.get_images())
    elif cmd == "stats":
        rich_ui.show_stats(docker.get_stats_once())
    elif cmd == "df":
        rich_ui.show_disk_usage(docker.get_disk_usage())
    elif cmd == "logs":
        if len(args) < 2:
            rich_ui.cli_error("Usage: dockman logs <container> [baris]")
            sys.exit(1)
        name = args[1]
        tail = int(args[2]) if len(args) > 2 else 50
        rich_ui.show_logs(name, docker.get_container_logs(name, tail=tail))
    elif cmd == "live":
        if len(args) < 2:
            rich_ui.cli_error("Usage: dockman live <container>")
            sys.exit(1)
        rich_ui.stream_logs(args[1])
    elif cmd == "inspect":
        if len(args) < 2:
            rich_ui.cli_error("Usage: dockman inspect <container>")
            sys.exit(1)
        rich_ui.show_inspect(args[1], docker.get_container_inspect(args[1]))
    elif cmd == "screens":
        rich_ui.show_screen_sessions(docker.get_screens())
    elif cmd == "report":
        print()
        output_path = args[1] if len(args) > 1 else None
        result = rich_ui.generate_server_docs_with_progress(
            output_dir=config.get_doc_output_dir(),
            output_path=output_path,
        )
        if result:
            import os as _os
            size = _os.path.getsize(result)
            rich_ui.cli_success(
                f"Report selesai!\n"
                f"  File : {result}\n"
                f"  Size : {size:,} bytes"
            )
    else:
        rich_ui.cli_error(f"Perintah tidak dikenal: '{cmd}'")
        print_help()
        sys.exit(1)


def print_help():
    print(f"""
  {config.APP_NAME} v{config.VERSION} - Docker Manager

  USAGE:
    dockman                    TUI mode (Curses, default)
    dockman --menu             Menu numbered (Rich output)
    dockman --setup            Setup wizard
    dockman --debug            TUI + detail error
    dockman --version          Tampilkan versi
    dockman --help             Tampilkan bantuan ini

  CLI COMMANDS (output Rich):
    dockman ps                 List semua container
    dockman images             List semua images
    dockman stats              Docker stats (snapshot)
    dockman df                 Docker disk usage
    dockman logs <n>        Logs (50 baris)
    dockman logs <n> <n>    Logs (n baris)
    dockman live <n>        Live logs container
    dockman inspect <n>     Inspect container (JSON)
    dockman screens            List GNU screen sessions
    dockman report             Generate server report
    dockman report <path>      Generate ke path custom

  CONFIG: {config.CONFIG_FILE}
""")


def main():
    args = sys.argv[1:]

    if "--version" in args or "-v" in args:
        print(f"{config.APP_NAME} v{config.VERSION}")
        sys.exit(0)

    if "--help" in args or "-h" in args:
        print_help()
        sys.exit(0)

    config.load()

    if "--setup" in args:
        # (inline import stripped by build.py: from ui.wizard import run_wizard)
        run_wizard()
        sys.exit(0)

    # Skip docker check untuk report
    skip_docker = args and args[0] == "report"
    if not skip_docker:
        try:
            check_docker()
        except DockerError as e:
            print(f"\n  ERROR: {e}\n")
            sys.exit(1)

    # First run wizard
    if config.is_first_run() and not args:
        print(f"\n  Selamat datang di {config.APP_NAME} v{config.VERSION}!")
        print("  Config belum ada. Jalankan setup wizard?\n")
        val = input("  [Y/n]: ").strip()
        if val.lower() != "n":
            # (inline import stripped by build.py: from ui.wizard import run_wizard)
            run_wizard()
            config.load()
            print()

    # CLI command mode
    CLI_COMMANDS = {"ps", "images", "stats", "df", "logs",
                    "live", "inspect", "screens", "report"}
    if args and args[0] in CLI_COMMANDS:
        run_cli_command(args)
        return

    # Menu mode
    if "--menu" in args or "-m" in args or "menu" in args:
        run_cli_menu()
        return

    debug_mode = "--debug" in args

    # Banner (skip di debug mode)
    dockman_banner(skip=debug_mode)

    # TUI mode (Curses)
    if not os.environ.get("TERM"):
        os.environ["TERM"] = "xterm-256color"

    tui_error = None
    try:
        run_tui()
        return
    except Exception as e:
        tui_error = e

    if debug_mode:
        print(f"\n  TUI Error: {type(tui_error).__name__}: {tui_error}")
        traceback.print_exc()
        print(f"\n  TERM   = {os.environ.get('TERM')}")
        print(f"  Config = {config.CONFIG_FILE}")
        sys.exit(1)
    else:
        print(f"\n  WARN: TUI gagal ({type(tui_error).__name__}), beralih ke --menu...")
        print("  Tip: dockman --debug untuk detail\n")
        time.sleep(1)
        run_cli_menu()


if __name__ == "__main__":
    main()