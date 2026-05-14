#!/bin/bash
# ============================================================
#  DOCKMAN Universal Installer v3.0
#  Support: Ubuntu/Debian, RHEL/CentOS/Fedora, Arch, Alpine
#
#  Install/Update dari branch v3:
#    bash <(curl -fsSL https://raw.githubusercontent.com/bugsdroid/dockman/v3/install-dockman.sh)
#
#  Install dari main (stable v2.x):
#    bash <(curl -fsSL https://raw.githubusercontent.com/bugsdroid/dockman/main/install-dockman.sh)
#
#  Atau jika sudah punya file ini:
#    bash install-dockman.sh            -> install / update
#    bash install-dockman.sh uninstall  -> hapus dockman
#    bash install-dockman.sh check      -> cek dependencies
#    bash install-dockman.sh build      -> build saja (lokal)
#    bash install-dockman.sh bootstrap  -> install + langsung jalankan Bootstrap Wizard
# ============================================================

set -e

REPO_URL="https://github.com/bugsdroid/dockman.git"
REPO_BRANCH="v3"   # default branch untuk installer ini
INSTALL_PATH="/usr/local/bin/dockman"
BUILD_TMP="/tmp/dockman-build-$$"

# Deteksi mode: lokal (ada dockman_main/build.py) atau remote (curl | bash)
if [[ -n "${BASH_SOURCE[0]}" && "${BASH_SOURCE[0]}" != "bash" && -f "$(dirname "${BASH_SOURCE[0]}")/dockman_main/build.py" ]]; then
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    LOCAL_MODE=1
else
    SCRIPT_DIR="$BUILD_TMP"
    LOCAL_MODE=0
fi

DIST_FILE="$SCRIPT_DIR/dockman_main/dist/dockman.py"

# Flag bootstrap
BOOTSTRAP_AFTER_INSTALL=0
[[ "${1}" == "bootstrap" ]] && BOOTSTRAP_AFTER_INSTALL=1

# ── Warna ──────────────────────────────────────────────────────────────────────
if [[ -t 1 ]] && command -v tput &>/dev/null && tput colors &>/dev/null 2>&1; then
    C_GREEN="\033[0;32m"; C_YELLOW="\033[0;33m"
    C_RED="\033[0;31m";   C_CYAN="\033[0;36m"
    C_BOLD="\033[1m";     C_RESET="\033[0m"
else
    C_GREEN=""; C_YELLOW=""; C_RED=""; C_CYAN=""; C_BOLD=""; C_RESET=""
fi

ok()   { echo -e "  ${C_GREEN}[OK]${C_RESET}  $*"; }
warn() { echo -e "  ${C_YELLOW}[!!]${C_RESET}  $*"; }
err()  { echo -e "  ${C_RED}[XX]${C_RESET}  $*"; }
info() { echo -e "  ${C_CYAN}[..]${C_RESET}  $*"; }
line() { echo "  $(printf '%0.s-' {1..54})"; }

# ── Detect OS ──────────────────────────────────────────────────────────────────
detect_os() {
    PKG_MANAGER=""; PKG_INSTALL=""; PKG_UPDATE=""; OS_FAMILY=""
    if [[ -f /etc/os-release ]]; then
        . /etc/os-release; ID_LOWER="${ID,,}"
    else
        ID_LOWER="unknown"
    fi
    case "$ID_LOWER" in
        ubuntu|debian|linuxmint|pop|elementary|zorin|kali|raspbian)
            PKG_MANAGER="apt"; PKG_INSTALL="sudo apt-get install -y"
            PKG_UPDATE="sudo apt-get update -qq"; OS_FAMILY="debian" ;;
        fedora)
            PKG_MANAGER="dnf"; PKG_INSTALL="sudo dnf install -y"
            PKG_UPDATE=""; OS_FAMILY="redhat" ;;
        rhel|centos|rocky|almalinux|ol)
            PKG_MANAGER="yum"; PKG_INSTALL="sudo yum install -y"
            PKG_UPDATE=""; OS_FAMILY="redhat" ;;
        arch|manjaro|endeavouros|garuda)
            PKG_MANAGER="pacman"; PKG_INSTALL="sudo pacman -S --noconfirm"
            PKG_UPDATE="sudo pacman -Sy"; OS_FAMILY="arch" ;;
        alpine)
            PKG_MANAGER="apk"; PKG_INSTALL="sudo apk add --no-cache"
            PKG_UPDATE="sudo apk update"; OS_FAMILY="alpine" ;;
        *)
            PKG_MANAGER="unknown"; OS_FAMILY="unknown" ;;
    esac
}

