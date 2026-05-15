# DOCKMAN v3.0.0 - ROADMAP

**Philosophy:** "OSMC for Docker-based personal media servers"  
**Goal:** User install OS → install dockman → server siap, tanpa perlu tau Linux command  
**Repo:** https://github.com/bugsdroid/dockman  
**Current stable:** v2.3.0 (branch: `main`)  
**In development:** v3.0.0 (branch: `v3`)

---

## PROGRESS IMPLEMENTASI

```
✅  Step 1  Bootstrap Wizard skeleton (7 phases, resume-able, per-phase rerun)
✅  Step 2  Network setup (netplan static IP + rollback otomatis)
✅  Step 3  DoH via systemd-resolved (Cloudflare/Google/Quad9)
✅  Step 4  Storage management (wizard mode, safety net 5 lapis, UUID fstab)
✅  Step 5  Docker setup (install, daemon config, group, network mode)
✅  Step 6  Stack selection & auto-generate docker-compose.yml
✅  Step 7  Remote access (Tailscale + Cloudflare Tunnel)
✅  Step 8  SSH Autostart toggle (~/.bash_profile)
✅  Step 9  Installer update v3.0 (bootstrap support, uninstall cleanup)
✅  Step 9b Test suite (test-bootstrap.sh: build + unit + smoke + integration)
⏳  Step 10 Testing di VM (manual checklist)
⏳  Step 11 Bugfix dari hasil testing
⏳  Step 12 Release v3.0.0
```

---

## ARSITEKTUR v3

```
dockman_main/
├── core/                  # Business logic - ZERO UI dependency
│   ├── config.py            # Configuration manager
│   ├── docker.py            # Docker data layer
│   ├── utils.py             # Shell execution utilities
│   ├── bootstrap.py         # ◄ BARU: state, phases, compose gen, helpers
│   └── serverdocs.py        # Server report generator
├── ui/                    # UI layer - ZERO business logic
│   ├── curses_ui.py         # TUI interaktif (dockman --tui)
│   ├── rich_ui.py           # Output tabel & logs
│   ├── cli_menu.py          # 3-column numbered menu (default)
│   ├── wizard.py            # Setup wizard config dockman
│   └── bootstrap_wizard.py  # ◄ BARU: interactive 7-phase wizard UI
├── main.py                # Entry point + CLI router (+ --bootstrap)
└── build.py               # Compiler: multi-file -> single dockman.py

install-dockman.sh           # Universal installer v3.0
test-bootstrap.sh            # ◄ BARU: test suite
README.v3.md                 # ◄ BARU: README khusus branch v3
IMPLEMENTATION_PROGRESS.md  # ◄ BARU: progress & checklist testing
```

---

## FITUR BARU v3.0.0

### Bootstrap Wizard (7 Phases)
*Core dari semua fitur baru*

```
Phase 1: System Prep
  - Update system packages
  - Set hostname, timezone, locale
  - SSH hardening (optional, dengan warning)

Phase 2: Network Setup
  - Static IP via netplan (+ rollback otomatis jika gagal)
  - DoH via systemd-resolved (Cloudflare/Google/Quad9)
  - UFW basic rules (SSH, HTTP, HTTPS)
  - mDNS via avahi-daemon (.local hostname)

Phase 3: Storage Management
  - Deteksi & display disk (tandai OS disk, jangan format!)
  - Format & mount dengan UUID di fstab (nofail,noatime)
  - Safety net 5 lapis untuk operasi destructive
  - Auto-create folder structure: movies/tv/music/downloads/config

Phase 4: Docker Setup
  - Install Docker (via get.docker.com)
  - Daemon config: log rotation, storage driver overlay2
  - Tambah user ke docker group
  - Pilih network mode: bridge atau macvlan

Phase 5: Stack Selection
  - Media Server   : Jellyfin / Plex / Emby
  - Downloader     : qBittorrent / Deluge / SABnzbd
  - Arr Suite      : Radarr / Sonarr / Lidarr / Bazarr
  - Indexer        : Prowlarr / Jackett
  - Request Manager: Jellyseerr / Overseerr
  - Reverse Proxy  : Nginx Proxy Manager / Caddy
  - Dashboard      : Homarr / Heimdall
  - Monitoring     : Portainer / Watchtower
  - DNS/Adblock    : AdGuard Home / Pi-hole
  + Port conflict detection sebelum deploy

Phase 6: Remote Access
  - Tailscale (akses personal, zero config)
  - Cloudflare Tunnel (akses publik, domain sendiri, HTTPS)
  - Bisa pilih salah satu atau keduanya

Phase 7: Deploy & Verify
  - Auto-generate docker-compose.yml berdasarkan pilihan Phase 5
  - docker compose up -d
  - Health check semua container (tunggu 30 detik)
  - Tampilkan summary: service, URL akses, default credentials
  - Toggle SSH autostart
```

