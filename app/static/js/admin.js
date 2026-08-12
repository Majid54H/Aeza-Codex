/** Admin UI client */

const uploadForm = document.getElementById("upload-form");
const fileInput = document.getElementById("file-input");
const documentList = document.getElementById("document-list");
const reindexBtn = document.getElementById("reindex-btn");
const uploadStatus = document.getElementById("upload-status");
const urlForm = document.getElementById("url-form");
const urlInput = document.getElementById("url-input");
const settingsForm = document.getElementById("settings-form");
const settingsStatus = document.getElementById("settings-status");
const chatbotNameInput = document.getElementById("chatbot-name");
const welcomeInput = document.getElementById("welcome-message");
const colorInput = document.getElementById("primary-color");
const colorTextInput = document.getElementById("primary-color-text");
const logoInput = document.getElementById("logo-url");
const statName = document.getElementById("stat-name");
const statCount = document.getElementById("stat-count");
const statStatus = document.getElementById("stat-status");

function setStatus(el, message, isError = false) {
    if (!el) return;
    el.textContent = message;
    el.className = isError ? "upload-status error" : "upload-status success";
}

function setUploadStatus(message, isError = false) {
    setStatus(uploadStatus, message, isError);
}

function dashboardStatus(docs) {
    if (!docs.length) return "No knowledge";
    const pending = docs.filter((d) => d.status === "pending").length;
    const indexed = docs.filter((d) => d.status === "indexed").length;
    if (indexed && pending) return `Ready · ${pending} pending URL${pending === 1 ? "" : "s"}`;
    if (indexed) return "Ready";
    if (pending) return "Pending URLs";
    return "Needs attention";
}

function renderDashboard(settings, docs) {
    if (statName) statName.textContent = settings.chatbot_name || "Aeza Codex";
    if (statCount) statCount.textContent = String(docs.length);
    if (statStatus) statStatus.textContent = dashboardStatus(docs);
}

function sourceLabel(doc) {
    const name = doc.filename || doc.url || doc.id;
    const kind = doc.source_type === "url" ? "URL" : "Document";
    return `${kind}: ${name} — ${doc.chunks ?? 0} chunks (${doc.status || "unknown"})`;
}

async function loadDocuments() {
    const res = await fetch("/api/knowledge/documents");
    const docs = await res.json();
    documentList.innerHTML = docs.length
        ? docs.map((d) => `<li>${sourceLabel(d)}</li>`).join("")
        : "<li>No knowledge sources yet.</li>";
    return docs;
}

async function loadSettings() {
    const res = await fetch("/api/admin/settings");
    const settings = await res.json();
    chatbotNameInput.value = settings.chatbot_name || "";
    welcomeInput.value = settings.welcome_message || "";
    colorInput.value = settings.primary_color || "#6366f1";
    colorTextInput.value = settings.primary_color || "#6366f1";
    logoInput.value = settings.logo_url || "";
    return settings;
}

async function refresh() {
    const [settings, docs] = await Promise.all([loadSettings(), loadDocuments()]);
    renderDashboard(settings, docs);
}

uploadForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const file = fileInput.files[0];
    if (!file) {
        setUploadStatus("Choose a document to upload.", true);
        return;
    }

    setUploadStatus("Uploading and indexing...");

    const formData = new FormData();
    formData.append("file", file);

    try {
        const res = await fetch("/api/knowledge/upload", { method: "POST", body: formData });
        const data = await res.json();

        if (!res.ok) {
            const detail = data.detail || "Upload failed.";
            setUploadStatus(typeof detail === "string" ? detail : "Upload failed.", true);
            return;
        }

        setUploadStatus(`Indexed ${data.filename}: ${data.chunks} chunks (${data.status}).`);
        fileInput.value = "";
        await refresh();
    } catch {
        setUploadStatus("Upload failed. Please try again.", true);
    }
});

urlForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const url = urlInput.value.trim();
    if (!url) {
        setUploadStatus("Enter a website URL.", true);
        return;
    }

    setUploadStatus("Fetching and indexing page...");
    try {
        const res = await fetch("/api/knowledge/url", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ url }),
        });
        const data = await res.json();
        if (!res.ok) {
            const detail = data.detail || "Could not save URL.";
            setUploadStatus(typeof detail === "string" ? detail : "Could not save URL.", true);
            return;
        }
        setUploadStatus(`Indexed ${data.filename}: ${data.chunks} chunks (${data.status}).`);
        urlInput.value = "";
        await refresh();
    } catch {
        setUploadStatus("Could not save URL. Please try again.", true);
    }
});

reindexBtn.addEventListener("click", async () => {
    setUploadStatus("Re-indexing all documents...");
    try {
        const res = await fetch("/api/admin/reindex", { method: "POST" });
        const data = await res.json();
        setUploadStatus(data.status === "reindex_complete" ? "Re-index complete." : "Re-index started.");
        await refresh();
    } catch {
        setUploadStatus("Re-index failed.", true);
    }
});

colorInput.addEventListener("input", () => {
    colorTextInput.value = colorInput.value;
});

colorTextInput.addEventListener("input", () => {
    if (/^#[0-9a-fA-F]{6}$/.test(colorTextInput.value)) {
        colorInput.value = colorTextInput.value;
    }
});

settingsForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const payload = {
        chatbot_name: chatbotNameInput.value.trim(),
        welcome_message: welcomeInput.value.trim(),
        primary_color: colorTextInput.value.trim() || colorInput.value,
        logo_url: logoInput.value.trim(),
    };
    setStatus(settingsStatus, "Saving branding...");
    try {
        const res = await fetch("/api/admin/settings", {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload),
        });
        const data = await res.json();
        if (!res.ok) {
            setStatus(settingsStatus, "Could not save branding.", true);
            return;
        }
        setStatus(settingsStatus, "Branding saved.");
        const docs = await loadDocuments();
        renderDashboard(data, docs);
    } catch {
        setStatus(settingsStatus, "Could not save branding.", true);
    }
});

refresh();
