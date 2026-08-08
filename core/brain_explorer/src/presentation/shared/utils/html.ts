/**
 * @author Yoel David <yoeldcd@gmail.com>
 * @see https://x.com/SAY6267
 * @version: 1.0.0
 *
 * Small DOM helpers for safe Brain Explorer rendering.
 */

/**
 * Escape text before placing it inside HTML templates.
 *
 * @param {unknown} value Raw value to escape.
 * @returns {string} HTML-safe text.
 */
export function escapeHtml(value: unknown): string {
    return String(value ?? "")
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#39;");
}

/**
 * Render JSON values with stable indentation.
 *
 * @param {unknown} value Value to render.
 * @returns {string} Pretty JSON or text fallback.
 */
export function prettyJson(value: unknown): string {
    if (value === undefined || value === null || value === "") {
        return "";
    }
    if (typeof value === "string") {
        return value;
    }
    try {
        return JSON.stringify(value, null, 2);
    } catch (_error) {
        return String(value);
    }
}

/**
 * Render code inside a Prism-compatible code block.
 *
 * @param {unknown} value Code or structured data.
 * @param {string} language Prism language id.
 * @returns {string} HTML code block.
 */
export function codeBlock(value: unknown, language = "text"): string {
    const text = typeof value === "string" ? value : prettyJson(value);
    const safeLanguage = language.replace(/[^a-z0-9_-]/gi, "") || "text";
    return `<pre class="code-block language-${safeLanguage}"><code class="language-${safeLanguage}">${highlightCode(text, safeLanguage)}</code></pre>`;
}

/**
 * Render safe enriched Markdown plus Brain's narrative-closure syntax.
 *
 * @param {string} markdown Markdown source.
 * @returns {string} Rendered HTML.
 */
export function renderMarkdown(markdown: string): string {
    const trimmed = String(markdown || "").trim();
    if (isJsonDocument(trimmed)) {
        return `<div class="rich-markdown">${codeBlock(trimmed, "json")}</div>`;
    }
    if (trimmed.startsWith("#!") || trimmed.startsWith("import sys") || trimmed.startsWith("def main():")) {
        const lang = trimmed.includes("python") || trimmed.includes("py") || trimmed.startsWith("import sys") || trimmed.startsWith("def main():") ? "python" : "bash";
        return `<div class="rich-markdown">${codeBlock(trimmed, lang)}</div>`;
    }
    const firstLines = trimmed.split(/\n/).slice(0, 10);
    const logMatchCount = firstLines.filter(line => 
        line.match(/^\[(INFO|ERROR|WARNING|SUCCESS|WARN|FAIL|FATAL|OK)\]/i) || 
        line.match(/^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}/)
    ).length;
    if (logMatchCount >= 2 || (firstLines.length > 0 && logMatchCount === firstLines.length)) {
        return `<div class="rich-markdown">${codeBlock(trimmed, "log")}</div>`;
    }
    const lines = normalizeInlineLists(String(markdown || "")).split(/\r?\n/);
    return `<div class="rich-markdown">${renderMarkdownBlocks(lines)}</div>`;
}

/**
 * Determine whether a complete source string is valid JSON.
 * @param {string} value Candidate document.
 * @returns {boolean} True only for parsed JSON objects or arrays.
 */
function isJsonDocument(value: string): boolean {
    if (!(value.startsWith("{") || value.startsWith("["))) return false;
    try {
        const parsed: unknown = JSON.parse(value);
        return typeof parsed === "object" && parsed !== null;
    } catch {
        return false;
    }
}

/**
 * Recover ordered or unordered lists whose line breaks were flattened in storage.
 * @param {string} source Original Markdown source.
 * @returns {string} Source with unambiguous inline list markers restored to lines.
 */
function normalizeInlineLists(source: string): string {
    return source.split(/\r?\n/).map(line => {
        if (/^\s*1\.\s+/.test(line) && (line.match(/\s+\d+\.\s+/g)?.length ?? 0) > 0) {
            return line.replace(/\s+(?=\d+\.\s+)/g, "\n");
        }
        if (/^\s*[-*+]\s+/.test(line) && (line.match(/\s+[-*+]\s+/g)?.length ?? 0) > 0) {
            return line.replace(/\s+(?=[-*+]\s+)/g, "\n");
        }
        return line;
    }).join("\n");
}

