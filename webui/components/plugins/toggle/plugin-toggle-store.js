import { createStore } from "/js/AlpineStore.js";
import { store as settingsStore } from "/components/plugins/plugin-settings-store.js";

const fetchApi = globalThis.fetchApi;

const model = {
    pluginName: null,
    
    // Context selectors
    projects: [],
    agentProfiles: [],
    projectName: "",
    agentProfileKey: "",

    // State
    isLoading: false,
    isSaving: false,
    error: null,
    
    // Status: 'enabled' | 'disabled'
    status: 'enabled',
    alwaysEnabled: false,
    explicitPath: null,
    configs: [],

    async open(plugin) {
        this.isLoading = true;
        this.error = null;
        this.projects = [];
        this.agentProfiles = [];
        this.projectName = "";
        this.agentProfileKey = "";
        this.configs = [];

        const pluginName = typeof plugin === 'string' ? plugin : plugin?.name;
        this.pluginName = pluginName;
        this.alwaysEnabled = typeof plugin === 'object' ? !!plugin.always_enabled : false;

        try {
            await Promise.all([this.loadProjects(), this.loadAgentProfiles()]);
            await this.loadConfigs();
        } finally {
            this.isLoading = false;
        }
    },

    cleanup() {
        this.pluginName = null;
        this.projectName = "";
        this.agentProfileKey = "";
        this.error = null;
        this.configs = [];
    },

    async loadProjects() {
        try {
            const response = await fetchApi("/projects", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ action: "list_options" }),
            });
            const data = await response.json().catch(() => ({}));
            this.projects = data.ok ? (data.data || []) : [];
        } catch {
            this.projects = [];
        }
    },

    async loadAgentProfiles() {
        try {
            const response = await fetchApi("/agents", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ action: "list" }),
            });
            const data = await response.json().catch(() => ({}));
            this.agentProfiles = data.ok ? (data.data || []) : [];
        } catch {
            this.agentProfiles = [];
        }
    },

    async loadConfigs() {
        if (!this.pluginName) return;
        this.isLoading = true;
        try {
            const response = await fetchApi("/plugins", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    action: "list_configs",
                    plugin_name: this.pluginName,
                    asset_type: "toggle"
                }),
            });
            const result = await response.json().catch(() => ({}));
            this.configs = result.ok ? (result.data || []) : [];
            this.calculateStatus();
        } catch (e) {
            this.error = e?.message || "Failed to load configurations";
        } finally {
            this.isLoading = false;
        }
    },

    async openConfigWithScope() {
        if (!this.pluginName) return;

        if (settingsStore.pluginName !== this.pluginName) {
            // Different plugin — full init with current scope
            await settingsStore.open(this.pluginName, {
                projectName: this.projectName || "",
                agentProfileKey: this.agentProfileKey || "",
            });
        } else {
            // Same plugin — push current scope explicitly.
            // onScopeChanged() syncs on @change events, but if the user never touched
            // the scope selectors after the modal opened the settings store may still
            // hold a stale scope from a prior session.
            settingsStore.projectName = this.projectName || "";
            settingsStore.agentProfileKey = this.agentProfileKey || "";
        }
        await window.openModal?.("components/plugins/plugin-settings.html");
    },

    async openConfigListModal() {
        await window.openModal?.("/components/plugins/toggle/plugin-toggles.html");
    },

    async loadConfigList() {
        await this.loadConfigs();
    },

    async switchToConfig(projectName, agentProfile) {
        this.projectName = projectName || "";
        this.agentProfileKey = agentProfile || "";
        this.onScopeChanged();
        await window.closeModal?.();
    },

    async deleteConfig(path) {
        if (!this.pluginName || !path) return;
        this.isLoading = true;
        try {
            const response = await fetchApi("/plugins", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    action: "delete_config",
                    plugin_name: this.pluginName,
                    path: path
                }),
            });
            const result = await response.json();
            if (!result.ok) throw new Error(result.error);
            await this.loadConfigs();
        } catch (e) {
            this.error = e.message || "Delete failed";
        } finally {
            this.isLoading = false;
        }
    },

    calculateStatus() {
        if (this.alwaysEnabled) {
            this.explicitPath = null;
            this.status = 'enabled';
            return;
        }

        const p = this.projectName || "";
        const a = this.agentProfileKey || "";
        const explicit = this.configs.find(
            c => (c.project_name||"") === p && (c.agent_profile||"") === a
        );

        if (explicit) {
            this.explicitPath = explicit.path;
            this.status = explicit.path.endsWith(".toggle-1") ? 'enabled' : 'disabled';
        } else {
            this.explicitPath = null;
            this.status = 'enabled'; // default when no explicit config
        }
    },

    async setEnabled(enabled) {
        if (!this.pluginName || this.alwaysEnabled) return;
        this.isSaving = true;
        try {
            const response = await fetchApi("/plugins", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    action: "toggle_plugin",
                    plugin_name: this.pluginName,
                    project_name: this.projectName || "",
                    agent_profile: this.agentProfileKey || "",
                    enabled: enabled
                }),
            });
            const result = await response.json();
            if (!result.ok) throw new Error(result.error);
            await new Promise(r => setTimeout(r, 100));
            await this.loadConfigs();
        } catch (e) {
            this.error = e.message || "Failed to save";
        } finally {
            this.isSaving = false;
        }
    },

    async onScopeChanged() {
        this.calculateStatus();

        // Sync scope with settings store so its loadSettings picks up the right context
        settingsStore.projectName = this.projectName || "";
        settingsStore.agentProfileKey = this.agentProfileKey || "";
        await settingsStore.loadSettings();
    },

    projectLabel(key) {
        if (!key) return "Global";
        const found = (this.projects || []).find(p => p.key === key);
        return found?.label || key;
    },

    agentProfileLabel(key) {
        if (!key) return "All profiles";
        const found = (this.agentProfiles || []).find(p => p.key === key);
        return found?.label || key;
    },

    get statusLabel() {
        return this.status === 'enabled' ? 'ON' : 'OFF';
    },

    get noScopeRuleMessage() {
        if (this.alwaysEnabled || this.isLoading) return "";
        if (this.configs.length === 0) return "No activation rules configured. Plugin defaults to ON.";
        if (!this.explicitPath) return "No rule set for this scope. Status defaults to ON.";
        return "";
    }
};

export const store = createStore("pluginToggle", model);
