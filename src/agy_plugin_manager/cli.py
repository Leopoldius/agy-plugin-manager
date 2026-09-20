#!/usr/bin/env python3
from __future__ import annotations

import argparse
import configparser
import json
import os
import platform
import shutil
import sys
import tempfile
from datetime import datetime
from pathlib import Path

from . import __version__

VERSION = __version__
VALID_STATES = {"on", "off", "keep"}
AUTO_VALUE = "auto"


def script_dir() -> Path:
    return Path(__file__).resolve().parent


def source_root() -> Path | None:
    candidate = script_dir().parent.parent

    if (
        (candidate / "pyproject.toml").is_file()
        and (candidate / "docs" / "plugins").is_dir()
    ):
        return candidate.resolve()

    return None


def user_config_dir() -> Path:
    if os.name == "nt":
        appdata = os.environ.get("APPDATA")
        if appdata:
            return Path(appdata).expanduser().resolve() / "agy-plugin-manager"

    xdg_config = os.environ.get("XDG_CONFIG_HOME")
    if xdg_config:
        return Path(xdg_config).expanduser().resolve() / "agy-plugin-manager"

    return home_dir() / ".config" / "agy-plugin-manager"


def packaged_data_dir() -> Path:
    return script_dir() / "data"


def default_ini_path() -> Path:
    root = source_root()

    if root is not None:
        source_ini = root / "agy-plugins.ini"
        if source_ini.is_file():
            return source_ini

    user_ini = user_config_dir() / "agy-plugins.ini"
    if user_ini.is_file():
        return user_ini

    packaged_ini = packaged_data_dir() / "agy-plugins.ini"
    if packaged_ini.is_file():
        return packaged_ini

    return user_ini


def home_dir() -> Path:
    return Path.home()


def gemini_root() -> Path:
    return home_dir() / ".gemini"


def standard_config_path() -> Path:
    return gemini_root() / "config" / "config.json"


def expand_path(value: str) -> Path:
    return Path(os.path.expandvars(os.path.expanduser(value))).resolve()


def is_auto(value: str | None) -> bool:
    return value is None or value.strip().lower() in {"", AUTO_VALUE}


def load_ini_optional(path: Path) -> configparser.ConfigParser | None:
    if not path.is_file():
        return None

    cfg = configparser.ConfigParser(interpolation=None)
    cfg.optionxform = str
    cfg.read(path, encoding="utf-8")

    if "general" not in cfg:
        raise ValueError("INI exists but [general] section is missing")

    return cfg


def looks_like_antigravity_config(path: Path) -> bool:
    try:
        with path.open("r", encoding="utf-8-sig") as f:
            data = json.load(f)
    except (OSError, UnicodeError, json.JSONDecodeError):
        return False

    if not isinstance(data, dict):
        return False

    plugins = data.get("plugins")
    if not isinstance(plugins, dict) or not plugins:
        return False

    for value in plugins.values():
        if isinstance(value, dict) and isinstance(value.get("enabled"), bool):
            return True

    return False


def discover_config_path() -> tuple[Path, str]:
    standard = standard_config_path()

    if standard.is_file() and looks_like_antigravity_config(standard):
        return standard.resolve(), "auto:standard"

    root = gemini_root()
    if not root.is_dir():
        raise FileNotFoundError(
            f"Could not find Antigravity config. "
            f"Expected standard root: {root}"
        )

    candidates: list[Path] = []

    # Keep discovery bounded so plugin trees and caches are not scanned deeply.
    for path in root.rglob("config.json"):
        try:
            rel = path.relative_to(root)
        except ValueError:
            continue

        if len(rel.parts) > 5:
            continue

        lower_parts = {part.lower() for part in rel.parts}
        if "backups" in lower_parts:
            continue

        if path.is_file() and looks_like_antigravity_config(path):
            candidates.append(path.resolve())

    candidates = sorted(set(candidates), key=lambda p: str(p).lower())

    if len(candidates) == 1:
        return candidates[0], "auto:scan"

    if not candidates:
        raise FileNotFoundError(
            "Could not auto-detect Antigravity config.json. "
            "Use --config PATH or set config=PATH in agy-plugins.ini."
        )

    lines = "\n".join(f"  {path}" for path in candidates)
    raise RuntimeError(
        "Multiple Antigravity-like config files were found. "
        "Refusing to guess. Use --config PATH or set config=PATH in INI:\n"
        + lines
    )


