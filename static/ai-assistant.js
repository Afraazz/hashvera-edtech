(function () {
    const STORAGE_KEY = "hashvera-assistant-history-v2";
    const OPEN_KEY = "hashvera-assistant-open";

    function loadHistory() {
        try {
            return JSON.parse(localStorage.getItem(STORAGE_KEY) || "[]").slice(-8);
        } catch (error) {
            return [];
        }
    }

    function saveHistory(history) {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(history.slice(-8)));
    }

    function renderMarkdown(text) {
        if (!text) return "";
        // 1. Escape HTML first
        let html = text
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;");

        // 2. Code blocks: ```lang\ncode\n```
        html = html.replace(/```(?:[a-zA-Z0-9]+)?\n([\s\S]*?)\n```/g, (match, code) => {
            return `<pre style="background: rgba(0, 0, 0, 0.15); padding: 8px 10px; border-radius: 8px; margin: 8px 0; overflow-x: auto; font-family: monospace; font-size: 0.85em; border: 1px solid var(--line); white-space: pre;"><code>${code}</code></pre>`;
        });

        // 3. Inline code: `code`
        html = html.replace(/`([^`\n]+)`/g, '<code style="background: rgba(0, 0, 0, 0.1); padding: 2px 4px; border-radius: 4px; font-family: monospace; font-size: 0.9em;">$1</code>');

        // 4. Headers: ### header, ## header, # header
        html = html.replace(/^###\s+(.*)$/gm, '<h3 style="font-size: 1.05rem; font-weight: bold; margin: 8px 0 4px; color: var(--primary); font-family: inherit;">$1</h3>');
        html = html.replace(/^##\s+(.*)$/gm, '<h2 style="font-size: 1.12rem; font-weight: bold; margin: 10px 0 6px; color: var(--primary); font-family: inherit;">$1</h2>');
        html = html.replace(/^#\s+(.*)$/gm, '<h1 style="font-size: 1.2rem; font-weight: bold; margin: 12px 0 8px; color: var(--primary); font-family: inherit;">$1</h1>');

        // 5. Bold: **text**
        html = html.replace(/\*\*([\s\S]*?)\*\*/g, "<strong>$1</strong>");

        // 6. Italic: *text* or _text_
        html = html.replace(/\*([\s\S]*?)\*/g, "<em>$1</em>");
        html = html.replace(/_([\s\S]*?)_/g, "<em>$1</em>");

        // 7. Links: [text](url)
        html = html.replace(/\[([^\]]+)\]\(([^)]+)\)/g, (match, linkText, url) => {
            const isExternal = url.startsWith("http");
            return `<a href="${url}"${isExternal ? ' target="_blank" rel="noopener"' : ""} style="color: var(--primary); font-weight: bold; text-decoration: underline;">${linkText}</a>`;
        });

        // 8. Unordered Lists: lines starting with "- " or "* "
        const lines = html.split("\n");
        let inList = false;
        const processed = [];
        lines.forEach((line) => {
            const trimmed = line.trim();
            const listMatch = trimmed.match(/^[-*]\s+(.*)$/);
            if (listMatch) {
                if (!inList) {
                    processed.push('<ul style="margin: 6px 0; padding-left: 18px; list-style-type: disc;">');
                    inList = true;
                }
                processed.push(`<li style="margin: 4px 0;">${listMatch[1]}</li>`);
            } else {
                if (inList) {
                    processed.push("</ul>");
                    inList = false;
                }
                processed.push(line);
            }
        });
        if (inList) {
            processed.push("</ul>");
        }
        
        return processed.join("\n");
    }

    function createMessage(role, text, actions, isLoading = false) {
        const wrapper = document.createElement("div");
        wrapper.className = `ai-message ai-message-${role}`;

        const bubble = document.createElement("div");
        bubble.className = "ai-message-bubble";
        
        if (isLoading) {
            bubble.innerHTML = `
                <div class="typing-indicator">
                    <span></span>
                    <span></span>
                    <span></span>
                </div>
            `;
        } else {
            bubble.innerHTML = renderMarkdown(text);
        }
        wrapper.appendChild(bubble);

        if (actions && actions.length) {
            const actionRow = document.createElement("div");
            actionRow.className = "ai-message-actions";
            actions.forEach((action) => {
                const link = document.createElement("a");
                link.href = action.href;
                link.textContent = action.label;
                actionRow.appendChild(link);
            });
            wrapper.appendChild(actionRow);
        }

        return wrapper;
    }

    function bootAssistant() {
        const root = document.getElementById("ai-assistant");
        if (!root) {
            return;
        }

        const endpoint = root.dataset.endpoint;
        const toggle = document.getElementById("ai-assistant-toggle");
        const close = document.getElementById("ai-assistant-close");
        const clear = document.getElementById("ai-assistant-clear");
        const panel = document.getElementById("ai-assistant-panel");
        const aiThemeRoot = document.getElementById('ai-assistant-theme');

        // Synchronize assistant theme with HashVera data-theme or system preference
        function applyTheme() {
            if (!aiThemeRoot) return;
            const currentTheme = document.body.getAttribute('data-theme') || 
                                 (window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light');
            aiThemeRoot.setAttribute('data-theme', currentTheme);
        }

        // Apply immediately and listen for both system and HashVera theme toggle changes
        applyTheme();
        window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', applyTheme);
        const themeObserver = new MutationObserver((mutations) => {
            mutations.forEach((mutation) => {
                if (mutation.type === "attributes" && mutation.attributeName === "data-theme") {
                    applyTheme();
                }
            });
        });
        themeObserver.observe(document.body, { attributes: true, attributeFilter: ["data-theme"] });

        const messages = document.getElementById("ai-assistant-messages");
        const form = document.getElementById("ai-assistant-form");
        const input = document.getElementById("ai-assistant-input");
        const prompts = document.getElementById("ai-assistant-prompts");
        let history = loadHistory();
        let busy = false;

        const aiSection = document.getElementById("ai-assistant");
        const username = aiSection ? aiSection.getAttribute("data-user") : "";

        function renderHistory() {
            messages.innerHTML = "";
            if (!history.length) {
                let greeting = username 
                    ? `Hi ${username}, I am HashVera Assist. Ask me about verification, records, corrections, support, or ledger integrity.`
                    : "Hi, I am HashVera Assist. Ask me about verification, records, corrections, support, or ledger integrity.";
                messages.appendChild(createMessage(
                    "assistant",
                    greeting,
                    [{ label: "FAQ", href: "/faq" }, { label: "Verify", href: "/verify" }]
                ));
            }
            history.forEach((item) => {
                messages.appendChild(createMessage(item.role, item.text, item.actions));
            });
            messages.scrollTop = messages.scrollHeight;
        }

        function setOpen(isOpen) {
            panel.hidden = !isOpen;
            toggle.setAttribute("aria-expanded", String(isOpen));
            localStorage.setItem(OPEN_KEY, isOpen ? "1" : "0");
            if (isOpen) {
                window.setTimeout(() => input.focus(), 60);
            }
        }

        async function sendMessage(text) {
            if (busy || !text.trim()) {
                return;
            }
            busy = true;
            const cleanText = text.trim();
            input.value = "";

            history.push({ role: "user", text: cleanText });
            renderHistory();

            const loading = createMessage("assistant", "", null, true);
            loading.classList.add("ai-message-loading");
            messages.appendChild(loading);
            messages.scrollTop = messages.scrollHeight;

            try {
                const response = await fetch(endpoint, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ message: cleanText, history })
                });
                const data = await response.json();
                loading.remove();

                if (!response.ok || data.status !== "ok") {
                    throw new Error(data.message || "Assistant unavailable.");
                }

                history.push({ role: "assistant", text: data.answer, actions: data.actions || [] });
                saveHistory(history);
                renderHistory();
            } catch (error) {
                loading.remove();
                history.push({
                    role: "assistant",
                    text: "I could not reach the assistant service. Please try again or open Support.",
                    actions: [{ label: "Support", href: "/support" }]
                });
                saveHistory(history);
                renderHistory();
            } finally {
                busy = false;
            }
        }

        renderHistory();
        setOpen(localStorage.getItem(OPEN_KEY) === "1");

        toggle.addEventListener("click", () => setOpen(panel.hidden));
        close.addEventListener("click", () => setOpen(false));
        
        if (clear) {
            clear.addEventListener("click", () => {
                // If there's already a confirmation message showing, don't add another one
                if (messages.querySelector('.ai-clear-confirm')) return;

                const wrapper = document.createElement("div");
                wrapper.className = "ai-message ai-clear-confirm";
                
                const avatar = document.createElement("div");
                avatar.className = "ai-message-avatar";
                wrapper.appendChild(avatar);

                const content = document.createElement("div");
                content.className = "ai-message-content";
                content.innerHTML = "<p>Are you sure you want to clear your chat history?</p>";
                
                const actionRow = document.createElement("div");
                actionRow.className = "ai-message-actions";
                
                const btnYes = document.createElement("a");
                btnYes.href = "#";
                btnYes.className = "ai-btn-danger";
                btnYes.textContent = "Yes, clear it";
                btnYes.addEventListener("click", (e) => {
                    e.preventDefault();
                    history = [];
                    saveHistory(history);
                    renderHistory();
                });

                const btnNo = document.createElement("a");
                btnNo.href = "#";
                btnNo.textContent = "Cancel";
                btnNo.addEventListener("click", (e) => {
                    e.preventDefault();
                    wrapper.remove();
                });

                actionRow.appendChild(btnYes);
                actionRow.appendChild(btnNo);
                content.appendChild(actionRow);
                wrapper.appendChild(content);
                
                messages.appendChild(wrapper);
                messages.scrollTop = messages.scrollHeight;
            });
        }

        form.addEventListener("submit", (event) => {
            event.preventDefault();
            sendMessage(input.value);
        });
        input.addEventListener("input", () => {
            input.style.height = "auto";
            input.style.height = `${Math.min(input.scrollHeight, 96)}px`;
        });
        prompts.addEventListener("click", (event) => {
            const prompt = event.target.closest("[data-ai-prompt]");
            if (prompt) {
                sendMessage(prompt.dataset.aiPrompt || "");
            }
        });
    }

    document.addEventListener("DOMContentLoaded", bootAssistant);
})();
