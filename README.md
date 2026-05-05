# dockman>_

<p align="center">
  <img src="image-assets/dockman_logo_black.png" alt="Dockman Logo" width="600"/>
</p>

<p align="center">
  <strong>Personal Docker &amp; Media Server Management Tool</strong>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.8%2B-blue?logo=python">
  <img src="https://img.shields.io/badge/License-MIT-green">
  <img src="https://img.shields.io/badge/Version-2.2.1-orange">
  <img src="https://img.shields.io/badge/Platform-Linux-lightgrey?logo=linux">
</p>

<p align="center">
  🇬🇧 English &nbsp;|&nbsp;
  <a href="README.id.md">🇮🇩 Bahasa Indonesia</a>
</p>

---

Dockman is a Python-based TUI (Terminal User Interface) for managing Docker containers, images, compose, GNU Screen, rclone, and server reports — all from one place, right in your terminal.

---

## 🤔 Why Dockman?

- No need to remember long Docker commands
- Clean interactive interface (TUI)
- Faster daily workflow
- Beginner-friendly but powerful

---

## 📸 Screenshot

<p align="center">
  <img src="image-assets/sc%20home.png" alt="Dockman Home Dashboard" width="900"/>
</p>

---

## ✨ Features

- **Interactive TUI** — keyboard navigation, anti-flicker, letter shortcuts `[X]`
- **Home Dashboard** — neofetch-style: sysinfo, RAM, storage bar, block devices, docker summary
- **Container Management** — view logs, live logs, restart, stop/start, exec shell, pull image, remove
- **Bulk Actions** — update all images, restart all, compose up/down/pull, prune volumes/images
- **Docker Images** — list, pull update, delete
- **Docker Compose** — view, edit, backup, validate config
- **GNU Screen** — list, attach, create new session, run commands in background, kill session
- **Extras** — manage alias/bashrc, cron job viewer & editor, rclone copy from cloud
- **Server Report** — generate full server documentation (hardware, storage, network, docker, cron, etc.)
- **Settings** — configure all parameters directly from TUI
- **Hybrid UI** — navigation via Curses, output via Rich (colored tables, syntax highlight, progress bar)

---

