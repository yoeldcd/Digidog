import { escapeHtml, renderMarkdown } from "../../shared/utils/html.ts";
import { icon } from "../../shared/utils/icons.ts";
import type { QueryEvidenceViewModel } from "../view_models/query-view-model.ts";

/** Render one journal entry as a chronological log card. */
export function renderLogResult(item: QueryEvidenceViewModel): string {
    const date = escapeHtml(item.date?.display || "Undated");
    return `<li class="query-result-card log-result-card" role="link" tabindex="0" data-route="logs" data-target-id="${escapeHtml(item.resourceId)}" data-route-target="${escapeHtml(JSON.stringify(item.target))}"><article>
        <header class="query-card-header"><span class="query-card-icon">${icon("clock")}</span><div><div class="query-card-badges"><span class="query-badge">Log</span></div><h3>${escapeHtml(item.title)}</h3></div><time class="query-card-date" datetime="${escapeHtml(item.date?.comparable || "")}">${date}</time></header>
        <div class="query-card-body">${renderMarkdown(item.markdown)}</div>
        <footer class="query-card-footer"><span>${escapeHtml(item.mechanism)} match</span><button type="button" class="query-card-open" data-route="logs" data-target-id="${escapeHtml(item.resourceId)}" data-route-target="${escapeHtml(JSON.stringify(item.target))}"><span>Open</span>${icon("chevronRight")}</button></footer>
    </article></li>`;
}