**Fitur wizard:**
- **Resume-able** — progress disimpan ke `~/.config/dockman/bootstrap_state.json`
- **Per-phase rerun** — `dockman --bootstrap 3` langsung ke Phase 3
- **Skip** — setiap phase bisa di-skip
- **Safety first** — operasi destructive punya konfirmasi berlapis

---

## DISTRIBUTION PLAN

```
install-dockman.sh v3.0
  - Clone branch v3 dari GitHub (--depth=1)
  - Build dockman.py dari source
  - Install ke /usr/local/bin/dockman
  - Tawarkan Bootstrap Wizard setelah install
  - Support: install, uninstall, check, build, bootstrap
```

**Target OS (prioritas):**
```
Ubuntu 24.04 LTS (Noble)   ✓ primary target
Ubuntu 22.04 LTS (Jammy)   ✓
Debian 12 (Bookworm)       ✓
Debian 11 (Bullseye)       ✓
```

---

## TESTING SETUP

**VM spec:**
```
OS     : Ubuntu 24.04 LTS
RAM    : 2GB
CPU    : 2 core
Disk 1 : 20GB (OS)
Disk 2 : 10GB (test storage management)
Network: Bridge adapter
```

**Test commands:**
```bash
# Automated tests
bash test-bootstrap.sh all       # semua test
bash test-bootstrap.sh build     # test build
bash test-bootstrap.sh unit      # test unit
bash test-bootstrap.sh system    # cek environment

# Interactive test
python3 dockman_main/dist/dockman.py --bootstrap
python3 dockman_main/dist/dockman.py --bootstrap 3

# Install test
bash install-dockman.sh
dockman --version    # harus: DOCKMAN 3.0.0
dockman --bootstrap
```

---

## TODO SEBELUM RELEASE

**Step 10 - Testing di VM:**
- [ ] Automated test suite: `bash test-bootstrap.sh all` PASS
- [ ] Manual checklist Phase 1-7 di Ubuntu 24.04
- [ ] Test install dari curl: `bash <(curl ...) bootstrap`
- [ ] Test resume wizard (interrupt Ctrl+C di tengah, lanjut)
- [ ] Test per-phase rerun (menu 34)
- [ ] Test uninstall + cleanup state
- [ ] Test di Debian 12

**Step 11 - Bugfix:**
- [ ] Fix semua issue yang ditemukan di Step 10
- [ ] Re-run test suite setelah fix

**Step 12 - Release:**
- [ ] Merge branch `v3` ke `main`
- [ ] Tag v3.0.0
- [ ] Update README.md dengan fitur Bootstrap Wizard
- [ ] Update README.id.md
- [ ] Buat GitHub Release dengan changelog

---

## CATATAN PENTING UNTUK IMPLEMENTASI

1. **Semua fitur baru compatible dengan existing** - tidak break fitur v2.x
2. **Arsitektur tetap sama** - `core/` tanpa UI, `ui/` tanpa business logic
3. **Build system tetap** - `build.py` compile ke satu `dockman.py`
4. **Safety first** - storage & network operations punya rollback
5. **Bahasa Indonesia** - semua UI text tetap Bahasa Indonesia
6. **Resume-able** - semua operasi panjang bisa dilanjutkan
7. **Test di VM dulu** - wajib sebelum merge ke main

---

## VERSION PLAN

```
v2.3.x  → current stable (main branch, bugfix only)
v3.0.0  → in development (v3 branch) - Bootstrap Wizard
v3.1.x  → planned - Advanced storage mode, offline installer
```

---

*Dokumen ini diupdate setiap milestone selesai.*  
*Untuk lanjut testing: clone branch v3 dan ikuti petunjuk di IMPLEMENTATION_PROGRESS.md*