/**
 * Parse block-level Markdown constructs without permitting raw HTML.
 * @param {string[]} lines Normalized source lines.
 * @returns {string} Safe block HTML.
 */
function renderMarkdownBlocks(lines: string[]): string {
    const html: string[] = [];
    let index = 0;
    while (index < lines.length) {
        const line = lines[index] ?? "";
        if (!line.trim()) {
            index += 1;
            continue;
        }
        const fence = line.match(/^\s*```([a-z0-9_-]+)?\s*$/i);
        if (fence) {
            const codeLines: string[] = [];
            index += 1;
            while (index < lines.length && !/^\s*```\s*$/.test(lines[index] ?? "")) {
                codeLines.push(lines[index] ?? "");
                index += 1;
            }
            if (index < lines.length) index += 1;
            html.push(codeBlock(codeLines.join("\n"), fence[1] ?? "markdown"));
            continue;
        }
        const heading = line.match(/^\s*(#{1,6})\s+(.+?)\s*#*\s*$/);
        if (heading) {
            const level = heading[1]?.length ?? 1;
            html.push(`<h${level}>${inlineMarkdown(heading[2] ?? "")}</h${level}>`);
            index += 1;
            continue;
        }
        if (/^\s{0,3}([-*_])(?:\s*\1){2,}\s*$/.test(line)) {
            html.push("<hr>");
            index += 1;
            continue;
        }
        if (isTableHeader(lines, index)) {
            const headerCells = tableCells(line);
            const bodyRows: string[][] = [];
            index += 2;
            while (index < lines.length && (lines[index] ?? "").includes("|")) {
                bodyRows.push(tableCells(lines[index] ?? ""));
                index += 1;
            }
            html.push(renderTable(headerCells, bodyRows));
            continue;
        }
        if (/^\s*>\s?/.test(line)) {
            const quoteLines: string[] = [];
            while (index < lines.length && /^\s*>\s?/.test(lines[index] ?? "")) {
                quoteLines.push((lines[index] ?? "").replace(/^\s*>\s?/, ""));
                index += 1;
            }
            html.push(`<blockquote>${renderMarkdownBlocks(quoteLines)}</blockquote>`);
            continue;
        }
        const listMatch = listItem(line);
        if (listMatch) {
            const items: string[] = [];
            const ordered = listMatch.ordered;
            const start = listMatch.start;
            while (index < lines.length) {
                const item = listItem(lines[index] ?? "");
                if (!item || item.ordered !== ordered) break;
                const task = item.content.match(/^\[([ xX])\]\s+(.+)$/);
                items.push(task
                    ? `<li class="task-list-item"><input type="checkbox" disabled ${task[1]?.toLowerCase() === "x" ? "checked" : ""}>${inlineMarkdown(task[2] ?? "")}</li>`
                    : `<li>${inlineMarkdown(item.content)}</li>`);
                index += 1;
            }
            const tag = ordered ? "ol" : "ul";
            const startAttribute = ordered && start !== 1 ? ` start="${start}"` : "";
            html.push(`<${tag}${startAttribute}>${items.join("")}</${tag}>`);
            continue;
        }
        const paragraph: string[] = [];
        while (index < lines.length && (lines[index] ?? "").trim() && !startsMarkdownBlock(lines, index)) {
            paragraph.push((lines[index] ?? "").trim());
            index += 1;
        }
        if (!paragraph.length) {
            paragraph.push(line.trim());
            index += 1;
        }
        html.push(`<p>${inlineMarkdown(paragraph.join(" "))}</p>`);
    }
    return html.join("");
}

/**
 * Determine whether a source position begins a non-paragraph block.
 * @param {string[]} lines Complete Markdown source lines.
 * @param {number} index Candidate line position.
 * @returns {boolean} Whether a block construct begins at the position.
 */
function startsMarkdownBlock(lines: string[], index: number): boolean {
    const line = lines[index] ?? "";
    return /^\s*```/.test(line)
        || /^\s*#{1,6}\s+/.test(line)
        || /^\s*>\s?/.test(line)
        || /^\s*(?:[-*+]\s+|\d+[.)]\s+)/.test(line)
        || /^\s{0,3}([-*_])(?:\s*\1){2,}\s*$/.test(line)
        || isTableHeader(lines, index);
}

/**
 * Parse one ordered or unordered list marker.
 * @param {string} line Candidate Markdown line.
 * @returns {MarkdownListItem | null} Parsed item or null.
 */
function listItem(line: string): MarkdownListItem | null {
    const match = line.match(/^\s*(?:(\d+)[.)]|[-*+])\s+(.+)$/);
    if (!match) return null;
    return { ordered: Boolean(match[1]), start: Number(match[1] ?? 1), content: match[2] ?? "" };
}

/**
 * Parsed list-marker contract used by block rendering.
 */
interface MarkdownListItem {
    /**
     * Whether the source marker is numeric.
     * @type {boolean}
     */
    ordered: boolean;
    /**
     * Numeric starting position, or one for unordered items.
     * @type {number}
     */
    start: number;
    /**
     * Markdown source following the marker.
     * @type {string}
     */
    content: string;
}

/**
 * Determine whether two source lines form a GitHub-style table header.
 * @param {string[]} lines Complete Markdown source lines.
 * @param {number} index Candidate header position.
 * @returns {boolean} Whether the lines begin a table.
 */
function isTableHeader(lines: string[], index: number): boolean {
    const header = lines[index] ?? "";
    const delimiter = lines[index + 1] ?? "";
    return header.includes("|") && /^\s*\|?\s*:?-{3,}:?\s*(?:\|\s*:?-{3,}:?\s*)+\|?\s*$/.test(delimiter);
}

/**
 * Split one pipe-delimited table row into trimmed cells.
 * @param {string} line Pipe-delimited Markdown row.
 * @returns {string[]} Trimmed table cells.
 */
function tableCells(line: string): string[] {
    return line.trim().replace(/^\|/, "").replace(/\|$/, "").split("|").map(cell => cell.trim());
}

/**
 * Render one safe responsive Markdown table.
 * @param {string[]} headers Header cell sources.
 * @param {string[][]} rows Body row sources.
 * @returns {string} Safe responsive table HTML.
 */
function renderTable(headers: string[], rows: string[][]): string {
    const head = headers.map(cell => `<th>${inlineMarkdown(cell)}</th>`).join("");
    const body = rows.map(row => `<tr>${row.map(cell => `<td>${inlineMarkdown(cell)}</td>`).join("")}</tr>`).join("");
    return `<div class="rich-table-scroll"><table><thead><tr>${head}</tr></thead><tbody>${body}</tbody></table></div>`;
}

/**
 * Convert a path-like value into a compact display label.
 *
 * @param {string} value Full path-like value.
 * @returns {string} Last path segment or the original value.
 */
/**
 * Highlight visible text fragments without replacing their owning interactive elements.
 *
 * @param {ParentNode} root Mounted layout root.
 * @param {string} query Current reactive query.
 * @param {string} itemSelector Selector resolving searchable visible items.
 */
export function highlightRenderedContent(root: ParentNode, query: string, itemSelector: string): void {
    const parents = new Set<Node>();
    root.querySelectorAll<HTMLElement>("mark[data-reactive-search-match]").forEach(mark => {
        const parent = mark.parentNode;
        if (parent) parents.add(parent);
        mark.replaceWith(document.createTextNode(mark.textContent || ""));
    });
    parents.forEach(parent => parent.normalize());
    const needle = query.trim().toLocaleLowerCase();
    if (!needle) return;
    root.querySelectorAll<HTMLElement>(itemSelector).forEach(item => {
        const walker = document.createTreeWalker(item, NodeFilter.SHOW_TEXT);
        const textNodes: Text[] = [];
        let current = walker.nextNode();
        while (current) {
            const parent = current.parentElement;
            if (current instanceof Text && parent && !parent.closest("script, style, textarea, input, mark, [data-reactive-highlight-ignore]")) {
                textNodes.push(current);
            }
            current = walker.nextNode();
        }
        textNodes.forEach(textNode => {
            const source = textNode.data;
            const normalized = source.toLocaleLowerCase();
            let cursor = 0;
            let matchIndex = normalized.indexOf(needle);
            if (matchIndex < 0) return;
            const fragment = document.createDocumentFragment();
            while (matchIndex >= 0) {
                fragment.append(source.slice(cursor, matchIndex));
                const mark = document.createElement("mark");
                mark.dataset.reactiveSearchMatch = "";
                mark.className = "reactive-search-match";
                mark.textContent = source.slice(matchIndex, matchIndex + needle.length);
                fragment.append(mark);
                cursor = matchIndex + needle.length;
                matchIndex = normalized.indexOf(needle, cursor);
            }
            fragment.append(source.slice(cursor));
            textNode.replaceWith(fragment);
        });
    });
}

export function filterRenderedContent(root: ParentNode, query: string, itemSelector: string, containerSelector: string): void {
    const needle = query.trim().toLocaleLowerCase();
    const items = Array.from(root.querySelectorAll<HTMLElement>(itemSelector));
    let visible = 0;
    items.forEach(item => {
        const content = `${item.textContent || ""} ${item.dataset.reactiveContent || ""}`.toLocaleLowerCase();
        const matches = !needle || content.includes(needle);
        item.hidden = !matches;
        if (matches) visible += 1;
    });
    highlightRenderedContent(root, query, `${itemSelector}:not([hidden])`);
    root.querySelector("[data-role='reactive-content-empty']")?.remove();
    const container = root.querySelector(containerSelector);
    if (needle && items.length && !visible && container) {
        const empty = document.createElement("p");
        empty.className = "empty-state";
        empty.dataset.role = "reactive-content-empty";
        empty.textContent = "No items match your filter.";
        container.append(empty);
    }
}

export function compactLabel(value: string): string {
    const text = String(value || "");
    const parts = text.split(".");
    return parts[parts.length - 1] || text;
}

/**
 * Create an HTML option list from strings.
 *
 * @param {string[]} values Option values.
 * @param {string} selected Selected value.
 * @returns {string} HTML option tags.
 */
export function optionTags(values: string[], selected: string): string {
    return values
        .map(value => `<option value="${escapeHtml(value)}" ${value === selected ? "selected" : ""}>${escapeHtml(value)}</option>`)
        .join("");
}

/**
 * Apply deterministic token spans to an already identified fenced-code language.
 *
 * @param {unknown} value Unknown code body normalized and escaped before highlighting.
 * @param {string} language Fence language identifier selecting the safe token rules.
 * @returns {string} Escaped HTML containing presentation-only token spans.
 */
function highlightCode(value: unknown, language: string): string {
    const escaped = escapeHtml(value);
    const lang = String(language || "").toLowerCase();
    if (lang === "json" || lang === "javascript" || lang === "js" || lang === "typescript" || lang === "ts") {
        return escaped
            .replace(/(&quot;[^&]*?&quot;)(\s*:)?/g, (_match, stringValue, colon) => colon ? `<span class="token property">${stringValue}</span>${colon}` : `<span class="token string">${stringValue}</span>`)
            .replace(/\b(true|false|null)\b/g, `<span class="token boolean">$1</span>`)
            .replace(/\b(-?\d+(?:\.\d+)?)\b/g, `<span class="token number">$1</span>`)
            .replace(/\b(const|let|var|function|class|return|import|export|from|extends|super|new|this|typeof|async|await|if|else|for|while|do|switch|case|break|continue|default|try|catch|finally|throw)\b/g, `<span class="token keyword">$1</span>`);
    }
    if (lang === "python" || lang === "py") {
        return escaped
            .replace(/(&quot;&quot;&quot;[\s\S]*?&quot;&quot;&quot;|&#39;&#39;&#39;[\s\S]*?&#39;&#39;&#39;|&quot;[^&]*?&quot;|&#39;[^&]*?&#39;)/g, `<span class="token string">$1</span>`)
            .replace(/\b(True|False|None)\b/g, `<span class="token boolean">$1</span>`)
            .replace(/\b(-?\d+(?:\.\d+)?)\b/g, `<span class="token number">$1</span>`)
            .replace(/\b(def|class|return|import|from|as|global|nonlocal|lambda|yield|if|elif|else|for|while|break|continue|try|except|finally|raise|assert|with|pass|in|is|not|and|or)\b/g, `<span class="token keyword">$1</span>`);
    }
    if (lang === "bash" || lang === "shell" || lang === "powershell") {
        return escaped
            .replace(/(^|\n)(#.*)/g, `$1<span class="token comment">$2</span>`)
            .replace(/(&quot;.*?&quot;|'.*?')/g, `<span class="token string">$1</span>`)
            .replace(/\b(if|then|elif|else|fi|for|in|do|done|while|break|continue|return|function|exit)\b/g, `<span class="token keyword">$1</span>`);
    }
    if (lang === "log") {
        return escaped
            .replace(/(\[INFO\])/gi, `<span class="token info">$1</span>`)
            .replace(/(\[ERROR\]|\[FAIL\]|\[FATAL\])/gi, `<span class="token error">$1</span>`)
            .replace(/(\[WARNING\]|\[WARN\])/gi, `<span class="token warning">$1</span>`)
            .replace(/(\[SUCCESS\]|\[OK\])/gi, `<span class="token success">$1</span>`)
            .replace(/(\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2})/g, `<span class="token timestamp">$1</span>`);
    }
    return escaped;
}

/**
 * Render safe inline Markdown and Brain narrative closures.
 *
 * @param {string} value Plain source text from a paragraph, list item, or heading.
 * @returns {string} Escaped HTML with code, strong, and emphasis spans.
 */
function inlineMarkdown(value: string): string {
    const protectedTokens: string[] = [];
    const protect = (html: string): string => {
        const token = `\u0000${protectedTokens.length}\u0000`;
        protectedTokens.push(html);
        return token;
    };
    let source = String(value || "")
        .replace(/`([^`]+)`/g, (_match, code) => protect(renderStandaloneClosure(code) || `<code>${escapeHtml(code)}</code>`))
        .replace(/!\s*\[([^\]]*)\]\(\s*(?:<([^>\n]+)>|([^\s)]+))(?:\s+["']([^"']*)["'])?\s*\)/g, (_match, alt, enclosedTarget, bareTarget, title) => {
            const safeTarget = safeMarkdownImageUrl(enclosedTarget || bareTarget || "");
            if (!safeTarget) return _match;
            const titleAttribute = title ? ` title="${escapeHtml(title)}"` : "";
            return protect(`<img src="${escapeHtml(safeTarget)}" alt="${escapeHtml(alt)}"${titleAttribute} loading="lazy">`);
        })
        .replace(/\[([^\]]+)\]\(([^\s)]+)(?:\s+["']([^"']*)["'])?\)/g, (_match, label, target, title) => {
            const safeTarget = safeMarkdownUrl(target);
            if (!safeTarget) return _match;
            const titleAttribute = title ? ` title="${escapeHtml(title)}"` : "";
            return protect(`<a href="${escapeHtml(safeTarget)}"${titleAttribute} target="_blank" rel="noopener noreferrer">${escapeHtml(label)}</a>`);
        })
        .replace(/<(https?:\/\/[^\s>]+)>/g, (_match, target) => protect(`<a href="${escapeHtml(target)}" target="_blank" rel="noopener noreferrer">${escapeHtml(target)}</a>`));
    source = escapeHtml(source)
        .replace(/\[([^\]\n]+)\]/g, (_match, content) => narrativeClosureMarkup("square", "[", content, "]"))
        .replace(/\(([^)\n]+)\)/g, (_match, content) => narrativeClosureMarkup("round", "(", content, ")"))
        .replace(/\{([^}\n]+)\}/g, (_match, content) => narrativeClosureMarkup("curly", "{", content, "}"))
        .replace(/~~([^~]+)~~/g, `<del>$1</del>`)
        .replace(/\*\*([^*]+)\*\*/g, `<strong>$1</strong>`)
        .replace(/__([^_]+)__/g, `<strong>$1</strong>`)
        .replace(/\*([^*]+)\*/g, `<em>$1</em>`)
        .replace(/_([^_]+)_/g, `<em>$1</em>`);
    return source.replace(/\u0000(\d+)\u0000/g, (_match, index) => protectedTokens[Number(index)] ?? "");
}

