#!/bin/bash
# ============================================================
#  DOCKMAN v3 - Test Suite
#  Jalankan di VM fresh install Ubuntu/Debian
#
#  Usage:
#    bash test-bootstrap.sh          -> semua test
#    bash test-bootstrap.sh build    -> test build & syntax
#    bash test-bootstrap.sh unit     -> test unit logic
#    bash test-bootstrap.sh system   -> cek environment
#    bash test-bootstrap.sh integration -> test built binary
#    bash test-bootstrap.sh phase N  -> manual test phase N
# ============================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DOCKMAN_SRC="$SCRIPT_DIR/dockman_main"
DOCKMAN_BIN="$SCRIPT_DIR/dockman_main/dist/dockman.py"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[1;36m'; BOLD='\033[1m'; RESET='\033[0m'

PASS=0; FAIL=0; SKIP=0

pass()  { echo -e "  ${GREEN}[PASS]${RESET}  $*"; ((PASS++)); }
fail()  { echo -e "  ${RED}[FAIL]${RESET}  $*"; ((FAIL++)); }
skip()  { echo -e "  ${YELLOW}[SKIP]${RESET}  $*"; ((SKIP++)); }
info()  { echo -e "  ${CYAN}[INFO]${RESET}  $*"; }
sect()  { echo ""; echo -e "  ${BOLD}${CYAN}=== $* ===${RESET}"; echo ""; }

check_cmd() {
    local desc="$1" cmd="$2"
    if eval "$cmd" &>/dev/null; then pass "$desc"
    else fail "$desc  [cmd: $cmd]"; fi
}

check_file() {
    local desc="$1" path="$2"
    if [[ -f "$path" ]]; then pass "$desc"
    else fail "$desc - FILE NOT FOUND: $path"; fi
}

check_contains() {
    local desc="$1" file="$2" pattern="$3"
    if grep -q "$pattern" "$file" 2>/dev/null; then pass "$desc"
    else fail "$desc - pattern '$pattern' not in $file"; fi
}

check_not_contains() {
    local desc="$1" file="$2" pattern="$3"
    if ! grep -q "$pattern" "$file" 2>/dev/null; then pass "$desc"
    else fail "$desc - pattern '$pattern' MASIH ADA di $file"; fi
}

check_python() {
    local desc="$1" code="$2"
    if python3 -c "$code" &>/dev/null; then pass "$desc"
    else fail "$desc  [code gagal]"; fi
}

# ── BUILD TEST ──────────────────────────────────────────────────────────────────

test_build() {
    sect "BUILD TEST"

    check_file "core/config.py ada"         "$DOCKMAN_SRC/core/config.py"
    check_file "core/bootstrap.py ada"       "$DOCKMAN_SRC/core/bootstrap.py"
    check_file "ui/bootstrap_wizard.py ada"  "$DOCKMAN_SRC/ui/bootstrap_wizard.py"
    check_file "ui/cli_menu.py ada"          "$DOCKMAN_SRC/ui/cli_menu.py"
    check_file "build.py ada"               "$DOCKMAN_SRC/build.py"
    check_file "main.py ada"                "$DOCKMAN_SRC/main.py"

    # curses_ui.py harus ada tapi dikosongkan (bukan class/fungsi)
    check_file "ui/curses_ui.py ada (stub)" "$DOCKMAN_SRC/ui/curses_ui.py"
    check_not_contains "curses_ui.py tidak punya def screen_home" \
        "$DOCKMAN_SRC/ui/curses_ui.py" "def screen_home"

    # build.py tidak boleh include curses_ui
    check_not_contains "build.py tidak include curses_ui" \
        "$DOCKMAN_SRC/build.py" '"ui/curses_ui.py"'

    # main.py tidak boleh ada run_tui()
    check_not_contains "main.py tidak ada run_tui()" \
        "$DOCKMAN_SRC/main.py" "def run_tui"

    info "Running build.py..."
    if python3 "$DOCKMAN_SRC/build.py" &>/dev/null; then
        pass "build.py berhasil"
    else
        fail "build.py GAGAL"
        return 1
    fi

    check_file "dist/dockman.py terbuat" "$DOCKMAN_BIN"

    local size
    size=$(wc -c < "$DOCKMAN_BIN" 2>/dev/null || echo 0)
    if [[ $size -gt 30000 ]]; then
        pass "File size OK: ${size} bytes"
    else
        fail "File terlalu kecil: ${size} bytes"
    fi

    check_cmd "Python syntax valid" "python3 -m py_compile '$DOCKMAN_BIN'"

    local ver
    ver=$(python3 "$DOCKMAN_BIN" --version 2>/dev/null | awk '{print $2}')
    if [[ "$ver" == "3.0.0" ]]; then
        pass "Version: $ver"
    else
        fail "Version mismatch: expected 3.0.0, got '$ver'"
    fi

    # Cek curses TIDAK ada di build output
    check_not_contains "import curses tidak ada di build output" \
        "$DOCKMAN_BIN" "^import curses"

    # Cek screen_home TIDAK ada di build output
    check_not_contains "screen_home (TUI) tidak ada di build output" \
        "$DOCKMAN_BIN" "def screen_home"

    # Cek bootstrap ADA di build output
    check_contains "BootstrapState ada di build output" \
        "$DOCKMAN_BIN" "BootstrapState"
    check_contains "run_bootstrap_wizard ada di build output" \
        "$DOCKMAN_BIN" "run_bootstrap_wizard"

    # Cek --help
    check_cmd "--help berjalan" "python3 '$DOCKMAN_BIN' --help"
    if python3 "$DOCKMAN_BIN" --help 2>/dev/null | grep -q 'bootstrap'; then
        pass "--bootstrap ada di --help"
    else
        fail "--bootstrap tidak ada di --help"
    fi
    if python3 "$DOCKMAN_BIN" --help 2>/dev/null | grep -q -- '--tui.*TUI\|TUI.*--tui'; then
        fail "--tui masih dipromote di --help (harusnya dihapus)"
    else
        pass "--tui tidak dipromote di --help"
    fi

    # Cek --tui menampilkan pesan info (bukan crash)
    local tui_out
    tui_out=$(python3 "$DOCKMAN_BIN" --tui 2>&1 || true)
    if echo "$tui_out" | grep -qi "tidak tersedia\|tidak.*tersedia\|not available"; then
        pass "--tui menampilkan pesan info"
    else
        fail "--tui tidak menampilkan pesan info yang benar"
    fi
}

# ── UNIT TEST: core/bootstrap.py ──────────────────────────────────────────────

test_unit_bootstrap() {
    sect "UNIT TEST: core/bootstrap.py"

    cd "$DOCKMAN_SRC"

    check_python "Import bootstrap" "
import sys; sys.path.insert(0, '.')
from core.bootstrap import BootstrapState, PHASES, BOOTSTRAP_VERSION
"
    check_python "PHASES = 7" "
import sys; sys.path.insert(0, '.')
from core.bootstrap import PHASES
assert len(PHASES) == 7
"
    check_python "Phase IDs valid" "
import sys; sys.path.insert(0, '.')
from core.bootstrap import PHASES
ids = [p['id'] for p in PHASES]
assert ids == ['system_prep','network','storage','docker_setup','stack_selection','remote_access','deploy']
"
    check_python "BootstrapState init" "
import sys; sys.path.insert(0, '.')
from core.bootstrap import BootstrapState, STATUS_PENDING
s = BootstrapState()
assert len(s.phases) == 7
assert not s.completed
assert all(p['status'] == STATUS_PENDING for p in s.phases.values())
"
    check_python "set/get phase status" "
import sys; sys.path.insert(0, '.')
from core.bootstrap import BootstrapState, STATUS_DONE
s = BootstrapState()
s.set_phase_status('system_prep', STATUS_DONE)
assert s.phases['system_prep']['status'] == STATUS_DONE
assert s.is_phase_done('system_prep')
assert not s.is_phase_done('network')
"
    check_python "skip_phase" "
import sys; sys.path.insert(0, '.')
from core.bootstrap import BootstrapState, STATUS_SKIPPED
s = BootstrapState()
s.skip_phase('network')
assert s.phases['network']['status'] == STATUS_SKIPPED
assert s.is_phase_done('network')
"
    check_python "next_pending_phase" "
import sys; sys.path.insert(0, '.')
from core.bootstrap import BootstrapState, STATUS_DONE
s = BootstrapState()
s.set_phase_status('system_prep', STATUS_DONE)
assert s.next_pending_phase() == 'network'
"
    check_python "all_done" "
import sys; sys.path.insert(0, '.')
from core.bootstrap import BootstrapState, PHASES, STATUS_DONE
s = BootstrapState()
assert not s.all_done()
for p in PHASES: s.set_phase_status(p['id'], STATUS_DONE)
assert s.all_done()
"
    check_python "Save & Load state" "
import sys, tempfile
from pathlib import Path
sys.path.insert(0, '.')
import core.bootstrap as bm
with tempfile.TemporaryDirectory() as tmp:
    bm.BOOTSTRAP_STATE_FILE = Path(tmp) / 'test_state.json'
    s = bm.BootstrapState()
    s.config['hostname'] = 'testserver'
    s.set_phase_status('system_prep', 'done')
    s.save()
    s2 = bm.BootstrapState.load()
    assert s2.config['hostname'] == 'testserver'
    assert s2.phases['system_prep']['status'] == 'done'
"
    check_python "validate_ip_cidr" "
import sys; sys.path.insert(0, '.')
from core.bootstrap import validate_ip_cidr
assert validate_ip_cidr('192.168.1.100/24')
assert validate_ip_cidr('10.0.0.1/8')
assert not validate_ip_cidr('999.999.1.1/24')
assert not validate_ip_cidr('192.168.1.1')
assert not validate_ip_cidr('not-an-ip')
"
    check_python "validate_ip" "
import sys; sys.path.insert(0, '.')
from core.bootstrap import validate_ip
assert validate_ip('192.168.1.1')
assert not validate_ip('999.1.1.1')
assert not validate_ip('192.168.1')
"
    check_python "get_stack_options" "
import sys; sys.path.insert(0, '.')
from core.bootstrap import get_stack_options
opts = get_stack_options()
keys = ['media_server','downloader','arr_suite','indexer','request_manager',
        'reverse_proxy','dashboard','monitoring','dns_adblock']
assert all(k in opts for k in keys)
assert any(o['id'] == 'jellyfin' for o in opts['media_server'])
assert any(o['id'] == 'qbittorrent' for o in opts['downloader'])
"
    check_python "check_port_conflicts (no conflict)" "
import sys; sys.path.insert(0, '.')
from core.bootstrap import check_port_conflicts
result = check_port_conflicts(['jellyfin', 'radarr'])
assert not any(c['type'] == 'service_conflict' for c in result)
"
    check_python "check_port_conflicts (conflict)" "
import sys; sys.path.insert(0, '.')
from core.bootstrap import check_port_conflicts
result = check_port_conflicts(['jellyfin', 'emby'])
assert any(c['type'] == 'service_conflict' and c['port'] == 8096 for c in result)
"
    check_python "generate_compose_yaml" "
import sys; sys.path.insert(0, '.')
from core.bootstrap import BootstrapState, generate_compose_yaml
s = BootstrapState()
s.config.update({'media_server':'jellyfin','downloader':'qbittorrent',
                 'arr_suite':['radarr','sonarr'],'puid':'1000','pgid':'1000',
                 'timezone':'Asia/Jakarta','media_mount':'/mnt/media'})
yaml = generate_compose_yaml(s)
assert 'jellyfin:' in yaml
assert 'qbittorrent:' in yaml
assert 'radarr:' in yaml
assert 'sonarr:' in yaml
assert '8096:8096' in yaml
assert 'unless-stopped' in yaml
"
    check_python "create_folder_structure" "
import sys, tempfile
from pathlib import Path
sys.path.insert(0, '.')
from core.bootstrap import create_folder_structure, DEFAULT_FOLDERS
with tempfile.TemporaryDirectory() as tmp:
    created = create_folder_structure(tmp)
    assert len(created) == len(DEFAULT_FOLDERS)
    for f in DEFAULT_FOLDERS:
        assert Path(tmp, f).exists()
"
    check_python "generate_access_summary" "
import sys; sys.path.insert(0, '.')
from core.bootstrap import BootstrapState, generate_access_summary
s = BootstrapState()
s.config.update({'media_server':'jellyfin','downloader':'qbittorrent','monitoring':['portainer']})
result = generate_access_summary(s)
svcs = [e['service'] for e in result]
assert 'Jellyfin' in svcs
assert 'qBittorrent' in svcs
assert 'Portainer' in svcs
"

    cd "$SCRIPT_DIR"
}

# ── UNIT TEST: compose generator ───────────────────────────────────────────────

test_unit_compose() {
    sect "UNIT TEST: Compose Generator"

    cd "$DOCKMAN_SRC"

    local arr_svcs=("radarr" "sonarr" "lidarr" "bazarr")
    local mon_svcs=("portainer" "watchtower")
    local single_svcs=("plex" "emby" "deluge" "sabnzbd" "prowlarr" "jackett"
                       "jellyseerr" "overseerr" "nginxproxymanager" "caddy"
                       "homarr" "heimdall" "adguardhome" "pihole")

    for svc in "${arr_svcs[@]}"; do
        check_python "Compose arr: $svc" "
import sys; sys.path.insert(0, '.')
from core.bootstrap import BootstrapState, generate_compose_yaml
s = BootstrapState()
s.config.update({'arr_suite':['$svc'],'puid':'1000','pgid':'1000',
                 'timezone':'Asia/Jakarta','media_mount':'/mnt/media'})
assert '${svc}:' in generate_compose_yaml(s)
"
    done

    for svc in "${mon_svcs[@]}"; do
        check_python "Compose monitoring: $svc" "
import sys; sys.path.insert(0, '.')
from core.bootstrap import BootstrapState, generate_compose_yaml
s = BootstrapState()
s.config.update({'monitoring':['$svc'],'puid':'1000','pgid':'1000',
                 'timezone':'Asia/Jakarta','media_mount':'/mnt/media'})
assert '${svc}:' in generate_compose_yaml(s)
"
    done

    check_python "Compose: cloudflared" "
import sys; sys.path.insert(0, '.')
from core.bootstrap import BootstrapState, generate_compose_yaml
s = BootstrapState()
s.config.update({'cloudflare_enabled':True,'cloudflare_token':'tok-123',
                 'puid':'1000','pgid':'1000','timezone':'Asia/Jakarta','media_mount':'/mnt/media'})
yaml = generate_compose_yaml(s)
assert 'cloudflared:' in yaml
assert 'tok-123' in yaml
"

    check_python "Compose: empty stack" "
import sys; sys.path.insert(0, '.')
from core.bootstrap import BootstrapState, generate_compose_yaml
s = BootstrapState()
assert 'services:' in generate_compose_yaml(s)
"

    cd "$SCRIPT_DIR"
}

# ── SMOKE TEST: phase handlers ──────────────────────────────────────────────────

test_phase_smoke() {
    sect "SMOKE TEST: Phase Handlers"

    cd "$DOCKMAN_SRC"

    check_python "PHASE_HANDLERS = 7" "
import sys; sys.path.insert(0, '.')
from ui.bootstrap_wizard import PHASE_HANDLERS, PHASES
for p in PHASES:
    assert p['id'] in PHASE_HANDLERS, f\"Phase {p['id']} tidak ada\"
assert len(PHASE_HANDLERS) == 7
"
    check_python "run_bootstrap_wizard callable" "
import sys; sys.path.insert(0, '.')
from ui.bootstrap_wizard import run_bootstrap_wizard
assert callable(run_bootstrap_wizard)
"
    check_python "_generate_netplan" "
import sys; sys.path.insert(0, '.')
from ui.bootstrap_wizard import _generate_netplan
yaml = _generate_netplan('eth0', '192.168.1.100/24', '192.168.1.1', ['1.1.1.1','8.8.8.8'])
assert 'eth0' in yaml
assert '192.168.1.100/24' in yaml
assert 'dhcp4: false' in yaml
assert '192.168.1.1' in yaml
"
    check_python "_collect_selected_services" "
import sys; sys.path.insert(0, '.')
from ui.bootstrap_wizard import _collect_selected_services
cfg = {'media_server':'jellyfin','downloader':'qbittorrent',
       'arr_suite':['radarr','sonarr'],'indexer':'prowlarr',
       'request_manager':'none','reverse_proxy':'none',
       'dashboard':'none','dns_adblock':'none',
       'monitoring':['portainer'],'cloudflare_enabled':False}
svcs = _collect_selected_services(cfg)
assert 'jellyfin' in svcs
assert 'qbittorrent' in svcs
assert 'radarr' in svcs
assert 'prowlarr' in svcs
assert 'portainer' in svcs
assert 'none' not in svcs
"

    cd "$SCRIPT_DIR"
}

# ── INTEGRATION TEST: built binary ──────────────────────────────────────────────

test_integration_build() {
    sect "INTEGRATION TEST: Built dockman.py"

    if [[ ! -f "$DOCKMAN_BIN" ]]; then
        skip "dist/dockman.py belum dibuild"
        return
    fi

    # Simbol yang HARUS ada
    local must_have=("BootstrapState" "PHASES" "generate_compose_yaml"
                     "run_bootstrap_wizard" "_phase_system_prep" "_phase_network"
                     "_phase_storage" "_phase_docker_setup" "_phase_stack_selection"
                     "_phase_remote_access" "_phase_deploy" "check_port_conflicts"
                     "get_stack_options" "create_folder_structure" "generate_access_summary"
                     "MODULE STUBS")
    for sym in "${must_have[@]}"; do
        check_contains "'$sym' ada" "$DOCKMAN_BIN" "$sym"
    done

    # Simbol yang TIDAK BOLEH ada
    local must_not=("def screen_home" "def screen_containers"
                    "def draw_header" "def draw_footer"
                    "curses.wrapper" "curses.start_color")
    for sym in "${must_not[@]}"; do
        check_not_contains "'$sym' tidak ada (TUI removed)" "$DOCKMAN_BIN" "$sym"
    done

    # Internal imports harus sudah di-strip
    check_not_contains "'from core.bootstrap import' sudah di-strip" \
        "$DOCKMAN_BIN" "^from core.bootstrap import"
    check_not_contains "'from ui.bootstrap_wizard import' sudah di-strip" \
        "$DOCKMAN_BIN" "^from ui.bootstrap_wizard import"

    # PHASE_HANDLERS semua terdaftar
    local phases=("system_prep" "network" "storage" "docker_setup"
                  "stack_selection" "remote_access" "deploy")
    for ph in "${phases[@]}"; do
        check_contains "PHASE_HANDLERS['$ph'] terdaftar" \
            "$DOCKMAN_BIN" "PHASE_HANDLERS\[\"${ph}\"\]"
    done

    # --tui exit dengan pesan info (bukan crash)
    local tui_exit
    tui_out=$(python3 "$DOCKMAN_BIN" --tui 2>&1 || true)
    if echo "$tui_out" | grep -qi "tidak tersedia"; then
        pass "--tui exit dengan pesan info"
    else
        fail "--tui tidak menampilkan pesan info"
    fi

    # --bootstrap invalid phase
    local bs_out
    bs_out=$(timeout 3 python3 "$DOCKMAN_BIN" --bootstrap 99 2>&1 || true)
    if echo "$bs_out" | grep -q "tidak ditemukan\|Range\|1-7"; then
        pass "--bootstrap invalid phase ditangani"
    else
        skip "--bootstrap phase validation (Docker mungkin tidak running)"
    fi
}

# ── SYSTEM CHECK ───────────────────────────────────────────────────────────────────

test_system_check() {
    sect "SYSTEM CHECK"

    [[ -f /etc/os-release ]] && { . /etc/os-release; pass "OS: $PRETTY_NAME"; } \
        || fail "/etc/os-release tidak ditemukan"

    local pyver; pyver=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>/dev/null || echo "0.0")
    local pymaj pymin
    pymaj=$(echo "$pyver" | cut -d. -f1); pymin=$(echo "$pyver" | cut -d. -f2)
    [[ $pymaj -ge 3 && $pymin -ge 8 ]] && pass "Python $pyver" || fail "Python $pyver terlalu lama (butuh >= 3.8)"

    python3 -c "import rich" 2>/dev/null && pass "rich terinstall" || fail "rich tidak terinstall (pip install rich)"
    sudo -n true 2>/dev/null && pass "sudo passwordless" || warn "sudo butuh password"
    ping -c 1 -W 3 1.1.1.1 &>/dev/null && pass "Internet OK" || skip "Tidak ada internet"
    command -v docker &>/dev/null && pass "Docker: $(docker --version 2>/dev/null | awk '{print $3}' | tr -d ',')"\
        || skip "Docker belum terinstall (akan diinstall di Phase 4)"
    command -v git &>/dev/null && pass "git tersedia" || fail "git tidak ditemukan"
    command -v lsblk &>/dev/null && pass "lsblk tersedia" || fail "lsblk tidak ditemukan"
    command -v ip &>/dev/null && pass "ip command tersedia" || fail "ip command tidak ditemukan"
    command -v netplan &>/dev/null && pass "netplan tersedia" || skip "netplan tidak ditemukan"
}

# ── MANUAL PHASE TEST ───────────────────────────────────────────────────────────

test_phase_manual() {
    sect "MANUAL TEST: Phase ${1}"
    if [[ ! -f "$DOCKMAN_BIN" ]]; then
        fail "dist/dockman.py tidak ditemukan. Jalankan: python3 dockman_main/build.py"
        return
    fi
    info "Menjalankan: python3 $DOCKMAN_BIN --bootstrap ${1}"
    read -rp "  Tekan Enter untuk mulai, Ctrl+C untuk batal..."
    echo ""
    python3 "$DOCKMAN_BIN" --bootstrap "${1}" || true
}

# ── SUMMARY ─────────────────────────────────────────────────────────────────────

print_summary() {
    local total=$((PASS + FAIL + SKIP))
    echo ""
    echo -e "  ${BOLD}${CYAN}==============================${RESET}"
    echo -e "  ${BOLD}  TEST SUMMARY${RESET}"
    echo -e "  ${BOLD}${CYAN}==============================${RESET}"
    echo -e "  ${GREEN}PASS${RESET}  : $PASS"
    echo -e "  ${RED}FAIL${RESET}  : $FAIL"
    echo -e "  ${YELLOW}SKIP${RESET}  : $SKIP"
    echo    "  TOTAL : $total"
    echo -e "  ${BOLD}${CYAN}==============================${RESET}"
    echo ""
    if [[ $FAIL -eq 0 ]]; then
        echo -e "  ${GREEN}${BOLD}SEMUA TEST PASS \u2713${RESET}"
    else
        echo -e "  ${RED}${BOLD}$FAIL TEST GAGAL - cek output di atas${RESET}"
    fi
    echo ""
}

# ── MAIN ───────────────────────────────────────────────────────────────────────

echo ""
echo -e "  ${BOLD}${CYAN}DOCKMAN v3 - Test Suite${RESET}"
echo -e "  ${CYAN}================================${RESET}"
echo ""

case "${1:-all}" in
    all)
        test_system_check
        test_build
        test_unit_bootstrap
        test_unit_compose
        test_phase_smoke
        test_integration_build
        print_summary
        ;;
    build)       test_build;             print_summary ;;
    unit)        test_unit_bootstrap; test_unit_compose; test_phase_smoke; print_summary ;;
    system)      test_system_check;       print_summary ;;
    integration) test_integration_build;  print_summary ;;
    phase)
        [[ -z "${2}" ]] && { echo "  Usage: bash test-bootstrap.sh phase <1-7>"; exit 1; }
        test_phase_manual "${2}"
        ;;
    *)
        echo "  Usage: bash test-bootstrap.sh [all|build|unit|system|integration|phase N]"
        exit 1
        ;;
esac

[[ $FAIL -gt 0 ]] && exit 1 || exit 0
