"""
core/bootstrap.py - Bootstrap Wizard state & phase management untuk Dockman v3.0.0

Modul ini mengelola state bootstrap wizard dan mendefinisikan 7 phases.
Tidak ada UI dependency - murni business logic.
"""

import json
import socket
import shutil
import re
from pathlib import Path
from typing import Optional, Dict, List, Any
from datetime import datetime

from core.utils import run_cmd
from core.config import CONFIG_DIR, get_current_user


# ── State file ────────────────────────────────────────────────────────────────

BOOTSTRAP_STATE_FILE = CONFIG_DIR / "bootstrap_state.json"
BOOTSTRAP_VERSION    = "3.0.0"


# ── Phase definitions ─────────────────────────────────────────────────────────

PHASES = [
    {
        "id":          "system_prep",
        "number":      1,
        "title":       "Persiapan Sistem",
        "description": "Update packages, hostname, timezone, locale, SSH hardening",
        "steps": ["update_packages", "set_hostname", "set_timezone", "set_locale", "ssh_hardening"],
    },
    {
        "id":          "network",
        "number":      2,
        "title":       "Konfigurasi Jaringan",
        "description": "Static IP via netplan, DNS over HTTPS, UFW, mDNS",
        "steps": ["static_ip", "doh_setup", "ufw_basic", "mdns_setup"],
    },
    {
        "id":          "storage",
        "number":      3,
        "title":       "Manajemen Storage",
        "description": "Deteksi disk, format, mount, folder structure media",
        "steps": ["detect_disks", "select_disk", "format_mount", "folder_structure"],
    },
    {
        "id":          "docker_setup",
        "number":      4,
        "title":       "Setup Docker",
        "description": "Install Docker, daemon config, log rotation, network",
        "steps": ["install_docker", "daemon_config", "docker_network"],
    },
    {
        "id":          "stack_selection",
        "number":      5,
        "title":       "Pilih Stack Aplikasi",
        "description": "Media server, downloader, arr suite, reverse proxy, monitoring",
        "steps": ["media_server", "downloader", "arr_suite", "indexer",
                  "request_manager", "reverse_proxy", "dashboard", "monitoring", "dns_adblock"],
    },
    {
        "id":          "remote_access",
        "number":      6,
        "title":       "Remote Access",
        "description": "Tailscale dan/atau Cloudflare Tunnel",
        "steps": ["tailscale", "cloudflare_tunnel"],
    },
    {
        "id":          "deploy",
        "number":      7,
        "title":       "Deploy & Verifikasi",
        "description": "docker compose up, health check, tampilkan URL akses",
        "steps": ["generate_compose", "deploy", "health_check", "summary"],
    },
]

# Status konstanta
STATUS_PENDING = "pending"
STATUS_RUNNING = "running"
STATUS_DONE    = "done"
STATUS_SKIPPED = "skipped"
STATUS_FAILED  = "failed"


# ══════════════════════════════════════════════════════════════════════════════
#  BOOTSTRAP STATE
# ══════════════════════════════════════════════════════════════════════════════

