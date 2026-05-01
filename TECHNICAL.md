# Dockman - Technical Documentation

**Version:** 2.2.0  
**License:** MIT  
**Repository:** https://github.com/USERNAME/dockman

---

## 1. Architecture Overview

Dockman menggunakan **arsitektur hybrid UI**:

```
dockman/
├── core/               # Business logic - ZERO UI dependency
│   ├── config.py       # Configuration manager
│   ├── docker.py       # Docker data layer
│   ├── utils.py        # Shell execution utilities
│   └── serverdocs.py   # Server report generator
│
├── ui/                 # UI layer - ZERO business logic
│   ├── curses_ui.py    # Interactive TUI (Curses)
│   ├── rich_ui.py      # Rich output (tables, logs, progress)
│   ├── cli_menu.py     # Numbered menu fallback
│   └── wizard.py       # First-run setup wizard
│
├── main.py             # Entry point & CLI router
└── build.py            # Compiler: multi-file -> single dockman.py
```

**Prinsip utama:**
- `core/` tidak boleh import dari `ui/`
- `ui/` boleh import dari `core/`, tidak boleh antar-ui
- `main.py` adalah satu-satunya controller yang boleh import keduanya

---

## 2. Build System

Dockman dikembangkan sebagai **multi-file project** tapi di-compile ke
**satu file tunggal** untuk kemudahan instalasi.

### 2.1 Cara Build

```bash
cd ~/dockman
python3 build.py

# Output: dist/dockman.py (single file, ~140KB)
```

### 2.2 Cara Kerja build.py

```
Source files (urutan penting):
  core/config.py
  core/utils.py
  core/docker.py
  core/serverdocs.py
  ui/rich_ui.py
  ui/wizard.py
  ui/curses_ui.py
  ui/cli_menu.py
  main.py

Build process:
  1. Baca setiap file
  2. Strip internal imports (from core.x import, from ui.x import)
  3. Kumpulkan stdlib/pip imports (dedup)
  4. Inject MODULE STUBS sebelum main()
  5. Gabung semua ke satu file
  6. Tulis ke dist/dockman.py
```

### 2.3 MODULE STUBS

Karena internal imports di-strip, `main.py` perlu namespace objects:

```python
# Otomatis di-inject oleh build.py sebelum def main():
config = SimpleNamespace(load=load, get=get, ...)
docker = SimpleNamespace(get_containers=get_containers, ...)
rich_ui = SimpleNamespace(show_containers=show_containers, ...)
```

### 2.4 Aturan Penting saat Edit Source

**JANGAN** pakai lazy import di dalam fungsi untuk internal modules:
```python
# SALAH - akan di-strip tapi meninggalkan kode yang pakai alias
def my_func():
    from core.utils import run_cmd as _rc  # di-strip!
    _rc("command")                          # NameError!

# BENAR - import di top-level, otomatis tersedia setelah build
from core.utils import run_cmd
def my_func():
    run_cmd("command")
```

**JANGAN** pakai multiline import untuk internal modules:
```python
# SALAH - baris lanjutan tidak ikut di-strip
from ui.curses_ui import (
    init_colors, screen_home  # baris ini tertinggal!
)

# BENAR - satu baris
from ui.curses_ui import init_colors, screen_home
```

---

## 3. Configuration

Config disimpan di `~/.config/dockman/config.ini`.

```ini
[general]
editor          = nano
hostname        = rlserver
fetch_interval  = 10        # detik auto-refresh container list
doc_output_dir  = /home/suhu

[docker]
compose_file    = /mnt/media/docker-compose.yml
compose_dir     = /mnt/media
compose_cmd     = docker compose   # atau: docker-compose (v1), auto

[rclone]
remote_name     = mega
remote_path     = film
dest_radarr     = /mnt/media/downloads/complete/radarr
dest_sonarr     = /mnt/media/downloads/complete/sonarr

[alias]
file            = /home/suhu/.bashrc
```

### 3.1 API Config

```python
import core.config as config

config.load()                    # Load dari file
config.get("section", "key")     # Baca nilai
config.set_value("section", "key", "val")  # Tulis & simpan
config.get_hostname()            # Shortcut getter
config.get_compose_cmd()         # Auto-detect v1/v2
config.is_first_run()            # Cek apakah wizard perlu dijalankan
```

---

## 4. Core Modules

### 4.1 core/utils.py

