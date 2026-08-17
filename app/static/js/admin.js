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

const authPanel = document.getElementById("auth-panel");
const adminDashboard = document.getElementById("admin-dashboard");
const adminLoginForm = document.getElementById("admin-login-form");
const adminUsernameInput = document.getElementById("admin-username");
const adminPasswordInput = document.getElementById("admin-password");
const adminLoginStatus = document.getElementById("admin-login-status");

const credentialsForm = document.getElementById("credentials-form");
const adminCurrentPasswordInput = document.getElementById("admin-current-password");
const adminNewUsernameInput = document.getElementById("admin-new-username");
const adminNewPasswordInput = document.getElementById("admin-new-password");
const credentialsStatus = document.getElementById("credentials-status");

const toggleRecoverBtn = document.getElementById("toggle-recover-btn");
const recoverCredentialsForm = document.getElementById("recover-credentials-form");
const recoverPasswordInput = document.getElementById("recover-password");
const recoverNewUsernameInput = document.getElementById("recover-new-username");
const recoverNewPasswordInput = document.getElementById("recover-new-password");
const recoverStatus = document.getElementById("recover-status");

const adminLogoutBtn = document.getElementById("admin-logout-btn");
const adminUserLabel = document.getElementById("admin-user-label");

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
    if (statName) statName.textContent = (settings && settings.chatbot_name) || "—";
    if (statCount) statCount.textContent = Array.isArray(docs) ? String(docs.length) : "—";
    if (statStatus) statStatus.textContent = Array.isArray(docs) ? dashboardStatus(docs) : "—";
}

const fileNameLabel = document.getElementById("file-name");

function svgIcon(paths) {
    const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    svg.setAttribute("class", "source-icon");
    svg.setAttribute("viewBox", "0 0 24 24");
    svg.setAttribute("aria-hidden", "true");
    for (const attrs of paths) {
        const el = document.createElementNS("http://www.w3.org/2000/svg", attrs.tag);
        for (const [key, value] of Object.entries(attrs)) {
            if (key !== "tag") el.setAttribute(key, value);
        }
        svg.appendChild(el);
    }
    return svg;
}

function fileIcon() {
    return svgIcon([
        {
            tag: "path",
            d: "M7 3.5h7l5 5V20a1.5 1.5 0 0 1-1.5 1.5h-10.5A1.5 1.5 0 0 1 5.5 20V5A1.5 1.5 0 0 1 7 3.5z",
            fill: "none",
            stroke: "currentColor",
            "stroke-width": "1.6",
            "stroke-linejoin": "round",
        },
        {
            tag: "path",
            d: "M14 3.5V9h5.5",
            fill: "none",
            stroke: "currentColor",
            "stroke-width": "1.6",
            "stroke-linejoin": "round",
        },
    ]);
}

function linkIcon() {
    return svgIcon([
        {
            tag: "path",
            d: "M10 13.5 8.5 15a3.2 3.2 0 0 1-4.5-4.5L7.5 7a3.2 3.2 0 0 1 4.5 0",
            fill: "none",
            stroke: "currentColor",
            "stroke-width": "1.6",
            "stroke-linecap": "round",
        },
        {
            tag: "path",
            d: "M14 10.5 15.5 9a3.2 3.2 0 0 1 4.5 4.5L16.5 17a3.2 3.2 0 0 1-4.5 0",
            fill: "none",
            stroke: "currentColor",
            "stroke-width": "1.6",
            "stroke-linecap": "round",
        },
    ]);
}

function setChosenFileName(name) {
    if (fileNameLabel) fileNameLabel.textContent = name || "No file chosen";
}

function sourceLabel(doc) {
    const name = doc.filename || doc.url || doc.id;
    const kind = doc.source_type === "url" ? "URL" : "Document";
    return `${kind}: ${name} — ${doc.chunks ?? 0} chunks (${doc.status || "unknown"})`;
}

