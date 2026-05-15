# DOCKMAN v3.0.0 - IMPLEMENTATION PROGRESS

**Branch:** `v3`  
**Base:** `main` (v2.3.0)  
**Philosophy:** "OSMC for Docker-based personal media servers"

---

## STATUS IMPLEMENTASI

```
✅  Step 1   Bootstrap Wizard skeleton (7 phases, resume-able, per-phase rerun)
✅  Step 2   Network setup (netplan static IP + rollback otomatis)
✅  Step 3   DoH via systemd-resolved (Cloudflare/Google/Quad9)
✅  Step 4   Storage management (wizard mode, safety net 5 lapis, UUID fstab)
✅  Step 5   Docker setup (install, daemon config, group, network mode)
✅  Step 6   Stack selection & auto-generate docker-compose.yml
✅  Step 7   Remote access (Tailscale + Cloudflare Tunnel)
✅  Step 8   SSH Autostart toggle (~/.bash_profile)
✅  Step 9   Installer update v3.0 (bootstrap support, uninstall cleanup)
✅  Step 9b  Test suite (test-bootstrap.sh: build + unit + smoke + integration)
✅  Step 9c  Hapus TUI mode (curses) dari v3
⏳  Step 10  Testing di VM (manual checklist)
⏳  Step 11  Bugfix dari hasil testing
⏳  Step 12  Release v3.0.0
```

---

## FILES DI v3

### Baru
```
dockman_main/core/bootstrap.py       state management, phases, compose gen, helpers
dockman_main/ui/bootstrap_wizard.py  interactive UI 7 phases
test-bootstrap.sh                    test suite (50+ test cases)
README.v3.md                         README branch v3
IMPLEMENTATION_PROGRESS.md          dokumen ini
```

### Diubah
```
dockman_main/core/config.py    VERSION 2.3.0 -> 3.0.0
dockman_main/ui/cli_menu.py    + menu 33 (Bootstrap) & 34 (phase rerun)
dockman_main/main.py           + --bootstrap flag, hapus TUI routing
dockman_main/build.py          + bootstrap modules, - curses_ui, - curses import
install-dockman.sh             v2.5 -> v3.0
CHANGELOG.md                   + v3.0.0 section
ROADMAP.md                     updated
```

### Dikosongkan (bukan dihapus, agar git history jelas)
```
dockman_main/ui/curses_ui.py   TUI dihapus di v3, file berisi komentar penjelasan
```

---

## CARA TEST DI VM

### Setup VM
```
OS     : Ubuntu 24.04 LTS (prioritas)
RAM    : 2GB minimum
CPU    : 2 core
Disk 1 : 20GB (OS)
Disk 2 : 10GB (test storage management Phase 3)
Network: Bridge adapter
```

### Clone & Build
```bash
git clone -b v3 https://github.com/bugsdroid/dockman.git
cd dockman
pip install rich --break-system-packages
cd dockman_main && python3 build.py && cd ..
```

### Automated test (non-interactive)
```bash
bash test-bootstrap.sh all          # semua test
bash test-bootstrap.sh build        # test build & syntax
bash test-bootstrap.sh unit         # test unit logic
bash test-bootstrap.sh system       # cek environment VM
bash test-bootstrap.sh integration  # test built binary
```

### Manual test (interaktif)
```bash
# Semua phase dari awal
python3 dockman_main/dist/dockman.py --bootstrap

# Phase tertentu langsung
python3 dockman_main/dist/dockman.py --bootstrap 1
python3 dockman_main/dist/dockman.py --bootstrap 2
python3 dockman_main/dist/dockman.py --bootstrap 3
python3 dockman_main/dist/dockman.py --bootstrap 4
python3 dockman_main/dist/dockman.py --bootstrap 5
python3 dockman_main/dist/dockman.py --bootstrap 6
python3 dockman_main/dist/dockman.py --bootstrap 7

# Verifikasi TUI dihapus
python3 dockman_main/dist/dockman.py --tui  # harus tampil pesan info, bukan error

# Via install
bash install-dockman.sh
dockman --version    # DOCKMAN 3.0.0
dockman --bootstrap
```

---

## CHECKLIST TEST MANUAL

### Pre-flight
- [ ] `bash test-bootstrap.sh all` → semua PASS
- [ ] `dockman --version` → `DOCKMAN 3.0.0`
- [ ] `dockman --help` → ada `--bootstrap`, tidak ada `--tui` (atau ada pesan info)
- [ ] `dockman --tui` → tampil pesan info bahwa TUI tidak tersedia, exit 0
- [ ] `dockman` → menu 3 kolom muncul dengan entry 33 & 34

### Phase 1 - System Prep
- [ ] Update packages berjalan
- [ ] Hostname berubah: `hostname` menunjukkan nilai baru
- [ ] Timezone berubah: `timedatectl` menunjukkan timezone baru
- [ ] Locale: `locale` menunjukkan en_US.UTF-8
- [ ] SSH hardening (opsional, test dengan server yang punya SSH key)
- [ ] Skip berjalan, state tersimpan