def resolve_config_path(
    cfg: configparser.ConfigParser | None,
    cli_value: str | None,
) -> tuple[Path, str]:
    if not is_auto(cli_value):
        path = expand_path(cli_value)
        return path, "cli"

    if cfg is not None:
        ini_value = cfg["general"].get("config", AUTO_VALUE)
        if not is_auto(ini_value):
            path = expand_path(ini_value)
            return path, "ini"

    return discover_config_path()


def resolve_plugins_dir(
    cfg: configparser.ConfigParser | None,
    cli_value: str | None,
    config_path: Path,
) -> tuple[Path, str]:
    if not is_auto(cli_value):
        return expand_path(cli_value), "cli"

    if cfg is not None:
        ini_value = cfg["general"].get("plugins_dir", AUTO_VALUE)
        if not is_auto(ini_value):
            return expand_path(ini_value), "ini"

    sibling = config_path.parent / "plugins"
    if sibling.is_dir():
        return sibling.resolve(), "auto:sibling"

    standard = gemini_root() / "config" / "plugins"
    if standard.is_dir():
        return standard.resolve(), "auto:standard"

    # Keep a deterministic path even when the directory does not exist.
    return sibling.resolve(), "auto:derived"


def resolve_backup_dir(
    cfg: configparser.ConfigParser | None,
    cli_value: str | None,
    config_path: Path,
) -> tuple[Path, str]:
    if not is_auto(cli_value):
        return expand_path(cli_value), "cli"

    if cfg is not None:
        ini_value = cfg["general"].get("backup_dir", AUTO_VALUE)
        if not is_auto(ini_value):
            return expand_path(ini_value), "ini"

    return (config_path.parent / "backups").resolve(), "auto:derived"


def get_settings(
    cfg: configparser.ConfigParser | None,
    args,
) -> dict:
    config_path, config_source = resolve_config_path(
        cfg,
        args.config,
    )

    plugins_dir, plugins_source = resolve_plugins_dir(
        cfg,
        args.plugins_dir,
        config_path,
    )

    backup_dir, backup_source = resolve_backup_dir(
        cfg,
        args.backup_dir,
        config_path,
    )

    if cfg is None:
        return {
            "config": config_path,
            "config_source": config_source,
            "plugins_dir": plugins_dir,
            "plugins_source": plugins_source,
            "backup_dir": backup_dir,
            "backup_source": backup_source,
            "default_profile": None,
            "backup": True,
            "verbosity": 1,
            "ini_loaded": False,
        }

    g = cfg["general"]

    verbosity = int(g.get("verbosity", "1"))
    if verbosity not in range(4):
        raise ValueError("general.verbosity must be 0..3")

    return {
        "config": config_path,
        "config_source": config_source,
        "plugins_dir": plugins_dir,
        "plugins_source": plugins_source,
        "backup_dir": backup_dir,
        "backup_source": backup_source,
        "default_profile": g.get("default_profile", "clean").strip(),
        "backup": g.getboolean("backup", fallback=True),
        "verbosity": verbosity,
        "ini_loaded": True,
    }


def list_profiles(cfg: configparser.ConfigParser | None) -> list[str]:
    if cfg is None:
        return []

    prefix = "profile."
    return sorted(
        section[len(prefix):]
        for section in cfg.sections()
        if section.startswith(prefix)
    )