install_pkg() {
    local cmd="$1" pkg="$2" optional="$3"
    if command -v "$cmd" &>/dev/null; then
        ok "$cmd sudah terinstall"
        return 0
    fi
    warn "$cmd tidak ditemukan, menginstall..."
    [[ -z "$PKG_INSTALL" ]] && { warn "Package manager tidak dikenal."; return 1; }
    if [[ -z "$REPO_UPDATED" && -n "$PKG_UPDATE" ]]; then
        eval "$PKG_UPDATE" &>/dev/null; REPO_UPDATED=1
    fi
    if eval "$PKG_INSTALL $pkg" &>/dev/null; then
        ok "$cmd berhasil diinstall"
    else
        [[ "$optional" == "optional" ]] && warn "$cmd gagal (opsional)" || err "$cmd gagal diinstall!"
        return 1
    fi
}

ensure_python() {
    if command -v python3 &>/dev/null; then
        local ver=$(python3 --version 2>&1 | awk '{print $2}')
        ok "python3 $ver"
        return 0
    fi
    warn "python3 tidak ditemukan, menginstall..."
    [[ -z "$PKG_INSTALL" ]] && { err "Tidak bisa auto-install python3."; exit 1; }
    [[ -z "$REPO_UPDATED" && -n "$PKG_UPDATE" ]] && eval "$PKG_UPDATE" &>/dev/null && REPO_UPDATED=1
    case "$OS_FAMILY" in
        debian) eval "$PKG_INSTALL python3 python3-pip python3-venv" &>/dev/null ;;
        redhat) eval "$PKG_INSTALL python3 python3-pip" &>/dev/null ;;
        arch)   eval "$PKG_INSTALL python python-pip" &>/dev/null ;;
        alpine) eval "$PKG_INSTALL python3 py3-pip" &>/dev/null ;;
    esac
    command -v python3 &>/dev/null && ok "python3 berhasil diinstall" || { err "python3 gagal!"; exit 1; }
}

ensure_pip() {
    if python3 -m pip --version &>/dev/null; then
        ok "pip tersedia"
        return 0
    fi
    warn "pip tidak ditemukan, menginstall..."
    case "$OS_FAMILY" in
        debian)  eval "$PKG_INSTALL python3-pip" &>/dev/null ;;
        redhat)  eval "$PKG_INSTALL python3-pip" &>/dev/null ;;
        arch)    eval "$PKG_INSTALL python-pip"  &>/dev/null ;;
        alpine)  eval "$PKG_INSTALL py3-pip"     &>/dev/null ;;
        *) python3 -m ensurepip --upgrade &>/dev/null ;;
    esac
    python3 -m pip --version &>/dev/null && ok "pip berhasil diinstall" || warn "pip tidak tersedia"
}

install_rich() {
    if python3 -c "import rich" 2>/dev/null; then
        ok "rich sudah terinstall"
        return 0
    fi
    warn "rich tidak ditemukan, menginstall..."
    if python3 -m pip install rich --break-system-packages -q 2>/dev/null || \
       python3 -m pip install rich -q 2>/dev/null; then
        ok "rich berhasil diinstall"
    else
        warn "rich gagal diinstall."
        return 1
    fi
}

install_docker() {
    if command -v docker &>/dev/null; then
        ok "docker sudah terinstall"
        return 0
    fi
    warn "Docker tidak ditemukan. Bootstrap Wizard bisa install Docker nanti."
    info "Untuk install sekarang, pilih Y:"
    read -rp "  Install Docker sekarang? (y/N): " inst_now
    if [[ "${inst_now,,}" != "y" ]]; then
        warn "Skip. Bootstrap Wizard (dockman --bootstrap) akan install Docker di Phase 4."
        return 0
    fi
    case "$OS_FAMILY" in
        debian)
            if curl -fsSL https://get.docker.com | sudo sh &>/dev/null; then
                sudo systemctl enable --now docker &>/dev/null
                ok "Docker berhasil diinstall"
            else
                err "Docker gagal diinstall."
                return 1
            fi ;;
        redhat|arch|alpine)
            eval "$PKG_INSTALL docker" &>/dev/null && ok "Docker diinstall" || return 1 ;;
        *) err "Auto-install Docker tidak support di OS ini."; return 1 ;;
    esac
}

