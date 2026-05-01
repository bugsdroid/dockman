#!/bin/bash
# ============================================================
#  DOCKMAN Universal Installer v2.1
#  Support: Ubuntu/Debian, RHEL/CentOS/Fedora, Arch, Alpine
#  Cara pakai:
#    bash install-dockman.sh            -> install / update
#    bash install-dockman.sh uninstall  -> hapus dockman
#    bash install-dockman.sh check      -> cek dependencies
#    bash install-dockman.sh build      -> build saja (tanpa install)
# ============================================================

set -e

INSTALL_PATH="/usr/local/bin/dockman"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
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
    # Cek python3
    if command -v python3 &>/dev/null; then
        local ver=$(python3 --version 2>&1 | awk '{print $2}')
        ok "python3 $ver"
        return 0
    fi
    warn "python3 tidak ditemukan, menginstall..."
    if [[ -z "$PKG_INSTALL" ]]; then
        err "Tidak bisa auto-install python3. Install manual: https://python.org"
        exit 1
    fi
    [[ -z "$REPO_UPDATED" && -n "$PKG_UPDATE" ]] && eval "$PKG_UPDATE" &>/dev/null && REPO_UPDATED=1
    case "$OS_FAMILY" in
        debian) eval "$PKG_INSTALL python3 python3-pip python3-venv" &>/dev/null ;;
        redhat) eval "$PKG_INSTALL python3 python3-pip" &>/dev/null ;;
        arch)   eval "$PKG_INSTALL python python-pip" &>/dev/null ;;
        alpine) eval "$PKG_INSTALL python3 py3-pip" &>/dev/null ;;
    esac
    if command -v python3 &>/dev/null; then
        ok "python3 berhasil diinstall"
    else
        err "python3 gagal diinstall!"
        exit 1
    fi
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
        warn "rich gagal. Output tidak berwarna."
        return 1
    fi
}

install_textual() {
    if python3 -c "import textual" 2>/dev/null; then
        local ver=$(python3 -c "import textual; print(textual.__version__)" 2>/dev/null)
        ok "textual v${ver} sudah terinstall"
        return 0
    fi
    warn "textual tidak ditemukan, menginstall..."
    if python3 -m pip install "textual>=0.47.0" --break-system-packages -q 2>/dev/null || \
       python3 -m pip install "textual>=0.47.0" -q 2>/dev/null; then
        ok "textual berhasil diinstall"
    else
        warn "textual gagal diinstall."
        warn "TUI akan fallback ke --menu mode."
        warn "Install manual: pip install textual --break-system-packages"
        return 1
    fi
}


install_rich() {
    if python3 -c "import rich" 2>/dev/null; then
        ok "rich sudah terinstall"
        return 0
    fi
    warn "rich tidak ditemukan, menginstall via pip..."
    if python3 -m pip install rich --break-system-packages -q 2>/dev/null || \
       python3 -m pip install rich -q 2>/dev/null; then
        ok "rich berhasil diinstall"
    else
        warn "rich gagal diinstall. Output tidak berwarna."
        return 1
    fi
}