class BootstrapState:
    """
    Menyimpan dan load state bootstrap wizard ke JSON.
    State bisa dilanjutkan dari phase manapun (resume-able).
    Wizard bisa dipanggil ulang per-section tanpa harus dari awal.
    """

    def __init__(self):
        self.version       = BOOTSTRAP_VERSION
        self.created_at    = datetime.now().isoformat()
        self.updated_at    = datetime.now().isoformat()
        self.current_phase = None
        self.completed     = False

        # Status per phase
        self.phases: Dict[str, Dict] = {
            p["id"]: {
                "status":  STATUS_PENDING,
                "skipped": False,
                "data":    {},
            }
            for p in PHASES
        }

        # Data global yang dikumpulkan wizard
        self.config: Dict[str, Any] = {
            # System
            "hostname":          "",
            "timezone":          "Asia/Jakarta",
            "locale":            "en_US.UTF-8",
            "ssh_hardening":     False,

            # Network
            "interface":         "",
            "static_ip":         "",
            "gateway":           "",
            "dns_servers":       ["1.1.1.1", "1.0.0.1"],
            "doh_provider":      "cloudflare",
            "doh_enabled":       False,
            "ufw_enabled":       False,
            "mdns_enabled":      False,

            # Storage
            "media_disk":        "",
            "media_mount":       "/mnt/media",
            "media_uuid":        "",
            "storage_mode":      "wizard",
            "folder_structure":  "default",

            # Docker
            "puid":              "1000",
            "pgid":              "1000",
            "docker_network":    "bridge",

            # Stack selections
            "media_server":      "",
            "downloader":        "",
            "arr_suite":         [],
            "indexer":           "",
            "request_manager":   "",
            "reverse_proxy":     "",
            "dashboard":         "",
            "monitoring":        [],
            "dns_adblock":       "",

            # Remote access
            "tailscale_enabled":     False,
            "tailscale_authkey":     "",
            "cloudflare_enabled":    False,
            "cloudflare_token":      "",
            "cloudflare_domain":     "",
            "cloudflare_subdomains": {},

            # SSH autostart
            "ssh_autostart": False,
        }

    # ── State operations ───────────────────────────────────────────────────────

    def set_phase_status(self, phase_id: str, status: str):
        if phase_id in self.phases:
            self.phases[phase_id]["status"] = status
            self.updated_at = datetime.now().isoformat()

    def set_phase_data(self, phase_id: str, key: str, value: Any):
        if phase_id in self.phases:
            self.phases[phase_id]["data"][key] = value
            self.updated_at = datetime.now().isoformat()

    def get_phase_data(self, phase_id: str, key: str, fallback=None):
        return self.phases.get(phase_id, {}).get("data", {}).get(key, fallback)

    def skip_phase(self, phase_id: str):
        if phase_id in self.phases:
            self.phases[phase_id]["status"]  = STATUS_SKIPPED
            self.phases[phase_id]["skipped"] = True
            self.updated_at = datetime.now().isoformat()

    def is_phase_done(self, phase_id: str) -> bool:
        s = self.phases.get(phase_id, {}).get("status", STATUS_PENDING)
        return s in (STATUS_DONE, STATUS_SKIPPED)

    def next_pending_phase(self) -> Optional[str]:
        for p in PHASES:
            if not self.is_phase_done(p["id"]):
                return p["id"]
        return None

    def all_done(self) -> bool:
        return all(self.is_phase_done(p["id"]) for p in PHASES)

    def done_phases(self) -> List[str]:
        return [p["id"] for p in PHASES if self.is_phase_done(p["id"])]

    def pending_phases(self) -> List[str]:
        return [p["id"] for p in PHASES if not self.is_phase_done(p["id"])]

    # ── Persistence ────────────────────────────────────────────────────────────

    def save(self):
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        data = {
            "version":       self.version,
            "created_at":    self.created_at,
            "updated_at":    self.updated_at,
            "current_phase": self.current_phase,
            "completed":     self.completed,
            "phases":        self.phases,
            "config":        self.config,
        }
        BOOTSTRAP_STATE_FILE.write_text(
            json.dumps(data, indent=2, ensure_ascii=False),
            encoding="utf-8"
        )

    @classmethod
    def load(cls) -> "BootstrapState":
        state = cls()
        if BOOTSTRAP_STATE_FILE.exists():
            try:
                data = json.loads(BOOTSTRAP_STATE_FILE.read_text(encoding="utf-8"))
                state.version       = data.get("version", BOOTSTRAP_VERSION)
                state.created_at    = data.get("created_at", state.created_at)
                state.updated_at    = data.get("updated_at", state.updated_at)
                state.current_phase = data.get("current_phase")
                state.completed     = data.get("completed", False)
                saved_cfg = data.get("config", {})
                state.config = {**state.config, **saved_cfg}
                for pid, pdata in data.get("phases", {}).items():
                    if pid in state.phases:
                        state.phases[pid].update(pdata)
            except Exception:
                pass
        return state

    @classmethod
    def reset(cls) -> "BootstrapState":
        if BOOTSTRAP_STATE_FILE.exists():
            BOOTSTRAP_STATE_FILE.unlink()
        return cls()

    @staticmethod
    def exists() -> bool:
        return BOOTSTRAP_STATE_FILE.exists()


# ══════════════════════════════════════════════════════════════════════════════
#  SYSTEM INFO
# ══════════════════════════════════════════════════════════════════════════════

def get_system_info() -> Dict[str, str]:
    """Kumpulkan info sistem untuk pre-flight check."""
    def q(cmd, fallback="?"):
        out, _, code = run_cmd(cmd, timeout=5)
        return out.strip() if code == 0 and out.strip() else fallback

    return {
        "hostname":     q("hostname"),
        "os":           q("lsb_release -ds 2>/dev/null", "Linux"),
        "kernel":       q("uname -r"),
        "arch":         q("uname -m"),
        "ram_gb":       q("free -g 2>/dev/null | awk '/^Mem:/{print $2}'", "?"),
        "python":       q("python3 --version 2>/dev/null", "tidak ada"),
        "docker":       q("docker --version 2>/dev/null", "belum install"),
        "docker_group": "ya" if _user_in_docker_group() else "tidak",
        "internet":     "ok" if _check_internet() else "tidak ada",
        "sudo":         "ya" if _can_sudo() else "tidak (perlu!)",
        "timezone":     q("timedatectl show --property=Timezone --value 2>/dev/null || cat /etc/timezone 2>/dev/null", "?"),
    }


