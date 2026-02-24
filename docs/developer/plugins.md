# Plugins

This page documents the current Agent Zero plugin system, including manifest format, discovery rules, scoped configuration, and activation behavior.

## Overview

Plugins extend Agent Zero through convention-based folders. A plugin can provide:

- Backend: API handlers, tools, helpers, Python lifecycle extensions
- Frontend: WebUI components and extension-point injections
- Agent profiles: plugin-scoped subagent definitions
- Settings: scoped plugin configuration loaded through the plugin settings store
- Activation control: global and per-scope ON/OFF rules

Primary roots (priority order):

1. `usr/plugins/` (user/custom plugins)
2. `plugins/` (core/built-in plugins)

On name collisions, user plugins take precedence.

## Manifest (`plugin.yaml`)

Every plugin must contain `plugin.yaml`:

```yaml
title: My Plugin
description: What this plugin does.
version: 1.0.0
settings_sections:
  - agent
per_project_config: false
per_agent_config: false
always_enabled: false
```

Field reference:

- `name`: UI display name
- `description`: short plugin summary
- `version`: plugin version string
- `settings_sections`: where plugin settings appear (`agent`, `external`, `mcp`, `developer`, `backup`)
- `per_project_config`: enables project-scoped settings/toggles
- `per_agent_config`: enables agent-profile-scoped settings/toggles
- `always_enabled`: forces ON state and disables toggle controls

## Recommended Structure

```text
usr/plugins/<plugin_name>/
├── plugin.yaml
├── default_config.yaml              # optional defaults
├── api/                             # ApiHandler implementations
├── tools/                           # Tool implementations
├── helpers/                         # shared Python logic
├── prompts/
├── agents/
│   └── <profile>/agent.yaml         # optional plugin-distributed agent profile
├── extensions/
│   ├── python/<extension_point>/
│   └── webui/<extension_point>/
└── webui/
    ├── config.html                  # optional settings UI
    └── ...
```

## Settings Resolution

Plugin settings are resolved by scope. Higher priority overrides lower priority:

1. `project/.a0proj/agents/<profile>/plugins/<name>/config.json`
2. `project/.a0proj/plugins/<name>/config.json`
3. `usr/agents/<profile>/plugins/<name>/config.json`
4. `usr/plugins/<name>/config.json`
5. `plugins/<name>/default_config.yaml` (fallback defaults)

Notes:

- Runtime reads support JSON and YAML fallback files.
- Save path is scope-specific and persisted through plugin settings APIs.

## Activation Model

Activation is independent per scope and file-based:

- `.toggle-1` means ON
- `.toggle-0` means OFF
- no explicit rule means ON by default

WebUI activation states:

- `ON`: explicit ON or implicit default
- `OFF`: explicit OFF rule at selected scope
- `Advanced`: at least one project/agent-profile override exists

`always_enabled: true` bypasses OFF state and keeps the plugin ON in both backend and UI.

## UI Flow

Current plugin UX surfaces activation in two places:

- Plugin list: simple ON/OFF selector, with `Advanced` option when scoped overrides are enabled
- Plugin switch modal: scope-aware ON/OFF controls per project/profile, with direct handoff to settings

Scope synchronization behavior:

- Opening "Configure Plugin" from the switch modal propagates current scope into settings store
- Switching scope in settings also mirrors into toggle store so activation status stays aligned

## API Surface

Core plugin management endpoint: `POST /api/plugins`

Supported actions:

- `get_config`
- `save_config`
- `list_configs`
- `delete_config`
- `toggle_plugin`

## Migration Notes

Current plugin format is YAML-based (`plugin.yaml`, `default_config.yaml`, `agent.yaml` for agent profiles). Legacy JSON manifests should be migrated.

## See Also

- `AGENTS.plugins.md` for full architecture details
- `skills/a0-create-plugin/SKILL.md` for plugin authoring workflow
