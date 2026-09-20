# Version history

[Back to project home](README.md)

Detailed release notes for `agy-plugin-manager`.

## 0.5

Date: 2026-09-20

- skill-description-command - Added `describe <plugin> <skill> short|full`.
- short-description-mode - Reads the local high-level summary from `docs/plugins/<plugin>/desc_<skill>.md`.
- short-summary-extraction - Prints only the `## Summary` section from the local description page.
- short-database-validation - Fails with a clear error when the local `docs/plugins` description database is unavailable.
- full-description-mode - Reads the full installed `SKILL.md` from the local Antigravity/Gemini plugin installation.
- installed-plugin-discovery - Resolves the plugin directory from `--plugins-dir`, the INI setting, or the standard local plugin path.
- plugin-name-normalization - Treats `-` and `_` as equivalent when matching plugin and skill names.
- single-skill-fallback - Uses the only available `SKILL.md` in a plugin when no directory-name match exists.
- description-errors - Reports available plugins or skills when a requested description cannot be found.
- standalone-describe - Makes `describe` available without requiring an INI file.
- version-update - Bumped the script and README version to `0.5`.

## 0.4

Date: 2026-09-20

- config-auto-discovery - Added automatic discovery of the Antigravity `config.json`.
- standard-config-path - Checks the standard `~/.gemini/config/config.json` location first.
- fallback-config-scan - Falls back to a bounded search under `~/.gemini` when the standard config is unavailable or invalid.
- config-validation - Accepts only Antigravity-like JSON configs containing plugin entries with boolean `enabled` values.
- ambiguity-protection - Refuses to guess when multiple matching config files are found.
- plugins-dir-auto-discovery - Resolves the plugin directory from the config location or the standard Gemini plugin path.
- backup-dir-auto-discovery - Derives a deterministic backup directory from the active config location.
- explicit-path-overrides - Added `--config`, `--plugins-dir`, and `--backup-dir` overrides.
- path-precedence - Added CLI over INI over auto-discovery precedence.
- version-reporting - Added `--version` and an internal `VERSION` constant.
- safe-backups - Added timestamped config backups before changes.
- atomic-config-write - Writes through a temporary JSON file, validates it, then replaces the active config.
- public-research-docs - Added published Antigravity reverse-engineering and usage documentation.
- plugin-documentation - Added high-level local plugin and skill summaries under `docs/plugins`.

## 0.3

Date: 2026-09-20

- standalone-mode - Made `agy-plugins.ini` optional for basic plugin inspection and control.
- manual-set-command - Added `set <plugin> on|off`.
- manual-enable-command - Added `enable <plugin>`.
- manual-disable-command - Added `disable <plugin>`.
- plugin-existence-validation - Manual changes verify that the requested plugin exists and has a boolean `enabled` field.
- minimal-config-mutation - Manual changes update only the selected plugin's `enabled` value.
- standalone-status - Allows `status` without an INI profile and reports the current state directly.

## 0.2

Date: 2026-09-20

- verbosity-levels - Added `-v/--verbosity` levels from 0 to 3.
- summary-verbosity - Level 0 prints status counters only.
- plugin-table-verbosity - Level 1 prints the top-level plugin table.
- nested-capability-verbosity - Level 2 discovers recognized nested skills, instructions, and MCP-related files.
- full-tree-verbosity - Level 3 prints the complete recursive plugin file tree.
- nested-state-display - Nested entries inherit and display the state of their parent plugin.
- nested-skill-detection - Recognizes `SKILL.md` files.
- instruction-detection - Recognizes `instructions.md` and `instruction.md`.
- mcp-file-detection - Recognizes MCP-related JSON, YAML, YML, and Markdown files.

## 0.1

Date: 2026-09-20

- plugin-status - Added top-level Antigravity plugin state inspection.
- profile-loading - Added named plugin profiles from `agy-plugins.ini`.
- profile-status-comparison - Added comparison of current plugin state against a selected profile.
- profile-diff - Added `diff <profile>` to show required state changes.
- profile-apply - Added `apply <profile>` to apply managed plugin states.
- full-profile-alias - Added `on` as an alias for `apply full`.
- clean-profile-alias - Added `off` as an alias for `apply clean`.
- profile-states - Added `on`, `off`, and `keep` profile values.
- status-values - Added `OK`, `DIFF`, `KEEP`, `MISSING`, and `UNMANAGED` status reporting.
- exit-codes - Added distinct success, profile-difference, and apply-refusal exit codes.