def _user_in_docker_group() -> bool:
    user = get_current_user()
    out, _, _ = run_cmd(f"groups {user} 2>/dev/null")
    return "docker" in out.split()


def _check_internet() -> bool:
    _, _, code = run_cmd("ping -c 1 -W 3 1.1.1.1 2>/dev/null")
    return code == 0


def _can_sudo() -> bool:
    _, _, code = run_cmd("sudo -n true 2>/dev/null")
    return code == 0


# ══════════════════════════════════════════════════════════════════════════════
#  NETWORK HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def get_network_interfaces() -> List[Dict]:
    """Ambil list interface jaringan aktif (bukan loopback)."""
    out, _, code = run_cmd("ip -br addr show 2>/dev/null")
    interfaces = []
    if code != 0:
        return interfaces
    for line in out.splitlines():
        parts = line.split()
        if len(parts) < 2:
            continue
        name  = parts[0]
        state = parts[1]
        ip    = parts[2] if len(parts) > 2 else ""
        if name == "lo":
            continue
        interfaces.append({
            "name":  name,
            "state": state,
            "ip":    ip,
            "up":    state.upper() == "UP",
        })
    return interfaces


def get_current_ip(interface: str) -> str:
    out, _, _ = run_cmd(
        f"ip addr show {interface} 2>/dev/null | grep 'inet ' | awk '{{print $2}}'"
    )
    return out.strip()


def get_default_gateway() -> str:
    out, _, _ = run_cmd("ip route 2>/dev/null | grep default | awk '{print $3}' | head -1")
    return out.strip()


def validate_ip_cidr(ip_cidr: str) -> bool:
    if not re.match(r"^\d{1,3}(\.\d{1,3}){3}/\d{1,2}$", ip_cidr):
        return False
    ip_part, cidr_part = ip_cidr.split("/")
    if not (0 <= int(cidr_part) <= 32):
        return False
    for octet in ip_part.split("."):
        if not (0 <= int(octet) <= 255):
            return False
    return True


def validate_ip(ip: str) -> bool:
    if not re.match(r"^\d{1,3}(\.\d{1,3}){3}$", ip):
        return False
    for octet in ip.split("."):
        if not (0 <= int(octet) <= 255):
            return False
    return True


def get_netplan_files() -> List[str]:
    out, _, _ = run_cmd("ls /etc/netplan/*.yaml /etc/netplan/*.yml 2>/dev/null")
    return [f for f in out.splitlines() if f.strip()]


# ══════════════════════════════════════════════════════════════════════════════
#  STORAGE HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def get_available_disks() -> List[Dict]:
    """Ambil list disk yang tersedia."""
    out, _, code = run_cmd(
        "lsblk -o NAME,SIZE,TYPE,FSTYPE,MOUNTPOINT,VENDOR,MODEL "
        "--noheadings 2>/dev/null"
    )
    disks = []
    if code != 0:
        return disks
    for line in out.splitlines():
        parts = line.split(None, 6)
        if len(parts) < 3:
            continue
        dtype = parts[2].strip()
        if dtype != "disk":
            continue
        name = parts[0].strip()
        disks.append({
            "name":       name,
            "path":       f"/dev/{name}",
            "size":       parts[1].strip() if len(parts) > 1 else "?",
            "fstype":     parts[3].strip() if len(parts) > 3 else "",
            "mountpoint": parts[4].strip() if len(parts) > 4 else "",
            "vendor":     parts[5].strip() if len(parts) > 5 else "",
            "model":      parts[6].strip() if len(parts) > 6 else "",
            "is_os_disk": _is_os_disk(name),
        })
    return disks


def _is_os_disk(disk_name: str) -> bool:
    out, _, _ = run_cmd(f"lsblk -no MOUNTPOINT /dev/{disk_name} 2>/dev/null")
    return any(m.strip() == "/" for m in out.splitlines())


def get_disk_uuid(partition: str) -> str:
    out, _, _ = run_cmd(f"blkid -s UUID -o value {partition} 2>/dev/null")
    return out.strip()


# ══════════════════════════════════════════════════════════════════════════════
#  DOCKER HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def get_user_ids() -> Dict[str, str]:
    user = get_current_user()
    puid, _, _ = run_cmd(f"id -u {user} 2>/dev/null")
    pgid, _, _ = run_cmd(f"id -g {user} 2>/dev/null")
    return {
        "user": user,
        "puid": puid.strip() or "1000",
        "pgid": pgid.strip() or "1000",
    }


