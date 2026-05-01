"""
ui/rich_ui.py - Rich UI layer untuk Dockman
Semua output yang pakai Rich ada di sini.
Dipanggil setelah curses di-endwin(), TIDAK pernah dipanggil di dalam curses loop.
"""

from typing import List, Dict, Optional
import sys
import time

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
    from core.serverdocs import ServerDocsGenerator

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
    from core.serverdocs import ServerDocsGenerator

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
