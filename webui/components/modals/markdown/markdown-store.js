import { createStore } from "/js/AlpineStore.js";
import { renderSafeMarkdown } from "/js/safe-markdown.js";

export const store = createStore("markdownModal", {
    title: "",
    content: "",
    error: null,

    open(title, content) {
        this.title = title;
        this.content = content;
        this.error = null;
    },

    get renderedHtml() {
        if (!this.content) return "";
        return renderSafeMarkdown(this.content);
    },

    cleanup() {
        this.title = "";
        this.content = "";
        this.error = null;
    },
});