## 📦 Installation

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/bugsdroid/dockman/main/install-dockman.sh)
```

The installer automatically handles dependencies: Python3, pip, Rich, Docker, GNU Screen, rclone, nano.

| OS | Package Manager |
|---|---|
| Ubuntu / Debian / Mint | apt |
| Fedora | dnf |
| RHEL / CentOS / Rocky | yum |
| Arch / Manjaro | pacman |
| Alpine | apk |

### Update & Uninstall

```bash
# Update to latest version
bash <(curl -fsSL https://raw.githubusercontent.com/bugsdroid/dockman/main/install-dockman.sh)

# Uninstall
bash <(curl -fsSL https://raw.githubusercontent.com/bugsdroid/dockman/main/install-dockman.sh) uninstall

# Check dependencies
bash <(curl -fsSL https://raw.githubusercontent.com/bugsdroid/dockman/main/install-dockman.sh) check
```

---

## 🚀 Usage

```bash
dockman              # Interactive TUI (default)
dockman --menu       # Numbered menu (fallback)
dockman --setup      # Initial setup wizard
dockman --debug      # TUI + traceback on error
dockman --version    # Show version
```

### CLI Commands (without TUI)

```bash
dockman ps                # List all containers
dockman images            # List docker images
dockman stats             # Resource usage snapshot
dockman df                # Docker disk usage
dockman logs <name>       # Last 50 lines of logs
dockman logs <name> <n>   # Last n lines of logs
dockman live <name>       # Live streaming logs
dockman inspect <name>    # Inspect container (JSON)
dockman screens           # List GNU screen sessions
dockman report            # Generate server report
dockman report <path>     # Generate to custom path
```

---

## ⌨️ TUI Navigation

| Key | Action |
|---|---|
| `↑` / `k` | Up |
| `↓` / `j` | Down |
| `Enter` | Select / open menu |
| `q` / `Esc` | Back / quit |
| `r` | Refresh containers |
| `a` | All container actions |
| `i` | Images list |
| `s` | Docker stats |
| `d` | Disk usage |
| `c` | Docker Compose |
| `x` | Extras (alias, cron, rclone, report) |
| `w` | GNU Screen manager |
| `t` | Settings / configuration |
| `?` | Help |

> **Tip:** In any menu, items marked `[X]` can be selected instantly by pressing that letter.

---

## ⚙️ Configuration

Config is stored at `~/.config/dockman/config.ini`.

```ini
[general]
editor          = nano
hostname        = myserver
fetch_interval  = 10
doc_output_dir  = /home/user

[docker]
compose_file    = /mnt/media/docker-compose.yml
compose_dir     = /mnt/media
compose_cmd     = docker compose

[rclone]
remote_name     = mega
remote_path     = film
dest_radarr     = /mnt/media/downloads/complete/radarr
dest_sonarr     = /mnt/media/downloads/complete/sonarr

[alias]
file            = /home/user/.bashrc
```

The setup wizard runs automatically on first launch.

---

## 📋 Releases

| Version | Date | Notes |
|---|---|---|
| [v2.2.0](https://github.com/bugsdroid/dockman/releases/tag/v2.2.0) | 2026-04-28 | Home Dashboard, animated banner, remote install |
| v2.1.0 | 2026-04-20 | GNU Screen, rclone, server report, wizard |
| v2.0.0 | 2026-04-10 | Hybrid UI (Curses + Rich), CLI commands |
| v1.0.0 | 2026-03-01 | First release |

See [CHANGELOG.md](CHANGELOG.md) for detailed changes per version.

---

## 📁 File Locations

| File | Path |
|---|---|
| Binary | `/usr/local/bin/dockman` |
| Config | `~/.config/dockman/config.ini` |
| Server Report | `<doc_output_dir>/server-docs-YYYYMMDD.txt` |
| Binary backup | `/usr/local/bin/dockman.bak_YYYYMMDD_HHMMSS` |

---

## 🛠️ Development

```bash
git clone https://github.com/bugsdroid/dockman.git
cd dockman
pip install rich --break-system-packages

# Edit source
nano dockman_main/ui/curses_ui.py

# Build single file
cd dockman_main
python3 build.py
# Output: dist/dockman.py

# Test without installing
python3 dist/dockman.py --version
python3 dist/dockman.py ps

# Install for TUI testing
sudo cp dist/dockman.py /usr/local/bin/dockman
dockman
```

### Architecture

```
dockman/
├── dockman_main/       # Source code
│   ├── core/           # Business logic (no UI)
│   │   ├── config.py
│   │   ├── docker.py
│   │   ├── utils.py
│   │   └── serverdocs.py
│   ├── ui/             # UI layer
│   │   ├── curses_ui.py   # Interactive TUI
│   │   ├── rich_ui.py     # Table & log output
│   │   ├── cli_menu.py    # Numbered menu fallback
│   │   └── wizard.py      # Setup wizard
│   ├── main.py
│   └── build.py
├── dockman.py          # Pre-built single file (ready to install)
├── install-dockman.sh  # Universal installer
├── image-assets/       # Logo & screenshots
├── CHANGELOG.md
└── TECHNICAL.md
```

**Rule:** `core/` must not import from `ui/`. The build system compiles all files into a single `dockman.py`.

---

## 📋 Dependencies

- Python 3.8+
- [Rich](https://github.com/Textualize/rich) — beautiful terminal output
- Docker Engine
- GNU Screen
- rclone *(optional, for cloud copy feature)*
- nano *(or any other editor)*

---

## 📄 License

MIT License — free to use and modify.

---

*Built for personal media servers. Tested on Ubuntu/Debian.*
