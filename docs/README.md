# Documentation

[Back to project home](../README.md)

This directory contains supporting documentation for `agy-plugin-manager`.

## Contents

- [Antigravity CLI internals](antigravity_internal.md) - Empirical notes about observed Antigravity CLI internals, prompt construction, plugin injection, model-facing tools, local data layout, and structured-output behavior.
- [Antigravity CLI usage and quota behavior](antigravity_usage.md) - Empirical notes about usage reporting, quota buckets, model calibration, and quota-aware routing observations.
- [Plugin skill summaries](plugins/README.md) - High-level summaries of locally observed plugin groups and skills.

## Plugin documentation layout

The `plugins/` subtree mirrors the observed plugin grouping and skill naming from the local Gemini configuration layout.

Observed source layout:

```text
~/.gemini/config/plugins/<plugin_name>/
```

Documentation layout:

```text
docs/plugins/<plugin_name>/
```

Typical skill mapping:

```text
~/.gemini/config/plugins/<plugin_name>/skills/<skill_name>/SKILL.md
        ->
docs/plugins/<plugin_name>/desc_<skill_name>.md
```

The published documentation contains independent high-level summaries only. Original plugin prompts, bundled scripts, credentials, private paths, and internal operational instructions are intentionally not reproduced.

## Publication note

Local usernames, workspace paths, and other user-specific identifiers in the published research notes are anonymized.

This project is independent and is not affiliated with or endorsed by Google, Google DeepMind, Gemini, Antigravity, or the plugin publishers.
