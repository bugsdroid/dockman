# CHANGELOG

Semua perubahan penting pada Dockman dicatat di sini.
Format: `[versi] - tanggal` → `Added / Changed / Fixed`

---

## [3.0.0] - WIP (branch: v3)

### Added

- **Bootstrap Wizard** (7 phases) — setup server dari nol tanpa perlu tau Linux command
  - Phase 1: Persiapan Sistem — update packages, hostname, timezone, locale, SSH hardening
  - Phase 2: Konfigurasi Jaringan — static IP via netplan (dengan rollback otomatis), UFW, mDNS, DoH
  - Phase 3: Manajemen Storage — deteksi disk, format, mount via UUID, fstab, folder structure
  - Phase 4: Setup Docker — install Docker, daemon config (log rotation), docker group, network mode
  - Phase 5: Pilih Stack Aplikasi — media server, downloader, arr suite, indexer, reverse proxy, monitoring
  - Phase 6: Remote Access — Tailscale dan/atau Cloudflare Tunnel
  - Phase 7: Deploy & Verifikasi — generate compose, docker compose up, health check, summary URL
- **Resume-able wizard** — progress disimpan ke `~/.config/dockman/bootstrap_state.json`, bisa dilanjutkan
- **Per-phase re-run** — bisa jalankan ulang phase tertentu tanpa harus dari awal
- **Compose generator** — auto-generate `docker-compose.yml` berdasarkan pilihan stack
- **Port conflict detection** — deteksi konflik port antar service sebelum deploy
- **Safety net berlapis** untuk operasi destructive (format disk):
  - Layer 1: Informasi dan preview dalam bahasa manusia
  - Layer 2: Warning eksplisit
  - Layer 3: Konfirmasi ketik ukuran disk (mirip GitHub delete repo)
  - Layer 4: Auto-backup partition table sebelum eksekusi
  - Layer 5: Info rollback jika gagal
- **Netplan rollback otomatis** — jika apply static IP gagal, config lama dipulihkan
- **SSH autostart toggle** — dockman otomatis terbuka saat SSH login
- **`dockman --bootstrap`** — CLI flag untuk langsung masuk wizard
- **`dockman --bootstrap <n>`** — langsung ke phase N (1-7)
- Menu entry **33** (Bootstrap Wizard) dan **34** (jalankan ulang phase) di numbered menu
- **`core/bootstrap.py`** — modul baru: state management, phase definitions, compose generator, helpers
- **`ui/bootstrap_wizard.py`** — modul baru: interactive wizard UI untuk 7 phases

### Stack yang didukung

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

### Changed
- Version bump: 2.3.0 → 3.0.0
- `build.py` diupdate: include `core/bootstrap.py` dan `ui/bootstrap_wizard.py`
- `main.py` diupdate: routing `--bootstrap` flag
- `cli_menu.py` diupdate: tambah section BOOTSTRAP di menu

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
- **`NameError: config_load`** di menu pilihan 31
- **Polkit authentication popup** saat generate server report
- **UFW detection** di server report: multi-fallback 5-step

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
