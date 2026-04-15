from __future__ import annotations

from agent import LoopData
from helpers import plugins, projects
from helpers.extension import Extension

from plugins._skills.helpers.runtime import PLUGIN_NAME, resolve_active_skills


class IncludeActiveSkills(Extension):
    async def execute(self, loop_data: LoopData = LoopData(), **kwargs):
        if not self.agent:
            return

        project_name = projects.get_context_project_name(self.agent.context) or ""
        config = (
            plugins.get_plugin_config(
                PLUGIN_NAME,
                agent=self.agent,
                project_name=project_name,
                agent_profile="",
            )
            or {}
        )
        active_skills = resolve_active_skills(self.agent, config.get("active_skills"))
        if not active_skills:
            return

        content = "\n\n".join(item["content"] for item in active_skills if item.get("content")).strip()
        if not content:
            return

        loop_data.extras_persistent["active_skills"] = self.agent.read_prompt(
            "agent.system.active_skills.md",
            skills=content,
        )
