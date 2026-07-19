/** Shared structured presentation for long image and entity descriptions. */

import { escapeHtml, renderMarkdown } from "../utils/html.ts";

export interface DescriptionSection {
    id: string;
    title: string;
    body: string;
}

export interface DescriptionCardOptions {
    title?: string;
    emptyText?: string;
    openFirst?: boolean;
}

const ENTITY_SECTION_TITLES = new Set([
    "subject",
    "subjects",
    "main subject",
    "main subjects",
    "tag",
    "tags",
    "semantic tag",
    "semantic tags"
]);

interface DescriptionMarker {
    index: number;
    end: number;
    title: string;
}

/**
 * Split model-authored Markdown into stable sections.
 *
 * Headings and bold field labels such as `**Subjects:**` are treated as
 * section boundaries even when several fields share one physical line.
 */
export function parseDescriptionSections(markdown: string): DescriptionSection[] {
    const source = String(markdown || "").trim();
    if (!source) return [];

    const markerPattern = /(?:^|\n)[ \t]{0,3}#{1,4}[ \t]+([^\n]+)|\*\*([^*\n:]{1,80}):\*\*/gm;
    const markers: DescriptionMarker[] = [];
    let match: RegExpExecArray | null;
    while ((match = markerPattern.exec(source)) !== null) {
        const startsWithNewline = match[0].startsWith("\n");
        markers.push({
            index: match.index + (startsWithNewline ? 1 : 0),
            end: markerPattern.lastIndex,
            title: normalizeSectionTitle(match[1] || match[2] || "Description")
        });
    }
    if (!markers.length) return [createSection("Description", source, 0)];

    const sections: DescriptionSection[] = [];
    const preamble = source.slice(0, markers[0].index).trim();
    if (preamble) sections.push(createSection("Overview", preamble, sections.length));
    markers.forEach((marker, index) => {
        const nextIndex = markers[index + 1]?.index ?? source.length;
        const body = normalizeSectionBody(source.slice(marker.end, nextIndex).replace(/^[\s:–—]+/, "").trim());
        if (body) sections.push(createSection(marker.title, body, sections.length));
    });
    return sections.length ? sections : [createSection("Description", source, 0)];
}

/** Render a bounded description card with native, accessible disclosures. */
export function renderDescriptionCard(markdown: string, options: DescriptionCardOptions = {}): string {
    const title = options.title || "Description";
    const emptyText = options.emptyText || "No description available.";
    const sections = parseDescriptionSections(markdown);
    const content = sections.length
        ? sections.map((section, index) => `
            <details class="description-card-section" ${options.openFirst !== false && index === 0 ? "open" : ""}>
                <summary>
                    <span>${escapeHtml(section.title)}</span>
                    <span class="description-card-chevron" aria-hidden="true">&#8250;</span>
                </summary>
                <div class="description-card-body">${renderDescriptionSection(section)}</div>
            </details>
        `).join("")
        : `<p class="description-card-empty">${escapeHtml(emptyText)}</p>`;
    return `
        <article class="description-card" data-role="description-card">
            <header>
                <strong>${escapeHtml(title)}</strong>
                ${sections.length > 1 ? `<span>${sections.length} sections</span>` : ""}
            </header>
            <div class="description-card-sections">${content}</div>
        </article>
    `;
}

/** Extract entity-like values from Subjects and tag sections. */
export function descriptionEntityValues(section: DescriptionSection): string[] {
    if (!ENTITY_SECTION_TITLES.has(section.title.trim().toLowerCase())) return [];
    const normalized = section.body
        .replace(/\s*,\s*and\s+/gi, ",")
        .replace(/\s+and\s+/gi, ",")
        .replace(/^[-*]\s*/, "");
    const seen = new Set<string>();
    return normalized
        .split(/\s*,\s*|\r?\n+/)
        .map(value => value.replace(/^[-*]\s*/, "").replace(/[.;:]+$/, "").trim())
        .filter(value => {
            const key = value.toLowerCase();
            if (!value || value.length > 80 || seen.has(key)) return false;
            seen.add(key);
            return true;
        });
}

/** Render entity sections as resolvable badges and all other bodies as Markdown. */
function renderDescriptionSection(section: DescriptionSection): string {
    const entities = descriptionEntityValues(section);
    if (!entities.length) return renderMarkdown(section.body);
    return `
        <div class="description-entity-badges" aria-label="${escapeHtml(section.title)} entities">
            ${entities.map(entity => `
                <button type="button" class="description-entity-badge" data-action="resolve-description-entity" data-entity-label="${escapeHtml(entity)}">
                    ${escapeHtml(entity)}
                </button>
            `).join("")}
        </div>
    `;
}

/** Convert compact model-authored inline lists into Markdown list lines. */
function normalizeSectionBody(body: string): string {
    if (/^[-*]\s+/.test(body)) return body.replace(/\s+([-*])\s+/g, "\n$1 ");
    if (/^\d+\.\s+/.test(body)) return body.replace(/\s+(\d+\.)\s+/g, "\n$1 ");
    return body;
}

/** Create a unique, selector-safe section identity. */
function createSection(title: string, body: string, index: number): DescriptionSection {
    const slug = title.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "") || "section";
    return { id: `${slug}-${index + 1}`, title, body };
}

/** Remove residual Markdown emphasis from disclosure labels. */
function normalizeSectionTitle(title: string): string {
    return String(title || "Description")
        .replace(/^\*+|\*+$/g, "")
        .replace(/\s+/g, " ")
        .trim()
        .replace(/:$/, "") || "Description";
}
