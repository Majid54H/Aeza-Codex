/** Admin UI client */

const uploadForm = document.getElementById("upload-form");
const fileInput = document.getElementById("file-input");
const documentList = document.getElementById("document-list");
const reindexBtn = document.getElementById("reindex-btn");

async function loadDocuments() {
    const res = await fetch("/api/knowledge/documents");
    const docs = await res.json();
    documentList.innerHTML = docs
        .map((d) => `<li>${d.filename || d.id} — ${d.chunks ?? 0} chunks</li>`)
        .join("");
}

uploadForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const file = fileInput.files[0];
    if (!file) return;

    const formData = new FormData();
    formData.append("file", file);

    await fetch("/api/knowledge/ingest", { method: "POST", body: formData });
    fileInput.value = "";
    await loadDocuments();
});

reindexBtn.addEventListener("click", async () => {
    await fetch("/api/admin/reindex", { method: "POST" });
    alert("Re-index started.");
});

loadDocuments();
