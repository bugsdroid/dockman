#!/usr/bin/env python3
"""
main.py - Entry point Dockman v3.0.0
"""

import sys
import os
import time
import traceback

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import core.config as config
from core.utils import check_docker, DockerError
import ui.rich_ui as rich_ui


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
    from ui.curses_ui import init_colors, screen_home, screen_containers

    def tui_main(stdscr):
        stdscr.keypad(True)
        init_colors()
        curses.curs_set(0)
        screen_home(stdscr)
        screen_containers(stdscr)

    curses.wrapper(tui_main)


def run_cli_menu():
    """Jalankan menu numbered 3 kolom (default)."""
    from ui.cli_menu import run_menu
    run_menu()


def run_bootstrap(phase_id: str = None):
    """Jalankan Bootstrap Wizard."""
    from ui.bootstrap_wizard import run_bootstrap_wizard
    run_bootstrap_wizard(phase_id=phase_id)


def run_cli_command(args):
    """CLI command langsung dengan Rich output."""
    import core.docker as docker

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
  {config.APP_NAME} v{config.VERSION} - Docker & Media Server Manager

  USAGE:
    dockman                    Menu numbered 3 kolom (default)
    dockman --tui              TUI mode (Curses interaktif)
    dockman --bootstrap        Bootstrap Wizard (setup server dari nol)
    dockman --bootstrap <n>    Jalankan ulang phase N (1-7)
    dockman --setup            Setup wizard dockman (config dasar)
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

  BOOTSTRAP WIZARD:
    Phase 1 - Persiapan Sistem   (hostname, timezone, update, SSH)
    Phase 2 - Konfigurasi Jaringan (static IP, UFW, mDNS, DoH)
    Phase 3 - Manajemen Storage  (disk, format, mount, folder)
    Phase 4 - Setup Docker       (install, daemon config, network)
    Phase 5 - Pilih Stack        (Jellyfin, qBittorrent, Radarr, dll)
    Phase 6 - Remote Access      (Tailscale, Cloudflare Tunnel)
    Phase 7 - Deploy & Verifikasi

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
        from ui.wizard import run_wizard
        run_wizard()
        sys.exit(0)

    # Bootstrap wizard
    if "--bootstrap" in args:
        idx = args.index("--bootstrap")
        # Cek apakah ada phase number setelah flag
        phase_id = None
        if len(args) > idx + 1:
            phase_arg = args[idx + 1]
            if phase_arg.isdigit():
                phase_num = int(phase_arg)
                from core.bootstrap import PHASES
                for p in PHASES:
                    if p["number"] == phase_num:
                        phase_id = p["id"]
                        break
                if not phase_id:
                    print(f"  Phase {phase_num} tidak ditemukan. Range: 1-7")
                    sys.exit(1)
        run_bootstrap(phase_id=phase_id)
        sys.exit(0)

    # Skip docker check untuk report dan bootstrap
    skip_docker = args and args[0] in ("report",)
    if not skip_docker:
        try:
            check_docker()
        except DockerError as e:
            print(f"\n  ERROR: {e}\n")
            sys.exit(1)

    if config.is_first_run() and not args:
        print(f"\n  Selamat datang di {config.APP_NAME} v{config.VERSION}!")
        print("  Config belum ada. Jalankan setup wizard?\n")
        val = input("  [Y/n]: ").strip()
        if val.lower() != "n":
            from ui.wizard import run_wizard
            run_wizard()
            config.load()
            print()

    CLI_COMMANDS = {"ps", "images", "stats", "df", "logs",
                    "live", "inspect", "screens", "report"}
    if args and args[0] in CLI_COMMANDS:
        run_cli_command(args)
        return

    if "--menu" in args or "-m" in args or "menu" in args:
        dockman_banner()
        run_cli_menu()
        return

    # --tui flag untuk TUI curses (opsional)
    if "--tui" in args:
        debug_mode = "--debug" in args
        dockman_banner(skip=debug_mode)
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
            print(f"\n  WARN: TUI gagal ({type(tui_error).__name__}), beralih ke menu...")
            print("  Tip: dockman --debug untuk detail\n")
            time.sleep(1)

    # Default: numbered menu 3 kolom + banner
    dockman_banner()
    run_cli_menu()


if __name__ == "__main__":
    main()