def load_profile(
    cfg: configparser.ConfigParser | None,
    name: str,
) -> dict[str, str]:
    if cfg is None:
        raise ValueError(
            "Profiles require agy-plugins.ini. "
            "Without INI, use status, set, enable, or disable."
        )

    section = f"profile.{name}"
    if section not in cfg:
        available = ", ".join(list_profiles(cfg)) or "<none>"
        raise ValueError(
            f"Profile '{name}' not found. Available: {available}"
        )

    result: dict[str, str] = {}

    for plugin, raw_state in cfg[section].items():
        state = raw_state.strip().lower()
        if state not in VALID_STATES:
            raise ValueError(
                f"Invalid state '{raw_state}' for plugin '{plugin}'. "
                "Expected on, off, or keep."
            )
        result[plugin] = state

    return result


def load_json_config(path: Path) -> dict:
    if not path.is_file():
        raise FileNotFoundError(f"Antigravity config not found: {path}")

    with path.open("r", encoding="utf-8-sig") as f:
        data = json.load(f)

    if not isinstance(data, dict):
        raise ValueError("Antigravity config root must be a JSON object")

    if "plugins" not in data:
        data["plugins"] = {}

    if not isinstance(data["plugins"], dict):
        raise ValueError("'plugins' must be a JSON object")

    return data


def get_current_states(data: dict) -> dict[str, bool]:
    result: dict[str, bool] = {}

    for name, value in data["plugins"].items():
        if isinstance(value, dict) and isinstance(value.get("enabled"), bool):
            result[name] = value["enabled"]

    return result


def state_text(value) -> str:
    if value is True:
        return "ON"
    if value is False:
        return "OFF"
    return "-"


def desired_bool(state: str):
    if state == "on":
        return True
    if state == "off":
        return False
    return None


def build_status_rows(
    current: dict[str, bool],
    desired: dict[str, str] | None,
) -> list[dict]:
    if desired is None:
        return [
            {
                "plugin": name,
                "current": state_text(current[name]),
                "desired": "-",
                "status": "CURRENT",
            }
            for name in sorted(current)
        ]

    rows = []

    for name in sorted(set(current) | set(desired)):
        has_current = name in current
        has_desired = name in desired

        current_value = current.get(name)
        desired_state = desired.get(name)

        if has_current and has_desired:
            if desired_state == "keep":
                status = "KEEP"
            else:
                status = (
                    "OK"
                    if current_value == desired_bool(desired_state)
                    else "DIFF"
                )
        elif has_current:
            status = "UNMANAGED"
        else:
            status = "MISSING"

        rows.append({
            "plugin": name,
            "current": state_text(current_value) if has_current else "-",
            "desired": desired_state.upper() if has_desired else "-",
            "status": status,
        })

    return rows


def print_table(rows: list[dict]) -> None:
    headers = ("Plugin", "Current", "Desired", "Status")
    data = [
        (
            row["plugin"],
            row["current"],
            row["desired"],
            row["status"],
        )
        for row in rows
    ]

    widths = [len(x) for x in headers]

    for row in data:
        for index, value in enumerate(row):
            widths[index] = max(widths[index], len(value))

    fmt = "  ".join(f"{{:<{width}}}" for width in widths)

    print(fmt.format(*headers))
    print(fmt.format(*("-" * width for width in widths)))

    for row in data:
        print(fmt.format(*row))


def nested_kind(rel: Path) -> str | None:
    name = rel.name.lower()
    lower_parts = [part.lower() for part in rel.parts]

    if name == "skill.md":
        return "SKILL"

    if name in {"instructions.md", "instruction.md"}:
        return "INSTR"

    if (
        "mcp" in lower_parts
        or name.startswith("mcp")
        or "mcp" in name
    ) and rel.suffix.lower() in {".json", ".yaml", ".yml", ".md"}:
        return "MCP"

    return None


def nested_entries(
    plugin_dir: Path,
    verbosity: int,
) -> list[tuple[str, str]]:
    if not plugin_dir.is_dir():
        return []

    result = []

    for path in sorted(
        plugin_dir.rglob("*"),
        key=lambda item: str(item).lower(),
    ):
        if not path.is_file():
            continue

        rel = path.relative_to(plugin_dir)
        kind = nested_kind(rel)

        if kind is not None:
            result.append((kind, str(rel)))
        elif verbosity >= 3:
            result.append(("FILE", str(rel)))

    return result


