import * as API from "/js/api.js";
import { store as settingsStore } from "/components/settings/settings-store.js";
import { store as chatsStore } from "/components/sidebar/chats/chats-store.js";
import { store as projectsStore } from "/components/projects/projects-store.js";
import {
  toastFrontendError,
  toastFrontendInfo,
} from "/components/notifications/notification-store.js";

const CATALOG_API = "/plugins/_skills/skills_catalog";
const MAX_ACTIVE_SKILLS_FALLBACK = 5;

function normalizeEntry(entry) {
  if (!entry) return null;
  if (typeof entry === "string") {
    const trimmed = entry.trim();
    if (!trimmed) return null;
    return trimmed.includes("/")
      ? { path: trimmed.replace(/\/+$/, "") }
      : { name: trimmed };
  }

  if (typeof entry !== "object") return null;
  const name = String(entry.name || "").trim();
  const path = String(entry.path || "").trim().replace(/\/+$/, "");
  if (!name && !path) return null;
  return {
    ...(name ? { name } : {}),
    ...(path ? { path } : {}),
  };
}

function entryKey(entry) {
  if (!entry) return "";
  return String(entry.path || entry.name || "").trim().toLowerCase();
}

function ensureConfig(config) {
  if (!config || typeof config !== "object") return;
  const activeSkills = Array.isArray(config.active_skills) ? config.active_skills : [];
  const normalized = [];
  const seen = new Set();

  for (const item of activeSkills) {
    const entry = normalizeEntry(item);
    const key = entryKey(entry);
    if (!entry || !key || seen.has(key)) continue;
    seen.add(key);
    normalized.push(entry);
  }

  config.active_skills = normalized;
}

window.createSkillsConfigModel = (context, config) => ({
  loadingCatalog: false,
  catalog: [],
  search: "",
  maxActiveSkills: MAX_ACTIVE_SKILLS_FALLBACK,

  initDefaults() {
    ensureConfig(config);
  },

  get activeEntries() {
    ensureConfig(config);
    return config.active_skills;
  },

  get selectedCount() {
    return this.activeEntries.length;
  },

  get selectedCountLabel() {
    return `${this.selectedCount} / ${this.maxActiveSkills}`;
  },

  get limitDescription() {
    return `Max in extras: ${this.maxActiveSkills}`;
  },

  get activeProject() {
    return chatsStore.selectedContext?.project || null;
  },

  get scopeSummary() {
    if (context.projectName) {
      return `Project: ${context.projectLabel(context.projectName)}`;
    }
    return "Project: Global";
  },

  get catalogMap() {
    const byKey = new Map();
    for (const skill of this.catalog) {
      byKey.set(entryKey(skill), skill);
      if (skill.name) {
        byKey.set(String(skill.name).trim().toLowerCase(), skill);
      }
    }
    return byKey;
  },

  get filteredCatalog() {
    const query = this.search.trim().toLowerCase();
    if (!query) return this.catalog;

    return this.catalog.filter((skill) => {
      const haystack = [
        skill.name,
        skill.description,
        skill.path,
        skill.origin,
      ]
        .filter(Boolean)
        .join(" ")
        .toLowerCase();
      return haystack.includes(query);
    });
  },

  entryKey(entry) {
    return entryKey(entry);
  },

  isSelected(skill) {
    return this.activeEntries.some((entry) => entryKey(entry) === entryKey(skill));
  },

  isCheckboxDisabled(skill) {
    return !this.isSelected(skill) && this.selectedCount >= this.maxActiveSkills;
  },

  isEntryMissing(entry) {
    const key = entryKey(entry);
    if (!key) return false;
    if (this.catalogMap.has(key)) return false;
    if (entry.name && this.catalogMap.has(String(entry.name).trim().toLowerCase())) return false;
    return true;
  },

  labelForEntry(entry) {
    const skill = this._resolveEntry(entry);
    if (skill?.name) return skill.name;
    return entry?.name || "(unnamed skill)";
  },

  secondaryLabelForEntry(entry) {
    const skill = this._resolveEntry(entry);
    if (skill) {
      return `${skill.origin} | ${skill.path}`;
    }
    if (entry?.path) return `Not visible in the current catalog | ${entry.path}`;
    return "Not visible in the current catalog";
  },

  _resolveEntry(entry) {
    const key = entryKey(entry);
    if (key && this.catalogMap.has(key)) {
      return this.catalogMap.get(key);
    }
    const name = String(entry?.name || "").trim().toLowerCase();
    return name ? this.catalogMap.get(name) || null : null;
  },

  toggleSkill(skill, selected) {
    ensureConfig(config);
    const key = entryKey(skill);
    const nextEntries = this.activeEntries.filter((entry) => entryKey(entry) !== key);

    if (selected) {
      if (this.selectedCount >= this.maxActiveSkills) {
        void toastFrontendInfo(
          `You can activate at most ${this.maxActiveSkills} skills in extras.`,
          "Skills"
        );
        return;
      }

      nextEntries.push({
        name: String(skill.name || "").trim(),
        path: String(skill.path || "").trim(),
      });
    }

    config.active_skills = nextEntries;
  },

  removeEntry(entry) {
    ensureConfig(config);
    const key = entryKey(entry);
    config.active_skills = this.activeEntries.filter((item) => entryKey(item) !== key);
  },

  clearSelections() {
    ensureConfig(config);
    config.active_skills = [];
  },

  async loadCatalog() {
    this.loadingCatalog = true;
    try {
      const response = await API.callJsonApi(CATALOG_API, {
        action: "list",
        project_name: context.projectName || "",
      });

      if (!response?.ok) {
        throw new Error(response?.error || "Failed to load skills catalog");
      }

      this.catalog = Array.isArray(response.skills) ? response.skills : [];
      this.maxActiveSkills = Number(response.max_active_skills) || MAX_ACTIVE_SKILLS_FALLBACK;
    } catch (error) {
      this.catalog = [];
      this.maxActiveSkills = MAX_ACTIVE_SKILLS_FALLBACK;
      await toastFrontendError(error?.message || "Failed to load skills catalog", "Skills");
    } finally {
      this.loadingCatalog = false;
    }
  },

  async navigateAway(callback) {
    if (context.hasUnsavedChanges && !context.confirmDiscardUnsavedChanges()) {
      return;
    }

    await window.closeModal?.();
    await callback();
  },

  async openSettingsSkills() {
    await this.navigateAway(async () => {
      await settingsStore.open("skills");
    });
  },

  async openActiveProjectSkills() {
    const projectName = this.activeProject?.name;
    if (!projectName) {
      await toastFrontendInfo("No active project is selected in the current chat.", "Skills");
      return;
    }

    await this.navigateAway(async () => {
      await projectsStore.openEditModal(projectName);
      this.scrollProjectSkillsSection();
    });
  },

  scrollProjectSkillsSection(attempt = 0) {
    const headers = Array.from(
      document.querySelectorAll(".project-detail-header .projects-project-card-title")
    );
    const target = headers.find(
      (header) => header.textContent?.trim().toLowerCase() === "skills"
    );
    const section = target?.closest(".project-detail");

    if (section) {
      section.scrollIntoView({ behavior: "smooth", block: "start" });
      return;
    }

    if (attempt < 12) {
      window.setTimeout(() => this.scrollProjectSkillsSection(attempt + 1), 120);
    }
  },
});

export {};
