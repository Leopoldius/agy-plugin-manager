#!/usr/bin/env python3
from __future__ import annotations

import argparse
import configparser
import json
import os
import shutil
import sys
import tempfile
from datetime import datetime
from pathlib import Path

VERSION = "0.4"
VALID_STATES = {"on", "off", "keep"}
AUTO_VALUE = "auto"


def script_dir() -> Path:
    return Path(__file__).resolve().parent


def default_ini_path() -> Path:
    return script_dir() / "agy-plugins.ini"


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
        ini_path = Path(args.ini).resolve()
        cfg = load_ini_optional(ini_path)
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

        if cfg is None:            raise ValueError(
                f"Command '{args.command}' requires "
                f"INI file: {ini_path}. "
                "Without INI use status, set, enable, or disable."
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