def is_docker_installed() -> bool:
    return shutil.which("docker") is not None


def is_docker_running() -> bool:
    _, _, code = run_cmd("docker info >/dev/null 2>&1")
    return code == 0


# ══════════════════════════════════════════════════════════════════════════════
#  STACK OPTIONS
# ══════════════════════════════════════════════════════════════════════════════

def get_stack_options() -> Dict[str, List[Dict]]:
    """Return semua pilihan stack yang tersedia."""
    return {
        "media_server": [
            {"id": "jellyfin",  "name": "Jellyfin",
             "desc": "Open source, gratis, no akun. Recommended.",
             "recommended": True},
            {"id": "plex",      "name": "Plex",
             "desc": "Polished UI, butuh akun Plex (gratis)"},
            {"id": "emby",      "name": "Emby",
             "desc": "Mirip Plex, ada versi gratis & premium"},
            {"id": "none",      "name": "Tidak perlu",
             "desc": "Skip media server"},
        ],
        "downloader": [
            {"id": "qbittorrent", "name": "qBittorrent",
             "desc": "Ringan, web UI bersih. Recommended.",
             "recommended": True},
            {"id": "deluge",    "name": "Deluge",
             "desc": "Ringan, bisa dikembangkan dengan plugin"},
            {"id": "sabnzbd",   "name": "SABnzbd",
             "desc": "Usenet downloader"},
            {"id": "none",      "name": "Tidak perlu",
             "desc": "Skip downloader"},
        ],
        "arr_suite": [
            {"id": "radarr",  "name": "Radarr",  "desc": "Manajemen & download film otomatis"},
            {"id": "sonarr",  "name": "Sonarr",  "desc": "Manajemen & download series TV"},
            {"id": "lidarr",  "name": "Lidarr",  "desc": "Manajemen & download musik"},
            {"id": "bazarr",  "name": "Bazarr",  "desc": "Manajemen subtitle otomatis"},
        ],
        "indexer": [
            {"id": "prowlarr", "name": "Prowlarr",
             "desc": "Indexer manager terpadu (recommended)",
             "recommended": True},
            {"id": "jackett",  "name": "Jackett",
             "desc": "Indexer proxy klasik"},
            {"id": "none",     "name": "Tidak perlu",
             "desc": "Skip indexer"},
        ],
        "request_manager": [
            {"id": "jellyseerr", "name": "Jellyseerr",
             "desc": "Request manager untuk Jellyfin. Recommended.",
             "recommended": True},
            {"id": "overseerr",  "name": "Overseerr",
             "desc": "Request manager untuk Plex"},
            {"id": "none",       "name": "Tidak perlu",
             "desc": "Skip"},
        ],
        "reverse_proxy": [
            {"id": "nginxproxymanager", "name": "Nginx Proxy Manager",
             "desc": "GUI-based, mudah untuk pemula. Recommended.",
             "recommended": True},
            {"id": "caddy",     "name": "Caddy",
             "desc": "Auto HTTPS, konfigurasi via Caddyfile"},
            {"id": "none",      "name": "Tidak perlu",
             "desc": "Akses langsung via IP:port"},
        ],
        "dashboard": [
            {"id": "homarr",   "name": "Homarr",
             "desc": "Dashboard modern dengan widgets & integrasi Docker",
             "recommended": True},
            {"id": "heimdall", "name": "Heimdall",
             "desc": "Dashboard simpel, icon-based"},
            {"id": "none",     "name": "Tidak perlu",
             "desc": "Skip dashboard"},
        ],
        "monitoring": [
            {"id": "portainer",  "name": "Portainer",
             "desc": "Docker management via web browser"},
            {"id": "watchtower", "name": "Watchtower",
             "desc": "Auto-update container images secara terjadwal"},
        ],
        "dns_adblock": [
            {"id": "adguardhome", "name": "AdGuard Home",
             "desc": "DNS + ad blocking, UI modern. Recommended.",
             "recommended": True},
            {"id": "pihole",  "name": "Pi-hole",
             "desc": "DNS + ad blocking, solusi klasik"},
            {"id": "none",    "name": "Tidak perlu",
             "desc": "Skip DNS/adblock"},
        ],
    }


# ══════════════════════════════════════════════════════════════════════════════
#  PORT CONFLICT DETECTION
# ══════════════════════════════════════════════════════════════════════════════

