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

function stockLabel(stock) {
    const raw = String(stock || "").trim();
    if (!raw) return "";
    const lower = raw.toLowerCase();
    if (lower === "0" || lower === "out of stock" || lower === "oos") {
        return { text: "Out of stock", inStock: false };
    }
    const digits = raw.replace(/[^\d]/g, "");
    if (digits) {
        return { text: `In stock (${digits} pcs)`, inStock: true };
    }
    return { text: raw, inStock: true };
}

function appendDetailRow(parent, icon, label, value, valueClass, options = {}) {
    if (!value) return;
    const row = document.createElement("div");
    row.className = "product-card-row";
    const iconEl = document.createElement("span");
    iconEl.className = "product-card-icon";
    iconEl.setAttribute("aria-hidden", "true");
    iconEl.textContent = icon;

    const textWrap = document.createElement("span");
    textWrap.className = "product-card-text";

    const labelEl = document.createElement("span");
    labelEl.className = "product-card-label";
    labelEl.textContent = `${label}: `;
    textWrap.appendChild(labelEl);

    if (options.swatchColor) {
        const swatch = document.createElement("span");
        swatch.className = "product-color-swatch";
        swatch.style.backgroundColor = options.swatchColor;
        swatch.setAttribute("aria-hidden", "true");
        textWrap.appendChild(swatch);
    }

    const valueEl = document.createElement("span");
    valueEl.className = valueClass || "product-card-value";
    valueEl.textContent = value;
    textWrap.appendChild(valueEl);

    row.appendChild(iconEl);
    row.appendChild(textWrap);
    parent.appendChild(row);
}

function colorSwatchFromName(name) {
    const raw = String(name || "").toLowerCase();
    const map = {
        grey: "#9CA3AF",
        gray: "#9CA3AF",
        black: "#111111",
        white: "#F3F4F6",
        beige: "#D4B896",
        brown: "#8B5E3C",
        red: "#DC2626",
        blue: "#2563EB",
        green: "#16A34A",
        yellow: "#EAB308",
        orange: "#EA580C",
        pink: "#EC4899",
        purple: "#9333EA",
        navy: "#1E3A8A",
        cream: "#F5F0E6",
        canvas: "#C4A882",
    };
    for (const [key, hex] of Object.entries(map)) {
        if (raw.includes(key)) return hex;
    }
    return "#D1D5DB";
}

function renderProductCard(product) {
    const card = document.createElement("article");
    card.className = "product-card";
    if (product.best_value) card.classList.add("is-best-value");

    if (product.best_value) {
        const badge = document.createElement("div");
        badge.className = "product-badge best-value";
        badge.textContent = "Best Value";
        card.appendChild(badge);
    }

    if (product.subcategory || product.category) {
        const meta = document.createElement("div");
        meta.className = "product-card-meta";
        if (product.subcategory) {
            const sub = document.createElement("span");
            sub.className = "product-chip subcategory";
            sub.textContent = product.subcategory;
            meta.appendChild(sub);
        } else if (product.category) {
            const cat = document.createElement("span");
            cat.className = "product-chip category";
            cat.textContent = product.category;
            meta.appendChild(cat);
        }
        card.appendChild(meta);
    }

    const title = document.createElement("h4");
    title.className = "product-card-title";
    title.textContent = product.name || "Product";
    card.appendChild(title);

    if (product.color) {
        appendDetailRow(card, "◉", "Color", product.color, "product-color-value", {
            swatchColor: colorSwatchFromName(product.color),
        });
    }
    appendDetailRow(card, "▣", "Size", product.size, "product-size-value");
    appendDetailRow(card, "₨", "Price", product.price, "product-price");

    if (product.discount) {
        const discount = document.createElement("div");
        discount.className = "product-discount";
        const tag = document.createElement("span");
        tag.className = "product-discount-tag";
        tag.textContent = product.discount;
        discount.appendChild(tag);
        card.appendChild(discount);
    }

    const stock = stockLabel(product.stock);
    if (stock) {
        const stockRow = document.createElement("div");
        stockRow.className = `product-stock ${stock.inStock ? "in-stock" : "out-stock"}`;
        const dot = document.createElement("span");
        dot.className = "product-stock-dot";
        stockRow.appendChild(dot);
        const label = document.createElement("span");
        label.textContent = stock.text;
        stockRow.appendChild(label);
        card.appendChild(stockRow);
    }

    return card;
}

