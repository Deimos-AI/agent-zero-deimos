from __future__ import annotations

from helpers.api import ApiHandler, Request, Response

from plugins._skills.helpers.runtime import (
    get_max_active_skills,
    list_catalog,
)


class SkillsCatalog(ApiHandler):
    async def process(self, input: dict, request: Request) -> dict | Response:
        action = str(input.get("action", "list") or "list").strip().lower()

        if action != "list":
            return {"ok": False, "error": f"Unknown action: {action}"}

        project_name = str(input.get("project_name", "") or "").strip()

        return {
            "ok": True,
            "skills": list_catalog(project_name=project_name),
            "max_active_skills": get_max_active_skills(),
        }