SERVICE_PORTS: Dict[str, List[int]] = {
    "jellyfin":          [8096, 8920, 7359, 1900],
    "plex":              [32400, 32469, 1900, 5353],
    "emby":              [8096, 8920],
    "qbittorrent":       [8080, 6881],
    "deluge":            [8112, 6881],
    "sabnzbd":           [8080],
    "radarr":            [7878],
    "sonarr":            [8989],
    "lidarr":            [8686],
    "bazarr":            [6767],
    "prowlarr":          [9696],
    "jackett":           [9117],
    "jellyseerr":        [5055],
    "overseerr":         [5055],
    "nginxproxymanager": [80, 443, 81],
    "caddy":             [80, 443, 2019],
    "homarr":            [7575],
    "heimdall":          [80, 443],
    "portainer":         [9000, 9443],
    "watchtower":        [],
    "adguardhome":       [3000, 53],
    "pihole":            [80, 53],
    "cloudflared":       [],
}


def check_port_conflicts(services: List[str]) -> List[Dict]:
    """
    Cek konflik port antar service yang dipilih + port sistem yang sudah dipakai.
    Return list of conflict dicts.
    """
    conflicts = []
    port_map: Dict[int, List[str]] = {}
    for svc in services:
        for port in SERVICE_PORTS.get(svc, []):
            port_map.setdefault(port, []).append(svc)

    out, _, _ = run_cmd("ss -tlnp 2>/dev/null | grep LISTEN | awk '{print $4}'")
    used_ports = set()
    for addr in out.splitlines():
        try:
            used_ports.add(int(addr.rsplit(":", 1)[-1]))
        except (ValueError, IndexError):
            pass

    for port, svcs in port_map.items():
        if len(svcs) > 1:
            conflicts.append({
                "type":     "service_conflict",
                "port":     port,
                "services": svcs,
                "message":  f"Port {port} dipakai oleh: {', '.join(svcs)}",
            })

    for port, svcs in port_map.items():
        if port in used_ports and len(svcs) == 1:
            conflicts.append({
                "type":     "system_conflict",
                "port":     port,
                "services": svcs,
                "message":  f"Port {port} ({svcs[0]}) sudah dipakai sistem",
            })

    return conflicts


# ══════════════════════════════════════════════════════════════════════════════
#  COMPOSE GENERATOR
# ══════════════════════════════════════════════════════════════════════════════

def generate_compose_yaml(state: "BootstrapState") -> str:
    """
    Generate docker-compose.yml berdasarkan pilihan stack di state.
    Return string YAML yang siap ditulis ke file.
    """
    cfg   = state.config
    puid  = cfg.get("puid", "1000")
    pgid  = cfg.get("pgid", "1000")
    tz    = cfg.get("timezone", "Asia/Jakarta")
    media = cfg.get("media_mount", "/mnt/media")

    services = {}

    ms = cfg.get("media_server", "")
    if ms == "jellyfin":  services["jellyfin"]  = _svc_jellyfin(puid, pgid, tz, media)
    elif ms == "plex":    services["plex"]      = _svc_plex(puid, pgid, tz, media)
    elif ms == "emby":    services["emby"]      = _svc_emby(puid, pgid, tz, media)

    dl = cfg.get("downloader", "")
    if dl == "qbittorrent": services["qbittorrent"] = _svc_qbittorrent(puid, pgid, tz, media)
    elif dl == "deluge":    services["deluge"]       = _svc_deluge(puid, pgid, tz, media)
    elif dl == "sabnzbd":   services["sabnzbd"]      = _svc_sabnzbd(puid, pgid, tz, media)

    for arr in cfg.get("arr_suite", []):
        fn = {"radarr": _svc_radarr, "sonarr": _svc_sonarr,
              "lidarr": _svc_lidarr, "bazarr": _svc_bazarr}.get(arr)
        if fn: services[arr] = fn(puid, pgid, tz, media)

    idx = cfg.get("indexer", "")
    if idx == "prowlarr":  services["prowlarr"] = _svc_prowlarr(puid, pgid, tz)
    elif idx == "jackett": services["jackett"]  = _svc_jackett(puid, pgid, tz)

    rm = cfg.get("request_manager", "")
    if rm == "jellyseerr":  services["jellyseerr"] = _svc_jellyseerr(tz)
    elif rm == "overseerr": services["overseerr"]  = _svc_overseerr(puid, pgid, tz)

    rp = cfg.get("reverse_proxy", "")
    if rp == "nginxproxymanager": services["nginxproxymanager"] = _svc_npm()
    elif rp == "caddy":           services["caddy"]             = _svc_caddy()

    dash = cfg.get("dashboard", "")
    if dash == "homarr":   services["homarr"]   = _svc_homarr()
    elif dash == "heimdall": services["heimdall"] = _svc_heimdall(puid, pgid, tz)

    for mon in cfg.get("monitoring", []):
        if mon == "portainer":  services["portainer"]  = _svc_portainer()
        elif mon == "watchtower": services["watchtower"] = _svc_watchtower()

    dns = cfg.get("dns_adblock", "")
    if dns == "adguardhome": services["adguardhome"] = _svc_adguardhome()
    elif dns == "pihole":    services["pihole"]      = _svc_pihole(tz)

    if cfg.get("cloudflare_enabled"):
        services["cloudflared"] = _svc_cloudflared(cfg.get("cloudflare_token", ""))

    return _render_compose(services)