install_textual() {
    if python3 -c "import textual" 2>/dev/null; then
        local ver=$(python3 -c "import textual; print(textual.__version__)" 2>/dev/null)
        ok "textual sudah terinstall (v${ver})"
        return 0
    fi
    warn "textual tidak ditemukan, menginstall via pip..."
    if python3 -m pip install "textual>=0.47.0" --break-system-packages -q 2>/dev/null || \
       python3 -m pip install "textual>=0.47.0" -q 2>/dev/null; then
        ok "textual berhasil diinstall"
    else
        warn "textual gagal diinstall."
        warn "TUI akan fallback ke --menu mode."
        warn "Install manual: pip install textual --break-system-packages"
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

do_build() {
    info "Menjalankan build.py..."
    if [[ ! -f "$SCRIPT_DIR/build.py" ]]; then
        err "build.py tidak ditemukan di $SCRIPT_DIR"
        err "Pastikan semua source file ada (core/, ui/, main.py)"
        exit 1
    fi
    python3 "$SCRIPT_DIR/build.py"
    if [[ ! -f "$DIST_FILE" ]]; then
        err "Build gagal - dist/dockman.py tidak terbentuk"
        exit 1
    fi
    ok "Build selesai: $DIST_FILE"
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

# ══ BUILD ONLY ═════════════════════════════════════════════════════════════════
if [[ "${1}" == "build" ]]; then
    echo ""
    echo -e "  ${C_BOLD}DOCKMAN Build${C_RESET}"
    line
    detect_os
    do_build
    echo ""
    exit 0
fi

# ══ CHECK / INSTALL / UPDATE ═══════════════════════════════════════════════════
CHECK_ONLY=0
[[ "${1}" == "check" ]] && CHECK_ONLY=1

echo ""
echo -e "  ${C_BOLD}========================================${C_RESET}"
if [[ $CHECK_ONLY -eq 1 ]]; then
    echo -e "  ${C_BOLD}  DOCKMAN - Cek Dependencies${C_RESET}"
elif [[ -f "$INSTALL_PATH" ]]; then
    echo -e "  ${C_BOLD}  DOCKMAN - Update${C_RESET}"
else
    echo -e "  ${C_BOLD}  DOCKMAN - Install${C_RESET}"
fi
echo -e "  ${C_BOLD}========================================${C_RESET}"

detect_os
info "OS Family  : $OS_FAMILY"
info "Pkg Manager: $PKG_MANAGER"
line

echo ""
echo -e "  ${C_BOLD}[1/7] Python3${C_RESET}"
ensure_python

echo ""
echo -e "  ${C_BOLD}[2/7] pip${C_RESET}"
ensure_pip

echo ""
echo -e "  ${C_BOLD}[3/7] Rich (Python library)${C_RESET}"
install_rich || true

echo ""
echo -e "  ${C_BOLD}[4/7] Textual (Python TUI library)${C_RESET}"
install_textual || true

echo ""
echo -e "  ${C_BOLD}[5/7] Docker${C_RESET}"
install_docker || warn "Docker perlu diinstall manual"

echo ""
echo -e "  ${C_BOLD}[5/7] GNU Screen${C_RESET}"
install_pkg "screen" "screen" "optional" || true

echo ""
echo -e "  ${C_BOLD}[6/7] rclone${C_RESET}"
if command -v rclone &>/dev/null; then
    ok "rclone sudah terinstall"
else
    warn "rclone tidak ditemukan"
    info "Install manual: curl https://rclone.org/install.sh | sudo bash"
fi

echo ""
echo -e "  ${C_BOLD}[7/7] nano (editor)${C_RESET}"
install_pkg "nano" "nano" "optional" || true

line

[[ $CHECK_ONLY -eq 1 ]] && { echo ""; ok "Cek selesai."; echo ""; exit 0; }

# ── Build ──────────────────────────────────────────────────────────────────────
echo ""
echo -e "  ${C_BOLD}Build dockman...${C_RESET}"
do_build

# ── Install ────────────────────────────────────────────────────────────────────
echo ""
echo -e "  ${C_BOLD}Install...${C_RESET}"

if [[ -f "$INSTALL_PATH" ]]; then
    BACKUP="${INSTALL_PATH}.bak_$(date +%Y%m%d_%H%M%S)"
    sudo cp "$INSTALL_PATH" "$BACKUP"
    ok "Backup versi lama: $BACKUP"
fi

sudo cp "$DIST_FILE" "$INSTALL_PATH"
sudo chmod +x "$INSTALL_PATH"
ok "Installed: $INSTALL_PATH"

# ── Docker group ───────────────────────────────────────────────────────────────
echo ""
setup_docker_group

# ── Summary ────────────────────────────────────────────────────────────────────
echo ""
echo -e "  ${C_BOLD}========================================${C_RESET}"
echo -e "  ${C_BOLD}  DOCKMAN siap dipakai!${C_RESET}"
echo -e "  ${C_BOLD}========================================${C_RESET}"
echo ""
echo "  USAGE:"
echo "    dockman              -> TUI mode"
echo "    dockman --menu       -> Menu numbered"
echo "    dockman --setup      -> Setup wizard"
echo "    dockman ps           -> List container (Rich)"
echo "    dockman logs <name>  -> Lihat logs"
echo "    dockman report       -> Generate server report"
echo "    dockman --help       -> Semua command"
echo ""
echo "  UPDATE:"
echo "    cd $(dirname $SCRIPT_DIR)/dockman"
echo "    git pull && bash install-dockman.sh"
echo ""
echo "  UNINSTALL:"
echo "    bash install-dockman.sh uninstall"
echo ""

if [[ -n "$NEED_RELOGIN" ]]; then
    echo -e "  ${C_YELLOW}PENTING: Logout & login ulang agar docker group aktif!${C_RESET}"
    echo -e "  ${C_YELLOW}Atau jalankan: newgrp docker${C_RESET}"
    echo ""
fi

line
echo ""
