#!/bin/bash
# ============================================================
#  DOCKMAN Universal Installer v2.3
#  Support: Ubuntu/Debian, RHEL/CentOS/Fedora, Arch, Alpine
#
#  Install/Update langsung dari GitHub (tanpa clone):
#    bash <(curl -fsSL https://raw.githubusercontent.com/bugsdroid/dockman/main/install-dockman.sh)
#
#  Atau jika sudah punya file ini:
#    bash install-dockman.sh            -> install / update
#    bash install-dockman.sh uninstall  -> hapus dockman
#    bash install-dockman.sh check      -> cek dependencies
# ============================================================

set -e

REPO_RAW="https://raw.githubusercontent.com/bugsdroid/dockman/main"
INSTALL_PATH="/usr/local/bin/dockman"

# Deteksi mode: lokal (ada build.py) atau remote (curl | bash)
if [[ -n "${BASH_SOURCE[0]}" && "${BASH_SOURCE[0]}" != "bash" && -f "$(dirname "${BASH_SOURCE[0]}")/build.py" ]]; then
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    LOCAL_MODE=1
else
    SCRIPT_DIR="/tmp"
    LOCAL_MODE=0
fi

DIST_FILE="$SCRIPT_DIR/dist/dockman.py"

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
line() { echo "  $(printf '%0.s-' {1..50})"; }

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
        warn "rich gagal diinstall. Output tidak berwarna."
        return 1
    fi
}

install_docker() {
    if command -v docker &>/dev/null; then
        ok "docker sudah terinstall"
        return 0
    fi
    warn "Docker tidak ditemukan, menginstall..."
    case "$OS_FAMILY" in
        debian)
            if curl -fsSL https://get.docker.com | sudo sh &>/dev/null; then
                sudo systemctl enable --now docker &>/dev/null
                ok "Docker berhasil diinstall"
            else
                err "Docker gagal diinstall. Install manual: https://docs.docker.com/engine/install/"
                return 1
            fi ;;
        redhat|arch|alpine)
            eval "$PKG_INSTALL docker" &>/dev/null && ok "Docker diinstall" || return 1 ;;
        *) err "Auto-install Docker tidak support di OS ini."; return 1 ;;
    esac
}