ensure_git() {
    if command -v git &>/dev/null; then
        ok "git tersedia"
        return 0
    fi
    warn "git tidak ditemukan, menginstall..."
    [[ -z "$PKG_INSTALL" ]] && { err "Package manager tidak dikenal."; return 1; }
    if [[ -z "$REPO_UPDATED" && -n "$PKG_UPDATE" ]]; then
        eval "$PKG_UPDATE" &>/dev/null; REPO_UPDATED=1
    fi
    if eval "$PKG_INSTALL git" &>/dev/null; then
        ok "git berhasil diinstall"
    else
        err "git gagal diinstall!"
        return 1
    fi
}

setup_docker_group() {
    local user="${SUDO_USER:-$USER}"
    if ! command -v docker &>/dev/null; then
        return 0   # docker belum install, skip
    fi
    if groups "$user" 2>/dev/null | grep -q docker; then
        ok "User '$user' sudah di grup docker"
    else
        warn "User '$user' belum di grup docker"
        sudo usermod -aG docker "$user" 2>/dev/null && {
            warn "Ditambahkan ke grup docker. PERLU logout & login ulang!"
            NEED_RELOGIN=1
        } || warn "Gagal. Jalankan: sudo usermod -aG docker $user"
    fi
}

install_rclone() {
    if command -v rclone &>/dev/null; then
        ok "rclone sudah terinstall ($(rclone --version 2>/dev/null | head -1))"
        return 0
    fi
    warn "rclone tidak ditemukan, menginstall..."
    if curl -fsSL https://rclone.org/install.sh | sudo bash &>/dev/null; then
        ok "rclone berhasil diinstall"
    else
        warn "Auto-install rclone gagal."
        return 1
    fi
}

setup_rclone_mega() {
    if ! command -v rclone &>/dev/null; then
        warn "rclone tidak terinstall, skip konfigurasi Mega."
        return 0
    fi

    echo ""
    echo -e "  ${C_BOLD}--- Konfigurasi rclone Mega ---${C_RESET}"

    local existing_remotes
    existing_remotes=$(rclone listremotes 2>/dev/null || echo "")

    if echo "$existing_remotes" | grep -q "mega:"; then
        ok "Remote 'mega' sudah terkonfigurasi"
        info "Remote yang ada: $(echo $existing_remotes | tr '\n' ' ')"
        return 0
    fi

    warn "Remote 'mega' belum dikonfigurasi."
    echo ""
    read -rp "  Setup koneksi Mega sekarang? (y/N): " setup_now

    if [[ "${setup_now,,}" != "y" ]]; then
        warn "Skip. Setup nanti dengan: rclone config"
        return 0
    fi

    echo ""
    echo -e "  ${C_BOLD}Panduan setup Mega di rclone:${C_RESET}"
    echo "  1. Pilih  'n' (New remote)"
    echo "  2. Nama   -> ketik: mega"
    echo "  3. Tipe   -> cari dan pilih: mega"
    echo "  4. Email  -> masukkan email akun Mega kamu"
    echo "  5. Password -> masukkan password Mega kamu"
    echo "  6. Sisanya -> Enter saja (default)"
    echo "  7. Pilih  'q' untuk quit setelah selesai"
    echo ""
    read -rp "  Tekan Enter untuk mulai rclone config..." _
    rclone config

    after_remotes=$(rclone listremotes 2>/dev/null || echo "")
    if echo "$after_remotes" | grep -q "mega:"; then
        ok "Remote 'mega' berhasil dikonfigurasi!"
    else
        warn "Remote 'mega' tidak ditemukan. Jalankan manual: rclone config"
    fi
}

# ── Build dari source lokal ───────────────────────────────────────────────────
do_build_local() {
    info "Mode lokal: build dari source..."
    if [[ ! -f "$SCRIPT_DIR/dockman_main/build.py" ]]; then
        err "build.py tidak ditemukan di $SCRIPT_DIR/dockman_main/"
        exit 1
    fi
    cd "$SCRIPT_DIR/dockman_main"
    python3 build.py
    DIST_FILE="$SCRIPT_DIR/dockman_main/dist/dockman.py"
    if [[ ! -f "$DIST_FILE" ]]; then
        err "Build gagal - dist/dockman.py tidak terbentuk"
        exit 1
    fi
    ok "Build selesai: $DIST_FILE"
}

