from __future__ import annotations

from pathlib import Path
from typing import Any, TypedDict

from helpers import files, plugins as plugin_helpers, projects, skills


PLUGIN_NAME = "_skills"
DEFAULT_MAX_ACTIVE_SKILLS = 5


class ActiveSkillEntry(TypedDict, total=False):
    name: str
    path: str


class CatalogSkill(TypedDict):
    name: str
    description: str
    path: str
    origin: str


def get_max_active_skills() -> int:
    try:
        from tools.skills_tool import max_loaded_skills

        value = int(max_loaded_skills())
        return value if value > 0 else DEFAULT_MAX_ACTIVE_SKILLS
    except Exception:
        return DEFAULT_MAX_ACTIVE_SKILLS


def coerce_config(config: dict[str, Any] | None) -> dict[str, Any]:
    normalized = dict(config or {})
    normalized["active_skills"] = normalize_active_skills(normalized.get("active_skills"))
    return normalized


def normalize_active_skills(raw: Any) -> list[ActiveSkillEntry]:
    if not isinstance(raw, list):
        return []

    limit = get_max_active_skills()
    normalized: list[ActiveSkillEntry] = []
    seen: set[str] = set()

    for item in raw:
        entry = _normalize_active_skill_entry(item)
        if not entry:
            continue

        key = _entry_key(entry)
        if not key or key in seen:
            continue

        seen.add(key)
        normalized.append(entry)
        if len(normalized) >= limit:
            break

    return normalized


def list_catalog(project_name: str = "") -> list[CatalogSkill]:
    catalog: list[CatalogSkill] = []
    seen_paths: set[str] = set()

    for root in _get_catalog_roots(project_name=project_name):
        root_path = Path(root)
        for skill_md in skills.discover_skill_md_files(root_path):
            skill = skills.skill_from_markdown(skill_md, include_content=False)
            if not skill:
                continue

            runtime_path = files.normalize_a0_path(str(skill.path))
            if runtime_path in seen_paths:
                continue

            seen_paths.add(runtime_path)
            catalog.append(
                {
                    "name": skill.name or skill.path.name,
                    "description": skill.description or "",
                    "path": runtime_path,
                    "origin": classify_origin(runtime_path, project_name=project_name),
                }
            )

    catalog.sort(key=lambda item: (item["name"].lower(), item["path"]))
    return catalog


def resolve_active_skills(agent: Any, raw_entries: Any) -> list[dict[str, str]]:
    visible_roots = [files.fix_dev_path(root) for root in skills.get_skill_roots(agent)]
    resolved: list[dict[str, str]] = []
    seen_paths: set[str] = set()

    for entry in normalize_active_skills(raw_entries):
        skill = _resolve_skill_entry(entry, visible_roots)
        if not skill:
            continue

        runtime_path = files.normalize_a0_path(str(skill.path))
        if runtime_path in seen_paths:
            continue

        seen_paths.add(runtime_path)
        resolved.append(
            {
                "name": skill.name or skill.path.name,
                "path": runtime_path,
                "content": format_skill_for_prompt(skill),
            }
        )

    return resolved


def format_skill_for_prompt(skill: skills.Skill) -> str:
    lines = [
        f"Skill: {skill.name or skill.path.name}",
        f"Path: {files.normalize_a0_path(str(skill.path))}",
    ]

    if skill.description:
        lines.extend(["", "Description:", skill.description.strip()])

    lines.extend(["", "Instructions:", (skill.content or "").strip() or "(empty)"])
    return "\n".join(lines)


def classify_origin(skill_path: str, project_name: str = "") -> str:
    abs_path = files.fix_dev_path(skill_path)

    if project_name:
        project_root = projects.get_project_meta(project_name, "skills")
        if files.exists(project_root) and files.is_in_dir(abs_path, project_root):
            return "Project"

    user_root = files.get_abs_path("usr", "skills")
    if files.exists(user_root) and files.is_in_dir(abs_path, user_root):
        return "User"

    normalized_path = files.normalize_a0_path(abs_path)
    if "/usr/plugins/" in normalized_path:
        return "Community plugin"
    if "/plugins/" in normalized_path:
        return "Built-in plugin"
    return "Built-in"


def _entry_key(entry: ActiveSkillEntry) -> str:
    return str(entry.get("path") or entry.get("name") or "").strip().lower()


def _normalize_active_skill_entry(item: Any) -> ActiveSkillEntry | None:
    if isinstance(item, str):
        stripped = item.strip()
        if not stripped:
            return None
        if "/" in stripped:
            return {"path": _normalize_skill_path(stripped)}
        return {"name": stripped}

    if not isinstance(item, dict):
        return None

    name = str(item.get("name") or "").strip()
    path = str(item.get("path") or "").strip()

    if path:
        path = _normalize_skill_path(path)
    if not (path or name):
        return None

    entry: ActiveSkillEntry = {}
    if name:
        entry["name"] = name
    if path:
        entry["path"] = path
    return entry


def _normalize_skill_path(path: str) -> str:
    fixed = path.strip().replace("\\", "/")
    if fixed.startswith("/a0/"):
        return fixed.rstrip("/")
    if fixed.startswith("/"):
        return files.normalize_a0_path(fixed).rstrip("/")
    return files.normalize_a0_path(files.get_abs_path(fixed)).rstrip("/")


def _get_catalog_roots(project_name: str = "") -> list[str]:
    roots: list[str] = []
    seen: set[str] = set()

    def add(path: str) -> None:
        if not path:
            return
        fixed = files.fix_dev_path(path)
        if not files.exists(fixed) or fixed in seen:
            return
        seen.add(fixed)
        roots.append(fixed)

    if project_name:
        add(projects.get_project_meta(project_name, "skills"))

    add(files.get_abs_path("usr", "skills"))
    for path in plugin_helpers.get_enabled_plugin_paths(None, "skills"):
        add(path)
    add(files.get_abs_path("skills"))

    return roots


def _resolve_skill_entry(entry: ActiveSkillEntry, visible_roots: list[str]) -> skills.Skill | None:
    skill_path = str(entry.get("path") or "").strip()
    if skill_path:
        skill = _load_skill_from_path(skill_path, visible_roots)
        if skill:
            return skill

    skill_name = str(entry.get("name") or "").strip()
    if not skill_name:
        return None

    target = skill_name.lower().strip()
    for root in visible_roots:
        for skill_md in skills.discover_skill_md_files(Path(root)):
            skill = skills.skill_from_markdown(skill_md, include_content=True)
            if not skill:
                continue
            candidates = {
                (skill.name or "").strip().lower(),
                skill.path.name.strip().lower(),
            }
            if target in candidates:
                return skill

    return None


def _load_skill_from_path(skill_path: str, visible_roots: list[str]) -> skills.Skill | None:
    abs_path = files.fix_dev_path(skill_path)
    if not any(files.is_in_dir(abs_path, root) for root in visible_roots):
        return None

    skill_md = Path(abs_path) / "SKILL.md"
    if not skill_md.is_file():
        return None

    return skills.skill_from_markdown(skill_md, include_content=True)
