# CHANGELOG

Semua perubahan penting pada Dockman dicatat di sini.
Format: `[versi] - tanggal` → `Added / Changed / Fixed`

---

## [2.2.0] - 2026-04-28

### Added
- **Home Dashboard** (neofetch-style) sebagai landing page saat `dockman` dijalankan
  - System info: OS, Kernel, CPU, Cores, RAM, Uptime, Load
  - Network interfaces dengan IP
  - Storage dengan visual progress bar per mount point
  - Block devices (lsblk) dengan tree view
  - Docker summary (running/stopped/images)
- **Banner animasi** `dockman>_` saat startup
  - True color, 256-color, dan basic terminal support
- `dockman --setup` bisa dijalankan kapan saja
- Auto-install Python, pip, Rich di installer

### Changed
- Kembali ke Curses TUI (stable, tanpa Textual dependency)
- Home screen sebagai landing page, bukan langsung container list

### Fixed
- Netplan section di server report: try `sudo cat` jika permission denied

---

## [2.1.0] - 2026-04-20

### Added
- GNU Screen manager (list, attach, buat session, kill)
- Rclone copy dari cloud (Radarr/Sonarr/manual destination)
- Server report generator (`dockman report`)
- Netplan config section di server report
- Setup wizard (`dockman --setup`)

### Changed
- Installer universal (apt/dnf/yum/pacman/apk)
- Build system: multi-file → single `dockman.py`

---

## [2.0.0] - 2026-04-10

### Added
- Hybrid UI: Curses untuk navigasi, Rich untuk output
- Anti-flicker pattern (`erase` + `noutrefresh` + `doupdate`)
- Keyboard shortcut `[X]` di semua menu
- Docker stats, disk usage, inspect JSON
- Compose view/edit/backup/validate
- CLI commands: `ps`, `images`, `stats`, `df`, `logs`, `live`, `inspect`, `screens`, `report`

### Changed
- Arsitektur dipisah: `core/` (business logic) dan `ui/` (tampilan)
- `core/` zero UI dependency

---

## [1.0.0] - 2026-03-01

### Added
- Versi pertama: manajemen Docker container via terminal
- List, start, stop, restart, logs container
- Basic Rich output
