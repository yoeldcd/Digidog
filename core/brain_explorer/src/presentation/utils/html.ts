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
export function escapeHtml(value) {
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
export function prettyJson(value) {
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
export function codeBlock(value, language = "text") {
    const text = typeof value === "string" ? value : prettyJson(value);
    const safeLanguage = language.replace(/[^a-z0-9_-]/gi, "") || "text";
    return `<pre class="code-block language-${safeLanguage}"><code class="language-${safeLanguage}">${highlightCode(text, safeLanguage)}</code></pre>`;
}

/**
 * Render a conservative subset of Markdown for memory preview.
 *
 * @param {string} markdown Markdown source.
 * @returns {string} Rendered HTML.
 */
export function renderMarkdown(markdown) {
    const trimmed = String(markdown || "").trim();
    if ((trimmed.startsWith("{") && trimmed.endsWith("}")) || (trimmed.startsWith("[") && trimmed.endsWith("]"))) {
        return codeBlock(trimmed, "json");
    }
    if (trimmed.startsWith("#!") || trimmed.startsWith("import sys") || trimmed.startsWith("def main():")) {
        const lang = trimmed.includes("python") || trimmed.includes("py") || trimmed.startsWith("import sys") || trimmed.startsWith("def main():") ? "python" : "bash";
        return codeBlock(trimmed, lang);
    }
    const firstLines = trimmed.split(/\n/).slice(0, 10);
    const logMatchCount = firstLines.filter(line => 
        line.match(/^\[(INFO|ERROR|WARNING|SUCCESS|WARN|FAIL|FATAL|OK)\]/i) || 
        line.match(/^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}/)
    ).length;
    if (logMatchCount >= 2 || (firstLines.length > 0 && logMatchCount === firstLines.length)) {
        return codeBlock(trimmed, "log");
    }
    const lines = String(markdown || "").split(/\r?\n/);
    const html = [];
    let paragraph = [];
    let list = [];
    let codeLines = [];
    let codeLanguage = "markdown";

    const flushParagraph = () => {
        if (!paragraph.length) {
            return;
        }
        html.push(`<p>${inlineMarkdown(paragraph.join(" "))}</p>`);
        paragraph = [];
    };
    const flushList = () => {
        if (!list.length) {
            return;
        }
        html.push(`<ul>${list.map(item => `<li>${inlineMarkdown(item)}</li>`).join("")}</ul>`);
        list = [];
    };
    const flushCode = () => {
        if (!codeLines.length) {
            return;
        }
        html.push(codeBlock(codeLines.join("\n"), codeLanguage));
        codeLines = [];
        codeLanguage = "markdown";
    };

    let inCode = false;
    for (const line of lines) {
        const fence = line.match(/^```([a-z0-9_-]+)?\s*$/i);
        if (fence) {
            if (inCode) {
                flushCode();
                inCode = false;
            } else {
                flushParagraph();
                flushList();
                inCode = true;
                codeLanguage = fence[1] || "markdown";
            }
            continue;
        }
        if (inCode) {
            codeLines.push(line);
            continue;
        }
        if (!line.trim()) {
            flushParagraph();
            flushList();
            continue;
        }
        const heading = line.match(/^(#{1,4})\s+(.+)$/);
        if (heading) {
            flushParagraph();
            flushList();
            html.push(`<h${heading[1].length}>${inlineMarkdown(heading[2])}</h${heading[1].length}>`);
            continue;
        }
        const bullet = line.match(/^\s*[-*]\s+(.+)$/);
        if (bullet) {
            flushParagraph();
            list.push(bullet[1]);
            continue;
        }
        const quote = line.match(/^>\s+(.+)$/);
        if (quote) {
            flushParagraph();
            flushList();
            html.push(`<blockquote>${inlineMarkdown(quote[1])}</blockquote>`);
            continue;
        }
        paragraph.push(line.trim());
    }
    flushParagraph();
    flushList();
    flushCode();
    return html.join("");
}

/**
 * Convert a path-like value into a compact display label.
 *
 * @param {string} value Full path-like value.
 * @returns {string} Last path segment or the original value.
 */
export function compactLabel(value) {
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
export function optionTags(values, selected) {
    return values
        .map(value => `<option value="${escapeHtml(value)}" ${value === selected ? "selected" : ""}>${escapeHtml(value)}</option>`)
        .join("");
}

function highlightCode(value, language) {
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

function inlineMarkdown(value) {
    return escapeHtml(value)
        .replace(/`([^`]+)`/g, `<code>$1</code>`)
        .replace(/\*\*([^*]+)\*\*/g, `<strong>$1</strong>`)
        .replace(/\*([^*]+)\*/g, `<em>$1</em>`);
}