```python
run_cmd(cmd, timeout=30)
# -> (stdout, stderr, returncode)
# Tidak pernah raise exception

run_interactive(cmd)
# -> returncode
# Untuk command yang butuh TTY (nano, exec shell, dll)

run_stream(cmd)
# -> generator of lines
# Untuk streaming output (progress, live logs)

sanitize_input(s)
# -> string bersih
# Hapus karakter berbahaya untuk shell injection

check_docker()
# -> docker_version string
# Raise DockerError jika tidak bisa akses

check_tool(name)
# -> path or None
```

### 4.2 core/docker.py

Semua fungsi return Python objects, tidak ada UI logic:

```python
get_containers()     # -> List[Dict]  {name, status, image, ports, running, healthy}
get_images()         # -> List[Dict]  {name, size, created, id}
get_stats_once()     # -> List[Dict]  {name, cpu, mem, net, block}
get_disk_usage()     # -> str (raw docker system df output)
get_screens()        # -> List[Dict]  {sid, pid, name, status}

container_action(name, action)   # action: start|stop|restart|rm
                                 # -> (bool ok, str message)
pull_image(image)                # -> (bool ok, str message)
compose_action(action, flags)    # action: up|down|pull
compose_validate()               # -> (bool ok, str message)
screen_kill(sid)                 # -> (bool ok, str message)
```

### 4.3 core/serverdocs.py

```python
gen = ServerDocsGenerator(
    output_dir="/home/suhu",
    progress_cb=lambda step, total, label: print(f"{step}/{total}: {label}")
)
path = gen.generate()   # -> str path file output

# Sections yang di-generate (urutan):
# Header, Informasi Sistem, Hardware, Storage, Mount Points,
# Jaringan, Netplan Config, Firewall, Software, Services,
# Docker, Compose Projects, File YML, Cron Jobs, Footer
```

---

## 5. UI Modules

### 5.1 ui/curses_ui.py - Interactive TUI

Fungsi-fungsi utama:

```python
init_colors()           # Setup color pairs curses
screen_home(stdscr)     # Home dashboard (neofetch-style)
screen_containers(stdscr)   # Main container list
menu_container(stdscr, container_dict)  # Per-container actions
menu_all_actions(stdscr)    # Bulk actions
menu_images(stdscr)
menu_compose(stdscr)
menu_extras(stdscr)
menu_gnu_screen(stdscr)
menu_settings(stdscr)
screen_help(stdscr)
```

**Anti-flicker pattern:**
```python
stdscr.erase()          # bukan clear() - tidak trigger repaint fisik
stdscr.noutrefresh()    # tandai "siap render"
curses.doupdate()       # flush semua sekaligus - tidak ada frame kosong
```

**Keyboard shortcut system:**
```python
# Di list_select(), shortcut huruf di-parse dari label [X]
# Contoh: "[R] Restart Container" -> tekan R langsung pilih
shortcuts = {}
m = re.match(r'^\[([A-Za-z0-9])\]', label)
if m: shortcuts[ord(ch)] = idx
```

### 5.2 ui/rich_ui.py - Rich Output

Dipanggil setelah `curses.endwin()`, TIDAK PERNAH di dalam loop curses:

```python
show_containers(containers)   # Rich table
show_images(images)           # Rich table
show_stats(stats)             # Rich table + CPU color coding
show_disk_usage(raw)          # Rich panel
show_logs(name, content)      # Rich panel + log coloring
stream_logs(name, tail)       # Live streaming dengan color
show_inspect(name, json_str)  # Syntax highlighted JSON
show_compose_file(filepath)   # Syntax highlighted YAML
show_screen_sessions(sessions)# Rich table
generate_server_docs_with_progress(output_dir, output_path)
                              # Rich progress bar + ServerDocsGenerator
```

**Hybrid UI flow:**
```python
# Di curses_ui.py, saat mau tampilkan output Rich:
curses.endwin()          # 1. Keluar curses
rich_ui.show_logs(...)   # 2. Tampilkan dengan Rich
input("Enter...")        # 3. Tunggu user
stdscr.touchwin()        # 4. Restore curses
stdscr.refresh()
curses.doupdate()
```

### 5.3 ui/cli_menu.py - Fallback Menu

Dijalankan via `dockman --menu`. Semua output pakai Rich.
Nomor menu 1-32 dengan kategori: Container, Compose, Maintenance,
Extras, GNU Screen, Settings.

