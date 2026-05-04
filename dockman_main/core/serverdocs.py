"""
core/serverdocs.py - Server documentation generator
Port dari server-docs.sh ke Python, dengan output path yang configurable.
"""

import subprocess
import socket
import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

from core.utils import run_cmd


def _run(cmd: str) -> str:
    out, err, code = run_cmd(cmd, timeout=15)
    if code == 0 and out:
        return out
    return err or "(tidak ada output)"

def _section(title: str) -> str:
    return f"\n{'='*60}\n {title}\n{'='*60}\n"

def _divider() -> str:
    return "-" * 60 + "\n"


class ServerDocsGenerator:
    def __init__(self, output_dir: str = None, progress_cb: Callable = None):
        from core.config import get_doc_output_dir
        self.output_dir  = Path(output_dir or get_doc_output_dir())
        self.progress_cb = progress_cb or (lambda s, t, l: None)
        self.hostname    = socket.gethostname()
        self._lines      = []

    def _w(self, text: str = ""):
        self._lines.append(text)

    def _flush(self) -> str:
        return "\n".join(self._lines)

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
        self._w(f"GPU            : {_run('lspci | grep -i vga | sed \"s/.*: //\"')}")

    def section_storage(self):
        self._w(_section("STORAGE"))
        self._w(_run("lsblk -o NAME,SIZE,TYPE,FSTYPE,MOUNTPOINT,LABEL"))
        self._w("\n--- Penggunaan Disk ---")
        self._w(_run("df -h --output=target,size,used,avail,pcent | grep -E '^(/|/data|/mnt|/boot)'"))

    def section_mounts(self):
        self._w(_section("MOUNT POINTS MEDIA"))
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
        self._w(_run("systemctl list-units --type=service --state=running --no-legend | awk '{print $1, $3, $4}'"))

    def section_docker(self):
        self._w(_section("DOCKER"))
        self._w("--- Versi ---")
        self._w(_run("docker version 2>/dev/null || echo 'Docker tidak terinstall'"))
        self._w("\n--- Info ---")
        self._w(_run("docker info 2>/dev/null | grep -E 'Containers|Running|Paused|Stopped|Images|Storage Driver|Docker Root Dir|Total Memory'"))
        self._w("\n--- Semua Container ---")
        self._w(_run("docker ps -a --format 'table {{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}' 2>/dev/null"))
        self._w("\n--- Images ---")
        self._w(_run("docker images --format 'table {{.Repository}}\t{{.Tag}}\t{{.Size}}\t{{.CreatedSince}}' 2>/dev/null"))
        self._w("\n--- Networks ---")
        self._w(_run("docker network ls 2>/dev/null"))
        self._w("\n--- Volumes ---")
        self._w(_run("docker volume ls 2>/dev/null"))
        self._w("\n--- Disk Usage ---")
        self._w(_run("docker system df 2>/dev/null"))

    def section_compose_projects(self):
        self._w(_section("DOCKER COMPOSE PROJECTS"))
        search_base = "/home /root /opt /srv /etc /data /mnt"
        out = _run(f"find {search_base} -maxdepth 6 \\( -name 'docker-compose.yml' -o -name 'docker-compose.yaml' -o -name 'compose.yml' -o -name 'compose.yaml' \\) 2>/dev/null | sort")
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
            self._w(_run(f"cd '{dirpath}' && (docker compose ps 2>/dev/null || docker-compose ps 2>/dev/null) || echo 'Tidak dapat membaca status'"))
            self._w(f"\n[Isi {Path(filepath).name}]")
            try:
                with open(filepath, "r", errors="replace") as f:
                    self._w(f.read())
            except Exception as e:
                self._w(f"[Tidak bisa dibaca: {e}]")

    def section_yml_files(self):
        self._w(_section("SEMUA FILE YML / YAML"))
        search_base = "/home /root /opt /srv /etc /data /mnt"
        out = _run(f"find {search_base} -maxdepth 6 \\( -name '*.yml' -o -name '*.yaml' \\) ! -path '*/node_modules/*' ! -path '*/.git/*' ! -path '*/vendor/*' 2>/dev/null | sort")
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
        out = _run(f"find {search_base} -maxdepth 6 \\( -name '*.yml' -o -name '*.yaml' \\) ! -name 'docker-compose*' ! -name 'compose.yml' ! -name 'compose.yaml' ! -path '*/node_modules/*' ! -path '*/.git/*' ! -path '*/vendor/*' 2>/dev/null | sort")
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
        from core.config import get_current_user
        cur_user = get_current_user()
        self._w(_section("CRON JOBS"))
        self._w(f"--- Root ---")
        self._w(_run("crontab -l 2>/dev/null || echo 'Tidak ada cron job untuk root'"))
        self._w(f"\n--- User {cur_user} ---")
        self._w(_run(f"crontab -u {cur_user} -l 2>/dev/null || echo 'Tidak ada cron job untuk {cur_user}'"))
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
        from core.config import get_current_user
        self._w("")
        self._w("=" * 60)
        self._w(f" Dibuat oleh : {get_current_user()}")
        self._w(f" Waktu       : {datetime.now().strftime('%d %B %Y, %H:%M WIB')}")
        self._w("=" * 60)

    def section_netplan(self):
        self._w(_section("NETPLAN NETWORK CONFIGURATION"))
        netplan_dir = Path("/etc/netplan")
        if not netplan_dir.exists():
            self._w("Netplan tidak ditemukan (/etc/netplan tidak ada).")
            self._w("Sistem mungkin menggunakan NetworkManager atau ifupdown.")
            return
        try:
            files = sorted([f for f in netplan_dir.iterdir() if f.suffix in (".yaml", ".yml") and f.is_file()])
        except PermissionError:
            out, err, code = run_cmd("sudo ls /etc/netplan/ 2>/dev/null")
            if code != 0:
                self._w("Tidak bisa membaca /etc/netplan/ (Permission denied).")
                return
            files = [netplan_dir / f.strip() for f in out.splitlines() if f.strip().endswith(('.yaml', '.yml'))]
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
            content = None
            try:
                content = Path(filepath).read_text(errors="replace")
            except PermissionError:
                out, err, code = run_cmd(f"sudo cat '{filepath}' 2>/dev/null")
                if code == 0 and out:
                    content = out
                else:
                    self._w(f"[Permission denied]")
            except OSError as e:
                self._w(f"[Error: {e}]")
            if content:
                self._w(content)
            self._w("")
        for cmd_try in ["netplan status 2>/dev/null", "sudo netplan status 2>/dev/null"]:
            out, _, code = run_cmd(cmd_try)
            if code == 0 and out and "command not found" not in out.lower():
                self._w("\n--- Netplan Status ---")
                self._w(out)
                break

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
        total = len(self.SECTIONS)
        self._lines = []
        for step, (label, method_name) in enumerate(self.SECTIONS, 1):
            self.progress_cb(step, total, label)
            try:
                getattr(self, method_name)()
            except Exception as e:
                self._w(f"\n[ERROR di section {label}: {e}]\n")
        if output_path:
            out_path = Path(output_path)
        else:
            filename = f"server-docs-{datetime.now().strftime('%Y%m%d')}.txt"
            out_path = self.output_dir / filename
        out_path.parent.mkdir(parents=True, exist_ok=True)
        content = self._flush()
        out_path.write_text(content, encoding="utf-8", errors="replace")
        return str(out_path)