def print_nested(
    plugins_dir: Path,
    rows: list[dict],
    verbosity: int,
) -> None:
    if verbosity < 2:
        return

    print()
    print("Nested plugin contents:")

    found_any = False

    for row in rows:
        root = plugins_dir / row["plugin"]

        if not root.is_dir():
            continue

        found_any = True

        print()
        print(
            f'{row["plugin"]} '
            f'[{row["current"]} -> {row["desired"]}, {row["status"]}]'
        )

        entries = nested_entries(root, verbosity)

        if not entries:
            print("  <no recognized nested capabilities>")
            continue

        for kind, rel in entries:
            print(
                f'  {kind:<7} {row["current"]:<3}  {rel}'
            )

    if not found_any:
        print("  <no plugin directories found>")



def canonical_name(value: str) -> str:
    return value.strip().lower().replace("_", "-")


def find_named_directory(root: Path, requested: str, label: str) -> Path:
    if not root.is_dir():
        raise FileNotFoundError(f"{label} directory not found: {root}")

    exact = root / requested
    if exact.is_dir():
        return exact

    wanted = canonical_name(requested)
    matches = sorted(
        (
            path
            for path in root.iterdir()
            if path.is_dir() and canonical_name(path.name) == wanted
        ),
        key=lambda path: path.name.lower(),
    )

    if len(matches) == 1:
        return matches[0]

    if len(matches) > 1:
        choices = ", ".join(path.name for path in matches)
        raise ValueError(
            f"Ambiguous {label.lower()} '{requested}'. Matches: {choices}"
        )

    available = ", ".join(
        sorted(path.name for path in root.iterdir() if path.is_dir())
    ) or "<none>"
    raise FileNotFoundError(
        f"{label} '{requested}' not found under {root}. "
        f"Available: {available}"
    )


def extract_markdown_summary(path: Path) -> str:
    try:
        text = path.read_text(encoding="utf-8-sig")
    except OSError as exc:
        raise OSError(f"Could not read short description: {path}") from exc

    lines = text.splitlines()
    start = None

    for index, line in enumerate(lines):
        if line.strip().lower() == "## summary":
            start = index + 1
            break

    if start is None:
        raise ValueError(
            f"Short description has no '## Summary' section: {path}"
        )

    collected = []

    for line in lines[start:]:
        if line.startswith("## "):
            break
        collected.append(line)

    summary = "\n".join(collected).strip()

    if not summary:
        raise ValueError(f"Short description is empty: {path}")

    return summary


def short_database_root() -> tuple[Path, str]:
    checked = []
    root = source_root()

    if root is not None:
        source_docs = root / "docs" / "plugins"
        checked.append(source_docs)

        if source_docs.is_dir():
            return source_docs.resolve(), "source"

    packaged_docs = packaged_data_dir() / "plugins"
    checked.append(packaged_docs)

    if packaged_docs.is_dir():
        return packaged_docs.resolve(), "package"

    locations = ", ".join(str(path) for path in checked)

    raise FileNotFoundError(
        "Short description database not found. "
        f"Checked: {locations}. Nothing to read for mode 'short'."
    )


def find_short_description(plugin_name: str, skill_name: str) -> Path:
    docs_root, _ = short_database_root()

    plugin_root = find_named_directory(
        docs_root,
        plugin_name,
        "Plugin documentation",
    )

    wanted = canonical_name(skill_name)
    matches = []

    for path in sorted(
        plugin_root.glob("desc_*.md"),
        key=lambda item: item.name.lower(),
    ):
        logical_name = path.stem[len("desc_"):]
        if canonical_name(logical_name) == wanted:
            matches.append(path)

    if len(matches) == 1:
        return matches[0]

    if len(matches) > 1:
        choices = ", ".join(path.name for path in matches)
        raise ValueError(
            f"Ambiguous short description for '{skill_name}': {choices}"
        )

    available = ", ".join(
        path.stem[len("desc_"):]
        for path in sorted(
            plugin_root.glob("desc_*.md"),
            key=lambda item: item.name.lower(),
        )
    ) or "<none>"

    raise FileNotFoundError(
        f"Short description for skill '{skill_name}' was not found in "
        f"{plugin_root}. Available: {available}"
    )


