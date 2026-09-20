#!/bin/sh
set -eu

REF="${AGY_PLUGIN_MANAGER_REF:-main}"
SOURCE_URL="${AGY_PLUGIN_MANAGER_SOURCE_URL:-https://github.com/Leopoldius/agy-plugin-manager/archive/refs/heads/${REF}.zip}"
DATA_HOME="${XDG_DATA_HOME:-$HOME/.local/share}"
BIN_HOME="${XDG_BIN_HOME:-$HOME/.local/bin}"
INSTALL_ROOT="$DATA_HOME/agy-plugin-manager"
VENV_DIR="$INSTALL_ROOT/venv"
LAUNCHER="$BIN_HOME/agy-plugins"

find_python() {
    if command -v python3 >/dev/null 2>&1; then
        printf '%s\n' "python3"
        return
    fi

    if command -v python >/dev/null 2>&1; then
        printf '%s\n' "python"
        return
    fi

    return 1
}

PYTHON="$(find_python || true)"

if [ -z "$PYTHON" ]; then
    echo "ERROR: Python 3.10 or newer is required." >&2
    exit 1
fi

if ! "$PYTHON" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)'; then
    echo "ERROR: Python 3.10 or newer is required." >&2
    exit 1
fi

mkdir -p "$INSTALL_ROOT" "$BIN_HOME"

if [ ! -x "$VENV_DIR/bin/python" ]; then
    if ! "$PYTHON" -m venv "$VENV_DIR"; then
        cat >&2 <<'EOF'
ERROR: Python venv support is unavailable.

Debian/Ubuntu:
  sudo apt install python3-venv

Fedora:
  sudo dnf install python3

Arch:
  sudo pacman -S python
EOF
        exit 1
    fi
fi

"$VENV_DIR/bin/python" -m pip install     --disable-pip-version-check     --upgrade     --force-reinstall     "$SOURCE_URL"

cat > "$LAUNCHER" <<EOF
#!/bin/sh
exec "$VENV_DIR/bin/agy-plugins" "\$@"
EOF

chmod 0755 "$LAUNCHER"

echo
echo "Installed agy-plugin-manager."
echo "Launcher: $LAUNCHER"

case ":$PATH:" in
    *":$BIN_HOME:"*)
        ;;
    *)
        echo "WARNING: $BIN_HOME is not currently in PATH."
        echo "Add it to your shell PATH, then open a new shell."
        ;;
esac

echo
"$VENV_DIR/bin/agy-plugins" self-info