### Phase 2 - Network
- [ ] Interface terdeteksi dengan benar
- [ ] Validasi IP: `192.168.1.100/24` diterima, `999.999.1.1` ditolak
- [ ] Preview netplan YAML tampil sebelum apply
- [ ] Rollback berjalan jika apply gagal
- [ ] UFW aktif: `sudo ufw status` → active
- [ ] mDNS: `ping <hostname>.local` berhasil dari perangkat lain
- [ ] DoH: `resolvectl status` → DNS over TLS
- [ ] Skip tiap sub-step berjalan

### Phase 3 - Storage
- [ ] OS disk ditandai `[OS DISK]`, tidak bisa dipilih untuk format
- [ ] Disk 2 bisa dipilih, safety confirmation muncul
- [ ] Format + mount + fstab berhasil (cek `lsblk` dan `cat /etc/fstab`)
- [ ] Folder structure terbuat: `movies/ tv/ music/ downloads/ config/`
- [ ] Skip (pilih 0): langsung ke folder structure tanpa format

### Phase 4 - Docker
- [ ] Install Docker berhasil di VM fresh
- [ ] User ditambah ke grup docker
- [ ] `/etc/docker/daemon.json` ada dengan log rotation
- [ ] PUID/PGID terdeteksi dari current user

### Phase 5 - Stack
- [ ] Semua 9 kategori tampil
- [ ] Single-select dan multi-select berjalan
- [ ] Port conflict terdeteksi (pilih Jellyfin + Emby → harus warning port 8096)
- [ ] Summary pilihan tampil di akhir

### Phase 6 - Remote Access
- [ ] Pilihan A/B/C/0 berjalan
- [ ] Tailscale: install script berjalan
- [ ] Cloudflare: token tersimpan di state
- [ ] Skip berjalan

### Phase 7 - Deploy
- [ ] `docker-compose.yml` di-generate sesuai pilihan Phase 5
- [ ] `docker compose config` tidak error (YAML valid)
- [ ] Preview YAML tampil sebelum deploy
- [ ] `docker compose up -d` berjalan
- [ ] Summary URL akses tampil
- [ ] SSH autostart: cek `~/.bash_profile` ada snippet dockman

### End-to-End
- [ ] Interrupt Ctrl+C di tengah phase → state tersimpan
- [ ] Resume: `dockman --bootstrap` → layar resume tampil, bisa lanjut
- [ ] Per-phase rerun dari menu: pilih `34` → pilih nomor phase → phase jalan
- [ ] Semua phase selesai → layar completed tampil dengan summary URL
- [ ] Uninstall: `bash install-dockman.sh uninstall` → tanya hapus state juga

---

## BOOTSTRAP STATE STRUCTURE

```json
{
  "version": "3.0.0",
  "created_at": "2026-05-14T...",
  "updated_at": "2026-05-14T...",
  "current_phase": "stack_selection",
  "completed": false,
  "phases": {
    "system_prep":     {"status": "done",    "skipped": false, "data": {}},
    "network":         {"status": "done",    "skipped": false, "data": {}},
    "storage":         {"status": "done",    "skipped": false, "data": {}},
    "docker_setup":    {"status": "done",    "skipped": false, "data": {}},
    "stack_selection": {"status": "running", "skipped": false, "data": {}},
    "remote_access":   {"status": "pending", "skipped": false, "data": {}},
    "deploy":          {"status": "pending", "skipped": false, "data": {}}
  },
  "config": {
    "hostname": "mediaserver",
    "timezone": "Asia/Jakarta",
    "static_ip": "192.168.1.100/24",
    "gateway": "192.168.1.1",
    "media_mount": "/mnt/media",
    "puid": "1000",
    "pgid": "1000",
    "media_server": "jellyfin",
    "downloader": "qbittorrent",
    "arr_suite": ["radarr", "sonarr"],
    "indexer": "prowlarr",
    "reverse_proxy": "nginxproxymanager",
    "monitoring": ["portainer", "watchtower"],
    "tailscale_enabled": false,
    "cloudflare_enabled": false
  }
}
```

---

## TODO SEBELUM RELEASE v3.0.0

**Step 10 - Testing di VM:**
- [ ] `bash test-bootstrap.sh all` → PASS
- [ ] Manual checklist Phase 1-7 di Ubuntu 24.04
- [ ] Test install dari curl + bootstrap
- [ ] Test resume (interrupt & lanjut)
- [ ] Test per-phase rerun
- [ ] Test uninstall + cleanup state
- [ ] Test di Debian 12

**Step 11 - Bugfix:**
- [ ] Fix semua issue dari Step 10
- [ ] Re-run test suite setelah fix

**Step 12 - Release:**
- [ ] Merge `v3` → `main`
- [ ] Tag `v3.0.0`
- [ ] Update README.md
- [ ] GitHub Release dengan changelog

---

*Upload file ini di chat baru untuk lanjut ke step testing & bugfix.*