def resolve_plugins_dir_for_describe(
    cfg: configparser.ConfigParser | None,
    cli_value: str | None,
) -> tuple[Path, str]:
    if not is_auto(cli_value):
        return expand_path(cli_value), "cli"

    if cfg is not None:
        ini_value = cfg["general"].get("plugins_dir", AUTO_VALUE)
        if not is_auto(ini_value):
            return expand_path(ini_value), "ini"

    standard = gemini_root() / "config" / "plugins"

    if standard.is_dir():
        return standard.resolve(), "auto:standard"

    try:
        config_path, _ = discover_config_path()
    except (FileNotFoundError, RuntimeError):
        return standard.resolve(), "auto:derived"

    return resolve_plugins_dir(cfg, AUTO_VALUE, config_path)


def find_full_skill_file(
    plugins_dir: Path,
    plugin_name: str,
    skill_name: str,
) -> Path:
    plugin_root = find_named_directory(
        plugins_dir,
        plugin_name,
        "Installed plugin",
    )

    skill_files = sorted(
        (
            path
            for path in plugin_root.rglob("SKILL.md")
            if path.is_file()
        ),
        key=lambda path: str(path).lower(),
    )

    if not skill_files:
        raise FileNotFoundError(
            f"No SKILL.md files found under installed plugin: {plugin_root}"
        )

    wanted = canonical_name(skill_name)
    matches = []

    for path in skill_files:
        parent = path.parent

        if canonical_name(parent.name) == wanted:
            matches.append(path)

    if len(matches) == 1:
        return matches[0]

    if len(matches) > 1:
        choices = ", ".join(
            str(path.relative_to(plugin_root))
            for path in matches
        )
        raise ValueError(
            f"Ambiguous installed skill '{skill_name}'. Matches: {choices}"
        )

    if len(skill_files) == 1:
        return skill_files[0]

    available = ", ".join(
        sorted(
            {
                path.parent.name
                for path in skill_files
                if path.parent != plugin_root
            }
        )
    ) or "<root-level skills>"

    raise FileNotFoundError(
        f"Installed skill '{skill_name}' was not found under {plugin_root}. "
        f"Available skill directories: {available}"
    )


def command_describe(
    cfg: configparser.ConfigParser | None,
    args,
) -> int:
    if args.mode == "short":
        source = find_short_description(args.plugin, args.skill)
        content = extract_markdown_summary(source)
    else:
        plugins_dir, plugins_source = resolve_plugins_dir_for_describe(
            cfg,
            args.plugins_dir,
        )
        source = find_full_skill_file(
            plugins_dir,
            args.plugin,
            args.skill,
        )

        try:
            content = source.read_text(encoding="utf-8-sig").strip()
        except OSError as exc:
            raise OSError(f"Could not read installed skill: {source}") from exc

        print(f"Plugins dir : {plugins_dir} [{plugins_source}]")

    print(f"Plugin      : {args.plugin}")
    print(f"Skill       : {args.skill}")
    print(f"Mode        : {args.mode}")
    print(f"Source      : {source}")
    print()
    print(content)

    return 0

def detect_installation() -> str:
    normalized = str(script_dir()).replace("\\", "/").lower()

    if source_root() is not None:
        return "source-checkout"

    if "/agy-plugin-manager/venv/" in normalized:
        return "standalone"

    if "/pipx/venvs/" in normalized:
        return "pipx"

    if "/uv/tools/" in normalized or "/uv/tool/" in normalized:
        return "uv-tool"

    return "python-environment"


