/** Chat UI client */

const messagesEl = document.getElementById("messages");
const form = document.getElementById("chat-form");
const input = document.getElementById("message-input");
const loadingIndicator = document.getElementById("loading-indicator");
const sendButton = document.getElementById("send-button");

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
