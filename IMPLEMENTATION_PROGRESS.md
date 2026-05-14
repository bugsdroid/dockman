# DOCKMAN v3.0.0 - IMPLEMENTATION PROGRESS

**Branch:** `v3`  
**Base:** `main` (v2.3.0)  
**Philosophy:** "OSMC for Docker-based personal media servers"

---

## STATUS IMPLEMENTASI

```
Step 1: Bootstrap Wizard skeleton (7 phases, flow dasar)     ✅ DONE
Step 2: Network setup (netplan static IP + rollback)         ✅ DONE (Phase 2)
Step 3: DoH setup (systemd-resolved)                        ✅ DONE (Phase 2)
Step 4: Storage management (wizard mode + safety net)       ✅ DONE (Phase 3)
Step 5: Docker network setup                                ✅ DONE (Phase 4)
Step 6: Stack selection & auto-generate compose             ✅ DONE (Phase 5)
Step 7: Remote access (Tailscale + Cloudflare Tunnel)       ✅ DONE (Phase 6)
Step 8: SSH Autostart toggle                                ✅ DONE (Phase 7)
Step 9: Bundle installer update (v3.0)                      ✅ DONE
Step 9b: Test script (test-bootstrap.sh)                    ✅ DONE
Step 10: Testing di VM                                      ⏳ TODO (manual)
Step 11: Release v3.0.0                                     ⏳ TODO
```

---

## FILES BARU DI v3

```
dockman_main/
├── core/
│   └── bootstrap.py           <-- BARU: state, phases, compose gen, helpers
└── ui/
    └── bootstrap_wizard.py    <-- BARU: interactive UI 7 phases

test-bootstrap.sh               <-- BARU: test suite (build + unit + smoke)
IMPLEMENTATION_PROGRESS.md     <-- BARU: dokumen ini
```

## FILES YANG DIUBAH DI v3

```
dockman_main/
├── core/config.py      VERSION 2.3.0 -> 3.0.0
├── ui/cli_menu.py      + menu entry 33 (Bootstrap) & 34 (phase tertentu)
├── main.py             + routing --bootstrap flag
└── build.py            + include bootstrap modules di SOURCE_FILES

install-dockman.sh  v2.5 -> v3.0 (bootstrap support, uninstall cleanup state)
CHANGELOG.md        + v3.0.0 section
```

---

## CARA TEST DI VM

### Setup VM

```
OS     : Ubuntu 24.04 LTS (prioritas)
RAM    : 2GB minimum
CPU    : 2 core
Disk 1 : 20GB (OS)
Disk 2 : 10GB (untuk test storage management Phase 3)
Network: Bridge adapter (butuh IP dari router)
```

### Clone & Build

```bash
# Clone branch v3
git clone -b v3 https://github.com/bugsdroid/dockman.git
cd dockman

# Install dependency
pip install rich --break-system-packages

# Build
cd dockman_main && python3 build.py
cd ..
```

### Run test suite (non-interactive)

```bash
# Semua test otomatis
bash test-bootstrap.sh all

# Test build saja
bash test-bootstrap.sh build

# Test unit (logic, tanpa UI)
bash test-bootstrap.sh unit

# Test system check (environment)
bash test-bootstrap.sh system
```

### Run manual phase test (interaktif)

```bash
# Semua phase dari awal
python3 dockman_main/dist/dockman.py --bootstrap

# Phase tertentu
python3 dockman_main/dist/dockman.py --bootstrap 1   # System prep
python3 dockman_main/dist/dockman.py --bootstrap 2   # Network
python3 dockman_main/dist/dockman.py --bootstrap 3   # Storage
python3 dockman_main/dist/dockman.py --bootstrap 4   # Docker
python3 dockman_main/dist/dockman.py --bootstrap 5   # Stack selection
python3 dockman_main/dist/dockman.py --bootstrap 6   # Remote access
python3 dockman_main/dist/dockman.py --bootstrap 7   # Deploy

# Via test script (interactive)
bash test-bootstrap.sh phase 3
```

### Install & test terintegrasi

```bash
# Install dari branch v3
bash <(curl -fsSL https://raw.githubusercontent.com/bugsdroid/dockman/v3/install-dockman.sh)

# Verifikasi
dockman --version   # harus: DOCKMAN 3.0.0
dockman --help      # harus ada --bootstrap

# Jalankan bootstrap wizard
dockman --bootstrap
```