setup_docker_group() {
    local user="${SUDO_USER:-$USER}"
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

# ── Download pre-built binary dari GitHub ─────────────────────────────────────
do_download() {
    info "Mengunduh dockman.py dari GitHub..."
    local tmp_file="/tmp/dockman.py.$$"
    if command -v curl &>/dev/null; then
        curl -fsSL "${REPO_RAW}/dockman.py" -o "$tmp_file"
    elif command -v wget &>/dev/null; then
        wget -qO "$tmp_file" "${REPO_RAW}/dockman.py"
    else
        err "curl atau wget diperlukan untuk download!"
        exit 1
    fi
    # Verifikasi file valid
    if python3 -c "import ast; ast.parse(open('$tmp_file').read())" 2>/dev/null; then
        DIST_FILE="$tmp_file"
        ok "Download selesai"
    else
        err "File yang didownload tidak valid!"
        rm -f "$tmp_file"
        exit 1
    fi
}

# ── Build dari source lokal ───────────────────────────────────────────────────
do_build() {
    info "Menjalankan build.py..."
    if [[ ! -f "$SCRIPT_DIR/build.py" ]]; then
        err "build.py tidak ditemukan di $SCRIPT_DIR"
        exit 1
    fi
    python3 "$SCRIPT_DIR/build.py"
    if [[ ! -f "$DIST_FILE" ]]; then
        err "Build gagal - dist/dockman.py tidak terbentuk"
        exit 1
    fi
    ok "Build selesai: $DIST_FILE"
}

# ── Ambil dockman.py: lokal build atau download ───────────────────────────────
do_get_binary() {
    if [[ $LOCAL_MODE -eq 1 ]]; then
        info "Mode lokal: build dari source..."
        do_build
    else
        info "Mode remote: download pre-built binary..."
        do_download
    fi
}

# ══ UNINSTALL ══════════════════════════════════════════════════════════════════
if [[ "${1}" == "uninstall" ]]; then
    echo ""
    echo -e "  ${C_BOLD}DOCKMAN Uninstall${C_RESET}"
    line
    if [[ -f "$INSTALL_PATH" ]]; then
        sudo rm -f "$INSTALL_PATH"
        ok "Dihapus dari $INSTALL_PATH"
        BACKUPS=$(ls ${INSTALL_PATH}.bak_* 2>/dev/null | wc -l)
        if [[ $BACKUPS -gt 0 ]]; then
            read -rp "  Hapus $BACKUPS file backup? (y/N): " del_bak
            [[ "${del_bak,,}" == "y" ]] && sudo rm -f ${INSTALL_PATH}.bak_* && ok "Backup dihapus"
        fi
    else
        warn "dockman tidak ditemukan di $INSTALL_PATH"
    fi
    echo ""
    exit 0
fi

# ══ BUILD ONLY (hanya mode lokal) ══════════════════════════════════════════════
if [[ "${1}" == "build" ]]; then
    echo ""
    echo -e "  ${C_BOLD}DOCKMAN Build${C_RESET}"
    line
    if [[ $LOCAL_MODE -eq 0 ]]; then
        err "Mode build hanya tersedia jika dijalankan dari direktori source."
        exit 1
    fi
    detect_os
    do_build
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
    info "OS Family  : $OS_FAMILY"
    info "Pkg Manager: $PKG_MANAGER"
    line
    ensure_python
    ensure_pip
    install_rich || true
    install_docker || true
    install_pkg "screen" "screen" "optional" || true
    command -v rclone &>/dev/null && ok "rclone terinstall" || warn "rclone tidak ditemukan"
    install_pkg "nano" "nano" "optional" || true
    echo ""
    ok "Cek selesai."
    echo ""
    exit 0
fi

# ══ INSTALL / UPDATE ═══════════════════════════════════════════════════════════
echo ""
echo -e "  ${C_BOLD}========================================${C_RESET}"
if [[ -f "$INSTALL_PATH" ]]; then
    # Tampilkan versi lama vs baru
    OLD_VER=$("$INSTALL_PATH" --version 2>/dev/null | awk '{print $2}' || echo "?")
    echo -e "  ${C_BOLD}  DOCKMAN - Update (versi saat ini: $OLD_VER)${C_RESET}"
else
    echo -e "  ${C_BOLD}  DOCKMAN - Install${C_RESET}"
fi
echo -e "  ${C_BOLD}========================================${C_RESET}"

detect_os
info "OS Family  : $OS_FAMILY"
info "Mode       : $([ $LOCAL_MODE -eq 1 ] && echo 'lokal (build dari source)' || echo 'remote (download dari GitHub)')"
line

echo ""
echo -e "  ${C_BOLD}[1/6] Python3${C_RESET}"
ensure_python

echo ""
echo -e "  ${C_BOLD}[2/6] pip${C_RESET}"
ensure_pip

echo ""
echo -e "  ${C_BOLD}[3/6] Rich (Python library)${C_RESET}"
install_rich || true

echo ""
echo -e "  ${C_BOLD}[4/6] Docker${C_RESET}"
install_docker || warn "Docker perlu diinstall manual"

echo ""
echo -e "  ${C_BOLD}[5/6] GNU Screen${C_RESET}"
install_pkg "screen" "screen" "optional" || true

echo ""
echo -e "  ${C_BOLD}[6/6] nano (editor)${C_RESET}"
install_pkg "nano" "nano" "optional" || true

line

# ── Ambil binary ───────────────────────────────────────────────────────────────
echo ""
echo -e "  ${C_BOLD}Menyiapkan dockman.py...${C_RESET}"
do_get_binary

# ── Install ────────────────────────────────────────────────────────────────────
echo ""
echo -e "  ${C_BOLD}Installing...${C_RESET}"

if [[ -f "$INSTALL_PATH" ]]; then
    BACKUP="${INSTALL_PATH}.bak_$(date +%Y%m%d_%H%M%S)"
    sudo cp "$INSTALL_PATH" "$BACKUP"
    ok "Backup versi lama: $BACKUP"
fi

sudo cp "$DIST_FILE" "$INSTALL_PATH"
sudo chmod +x "$INSTALL_PATH"

# Bersihkan tmp jika mode remote
[[ $LOCAL_MODE -eq 0 ]] && rm -f "$DIST_FILE"

# Verifikasi
NEW_VER=$("$INSTALL_PATH" --version 2>/dev/null | awk '{print $2}' || echo "?")
ok "Installed: $INSTALL_PATH (v${NEW_VER})"

# ── Docker group ───────────────────────────────────────────────────────────────
echo ""
setup_docker_group

# ── Summary ────────────────────────────────────────────────────────────────────
echo ""
echo -e "  ${C_BOLD}========================================${C_RESET}"
echo -e "  ${C_BOLD}  DOCKMAN v${NEW_VER} siap dipakai!${C_RESET}"
echo -e "  ${C_BOLD}========================================${C_RESET}"
echo ""
echo "  USAGE:"
echo "    dockman              -> TUI mode"
echo "    dockman --menu       -> Menu numbered"
echo "    dockman --setup      -> Setup wizard"
echo "    dockman ps           -> List container"
echo "    dockman logs <name>  -> Lihat logs"
echo "    dockman report       -> Generate server report"
echo "    dockman --help       -> Semua command"
echo ""
echo "  UPDATE ke versi terbaru:"
echo "    bash <(curl -fsSL https://raw.githubusercontent.com/bugsdroid/dockman/main/install-dockman.sh)"
echo ""
echo "  UNINSTALL:"
echo "    bash <(curl -fsSL https://raw.githubusercontent.com/bugsdroid/dockman/main/install-dockman.sh) uninstall"
echo ""

if [[ -n "$NEED_RELOGIN" ]]; then
    echo -e "  ${C_YELLOW}PENTING: Logout & login ulang agar docker group aktif!${C_RESET}"
    echo -e "  ${C_YELLOW}Atau jalankan: newgrp docker${C_RESET}"
    echo ""
fi

line
echo ""
