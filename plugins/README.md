# Agent Zero Plugins

This directory contains default plugins shipped with Agent Zero.

## Architecture

Agent Zero uses a convention-over-configuration plugin model:

- Runtime capabilities are discovered from directory structure.
- Backend owns discovery, routing, and static asset serving.
- Frontend uses explicit `x-extension` breakpoints plus the standard `x-component` loader.

## Directory Conventions

Each plugin lives in `plugins/<plugin_id>/` (or `usr/plugins/<plugin_id>/` for overrides).

Capability discovery is based on these paths:

- `api/*.py` - API handlers (`ApiHandler` subclasses), exposed under `/api/plugins/<plugin_id>/<handler>`
- `tools/*.py` - agent tools (`Tool` subclasses)
- `helpers/*.py` - shared Python helpers
- `extensions/python/<extension_point>/*.py` - backend lifecycle extensions
- `extensions/webui/<extension_point>/*` - WebUI extension assets (HTML/JS)
- `webui/**` - full plugin-owned UI pages/components (loaded directly by path)
- `prompts/**/*.md` - prompt templates
- `agents/` - agent profiles

## Frontend Extensions

### HTML insertion via breakpoints

Core UI defines insertion points like:

```html
<x-extension id="sidebar-quick-actions-main-start"></x-extension>
```

Resolution flow:

1. `webui/js/extensions.js` finds `x-extension` nodes.
2. It calls `/api/load_webui_extensions` with the extension point and HTML filters.
3. Backend returns matching files from `plugins/*/extensions/webui/<extension_point>/`.
4. `extensions.js` injects returned entries as `<x-component path="...">`.
5. `components.js` loads each component using the standard component pipeline.

Baseline extension template (project convention):

```html
<div x-data>
  <button
    x-move-after=".config-button#dashboard"
    class="config-button"
    id="my-plugin-button"
    @click="openModal('../plugins/my-plugin/webui/my-modal.html')"
    title="My Plugin">
    <span class="material-symbols-outlined">extension</span>
  </button>
</div>
```

Required baseline for HTML UI extensions in this repository:
- include a root `x-data` scope
- include one explicit `x-move-*` placement directive

### JS hook extensions

JS hooks are loaded from the same extension point structure:

`plugins/<plugin_id>/extensions/webui/<extension_point>/*.js`

Runtime code calls:

`callJsExtensions("<extension_point>", ...args)`

Example:

`set_messages_before_loop` and `set_messages_after_loop` in `webui/js/messages.js`.

### Fine placement helpers

`initFw.js` provides Alpine move directives for plugin markup:

- `x-move-to-start`
- `x-move-to-end`
- `x-move-to`
- `x-move-before`
- `x-move-after`

## Plugin Author Flow

1. Pick an existing core breakpoint ID (`<x-extension id="...">`).
2. Add an HTML/JS extension under `extensions/webui/<extension_point>/`.
3. For HTML UI entries, use the baseline pattern: root `x-data` plus one explicit `x-move-*` directive.
4. Put complete plugin pages/components in `webui/` and open them directly by path.

## Routes

- Plugin static assets: `GET /plugins/<plugin_id>/<path>`
- Plugin APIs: `POST /api/plugins/<plugin_id>/<handler>`
- WebUI extension discovery: `POST /api/load_webui_extensions`

## Notes

- User plugins in `usr/plugins/` override repo plugins by plugin ID.
- Runtime behavior is fully convention-driven from directory structure.
