"""
ui/bootstrap_wizard.py - Interactive Bootstrap Wizard UI untuk Dockman v3.0.0

7-phase wizard untuk setup server dari nol.
UI layer saja - semua business logic ada di core/bootstrap.py.
"""

import os
import sys
import time
from pathlib import Path
from typing import List, Dict, Optional, Tuple

import core.config as config
from core.bootstrap import (
    BootstrapState, PHASES, STATUS_DONE, STATUS_SKIPPED, STATUS_PENDING, STATUS_FAILED,
    get_system_info, get_network_interfaces, get_current_ip, get_default_gateway,
    validate_ip_cidr, validate_ip, get_netplan_files,
    get_available_disks, get_disk_uuid, get_user_ids,
    is_docker_installed, is_docker_running,
    get_stack_options, check_port_conflicts,
    generate_compose_yaml, create_folder_structure,
    generate_access_summary, DEFAULT_FOLDERS,
    BOOTSTRAP_VERSION,
)
from core.utils import run_cmd, run_interactive, sanitize_input


# ── Warna ANSI ──────────────────────────────────────────────────────────────────

if sys.stdout.isatty():
    C = {
        "reset":  "\033[0m",
        "bold":   "\033[1m",
        "dim":    "\033[2m",
        "cyan":   "\033[1;36m",
        "green":  "\033[1;32m",
        "yellow": "\033[1;33m",
        "red":    "\033[1;31m",
        "blue":   "\033[1;34m",
        "white":  "\033[1;37m",
        "dgray":  "\033[2;37m",
    }
else:
    C = {k: "" for k in ["reset","bold","dim","cyan","green","yellow","red","blue","white","dgray"]}

W = 66  # lebar banner


# ── Print helpers ──────────────────────────────────────────────────────────────

def _line(char="="):    print(f"  {C['cyan']}{char * W}{C['reset']}")
def _dline(char="-"):   print(f"  {C['dim']}{char * W}{C['reset']}")
def _ok(msg):           print(f"  {C['green']}[OK]{C['reset']}  {msg}")
def _warn(msg):         print(f"  {C['yellow']}[!!]{C['reset']}  {msg}")
def _err(msg):          print(f"  {C['red']}[XX]{C['reset']}  {msg}")
def _info(msg):         print(f"  {C['cyan']}[..]{C['reset']}  {msg}")
def _note(msg):         print(f"  {C['dgray']}  {msg}{C['reset']}")
def _nl():              print()


