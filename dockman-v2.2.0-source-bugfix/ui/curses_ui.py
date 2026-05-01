"""
ui/curses_ui.py - Curses TUI layer untuk Dockman
Semua navigasi, input, dan menu interaktif ada di sini.
TIDAK boleh ada Rich di dalam file ini.
"""

import curses
import re
import time
from datetime import datetime
from typing import List, Dict, Callable, Optional

import core.config as config
import core.docker as docker
from core.utils import run_cmd, run_interactive, sanitize_input, check_tool
import ui.rich_ui as rich_ui

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