function renderProductUi(stack, ui) {
    if (!stack || !ui || !ui.layout) return;

    const existing = stack.querySelector(".product-ui");
    if (existing) existing.remove();

    const wrap = document.createElement("div");
    wrap.className = `product-ui product-ui-${ui.layout}`;

    const products = Array.isArray(ui.products) ? ui.products : [];
    const grid = document.createElement("div");
    grid.className = ui.layout === "product_compare" ? "product-compare-grid" : "product-card-grid";
    products.forEach((product) => {
        grid.appendChild(renderProductCard(product));
    });
    wrap.appendChild(grid);

    if (ui.layout === "product_compare" && Array.isArray(ui.features) && ui.features.length) {
        const section = document.createElement("div");
        section.className = "product-compare-table-wrap";

        const heading = document.createElement("h4");
        heading.className = "product-compare-heading";
        heading.textContent = "Quick compare";
        section.appendChild(heading);

        const table = document.createElement("table");
        table.className = "product-compare-table";

        const thead = document.createElement("thead");
        const headRow = document.createElement("tr");
        const featureTh = document.createElement("th");
        featureTh.textContent = "Feature";
        headRow.appendChild(featureTh);
        products.forEach((product) => {
            const th = document.createElement("th");
            th.textContent = product.name || "Product";
            headRow.appendChild(th);
        });
        thead.appendChild(headRow);
        table.appendChild(thead);

        const tbody = document.createElement("tbody");
        ui.features.forEach((feature) => {
            const tr = document.createElement("tr");
            const labelTd = document.createElement("td");
            labelTd.className = "product-compare-feature";
            labelTd.textContent = feature.label || "";
            tr.appendChild(labelTd);
            const rowClass = {
                Color: "compare-color",
                Price: "compare-price",
                Discount: "compare-discount",
                Stock: "compare-stock",
            }[feature.label || ""];
            (feature.values || []).forEach((value) => {
                const td = document.createElement("td");
                if (rowClass) td.classList.add(rowClass);
                if (feature.label === "Color" && value) {
                    const wrap = document.createElement("span");
                    wrap.className = "product-compare-color-cell";
                    const swatch = document.createElement("span");
                    swatch.className = "product-color-swatch";
                    swatch.style.backgroundColor = colorSwatchFromName(value);
                    swatch.setAttribute("aria-hidden", "true");
                    wrap.appendChild(swatch);
                    const text = document.createElement("span");
                    text.textContent = value;
                    wrap.appendChild(text);
                    td.appendChild(wrap);
                } else {
                    td.textContent = value || "—";
                }
                tr.appendChild(td);
            });
            tbody.appendChild(tr);
        });
        table.appendChild(tbody);
        section.appendChild(table);
        wrap.appendChild(section);
    }

    if (ui.tip) {
        const tip = document.createElement("div");
        tip.className = "product-tip";
        const tipLabel = document.createElement("strong");
        tipLabel.textContent = "Not sure? ";
        tip.appendChild(tipLabel);
        tip.appendChild(document.createTextNode(String(ui.tip).replace(/^Not sure\?\s*/i, "")));
        wrap.appendChild(tip);
    }

    const meta = stack.querySelector(".msg-meta");
    if (meta) {
        stack.insertBefore(wrap, meta);
    } else {
        stack.appendChild(wrap);
    }
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

async function requestJsonChat(message) {
    const res = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message, session_id: sessionId }),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
        const err = new Error(data.detail || "chat failed");
        err.status = res.status;
        throw err;
    }
    if (data.session_id) sessionId = data.session_id;
    return { text: data.reply || "", ui: data.ui || null };
}

function failMessage(err) {
    const status = err && err.status;
    if (status === 504 || status === 408) {
        return "The assistant took too long to answer. Please try again in a moment.";
    }
    return "Sorry, something went wrong. Please try again.";
}

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
    let ui = null;

    try {
        const res = await fetch("/api/chat/stream", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ message, session_id: sessionId }),
        });
        if (!res.ok || !res.body) {
            const err = new Error("stream failed");
            err.status = res.status;
            throw err;
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
            if (event.type === "done" && event.ui) {
                ui = event.ui;
            }
            if (event.type === "error") {
                if (!bubble) {
                    hideTyping();
                    bubble = startAssistantMessage();
                }
                fullText = event.text || failMessage();
                updateAssistantMessage(bubble, fullText);
            }
        });
        if (!fullText) {
            const fallback = await requestJsonChat(message);
            fullText = fallback.text;
            ui = fallback.ui;
        }
        hideTyping();
        if (!bubble) bubble = startAssistantMessage();
        if (fullText) updateAssistantMessage(bubble, fullText);
        if (ui && bubble) {
            const stack = bubble.closest(".msg-stack");
            renderProductUi(stack, ui);
        }
        if (!fullText) updateAssistantMessage(bubble, failMessage());
        if (bubble) bubble.classList.remove("is-streaming");
    } catch (err) {
        hideTyping();
        const text = failMessage(err);
        if (!bubble) appendMessage("assistant", text);
        else updateAssistantMessage(bubble, text);
    } finally {
        if (loadingIndicator) loadingIndicator.classList.remove("active");
        if (sendButton) sendButton.disabled = false;
        if (input) input.focus();
    }
});