def _render_compose(services: Dict) -> str:
    lines = [
        "# docker-compose.yml",
        f"# Generated by Dockman Bootstrap Wizard v{BOOTSTRAP_VERSION}",
        f"# {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "services:",
    ]
    for svc_name, svc_def in services.items():
        lines.append(f"  {svc_name}:")
        _yaml_dict(lines, svc_def, indent=4)
        lines.append("")
    return "\n".join(lines)


def _yaml_dict(lines: List[str], d: Dict, indent: int):
    pad = " " * indent
    for k, v in d.items():
        if isinstance(v, dict):
            lines.append(f"{pad}{k}:")
            _yaml_dict(lines, v, indent + 2)
        elif isinstance(v, list):
            if not v:
                lines.append(f"{pad}{k}: []")
            else:
                lines.append(f"{pad}{k}:")
                for item in v:
                    lines.append(f"{pad}  - {item}")
        elif isinstance(v, bool):
            lines.append(f"{pad}{k}: {'true' if v else 'false'}")
        elif v is None:
            lines.append(f"{pad}{k}:")
        else:
            sv = str(v)
            if any(c in sv for c in ':#{}[],&*?|-<>=!%@\\'):
                sv = f'"{sv}"'
            lines.append(f"{pad}{k}: {sv}")


# ── Helpers ────────────────────────────────────────────────────────────────────

def _lsio(img):       return f"lscr.io/linuxserver/{img}:latest"
def _cfg_vol(name):   return f"/opt/dockman/config/{name}:/config"
def _env(p, g, tz):   return [f"PUID={p}", f"PGID={g}", f"TZ={tz}"]
def _base_svc(name):  return {"container_name": name, "restart": "unless-stopped"}


def _svc_jellyfin(p, g, tz, media):
    s = _base_svc("jellyfin")
    s["image"] = _lsio("jellyfin")
    s["environment"] = _env(p, g, tz)
    s["volumes"] = [f"{media}/config/jellyfin:/config",
                    f"{media}/movies:/data/movies", f"{media}/tv:/data/tv"]
    s["ports"] = ["8096:8096", "8920:8920"]
    return s

def _svc_plex(p, g, tz, media):
    s = _base_svc("plex")
    s["image"] = _lsio("plex")
    s["network_mode"] = "host"
    s["environment"] = _env(p, g, tz) + ["VERSION=docker"]
    s["volumes"] = [f"{media}/config/plex:/config",
                    f"{media}/movies:/movies", f"{media}/tv:/tv"]
    return s

def _svc_emby(p, g, tz, media):
    s = _base_svc("emby")
    s["image"] = _lsio("emby")
    s["environment"] = _env(p, g, tz)
    s["volumes"] = [f"{media}/config/emby:/config",
                    f"{media}/movies:/data/movies", f"{media}/tv:/data/tv"]
    s["ports"] = ["8096:8096", "8920:8920"]
    return s

def _svc_qbittorrent(p, g, tz, media):
    s = _base_svc("qbittorrent")
    s["image"] = _lsio("qbittorrent")
    s["environment"] = _env(p, g, tz) + ["WEBUI_PORT=8080"]
    s["volumes"] = [f"{media}/config/qbittorrent:/config", f"{media}/downloads:/downloads"]
    s["ports"] = ["8080:8080", "6881:6881", "6881:6881/udp"]
    return s

def _svc_deluge(p, g, tz, media):
    s = _base_svc("deluge")
    s["image"] = _lsio("deluge")
    s["environment"] = _env(p, g, tz) + ["DELUGE_LOGLEVEL=error"]
    s["volumes"] = [f"{media}/config/deluge:/config", f"{media}/downloads:/downloads"]
    s["ports"] = ["8112:8112", "6881:6881", "6881:6881/udp"]
    return s

def _svc_sabnzbd(p, g, tz, media):
    s = _base_svc("sabnzbd")
    s["image"] = _lsio("sabnzbd")
    s["environment"] = _env(p, g, tz)
    s["volumes"] = [f"{media}/config/sabnzbd:/config", f"{media}/downloads:/downloads"]
    s["ports"] = ["8080:8080"]
    return s