async function loadDocuments() {
    const res = await fetch("/api/knowledge/documents", { credentials: "include" });
    const docs = await res.json();
    const list = Array.isArray(docs) ? docs : [];
    documentList.replaceChildren();
    if (!list.length) {
        const empty = document.createElement("li");
        empty.textContent = "No knowledge sources yet.";
        documentList.appendChild(empty);
        return list;
    }
    for (const d of list) {
        const li = document.createElement("li");
        const main = document.createElement("div");
        main.className = "source-main";
        main.appendChild(d.source_type === "url" ? linkIcon() : fileIcon());
        const label = document.createElement("span");
        label.textContent = sourceLabel(d);
        main.appendChild(label);
        li.appendChild(main);

        const delBtn = document.createElement("button");
        delBtn.type = "button";
        delBtn.className = "source-delete";
        delBtn.textContent = "Delete";
        delBtn.dataset.id = d.id || "";
        delBtn.addEventListener("click", () => deleteSource(d));
        li.appendChild(delBtn);
        documentList.appendChild(li);
    }
    return list;
}

const confirmDialog = document.getElementById("confirm-dialog");
const confirmMessage = document.getElementById("confirm-message");
const confirmCancel = document.getElementById("confirm-cancel");
const confirmOk = document.getElementById("confirm-ok");
let pendingDelete = null;

function openConfirm(name) {
    if (confirmMessage) {
        confirmMessage.textContent = `Delete ${name}? This cannot be undone.`;
    }
    if (confirmDialog) confirmDialog.hidden = false;
}

function closeConfirm() {
    pendingDelete = null;
    if (confirmDialog) confirmDialog.hidden = true;
}

async function deleteSource(doc) {
    const name = doc.filename || doc.url || doc.id || "this source";
    if (!doc.id) {
        setUploadStatus("Could not delete source.", true);
        return;
    }
    pendingDelete = { id: doc.id, name };
    openConfirm(name);
}

async function confirmDelete() {
    const target = pendingDelete;
    closeConfirm();
    if (!target) return;
    setUploadStatus("Deleting source...");
    try {
        const res = await fetch(`/api/knowledge/documents/${encodeURIComponent(target.id)}`, {
            method: "DELETE",
            credentials: "include",
        });
        if (!res.ok) {
            setUploadStatus("Could not delete source.", true);
            return;
        }
        setUploadStatus(`Deleted ${target.name}.`);
        await refresh();
    } catch {
        setUploadStatus("Could not delete source.", true);
    }
}

function isHexColor(value) {
    return /^#[0-9a-fA-F]{6}$/.test(value || "");
}

async function loadSettings() {
    const res = await fetch("/api/admin/settings", { credentials: "include" });
    const settings = await res.json();
    chatbotNameInput.value = settings.chatbot_name || "";
    welcomeInput.value = settings.welcome_message || "";
    if (isHexColor(settings.primary_color)) {
        colorInput.value = settings.primary_color;
        colorTextInput.value = settings.primary_color;
    } else {
        colorInput.value = "#000000";
        colorTextInput.value = "";
    }
    logoInput.value = settings.logo_url || "";
    return settings;
}

async function refresh() {
    try {
        const [settings, docs] = await Promise.all([loadSettings(), loadDocuments()]);
        renderDashboard(settings, docs);
    } catch {
        renderDashboard({}, []);
    }
}

function setAuthUI(authenticated, username = "") {
    if (authPanel) authPanel.hidden = !!authenticated;
    if (adminDashboard) adminDashboard.hidden = !authenticated;
    if (adminUserLabel) {
        adminUserLabel.textContent = authenticated && username ? username : "";
    }
    if (authenticated && adminNewUsernameInput && username) {
        adminNewUsernameInput.value = username;
    }
}