---

## CHECKLIST TEST MANUAL (per phase)

### Phase 1 - System Prep
- [ ] Update packages berjalan tanpa error
- [ ] Hostname berubah setelah diset
- [ ] Timezone berubah: `timedatectl` menunjukkan timezone baru
- [ ] Locale: `locale` menunjukkan en_US.UTF-8
- [ ] SSH hardening: test dengan `sudo sshd -T | grep -E 'permitrootlogin|passwordauth'`
- [ ] Phase bisa di-skip
- [ ] State tersimpan di `~/.config/dockman/bootstrap_state.json`

### Phase 2 - Network
- [ ] Interface terdeteksi dengan benar
- [ ] Validasi IP/CIDR: `192.168.1.100/24` diterima, `999.999.1.1/24` ditolak
- [ ] Preview netplan YAML ditampilkan sebelum apply
- [ ] Rollback berjalan jika apply gagal (test dengan IP invalid)
- [ ] UFW aktif: `sudo ufw status` menunjukkan active
- [ ] mDNS: `avahi-daemon` running, server bisa diping via `<hostname>.local`
- [ ] DoH: `resolvectl status` menunjukkan DNS over TLS
- [ ] Setiap sub-step bisa di-skip

### Phase 3 - Storage
- [ ] Disk terdeteksi: OS disk ditandai `[OS DISK]`, tidak bisa dipilih untuk format
- [ ] Wizard mode: folder structure dibuat di path yang benar
- [ ] Format disk (di Disk 2 VM): partisi dibuat, ext4, mount berhasil
- [ ] fstab diupdate dengan UUID dan `nofail,noatime`
- [ ] Folder structure default terbuat semua (movies, tv, music, downloads, dll)
- [ ] Safety net: konfirmasi eksplisit muncul sebelum format
- [ ] Skip: langsung lanjut tanpa format

### Phase 4 - Docker
- [ ] Docker install berjalan (di VM fresh tanpa Docker)
- [ ] User ditambahkan ke grup docker
- [ ] Daemon config diterapkan: `/etc/docker/daemon.json` ada
- [ ] Network mode bisa dipilih: bridge atau macvlan
- [ ] PUID/PGID otomatis detect dari current user

### Phase 5 - Stack Selection
- [ ] Semua 9 kategori muncul
- [ ] Single-select berjalan (media server, downloader, dll)
- [ ] Multi-select berjalan (arr suite, monitoring)
- [ ] Recommended item ditandai
- [ ] Port conflict terdeteksi (coba pilih Jellyfin + Emby)
- [ ] Summary pilihan ditampilkan di akhir

### Phase 6 - Remote Access
- [ ] Opsi A/B/C/0 berjalan
- [ ] Tailscale: install script berjalan
- [ ] Cloudflare: token tersimpan di state
- [ ] Skip berjalan

### Phase 7 - Deploy
- [ ] docker-compose.yml di-generate berdasarkan pilihan Phase 5
- [ ] YAML valid: `docker compose config` tidak error
- [ ] Preview YAML ditampilkan sebelum deploy
- [ ] `docker compose up -d` berjalan
- [ ] Summary URL akses ditampilkan
- [ ] SSH autostart di-toggle ke ~/.bash_profile

### End-to-End
- [ ] Interrupt wizard di tengah (Ctrl+C), state tersimpan
- [ ] Resume wizard dari phase yang tertunda
- [ ] Jalankan ulang phase tertentu dari menu (pilihan 34)
- [ ] Semua phase selesai: layar completed ditampilkan
- [ ] `dockman --bootstrap` pada server yang sudah selesai: tampilkan layar completed

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

### Wajib
- [ ] Semua checklist manual di atas lulus di Ubuntu 24.04
- [ ] Test di Debian 12
- [ ] Fix bug yang ditemukan selama testing

### Nice to have
- [ ] Advanced mode untuk storage (Phase 3) 
- [ ] Test di Ubuntu 22.04
- [ ] Test di Debian 11
- [ ] Offline bundle installer
- [ ] Update README.md dengan fitur Bootstrap Wizard
- [ ] Screenshot/GIF demo Bootstrap Wizard

---

*Upload file ini di chat baru untuk lanjut ke step berikutnya (testing & bugfix).*
