# Installation

[Back to project home](README.md)

This document contains installation and removal instructions for `agy-plugin-manager`.

## Requirements

- Python 3.10 or newer
- No third-party runtime Python packages

Windows and Linux are supported by the package and installer layout.

Windows installation paths have been runtime-tested with version 0.6.

Linux installers are present for Debian/Ubuntu, Fedora, Arch, and similar distributions, but Linux runtime testing is still pending.

## Installed command

All installation methods expose the same command:

```text
agy-plugins
```

Verify an installation with:

```text
agy-plugins --version
agy-plugins self-info
```

## Standalone installer

The standalone installer creates an isolated virtual environment and exposes the `agy-plugins` command without modifying the system Python environment.

### Windows PowerShell

Install from the released `main` branch:

```powershell
Invoke-WebRequest https://raw.githubusercontent.com/Leopoldius/agy-plugin-manager/main/install.ps1 -OutFile $env:TEMP\agy-plugin-manager-install.ps1
& $env:TEMP\agy-plugin-manager-install.ps1
```

Default locations:

```text
%LOCALAPPDATA%\agy-plugin-manager\venv\
%LOCALAPPDATA%\agy-plugin-manager\bin\agy-plugins.cmd
```

The installer adds the `bin` directory to the user PATH when needed.

To install a non-default branch from a source checkout:

```powershell
.\install.ps1 -Ref develop
```

Remove the standalone installation:

```powershell
.\uninstall.ps1
```

### Linux

Install from the released `main` branch:

```bash
curl -fsSL https://raw.githubusercontent.com/Leopoldius/agy-plugin-manager/main/install.sh -o /tmp/agy-plugin-manager-install.sh
sh /tmp/agy-plugin-manager-install.sh
```

Default locations:

```text
~/.local/share/agy-plugin-manager/venv/
~/.local/bin/agy-plugins
```

The installer uses the standard user-local `~/.local/bin` location and warns when that directory is not in PATH.

To install a non-default branch from a source checkout:

```bash
AGY_PLUGIN_MANAGER_REF=develop ./install.sh
```

Remove the standalone installation:

```bash
./uninstall.sh
```

If Python venv support is missing, install the distribution package that provides it.

Debian/Ubuntu:

```bash
sudo apt install python3-venv
```

Fedora:

```bash
sudo dnf install python3
```

Arch:

```bash
sudo pacman -S python
```

## pipx

`pipx` installs the project into an isolated Python environment and exposes `agy-plugins` as a normal command.

Until a PyPI release is published, install directly from the GitHub archive.

Windows or Linux:

```text
pipx install https://github.com/Leopoldius/agy-plugin-manager/archive/refs/heads/main.zip
```

For development testing from a source checkout:

```text
pipx install . --force
```

If the pipx application directory is not in PATH, run:

```text
pipx ensurepath
```

Then open a new shell if required.

Remove the package:

```text
pipx uninstall agy-plugin-manager
```

## uv tool

`uv tool` can install the same Python package into an isolated environment.

Windows or Linux:

```text
uv tool install https://github.com/Leopoldius/agy-plugin-manager/archive/refs/heads/main.zip
```

For development testing from a source checkout:

```text
uv tool install . --force
```

Remove the package:

```text
uv tool uninstall agy-plugin-manager
```

## Source checkout

Installation is optional for development.

From the repository root, the compatibility launcher can still be used directly.

Windows:

```powershell
python .\agy-plugins.py --version
python .\agy-plugins.py status
```

Linux:

```bash
python3 ./agy-plugins.py --version
python3 ./agy-plugins.py status
```

The source launcher imports the same package implementation from `src/agy_plugin_manager`.

## Installation diagnostics

Use:

```text
agy-plugins self-info
```

The command reports:

- version;
- detected installation type;
- executable path;
- package path;
- short-description database path;
- default INI path;
- Python version;
- platform.

Typical installation types include:

```text
source-checkout
standalone
pipx
uv-tool
python-environment
```

## Short-description database

Installed packages contain their own copy of the short-description database under the Python package data directory.

A source checkout prefers:

```text
docs/plugins/
```

An installed package uses:

```text
agy_plugin_manager/data/plugins/
```

This allows `describe ... short` to work without a repository checkout.

## Default profile data

Installed packages also include the default `agy-plugins.ini`.

A source checkout prefers the repository-level `agy-plugins.ini`.

An installed package falls back to the packaged copy when no user configuration file overrides it.

## Windows 0.6 validation status

The following flows have been tested successfully on Windows 10 with Python 3.12.4:

- source checkout launcher;
- standalone `install.ps1`;
- standalone command execution through PATH;
- packaged `describe ... short`;
- installed-plugin `describe ... full`;
- packaged profiles;
- standalone `uninstall.ps1`;
- pipx installation;
- pipx packaged data and profiles;
- pipx uninstall.

Linux runtime validation is deferred.