async function checkAuthStatus() {
    try {
        const res = await fetch("/api/admin/auth-status", { credentials: "include" });
        if (!res.ok) return { authenticated: false, username: "" };
        const data = await res.json();
        return {
            authenticated: !!data.authenticated,
            username: data.username || "",
        };
    } catch {
        return { authenticated: false, username: "" };
    }
}

async function initAuth() {
    const { authenticated, username } = await checkAuthStatus();
    setAuthUI(authenticated, username);
    if (authenticated) {
        try {
            await refresh();
        } catch {
            /* keep dashboard visible even if refresh fails */
        }
    }
}

async function logoutAdmin() {
    try {
        await fetch("/api/admin/logout", { method: "POST", credentials: "include" });
    } catch {
        /* still show login on failure */
    }
    if (adminLoginForm) adminLoginForm.reset();
    if (recoverCredentialsForm) {
        recoverCredentialsForm.hidden = true;
        recoverCredentialsForm.reset();
    }
    if (toggleRecoverBtn) toggleRecoverBtn.setAttribute("aria-expanded", "false");
    if (adminLoginStatus) adminLoginStatus.textContent = "";
    setAuthUI(false);
}

if (adminLoginForm) {
    adminLoginForm.addEventListener("submit", async (e) => {
        e.preventDefault();
        if (!adminUsernameInput || !adminPasswordInput) return;
        if (!adminLoginStatus) return;

        adminLoginStatus.textContent = "";
        try {
            const res = await fetch("/api/admin/login", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                credentials: "include",
                body: JSON.stringify({
                    username: adminUsernameInput.value.trim(),
                    password: adminPasswordInput.value,
                }),
            });
            const data = await res.json().catch(() => ({}));
            if (!res.ok) {
                adminLoginStatus.textContent = data.detail || "Login failed.";
                adminLoginStatus.className = "upload-status error";
                return;
            }
            setAuthUI(true, data.username || adminUsernameInput.value.trim());
            adminLoginStatus.textContent = "";
            try {
                await refresh();
            } catch {
                /* dashboard already visible */
            }
        } catch {
            adminLoginStatus.textContent = "Login failed. Please try again.";
            adminLoginStatus.className = "upload-status error";
        }
    });
}

if (toggleRecoverBtn && recoverCredentialsForm) {
    toggleRecoverBtn.addEventListener("click", () => {
        const expanded = recoverCredentialsForm.hidden;
        recoverCredentialsForm.hidden = !expanded;
        toggleRecoverBtn.setAttribute("aria-expanded", expanded ? "true" : "false");
        if (expanded && recoverPasswordInput) {
            recoverPasswordInput.focus();
        }
    });
}

if (recoverCredentialsForm) {
    recoverCredentialsForm.addEventListener("submit", async (e) => {
        e.preventDefault();
        if (!recoverStatus) return;
        recoverStatus.textContent = "Saving new credentials...";
        recoverStatus.className = "upload-status";
        try {
            const res = await fetch("/api/admin/recover-credentials", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                credentials: "include",
                body: JSON.stringify({
                    recovery_password: recoverPasswordInput.value,
                    new_username: recoverNewUsernameInput.value.trim(),
                    new_password: recoverNewPasswordInput.value,
                }),
            });
            const data = await res.json().catch(() => ({}));
            if (!res.ok) {
                recoverStatus.textContent = data.detail || "Could not update credentials.";
                recoverStatus.className = "upload-status error";
                return;
            }
            recoverStatus.textContent = "Credentials saved.";
            recoverStatus.className = "upload-status success";
            recoverCredentialsForm.reset();
            recoverCredentialsForm.hidden = true;
            if (toggleRecoverBtn) toggleRecoverBtn.setAttribute("aria-expanded", "false");
            setAuthUI(true, data.username || recoverNewUsernameInput.value.trim());
            try {
                await refresh();
            } catch {
                /* dashboard already visible */
            }
        } catch {
            recoverStatus.textContent = "Update failed. Please try again.";
            recoverStatus.className = "upload-status error";
        }
    });
}

