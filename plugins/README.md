# Agent Zero Plugins

This directory contains default plugins shipped with Agent Zero and is the source of truth for the plugin system.

## Architecture

Agent Zero uses a convention-over-configuration plugin model:

- Runtime capabilities are discovered from directory structure.
- Backend owns discovery, routing, and static asset serving.
- Frontend uses explicit `x-extension` breakpoints plus the standard `x-component` loader.

### Internal Components

1. **Backend plugin discovery** (`python/helpers/plugins.py`)
   - `get_plugin_roots()` resolves roots in priority order (`usr/plugins` first, then `plugins`).
   - `list_plugins()` builds the effective set (first root wins on ID conflicts).
   - `get_webui_extensions(extension_point, filters)` scans `extensions/webui/<extension_point>/`.

2. **Path resolution** (`python/helpers/subagents.py`)
   - `get_paths(..., include_plugins=True)` includes plugin candidates for prompts/tools.

3. **Python extension runtime** (`python/helpers/extension.py`)
   - `call_extensions(extension_point, agent, **kwargs)` executes extension classes.
   - Searches `python/extensions/<point>/` and `plugins/*/extensions/python/<point>/`.
   - Extension classes derive from `Extension` and implement `async execute()`.

4. **API and static routes** (`run_ui.py`, `python/api/load_webui_extensions.py`)
   - `GET /plugins/<plugin_id>/<path>` serves plugin static assets.
   - Plugin APIs are mounted under `/api/plugins/<plugin_id>/<handler>`.
   - `POST /api/load_webui_extensions` returns extension files for a given extension point.

5. **Frontend WebUI extension runtime** (`webui/js/extensions.js`)
   - HTML flow: discovers `<x-extension>` tags, calls backend API, injects `<x-component>` tags.
   - JS flow: `callJsExtensions("<extension_point>", contextObject)` loads and executes plugin JS modules.
   - Both HTML and JS lookups are cached per extension point.

## File Structure

```text
plugins/
  <plugin_id>/
    api/                          # API handlers (ApiHandler subclasses)
    tools/                        # Agent tools (Tool subclasses)
    helpers/                      # Shared Python helpers
    prompts/                      # Prompt templates
    agents/                       # Agent profiles
    extensions/
      python/<extension_point>/   # Python lifecycle extensions
      webui/<extension_point>/    # WebUI HTML/JS hook contributions
    webui/                        # Full plugin-owned UI pages/components

usr/plugins/<plugin_id>/          # User overrides (higher priority)
```

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

Current sidebar surfaces:

- `sidebar-start`
- `sidebar-end`
- `sidebar-top-wrapper-start`
- `sidebar-top-wrapper-end`
- `sidebar-quick-actions-main-start`
- `sidebar-quick-actions-main-end`
- `sidebar-quick-actions-dropdown-start`
- `sidebar-quick-actions-dropdown-end`
- `sidebar-chats-list-start`
- `sidebar-chats-list-end`
- `sidebar-tasks-list-start`
- `sidebar-tasks-list-end`
- `sidebar-bottom-wrapper-start`
- `sidebar-bottom-wrapper-end`

Current input surfaces:

- `chat-input-start`
- `chat-input-end`
- `chat-input-progress-start`
- `chat-input-progress-end`
- `chat-input-box-start`
- `chat-input-box-end`
- `chat-input-bottom-actions-start`
- `chat-input-bottom-actions-end`

Current chat surfaces:

- `chat-top-start`
- `chat-top-end`

Current welcome surfaces:

- `welcome-screen-start`
- `welcome-screen-end`
- `welcome-actions-start`
- `welcome-actions-end`
- `welcome-banners-start`
- `welcome-banners-end`

Current modal surfaces:

- `modal-shell-start`
- `modal-shell-end`

Placement pattern:
- keep wrapper-level anchors in parent composition files
- keep section anchors in their owning component files, inside local `x-data` scope

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

`callJsExtensions("<extension_point>", contextObject)`

JS hook convention:
- pass one mutable context object when extensions are expected to influence behavior
- that object is passed by reference, so mutations are visible to subsequent hooks in the same flow
- hooks that support cancellation expose a `cancel: false` or `skip: false` field; set it to `true` to abort the operation

Current JS hook points:

| Hook | File | Context fields | skip/cancel |
|---|---|---|---|
| `set_messages_before_loop` | messages.js | `messages, history, scrollerOptions, massRender, results` | - |
| `set_messages_after_loop` | messages.js | same as above | - |
| `send_message_before` | index.js | `message, attachments, context, cancel` | `cancel` |
| `apply_snapshot_before` | index.js | `snapshot, willUpdateMessages, skip` | `skip` |
| `open_modal_before` | modals.js | `modalPath, modal, cancel` | `cancel` |
| `close_modal_before` | modals.js | `modalPath, modal, cancel` | `cancel` |

### Fine placement helpers

`initFw.js` provides Alpine move directives for plugin markup:

- `x-move-to-start`
- `x-move-to-end`
- `x-move-to`
- `x-move-before`
- `x-move-after`

Placement behavior:
- `x-move-to-start`, `x-move-to-end`, and `x-move-to` resolve a parent selector and insert the extension element as that parent's child.
- `x-move-before` and `x-move-after` resolve a reference selector and insert the extension element as a sibling in the reference element's parent.
- This structural difference can produce different visual results when parent and sibling styling differ (for example dropdown spacing/padding).
- Example anchor selector for placing after the first dropdown item: `x-move-after=".quick-actions-dropdown .dropdown-header + .dropdown-item"`.

## Plugin Author Flow

1. Create `plugins/<plugin_id>/`.
2. Add backend capabilities by convention (`api/`, `tools/`, `helpers/`, `extensions/python/`, `prompts/`, `agents/`).
3. Pick a WebUI breakpoint or JS hook extension point.
4. For HTML UI entries: place files under `extensions/webui/<extension_point>/`, use root `x-data` + one `x-move-*` directive.
5. For JS hooks: place `*.js` files under `extensions/webui/<extension_point>/`, export a default async function.
6. Place full plugin pages/components in `webui/` and open them directly by path.

### Python extension example

```python
# plugins/my-plugin/extensions/python/monologue_end/_50_my_extension.py
from python.helpers.extension import Extension

class MyExtension(Extension):
    async def execute(self, **kwargs):
        pass
```

### HTML WebUI extension example

```html
<!-- plugins/my-plugin/extensions/webui/sidebar-quick-actions-main-start/my-button.html -->
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

### JS hook example

```js
// plugins/my-plugin/extensions/webui/send_message_before/transform.js
export default async function(ctx) {
  // prepend a tag to every outgoing message
  ctx.message = "[my-plugin] " + ctx.message;
}
```

### Full plugin UI page

```html
<!-- opened via openModal() or x-component -->
<x-component path="../plugins/my-plugin/webui/my-modal.html"></x-component>
```

## Routes

- Plugin static assets: `GET /plugins/<plugin_id>/<path>`
- Plugin APIs: `POST /api/plugins/<plugin_id>/<handler>`
- WebUI extension discovery: `POST /api/load_webui_extensions`

## Notes

- User plugins in `usr/plugins/` override repo plugins by plugin ID.
- Runtime behavior is fully convention-driven from directory structure.
- Extension point ordering between multiple plugins is currently implicit (filesystem order).
- Project-specific plugin roots are not yet active (commented out in `get_plugin_roots()`).
- When you need a new extension point for your plugin, submit a PR - we are actively expanding coverage based on community needs.