/**
 * Render one code-span as narrative syntax when its complete value is a closure.
 * @param {string} value Complete code-span source.
 * @returns {string} Narrative markup or an empty string.
 */
function renderStandaloneClosure(value: string): string {
    const match = String(value || "").match(/^(?:\[([^\]\n]+)\]|\(([^)\n]+)\)|\{([^}\n]+)\})$/);
    if (!match) return "";
    if (match[1] !== undefined) return narrativeClosureMarkup("square", "[", escapeHtml(match[1]), "]");
    if (match[2] !== undefined) return narrativeClosureMarkup("round", "(", escapeHtml(match[2]), ")");
    return narrativeClosureMarkup("curly", "{", escapeHtml(match[3] ?? ""), "}");
}

/**
 * Compose visible delimiters and emphasized closure content without permitting HTML.
 * @param {"square" | "round" | "curly"} kind Closure presentation kind.
 * @param {string} open Opening delimiter.
 * @param {string} content Escaped inner content.
 * @param {string} close Closing delimiter.
 * @returns {string} Safe closure markup.
 */
function narrativeClosureMarkup(kind: "square" | "round" | "curly", open: string, content: string, close: string): string {
    return `<span class="narrative-closure narrative-${kind}"><span class="narrative-delimiter">${open}</span><span class="narrative-content">${content}</span><span class="narrative-delimiter">${close}</span></span>`;
}

