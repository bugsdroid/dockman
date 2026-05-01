"""
ui/wizard.py - First-run setup wizard untuk Dockman
Dijalankan di terminal biasa (bukan curses, bukan Rich)
agar portable dan tidak ada dependency issue.
"""

import shutil
import socket
import subprocess
from pathlib import Path

import core.config as config


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