def command_self_info() -> int:
    try:
        short_root, short_source = short_database_root()
        short_text = f"{short_root} [{short_source}]"
    except FileNotFoundError:
        short_text = "<unavailable>"

    ini_path = default_ini_path()

    print(f"Version      : {VERSION}")
    print(f"Installation : {detect_installation()}")
    print(f"Executable   : {Path(sys.argv[0]).resolve()}")
    print(f"Package      : {script_dir()}")
    print(f"Short DB     : {short_text}")
    print(
        f"Default INI  : {ini_path} "
        f"[{'present' if ini_path.is_file() else 'not found'}]"
    )
    print(f"Python       : {platform.python_version()}")
    print(f"Platform     : {platform.platform()}")

    return 0


def calculate_profile_changes(
    data: dict,
    desired: dict[str, str],
):
    changes = []
    missing = []

    for name, state in sorted(desired.items()):
        if state == "keep":
            continue

        plugin = data["plugins"].get(name)

        if not isinstance(plugin, dict):
            missing.append(name)
            continue

        expected = desired_bool(state)
        current = plugin.get("enabled")

        if current is not expected:
            changes.append((name, current, expected))

    return changes, missing


def make_backup(
    config_path: Path,
    backup_dir: Path,
) -> Path:
    backup_dir.mkdir(parents=True, exist_ok=True)

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = backup_dir / f"config.{stamp}.json"

    suffix = 1
    while backup.exists():
        backup = backup_dir / f"config.{stamp}.{suffix}.json"
        suffix += 1

    shutil.copy2(config_path, backup)
    return backup


def write_atomic(
    config_path: Path,
    data: dict,
    backup_dir: Path,
    create_backup: bool,
) -> Path | None:
    backup = None

    if create_backup:
        backup = make_backup(config_path, backup_dir)

    fd, temp_name = tempfile.mkstemp(
        prefix=config_path.name + ".",
        suffix=".tmp",
        dir=str(config_path.parent),
        text=True,
    )

    try:
        with os.fdopen(
            fd,
            "w",
            encoding="utf-8",
            newline="\n",
        ) as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())

        with open(temp_name, "r", encoding="utf-8") as f:
            json.load(f)

        os.replace(temp_name, config_path)

    except Exception:
        try:
            os.unlink(temp_name)
        except OSError:
            pass
        raise

    return backup


def require_plugin(data: dict, name: str) -> dict:
    plugin = data["plugins"].get(name)

    if not isinstance(plugin, dict):
        available = ", ".join(sorted(data["plugins"].keys()))
        raise ValueError(
            f"Plugin '{name}' not found in config. "
            f"Available: {available}"
        )

    if "enabled" not in plugin or not isinstance(plugin["enabled"], bool):
        raise ValueError(
            f"Plugin '{name}' has no boolean 'enabled' field"
        )

    return plugin


def apply_manual_state(
    settings: dict,
    plugin_name: str,
    enabled: bool,
) -> int:
    data = load_json_config(settings["config"])
    plugin = require_plugin(data, plugin_name)

    old = plugin["enabled"]

    if old == enabled:
        print(
            f"{plugin_name}: already "
            f"{state_text(enabled)}"
        )
        return 0

    plugin["enabled"] = enabled

    backup = write_atomic(
        settings["config"],
        data,
        settings["backup_dir"],
        settings["backup"],
    )

    print(
        f"{plugin_name}: "
        f"{state_text(old)} -> {state_text(enabled)}"
    )

    if backup:
        print(f"Backup : {backup}")

    print(f'Config : {settings["config"]}')
    print("Applied successfully.")

    return 0


def print_resolution(settings: dict) -> None:
    print(
        f'Config      : {settings["config"]} '
        f'[{settings["config_source"]}]'
    )
    print(
        f'Plugins dir : {settings["plugins_dir"]} '
        f'[{settings["plugins_source"]}]'
    )
    print(
        f'Backup dir  : {settings["backup_dir"]} '
        f'[{settings["backup_source"]}]'
    )