/**
 * Accept only navigation-safe Markdown URL schemes.
 * @param {string} value Raw link or image target.
 * @returns {string} Safe target, or an empty string when rejected.
 */
function safeMarkdownUrl(value: string): string {
    const target = String(value || "").trim();
    return /^(?:https?:\/\/|mailto:|\/|#)/i.test(target) ? target : "";
}

/**
 * Resolve a Markdown image target to a browser-safe URL.
 *
 * @param {string} value Raw Markdown image target.
 * @returns {string} Browser-safe image URL, or an empty string when rejected.
 */
function safeMarkdownImageUrl(value: string): string {
    const target = String(value || "").trim();
    const isWorkspaceRelativePath = /^(?:\.\/)?\$agent\//i.test(target);
    const isFileUrl = /^file:\/\/\//i.test(target);
    const isWindowsAbsolutePath = /^[a-zA-Z]:[\\/]/.test(target);
    if (isWorkspaceRelativePath || isFileUrl || isWindowsAbsolutePath) {
        return workspaceScopedUrl(`/api/workspace/image?path=${encodeURIComponent(target)}`);
    }

    const isBase64Image = /^data:image\/(?:gif|jpe?g|png|webp);base64,[a-z0-9+/=]+$/i.test(target);
    if (isBase64Image) {
        return target;
    }

    const isBlobImage = /^blob:[^\s]+$/i.test(target);
    if (isBlobImage) {
        return target;
    }

    const isDirectImageUrl = /^(?:https?:\/\/|\/|#)/i.test(target);
    return isDirectImageUrl ? target : "";
}

/**
 * Add the selected consumer workspace to a browser-loaded resource URL.
 *
 * Native image requests cannot carry the API client's `X-Workspace-Root` header,
 * so the validated workspace is transported as a query parameter instead.
 *
 * @param {string} path Same-origin resource path.
 * @returns {string} Workspace-scoped resource URL.
 */
export function workspaceScopedUrl(path: string): string {
    const workspaceRoot = globalThis.localStorage?.getItem("active_project_path")?.trim();
    if (!workspaceRoot) return path;
    const separator = path.includes("?") ? "&" : "?";
    return `${path}${separator}workspaceRoot=${encodeURIComponent(workspaceRoot)}`;
}