if (adminLogoutBtn) {
    adminLogoutBtn.addEventListener("click", logoutAdmin);
}

if (credentialsForm) {
    credentialsForm.addEventListener("submit", async (e) => {
        e.preventDefault();
        if (!credentialsStatus) return;
        try {
            credentialsStatus.textContent = "Updating credentials...";
            credentialsStatus.className = "upload-status";
            const res = await fetch("/api/admin/credentials", {
                method: "PUT",
                headers: { "Content-Type": "application/json" },
                credentials: "include",
                body: JSON.stringify({
                    current_password: adminCurrentPasswordInput.value,
                    new_username: adminNewUsernameInput.value.trim(),
                    new_password: adminNewPasswordInput.value,
                }),
            });
            const data = await res.json().catch(() => ({}));
            if (!res.ok) {
                credentialsStatus.textContent = data.detail || "Could not update.";
                credentialsStatus.className = "upload-status error";
                return;
            }
            credentialsForm.reset();
            await logoutAdmin();
            if (adminLoginStatus) {
                adminLoginStatus.textContent = "Credentials updated — please sign in again.";
                adminLoginStatus.className = "upload-status success";
            }
        } catch {
            credentialsStatus.textContent = "Update failed. Please try again.";
            credentialsStatus.className = "upload-status error";
        }
    });
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
        const res = await fetch("/api/knowledge/upload", { method: "POST", body: formData, credentials: "include" });
        const data = await res.json();

        if (!res.ok) {
            const detail = data.detail || "Upload failed.";
            setUploadStatus(typeof detail === "string" ? detail : "Upload failed.", true);
            return;
        }

        setUploadStatus(`Indexed ${data.filename}: ${data.chunks} chunks (${data.status}).`);
        fileInput.value = "";
        setChosenFileName("");
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
            credentials: "include",
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
        const res = await fetch("/api/admin/reindex", { method: "POST", credentials: "include" });
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
            credentials: "include",
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

fileInput.addEventListener("change", () => {
    setChosenFileName(fileInput.files[0] ? fileInput.files[0].name : "");
});

if (confirmCancel) confirmCancel.addEventListener("click", closeConfirm);
if (confirmOk) confirmOk.addEventListener("click", confirmDelete);
if (confirmDialog) {
    confirmDialog.addEventListener("click", (e) => {
        if (e.target.dataset.dialogClose !== undefined) closeConfirm();
    });
}
document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && confirmDialog && !confirmDialog.hidden) closeConfirm();
});

initAuth();

function embedSnippet(width, height) {
    const origin = window.location.origin;
    const w = (width || "380px").trim() || "380px";
    const h = (height || "640px").trim() || "640px";
    return (
        `<iframe src="${origin}/chat?embed=1" title="Chat" ` +
        `style="width:${w};height:${h};max-width:100%;border:0;border-radius:16px;"></iframe>`
    );
}

function refreshEmbedCode() {
    const code = document.getElementById("embed-code");
    const width = document.getElementById("embed-width");
    const height = document.getElementById("embed-height");
    if (!code) return;
    code.value = embedSnippet(width && width.value, height && height.value);
}

const embedWidth = document.getElementById("embed-width");
const embedHeight = document.getElementById("embed-height");
const copyEmbed = document.getElementById("copy-embed");
const embedStatus = document.getElementById("embed-status");

if (embedWidth) embedWidth.addEventListener("input", refreshEmbedCode);
if (embedHeight) embedHeight.addEventListener("input", refreshEmbedCode);
refreshEmbedCode();

if (copyEmbed) {
    copyEmbed.addEventListener("click", async () => {
        const code = document.getElementById("embed-code");
        if (!code) return;
        try {
            await navigator.clipboard.writeText(code.value);
            setStatus(embedStatus, "Embed code copied.");
        } catch {
            code.select();
            setStatus(embedStatus, "Select the code and copy it.", true);
        }
    });
}
