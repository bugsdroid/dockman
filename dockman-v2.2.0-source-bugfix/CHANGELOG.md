
## [2.2.0] - 2026-04-28

### Changed
- Kembali ke Curses TUI (stable, tanpa Textual dependency)
- Home screen baru sebagai landing page saat `dockman` dijalankan

### Added
- **Home Dashboard** (neofetch-style):
  - Logo dockman ASCII art
  - System info: OS, Kernel, CPU, Cores, RAM + progress bar, Uptime, Load
  - Network interfaces dengan IP
  - Storage dengan visual progress bar per mount point
  - Block devices (lsblk) dengan tree view
  - Docker summary (running/stopped/images)
- **Banner animasi** `dockman>_` saat startup (typewriter + blinking cursor)
  - True color support: #D2D6DC (dock) + #4F7CF7 (man>_)
  - Fallback 256-color dan basic terminal
- Auto-install Python, pip, Rich di installer
- `dockman --setup` bisa dijalankan kapan saja

### Fixed
- Netplan section di server report: try sudo jika permission denied
