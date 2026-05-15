# CHANGELOG

Semua perubahan penting pada Dockman dicatat di sini.
Format: `[versi] - tanggal` → `Added / Changed / Fixed / Removed`

---

## [3.0.0] - WIP (branch: v3)

### Added

- **Bootstrap Wizard** (7 phases) — setup server dari nol tanpa perlu tau Linux command
  - Phase 1: Persiapan Sistem — update packages, hostname, timezone, locale, SSH hardening
  - Phase 2: Konfigurasi Jaringan — static IP via netplan (rollback otomatis), UFW, mDNS, DoH
  - Phase 3: Manajemen Storage — deteksi disk, format, mount via UUID, fstab, folder structure
  - Phase 4: Setup Docker — install Docker, daemon config (log rotation), docker group, network mode
  - Phase 5: Pilih Stack — media server, downloader, arr suite, indexer, reverse proxy, monitoring
  - Phase 6: Remote Access — Tailscale dan/atau Cloudflare Tunnel
  - Phase 7: Deploy & Verifikasi — generate compose, `docker compose up`, health check, summary URL
- **Resume-able wizard** — progress disimpan ke `~/.config/dockman/bootstrap_state.json`
- **Per-phase rerun** — `dockman --bootstrap 3` langsung ke Phase 3
- **Compose generator** — auto-generate `docker-compose.yml` berdasarkan pilihan stack
- **Port conflict detection** — deteksi konflik port antar service sebelum deploy
- **Safety net 5 lapis** untuk operasi destructive (format disk)
- **Netplan rollback otomatis** — jika static IP gagal, config lama dipulihkan
- **SSH autostart toggle** — dockman otomatis buka saat SSH login
- **`dockman --bootstrap`** dan **`dockman --bootstrap <n>`** — CLI flags
- Menu entry **33** (Bootstrap Wizard) dan **34** (jalankan ulang phase) di numbered menu
- **`core/bootstrap.py`** — state management, phase definitions, compose generator, helpers
- **`ui/bootstrap_wizard.py`** — interactive wizard UI untuk 7 phases
- **`test-bootstrap.sh`** — test suite: build + unit + smoke + integration (50+ test cases)
- **`install-dockman.sh` v3.0** — bootstrap support, uninstall cleanup state
- **`README.v3.md`** — dokumentasi khusus branch v3

### Changed
- Version bump: 2.3.0 → 3.0.0
- `build.py` diupdate: include bootstrap modules, exclude curses
- `main.py` diupdate: routing `--bootstrap`, hapus TUI routing
- `cli_menu.py` diupdate: tambah section BOOTSTRAP (menu 33 & 34)

### Removed
- **TUI mode (curses)** — `dockman --tui` dan `ui/curses_ui.py` dihapus dari v3
  - Alasan: menu numbered 3 kolom lebih user-friendly, Bootstrap Wizard menggantikan home dashboard, curses bermasalah di beberapa terminal/SSH environment
  - `dockman --tui` sekarang menampilkan pesan info dan exit
  - Untuk referensi TUI, lihat branch `main` (v2.3.0)
- `import curses` dihapus dari build output
- `import traceback` dan `import time` (dari TUI fallback) dihapus dari main.py

### Stack yang didukung (Bootstrap Wizard Phase 5)

| Kategori | Pilihan |
|---|---|
| Media Server | Jellyfin, Plex, Emby |
| Downloader | qBittorrent, Deluge, SABnzbd |
| Arr Suite | Radarr, Sonarr, Lidarr, Bazarr |
| Indexer | Prowlarr, Jackett |
| Request Manager | Jellyseerr, Overseerr |
| Reverse Proxy | Nginx Proxy Manager, Caddy |
| Dashboard | Homarr, Heimdall |
| Monitoring | Portainer, Watchtower |
| DNS/Adblock | AdGuard Home, Pi-hole |
| Remote Access | Tailscale, Cloudflare Tunnel |

---

## [2.3.0] - 2026-05-10

### Changed
- **Default mode**: `dockman` tanpa argumen langsung masuk ke **numbered menu 3 kolom**
- **Menu redesign**: Layout 3 kolom yang rapi (CONTAINER | COMPOSE | MAINTENANCE, GNU SCREEN | EXTRAS | SETTINGS)
- **`dockman --tui`**: Flag untuk masuk ke TUI curses interaktif
- **`dockman --menu`**: Sama dengan default (backward compatible)
- **Banner `dockman>_`**: Muncul kembali saat startup
- Installer v2.5: `git clone --depth=1` + `python3 build.py`

### Fixed
- **`NameError: config_load`** di menu pilihan 31
- **Polkit authentication popup** saat generate server report
- **UFW detection** di server report: multi-fallback 5-step

---

## [2.2.0] - 2026-04-28

### Added
- **Home Dashboard** (neofetch-style) sebagai landing page
- **Banner animasi** `dockman>_` saat startup

### Fixed
- Netplan section di server report: try `sudo cat` jika permission denied

---

## [2.1.0] - 2026-04-20

### Added
- GNU Screen manager, Rclone copy dari cloud, Server report generator, Setup wizard

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