# ── Clone repo + build dari GitHub ───────────────────────────────────────────
do_build_remote() {
    info "Mode remote: clone branch ${REPO_BRANCH}..."

    ensure_git || { err "git diperlukan. Install: sudo apt install git"; exit 1; }

    rm -rf "$BUILD_TMP"
    info "Cloning repository (branch: ${REPO_BRANCH}, shallow)..."
    if git clone --depth=1 --branch="$REPO_BRANCH" --quiet "$REPO_URL" "$BUILD_TMP" 2>/dev/null; then
        ok "Clone selesai"
    else
        # Fallback ke main jika branch tidak ada
        warn "Branch ${REPO_BRANCH} tidak ditemukan, mencoba main..."
        if git clone --depth=1 --quiet "$REPO_URL" "$BUILD_TMP" 2>/dev/null; then
            ok "Clone dari main selesai"
        else
            err "Clone gagal! Cek koneksi internet."
            exit 1
        fi
    fi

    cd "$BUILD_TMP/dockman_main"
    info "Building dockman.py dari source..."
    python3 build.py

    DIST_FILE="$BUILD_TMP/dockman_main/dist/dockman.py"
    if [[ ! -f "$DIST_FILE" ]]; then
        err "Build gagal - dist/dockman.py tidak terbentuk"
        rm -rf "$BUILD_TMP"
        exit 1
    fi
    ok "Build selesai"
}

do_get_binary() {
    if [[ $LOCAL_MODE -eq 1 ]]; then
        do_build_local
    else
        do_build_remote
    fi
}

cleanup() {
    [[ $LOCAL_MODE -eq 0 && -d "$BUILD_TMP" ]] && rm -rf "$BUILD_TMP"
}
trap cleanup EXIT


# ══ UNINSTALL ══════════════════════════════════════════════════════════════════
if [[ "${1}" == "uninstall" ]]; then
    echo ""
    echo -e "  ${C_BOLD}DOCKMAN Uninstall${C_RESET}"
    line
    if [[ -f "$INSTALL_PATH" ]]; then
        sudo rm -f "$INSTALL_PATH"
        ok "Dihapus dari $INSTALL_PATH"
        # Hapus backup binary
        BACKUPS=$(ls ${INSTALL_PATH}.bak_* 2>/dev/null | wc -l)
        if [[ $BACKUPS -gt 0 ]]; then
            read -rp "  Hapus $BACKUPS file backup binary? (y/N): " del_bak
            [[ "${del_bak,,}" == "y" ]] && sudo rm -f ${INSTALL_PATH}.bak_* && ok "Backup binary dihapus"
        fi
        # Hapus bootstrap state
        BOOTSTRAP_STATE="$HOME/.config/dockman/bootstrap_state.json"
        if [[ -f "$BOOTSTRAP_STATE" ]]; then
            read -rp "  Hapus bootstrap wizard state? (y/N): " del_state
            [[ "${del_state,,}" == "y" ]] && rm -f "$BOOTSTRAP_STATE" && ok "Bootstrap state dihapus"
        fi
        # Hapus config
        DOCKMAN_CONFIG="$HOME/.config/dockman/config.ini"
        if [[ -f "$DOCKMAN_CONFIG" ]]; then
            read -rp "  Hapus config dockman (~/.config/dockman/)? (y/N): " del_cfg
            [[ "${del_cfg,,}" == "y" ]] && rm -rf "$HOME/.config/dockman/" && ok "Config dihapus"
        fi
    else
        warn "dockman tidak ditemukan di $INSTALL_PATH"
    fi
    echo ""
    exit 0
fi

# ══ BUILD ONLY ═════════════════════════════════════════════════════════════════
if [[ "${1}" == "build" ]]; then
    echo ""
    echo -e "  ${C_BOLD}DOCKMAN Build${C_RESET}"
    line
    detect_os
    if [[ $LOCAL_MODE -eq 1 ]]; then
        do_build_local
    else
        err "Mode 'build' hanya tersedia dari direktori source lokal."
        exit 1
    fi
    echo ""
    exit 0
fi