def _header(title: str, subtitle: str = ""):
    os.system("clear")
    _line()
    pad = max(0, (W - len(title)) // 2)
    print(f"  {C['cyan']}{' ' * pad}{C['bold']}{title}{C['reset']}")
    if subtitle:
        pad2 = max(0, (W - len(subtitle)) // 2)
        print(f"  {C['dgray']}{' ' * pad2}{subtitle}{C['reset']}")
    _line()
    _nl()


def _phase_header(phase_num: int, phase_title: str, total: int = 7):
    """Header per phase dengan progress indicator."""
    os.system("clear")
    _line()
    title = f"DOCKMAN v{BOOTSTRAP_VERSION}  —  Bootstrap Wizard"
    pad   = max(0, (W - len(title)) // 2)
    print(f"  {C['cyan']}{' ' * pad}{C['bold']}{title}{C['reset']}")
    _line()
    _nl()
    # Progress bar fases
    bar = ""
    for i in range(1, total + 1):
        if i < phase_num:
            bar += f"{C['green']}█{C['reset']}"
        elif i == phase_num:
            bar += f"{C['cyan']}█{C['reset']}"
        else:
            bar += f"{C['dim']}░{C['reset']}"
    print(f"  Phase {phase_num}/{total}  {bar}  {C['bold']}{phase_title}{C['reset']}")
    _nl()
    _dline()
    _nl()


def _ask(prompt: str, default: str = "", required: bool = False) -> str:
    """Input dengan default value. Return stripped string."""
    disp = f" [{C['dgray']}{default}{C['reset']}]" if default else ""
    while True:
        try:
            val = input(f"  {C['bold']}{prompt}{C['reset']}{disp}: ").strip()
        except (EOFError, KeyboardInterrupt):
            _nl()
            return default
        if val:
            return val
        if default:
            return default
        if required:
            _err("Wajib diisi.")
        else:
            return ""


def _ask_yn(prompt: str, default: bool = False) -> bool:
    """Tanya yes/no. Return bool."""
    hint  = f"Y/n" if default else "y/N"
    dflt  = "y" if default else "n"
    while True:
        try:
            val = input(f"  {C['bold']}{prompt}{C['reset']} [{hint}]: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            return default
        if not val:
            return default
        if val in ("y", "yes"):
            return True
        if val in ("n", "no"):
            return False
        _err("Ketik y atau n.")


def _pick(prompt: str, options: List[Dict], multi: bool = False,
          current: object = None) -> object:
    """
    Tampilkan pilihan bernomor, return id yang dipilih.
    multi=True  -> return List[str]
    multi=False -> return str
    """
    _nl()
    for i, opt in enumerate(options, 1):
        rec  = f" {C['green']}(recommended){C['reset']}" if opt.get("recommended") else ""
        name = f"{C['bold']}{opt['name']}{C['reset']}"
        desc = f"  {C['dgray']}{opt['desc']}{C['reset']}" if opt.get("desc") else ""

        if multi and current and opt["id"] in current:
            mark = f"{C['green']}[x]{C['reset']}"
        elif not multi and current and opt["id"] == current:
            mark = f"{C['green']}[*]{C['reset']}"
        else:
            mark = f"{C['dim']}[ ]{C['reset']}"

        print(f"  {mark} {C['dgray']}{i}{C['reset']}. {name}{rec}")
        if desc:
            print(f"         {desc}")

    _nl()
    if multi:
        _note("Pilih beberapa dengan angka dipisah koma, contoh: 1,2")
        _note("Enter tanpa input = tidak memilih apapun")
        try:
            raw = input(f"  {C['bold']}{prompt}{C['reset']}: ").strip()
        except (EOFError, KeyboardInterrupt):
            return current or []
        if not raw:
            return []
        result = []
        for part in raw.split(","):
            part = part.strip()
            if part.isdigit():
                idx = int(part) - 1
                if 0 <= idx < len(options):
                    result.append(options[idx]["id"])
        return result
    else:
        while True:
            try:
                raw = input(f"  {C['bold']}{prompt}{C['reset']}: ").strip()
            except (EOFError, KeyboardInterrupt):
                return options[0]["id"]
            if raw.isdigit():
                idx = int(raw) - 1
                if 0 <= idx < len(options):
                    return options[idx]["id"]
            _err(f"Masukkan angka 1-{len(options)}.")


def _pause(msg: str = "Tekan Enter untuk lanjut..."):
    try:
        input(f"\n  {C['dgray']}{msg}{C['reset']}")
    except (EOFError, KeyboardInterrupt):
        pass


def _confirm_destructive(label: str, confirm_text: str) -> bool:
    """
    Safety layer 3: konfirmasi eksplisit dengan ketik teks.
    Dipakai untuk operasi destructive (format disk, dll).
    """
    _nl()
    _warn(f"PERINGATAN: {label}")
    _warn("Operasi ini TIDAK BISA di-undo!")
    _nl()
    _note(f"Ketik  '{confirm_text}'  untuk konfirmasi, atau Enter untuk batal:")
    try:
        val = input(f"  > ").strip()
    except (EOFError, KeyboardInterrupt):
        return False
    if val == confirm_text:
        return True
    _info("Dibatalkan.")
    return False


# ══════════════════════════════════════════════════════════════════════════════
#  WIZARD ENTRY POINT
# ══════════════════════════════════════════════════════════════════════════════

def run_bootstrap_wizard(phase_id: Optional[str] = None):
    """
    Entry point wizard.
    phase_id = None  -> mulai/lanjut dari phase pending berikutnya
    phase_id = str   -> langsung ke phase tertentu (re-run)
    """
    state = BootstrapState.load()

    # Jika phase_id spesifik diminta (dari menu settings)
    if phase_id:
        _run_phase(state, phase_id)
        return

    # Cek apakah ada progress sebelumnya
    if state.exists() and not state.completed:
        _show_resume_screen(state)
        return

    if state.completed:
        _show_completed_screen(state)
        return

    # Fresh start
    _show_welcome(state)


def _show_welcome(state: BootstrapState):
    """Layar selamat datang sebelum wizard dimulai."""
    _header(
        "DOCKMAN Bootstrap Wizard",
        f"Setup media server dari nol  |  v{BOOTSTRAP_VERSION}"
    )

    print(f"  Wizard ini akan memandu kamu setup server secara lengkap:")
    _nl()
    for p in PHASES:
        num   = p["number"]
        title = p["title"]
        desc  = p["description"]
        print(f"  {C['cyan']}{num}{C['reset']}. {C['bold']}{title}{C['reset']}")
        print(f"     {C['dgray']}{desc}{C['reset']}")
    _nl()
    _dline()
    _nl()

    # Pre-flight check
    _info("Mengecek sistem...")
    info = get_system_info()
    _nl()
    _show_preflight(info)
    _nl()

    # Warning jika sudo tidak tersedia
    if info.get("sudo") != "ya":
        _warn("User tidak punya sudo! Beberapa operasi akan gagal.")
        _warn("Jalankan: sudo dockman --bootstrap")
        _nl()
        if not _ask_yn("Lanjut tetap?", default=False):
            return

    if not _ask_yn("Mulai Bootstrap Wizard?", default=True):
        return

    # Jalankan phase satu per satu
    _run_all_phases(state)


def _show_preflight(info: Dict):
    """Tampilkan hasil pre-flight check."""
    checks = [
        ("OS",           info.get("os",           "?")),
        ("Hostname",     info.get("hostname",     "?")),
        ("Timezone",     info.get("timezone",     "?")),
        ("Python",       info.get("python",       "?")),
        ("Docker",       info.get("docker",       "belum install")),
        ("Docker group", info.get("docker_group", "tidak")),
        ("Internet",     info.get("internet",     "?")),
        ("Sudo",         info.get("sudo",         "tidak")),
    ]
    for label, val in checks:
        ok = val not in ("tidak", "tidak ada", "tidak (perlu!)", "belum install", "?")
        icon = f"{C['green']}[OK]{C['reset']}" if ok else f"{C['yellow']}[!!]{C['reset']}"
        print(f"  {icon}  {label:<16} {val}")


def _show_resume_screen(state: BootstrapState):
    """Layar resume jika ada progress sebelumnya."""
    _header("DOCKMAN Bootstrap Wizard", "Progress ditemukan")

    done    = state.done_phases()
    pending = state.pending_phases()

    print(f"  Progress tersimpan dari sesi sebelumnya:")
    _nl()

    for p in PHASES:
        pid    = p["id"]
        status = state.phases[pid]["status"]
        if status == STATUS_DONE:
            icon = f"{C['green']}✓{C['reset']}"
        elif status == STATUS_SKIPPED:
            icon = f"{C['yellow']}→{C['reset']} (skip)"
        else:
            icon = f"{C['dim']}○{C['reset']}"
        print(f"  {icon}  Phase {p['number']}: {p['title']}")

    _nl()
    _dline()
    _nl()

    opts = [
        ("1", f"Lanjut dari phase berikutnya ({_pending_phase_title(state)})"),
        ("2", "Pilih phase tertentu untuk dijalankan ulang"),
        ("3", "Mulai ulang dari awal (reset semua progress)"),
        ("0", "Batal"),
    ]
    for k, v in opts:
        print(f"  {C['cyan']}{k}{C['reset']}. {v}")
    _nl()

    try:
        choice = input(f"  {C['bold']}Pilih{C['reset']}: ").strip()
    except (EOFError, KeyboardInterrupt):
        return

    if choice == "1":
        _run_all_phases(state)
    elif choice == "2":
        _pick_and_run_phase(state)
    elif choice == "3":
        if _confirm_destructive("Semua progress wizard akan dihapus.", "RESET"):
            state = BootstrapState.reset()
            _show_welcome(state)
    # 0 = kembali


def _show_completed_screen(state: BootstrapState):
    """Layar setelah semua phase selesai."""
    _header("Bootstrap Selesai!", "Server siap digunakan")
    _ok("Semua phase wizard berhasil dijalankan.")
    _nl()

    summary = generate_access_summary(state)
    if summary:
        print(f"  {C['bold']}Akses layanan kamu:{C['reset']}")
        _nl()
        for entry in summary:
            svc  = entry["service"]
            url  = entry["url"]
            note = entry.get("note", "")
            mdns = entry.get("url_mdns", "")
            print(f"  {C['cyan']}▶{C['reset']}  {C['bold']}{svc:<20}{C['reset']}  {url}")
            if mdns:
                print(f"              {C['dgray']}atau: {mdns}{C['reset']}")
            if note:
                print(f"              {C['dgray']}{note}{C['reset']}")
        _nl()

    _dline()
    opts = [
        ("1", "Jalankan ulang phase tertentu"),
        ("2", "Lihat docker compose status"),
        ("0", "Kembali ke menu dockman"),
    ]
    for k, v in opts:
        print(f"  {C['cyan']}{k}{C['reset']}. {v}")
    _nl()
    try:
        choice = input(f"  {C['bold']}Pilih{C['reset']}: ").strip()
    except (EOFError, KeyboardInterrupt):
        return
    if choice == "1":
        _pick_and_run_phase(state)
    elif choice == "2":
        compose_dir = config.get_compose_dir()
        if compose_dir:
            run_interactive(f"cd '{compose_dir}' && docker compose ps")
            _pause()


def _pending_phase_title(state: BootstrapState) -> str:
    nxt = state.next_pending_phase()
    if nxt:
        for p in PHASES:
            if p["id"] == nxt:
                return p["title"]
    return "selesai"


def _pick_and_run_phase(state: BootstrapState):
    """Pilih phase tertentu untuk dijalankan."""
    _nl()
    print(f"  {C['bold']}Pilih phase:{C['reset']}")
    _nl()
    for p in PHASES:
        pid    = p["id"]
        status = state.phases[pid]["status"]
        if status == STATUS_DONE:
            mark = f"{C['green']}✓{C['reset']}"
        elif status == STATUS_SKIPPED:
            mark = f"{C['yellow']}s{C['reset']}"
        else:
            mark = f"{C['dim']}○{C['reset']}"
        print(f"  {mark} {C['cyan']}{p['number']}{C['reset']}. {p['title']}")
    _nl()

    try:
        raw = input(f"  {C['bold']}Nomor phase (0=batal){C['reset']}: ").strip()
    except (EOFError, KeyboardInterrupt):
        return

    if not raw.isdigit():
        return
    num = int(raw)
    if num == 0:
        return
    for p in PHASES:
        if p["number"] == num:
            _run_phase(state, p["id"])
            return


# ══════════════════════════════════════════════════════════════════════════════
#  PHASE RUNNER
# ══════════════════════════════════════════════════════════════════════════════

def _run_all_phases(state: BootstrapState):
    """Jalankan semua phase yang belum done, berurutan."""
    for p in PHASES:
        if state.is_phase_done(p["id"]):
            continue
        _run_phase(state, p["id"])
        # Tanya lanjut ke phase berikutnya jika bukan phase terakhir
        if p["id"] != PHASES[-1]["id"] and not state.all_done():
            _nl()
            if not _ask_yn(f"Lanjut ke phase berikutnya?", default=True):
                _info("Progress disimpan. Jalankan 'dockman --bootstrap' untuk melanjutkan.")
                return

    if state.all_done():
        state.completed = True
        state.save()
        _show_completed_screen(state)


PHASE_HANDLERS = {}


def _run_phase(state: BootstrapState, phase_id: str):
    """Dispatch ke handler phase yang sesuai."""
    handler = PHASE_HANDLERS.get(phase_id)
    if handler:
        state.set_phase_status(phase_id, "running")
        state.current_phase = phase_id
        state.save()
        try:
            handler(state)
        except KeyboardInterrupt:
            _nl()
            _warn("Phase dibatalkan. Progress disimpan.")
            state.save()
    else:
        _warn(f"Phase '{phase_id}' belum diimplementasikan.")
        if _ask_yn("Skip phase ini?", default=True):
            state.skip_phase(phase_id)
            state.save()


# ══════════════════════════════════════════════════════════════════════════════
#  PHASE 1 - SYSTEM PREP
# ══════════════════════════════════════════════════════════════════════════════

def _phase_system_prep(state: BootstrapState):
    _phase_header(1, "Persiapan Sistem")

    # ── [1] Update packages ───────────────────────────────────────────────────────
    print(f"  {C['bold']}[1/5] Update System Packages{C['reset']}")
    _dline()
    _note("Akan menjalankan: apt-get update && apt-get upgrade -y")
    _note("(atau equivalent untuk distro kamu)")
    _nl()
    if _ask_yn("Update packages sekarang?", default=True):
        _info("Menjalankan update... (bisa beberapa menit)")
        ret = run_interactive(
            "sudo apt-get update -qq && sudo apt-get upgrade -y 2>/dev/null || "
            "sudo dnf upgrade -y 2>/dev/null || "
            "sudo pacman -Syu --noconfirm 2>/dev/null || "
            "echo 'Selesai (atau tidak ada package manager yang cocok)'"
        )
        if ret == 0:
            _ok("Packages berhasil diupdate.")
        else:
            _warn("Update selesai (mungkin ada warning, cek output di atas).")
        state.set_phase_data("system_prep", "packages_updated", True)
    else:
        _info("Skip update packages.")
    _nl()

    # ── [2] Hostname ─────────────────────────────────────────────────────────────
    print(f"  {C['bold']}[2/5] Hostname{C['reset']}")
    _dline()
    current_host = state.config.get("hostname") or config.get_hostname()
    _note(f"Hostname saat ini: {current_host}")
    _note("Hostname dipakai untuk identifikasi server dan mDNS (.local).")
    _nl()
    new_host = _ask("Hostname baru", default=current_host)
    new_host = sanitize_input(new_host) or current_host
    if new_host != current_host:
        out, err, code = run_cmd(f"sudo hostnamectl set-hostname '{new_host}' 2>/dev/null")
        if code == 0:
            _ok(f"Hostname diset ke: {new_host}")
            config.set_value("general", "hostname", new_host)
        else:
            _warn(f"Gagal set hostname: {err or 'permission denied?'}")
    state.config["hostname"] = new_host
    state.save()
    _nl()

    # ── [3] Timezone ─────────────────────────────────────────────────────────────
    print(f"  {C['bold']}[3/5] Timezone{C['reset']}")
    _dline()
    cur_tz = state.config.get("timezone", "Asia/Jakarta")
    _note(f"Timezone saat ini: {cur_tz}")
    _note("Contoh: Asia/Jakarta, Asia/Singapore, America/New_York")
    _note("Lihat daftar: timedatectl list-timezones")
    _nl()
    new_tz = _ask("Timezone", default=cur_tz)
    if new_tz and new_tz != cur_tz:
        _, err, code = run_cmd(f"sudo timedatectl set-timezone '{new_tz}' 2>/dev/null")
        if code == 0:
            _ok(f"Timezone diset ke: {new_tz}")
            state.config["timezone"] = new_tz
        else:
            _warn(f"Gagal set timezone: {err}")
            _note("Manual: sudo timedatectl set-timezone Asia/Jakarta")
    state.save()
    _nl()

    # ── [4] Locale ────────────────────────────────────────────────────────────────
    print(f"  {C['bold']}[4/5] Locale{C['reset']}")
    _dline()
    _note("Locale default untuk server: en_US.UTF-8 (recommended)")
    _nl()
    if _ask_yn("Set locale ke en_US.UTF-8?", default=True):
        cmds = [
            "sudo locale-gen en_US.UTF-8 2>/dev/null",
            "sudo update-locale LANG=en_US.UTF-8 2>/dev/null",
        ]
        for cmd in cmds:
            run_cmd(cmd)
        _ok("Locale diset ke en_US.UTF-8.")
        state.config["locale"] = "en_US.UTF-8"
    state.save()
    _nl()

    # ── [5] SSH Hardening ─────────────────────────────────────────────────────────
    print(f"  {C['bold']}[5/5] SSH Hardening (Opsional){C['reset']}")
    _dline()
    _note("Menonaktifkan login root via SSH dan password authentication.")
    _note("PASTIKAN kamu sudah setup SSH key sebelum mengaktifkan ini!")
    _note("Jika tidak, kamu bisa terkunci dari server sendiri.")
    _nl()
    if _ask_yn("Aktifkan SSH hardening?", default=False):
        if _ask_yn("Yakin? Pastikan SSH key sudah terpasang.", default=False):
            sshd_conf = "/etc/ssh/sshd_config"
            cmds = [
                f"sudo sed -i 's/^#\\?PermitRootLogin.*/PermitRootLogin no/' {sshd_conf}",
                f"sudo sed -i 's/^#\\?PasswordAuthentication.*/PasswordAuthentication no/' {sshd_conf}",
                "sudo systemctl reload sshd 2>/dev/null || sudo service ssh reload 2>/dev/null",
            ]
            success = True
            for cmd in cmds:
                _, err, code = run_cmd(cmd)
                if code != 0:
                    success = False
                    _warn(f"Warning: {err}")
            if success:
                _ok("SSH hardening aktif. Root login & password auth dinonaktifkan.")
                state.config["ssh_hardening"] = True
            else:
                _warn("SSH hardening sebagian gagal. Cek /etc/ssh/sshd_config manual.")
    state.save()
    _nl()

    # Selesai
    _dline()
    _ok("Phase 1 (Persiapan Sistem) selesai!")
    state.set_phase_status("system_prep", STATUS_DONE)
    state.save()
    _pause()


PHASE_HANDLERS["system_prep"] = _phase_system_prep


# ══════════════════════════════════════════════════════════════════════════════
#  PHASE 2 - NETWORK
# ══════════════════════════════════════════════════════════════════════════════

def _phase_network(state: BootstrapState):
    _phase_header(2, "Konfigurasi Jaringan")

    # ── [1] Static IP ──────────────────────────────────────────────────────────
    print(f"  {C['bold']}[1/4] Static IP via Netplan{C['reset']}")
    _dline()
    _note("Static IP sangat dianjurkan untuk server.")
    _note("Tanpa static IP, alamat server bisa berubah setelah reboot.")
    _nl()

    # Deteksi interface
    ifaces = get_network_interfaces()
    if not ifaces:
        _warn("Tidak ada interface jaringan aktif yang terdeteksi.")
    else:
        print(f"  Interface yang terdeteksi:")
        _nl()
        for i, iface in enumerate(ifaces, 1):
            status = f"{C['green']}UP{C['reset']}" if iface["up"] else f"{C['red']}DOWN{C['reset']}"
            print(f"  {C['cyan']}{i}{C['reset']}. {iface['name']:<12} {status:<20} {iface['ip']}")
        _nl()

    if _ask_yn("Setup static IP sekarang?", default=True):
        # Pilih interface
        cur_iface = state.config.get("interface", "")
        if ifaces:
            raw = _ask("Interface (nama atau nomor)", default=ifaces[0]["name"])
            if raw.isdigit() and 1 <= int(raw) <= len(ifaces):
                iface_name = ifaces[int(raw) - 1]["name"]
            else:
                iface_name = raw
        else:
            iface_name = _ask("Nama interface", default="eth0", required=True)

        # Ambil IP saat ini sebagai default
        cur_ip = get_current_ip(iface_name)
        gw     = get_default_gateway()

        _nl()
        _note(f"IP saat ini: {cur_ip}  |  Gateway: {gw}")
        _note("Format IP: 192.168.1.100/24  (sertakan prefix /24 atau /16 dll)")
        _nl()

        static_ip = ""
        while True:
            static_ip = _ask("Static IP/CIDR", default=cur_ip or "192.168.1.100/24", required=True)
            if validate_ip_cidr(static_ip):
                break
            _err(f"Format tidak valid: {static_ip}. Contoh: 192.168.1.100/24")

        gateway = ""
        while True:
            gateway = _ask("Gateway", default=gw or "192.168.1.1", required=True)
            if validate_ip(gateway):
                break
            _err(f"Format gateway tidak valid: {gateway}")

        dns_input = _ask("DNS servers (pisah koma)", default="1.1.1.1,8.8.8.8")
        dns_list  = [d.strip() for d in dns_input.split(",") if d.strip()]

        state.config["interface"]  = iface_name
        state.config["static_ip"]  = static_ip
        state.config["gateway"]    = gateway
        state.config["dns_servers"] = dns_list
        state.save()

        # Preview netplan config
        _nl()
        _note("Preview konfigurasi netplan yang akan dibuat:")
        _nl()
        netplan_content = _generate_netplan(iface_name, static_ip, gateway, dns_list)
        for line in netplan_content.splitlines():
            print(f"    {C['dgray']}{line}{C['reset']}")
        _nl()

        # Safety: konfirmasi sebelum apply
        _warn("Setelah apply, koneksi SSH akan terputus sesaat.")
        _warn("Jika IP baru tidak bisa diakses, jalankan 'sudo netplan revert' dari konsol.")
        _nl()

        if _ask_yn("Apply konfigurasi static IP?", default=False):
            _apply_netplan(iface_name, netplan_content, state)
        else:
            _info("Static IP tidak di-apply. Config tersimpan untuk nanti.")
    else:
        _info("Skip static IP setup.")
    _nl()

    # ── [2] UFW ────────────────────────────────────────────────────────────────────
    print(f"  {C['bold']}[2/4] Firewall (UFW){C['reset']}")
    _dline()
    _note("UFW (Uncomplicated Firewall) untuk proteksi dasar.")
    _note("Akan membuka port: SSH (22), HTTP (80), HTTPS (443)")
    _nl()
    if _ask_yn("Setup UFW?", default=True):
        cmds = [
            "sudo apt-get install -y ufw 2>/dev/null || sudo dnf install -y ufw 2>/dev/null",
            "sudo ufw --force reset",
            "sudo ufw default deny incoming",
            "sudo ufw default allow outgoing",
            "sudo ufw allow ssh",
            "sudo ufw allow 80/tcp",
            "sudo ufw allow 443/tcp",
            "sudo ufw --force enable",
        ]
        ok_count = 0
        for cmd in cmds:
            _, _, code = run_cmd(cmd, timeout=30)
            if code == 0:
                ok_count += 1
        if ok_count >= 5:
            _ok("UFW aktif. SSH, HTTP, HTTPS diperbolehkan.")
            state.config["ufw_enabled"] = True
        else:
            _warn("UFW setup sebagian gagal. Cek status: sudo ufw status")
    else:
        _info("Skip UFW.")
    state.save()
    _nl()

    # ── [3] mDNS ────────────────────────────────────────────────────────────────────
    print(f"  {C['bold']}[3/4] mDNS (.local hostname){C['reset']}")
    _dline()
    hostname = state.config.get("hostname", "server")
    _note(f"mDNS memungkinkan akses server via: {hostname}.local")
    _note("Menggunakan avahi-daemon (Bonjour/Zeroconf).")
    _nl()
    if _ask_yn("Install & aktifkan mDNS?", default=True):
        _, _, code1 = run_cmd(
            "sudo apt-get install -y avahi-daemon 2>/dev/null || "
            "sudo dnf install -y avahi avahi-tools 2>/dev/null",
            timeout=60
        )
        _, _, code2 = run_cmd("sudo systemctl enable --now avahi-daemon 2>/dev/null")
        if code2 == 0:
            _ok(f"mDNS aktif. Server bisa diakses via: {hostname}.local")
            state.config["mdns_enabled"] = True
        else:
            _warn("avahi-daemon gagal diaktifkan.")
    else:
        _info("Skip mDNS.")
    state.save()
    _nl()

    # ── [4] DoH ──────────────────────────────────────────────────────────────────────
    print(f"  {C['bold']}[4/4] DNS over HTTPS (Opsional){C['reset']}")
    _dline()
    _note("Mengenkripsi DNS query via systemd-resolved.")
    _note("Provider: Cloudflare (1.1.1.1) - recommended")
    _nl()
    if _ask_yn("Setup DNS over HTTPS?", default=False):
        providers = {
            "1": ("Cloudflare", "1.1.1.1#cloudflare-dns.com", "1.0.0.1#cloudflare-dns.com"),
            "2": ("Google",     "8.8.8.8#dns.google",         "8.8.4.4#dns.google"),
            "3": ("Quad9",      "9.9.9.9#dns.quad9.net",      "149.112.112.112#dns.quad9.net"),
        }
        _nl()
        for k, (name, p, s) in providers.items():
            print(f"  {C['cyan']}{k}{C['reset']}. {name}  ({p.split('#')[0]})")        
        _nl()
        choice = _ask("Pilih provider", default="1")
        prov   = providers.get(choice, providers["1"])

        resolved_conf = (
            "[Resolve]\n"
            f"DNS={prov[1]} {prov[2]}\n"
            "DNSOverTLS=yes\n"
            "DNSSEC=yes\n"
            "FallbackDNS=8.8.8.8#dns.google\n"
        )
        _, _, code = run_cmd(
            f"echo '{resolved_conf}' | sudo tee /etc/systemd/resolved.conf.d/doh.conf >/dev/null"
            " && sudo mkdir -p /etc/systemd/resolved.conf.d",
            timeout=10
        )
        run_cmd("sudo systemctl restart systemd-resolved 2>/dev/null")
        _ok(f"DoH aktif via {prov[0]}.")
        state.config["doh_enabled"]  = True
        state.config["doh_provider"] = prov[0].lower()
    else:
        _info("Skip DoH.")
    state.save()
    _nl()

    _dline()
    _ok("Phase 2 (Konfigurasi Jaringan) selesai!")
    state.set_phase_status("network", STATUS_DONE)
    state.save()
    _pause()


def _generate_netplan(interface: str, ip_cidr: str, gateway: str,
                      dns_list: List[str]) -> str:
    dns_str = ", ".join(f"{d}" for d in dns_list)
    return (
        f"network:\n"
        f"  version: 2\n"
        f"  ethernets:\n"
        f"    {interface}:\n"
        f"      dhcp4: false\n"
        f"      addresses:\n"
        f"        - {ip_cidr}\n"
        f"      routes:\n"
        f"        - to: default\n"
        f"          via: {gateway}\n"
        f"      nameservers:\n"
        f"        addresses: [{dns_str}]\n"
    )


def _apply_netplan(interface: str, content: str, state: BootstrapState):
    """Apply netplan dengan rollback otomatis jika gagal."""
    conf_path = f"/etc/netplan/99-dockman-{interface}.yaml"

    # Backup semua netplan yang ada
    existing = get_netplan_files()
    for f in existing:
        run_cmd(f"sudo cp '{f}' '{f}.bak_dockman' 2>/dev/null")

    # Tulis config baru
    _, err, code = run_cmd(
        f"echo '{content}' | sudo tee {conf_path} >/dev/null && "
        f"sudo chmod 600 {conf_path}"
    )
    if code != 0:
        _err(f"Gagal menulis {conf_path}: {err}")
        return

    # Apply dengan try
    _info("Applying netplan... (koneksi akan terputus sesaat)")
    _, err, code = run_cmd("sudo netplan apply 2>/dev/null", timeout=15)

    if code == 0:
        _ok("Netplan berhasil di-apply!")
        ip_part = state.config.get("static_ip", "").split("/")[0]
        if ip_part:
            _ok(f"Server sekarang bisa diakses di: {ip_part}")
        state.set_phase_data("network", "netplan_applied", True)
        state.save()
    else:
        _err("Netplan apply gagal. Mencoba rollback...")
        for f in existing:
            run_cmd(f"sudo cp '{f}.bak_dockman' '{f}' 2>/dev/null")
        run_cmd(f"sudo rm -f {conf_path}")
        run_cmd("sudo netplan apply 2>/dev/null", timeout=15)
        _warn("Rollback dilakukan. Konfigurasi lama dipulihkan.")


PHASE_HANDLERS["network"] = _phase_network


# ══════════════════════════════════════════════════════════════════════════════
#  PHASE 3 - STORAGE
# ══════════════════════════════════════════════════════════════════════════════

def _phase_storage(state: BootstrapState):
    _phase_header(3, "Manajemen Storage")

    # Pilih mode
    print(f"  {C['bold']}Mode Storage:{C['reset']}")
    _nl()
    print(f"  {C['cyan']}1{C['reset']}. {C['bold']}Wizard Mode{C['reset']} (recommended)")
    _note(    "     Struktur folder & mount options sudah dioptimalkan untuk media server")
    _note(    "     Cocok untuk: Radarr, Sonarr, Jellyfin, qBittorrent")
    _nl()
    print(f"  {C['cyan']}2{C['reset']}. {C['bold']}Advanced Mode{C['reset']}")
    _note(    "     Tentukan sendiri mount point dan folder structure")
    _nl()
    print(f"  {C['cyan']}0{C['reset']}. Skip (gunakan storage yang sudah ada)")
    _nl()

    try:
        mode_choice = input(f"  {C['bold']}Pilih{C['reset']}: ").strip()
    except (EOFError, KeyboardInterrupt):
        return

    if mode_choice == "0":
        _info("Skip storage setup.")
        state.config["storage_mode"] = "skip"
        state.skip_phase("storage")
        state.save()
        return

    mode = "wizard" if mode_choice != "2" else "advanced"
    state.config["storage_mode"] = mode
    _nl()

    # Deteksi disk
    _info("Mendeteksi disk yang tersedia...")
    disks = get_available_disks()
    _nl()

    if not disks:
        _warn("Tidak ada disk yang terdeteksi. Pastikan disk terhubung.")
        _pause()
        return

    print(f"  Disk yang tersedia:")
    _nl()
    for i, disk in enumerate(disks, 1):
        os_flag = f"  {C['red']}[OS DISK]{C['reset']}" if disk["is_os_disk"] else ""
        vendor  = f" {disk['vendor']}" if disk.get("vendor") else ""
        model   = f" {disk['model']}"  if disk.get("model")  else ""
        print(f"  {C['cyan']}{i}{C['reset']}. {C['bold']}{disk['path']}{C['reset']}  "
              f"{disk['size']:<8}{vendor}{model}{os_flag}")
        if disk.get("mountpoint"):
            _note(f"     Mount: {disk['mountpoint']}")
        if disk.get("fstype"):
            _note(f"     FS: {disk['fstype']}")
    _nl()

    # Pilih disk
    media_mount = _ask("Mount point untuk media",
                       default=state.config.get("media_mount", "/mnt/media"))
    state.config["media_mount"] = media_mount

    # Pilih disk target
    _nl()
    raw = _ask("Nomor disk yang akan dipakai (0=skip format, langsung mount)",
               default="0")

    if raw == "0" or not raw.isdigit():
        # Tidak format, langsung buat folder structure
        _info(f"Membuat folder structure di {media_mount}...")
        created = create_folder_structure(media_mount)
        for f in created:
            _ok(f"  {f}")
        _show_folder_summary(media_mount)
        state.set_phase_data("storage", "folders_created", True)
        state.set_phase_data("storage", "media_mount", media_mount)
        state.save()
    else:
        idx = int(raw) - 1
        if 0 <= idx < len(disks):
            disk = disks[idx]
            _run_disk_format(disk, media_mount, state)
        else:
            _err("Nomor disk tidak valid.")

    state.set_phase_status("storage", STATUS_DONE)
    state.save()
    _nl()
    _dline()
    _ok("Phase 3 (Manajemen Storage) selesai!")
    _pause()


def _run_disk_format(disk: Dict, mount_point: str, state: BootstrapState):
    """Format dan mount disk dengan safety net berlapis."""
    path = disk["path"]
    size = disk["size"]

    _nl()
    _dline()

    # Safety Layer 1: Informasi
    print(f"  {C['bold']}Informasi Disk:{C['reset']}")
    _nl()
    print(f"  Disk     : {C['bold']}{path}{C['reset']}")
    print(f"  Ukuran   : {size}")
    if disk.get("vendor") or disk.get("model"):
        print(f"  Model    : {disk.get('vendor','')} {disk.get('model','')}")
    if disk["is_os_disk"]:
        _err("INI ADALAH DISK OS! FORMAT AKAN MENGHANCURKAN SISTEM!")
        _err("Batalkan sekarang!")
        _pause("Tekan Enter untuk batal...")
        return
    _nl()

    # Safety Layer 2: Preview dalam bahasa manusia
    _warn(f"Disk {path} ({size}) akan diformat.")
    _warn("SEMUA DATA DI DISK INI AKAN HILANG PERMANEN.")
    _nl()
    print(f"  Yang akan dilakukan:")
    print(f"  1. Buat partisi di {path}")
    print(f"  2. Format dengan ext4")
    print(f"  3. Mount ke {mount_point}")
    print(f"  4. Tambah ke /etc/fstab (dengan nofail,noatime)")
    print(f"  5. Buat folder structure media")
    _nl()

    # Safety Layer 3: Konfirmasi eksplisit ketik ukuran disk
    if not _confirm_destructive(
        f"Format disk {path} ({size})",
        size.replace(" ", "")
    ):
        _info("Format dibatalkan.")
        return

    # Safety Layer 4: Backup partition table
    _info("Backup partition table...")
    pt_backup = f"/root/dockman-ptbackup-{path.replace('/', '_')}.bak"
    run_cmd(f"sudo sfdisk -d {path} > {pt_backup} 2>/dev/null")
    _info(f"Partition table tersimpan di: {pt_backup}")

    # Eksekusi
    _info(f"Memformat {path}...")

    # Buat partisi
    _, err, code = run_cmd(
        f"echo 'type=83' | sudo sfdisk {path} 2>/dev/null",
        timeout=30
    )
    if code != 0:
        _err(f"Gagal membuat partisi: {err}")
        return

    part = f"{path}1"
    time.sleep(1)  # Tunggu kernel update partition table

    # Format ext4
    _, err, code = run_cmd(f"sudo mkfs.ext4 -F {part} 2>/dev/null", timeout=120)
    if code != 0:
        _err(f"Gagal format ext4: {err}")
        return
    _ok(f"{part} berhasil diformat dengan ext4.")

    # Ambil UUID
    uuid = get_disk_uuid(part)
    if not uuid:
        _warn("Gagal mendapatkan UUID. Menggunakan device path.")
        fstab_device = part
    else:
        fstab_device = f"UUID={uuid}"
        state.config["media_uuid"] = uuid

    # Mount
    run_cmd(f"sudo mkdir -p {mount_point}")
    _, err, code = run_cmd(f"sudo mount {part} {mount_point} 2>/dev/null")
    if code != 0:
        _err(f"Gagal mount {part} ke {mount_point}: {err}")
        return
    _ok(f"Berhasil di-mount ke {mount_point}.")

    # fstab
    fstab_line = f"{fstab_device} {mount_point} ext4 defaults,nofail,noatime 0 2"
    # Hapus entry lama jika ada
    run_cmd(f"sudo sed -i '\\|{mount_point}|d' /etc/fstab 2>/dev/null")
    _, err, code = run_cmd(f"echo '{fstab_line}' | sudo tee -a /etc/fstab >/dev/null")
    if code == 0:
        _ok(f"fstab diupdate: {fstab_line}")
    else:
        _warn(f"Gagal update fstab: {err}")

    # Folder structure
    _nl()
    _info("Membuat folder structure...")
    created = create_folder_structure(mount_point)
    for f in created:
        _ok(f"  {f}")

    _show_folder_summary(mount_point)

    state.config["media_disk"]  = path
    state.config["media_mount"] = mount_point
    state.set_phase_data("storage", "disk_formatted", True)
    state.set_phase_data("storage", "partition", part)
    state.set_phase_data("storage", "uuid", uuid)
    state.set_phase_data("storage", "mount_point", mount_point)
    state.set_phase_data("storage", "fstab_entry", fstab_line)
    state.save()


def _show_folder_summary(base: str):
    _nl()
    _note(f"Folder structure di {base}:")
    for f in DEFAULT_FOLDERS:
        _note(f"  {base}/{f}")


PHASE_HANDLERS["storage"] = _phase_storage


# ══════════════════════════════════════════════════════════════════════════════
#  PHASE 4 - DOCKER SETUP
# ══════════════════════════════════════════════════════════════════════════════

def _phase_docker_setup(state: BootstrapState):
    _phase_header(4, "Setup Docker")

    # ── Install Docker ─────────────────────────────────────────────────────────────
    print(f"  {C['bold']}[1/3] Install Docker{C['reset']}")
    _dline()
    if is_docker_installed():
        ver, _, _ = run_cmd("docker --version 2>/dev/null")
        _ok(f"Docker sudah terinstall: {ver}")
    else:
        _note("Docker belum terinstall. Menginstall via get.docker.com...")
        _nl()
        if _ask_yn("Install Docker?", default=True):
            _info("Mendownload dan menginstall Docker... (bisa beberapa menit)")
            ret = run_interactive(
                "curl -fsSL https://get.docker.com | sudo sh 2>/dev/null || "
                "sudo apt-get install -y docker.io 2>/dev/null"
            )
            if ret == 0 and is_docker_installed():
                _ok("Docker berhasil diinstall!")
                run_cmd("sudo systemctl enable --now docker 2>/dev/null")
            else:
                _err("Docker gagal diinstall. Cek koneksi internet.")
                _note("Manual: curl -fsSL https://get.docker.com | sudo sh")
    _nl()

    # Tambah user ke docker group
    ids = get_user_ids()
    user = ids["user"]
    state.config["puid"] = ids["puid"]
    state.config["pgid"] = ids["pgid"]
    state.save()

    out, _, _ = run_cmd(f"groups {user} 2>/dev/null")
    if "docker" not in out.split():
        _info(f"Menambahkan user '{user}' ke grup docker...")
        _, err, code = run_cmd(f"sudo usermod -aG docker {user} 2>/dev/null")
        if code == 0:
            _ok(f"User '{user}' ditambahkan ke grup docker.")
            _warn("PENTING: Logout & login ulang agar grup aktif!")
            _note("Atau jalankan: newgrp docker")
        else:
            _warn(f"Gagal: {err}")
    else:
        _ok(f"User '{user}' sudah ada di grup docker.")
    _nl()

    # ── Daemon config ───────────────────────────────────────────────────────────────
    print(f"  {C['bold']}[2/3] Docker Daemon Config{C['reset']}")
    _dline()
    _note("Konfigurasi log rotation dan storage driver.")
    _note("Mencegah log container memenuhi disk.")
    _nl()
    if _ask_yn("Apply Docker daemon config (log rotation)?", default=True):
        daemon_cfg = (
            '{\n'
            '  "log-driver": "json-file",\n'
            '  "log-opts": {\n'
            '    "max-size": "10m",\n'
            '    "max-file": "3"\n'
            '  },\n'
            '  "storage-driver": "overlay2"\n'
            '}\n'
        )
        run_cmd("sudo mkdir -p /etc/docker")
        _, err, code = run_cmd(
            f"echo '{daemon_cfg}' | sudo tee /etc/docker/daemon.json >/dev/null"
        )
        if code == 0:
            run_cmd("sudo systemctl reload docker 2>/dev/null || sudo systemctl restart docker 2>/dev/null")
            _ok("Docker daemon config berhasil di-apply.")
        else:
            _warn(f"Gagal: {err}")
    _nl()

    # ── Docker network ─────────────────────────────────────────────────────────────
    print(f"  {C['bold']}[3/3] Docker Network{C['reset']}")
    _dline()
    _nl()
    print(f"  {C['cyan']}1{C['reset']}. {C['bold']}Bridge (default){C['reset']} - akses via IP:port")
    _note(    "     Paling simpel, cocok untuk hampir semua setup")
    _nl()
    print(f"  {C['cyan']}2{C['reset']}. {C['bold']}Macvlan{C['reset']} - container dapat IP sendiri")
    _note(    "     Untuk Plex/DLNA yang butuh discovery di jaringan lokal")
    _nl()
    net_choice = _ask("Pilih network mode", default="1")
    if net_choice == "2":
        state.config["docker_network"] = "macvlan"
        _info("Macvlan dipilih. Konfigurasi detail tersedia di docker-compose.yml yang digenerate.")
    else:
        state.config["docker_network"] = "bridge"
    state.save()
    _nl()

    _dline()
    _ok("Phase 4 (Setup Docker) selesai!")
    state.set_phase_status("docker_setup", STATUS_DONE)
    state.save()
    _pause()


PHASE_HANDLERS["docker_setup"] = _phase_docker_setup


# ══════════════════════════════════════════════════════════════════════════════
#  PHASE 5 - STACK SELECTION
# ══════════════════════════════════════════════════════════════════════════════

def _phase_stack_selection(state: BootstrapState):
    _phase_header(5, "Pilih Stack Aplikasi")

    opts = get_stack_options()
    cfg  = state.config

    sections = [
        ("media_server",    "[1/9] Media Server",       False),
        ("downloader",      "[2/9] Downloader",         False),
        ("arr_suite",       "[3/9] Arr Suite",          True),
        ("indexer",         "[4/9] Indexer",            False),
        ("request_manager", "[5/9] Request Manager",    False),
        ("reverse_proxy",   "[6/9] Reverse Proxy",      False),
        ("dashboard",       "[7/9] Dashboard",          False),
        ("monitoring",      "[8/9] Monitoring",         True),
        ("dns_adblock",     "[9/9] DNS / Ad Blocker",   False),
    ]

    for key, label, multi in sections:
        print(f"  {C['bold']}{label}{C['reset']}")
        _dline()
        current = cfg.get(key, [] if multi else "")
        result  = _pick(f"Pilih nomor", opts[key], multi=multi, current=current)
        cfg[key] = result
        state.save()
        _nl()

    # Cek konflik port
    all_services = _collect_selected_services(cfg)
    conflicts    = check_port_conflicts(all_services)
    if conflicts:
        _nl()
        _warn(f"Ditemukan {len(conflicts)} konflik port:")
        for c in conflicts:
            _warn(f"  {c['message']}")
        _note("Port bisa diubah di docker-compose.yml yang digenerate.")
        _nl()
    else:
        _ok("Tidak ada konflik port.")

    # Summary pilihan
    _nl()
    _dline()
    print(f"  {C['bold']}Ringkasan pilihan kamu:{C['reset']}")
    _nl()
    for key, label, multi in sections:
        val = cfg.get(key, "")
        if isinstance(val, list):
            display = ", ".join(val) if val else "(tidak dipilih)"
        else:
            display = val or "(tidak dipilih)"
        icon = f"{C['green']}✓{C['reset']}" if val and val != "none" and val != [] else f"{C['dim']}-{C['reset']}"
        print(f"  {icon}  {label.split('] ')[1]:<20} {display}")

    _nl()
    _dline()
    _ok("Phase 5 (Stack Selection) selesai!")
    state.set_phase_status("stack_selection", STATUS_DONE)
    state.save()
    _pause()


def _collect_selected_services(cfg: Dict) -> List[str]:
    services = []
    for key in ("media_server", "downloader", "indexer", "request_manager",
                "reverse_proxy", "dashboard", "dns_adblock"):
        val = cfg.get(key, "")
        if val and val != "none":
            services.append(val)
    services.extend(cfg.get("arr_suite", []))
    services.extend(cfg.get("monitoring", []))
    if cfg.get("cloudflare_enabled"):
        services.append("cloudflared")
    return services


PHASE_HANDLERS["stack_selection"] = _phase_stack_selection


# ══════════════════════════════════════════════════════════════════════════════
#  PHASE 6 - REMOTE ACCESS
# ══════════════════════════════════════════════════════════════════════════════

def _phase_remote_access(state: BootstrapState):
    _phase_header(6, "Remote Access")

    print(f"  Pilih cara akses server dari luar jaringan lokal:")
    _nl()
    print(f"  {C['cyan']}A{C['reset']}. {C['bold']}Tailscale{C['reset']} - akses personal, zero config, VPN mesh")
    _note(    "     Cocok untuk akses pribadi dari HP/laptop manapun")
    _note(    "     Gratis untuk personal (hingga 3 user, 100 device)")
    _nl()
    print(f"  {C['cyan']}B{C['reset']}. {C['bold']}Cloudflare Tunnel{C['reset']} - akses publik via domain sendiri, HTTPS otomatis")
    _note(    "     Cocok untuk share ke keluarga/teman dengan URL yang rapi")
    _note(    "     Butuh: domain + akun Cloudflare (keduanya bisa gratis)")
    _nl()
    print(f"  {C['cyan']}C{C['reset']}. {C['bold']}Keduanya{C['reset']}")
    print(f"  {C['cyan']}0{C['reset']}. Skip")
    _nl()

    try:
        choice = input(f"  {C['bold']}Pilih{C['reset']}: ").strip().upper()
    except (EOFError, KeyboardInterrupt):
        choice = "0"

    do_tailscale  = choice in ("A", "C")
    do_cloudflare = choice in ("B", "C")

    if do_tailscale:
        _setup_tailscale(state)

    if do_cloudflare:
        _setup_cloudflare(state)

    if not do_tailscale and not do_cloudflare:
        _info("Skip remote access.")

    _nl()
    _dline()
    _ok("Phase 6 (Remote Access) selesai!")
    state.set_phase_status("remote_access", STATUS_DONE)
    state.save()
    _pause()


def _setup_tailscale(state: BootstrapState):
    _nl()
    print(f"  {C['bold']}--- Tailscale ---{C['reset']}")
    _nl()

    # Cek apakah sudah terinstall
    out, _, code = run_cmd("tailscale version 2>/dev/null")
    if code == 0:
        _ok(f"Tailscale sudah terinstall: {out}")
    else:
        _info("Menginstall Tailscale...")
        ret = run_interactive(
            "curl -fsSL https://tailscale.com/install.sh | sudo sh 2>/dev/null"
        )
        if ret != 0:
            _err("Install Tailscale gagal. Manual: https://tailscale.com/download")
            return
        _ok("Tailscale berhasil diinstall.")

    _nl()
    _note("Kamu bisa login dengan dua cara:")
    _note("1. Auth key (untuk server headless, tanpa browser)")
    _note("2. Login interaktif (buka URL di browser)")
    _nl()

    auth_key = _ask("Auth key dari tailscale.com/settings/keys (Enter = login interaktif)")
    if auth_key:
        _, err, code = run_cmd(
            f"sudo tailscale up --authkey={auth_key} --accept-routes 2>/dev/null",
            timeout=30
        )
        if code == 0:
            _ok("Tailscale berhasil terhubung!")
            state.config["tailscale_enabled"]  = True
            state.config["tailscale_authkey"]   = "(saved)"
        else:
            _warn(f"Tailscale connect gagal: {err}")
    else:
        _info("Membuka Tailscale login...")
        run_interactive("sudo tailscale up 2>/dev/null")
        _ok("Tailscale login selesai (jika berhasil).")
        state.config["tailscale_enabled"] = True

    state.save()


def _setup_cloudflare(state: BootstrapState):
    _nl()
    print(f"  {C['bold']}--- Cloudflare Tunnel ---{C['reset']}")
    _nl()
    _note("Yang kamu butuhkan:")
    _note("1. Domain yang pointing ke Cloudflare nameservers")
    _note("2. Cloudflare API Token dengan permission: Zone.DNS (Edit)")
    _note("   Buat di: https://dash.cloudflare.com/profile/api-tokens")
    _nl()
    _note("Atau gunakan cara mudah: Cloudflare Zero Trust > Networks > Tunnels")
    _note("Dapatkan tunnel token dari dashboard, paste di sini.")
    _nl()

    domain = _ask("Domain kamu (contoh: rumah.com)",
                  default=state.config.get("cloudflare_domain", ""))
    if domain:
        state.config["cloudflare_domain"] = domain

    token = _ask("Cloudflare Tunnel Token",
                 default=state.config.get("cloudflare_token", ""))
    if token:
        state.config["cloudflare_token"]   = token
        state.config["cloudflare_enabled"] = True

        _nl()
        _ok("Cloudflare tunnel token disimpan.")
        _note("Tunnel akan di-deploy sebagai container di Phase 7 (Deploy).")

        # Tanya subdomain per service
        selected = _collect_selected_services(state.config)
        if selected and domain:
            _nl()
            _note("Tentukan subdomain untuk setiap service (Enter = skip):")
            subdomains = state.config.get("cloudflare_subdomains", {})
            for svc in selected:
                if svc in ("cloudflared", "watchtower"):
                    continue
                suggest = f"{svc}.{domain}"
                sub = _ask(f"  Subdomain untuk {svc}", default=suggest)
                if sub:
                    subdomains[svc] = sub
            state.config["cloudflare_subdomains"] = subdomains
    else:
        _info("Token kosong. Cloudflare tunnel tidak dikonfigurasi.")

    state.save()


PHASE_HANDLERS["remote_access"] = _phase_remote_access


# ══════════════════════════════════════════════════════════════════════════════
#  PHASE 7 - DEPLOY
# ══════════════════════════════════════════════════════════════════════════════

def _phase_deploy(state: BootstrapState):
    _phase_header(7, "Deploy & Verifikasi")

    # ── Generate compose ───────────────────────────────────────────────────────────
    print(f"  {C['bold']}[1/4] Generate docker-compose.yml{C['reset']}")
    _dline()

    media_mount  = state.config.get("media_mount", "/mnt/media")
    compose_dir  = str(Path(media_mount) / "docker")
    compose_file = str(Path(compose_dir) / "docker-compose.yml")

    _note(f"File akan disimpan ke: {compose_file}")
    _nl()

    # Custom path?
    custom = _ask("Path output (Enter = default)", default=compose_file)
    if custom:
        compose_file = custom
        compose_dir  = str(Path(custom).parent)

    # Generate
    _info("Generating docker-compose.yml...")
    try:
        yaml_content = generate_compose_yaml(state)
        Path(compose_dir).mkdir(parents=True, exist_ok=True)
        Path(compose_file).write_text(yaml_content, encoding="utf-8")
        _ok(f"docker-compose.yml berhasil digenerate!")
        _ok(f"Path: {compose_file}")

        # Update dockman config
        config.set_value("docker", "compose_file", compose_file)
        config.set_value("docker", "compose_dir",  compose_dir)

        state.set_phase_data("deploy", "compose_file", compose_file)
        state.set_phase_data("deploy", "compose_dir",  compose_dir)
        state.save()
    except Exception as e:
        _err(f"Gagal generate compose: {e}")
        return

    # Preview
    _nl()
    if _ask_yn("Tampilkan preview docker-compose.yml?", default=True):
        _nl()
        lines = yaml_content.splitlines()
        for line in lines[:60]:  # Max 60 baris preview
            print(f"    {C['dgray']}{line}{C['reset']}")
        if len(lines) > 60:
            _note(f"... ({len(lines) - 60} baris lagi, buka file untuk lengkapnya)")
        _nl()

    # ── Deploy ────────────────────────────────────────────────────────────────────────
    print(f"  {C['bold']}[2/4] Docker Compose UP{C['reset']}")
    _dline()
    _note("Akan menjalankan: docker compose up -d")
    _note("Semua image akan di-pull terlebih dahulu (butuh internet).")
    _nl()

    if not is_docker_running():
        _warn("Docker daemon tidak berjalan!")
        _info("Mencoba start Docker...")
        run_cmd("sudo systemctl start docker 2>/dev/null")
        time.sleep(2)
        if not is_docker_running():
            _err("Docker tidak bisa distart. Deploy dibatalkan.")
            return

    if _ask_yn("Deploy sekarang?", default=True):
        _info("Menjalankan docker compose up -d...")
        ret = run_interactive(f"cd '{compose_dir}' && docker compose up -d")
        if ret == 0:
            _ok("Docker Compose berhasil di-deploy!")
            state.set_phase_data("deploy", "deployed", True)
            state.save()
        else:
            _warn("Deploy selesai dengan warning/error. Cek output di atas.")
    else:
        _info(f"Skip deploy. Jalankan manual: cd '{compose_dir}' && docker compose up -d")
    _nl()

    # ── Health check ─────────────────────────────────────────────────────────────
    print(f"  {C['bold']}[3/4] Health Check{C['reset']}")
    _dline()
    _info("Menunggu container start... (30 detik)")
    time.sleep(30)
    run_interactive(f"cd '{compose_dir}' && docker compose ps")
    _nl()

    # ── Summary ───────────────────────────────────────────────────────────────────────
    print(f"  {C['bold']}[4/4] Summary URL Akses{C['reset']}")
    _dline()
    summary = generate_access_summary(state)
    if summary:
        _nl()
        for entry in summary:
            svc  = entry["service"]
            url  = entry["url"]
            note = entry.get("note", "")
            mdns = entry.get("url_mdns", "")
            print(f"  {C['green']}▶{C['reset']}  {C['bold']}{svc:<22}{C['reset']}  {C['cyan']}{url}{C['reset']}")
            if mdns:
                print(f"              {C['dgray']}atau: {mdns}{C['reset']}")
            if note:
                print(f"              {C['dgray']}{note}{C['reset']}")
        _nl()
    else:
        _note("Tidak ada service yang dipilih.")

    # SSH autostart
    _nl()
    _dline()
    print(f"  {C['bold']}SSH Autostart (Opsional){C['reset']}")
    _nl()
    _note("Saat login SSH, dockman otomatis terbuka.")
    _note("Bypass: ssh user@server -t 'DOCKMAN_SKIP=1 bash'")
    _nl()
    if _ask_yn("Aktifkan dockman autostart saat SSH login?", default=False):
        _enable_ssh_autostart(state)

    _nl()
    _dline()
    _ok("Phase 7 (Deploy & Verifikasi) selesai!")
    _ok("Bootstrap Wizard SELESAI! Server kamu siap digunakan.")
    state.set_phase_status("deploy", STATUS_DONE)
    state.save()
    _pause()


def _enable_ssh_autostart(state: BootstrapState):
    profile_file = Path.home() / ".bash_profile"
    marker_start = "# DOCKMAN_AUTOSTART_BEGIN"
    marker_end   = "# DOCKMAN_AUTOSTART_END"
    snippet = (
        f"\n{marker_start}\n"
        "if [[ $- == *i* ]] && [[ -z \"$DOCKMAN_SKIP\" ]]; then\n"
        "    dockman\n"
        "fi\n"
        f"{marker_end}\n"
    )
    try:
        content = profile_file.read_text() if profile_file.exists() else ""
        # Hapus snippet lama jika ada
        if marker_start in content:
            import re as _re
            content = _re.sub(
                rf"{marker_start}.*?{marker_end}\n?",
                "", content, flags=_re.DOTALL
            )
        content += snippet
        profile_file.write_text(content)
        _ok(f"Autostart ditambahkan ke {profile_file}")
        state.config["ssh_autostart"] = True
        state.save()
    except Exception as e:
        _warn(f"Gagal setup autostart: {e}")


PHASE_HANDLERS["deploy"] = _phase_deploy
