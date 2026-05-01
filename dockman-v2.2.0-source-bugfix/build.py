#!/usr/bin/env python3
"""
build.py - Compile semua source file menjadi satu dockman.py
Dijalankan sebelum install: python3 build.py
Output: dist/dockman.py (single file, siap install)
"""

import os
import re
import sys
from pathlib import Path
from datetime import datetime

# Urutan file yang akan digabung (urutan penting untuk dependency)
SOURCE_FILES = [
    "core/config.py",
    "core/utils.py",
    "core/docker.py",
    "core/serverdocs.py",
    "ui/rich_ui.py",
    "ui/wizard.py",
    "ui/curses_ui.py",
    "ui/cli_menu.py",
    "main.py",
]

# Import yang akan distrip dari setiap file (karena sudah inline)
INTERNAL_IMPORTS = {
    "import core.config as config",
    "import core.docker as docker",
    "from core.config import",
    "from core.utils import",
    "from core.docker import",
    "from core.serverdocs import",
    "import ui.rich_ui as rich_ui",
    "from ui.wizard import",
    "from ui.curses_ui import",
    "from ui.cli_menu import",
    "import core.config",
    "import core.utils",
    "import core.docker",
}

HEADER = '''#!/usr/bin/env python3
"""
dockman - Docker Manager TUI (compiled single-file)
Version : {version}
Built   : {date}
License : MIT
Repo    : https://github.com/USERNAME/dockman

File ini di-generate otomatis oleh build.py.
Jangan edit langsung - edit source di folder dockman/ lalu build ulang.
"""
'''

STDLIB_IMPORTS_SEEN = set()


def should_skip_line(line: str, filename: str) -> bool:
    """Apakah baris ini harus di-skip saat digabung."""
    stripped = line.strip()

    # Skip shebang (selain file pertama)
    if stripped.startswith("#!/"):
        return True

    # Skip docstring file-level (baris """...""" di awal file)
    # (handled separately)

    # Skip internal imports
    for imp in INTERNAL_IMPORTS:
        if stripped.startswith(imp):
            return True

    # Skip __init__.py
    if filename.endswith("__init__.py"):
        return True

    return False


def extract_stdlib_imports(content: str) -> tuple:
    """
    Pisahkan top-level stdlib/third-party imports dari body code.
    Handle multiline imports (parentheses).
    Hanya ambil import yang tidak di-indent (top-level).
    Return (imports_list, body_lines)
    """
    imports = []
    body    = []

    lines = content.splitlines()
    i = 0

    # Skip file-level docstring
    if lines and lines[0].strip().startswith('"""'):
        if lines[0].strip().endswith('"""') and len(lines[0].strip()) > 6:
            i = 1
        else:
            i = 1
            while i < len(lines):
                if '"""' in lines[i]:
                    i += 1
                    break
                i += 1

    while i < len(lines):
        line     = lines[i]
        stripped = line.strip()

        # Hanya proses top-level (tidak di-indent)
        is_top_level = len(line) == 0 or not line[0].isspace()

        if is_top_level:
            # Skip internal imports
            is_internal = any(stripped.startswith(x) for x in INTERNAL_IMPORTS)
            if is_internal:
                i += 1
                continue

            # Collect top-level import statements (termasuk multiline)
            is_import = (stripped.startswith("import ") or
                         (stripped.startswith("from ") and "import" in stripped))

            if is_import:
                import_lines = [line]
                full = stripped
                # Handle multiline import dengan parentheses
                while "(" in full and ")" not in full:
                    i += 1
                    if i >= len(lines):
                        break
                    import_lines.append(lines[i])
                    full += lines[i].strip()
                imports.append("\n".join(import_lines))
                i += 1
                continue

        body.append(line)
        i += 1

    return imports, body


