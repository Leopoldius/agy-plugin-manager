# Plugin skill summaries

[Back to project home](../../README.md)

This section contains unofficial, high-level summaries of locally observed Antigravity/Gemini plugin skills. It is intended for navigation and capability discovery only.

Original plugin files, detailed prompt text, source code, credentials, private paths, and internal operational instructions are intentionally not reproduced.

## Source layout mapping

The groups documented here correspond to plugin directories observed under the local Gemini configuration tree:

```text
~/.gemini/config/plugins/<plugin_name>/
```

On Windows, the same location is typically:

```text
%USERPROFILE%\.gemini\config\plugins\<plugin_name>\
```

The documentation folders intentionally reuse the same plugin/group names:

```text
docs/plugins/<plugin_name>/
```

Each `desc_<skill_name>.md` page corresponds to a skill discovered in the installed plugin tree, typically from a source layout like:

```text
~/.gemini/config/plugins/<plugin_name>/skills/<skill_name>/SKILL.md
```

So the documentation mirrors the plugin grouping and skill naming, while keeping only independent high-level summaries instead of copying the original plugin files.

## Groups

- [android-cli-plugin](android-cli-plugin/README.md) - Android command-line development support, including project, device, emulator, SDK, and documentation workflows. (1 skill)
- [chrome-devtools-plugin](chrome-devtools-plugin/README.md) - Browser automation, debugging, accessibility, performance, memory, and troubleshooting workflows built around Chrome DevTools. (5 skills)
- [data-agent-kit-plugin](data-agent-kit-plugin/README.md) - Data engineering and analytics workflows for Google Cloud, including BigQuery, Dataflow, Composer, dbt, Dataform, storage, and related tooling. (34 skills)
- [firebase](firebase/README.md) - Firebase development guidance covering setup, authentication, hosting, Firestore, Data Connect, Crashlytics, Remote Config, and security-related workflows. (11 skills)
- [flutter](flutter/README.md) - Dart and Flutter development guidance for testing, analysis, routing, layout, serialization, localization, HTTP, FFI, and related application workflows. (23 skills)
- [gemini-api](gemini-api/README.md) - Application development guidance for Gemini APIs, including standard interactions, live/real-time use cases, and multimodal workflows. (4 skills)
- [google-antigravity-sdk](google-antigravity-sdk/README.md) - High-level guidance for building agent applications with the Google Antigravity Python SDK. (1 skill)
- [google_maps_platform](google_maps_platform/README.md) - High-level development guidance for Google Maps Platform APIs and SDKs. (1 skill)
- [modern-web-guidance-plugin](modern-web-guidance-plugin/README.md) - Web development guidance focused on modern browser practices and Chrome extension development. (2 skills)
- [science](science/README.md) - Scientific research and data-access helpers covering literature, biological databases, molecular and protein analysis, genomics, and related research workflows. (40 skills)
