# agy-plugin-manager

Unofficial portable CLI for inspecting and managing Antigravity plugins, skills, and plugin profiles.

Current version: `0.5`

## Version history

| Date | Version | Author | Changes |
|---|---:|---|---|
| 2026-09-20 | 0.1 | Leopoldius | Initial Python plugin status and profile manager. |
| 2026-09-20 | 0.2 | Leopoldius | Added verbosity levels and nested skill/MCP inspection. |
| 2026-09-20 | 0.3 | Leopoldius | Added standalone operation without INI and manual `set`, `enable`, and `disable` commands. |
| 2026-09-20 | 0.4 | Leopoldius | Added path auto-discovery, explicit path overrides, version reporting, safe backups, and public research documentation. |
| 2026-09-20 | 0.5 | Leopoldius | Added `describe` with `short` summaries from `docs/plugins` and `full` output from installed `SKILL.md` files. |

Detailed per-version feature notes: [Versions.md](Versions.md)

The project uses simple incremental pre-1.0 versioning. The current version is stored directly in the script:

```python
VERSION = "0.5"
```

## What it does

`agy-plugin-manager` works directly with the Antigravity plugin configuration.

It can:

- auto-detect the local Antigravity configuration;
- show which plugins are currently enabled or disabled;
- inspect nested skills, MCP-related files, and plugin contents;
- enable or disable individual plugins without an INI file;
- compare the current state with named profiles;
- apply reusable plugin profiles from an optional INI file;
- create timestamped backups before changes;
- validate JSON before replacing the active configuration;
- show short local skill summaries from `docs/plugins` or full installed `SKILL.md` content.

The tool does not depend on the location of `agy.exe` and does not invoke the Antigravity CLI.

## Why

Antigravity can inject plugin-provided skills, instructions, and tools into the model context.

With many globally enabled plugins, even a small request can carry a large amount of recurring input context. Keeping only the plugins needed for a workflow can reduce that overhead and keep agent contexts cleaner.

This project exists to make the active plugin state visible and easy to manage.

## Documentation

The repository includes empirical reverse-engineering and usage notes collected while testing Antigravity CLI 1.2.7:

- [Antigravity CLI internals](docs/antigravity_internal.md)
- [Antigravity CLI usage and quota behavior](docs/antigravity_usage.md)
- [Plugin skill summaries](docs/plugins/README.md)

Local usernames, workspace paths, and other user-specific identifiers in the published notes are anonymized.

## Requirements

- Python 3.10 or newer
- No third-party Python packages

Windows is the primary target.

## Quick start

Show the current state:

```powershell
python .\agy-plugins.py status
```

Show nested skills and MCP-related files:

```powershell
python .\agy-plugins.py -v 2 status
```

Show the full recursive plugin file tree:

```powershell
python .\agy-plugins.py -v 3 status
```

Show the script version:

```powershell
python .\agy-plugins.py --version
```

## Skill descriptions

Version 0.5 adds the `describe` command:

```text
describe <plugin> <skill> short|full
```

Use `short` to read the high-level summary from this repository's local description database under `docs/plugins`:

```powershell
python .\agy-plugins.py describe science pubmed-database short
```

Only the `## Summary` section is printed. If the `docs/plugins` database is not present next to the script, the command fails instead of guessing or downloading anything.

Use `full` to read the original installed skill documentation from the locally installed plugin tree:

```powershell
python .\agy-plugins.py describe science pubmed-database full
```

For `full`, the plugin directory is resolved from `--plugins-dir`, the INI setting, or the standard local Antigravity/Gemini plugin location. The command searches the selected installed plugin for `SKILL.md`.

Plugin and skill matching treats `-` and `_` as equivalent. For plugins that contain exactly one `SKILL.md`, that file is used when no directory-name match is available.

The `short` mode does not require an INI file or an installed Antigravity configuration. The `full` mode requires the selected plugin to be installed locally.

## Standalone mode

The INI file is optional.

Without `agy-plugins.ini`, the following commands remain available:

```text
status
set
enable
disable
describe
```

Enable one plugin:

```powershell
python .\agy-plugins.py enable gemini-api
```

