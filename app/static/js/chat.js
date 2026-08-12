/** Chat UI client */

const messagesEl = document.getElementById("messages");
const form = document.getElementById("chat-form");
const input = document.getElementById("message-input");
const loadingIndicator = document.getElementById("loading-indicator");
const sendButton = document.getElementById("send-button");
const chatTitle = document.getElementById("chat-title");
const chatAvatar = document.getElementById("chat-avatar");
const chatDisclaimer = document.getElementById("chat-disclaimer");
const welcomePanel = document.getElementById("welcome-panel");
const welcomeHeading = document.getElementById("welcome-heading");
const welcomeCopy = document.getElementById("welcome-copy");

let sessionId = null;
let botName = "Assistant";
let dateShown = false;

function formatTime(date = new Date()) {
    return date.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
}

function initialFor(name) {
    const trimmed = (name || "").trim();
    return trimmed ? trimmed.charAt(0).toUpperCase() : "A";
}

function ensureDateDivider() {
    if (dateShown || !messagesEl) return;
    const pill = document.createElement("div");
    pill.className = "chat-date";
    pill.textContent = "Today";
    messagesEl.appendChild(pill);
    dateShown = true;
}

function setAvatar(name, logoUrl) {
    if (!chatAvatar) return;
    chatAvatar.replaceChildren();
    if (logoUrl) {
        const img = document.createElement("img");
        img.src = logoUrl;
        img.alt = "";
        chatAvatar.appendChild(img);
        return;
    }
    chatAvatar.textContent = initialFor(name);
}

function appendInline(el, text) {
    const re = /(\*\*[^*]+\*\*|__[^_]+__|`[^`]+`|\*[^*\n]+\*)/g;
    let last = 0;
    let match;
    while ((match = re.exec(text))) {
        if (match.index > last) {
            el.appendChild(document.createTextNode(text.slice(last, match.index)));
        }
        const token = match[0];
        if (token.startsWith("**") || token.startsWith("__")) {
            const strong = document.createElement("strong");
            strong.textContent = token.slice(2, -2);
            el.appendChild(strong);
        } else if (token.startsWith("`")) {
            const code = document.createElement("code");
            code.textContent = token.slice(1, -1);
            el.appendChild(code);
        } else {
            const em = document.createElement("em");
            em.textContent = token.slice(1, -1);
            el.appendChild(em);
        }
        last = match.index + token.length;
    }
    if (last < text.length) {
        el.appendChild(document.createTextNode(text.slice(last)));
    }
}

function renderMarkdown(parent, raw) {
    const lines = String(raw || "").replace(/\r\n/g, "\n").split("\n");
    let list = null;

    function closeList() {
        if (list) {
            parent.appendChild(list);
            list = null;
        }
    }

    function openList(ordered) {
        if (!list || (ordered && list.tagName !== "OL") || (!ordered && list.tagName !== "UL")) {
            closeList();
            list = document.createElement(ordered ? "ol" : "ul");
        }
    }

    for (const line of lines) {
        const trimmed = line.trim();
        if (!trimmed) {
            closeList();
            continue;
        }

        const heading = /^(#{1,3})\s+(.+)$/.exec(trimmed);
        const ulItem = /^[-*+]\s+(.+)$/.exec(trimmed);
        const olItem = /^\d+[.)]\s+(.+)$/.exec(trimmed);
        const boldHeading = /^\*\*([^*]+)\*\*\s*$/.exec(trimmed);

        if (heading) {
            closeList();
            const level = Math.min(heading[1].length, 3);
            const h = document.createElement(`h${level}`);
            appendInline(h, heading[2]);
            parent.appendChild(h);
        } else if (boldHeading) {
            closeList();
            const h = document.createElement("h3");
            h.textContent = boldHeading[1];
            parent.appendChild(h);
        } else if (ulItem) {
            openList(false);
            const li = document.createElement("li");
            appendInline(li, ulItem[1]);
            list.appendChild(li);
        } else if (olItem) {
            openList(true);
            const li = document.createElement("li");
            appendInline(li, olItem[1]);
            list.appendChild(li);
        } else {
            closeList();
            const p = document.createElement("p");
            appendInline(p, trimmed);
            parent.appendChild(p);
        }
    }
    closeList();
    if (!parent.childNodes.length) {
        parent.textContent = raw || "";
    }
}

function appendMessage(role, text) {
    if (!messagesEl) return;
    ensureDateDivider();

    const row = document.createElement("div");
    row.className = `msg-row msg-row-${role}`;

    if (role === "assistant") {
        const avatar = document.createElement("div");
        avatar.className = "msg-avatar";
        avatar.textContent = initialFor(botName);
        row.appendChild(avatar);
    }

    const stack = document.createElement("div");
    stack.className = "msg-stack";

    const bubble = document.createElement("div");
    bubble.className = `message message-${role}`;
    if (role === "assistant") {
        renderMarkdown(bubble, text);
    } else {
        bubble.textContent = text;
    }
    stack.appendChild(bubble);

    const meta = document.createElement("div");
    meta.className = "msg-meta";
    const time = document.createElement("span");
    time.textContent = formatTime();
    meta.appendChild(time);
    if (role === "user") {
        const ticks = document.createElement("span");
        ticks.className = "msg-ticks";
        ticks.setAttribute("aria-hidden", "true");
        ticks.textContent = "✓✓";
        meta.appendChild(ticks);
    }
    stack.appendChild(meta);
    row.appendChild(stack);
    messagesEl.appendChild(row);
    messagesEl.scrollTop = messagesEl.scrollHeight;
    return row;
}

