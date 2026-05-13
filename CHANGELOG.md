# CHANGELOG

Semua perubahan penting pada Dockman dicatat di sini.
Format: `[versi] - tanggal` → `Added / Changed / Fixed`

---

## [2.3.0] - 2026-05-10

### Changed
- **Default mode**: `dockman` tanpa argumen langsung masuk ke **numbered menu 3 kolom**
- **Menu redesign**: Layout 3 kolom yang rapi
  - Baris atas : `CONTAINER` | `COMPOSE` | `MAINTENANCE`
  - Baris bawah: `GNU SCREEN` | `EXTRAS` | `SETTINGS`
  - Header: `DOCKMAN vX.X.X — hostname — username` (cyan bold)
- **`dockman --tui`**: Flag baru untuk masuk ke TUI curses interaktif
- **`dockman --menu`**: Sama dengan default (backward compatible)
- **Banner `dockman>_`**: Muncul kembali saat startup (default + --menu mode)
- Installer (`install-dockman.sh` v2.5): `git clone --depth=1` + `python3 build.py`
- Source files lengkap di `dockman_main/`

### Fixed
- **`NameError: config_load`** di menu pilihan 31: import alias `load as config_load`
  ter-strip oleh build system, diganti dengan `load()` langsung
- **Polkit authentication popup** saat generate server report:
  - `section_netplan`: hapus `sudo netplan status`, `sudo ls /etc/netplan/`,
    `sudo cat` — semua bisa trigger polkit interaktif
  - `section_services`: tambah `DBUS_SESSION_BUS_ADDRESS=''` dan
    `--no-ask-password` untuk disable D-Bus auto-activation
  - Fallback ke `ps aux` jika systemctl tetap gagal
- **UFW detection** di server report: multi-fallback 5-step
  1. `sudo -n ufw status verbose` (passwordless)
  2. `ufw status verbose 2>&1`
  3. Baca `/etc/ufw/ufw.conf` langsung
  4. `systemctl is-active ufw`
  5. `sudo -n iptables -L ufw-user-input`

---

## [2.2.0] - 2026-04-28

### Added
- **Home Dashboard** (neofetch-style) sebagai landing page
- **Banner animasi** `dockman>_` saat startup
- `dockman --setup` bisa dijalankan kapan saja

### Changed
- Kembali ke Curses TUI (stable)
- Home screen sebagai landing page

### Fixed
- Netplan section di server report: try `sudo cat` jika permission denied

---

## [2.1.0] - 2026-04-20

### Added
- GNU Screen manager
- Rclone copy dari cloud
- Server report generator
- Setup wizard

### Changed
- Installer universal (apt/dnf/yum/pacman/apk)
- Build system: multi-file → single `dockman.py`

---

## [2.0.0] - 2026-04-10

### Added
- Hybrid UI: Curses + Rich
- CLI commands: `ps`, `images`, `stats`, `df`, `logs`, `live`, `inspect`, `screens`, `report`

### Changed
- Arsitektur dipisah: `core/` dan `ui/`

---

## [1.0.0] - 2026-03-01

### Added
- Versi pertama: manajemen Docker container via terminal
