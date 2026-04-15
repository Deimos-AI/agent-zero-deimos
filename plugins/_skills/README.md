# Skills

Skills is a built-in Agent Zero plugin that lets you pin skills into prompt extras for a chosen scope.

## What It Does

- activates selected skills for the current plugin scope
- injects those skills into prompt extras on every turn
- supports global and project scoped configurations without agent-profile variants
- links directly to the built-in Skills list
- links directly to the active project's Skills section when a project is active

## Why This Exists

Agent Zero already supports loading skills dynamically with `skills_tool`, and already has great built-in skill management surfaces. What it did not have was a lightweight way to make a few skills feel "always on" for a specific scope without modifying the core prompt system.

Skills fills that gap as a bundled built-in plugin.

## Notes

- keep the active list short because every selected skill is injected into prompt extras every turn
- this plugin enforces the same extras cap as the core `skills_tool`: at most 5 active skills
- selected skills are stored in normalized `/a0/...` form so configs stay portable across development and Docker-style layouts
- if a configured skill is not visible in the current agent scope, it is skipped quietly instead of breaking the prompt build
