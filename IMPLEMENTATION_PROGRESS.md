# DOCKMAN v3.0.0 - IMPLEMENTATION PROGRESS

**Branch:** `v3`  
**Base:** `main` (v2.3.0)  
**Philosophy:** "OSMC for Docker-based personal media servers"

---

## STATUS IMPLEMENTASI

```
Step 1: Bootstrap Wizard skeleton (7 phases, flow dasar)    ✅ DONE
Step 2: Network setup (netplan static IP + rollback)         ✅ DONE (di Phase 2)
Step 3: DoH setup (systemd-resolved)                        ✅ DONE (di Phase 2)
Step 4: Storage management (wizard mode)                    ✅ DONE (di Phase 3)
Step 5: Docker network setup                                ✅ DONE (di Phase 4)
Step 6: Stack selection & auto-generate compose             ✅ DONE (di Phase 5)
Step 7: Remote access (Tailscale + Cloudflare Tunnel)       ✅ DONE (di Phase 6)
Step 8: SSH Autostart toggle                                ✅ DONE (di Phase 7)
Step 9: Bundle installer (online)                           ⏳ TODO
Step 10: Testing di semua target OS                         ⏳ TODO
Step 11: Release v3.0.0                                     ⏳ TODO
```

---

## FILE BARU DI v3

```
dockman_main/
├── core/
│   └── bootstrap.py       <-- BARU: state, phases, compose generator, helpers
└── ui/
    └── bootstrap_wizard.py <-- BARU: interactive UI 7 phases
```

## FILE YANG DIUBAH DI v3

```
dockman_main/
├── core/config.py     VERSION 2.3.0 -> 3.0.0
├── ui/cli_menu.py     + menu entry 33 (Bootstrap) & 34 (phase tertentu)
├── main.py            + routing --bootstrap flag
└── build.py           + include bootstrap modules di SOURCE_FILES
```

---

## CARA TEST DI VM

```bash
# Clone branch v3
git clone -b v3 https://github.com/bugsdroid/dockman.git
cd dockman/dockman_main

# Build
python3 build.py

# Test CLI
python3 dist/dockman.py --version
python3 dist/dockman.py --help

# Test bootstrap wizard
python3 dist/dockman.py --bootstrap

# Test phase tertentu
python3 dist/dockman.py --bootstrap 5

# Test menu
python3 dist/dockman.py
# Pilih 33 untuk Bootstrap Wizard
```

## VM SPEC UNTUK TEST

```
RAM    : 2GB
CPU    : 2 core
Disk 1 : 20GB (OS)
Disk 2 : 10GB (untuk test storage management / format)
Network: Bridge adapter
OS     : Ubuntu 24.04 LTS (prioritas pertama)
```

---

## TODO SEBELUM RELEASE v3.0.0

### Testing
- [ ] Test Phase 1 (system prep) di Ubuntu 24.04 fresh
- [ ] Test Phase 2 (static IP) dengan rollback scenario
- [ ] Test Phase 3 (storage) dengan disk kedua di VM
- [ ] Test Phase 4 (Docker install) di VM tanpa Docker
- [ ] Test Phase 5 (stack) semua kombinasi compose generator
- [ ] Test Phase 6 (Tailscale) dengan auth key nyata
- [ ] Test Phase 7 (deploy) end-to-end
- [ ] Test resume wizard (interrupt & lanjut)
- [ ] Test `dockman --bootstrap 3` (langsung ke phase tertentu)

### Installer
- [ ] Update `install-dockman.sh` untuk include bootstrap state cleanup saat uninstall
- [ ] Tambah `dockman --bootstrap` di post-install message

### Dokumentasi
- [ ] Update README.md dengan fitur Bootstrap Wizard
- [ ] Update README.id.md
- [ ] Update TECHNICAL.md dengan arsitektur baru
- [ ] Screenshot/demo Bootstrap Wizard

### Polish
- [ ] Advanced mode untuk storage (Phase 3)
- [ ] Offline bundle installer
- [ ] Test di Debian 12, Ubuntu 22.04

---

## ARSITEKTUR v3

```
dockman_main/
├── core/               # Business logic - ZERO UI dependency
│   ├── config.py       # Configuration manager
│   ├── docker.py       # Docker data layer
│   ├── utils.py        # Shell execution utilities
│   ├── bootstrap.py    # Bootstrap state, phases, compose generator   [BARU v3]
│   └── serverdocs.py   # Server report generator
└── ui/                 # UI layer - ZERO business logic
    ├── curses_ui.py    # Interactive TUI (dockman --tui)
    ├── rich_ui.py      # Output tabel & logs
    ├── cli_menu.py     # 3-column numbered menu (default)
    ├── wizard.py       # Setup wizard (config dockman)
    └── bootstrap_wizard.py  # Bootstrap server wizard [BARU v3]
```

### State file
```
~/.config/dockman/
├── config.ini              # Config dockman (existing)
└── bootstrap_state.json    # Bootstrap wizard progress [BARU v3]
```

### Bootstrap state structure
```json
{
  "version": "3.0.0",
  "created_at": "2026-05-14T...",
  "updated_at": "2026-05-14T...",
  "current_phase": "stack_selection",
  "completed": false,
  "phases": {
    "system_prep":    {"status": "done",    "skipped": false, "data": {}},
    "network":        {"status": "done",    "skipped": false, "data": {}},
    "storage":        {"status": "done",    "skipped": false, "data": {}},
    "docker_setup":   {"status": "done",    "skipped": false, "data": {}},
    "stack_selection":{"status": "running", "skipped": false, "data": {}},
    "remote_access":  {"status": "pending", "skipped": false, "data": {}},
    "deploy":         {"status": "pending", "skipped": false, "data": {}}
  },
  "config": {
    "hostname": "mediaserver",
    "timezone": "Asia/Jakarta",
    "static_ip": "192.168.1.100/24",
    "media_mount": "/mnt/media",
    "media_server": "jellyfin",
    "downloader": "qbittorrent",
    "arr_suite": ["radarr", "sonarr"],
    ...
  }
}
```

---

*Buka chat baru dan upload IMPLEMENTATION_PROGRESS.md ini untuk lanjut ke step berikutnya.*
