/** Admin UI client */

const uploadForm = document.getElementById("upload-form");
const fileInput = document.getElementById("file-input");
const documentList = document.getElementById("document-list");
const reindexBtn = document.getElementById("reindex-btn");
const uploadStatus = document.getElementById("upload-status");

function setUploadStatus(message, isError = false) {
    if (!uploadStatus) return;
    uploadStatus.textContent = message;
    uploadStatus.className = isError ? "upload-status error" : "upload-status success";
}

async function loadDocuments() {
    const res = await fetch("/api/knowledge/documents");
    const docs = await res.json();
    documentList.innerHTML = docs.length
        ? docs
              .map(
                  (d) =>
                      `<li>${d.filename || d.id} — ${d.chunks ?? 0} chunks (${d.status || "unknown"})</li>`
              )
              .join("")
        : "<li>No documents uploaded yet.</li>";
}

uploadForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const file = fileInput.files[0];
    if (!file) return;

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
        await loadDocuments();
    } catch {
        setUploadStatus("Upload failed. Please try again.", true);
    }
});

reindexBtn.addEventListener("click", async () => {
    setUploadStatus("Re-indexing all documents...");
    try {
        const res = await fetch("/api/admin/reindex", { method: "POST" });
        const data = await res.json();
        setUploadStatus(data.status === "reindex_complete" ? "Re-index complete." : "Re-index started.");
        await loadDocuments();
    } catch {
        setUploadStatus("Re-index failed.", true);
    }
});

loadDocuments();