# ══ CHECK ═════════════════════════════════════════════════════════════════════
if [[ "${1}" == "check" ]]; then
    echo ""
    echo -e "  ${C_BOLD}========================================${C_RESET}"
    echo -e "  ${C_BOLD}  DOCKMAN - Cek Dependencies${C_RESET}"
    echo -e "  ${C_BOLD}========================================${C_RESET}"
    detect_os
    info "OS Family  : $OS_FAMILY ($ID_LOWER)"
    info "Pkg Manager: $PKG_MANAGER"
    line
    ensure_python
    ensure_pip
    python3 -c "import rich" 2>/dev/null && ok "rich terinstall" || warn "rich belum terinstall"
    command -v docker &>/dev/null && ok "docker $(docker --version 2>/dev/null | awk '{print $3}' | tr -d ',')"\
        || warn "Docker belum terinstall (Bootstrap Wizard bisa install di Phase 4)"
    command -v git &>/dev/null    && ok "git $(git --version | awk '{print $3}')" || warn "git belum terinstall"
    command -v screen &>/dev/null && ok "screen terinstall"  || warn "screen belum terinstall"
    command -v rclone &>/dev/null && ok "rclone terinstall" || warn "rclone belum terinstall"
    command -v nano &>/dev/null   && ok "nano terinstall"   || warn "nano belum terinstall"
    command -v netplan &>/dev/null && ok "netplan tersedia" || warn "netplan tidak ditemukan"
    command -v tailscale &>/dev/null && ok "tailscale terinstall" || warn "tailscale belum terinstall"
    echo ""
    # Cek bootstrap state
    if [[ -f "$HOME/.config/dockman/bootstrap_state.json" ]]; then
        ok "Bootstrap state ditemukan: ~/.config/dockman/bootstrap_state.json"
    else
        info "Belum ada bootstrap state. Jalankan: dockman --bootstrap"
    fi
    echo ""
    ok "Cek selesai."
    echo ""
    exit 0
fi


# ══ INSTALL / UPDATE ═══════════════════════════════════════════════════════════
echo ""
echo -e "  ${C_BOLD}========================================${C_RESET}"
if [[ -f "$INSTALL_PATH" ]]; then
    OLD_VER=$("$INSTALL_PATH" --version 2>/dev/null | awk '{print $2}' || echo "?")
    echo -e "  ${C_BOLD}  DOCKMAN - Update (saat ini: v$OLD_VER)${C_RESET}"
else
    echo -e "  ${C_BOLD}  DOCKMAN v3 - Install${C_RESET}"
fi
echo -e "  ${C_BOLD}========================================${C_RESET}"

detect_os
info "OS         : ${ID_LOWER} (${OS_FAMILY})"
info "Branch     : ${REPO_BRANCH}"
info "Mode       : $([ $LOCAL_MODE -eq 1 ] && echo 'lokal (build dari source)' || echo 'remote (clone + build dari GitHub)')"
line

echo ""
echo -e "  ${C_BOLD}[1/9] Python3${C_RESET}"
ensure_python

echo ""
echo -e "  ${C_BOLD}[2/9] pip${C_RESET}"
ensure_pip

echo ""
echo -e "  ${C_BOLD}[3/9] Rich (Python library)${C_RESET}"
install_rich || true

echo ""
echo -e "  ${C_BOLD}[4/9] Git${C_RESET}"
ensure_git || true

echo ""
echo -e "  ${C_BOLD}[5/9] Docker${C_RESET}"
# Di v3, Docker bisa diinstall via Bootstrap Wizard Phase 4, jadi tidak mandatory di sini
if command -v docker &>/dev/null; then
    ok "Docker sudah terinstall: $(docker --version 2>/dev/null | awk '{print $3}' | tr -d ',')" 
else
    warn "Docker belum terinstall."
    info "Bootstrap Wizard akan install Docker secara otomatis di Phase 4."
    info "Atau install manual sekarang:"
fi

echo ""
echo -e "  ${C_BOLD}[6/9] GNU Screen${C_RESET}"
install_pkg "screen" "screen" "optional" || true

echo ""
echo -e "  ${C_BOLD}[7/9] rclone + Mega${C_RESET}"
install_rclone || true
setup_rclone_mega || true

echo ""
echo -e "  ${C_BOLD}[8/9] nano (editor)${C_RESET}"
install_pkg "nano" "nano" "optional" || true

echo ""
echo -e "  ${C_BOLD}[9/9] Build & Install dockman${C_RESET}"
do_get_binary

echo ""
echo -e "  ${C_BOLD}Installing...${C_RESET}"