function startAssistantMessage() {
    if (!messagesEl) return null;
    ensureDateDivider();

    const row = document.createElement("div");
    row.className = "msg-row msg-row-assistant";

    const avatar = document.createElement("div");
    avatar.className = "msg-avatar";
    avatar.textContent = initialFor(botName);
    row.appendChild(avatar);

    const stack = document.createElement("div");
    stack.className = "msg-stack";

    const bubble = document.createElement("div");
    bubble.className = "message message-assistant is-streaming";
    stack.appendChild(bubble);

    const meta = document.createElement("div");
    meta.className = "msg-meta";
    const time = document.createElement("span");
    time.textContent = formatTime();
    meta.appendChild(time);
    stack.appendChild(meta);

    row.appendChild(stack);
    messagesEl.appendChild(row);
    messagesEl.scrollTop = messagesEl.scrollHeight;
    return bubble;
}

function updateAssistantMessage(bubble, text) {
    if (!bubble) return;
    bubble.replaceChildren();
    renderMarkdown(bubble, text);
    if (messagesEl) messagesEl.scrollTop = messagesEl.scrollHeight;
}

async function readChatStream(res, onEvent) {
    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const parts = buffer.split("\n\n");
        buffer = parts.pop() || "";
        for (const part of parts) {
            const line = part.split("\n").find((l) => l.startsWith("data: "));
            if (!line) continue;
            try {
                onEvent(JSON.parse(line.slice(6)));
            } catch {
                // skip malformed chunk
            }
        }
    }
}

function showTyping() {
    if (!messagesEl) return;
    ensureDateDivider();
    const row = document.createElement("div");
    row.className = "msg-row msg-row-assistant typing-row";
    row.id = "typing-row";

    const avatar = document.createElement("div");
    avatar.className = "msg-avatar";
    avatar.textContent = initialFor(botName);
    row.appendChild(avatar);

    const bubble = document.createElement("div");
    bubble.className = "message message-assistant typing-bubble";
    for (let i = 0; i < 3; i += 1) {
        bubble.appendChild(document.createElement("span"));
    }
    row.appendChild(bubble);
    messagesEl.appendChild(row);
    messagesEl.scrollTop = messagesEl.scrollHeight;
}

function hideTyping() {
    const row = document.getElementById("typing-row");
    if (row) row.remove();
}

async function applyBranding() {
    try {
        const res = await fetch("/api/admin/settings");
        if (!res.ok) return;
        const settings = await res.json();
        if (settings.chatbot_name) {
            botName = settings.chatbot_name;
            if (chatTitle) chatTitle.textContent = botName;
            document.title = `${botName} — Chat`;
        }
        setAvatar(botName, settings.logo_url || "");
        if (chatDisclaimer) {
            chatDisclaimer.textContent = `${botName} can make mistakes. Please verify important information.`;
        }
        if (welcomeHeading) {
            welcomeHeading.textContent = `Hi, I'm ${botName}`;
        }
        if (welcomeCopy) {
            welcomeCopy.textContent = settings.welcome_message || "";
            welcomeCopy.hidden = !settings.welcome_message;
        }
    } catch {
        setAvatar(botName, "");
    }
}

function setLoading(isLoading) {
    if (isLoading) {
        if (loadingIndicator) loadingIndicator.classList.add("active");
        if (sendButton) sendButton.disabled = true;
        showTyping();
    } else {
        if (loadingIndicator) loadingIndicator.classList.remove("active");
        if (sendButton) sendButton.disabled = false;
        hideTyping();
        if (input) input.focus();
    }
}

document.querySelectorAll(".welcome-chip").forEach((chip) => {
    chip.addEventListener("click", () => {
        if (!input || sendButton.disabled) return;
        input.value = chip.dataset.prompt || chip.textContent || "";
        form.requestSubmit();
    });
});

applyBranding();

form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const message = input.value.trim();
    if (!message || sendButton.disabled) return;

    if (welcomePanel) welcomePanel.hidden = true;

    appendMessage("user", message);
    input.value = "";
    if (sendButton) sendButton.disabled = true;
    if (loadingIndicator) loadingIndicator.classList.add("active");
    showTyping();

    let bubble = null;
    let fullText = "";

    try {
        const res = await fetch("/api/chat/stream", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ message, session_id: sessionId }),
        });
        if (!res.ok || !res.body) {
            throw new Error("stream failed");
        }
        await readChatStream(res, (event) => {
            if (event.type === "meta" && event.session_id) {
                sessionId = event.session_id;
            }
            if (event.type === "token" && event.text) {
                if (!bubble) {
                    hideTyping();
                    bubble = startAssistantMessage();
                }
                fullText += event.text;
                updateAssistantMessage(bubble, fullText);
            }
            if (event.type === "error") {
                if (!bubble) {
                    hideTyping();
                    bubble = startAssistantMessage();
                }
                updateAssistantMessage(bubble, event.text || "Sorry, something went wrong. Please try again.");
            }
        });
        if (!fullText) {
            hideTyping();
            if (!bubble) bubble = startAssistantMessage();
            updateAssistantMessage(bubble, "Sorry, something went wrong. Please try again.");
        }
        if (bubble) bubble.classList.remove("is-streaming");
    } catch {
        hideTyping();
        appendMessage("assistant", "Sorry, something went wrong. Please try again.");
    } finally {
        if (loadingIndicator) loadingIndicator.classList.remove("active");
        if (sendButton) sendButton.disabled = false;
        if (input) input.focus();
    }
});