Disable one plugin:

```powershell
python .\agy-plugins.py disable science
```

Equivalent explicit form:

```powershell
python .\agy-plugins.py set gemini-api on
python .\agy-plugins.py set science off
```

## Profile mode

If `agy-plugins.ini` is present next to the script, profile management becomes available.

Additional commands:

```text
profiles
diff
apply
on
off
```

List profiles:

```powershell
python .\agy-plugins.py profiles
```

Compare the current state with a profile:

```powershell
python .\agy-plugins.py diff clean
```

Apply a profile:

```powershell
python .\agy-plugins.py apply clean
```

Shortcuts:

```powershell
python .\agy-plugins.py on
python .\agy-plugins.py off
```

`on` is an alias for `apply full`.

`off` is an alias for `apply clean`.

## INI format

Example:

```ini
[general]
config=auto
plugins_dir=auto
backup_dir=auto
default_profile=clean
backup=true
verbosity=1

[profile.clean]
firebase=off
science=off
gemini-api=off

[profile.full]
firebase=on
science=on
gemini-api=on

[profile.coding]
firebase=off
science=off
google-antigravity-sdk=keep
```

Supported profile values:

```text
on
off
keep
```

Meaning:

```text
on    -> set enabled=true
off   -> set enabled=false
keep  -> leave the current state unchanged
```

## Auto-discovery

By default:

```ini
config=auto
plugins_dir=auto
backup_dir=auto
```

The tool first checks the standard location:

```text
~/.gemini/config/config.json
```

On Windows this normally resolves to:

```text
C:\Users\<user>\.gemini\config\config.json
```

If the standard file is not usable, the tool performs a bounded search under:

```text
~/.gemini
```

A candidate must contain a top-level `plugins` object with at least one plugin that has a boolean `enabled` field.

If several candidates match, the tool refuses to guess and asks for an explicit path.

## Explicit path overrides

CLI arguments have priority over INI settings and auto-discovery:

```powershell
python .\agy-plugins.py --config D:\agy\config.json status
```

All paths can be overridden:

```powershell
python .\agy-plugins.py \
  --config D:\agy\config.json \
  --plugins-dir D:\agy\plugins \
  --backup-dir D:\agy\backups \
  status
```

The same paths can be set in `agy-plugins.ini`.

## Verbosity

```text
0  Summary only
1  Top-level plugin table
2  Plugins plus recognized nested skills, MCP files, and instructions
3  Full recursive plugin file tree
```

Examples:

```powershell
python .\agy-plugins.py -v 0 status
python .\agy-plugins.py -v 1 status
python .\agy-plugins.py -v 2 status
python .\agy-plugins.py -v 3 status
```

At verbosity 2, the tool recognizes entries such as:

```text
SKILL.md
instructions.md
instruction.md
MCP-related JSON, YAML, and Markdown files
```

Nested entries inherit the current ON/OFF state of the parent plugin. Individual nested skills are not independently enabled or disabled by this tool.

## Status values

With a profile:

```text
OK          Current state matches the profile
DIFF        Current state differs from the profile
KEEP        Profile intentionally leaves the plugin unchanged
MISSING     Profile references a plugin not present in the config
UNMANAGED   Plugin exists but is not listed in the selected profile
```

Without a profile:

```text
CURRENT
```

is used because there is no desired state to compare against.

## Backups and safe writes

Before a change, the tool creates a timestamped backup by default.

Typical location:

```text
~/.gemini/config/backups/config.YYYYMMDD-HHMMSS.json
```

Write flow:

```text
read current config
-> modify in memory
-> create backup
-> write temporary JSON
-> parse temporary JSON again
-> atomically replace the original config
```

Only the selected plugin `enabled` values are intentionally changed.

Other configuration content is preserved.

## Exit codes

```text
0  Success
1  General error
2  Profile differs from current state, or profile contains missing plugins
3  Profile apply refused because a managed plugin is missing
```

## Disclaimer

This is an independent community project.

It is not affiliated with, endorsed by, or maintained by Google, Google DeepMind, Gemini, or the Antigravity team.

Antigravity configuration formats, plugin layouts, and internal behavior may change between releases.