if [[ -f "$INSTALL_PATH" ]]; then
    BACKUP="${INSTALL_PATH}.bak_$(date +%Y%m%d_%H%M%S)"
    sudo cp "$INSTALL_PATH" "$BACKUP"
    ok "Backup versi lama: $BACKUP"
fi

sudo cp "$DIST_FILE" "$INSTALL_PATH"
sudo chmod +x "$INSTALL_PATH"

[[ $LOCAL_MODE -eq 0 && -d "$BUILD_TMP" ]] && rm -rf "$BUILD_TMP"

NEW_VER=$("$INSTALL_PATH" --version 2>/dev/null | awk '{print $2}' || echo "?")
ok "Installed: $INSTALL_PATH (v${NEW_VER})"

echo ""
setup_docker_group

# ── Post-install summary ──────────────────────────────────────────────────────
echo ""
echo -e "  ${C_BOLD}========================================${C_RESET}"
echo -e "  ${C_BOLD}  DOCKMAN v${NEW_VER} siap dipakai!${C_RESET}"
echo -e "  ${C_BOLD}========================================${C_RESET}"
echo ""
echo "  USAGE:"
echo "    dockman                  -> Menu utama"
echo "    dockman --bootstrap      -> Bootstrap Wizard (setup server dari nol)"
echo "    dockman --bootstrap 3    -> Jalankan ulang phase 3 (Storage)"
echo "    dockman --tui            -> TUI curses interaktif"
echo "    dockman --setup          -> Setup wizard config dockman"
echo "    dockman ps               -> List container"
echo "    dockman logs <name>      -> Lihat logs container"
echo "    dockman report           -> Generate server report"
echo "    dockman --help           -> Semua command"
echo ""
echo "  BOOTSTRAP WIZARD (7 phases):"
echo "    Phase 1: Persiapan Sistem  (hostname, timezone, update)"
echo "    Phase 2: Konfigurasi Jaringan (static IP, UFW, mDNS)"
echo "    Phase 3: Manajemen Storage (disk, format, mount)"
echo "    Phase 4: Setup Docker"
echo "    Phase 5: Pilih Stack (Jellyfin, Radarr, dll)"
echo "    Phase 6: Remote Access (Tailscale, Cloudflare Tunnel)"
echo "    Phase 7: Deploy & Verifikasi"
echo ""
echo "  UPDATE ke versi terbaru (branch v3):"
echo "    bash <(curl -fsSL https://raw.githubusercontent.com/bugsdroid/dockman/v3/install-dockman.sh)"
echo ""
echo "  UNINSTALL:"
echo "    bash <(curl -fsSL https://raw.githubusercontent.com/bugsdroid/dockman/v3/install-dockman.sh) uninstall"
echo ""
echo "  CEK DEPENDENCIES:"
echo "    bash <(curl -fsSL https://raw.githubusercontent.com/bugsdroid/dockman/v3/install-dockman.sh) check"
echo ""

if [[ -n "$NEED_RELOGIN" ]]; then
    echo -e "  ${C_YELLOW}PENTING: Logout & login ulang agar docker group aktif!${C_RESET}"
    echo -e "  ${C_YELLOW}Atau jalankan: newgrp docker${C_RESET}"
    echo ""
fi

line
echo ""

# ── Auto-launch Bootstrap Wizard jika diminta ─────────────────────────────────
if [[ $BOOTSTRAP_AFTER_INSTALL -eq 1 ]]; then
    echo -e "  ${C_CYAN}Meluncurkan Bootstrap Wizard...${C_RESET}"
    echo ""
    sleep 1
    exec dockman --bootstrap
elif [[ ! -f "$HOME/.config/dockman/bootstrap_state.json" ]]; then
    # First-time install: tawarkan bootstrap wizard
    echo -e "  ${C_BOLD}Setup server dari nol?${C_RESET}"
    echo "  Bootstrap Wizard akan memandu kamu setup lengkap:"
    echo "  static IP, Docker, Jellyfin, qBittorrent, Radarr, dll."
    echo ""
    read -rp "  Jalankan Bootstrap Wizard sekarang? (y/N): " run_bootstrap
    if [[ "${run_bootstrap,,}" == "y" ]]; then
        echo ""
        exec dockman --bootstrap
    else
        echo ""
        info "Jalankan nanti dengan: dockman --bootstrap"
        info "Atau langsung pakai: dockman"
        echo ""
    fi
fi
