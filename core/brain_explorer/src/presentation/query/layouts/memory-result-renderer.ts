import { escapeHtml, renderMarkdown } from "../../shared/utils/html.ts";
import { icon } from "../../shared/utils/icons.ts";
import type { QueryEvidenceViewModel } from "../view_models/query-view-model.ts";

/** Render one durable-memory result without exposing storage implementation details. */
export function renderMemoryResult(item: QueryEvidenceViewModel): string {
    const scope = escapeHtml(item.origin.scope || "global");
    const isDiary = item.origin.sourceType === "diary";
    const typeLabel = isDiary ? "Diary" : "Memory";
    const dateBadge = isDiary && item.date
        ? `<time class="query-card-date" datetime="${escapeHtml(item.date.comparable)}">${escapeHtml(item.date.display)}</time>`
        : "";

    return `<li class="query-result-card memory-result-card" role="link" tabindex="0" data-route="memory" data-target-id="${escapeHtml(item.resourceId)}" data-route-target="${escapeHtml(JSON.stringify(item.target))}"><article>
        <header class="query-card-header"><span class="query-card-icon">${icon("book")}</span><div><div class="query-card-badges"><span class="query-badge is-scope">${scope}</span><span class="query-badge">${typeLabel}</span></div><h3>${escapeHtml(item.title)}</h3></div>${dateBadge}</header>
        <div class="query-card-body">${renderMarkdown(item.markdown)}</div>
        <footer class="query-card-footer"><span>${escapeHtml(item.mechanism)} match</span><button type="button" class="query-card-open" data-route="memory" data-target-id="${escapeHtml(item.resourceId)}" data-route-target="${escapeHtml(JSON.stringify(item.target))}"><span>Open</span>${icon("chevronRight")}</button></footer>
    </article></li>`;
}