def _arr(name, p, g, tz, media, port, data_dir, data_name):
    s = _base_svc(name)
    s["image"] = _lsio(name)
    s["environment"] = _env(p, g, tz)
    s["volumes"] = [f"{media}/config/{name}:/config",
                    f"{media}/{data_dir}:/{data_name}",
                    f"{media}/downloads:/downloads"]
    s["ports"] = [f"{port}:{port}"]
    return s

def _svc_radarr(p, g, tz, media):  return _arr("radarr", p, g, tz, media, 7878, "movies", "movies")
def _svc_sonarr(p, g, tz, media):  return _arr("sonarr", p, g, tz, media, 8989, "tv", "tv")
def _svc_lidarr(p, g, tz, media):  return _arr("lidarr", p, g, tz, media, 8686, "music", "music")
def _svc_bazarr(p, g, tz, media):  return _arr("bazarr", p, g, tz, media, 6767, "movies", "movies")

def _svc_prowlarr(p, g, tz):
    s = _base_svc("prowlarr")
    s["image"] = _lsio("prowlarr")
    s["environment"] = _env(p, g, tz)
    s["volumes"] = [_cfg_vol("prowlarr")]
    s["ports"] = ["9696:9696"]
    return s

def _svc_jackett(p, g, tz):
    s = _base_svc("jackett")
    s["image"] = _lsio("jackett")
    s["environment"] = _env(p, g, tz) + ["AUTO_UPDATE=true"]
    s["volumes"] = [_cfg_vol("jackett")]
    s["ports"] = ["9117:9117"]
    return s

def _svc_jellyseerr(tz):
    s = _base_svc("jellyseerr")
    s["image"] = "fallenbagel/jellyseerr:latest"
    s["environment"] = [f"TZ={tz}"]
    s["volumes"] = ["/opt/dockman/config/jellyseerr:/app/config"]
    s["ports"] = ["5055:5055"]
    return s

def _svc_overseerr(p, g, tz):
    s = _base_svc("overseerr")
    s["image"] = _lsio("overseerr")
    s["environment"] = _env(p, g, tz)
    s["volumes"] = [_cfg_vol("overseerr")]
    s["ports"] = ["5055:5055"]
    return s

def _svc_npm():
    s = _base_svc("nginxproxymanager")
    s["image"] = "jc21/nginx-proxy-manager:latest"
    s["ports"] = ["80:80", "443:443", "81:81"]
    s["volumes"] = ["/opt/dockman/config/npm/data:/data",
                    "/opt/dockman/config/npm/letsencrypt:/etc/letsencrypt"]
    return s

def _svc_caddy():
    s = _base_svc("caddy")
    s["image"] = "caddy:latest"
    s["ports"] = ["80:80", "443:443", "2019:2019"]
    s["volumes"] = ["/opt/dockman/config/caddy/Caddyfile:/etc/caddy/Caddyfile",
                    "/opt/dockman/config/caddy/data:/data",
                    "/opt/dockman/config/caddy/config:/config"]
    return s

def _svc_homarr():
    s = _base_svc("homarr")
    s["image"] = "ghcr.io/ajnart/homarr:latest"
    s["volumes"] = ["/var/run/docker.sock:/var/run/docker.sock",
                    "/opt/dockman/config/homarr:/app/data/configs"]
    s["ports"] = ["7575:7575"]
    return s

def _svc_heimdall(p, g, tz):
    s = _base_svc("heimdall")
    s["image"] = _lsio("heimdall")
    s["environment"] = _env(p, g, tz)
    s["volumes"] = [_cfg_vol("heimdall")]
    s["ports"] = ["80:80", "443:443"]
    return s

def _svc_portainer():
    s = _base_svc("portainer")
    s["image"] = "portainer/portainer-ce:latest"
    s["volumes"] = ["/var/run/docker.sock:/var/run/docker.sock",
                    "/opt/dockman/config/portainer:/data"]
    s["ports"] = ["9000:9000", "9443:9443"]
    return s

def _svc_watchtower():
    s = _base_svc("watchtower")
    s["image"] = "containrrr/watchtower:latest"
    s["volumes"] = ["/var/run/docker.sock:/var/run/docker.sock"]
    s["environment"] = ["WATCHTOWER_CLEANUP=true", "WATCHTOWER_SCHEDULE=0 0 4 * * *"]
    return s

def _svc_adguardhome():
    s = _base_svc("adguardhome")
    s["image"] = "adguard/adguardhome:latest"
    s["volumes"] = ["/opt/dockman/config/adguardhome/work:/opt/adguardhome/work",
                    "/opt/dockman/config/adguardhome/conf:/opt/adguardhome/conf"]
    s["ports"] = ["3000:3000", "53:53/tcp", "53:53/udp"]
    return s

