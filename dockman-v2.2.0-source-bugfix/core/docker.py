"""
core/docker.py - Docker data layer untuk Dockman
Semua docker command di sini. Tidak ada UI dependency.
"""

from typing import List, Dict, Optional
from core.utils import run_cmd, DockerError
from core.config import get_compose_dir, get_compose_cmd, get_compose_file


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