---

## 6. CLI Interface

```
dockman                    TUI mode (default)
dockman --menu             Numbered menu
dockman --setup            Setup wizard
dockman --debug            TUI + traceback jika error
dockman --version          Print version
dockman --help             Print help

# CLI commands (Rich output, tanpa TUI):
dockman ps                 List containers
dockman images             List images
dockman stats              Stats snapshot
dockman df                 Disk usage
dockman logs <name>        Logs 50 baris
dockman logs <name> <n>    Logs n baris
dockman live <name>        Live streaming logs
dockman inspect <name>     Inspect JSON
dockman screens            List GNU screen sessions
dockman report             Generate server report
dockman report <path>      Generate ke path custom
```

---

## 7. Installer

`install-dockman.sh` mendukung:

| OS | Package Manager |
|---|---|
| Ubuntu / Debian / Mint | apt |
| Fedora | dnf |
| RHEL / CentOS / Rocky | yum |
| Arch / Manjaro | pacman |
| Alpine | apk |

```bash
bash install-dockman.sh           # Install / update
bash install-dockman.sh uninstall # Hapus
bash install-dockman.sh check     # Cek dependencies
bash install-dockman.sh build     # Build saja (tanpa install)
```

**Dependencies yang di-auto-install:**
1. Python3 + pip
2. Rich (pip)
3. Docker (via get.docker.com)
4. GNU Screen
5. rclone
6. nano

---

## 8. Development Workflow

### 8.1 Setup dev environment

```bash
git clone https://github.com/USERNAME/dockman.git
cd dockman
# Tidak perlu virtualenv - hanya stdlib + rich
pip install rich --break-system-packages
```

### 8.2 Edit dan test

```bash
# Edit source
nano ui/curses_ui.py

# Build ke single file
python3 build.py

# Test langsung dari dist (tanpa install)
python3 dist/dockman.py --version
python3 dist/dockman.py ps
python3 dist/dockman.py --debug

# Install untuk test TUI
sudo cp dist/dockman.py /usr/local/bin/dockman
dockman
```

### 8.3 Update ke server

```bash
# Di laptop
git add -A
git commit -m "Fix: deskripsi perubahan"
git push

# Di server
cd ~/dockman
git pull
bash install-dockman.sh
```

### 8.4 Version bumping

Edit `core/config.py`:
```python
VERSION = "2.2.1"   # patch: bugfix
VERSION = "2.3.0"   # minor: fitur baru
VERSION = "3.0.0"   # major: breaking change / rewrite
```

---

## 9. Known Issues & Gotchas

### 9.1 Build: Internal import stripping

Build.py strip semua `from core.x` dan `from ui.x` imports.
Jika ada lazy import di dalam fungsi, **alias-nya akan hilang** tapi
kode yang memakainya tetap ada → `NameError` saat runtime.

**Solusi:** Selalu import di top-level file, bukan di dalam fungsi.

### 9.2 Curses: Unicode/emoji crash

Curses tidak support karakter multi-byte (emoji, box-drawing chars)
di beberapa terminal. Semua karakter di curses layer harus ASCII.

Rich layer boleh pakai unicode karena terminal sudah dalam mode normal.

### 9.3 Netplan: Permission denied

File `/etc/netplan/*.yaml` biasanya hanya bisa dibaca root.
`serverdocs.py` otomatis mencoba `sudo cat` sebagai fallback.
Jika `dockman report` dijalankan sebagai user biasa dan sudo
membutuhkan password, section netplan mungkin tidak terbaca.

**Workaround:** `sudo dockman report`

### 9.4 Docker group

Tanpa docker group, semua docker command butuh sudo:
```bash
sudo usermod -aG docker $USER
newgrp docker    # aktif tanpa logout
```

---

## 10. File Locations

| File | Path |
|---|---|
| Binary | `/usr/local/bin/dockman` |
| Config | `~/.config/dockman/config.ini` |
| Backup binary | `/usr/local/bin/dockman.bak_YYYYMMDD_HHMMSS` |
| Compose backup | `<compose_file>.bak_YYYYMMDD_HHMMSS` |
| Server report | `<doc_output_dir>/server-docs-YYYYMMDD.txt` |
| Source (dev) | `~/dockman/` |
| Built output | `~/dockman/dist/dockman.py` |
