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
  <img src="https://img.shields.io/badge/Version-2.3.0-orange">
  <img src="https://img.shields.io/badge/Platform-Linux-lightgrey?logo=linux">
</p>

<p align="center">
  🇬🇧 English &nbsp;|&nbsp;
  <a href="README.id.md">🇮🇩 Bahasa Indonesia</a>
</p>

---

Dockman is a Python-based TUI (Terminal User Interface) for managing Docker containers, images, compose, GNU Screen, rclone, and server reports — all from one place, right in your terminal.

---

## 🆕 What's New in v2.3.0

### 🗂️ Clean 3-column menu
`dockman` now opens directly into a **3-column numbered menu** — all categories visible at once, no scrolling:

```
  DOCKMAN v2.3.0  —  rlserver  —  suhu

  CONTAINER                 COMPOSE                   MAINTENANCE
  1. List container         9.  Compose UP             14. Prune image
  2. Update image           10. Compose DOWN            15. Prune volumes
  3. Update SEMUA           11. Lihat compose           16. Prune TOTAL
  4. Restart                12. Edit compose            17. Disk usage
  5. Restart SEMUA          13. Backup compose
  6. Docker Stats
  7. Lihat logs
  8. Exec shell

  GNU SCREEN                EXTRAS                    SETTINGS
  25. List session          18. Lihat alias            31. Lihat konfigurasi
  26. Attach                19. Grep alias             32. Wizard ulang
  27. Kill 1 session        20. Edit bashrc
  28. Kill SEMUA            21. Lihat cron
  29. Buat session          22. Edit cron
  30. Cmd background        23. Rclone mega.nz
                            24. Server report

  ────────────────────────────────────────────────────────────────────────────────
  0. Keluar
```

The old curses TUI is still available via `dockman --tui`.

### 🔥 UFW firewall detection fix (server report)
UFW always showed as “not detected” when running as non-root. Now uses a 5-step fallback:
1. `sudo -n ufw status verbose`
2. `ufw status verbose 2>&1`
3. Read `/etc/ufw/ufw.conf` directly (no root needed)
4. `systemctl is-active ufw`
5. `iptables -L ufw-user-input`

### 📦 Installer now builds from source
`install-dockman.sh` now does `git clone --depth=1` + `python3 build.py` — always gets the latest version directly from source.

---

## 🤔 Why Dockman?

- No need to remember long Docker commands
- Clean 3-column menu, all options visible at once
- Faster daily workflow
- Beginner-friendly but powerful

---

## 📸 Screenshot

<p align="center">
  <img src="image-assets/sc%20home.png" alt="Dockman Home Dashboard" width="900"/>
</p>

---

## ✨ Features

- **3-Column Menu** — all categories visible at once, no scrolling
- **Container Management** — view logs, live logs, restart, stop/start, exec shell, pull image, remove
- **Bulk Actions** — update all images, restart all, compose up/down/pull, prune volumes/images
- **Docker Images** — list, pull update, delete
- **Docker Compose** — view, edit, backup, validate config
- **GNU Screen** — list, attach, create new session, run commands in background, kill session
- **Extras** — manage alias/bashrc, cron job viewer & editor, rclone copy from cloud
- **Server Report** — generate full server documentation (hardware, storage, network, docker, cron, etc.)
- **Settings** — configure all parameters directly from menu
- **TUI mode** — optional curses dashboard via `dockman --tui`
- **Rich output** — colored tables, syntax highlight, progress bar

---

## 📦 Installation

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/bugsdroid/dockman/main/install-dockman.sh)
```

The installer automatically handles dependencies: Python3, pip, Rich, Git, Docker, GNU Screen, rclone, nano.

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
dockman              # 3-column numbered menu (default)
dockman --tui        # TUI curses interaktif (opsional)
dockman --setup      # Initial setup wizard
dockman --version    # Show version
```

### CLI Commands (without menu)

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

## ⌨️ Navigation

In the menu, type the number and press Enter. Press `Enter` after Rich output to return to menu.

For `dockman --tui` curses mode:

| Key | Action |
|---|---|
| `↑` / `k` | Up |
| `↓` / `j` | Down |
| `Enter` | Select / open menu |
| `q` / `Esc` | Back / quit |
| `r` | Refresh containers |
| `a` | All container actions |
| `s` | Docker stats |
| `c` | Docker Compose |
| `x` | Extras |
| `w` | GNU Screen manager |
| `t` | Settings |
| `?` | Help |

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
| [v2.3.0](https://github.com/bugsdroid/dockman/releases/tag/v2.3.0) | 2026-05-10 | 3-column menu, UFW fix, build-from-source installer |
| [v2.2.0](https://github.com/bugsdroid/dockman/releases/tag/v2.2.0) | 2026-04-28 | Home Dashboard, animated banner |
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
nano dockman_main/ui/cli_menu.py

# Build single file
cd dockman_main
python3 build.py
# Output: dist/dockman.py

# Test without installing
python3 dist/dockman.py --version
python3 dist/dockman.py

# Install for testing
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
│   │   ├── curses_ui.py   # TUI interaktif (dockman --tui)
│   │   ├── rich_ui.py     # Table & log output
│   │   ├── cli_menu.py    # 3-column numbered menu (default)
│   │   └── wizard.py      # Setup wizard
│   ├── main.py
│   └── build.py
├── install-dockman.sh  # Universal installer (builds from source)
├── image-assets/
├── CHANGELOG.md
└── TECHNICAL.md
```

---

## 📋 Dependencies

- Python 3.8+
- [Rich](https://github.com/Textualize/rich) — beautiful terminal output
- Git — for installation from source
- Docker Engine
- GNU Screen
- rclone *(optional, for cloud copy feature)*
- nano *(or any other editor)*

---

## 📄 License

MIT License — free to use and modify.

---

*Built for personal media servers. Tested on Ubuntu/Debian.*