def build(version: str = None, output: str = None):
    src_dir = Path(__file__).parent
    dist_dir = src_dir / "dist"
    dist_dir.mkdir(exist_ok=True)

    out_path = Path(output) if output else dist_dir / "dockman.py"

    # Baca versi dari config.py
    if not version:
        config_content = (src_dir / "core/config.py").read_text()
        m = re.search(r'VERSION\s*=\s*["\']([^"\']+)["\']', config_content)
        version = m.group(1) if m else "2.0.0"

    print(f"Building dockman v{version}...")

    all_imports_seen = set()
    all_imports_list = []
    all_bodies  = []

    for rel_path in SOURCE_FILES:
        filepath = src_dir / rel_path
        if not filepath.exists():
            print(f"  WARN: {rel_path} tidak ditemukan, skip.")
            continue

        content = filepath.read_text(encoding="utf-8")
        imports, body = extract_stdlib_imports(content)

        for imp in imports:
            key = imp.strip().splitlines()[0]  # gunakan baris pertama sebagai key dedup
            if key not in all_imports_seen:
                all_imports_seen.add(key)
                all_imports_list.append(imp)

        section_name = rel_path.replace("/", ".").replace(".py", "")
        all_bodies.append(f"\n# {'='*70}")
        all_bodies.append(f"# SOURCE: {rel_path}")
        all_bodies.append(f"# {'='*70}")
        all_bodies.extend(body)

        print(f"  OK: {rel_path} ({len(body)} baris)")

    # Susun output
    header = HEADER.format(
        version=version,
        date=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    )

    # Kelompokkan imports
    stdlib_core  = [i for i in all_imports_list if "rich" not in i]
    rich_imports = [i for i in all_imports_list if "rich" in i]

    import_block = "\n".join(stdlib_core)
    if rich_imports:
        import_block += "\n\n# Rich imports (dengan graceful fallback di rich_ui)\n"
        import_block += "\n".join(rich_imports)

    # Patch sys.path.insert di main.py (tidak diperlukan di single file)
    body_text = "\n".join(all_bodies)
    body_text = body_text.replace(
        "sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))",
        "# sys.path.insert - tidak diperlukan di single-file build"
    )

    # Patch inline lazy imports di dalam fungsi (baris yang diawali spasi + from/import internal)
    INLINE_INTERNAL = [
        "from ui.wizard import",
        "from ui.curses_ui import",
        "from ui.cli_menu import",
        "from ui.rich_ui import",
        "import core.docker as",
        "import core.config as",
        "from core.config import",
        "from core.utils import",
        "from core.docker import",
        "from core.serverdocs import",
    ]
    patched_lines = []
    for line in body_text.splitlines():
        stripped = line.strip()
        is_inline_internal = any(stripped.startswith(p) for p in INLINE_INTERNAL)
        if is_inline_internal:
            # Ganti dengan komentar, jaga panjang baris agar tidak geser indentasi
            indent = len(line) - len(line.lstrip())
            patched_lines.append(" " * indent + f"# (inline import stripped by build.py: {stripped})")
        else:
            patched_lines.append(line)
    body_text = "\n".join(patched_lines)

    # ── Module stubs ──────────────────────────────────────────────────────────
    # Di multi-file pakai: import core.config as config -> config.load()
    # Di single-file semua fungsi sudah inline, buat namespace object sebagai alias
    MODULE_STUBS = '''
# ========================================================================
# MODULE STUBS - di-generate otomatis oleh build.py
# Memetakan module references ke fungsi inline di single-file build
# ========================================================================
import types as _types

# Stub: import core.config as config
config = _types.SimpleNamespace(
    load=load, save=save, get=get, set_value=set_value,
    get_hostname=get_hostname, get_editor=get_editor,
    get_compose_file=get_compose_file, get_compose_dir=get_compose_dir,
    get_compose_cmd=get_compose_cmd, get_doc_output_dir=get_doc_output_dir,
    get_current_user=get_current_user, detect_compose_cmd=detect_compose_cmd,
    find_compose_files=find_compose_files, is_first_run=is_first_run,
    VERSION=VERSION, APP_NAME=APP_NAME,
    CONFIG_DIR=CONFIG_DIR, CONFIG_FILE=CONFIG_FILE,
)

# Stub: import core.docker as docker
docker = _types.SimpleNamespace(
    get_containers=get_containers, get_container_logs=get_container_logs,
    get_container_inspect=get_container_inspect, container_action=container_action,
    pull_image=pull_image, get_container_image=get_container_image,
    get_images=get_images, get_dangling_images=get_dangling_images,
    remove_image=remove_image, get_orphan_volumes=get_orphan_volumes,
    get_disk_usage=get_disk_usage, get_stats_once=get_stats_once,
    compose_action=compose_action, compose_validate=compose_validate,
    get_screens=get_screens, screen_kill=screen_kill,
)

# Stub: import ui.rich_ui as rich_ui
rich_ui = _types.SimpleNamespace(
    show_containers=show_containers, show_images=show_images,
    show_stats=show_stats, show_disk_usage=show_disk_usage,
    show_logs=show_logs, stream_logs=stream_logs,
    show_inspect=show_inspect, show_compose_file=show_compose_file,
    show_screen_sessions=show_screen_sessions,
    generate_server_docs_with_progress=generate_server_docs_with_progress,
    cli_header=cli_header, cli_error=cli_error,
    cli_success=cli_success, cli_info=cli_info,
    confirm_cli=confirm_cli, wait_key=wait_key,
    RICH_AVAILABLE=RICH_AVAILABLE,
)

# Stub: from ui.tui import run_tui (fungsi sudah inline)
# run_tui didefinisikan di main.py, dipanggil dari curses_ui
'''

    # Inject stubs SEBELUM SOURCE: main.py agar config/docker/rich_ui
    # sudah terdefinisi saat main() dipanggil
    MAIN_MARKER = "\n# " + "=" * 70 + "\n# SOURCE: main.py"
    if MAIN_MARKER in body_text:
        body_text = body_text.replace(MAIN_MARKER, MODULE_STUBS + MAIN_MARKER)
    else:
        # Fallback: inject di awal body
        body_text = MODULE_STUBS + body_text

    final_content = header + "\n" + import_block + "\n" + body_text

    out_path.write_text(final_content, encoding="utf-8")
    out_path.chmod(0o755)

    size = out_path.stat().st_size
    lines = final_content.count("\n")
    print(f"\nOutput: {out_path}")
    print(f"Size  : {size:,} bytes ({lines:,} baris)")
    print(f"\nSiap install:")
    print(f"  sudo cp {out_path} /usr/local/bin/dockman")
    print(f"  sudo chmod +x /usr/local/bin/dockman")

    return str(out_path)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Build dockman single-file")
    parser.add_argument("--version", help="Override versi")
    parser.add_argument("--output",  help="Path output file")
    args = parser.parse_args()
    build(version=args.version, output=args.output)
