// Chat Branching Plugin — injects a "branch" button into every message's action bar.
// Runs as a set_messages_after_loop JS extension.

import { createActionButton } from "/components/messages/action-buttons/simple-action-buttons.js";
import { callJsonApi } from "/js/api.js";

const LOG_NO_ATTR = "data-log-no";

/**
 * default export called by callJsExtensions("set_messages_after_loop", context)
 * context.messages is the raw log items array with { no, id, type, ... }
 */
export default async function injectBranchButtons(context) {
  if (!context?.messages?.length) return;

  // 1. Stamp every rendered element with its log "no" so the button can read it.
  for (const msg of context.messages) {
    const domId = msg.id || msg.no;
    // message containers use id="message-{id}", process steps use id="process-step-{id}"
    const el =
      document.getElementById(`message-${domId}`) ||
      document.getElementById(`process-step-${domId}`);
    if (el) el.setAttribute(LOG_NO_ATTR, String(msg.no));
  }

  // 2. Inject branch button into every action bar.
  //    Core renderers clear and rebuild action-button children on each update,
  //    so we check for the actual button element instead of a marker attribute.
  const bars = document.querySelectorAll(".step-action-buttons");
  for (const bar of bars) {
    if (bar.querySelector(".action-fork_right")) continue;

    // Resolve the log no from the nearest stamped ancestor
    const stamped = bar.closest(`[${LOG_NO_ATTR}]`);
    if (!stamped) continue;
    const logNo = Number(stamped.getAttribute(LOG_NO_ATTR));
    if (Number.isNaN(logNo)) continue;

    const btn = createActionButton("fork_right", "Branch chat", async () => {
      const ctxid = globalThis.getContext?.();
      if (!ctxid) throw new Error("No active chat");

      const res = await callJsonApi("/plugins/chat_branching/branch_chat", {
        context: ctxid,
        log_no: logNo,
      });

      if (!res?.ok) throw new Error(res?.message || "Branch failed");

      // Select the newly created branch chat
      const chatsStore = Alpine.store("chats");
      if (chatsStore) {
        chatsStore.selectChat(res.ctxid);
      }
    });

    if (btn) bar.appendChild(btn);
  }
}