#!/bin/sh
set -eu

DATA_HOME="${XDG_DATA_HOME:-$HOME/.local/share}"
BIN_HOME="${XDG_BIN_HOME:-$HOME/.local/bin}"
INSTALL_ROOT="$DATA_HOME/agy-plugin-manager"
LAUNCHER="$BIN_HOME/agy-plugins"

if [ -e "$LAUNCHER" ]; then
    rm -f "$LAUNCHER"
fi

if [ -d "$INSTALL_ROOT" ]; then
    rm -rf "$INSTALL_ROOT"
fi

echo "Removed agy-plugin-manager standalone installation."