def _svc_pihole(tz):
    s = _base_svc("pihole")
    s["image"] = "pihole/pihole:latest"
    s["environment"] = [f"TZ={tz}", "WEBPASSWORD=changeme"]
    s["volumes"] = ["/opt/dockman/config/pihole/etc:/etc/pihole",
                    "/opt/dockman/config/pihole/dnsmasq:/etc/dnsmasq.d"]
    s["ports"] = ["53:53/tcp", "53:53/udp", "80:80"]
    return s

def _svc_cloudflared(token: str):
    s = _base_svc("cloudflared")
    s["image"] = "cloudflare/cloudflared:latest"
    s["command"] = f"tunnel --no-autoupdate run --token {token}"
    return s


# ══════════════════════════════════════════════════════════════════════════════
#  FOLDER STRUCTURE
# ══════════════════════════════════════════════════════════════════════════════

DEFAULT_FOLDERS = [
    "movies", "tv", "music",
    "downloads", "downloads/complete",
    "downloads/complete/radarr", "downloads/complete/sonarr",
    "downloads/incomplete",
    "config",
]


def create_folder_structure(base_path: str, folders: List[str] = None) -> List[str]:
    """Buat folder structure di base_path. Return list folder yang dibuat."""
    folders = folders or DEFAULT_FOLDERS
    created = []
    base    = Path(base_path)
    for f in folders:
        full = base / f
        try:
            full.mkdir(parents=True, exist_ok=True)
            created.append(str(full))
        except Exception:
            pass
    return created


# ══════════════════════════════════════════════════════════════════════════════
#  ACCESS SUMMARY
# ══════════════════════════════════════════════════════════════════════════════

def generate_access_summary(state: "BootstrapState") -> List[Dict]:
    """Generate daftar URL akses setelah deploy."""
    cfg      = state.config
    host_ip  = _get_local_ip()
    hostname = cfg.get("hostname", socket.gethostname())
    mdns     = cfg.get("mdns_enabled", False)
    summary  = []

    def add(service, port, path="/", note=""):
        entry = {"service": service, "url": f"http://{host_ip}:{port}{path}", "note": note}
        if mdns:
            entry["url_mdns"] = f"http://{hostname}.local:{port}{path}"
        summary.append(entry)

    port_map = {
        "jellyfin":    ("Jellyfin",    8096, "/",     "Media streaming"),
        "plex":        ("Plex",         32400, "/web", "Media streaming"),
        "emby":        ("Emby",         8096, "/",     "Media streaming"),
        "qbittorrent": ("qBittorrent",  8080, "/",     "Default: admin/adminadmin"),
        "deluge":      ("Deluge",        8112, "/",     "Default password: deluge"),
        "sabnzbd":     ("SABnzbd",       8080, "/",     ""),
        "radarr":      ("Radarr",        7878, "/",     ""),
        "sonarr":      ("Sonarr",        8989, "/",     ""),
        "lidarr":      ("Lidarr",        8686, "/",     ""),
        "bazarr":      ("Bazarr",        6767, "/",     ""),
        "prowlarr":    ("Prowlarr",      9696, "/",     ""),
        "jackett":     ("Jackett",       9117, "/",     ""),
        "jellyseerr":  ("Jellyseerr",    5055, "/",     ""),
        "overseerr":   ("Overseerr",     5055, "/",     ""),
        "homarr":      ("Homarr",        7575, "/",     ""),
        "portainer":   ("Portainer",     9000, "/",     ""),
        "adguardhome": ("AdGuard Home",  3000, "/",     "Setup awal"),
        "pihole":      ("Pi-hole",       80,   "/admin","Password: changeme"),
    }

    for key in ("media_server", "downloader", "indexer", "request_manager",
                "reverse_proxy", "dashboard", "dns_adblock"):
        val = cfg.get(key, "")
        if val and val != "none" and val in port_map:
            name, port, path, note = port_map[val]
            add(name, port, path, note)

    for val in cfg.get("arr_suite", []):
        if val in port_map:
            name, port, path, note = port_map[val]
            add(name, port, path, note)

    for val in cfg.get("monitoring", []):
        if val in port_map:
            name, port, path, note = port_map[val]
            add(name, port, path, note)

    if cfg.get("reverse_proxy") == "nginxproxymanager":
        add("Nginx Proxy Manager (admin)", 81, "/",
            "Email: admin@example.com / changeme")

    return summary


def _get_local_ip() -> str:
    out, _, _ = run_cmd("hostname -I 2>/dev/null | awk '{print $1}'")
    return out.strip() or "localhost"
