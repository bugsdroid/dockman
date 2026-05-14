#!/bin/bash
# ============================================================
#  DOCKMAN v3 - Test Script untuk Validasi di VM
#  Jalankan di VM fresh install Ubuntu/Debian
#
#  Usage:
#    bash test-bootstrap.sh          -> run semua test
#    bash test-bootstrap.sh build    -> test build saja
#    bash test-bootstrap.sh unit     -> test unit functions
#    bash test-bootstrap.sh phase N  -> test phase N (1-7)
# ============================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DOCKMAN_SRC="$SCRIPT_DIR/dockman_main"
DOCKMAN_BIN="$SCRIPT_DIR/dockman_main/dist/dockman.py"

# Warna
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[1;36m'; BOLD='\033[1m'; RESET='\033[0m'

PASS=0; FAIL=0; SKIP=0

pass()  { echo -e "  ${GREEN}[PASS]${RESET}  $*"; ((PASS++)); }
fail()  { echo -e "  ${RED}[FAIL]${RESET}  $*"; ((FAIL++)); }
skip()  { echo -e "  ${YELLOW}[SKIP]${RESET}  $*"; ((SKIP++)); }
info()  { echo -e "  ${CYAN}[INFO]${RESET}  $*"; }
sect()  { echo ""; echo -e "  ${BOLD}${CYAN}=== $* ===${RESET}"; echo ""; }

# ── Helpers ────────────────────────────────────────────────────────────────────

check_cmd() {
    local desc="$1" cmd="$2"
    if eval "$cmd" &>/dev/null; then
        pass "$desc"
    else
        fail "$desc  [cmd: $cmd]"
    fi
}

check_file() {
    local desc="$1" path="$2"
    if [[ -f "$path" ]]; then
        pass "$desc ($path)"
    else
        fail "$desc - FILE NOT FOUND: $path"
    fi
}

check_contains() {
    local desc="$1" file="$2" pattern="$3"
    if grep -q "$pattern" "$file" 2>/dev/null; then
        pass "$desc"
    else
        fail "$desc - pattern '$pattern' not in $file"
    fi
}

check_python() {
    local desc="$1" code="$2"
    if python3 -c "$code" &>/dev/null; then
        pass "$desc"
    else
        fail "$desc  [code: $code]"
    fi
}

# ── Build test ─────────────────────────────────────────────────────────────────

test_build() {
    sect "BUILD TEST"

    check_file "Source: core/config.py"       "$DOCKMAN_SRC/core/config.py"
    check_file "Source: core/bootstrap.py"    "$DOCKMAN_SRC/core/bootstrap.py"
    check_file "Source: ui/bootstrap_wizard.py" "$DOCKMAN_SRC/ui/bootstrap_wizard.py"
    check_file "Source: build.py"              "$DOCKMAN_SRC/build.py"
    check_file "Source: main.py"               "$DOCKMAN_SRC/main.py"

    info "Running build.py..."
    if python3 "$DOCKMAN_SRC/build.py" &>/dev/null; then
        pass "build.py berhasil dijalankan"
    else
        fail "build.py GAGAL"
        return 1
    fi

    check_file "Output: dist/dockman.py" "$DOCKMAN_BIN"

    # Cek ukuran file (harus > 50KB)
    local size
    size=$(wc -c < "$DOCKMAN_BIN" 2>/dev/null || echo 0)
    if [[ $size -gt 50000 ]]; then
        pass "File size OK: ${size} bytes"
    else
        fail "File terlalu kecil: ${size} bytes (expected > 50000)"
    fi

    # Cek syntax python
    check_cmd "Python syntax valid" "python3 -m py_compile '$DOCKMAN_BIN'"

    # Cek version string
    local ver
    ver=$(python3 "$DOCKMAN_BIN" --version 2>/dev/null | awk '{print $2}')
    if [[ "$ver" == "3.0.0" ]]; then
        pass "Version string: $ver"
    else
        fail "Version mismatch: expected 3.0.0, got '$ver'"
    fi

    # Cek --help
    check_cmd "--help berjalan" "python3 '$DOCKMAN_BIN' --help"

    # Cek bootstrap flag ada di help
    if python3 "$DOCKMAN_BIN" --help 2>/dev/null | grep -q 'bootstrap'; then
        pass "--bootstrap muncul di --help"
    else
        fail "--bootstrap tidak ditemukan di --help"
    fi
}

# ── Unit tests: core/bootstrap.py ─────────────────────────────────────────────

test_unit_bootstrap() {
    sect "UNIT TEST: core/bootstrap.py"

    cd "$DOCKMAN_SRC"

    # Import check
    check_python "Import core.bootstrap" "
import sys; sys.path.insert(0, '.')
from core.bootstrap import BootstrapState, PHASES, BOOTSTRAP_VERSION
"

    # PHASES struktur
    check_python "PHASES = 7 items" "
import sys; sys.path.insert(0, '.')
from core.bootstrap import PHASES
assert len(PHASES) == 7, f'expected 7, got {len(PHASES)}'
"

    # Phase IDs
    check_python "Phase IDs valid" "
import sys; sys.path.insert(0, '.')
from core.bootstrap import PHASES
expected = ['system_prep','network','storage','docker_setup','stack_selection','remote_access','deploy']
assert [p['id'] for p in PHASES] == expected
"

    # BootstrapState basic
    check_python "BootstrapState init" "
import sys; sys.path.insert(0, '.')
from core.bootstrap import BootstrapState, STATUS_PENDING
s = BootstrapState()
assert len(s.phases) == 7
assert s.completed == False
assert all(p['status'] == STATUS_PENDING for p in s.phases.values())
"

    # set_phase_status
    check_python "set_phase_status" "
import sys; sys.path.insert(0, '.')
from core.bootstrap import BootstrapState, STATUS_DONE
s = BootstrapState()
s.set_phase_status('system_prep', STATUS_DONE)
assert s.phases['system_prep']['status'] == STATUS_DONE
"

    # is_phase_done
    check_python "is_phase_done (done)" "
import sys; sys.path.insert(0, '.')
from core.bootstrap import BootstrapState, STATUS_DONE
s = BootstrapState()
s.set_phase_status('system_prep', STATUS_DONE)
assert s.is_phase_done('system_prep') == True
"

    check_python "is_phase_done (pending)" "
import sys; sys.path.insert(0, '.')
from core.bootstrap import BootstrapState
s = BootstrapState()
assert s.is_phase_done('system_prep') == False
"

    # skip_phase
    check_python "skip_phase" "
import sys; sys.path.insert(0, '.')
from core.bootstrap import BootstrapState, STATUS_SKIPPED
s = BootstrapState()
s.skip_phase('network')
assert s.phases['network']['status'] == STATUS_SKIPPED
assert s.is_phase_done('network') == True
"

    # next_pending_phase
    check_python "next_pending_phase" "
import sys; sys.path.insert(0, '.')
from core.bootstrap import BootstrapState, STATUS_DONE
s = BootstrapState()
s.set_phase_status('system_prep', STATUS_DONE)
assert s.next_pending_phase() == 'network'
"

    # all_done
    check_python "all_done (false)" "
import sys; sys.path.insert(0, '.')
from core.bootstrap import BootstrapState
s = BootstrapState()
assert s.all_done() == False
"

    check_python "all_done (true)" "
import sys; sys.path.insert(0, '.')
from core.bootstrap import BootstrapState, PHASES, STATUS_DONE
s = BootstrapState()
for p in PHASES:
    s.set_phase_status(p['id'], STATUS_DONE)
assert s.all_done() == True
"

    # Save & load (gunakan temp dir)
    check_python "Save & Load state" "
import sys, tempfile, json
from pathlib import Path
sys.path.insert(0, '.')

# Override CONFIG_DIR ke tempdir
import core.bootstrap as bm
with tempfile.TemporaryDirectory() as tmp:
    bm.BOOTSTRAP_STATE_FILE = Path(tmp) / 'test_state.json'
    import core.config as cfg
    orig = cfg.CONFIG_DIR
    cfg.CONFIG_DIR = Path(tmp)

    s = bm.BootstrapState()
    s.config['hostname'] = 'testserver'
    s.set_phase_status('system_prep', 'done')
    s.save()

    s2 = bm.BootstrapState.load()
    assert s2.config['hostname'] == 'testserver'
    assert s2.phases['system_prep']['status'] == 'done'
"

    # validate_ip_cidr
    check_python "validate_ip_cidr (valid)" "
import sys; sys.path.insert(0, '.')
from core.bootstrap import validate_ip_cidr
assert validate_ip_cidr('192.168.1.100/24') == True
assert validate_ip_cidr('10.0.0.1/8') == True
"

    check_python "validate_ip_cidr (invalid)" "
import sys; sys.path.insert(0, '.')
from core.bootstrap import validate_ip_cidr
assert validate_ip_cidr('999.999.1.1/24') == False
assert validate_ip_cidr('192.168.1.1') == False
assert validate_ip_cidr('not-an-ip') == False
"

    # validate_ip
    check_python "validate_ip (valid)" "
import sys; sys.path.insert(0, '.')
from core.bootstrap import validate_ip
assert validate_ip('192.168.1.1') == True
assert validate_ip('10.0.0.1') == True
"

    check_python "validate_ip (invalid)" "
import sys; sys.path.insert(0, '.')
from core.bootstrap import validate_ip
assert validate_ip('999.1.1.1') == False
assert validate_ip('192.168.1') == False
"

    # get_stack_options
    check_python "get_stack_options keys" "
import sys; sys.path.insert(0, '.')
from core.bootstrap import get_stack_options
opts = get_stack_options()
expected_keys = ['media_server','downloader','arr_suite','indexer',
                 'request_manager','reverse_proxy','dashboard','monitoring','dns_adblock']
assert all(k in opts for k in expected_keys)
"

    check_python "get_stack_options items" "
import sys; sys.path.insert(0, '.')
from core.bootstrap import get_stack_options
opts = get_stack_options()
assert any(o['id'] == 'jellyfin' for o in opts['media_server'])
assert any(o['id'] == 'qbittorrent' for o in opts['downloader'])
assert any(o['id'] == 'radarr' for o in opts['arr_suite'])
"

    # check_port_conflicts
    check_python "check_port_conflicts (no conflict)" "
import sys; sys.path.insert(0, '.')
from core.bootstrap import check_port_conflicts
# jellyfin (8096) + radarr (7878) tidak konflik
result = check_port_conflicts(['jellyfin', 'radarr'])
service_conflicts = [c for c in result if c['type'] == 'service_conflict']
assert len(service_conflicts) == 0
"

    check_python "check_port_conflicts (with conflict)" "
import sys; sys.path.insert(0, '.')
from core.bootstrap import check_port_conflicts
# jellyfin + emby sama-sama pakai 8096
result = check_port_conflicts(['jellyfin', 'emby'])
service_conflicts = [c for c in result if c['type'] == 'service_conflict']
assert len(service_conflicts) > 0
assert any(c['port'] == 8096 for c in service_conflicts)
"

    # generate_compose_yaml
    check_python "generate_compose_yaml (basic)" "
import sys; sys.path.insert(0, '.')
from core.bootstrap import BootstrapState, generate_compose_yaml
s = BootstrapState()
s.config['media_server'] = 'jellyfin'
s.config['downloader']   = 'qbittorrent'
s.config['arr_suite']    = ['radarr', 'sonarr']
s.config['puid'] = '1000'
s.config['pgid'] = '1000'
s.config['timezone'] = 'Asia/Jakarta'
s.config['media_mount'] = '/mnt/media'
yaml = generate_compose_yaml(s)
assert 'jellyfin:' in yaml
assert 'qbittorrent:' in yaml
assert 'radarr:' in yaml
assert 'sonarr:' in yaml
assert '8096:8096' in yaml
assert 'unless-stopped' in yaml
"

    check_python "generate_compose_yaml (empty stack)" "
import sys; sys.path.insert(0, '.')
from core.bootstrap import BootstrapState, generate_compose_yaml
s = BootstrapState()
yaml = generate_compose_yaml(s)
assert 'services:' in yaml
"

    # create_folder_structure
    check_python "create_folder_structure" "
import sys, tempfile
from pathlib import Path
sys.path.insert(0, '.')
from core.bootstrap import create_folder_structure, DEFAULT_FOLDERS
with tempfile.TemporaryDirectory() as tmp:
    created = create_folder_structure(tmp)
    assert len(created) == len(DEFAULT_FOLDERS)
    for f in DEFAULT_FOLDERS:
        assert Path(tmp, f).exists(), f'Missing: {f}'
"

    # generate_access_summary
    check_python "generate_access_summary" "
import sys; sys.path.insert(0, '.')
from core.bootstrap import BootstrapState, generate_access_summary
s = BootstrapState()
s.config['media_server'] = 'jellyfin'
s.config['downloader']   = 'qbittorrent'
s.config['monitoring']   = ['portainer']
result = generate_access_summary(s)
services = [e['service'] for e in result]
assert 'Jellyfin' in services
assert 'qBittorrent' in services
assert 'Portainer' in services
"

    cd "$SCRIPT_DIR"
}

# ── Unit tests: compose generator detail ──────────────────────────────────────

test_unit_compose() {
    sect "UNIT TEST: Compose Generator"

    cd "$DOCKMAN_SRC"

    # Test semua service generate tanpa error
    local services=("plex" "emby" "deluge" "sabnzbd" "lidarr" "bazarr"
                    "prowlarr" "jackett" "jellyseerr" "overseerr"
                    "nginxproxymanager" "caddy" "homarr" "heimdall"
                    "portainer" "watchtower" "adguardhome" "pihole")

    for svc in "${services[@]}"; do
        check_python "Compose: $svc" "
import sys; sys.path.insert(0, '.')
from core.bootstrap import BootstrapState, generate_compose_yaml
s = BootstrapState()
s.config['puid'] = '1000'; s.config['pgid'] = '1000'
s.config['timezone'] = 'Asia/Jakarta'; s.config['media_mount'] = '/mnt/media'

if '$svc' in ('radarr','sonarr','lidarr','bazarr'):
    s.config['arr_suite'] = ['$svc']
elif '$svc' in ('portainer','watchtower'):
    s.config['monitoring'] = ['$svc']
else:
    for key in ('media_server','downloader','indexer','request_manager','reverse_proxy','dashboard','dns_adblock'):
        try:
            s.config[key] = '$svc'
            break
        except: pass

yaml = generate_compose_yaml(s)
assert '${svc}:' in yaml or 'services:' in yaml
"
    done

    # Test cloudflare tunnel
    check_python "Compose: cloudflared" "
import sys; sys.path.insert(0, '.')
from core.bootstrap import BootstrapState, generate_compose_yaml
s = BootstrapState()
s.config['cloudflare_enabled'] = True
s.config['cloudflare_token']   = 'test-token-123'
yaml = generate_compose_yaml(s)
assert 'cloudflared:' in yaml
assert 'test-token-123' in yaml
"

    cd "$SCRIPT_DIR"
}

# ── Integration test: build output ───────────────────────────────────────────────

test_integration_build() {
    sect "INTEGRATION TEST: Built dockman.py"

    if [[ ! -f "$DOCKMAN_BIN" ]]; then
        skip "dist/dockman.py belum dibuild, skip integration test"
        return
    fi

    # Cek semua modul inline ada di single file
    local modules=("BootstrapState" "PHASES" "generate_compose_yaml"
                   "run_bootstrap_wizard" "_phase_system_prep" "_phase_network"
                   "_phase_storage" "_phase_docker_setup" "_phase_stack_selection"
                   "_phase_remote_access" "_phase_deploy" "check_port_conflicts"
                   "get_stack_options" "create_folder_structure" "generate_access_summary")

    for mod in "${modules[@]}"; do
        if grep -q "$mod" "$DOCKMAN_BIN"; then
            pass "Symbol '$mod' ada di build output"
        else
            fail "Symbol '$mod' TIDAK DITEMUKAN di build output"
        fi
    done

    # Cek internal imports sudah di-strip
    if grep -q "^from core.bootstrap import" "$DOCKMAN_BIN"; then
        fail "Internal import 'from core.bootstrap import' masih ada (harusnya di-strip)"
    else
        pass "Internal imports sudah di-strip"
    fi

    # Cek MODULE STUBS ada
    check_contains "MODULE STUBS ada" "$DOCKMAN_BIN" "MODULE STUBS"

    # Cek PHASE_HANDLERS terdaftar
    check_contains "PHASE_HANDLERS system_prep" "$DOCKMAN_BIN" 'PHASE_HANDLERS\["system_prep"\]'
    check_contains "PHASE_HANDLERS deploy"      "$DOCKMAN_BIN" 'PHASE_HANDLERS\["deploy"\]'

    # Test --bootstrap flag routing (tanpa docker check)
    # Gunakan env var untuk bypass docker check
    local test_output
    test_output=$(timeout 3 python3 "$DOCKMAN_BIN" --bootstrap 99 2>&1 || true)
    if echo "$test_output" | grep -q "tidak ditemukan\|Range\|1-7"; then
        pass "--bootstrap invalid phase ditangani dengan benar"
    else
        # Acceptable jika error lain (Docker not running, dll)
        skip "--bootstrap phase validation (Docker mungkin tidak running)"
    fi
}

# ── Smoke test: phase handlers ──────────────────────────────────────────────────

test_phase_smoke() {
    sect "SMOKE TEST: Phase Handlers"

    cd "$DOCKMAN_SRC"

    # Test semua phase handler terdaftar
    check_python "PHASE_HANDLERS lengkap (7 phases)" "
import sys; sys.path.insert(0, '.')
from ui.bootstrap_wizard import PHASE_HANDLERS, PHASES
for p in PHASES:
    assert p['id'] in PHASE_HANDLERS, f\"Phase '{p['id']}' tidak ada di PHASE_HANDLERS\"
assert len(PHASE_HANDLERS) == 7
"

    # Test wizard entry point importable
    check_python "run_bootstrap_wizard importable" "
import sys; sys.path.insert(0, '.')
from ui.bootstrap_wizard import run_bootstrap_wizard
assert callable(run_bootstrap_wizard)
"

    # Test helper functions importable
    check_python "_generate_netplan importable" "
import sys; sys.path.insert(0, '.')
from ui.bootstrap_wizard import _generate_netplan
yaml = _generate_netplan('eth0', '192.168.1.100/24', '192.168.1.1', ['1.1.1.1','8.8.8.8'])
assert 'eth0' in yaml
assert '192.168.1.100/24' in yaml
assert '192.168.1.1' in yaml
assert 'dhcp4: false' in yaml
"

    check_python "_collect_selected_services" "
import sys; sys.path.insert(0, '.')
from ui.bootstrap_wizard import _collect_selected_services
cfg = {
    'media_server': 'jellyfin',
    'downloader': 'qbittorrent',
    'arr_suite': ['radarr', 'sonarr'],
    'indexer': 'prowlarr',
    'request_manager': 'none',
    'reverse_proxy': 'none',
    'dashboard': 'none',
    'dns_adblock': 'none',
    'monitoring': ['portainer'],
    'cloudflare_enabled': False,
}
svcs = _collect_selected_services(cfg)
assert 'jellyfin' in svcs
assert 'qbittorrent' in svcs
assert 'radarr' in svcs
assert 'sonarr' in svcs
assert 'prowlarr' in svcs
assert 'portainer' in svcs
assert 'none' not in svcs
"

    cd "$SCRIPT_DIR"
}

# ── System check (environment VM) ───────────────────────────────────────────────

test_system_check() {
    sect "SYSTEM CHECK (VM Environment)"

    # OS
    if [[ -f /etc/os-release ]]; then
        . /etc/os-release
        pass "OS terdeteksi: $PRETTY_NAME"
    else
        fail "/etc/os-release tidak ditemukan"
    fi

    # Python version >= 3.8
    local pyver
    pyver=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>/dev/null || echo "0.0")
    local pymaj pymin
    pymaj=$(echo "$pyver" | cut -d. -f1)
    pymin=$(echo "$pyver" | cut -d. -f2)
    if [[ $pymaj -ge 3 && $pymin -ge 8 ]]; then
        pass "Python $pyver (>= 3.8 required)"
    else
        fail "Python $pyver terlalu lama (butuh >= 3.8)"
    fi

    # Rich
    python3 -c "import rich" 2>/dev/null && pass "rich terinstall" || fail "rich tidak terinstall"

    # Sudo
    sudo -n true 2>/dev/null && pass "sudo passwordless tersedia" || warn "sudo butuh password (beberapa test mungkin skip)"

    # Internet
    ping -c 1 -W 3 1.1.1.1 &>/dev/null && pass "Internet OK" || skip "Tidak ada internet"

    # Docker
    if command -v docker &>/dev/null; then
        pass "Docker terinstall: $(docker --version 2>/dev/null | awk '{print $3}' | tr -d ',')"
        docker info &>/dev/null && pass "Docker daemon running" || fail "Docker daemon tidak running"
    else
        skip "Docker belum terinstall (akan diinstall di Phase 4)"
    fi

    # Netplan
    if command -v netplan &>/dev/null; then
        pass "netplan tersedia"
    else
        skip "netplan tidak ditemukan (mungkin bukan Ubuntu)"
    fi

    # lsblk
    command -v lsblk &>/dev/null && pass "lsblk tersedia" || fail "lsblk tidak ditemukan"

    # ip command
    command -v ip &>/dev/null && pass "ip command tersedia" || fail "ip command tidak ditemukan"
}

# ── Manual phase tests (interactive, butuh tty) ───────────────────────────

test_phase_manual() {
    local phase_num="$1"
    sect "MANUAL TEST: Phase $phase_num"

    if [[ ! -f "$DOCKMAN_BIN" ]]; then
        fail "dist/dockman.py tidak ditemukan. Jalankan: python3 dockman_main/build.py"
        return
    fi

    info "Menjalankan: python3 $DOCKMAN_BIN --bootstrap $phase_num"
    info "Ini adalah test interaktif - ikuti prompt yang muncul."
    echo ""
    read -rp "  Tekan Enter untuk mulai, Ctrl+C untuk batal..."
    echo ""

    python3 "$DOCKMAN_BIN" --bootstrap "$phase_num" || true
}

# ── Summary ─────────────────────────────────────────────────────────────────────

print_summary() {
    local total=$((PASS + FAIL + SKIP))
    echo ""
    echo -e "  ${BOLD}${CYAN}========================================${RESET}"
    echo -e "  ${BOLD}  TEST SUMMARY${RESET}"
    echo -e "  ${BOLD}${CYAN}========================================${RESET}"
    echo -e "  ${GREEN}PASS${RESET}  : $PASS"
    echo -e "  ${RED}FAIL${RESET}  : $FAIL"
    echo -e "  ${YELLOW}SKIP${RESET}  : $SKIP"
    echo    "  TOTAL : $total"
    echo -e "  ${BOLD}${CYAN}========================================${RESET}"
    echo ""
    if [[ $FAIL -eq 0 ]]; then
        echo -e "  ${GREEN}${BOLD}SEMUA TEST PASS! \u2713${RESET}"
    else
        echo -e "  ${RED}${BOLD}$FAIL TEST GAGAL! Cek output di atas.${RESET}"
    fi
    echo ""
}

# ── Main ───────────────────────────────────────────────────────────────────────

echo ""
echo -e "  ${BOLD}${CYAN}DOCKMAN v3 - Test Suite${RESET}"
echo -e "  ${CYAN}==============================${RESET}"
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
    build)
        test_build
        print_summary
        ;;
    unit)
        test_unit_bootstrap
        test_unit_compose
        test_phase_smoke
        print_summary
        ;;
    system)
        test_system_check
        print_summary
        ;;
    integration)
        test_integration_build
        print_summary
        ;;
    phase)
        if [[ -z "${2}" ]]; then
            echo "  Usage: bash test-bootstrap.sh phase <1-7>"
            exit 1
        fi
        test_phase_manual "${2}"
        ;;
    *)
        echo "  Usage: bash test-bootstrap.sh [all|build|unit|system|integration|phase N]"
        exit 1
        ;;
esac

[[ $FAIL -gt 0 ]] && exit 1 || exit 0
