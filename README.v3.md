# dockman>_ v3

> **Branch ini adalah development branch untuk v3.0.0**  
> Untuk versi stable, gunakan branch `main` (v2.3.0).

---

## 🆕 Apa yang Baru di v3

v3 memperkenalkan **Bootstrap Wizard** — 7-phase wizard untuk setup media server dari nol, tanpa perlu tau Linux command.

```
Install Ubuntu/Debian
       ↓
bash <(curl -fsSL https://raw.githubusercontent.com/bugsdroid/dockman/v3/install-dockman.sh)
       ↓ (otomatis)
Bootstrap Wizard jalan
       ↓
Server siap
       ↓
SSH → dockman autostart → manage everything
```

---

## 🚀 Install v3 (Development)

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/bugsdroid/dockman/v3/install-dockman.sh)
```

Atau install + langsung jalankan Bootstrap Wizard:

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/bugsdroid/dockman/v3/install-dockman.sh) bootstrap
```

---

## ✨ Bootstrap Wizard - 7 Phases

| Phase | Nama | Isi |
|---|---|---|
| 1 | Persiapan Sistem | Update packages, hostname, timezone, locale, SSH hardening |
| 2 | Konfigurasi Jaringan | Static IP via netplan, UFW, mDNS, DNS over HTTPS |
| 3 | Manajemen Storage | Deteksi disk, format, mount via UUID, fstab, folder structure |
| 4 | Setup Docker | Install Docker, daemon config (log rotation), docker group |
| 5 | Pilih Stack Aplikasi | Media server, downloader, arr suite, reverse proxy, monitoring |
| 6 | Remote Access | Tailscale dan/atau Cloudflare Tunnel |
| 7 | Deploy & Verifikasi | Generate compose, `docker compose up`, health check, URL akses |

### Stack yang didukung

| Kategori | Pilihan |
|---|---|
| Media Server | Jellyfin ★, Plex, Emby |
| Downloader | qBittorrent ★, Deluge, SABnzbd |
| Arr Suite | Radarr, Sonarr, Lidarr, Bazarr |
| Indexer | Prowlarr ★, Jackett |
| Request Manager | Jellyseerr ★, Overseerr |
| Reverse Proxy | Nginx Proxy Manager ★, Caddy |
| Dashboard | Homarr ★, Heimdall |
| Monitoring | Portainer, Watchtower |
| DNS/Adblock | AdGuard Home ★, Pi-hole |
| Remote Access | Tailscale, Cloudflare Tunnel |

★ = Recommended

### Fitur Keamanan (Storage)

Operasi format disk dilindungi safety net berlapis:
1. **Informasi** — tampilkan detail disk, tandai OS disk
2. **Warning** — peringatan eksplisit data akan hilang
3. **Konfirmasi** — ketik ukuran disk untuk konfirmasi (e.g. `500GB`)
4. **Backup** — auto-backup partition table sebelum eksekusi
5. **Rollback** — info recovery jika gagal di tengah jalan

### Netplan Rollback Otomatis

Jika apply static IP gagal, konfigurasi jaringan lama dipulihkan otomatis. Server tidak akan lock out.

---

## 💻 Usage

```bash
dockman                    # Menu utama
dockman --bootstrap        # Mulai/lanjut Bootstrap Wizard
dockman --bootstrap 3      # Langsung ke Phase 3 (Storage)
dockman --tui              # TUI curses interaktif
dockman --setup            # Setup wizard config dockman
dockman ps                 # List container
dockman --help             # Semua command
```

### Bootstrap dari menu numbered

```
33. Bootstrap Wizard (setup server dari nol)
34. Jalankan ulang phase tertentu (1-7)
```

---

## 🔄 Resume-able

Progress wizard disimpan ke `~/.config/dockman/bootstrap_state.json`.  
Jika wizard diinterrupt, bisa dilanjutkan dari phase terakhir:

```bash
dockman --bootstrap   # otomatis detect dan tawarkan resume
```

---

## 🧪 Testing di VM

```bash
git clone -b v3 https://github.com/bugsdroid/dockman.git
cd dockman
pip install rich --break-system-packages
cd dockman_main && python3 build.py && cd ..

# Test otomatis
bash test-bootstrap.sh all

# Test interaktif
python3 dockman_main/dist/dockman.py --bootstrap
```

---

## 📁 Arsitektur v3

```
dockman_main/
├── core/
│   ├── config.py         Configuration manager
│   ├── docker.py         Docker data layer
│   ├── utils.py          Shell execution utilities
│   ├── bootstrap.py      ◄ BARU: state, phases, compose gen
│   └── serverdocs.py     Server report generator
└── ui/
    ├── curses_ui.py      TUI interaktif (--tui)
    ├── rich_ui.py        Output tabel & logs
    ├── cli_menu.py       3-column numbered menu
    ├── wizard.py         Setup wizard config
    └── bootstrap_wizard.py  ◄ BARU: 7-phase wizard UI
```

---

## ⚠️ Status

Branch ini dalam **aktif development**. Belum untuk production.  
Bug report dan feedback via GitHub Issues sangat diterima.

Untuk versi stable: gunakan branch `main`.

---

## 📄 Lisensi

MIT License
