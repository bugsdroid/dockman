"""
ui/cli_menu.py - Numbered menu fallback untuk Dockman
Layout 2 kolom seperti screenshot v2.1.x
"""

import os
from pathlib import Path

from core.config import get_compose_file, get_compose_dir, get_compose_cmd
from core.config import get_editor, get, get_current_user, get_doc_output_dir
from core.config import get_hostname, VERSION, APP_NAME, find_compose_files
from core.config import set_value, CONFIG_FILE
from core.config import load as config_load
from core.utils import run_cmd, run_interactive, sanitize_input, check_tool
from core.docker import get_containers, get_container_logs, get_container_image
from core.docker import get_images, get_dangling_images, remove_image, get_orphan_volumes
from core.docker import get_disk_usage, get_stats_once, screen_kill, get_screens
from core.docker import container_action, get_container_inspect
import ui.rich_ui as rich_ui


def pick_container(show_all: bool = False):
    """Tampilkan list container, user pilih nomor."""
    containers = docker_get_all() if show_all else [
        c for c in docker_get_all() if c["running"]
    ]
    if not containers and not show_all:
        containers = docker_get_all()

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


def docker_get_all():
    return get_containers()


def run_menu():
    """Main loop menu numbered - layout 2 kolom."""

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

        # ── Header ──────────────────────────────────────────────────────────
        print()
        print(f"  \033[1;36mDOCKMAN v{VERSION}  \u2014  {hostname}  \u2014  {cur_user}\033[0m")
        print()

        # ── 2-column menu layout ─────────────────────────────────────────────
        COL_W = 30  # lebar kolom kiri

        def section_header(left, right=""):
            import re
            l = f"\033[1;36m{left}\033[0m"
            r = f"\033[1;36m{right}\033[0m" if right else ""
            l_plain = re.sub(r'\033\[[0-9;]*m', '', l)
            pad = max(0, COL_W - len(l_plain))
            print(f"  {l}{' ' * pad}  {r}")

        def item(left_num, left_text, right_num="", right_text=""):
            if left_num:
                l = f"{left_num}. {left_text}"
            else:
                l = ""
            r = f"{right_num}. {right_text}" if right_num else ""
            pad = max(0, COL_W - len(l))
            print(f"  {l}{' ' * pad}  {r}")

        # CONTAINER  |  MAINTENANCE
        section_header("CONTAINER", "MAINTENANCE")
        item("1",  "List semua container",       "14", "Prune image")
        item("2",  "Update image (1 container)", "15", "Prune volumes")
        item("3",  "Update SEMUA image",          "16", "Prune TOTAL")
        item("4",  "Restart container",           "17", "Disk usage")
        item("5",  "Restart SEMUA")
        item("6",  "Docker Stats")
        item("7",  "Lihat logs")
        item("8",  "Exec shell")
        print()

        # COMPOSE  |  EXTRAS
        section_header("COMPOSE", "EXTRAS")
        item("9",  "Compose UP",                 "18", "Lihat alias")
        item("10", "Compose DOWN",               "19", "Grep alias")
        item("11", "Lihat compose.yml",          "20", "Edit bashrc")
        item("12", "Edit compose.yml",           "21", "Lihat cron")
        item("13", "Backup compose.yml",         "22", "Edit cron")
        item("",   "",                           "23", f"Rclone {remote_name}.nz")
        item("",   "",                           "24", "Server report")
        print()

        # GNU SCREEN  |  SETTINGS
        section_header("GNU SCREEN", "SETTINGS")
        item("25", "List screen session",        "31", "Lihat konfigurasi")
        item("26", "Attach ke session",          "32", "Wizard setup ulang")
        item("27", "Kill 1 session")
        item("28", "Kill SEMUA session")
        item("29", "Buat session baru")
        item("30", "Jalankan cmd background")
        print()

        print(f"  \033[2m{'-' * 62}\033[0m")
        print(f"  \033[1;31m0. Keluar\033[0m")
        print()
        choice = input("  Pilih: ").strip()

        if choice == "0":
            break

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
            disk = get_disk_usage()
            rich_ui.show_disk_usage(disk)

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

        elif choice == "25":
            sessions = get_screens()
            rich_ui.show_screen_sessions(sessions)

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

        elif choice == "31":
            cfg = config_load()
            print(f"\n  Config: {CONFIG_FILE}\n")
            for section in cfg.sections():
                print(f"  [{section}]")
                for k, v in cfg.items(section):
                    print(f"    {k} = {v}")
                print()

        elif choice == "32":
            from ui.wizard import run_wizard
            run_wizard()

        else:
            rich_ui.cli_error(f"Pilihan tidak valid: {choice}")

        try:
            input("\n  Tekan Enter untuk lanjut...")
        except (EOFError, KeyboardInterrupt):
            break
