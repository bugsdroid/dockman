"""
ui/cli_menu.py - Numbered menu fallback untuk Dockman v3.0.0
Layout 3 kolom: CONTAINER|COMPOSE|MAINTENANCE dan GNU SCREEN|EXTRAS|SETTINGS
Tambahan: BOOTSTRAP WIZARD (menu 33 & 34)

Note v3: TUI mode (curses) dihapus. Menu ini adalah UI utama.
"""

import os
from pathlib import Path

from core.config import get_compose_file, get_compose_dir, get_compose_cmd
from core.config import get_editor, get, get_current_user, get_doc_output_dir
from core.config import get_hostname, VERSION, APP_NAME, find_compose_files
from core.config import set_value, CONFIG_FILE
from core.config import load
from core.utils import run_cmd, run_interactive, sanitize_input, check_tool
from core.docker import get_containers, get_container_logs, get_container_image
from core.docker import get_images, get_dangling_images, remove_image, get_orphan_volumes
from core.docker import get_disk_usage, get_stats_once, screen_kill, get_screens
from core.docker import container_action, get_container_inspect
import ui.rich_ui as rich_ui


def pick_container(show_all: bool = False):
    """Tampilkan list container, user pilih nomor."""
    containers = get_containers() if show_all else [
        c for c in get_containers() if c["running"]
    ]
    if not containers and not show_all:
        containers = get_containers()
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
    """Main loop menu numbered - layout 3 kolom."""

    while True:
        compose_file = get_compose_file()
        compose_dir  = get_compose_dir()
        compose_cmd  = get_compose_cmd()
        editor       = get_editor()
        alias_file   = get("alias", "file", str(Path.home() / ".bashrc"))
        remote_name  = get("rclone", "remote_name", "mega")
        remote_path  = get("rclone", "remote_path", "film")
        dest_radarr  = get("rclone", "dest_radarr",
                           "/mnt/media/downloads/complete/radarr")
        cur_user     = get_current_user()
        hostname     = get_hostname()
        doc_dir      = get_doc_output_dir()

        os.system("clear")

        # ── Header ───────────────────────────────────────────────────────────────────────
        print()
        print(f"  \033[1;36mDOCKMAN v{VERSION}  \u2014  {hostname}  \u2014  {cur_user}\033[0m")
        print()

        # ── 3-column layout ────────────────────────────────────────────────────────────
        COL_W = 26
        GAP   = 2

        def row3(c1="", c2="", c3="", hdr=False):
            import re as _re
            CYAN  = "\033[1;36m"
            RESET = "\033[0m"
            if hdr:
                l1 = f"{CYAN}{c1}{RESET}"
                l2 = f"{CYAN}{c2}{RESET}"
                l3 = f"{CYAN}{c3}{RESET}"
            else:
                l1, l2, l3 = c1, c2, c3
            p1 = max(0, COL_W - len(_re.sub(r'\033\[[0-9;]*m', '', l1)))
            p2 = max(0, COL_W - len(_re.sub(r'\033\[[0-9;]*m', '', l2)))
            print(f"  {l1}{' '*p1}{' '*GAP}{l2}{' '*p2}{' '*GAP}{l3}")

        def mi(n1, t1, n2="", t2="", n3="", t3=""):
            c1 = f"{n1}. {t1}" if n1 else ""
            c2 = f"{n2}. {t2}" if n2 else ""
            c3 = f"{n3}. {t3}" if n3 else ""
            row3(c1, c2, c3)

        # ── Baris 1: CONTAINER | COMPOSE | MAINTENANCE ────────────────────────────
        row3("CONTAINER", "COMPOSE", "MAINTENANCE", hdr=True)
        mi("1",  "List container",    "9",  "Compose UP",     "14", "Prune image")
        mi("2",  "Update image",      "10", "Compose DOWN",   "15", "Prune volumes")
        mi("3",  "Update SEMUA",      "11", "Lihat compose",  "16", "Prune TOTAL")
        mi("4",  "Restart",           "12", "Edit compose",   "17", "Disk usage")
        mi("5",  "Restart SEMUA",     "13", "Backup compose")
        mi("6",  "Docker Stats")
        mi("7",  "Lihat logs")
        mi("8",  "Exec shell")
        print()

        # ── Baris 2: GNU SCREEN | EXTRAS | SETTINGS ─────────────────────────────
        row3("GNU SCREEN", "EXTRAS", "SETTINGS", hdr=True)
        mi("25", "List session",      "18", "Lihat alias",    "31", "Lihat konfigurasi")
        mi("26", "Attach",            "19", "Grep alias",     "32", "Wizard ulang")
        mi("27", "Kill 1 session",    "20", "Edit bashrc")
        mi("28", "Kill SEMUA",        "21", "Lihat cron")
        mi("29", "Buat session",      "22", "Edit cron")
        mi("30", "Cmd background",    "23", f"Rclone {remote_name}.nz")
        mi("",   "",                  "24", "Server report")
        print()

        # ── Bootstrap Wizard ────────────────────────────────────────────────────────
        row3("BOOTSTRAP", "", "", hdr=True)
        mi("33", "Bootstrap Wizard (setup server dari nol)")
        mi("34", "Jalankan ulang phase tertentu (1-7)")
        print()

        print(f"  \033[2m{'\u2500' * 80}\033[0m")
        print(f"  \033[1;31m0. Keluar\033[0m")
        print()
        choice = input("  Pilih: ").strip()

        if choice == "0":
            break

        # ── Container ─────────────────────────────────────────────────────────────────
        elif choice == "1":
            rich_ui.show_containers(get_containers())

        elif choice == "2":
            name = pick_container()
            if name:
                image = get_container_image(name)
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
            stats = get_stats_once()
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
                    logs = get_container_logs(name, tail=int(n))
                    rich_ui.show_logs(name, logs)

        elif choice == "8":
            name = pick_container()
            if name:
                run_interactive(
                    f"docker exec -it {name} bash 2>/dev/null || "
                    f"docker exec -it {name} sh"
                )

        # ── Compose ───────────────────────────────────────────────────────────────────
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
                from datetime import datetime
                ts  = datetime.now().strftime("%Y%m%d_%H%M%S")
                dst = f"{compose_file}.bak_{ts}"
                _, err, code = run_cmd(f"cp '{compose_file}' '{dst}'")
                if code == 0:
                    rich_ui.cli_success(f"Backup: {dst}")
                else:
                    rich_ui.cli_error(f"Gagal: {err}")

        # ── Maintenance ───────────────────────────────────────────────────────────────
        elif choice == "14":
            imgs = get_dangling_images()
            if not imgs:
                rich_ui.cli_info("Tidak ada dangling image.")
            else:
                ok = input(f"  Hapus {len(imgs)} dangling image? (y/N): ")
                if ok.lower() == "y":
                    run_interactive("docker image prune -f")

        elif choice == "15":
            vols = get_orphan_volumes()
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
            rich_ui.show_disk_usage(get_disk_usage())

        # ── Extras ────────────────────────────────────────────────────────────────────
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

        # ── GNU Screen ─────────────────────────────────────────────────────────────────
        elif choice == "25":
            rich_ui.show_screen_sessions(get_screens())

        elif choice in ("26", "27"):
            sessions = get_screens()
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
                                ok2, msg = screen_kill(s["sid"])
                                (rich_ui.cli_success if ok2 else rich_ui.cli_error)(msg)
                    else:
                        rich_ui.cli_error("Nomor tidak valid.")
                except ValueError:
                    rich_ui.cli_info("Dibatalkan.")

        elif choice == "28":
            ok = input("  Kill SEMUA session? (y/N): ")
            if ok.lower() == "y":
                sessions = get_screens()
                failed = [s["name"] for s in sessions
                          if not screen_kill(s["sid"])[0]]
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

        # ── Settings ──────────────────────────────────────────────────────────────────
        elif choice == "31":
            cfg = load()
            print(f"\n  Config: {CONFIG_FILE}\n")
            for section in cfg.sections():
                print(f"  [{section}]")
                for k, v in cfg.items(section):
                    print(f"    {k} = {v}")
                print()

        elif choice == "32":
            from ui.wizard import run_wizard
            run_wizard()

        # ── Bootstrap Wizard ───────────────────────────────────────────────────────────
        elif choice == "33":
            from ui.bootstrap_wizard import run_bootstrap_wizard
            run_bootstrap_wizard()

        elif choice == "34":
            from core.bootstrap import PHASES
            from ui.bootstrap_wizard import run_bootstrap_wizard
            print()
            print(f"  Pilih phase yang ingin dijalankan ulang:")
            print()
            for p in PHASES:
                print(f"  {p['number']}. {p['title']}")
            print()
            raw = input("  Nomor phase (0=batal): ").strip()
            if raw.isdigit() and int(raw) > 0:
                phase_id = None
                for p in PHASES:
                    if p["number"] == int(raw):
                        phase_id = p["id"]
                        break
                if phase_id:
                    run_bootstrap_wizard(phase_id=phase_id)
                else:
                    rich_ui.cli_error(f"Phase {raw} tidak ditemukan. Range: 1-7")

        else:
            rich_ui.cli_error(f"Pilihan tidak valid: {choice}")

        try:
            input("\n  Tekan Enter untuk lanjut...")
        except (EOFError, KeyboardInterrupt):
            break
