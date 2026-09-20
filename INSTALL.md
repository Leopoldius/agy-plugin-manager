# Installation

[Back to project home](README.md)

This document contains installation, validation, and removal instructions for `agy-plugin-manager`.

## Current release status

Current development version: `0.6`.

Version `0.6` is currently being validated on the `develop` branch before promotion to `main`.

Until `0.6` is merged to `main`:

- use `develop` when testing the new installers and package layout;
- commands that explicitly reference `main` install the currently released main-branch version instead.

## Requirements

- Python 3.10 or newer
- No third-party runtime Python packages

Windows and Linux are supported by the package and installer layout.

Current runtime validation status:

- Windows 10: tested with Python 3.12.4
- standalone Windows installer: tested
- pipx on Windows: tested with pipx 1.17.4
- uv tool: packaging support is present, runtime validation is still pending
- Linux standalone installer: present, runtime validation is still pending
- Linux pipx/uv tool installation: packaging support is present, runtime validation is still pending

## Installed command

All installed forms expose the same command:

```text
agy-plugins
```

Verify an installation with:

```text
agy-plugins --version
agy-plugins self-info
```

A successful `self-info` command reports the version, installation type, executable, package path, short-description database, default INI, Python version, and platform.

## Standalone installer

The standalone installer creates an isolated virtual environment and exposes the `agy-plugins` command without modifying the system Python environment.

### Windows PowerShell

For the currently released `main` branch:

```powershell
Invoke-WebRequest https://raw.githubusercontent.com/Leopoldius/agy-plugin-manager/main/install.ps1 -OutFile $env:TEMP\agy-plugin-manager-install.ps1
& $env:TEMP\agy-plugin-manager-install.ps1
```

While version `0.6` is still on `develop`, test it from a source checkout with:

```powershell
.\install.ps1 -Ref develop
```

Default locations:

```text
%LOCALAPPDATA%\agy-plugin-manager\venv\
%LOCALAPPDATA%\agy-plugin-manager\bin\agy-plugins.cmd
```

The installer:

- finds Python 3;
- requires Python 3.10 or newer;
- creates an isolated virtual environment;
- builds and installs the Python package from the selected branch;
- creates `agy-plugins.cmd`;
- adds the standalone `bin` directory to the user PATH when needed;
- updates PATH for the current PowerShell process;
- runs `agy-plugins self-info` after installation.

Remove the standalone installation from a source checkout:

```powershell
.\uninstall.ps1
```

The uninstaller removes the standalone installation directory and removes its `bin` directory from the user PATH.

### Linux

For the currently released `main` branch:

```bash
curl -fsSL https://raw.githubusercontent.com/Leopoldius/agy-plugin-manager/main/install.sh -o /tmp/agy-plugin-manager-install.sh
sh /tmp/agy-plugin-manager-install.sh
```

While version `0.6` is still on `develop`, test it from a source checkout with:

```bash
AGY_PLUGIN_MANAGER_REF=develop ./install.sh
```

Default locations:

```text
~/.local/share/agy-plugin-manager/venv/
~/.local/bin/agy-plugins
```

The installer uses the standard user-local `~/.local/bin` location and warns when that directory is not already in PATH.

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

Linux runtime validation for version `0.6` is still pending.

## pipx

`pipx` installs the project into an isolated Python environment and exposes `agy-plugins` as a normal command.

### Install pipx

If `pipx` is already available:

```text
pipx --version
```

On Windows, if `pipx` is not installed:

```powershell
py -3 -m pip install --user pipx
```

If the `pipx.exe` directory is not yet in PATH, the module form can still be used:

```powershell
py -3 -m pipx --version
```

Configure the normal pipx application paths:

```powershell
py -3 -m pipx ensurepath
```

Open a new terminal if required for PATH changes to become visible to new command lookups.

### Install agy-plugin-manager with pipx

For the currently released `main` branch:

```text
pipx install https://github.com/Leopoldius/agy-plugin-manager/archive/refs/heads/main.zip
```

For version `0.6` testing from a local `develop` checkout:

```text
pipx install . --force
```

On Windows, the module form is equivalent when `pipx.exe` is not yet directly available:

```powershell
py -3 -m pipx install . --force
```

The default pipx application directory observed during Windows validation was:

```text
%USERPROFILE%\.local\bin
```

The actual pipx virtual environment location is implementation-specific. Use:

```text
agy-plugins self-info
```

to see the active package path.

Remove the package:

```text
pipx uninstall agy-plugin-manager
```

Or on Windows through the Python module form:

```powershell
py -3 -m pipx uninstall agy-plugin-manager
```

## uv tool

`uv tool` can install the same Python package into an isolated environment.

For the currently released `main` branch:

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

The package layout is prepared for `uv tool`, but this path has not yet been runtime-tested for version `0.6`.

## Source checkout

Installation is optional for development.

From the repository root, the compatibility launcher can still be used directly.

Windows:

```powershell
python .\agy-plugins.py --version
python .\agy-plugins.py self-info
python .\agy-plugins.py status
```

Linux:

```bash
python3 ./agy-plugins.py --version
python3 ./agy-plugins.py self-info
python3 ./agy-plugins.py status
```

The source launcher imports the same package implementation from:

```text
src/agy_plugin_manager/
```

In a source checkout, `self-info` should report:

```text
Installation : source-checkout
```

## Installation diagnostics

Use:

```text
agy-plugins self-info
```

Typical installation types include:

```text
source-checkout
standalone
pipx
uv-tool
python-environment
```

Examples verified on Windows 10 for version `0.6`:

Standalone:

```text
Installation : standalone
```

pipx:

```text
Installation : pipx
```

## Short-description database

A source checkout prefers the canonical repository database:

```text
docs/plugins/
```

Installed packages contain a packaged copy:

```text
agy_plugin_manager/data/plugins/
```

This allows:

```text
agy-plugins describe science pubmed-database short
```

to work without a repository checkout.

During version `0.6` validation, the source database and packaged database contained the same 133 files with matching Git blob content.

## Full skill descriptions

The `full` mode does not read the packaged summary database.

It resolves the locally installed Antigravity/Gemini plugin directory and reads the original installed `SKILL.md`:

```text
agy-plugins describe science pubmed-database full
```

This behavior was verified from both standalone and pipx installations on Windows.

## Default profile data

Installed packages include the default `agy-plugins.ini`.

A source checkout prefers the repository-level:

```text
agy-plugins.ini
```

An installed package falls back to:

```text
agy_plugin_manager/data/agy-plugins.ini
```

The packaged profiles verified during Windows testing are:

```text
clean
coding
full
```

## Windows 0.6 validation matrix

The following flows have been tested successfully on Windows 10 build 19045 with Python 3.12.4:

- source checkout `--version`;
- source checkout `self-info`;
- source checkout `describe ... short`;
- source checkout `describe ... full`;
- standalone `install.ps1 -Ref develop`;
- wheel build during standalone installation;
- standalone command execution through PATH;
- standalone packaged `describe ... short`;
- standalone installed-plugin `describe ... full`;
- standalone packaged profiles;
- standalone `uninstall.ps1`;
- confirmation that the standalone command disappears after uninstall;
- pipx 1.17.4 installation from the local checkout;
- pipx `self-info`;
- pipx packaged `describe ... short`;
- pipx installed-plugin `describe ... full`;
- pipx packaged profiles;
- pipx uninstall.

Not yet runtime-tested for version `0.6`:

- `uv tool` installation;
- Linux standalone installation;
- Linux pipx installation;
- Linux uv tool installation.
