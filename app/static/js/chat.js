/** Chat UI client */

const messagesEl = document.getElementById("messages");
const form = document.getElementById("chat-form");
const input = document.getElementById("message-input");
const loadingIndicator = document.getElementById("loading-indicator");
const sendButton = document.getElementById("send-button");
const chatTitle = document.getElementById("chat-title");
const chatWelcome = document.getElementById("chat-welcome");

async function applyBranding() {
    try {
        const res = await fetch("/api/admin/settings");
        if (!res.ok) return;
        const settings = await res.json();
        if (chatTitle && settings.chatbot_name) {
            chatTitle.textContent = settings.chatbot_name;
            document.title = `${settings.chatbot_name} — Chat`;
        }
        if (chatWelcome && settings.welcome_message) {
            chatWelcome.textContent = settings.welcome_message;
        }
        if (settings.primary_color) {
            document.documentElement.style.setProperty("--primary-color", settings.primary_color);
            if (sendButton) sendButton.style.background = settings.primary_color;
        }
    } catch {
        // Keep default branding if settings cannot be loaded.
    }
}

applyBranding();

function appendMessage(role, text) {
    const div = document.createElement("div");
    div.className = `message message-${role}`;
    div.textContent = `${role === "user" ? "You" : "Codex"}: ${text}`;
    messagesEl.appendChild(div);
    messagesEl.scrollTop = messagesEl.scrollHeight;
}

function setLoading(isLoading) {
    if (isLoading) {
        if (loadingIndicator) loadingIndicator.classList.add("active");
        if (sendButton) sendButton.disabled = true;
        if (input) input.disabled = true;
    } else {
        if (loadingIndicator) loadingIndicator.classList.remove("active");
        if (sendButton) sendButton.disabled = false;
        if (input) input.disabled = false;
    }
}

form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const message = input.value.trim();
    if (!message) return;

    appendMessage("user", message);
    input.value = "";

    setLoading(true);

    // Show a "typing..." bubble immediately.
    appendMessage("assistant", "…");

    try {
        const res = await fetch("/api/chat", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ message }),
        });

        const data = await res.json();

        // Remove the last loading bubble (the most recently appended assistant message)
        // and replace it with the real response.
        const last = messagesEl.lastElementChild;
        if (last && last.classList.contains("message-assistant")) {
            last.remove();
        }

        appendMessage("assistant", data.reply);
    } catch (err) {
        const last = messagesEl.lastElementChild;
        if (last && last.classList.contains("message-assistant")) {
            last.remove();
        }
        appendMessage("assistant", "Sorry, something went wrong. Please try again.");
    } finally {
        // Ensure UI is always restored even if the request fails.
        setLoading(false);
    }
});
