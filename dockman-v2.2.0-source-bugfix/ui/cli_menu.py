"""
ui/cli_menu.py - Fallback menu numbered untuk --menu mode
Output menggunakan Rich. Navigasi via angka di terminal.
"""

import os
import subprocess
from datetime import datetime
from pathlib import Path

import core.config as config
import core.docker as docker
from core.utils import run_interactive, sanitize_input, check_tool, run_cmd
import ui.rich_ui as rich_ui


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
            from ui.wizard import run_wizard
            run_wizard()

        else:
            rich_ui.cli_error(f"Pilihan tidak valid: {choice}")

        try:
            input("\n  Tekan Enter untuk lanjut...")
        except (EOFError, KeyboardInterrupt):
            break