def command_status(
    cfg: configparser.ConfigParser | None,
    settings: dict,
    profile_name: str | None,
    verbosity: int,
) -> int:
    data = load_json_config(settings["config"])
    current = get_current_states(data)

    desired = None

    if profile_name is not None:
        desired = load_profile(cfg, profile_name)
    elif cfg is not None and settings["default_profile"]:
        desired = load_profile(
            cfg,
            settings["default_profile"],
        )
        profile_name = settings["default_profile"]

    rows = build_status_rows(current, desired)

    print(f"Version     : {VERSION}")
    print_resolution(settings)
    print(
        "INI         : "
        + ("loaded" if settings["ini_loaded"] else "not found")
    )
    print(
        "Profile     : "
        + (profile_name if profile_name else "<none>")
    )
    print(f"Verbosity   : {verbosity}")
    print()

    if verbosity == 0:
        counts = {}
        for row in rows:
            counts[row["status"]] = counts.get(row["status"], 0) + 1

        print(
            "Status: "
            + " ".join(
                f"{name}={counts.get(name, 0)}"
                for name in (
                    "CURRENT",
                    "OK",
                    "DIFF",
                    "KEEP",
                    "MISSING",
                    "UNMANAGED",
                )
            )
        )
    else:
        print_table(rows)
        print_nested(
            settings["plugins_dir"],
            rows,
            verbosity,
        )

    if desired is not None and any(
        row["status"] in {"DIFF", "MISSING"}
        for row in rows
    ):
        return 2

    return 0


def command_diff(
    cfg: configparser.ConfigParser | None,
    settings: dict,
    profile_name: str,
) -> int:
    desired = load_profile(cfg, profile_name)
    data = load_json_config(settings["config"])
    changes, missing = calculate_profile_changes(
        data,
        desired,
    )

    print_resolution(settings)
    print()
    print(f"Changes for profile '{profile_name}':")
    print()

    if not changes and not missing:
        print("No changes.")
        return 0

    for name, old, new in changes:
        print(
            f"{name}: "
            f"{state_text(old)} -> {state_text(new)}"
        )

    for name in missing:
        print(f"{name}: MISSING")

    print()
    print(
        f"{len(changes)} change(s), "
        f"{len(missing)} missing plugin(s)"
    )

    return 2 if missing else 0


def command_apply(
    cfg: configparser.ConfigParser | None,
    settings: dict,
    profile_name: str,
) -> int:
    desired = load_profile(cfg, profile_name)
    data = load_json_config(settings["config"])

    changes, missing = calculate_profile_changes(
        data,
        desired,
    )

    if missing:
        print(
            "Refusing to apply because managed "
            "plugins are missing:"
        )
        for name in missing:
            print(f"  {name}")
        return 3

    if not changes:
        print(
            f"Profile '{profile_name}' "
            "is already applied."
        )
        return 0

    print_resolution(settings)
    print()
    print(f"Applying profile '{profile_name}':")
    print()

    for name, old, new in changes:
        print(
            f"{name}: "
            f"{state_text(old)} -> {state_text(new)}"
        )
        data["plugins"][name]["enabled"] = new

    backup = write_atomic(
        settings["config"],
        data,
        settings["backup_dir"],
        settings["backup"],
    )

    print()

    if backup:
        print(f"Backup : {backup}")

    print("Applied successfully.")

    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Display and manage Antigravity global Gemini plugins. "
            "INI is optional. Profiles require INI."
        )
    )

    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {VERSION}",
    )

    parser.add_argument(
        "--ini",
        default=str(default_ini_path()),
        help=(
            "INI path. Default: agy-plugins.ini next to script. "
            "If missing, manual status/control remains available."
        ),
    )

    parser.add_argument(
        "--config",
        default=AUTO_VALUE,
        help=(
            "Antigravity config.json path or 'auto'. "
            "CLI value overrides INI."
        ),
    )

    parser.add_argument(
        "--plugins-dir",
        default=AUTO_VALUE,
        help=(
            "Plugin directory path or 'auto'. "
            "CLI value overrides INI."
        ),
    )

    parser.add_argument(
        "--backup-dir",
        default=AUTO_VALUE,
        help=(
            "Backup directory path or 'auto'. "
            "CLI value overrides INI."
        ),
    )

    parser.add_argument(
        "-v",
        "--verbosity",
        type=int,
        choices=(0, 1, 2, 3),
        help=(
            "0=summary, 1=plugins, "
            "2=nested skills/MCP, "
            "3=full plugin file tree."
        ),
    )

    sub = parser.add_subparsers(
        dest="command",
        required=True,
    )

    status = sub.add_parser(
        "status",
        help="Show current plugin status.",
    )
    status.add_argument(
        "profile",
        nargs="?",
        help="Optional profile comparison. Requires INI.",
    )

    sub.add_parser(
        "profiles",
        help="List INI profiles.",
    )

    diff = sub.add_parser(
        "diff",
        help="Show profile changes. Requires INI.",
    )
    diff.add_argument("profile")

    apply_cmd = sub.add_parser(
        "apply",
        help="Apply profile. Requires INI.",
    )
    apply_cmd.add_argument("profile")

    set_cmd = sub.add_parser(
        "set",
        help="Manually set one plugin ON or OFF. INI not required.",
    )
    set_cmd.add_argument("plugin")
    set_cmd.add_argument(
        "state",
        choices=("on", "off"),
    )

    enable = sub.add_parser(
        "enable",
        help="Manually enable one plugin. INI not required.",
    )
    enable.add_argument("plugin")

    disable = sub.add_parser(
        "disable",
        help="Manually disable one plugin. INI not required.",
    )
    disable.add_argument("plugin")

    describe = sub.add_parser(
        "describe",
        help=(
            "Show a short repository summary or the full installed "
            "SKILL.md for one skill."
        ),
    )
    describe.add_argument("plugin")
    describe.add_argument("skill")
    describe.add_argument(
        "mode",
        choices=("short", "full"),
    )

    sub.add_parser(
        "self-info",
        help="Show installation, package, data, Python, and platform details.",
    )

    sub.add_parser(
        "on",
        help="Alias for apply full. Requires INI.",
    )

    sub.add_parser(
        "off",
        help="Alias for apply clean. Requires INI.",
    )

    return parser


def main() -> int:
    args = build_parser().parse_args()

    try:
        if args.command == "self-info":
            return command_self_info()

        ini_path = Path(args.ini).resolve()
        cfg = load_ini_optional(ini_path)

        if args.command == "describe":
            return command_describe(cfg, args)

        settings = get_settings(cfg, args)

        verbosity = (
            settings["verbosity"]
            if args.verbosity is None
            else args.verbosity
        )

        if args.command == "status":
            return command_status(
                cfg,
                settings,
                args.profile,
                verbosity,
            )

        if args.command == "set":
            return apply_manual_state(
                settings,
                args.plugin,
                args.state == "on",
            )

        if args.command == "enable":
            return apply_manual_state(
                settings,
                args.plugin,
                True,
            )

        if args.command == "disable":
            return apply_manual_state(
                settings,
                args.plugin,
                False,
            )

        if cfg is None:
            raise ValueError(
                f"Command '{args.command}' requires "
                f"INI file: {ini_path}. "
                "Without INI use status, set, enable, disable, or describe."
            )

        if args.command == "profiles":
            print("Available profiles:")
            for name in list_profiles(cfg):
                print(f"  {name}")
            return 0

        if args.command == "diff":
            return command_diff(
                cfg,
                settings,
                args.profile,
            )

        if args.command == "apply":
            return command_apply(
                cfg,
                settings,
                args.profile,
            )

        if args.command == "on":
            return command_apply(
                cfg,
                settings,
                "full",
            )

        if args.command == "off":
            return command_apply(
                cfg,
                settings,
                "clean",
            )

        raise ValueError(
            f"Unknown command: {args.command}"
        )

    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())