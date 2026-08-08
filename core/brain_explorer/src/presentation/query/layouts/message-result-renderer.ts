import { escapeHtml, renderMarkdown } from "../../shared/utils/html.ts";
import { icon } from "../../shared/utils/icons.ts";
import type { QueryEvidenceViewModel } from "../view_models/query-view-model.ts";

/** Render one conversation result as a message transcript card. */
export function renderMessageResult(item: QueryEvidenceViewModel): string {
    const date = escapeHtml(item.date?.display || "Undated");
    const dateTime = escapeHtml(item.date?.comparable || "");
    return `<li class="query-result-card message-result-card" role="link" tabindex="0" data-route="messages" data-target-id="${escapeHtml(item.resourceId)}" data-route-target="${escapeHtml(JSON.stringify(item.target))}"><article>
        <header class="query-card-header"><span class="query-card-icon">${icon("messageCircle")}</span><div><div class="query-card-badges"><span class="query-badge">Message</span></div><h3>${escapeHtml(item.title)}</h3></div><time class="query-card-date"${dateTime ? ` datetime="${dateTime}"` : ""}>${date}</time></header>
        <blockquote class="query-card-body message-result-excerpt">${renderMarkdown(item.markdown)}</blockquote>
        <footer class="query-card-footer"><span>${escapeHtml(item.mechanism)} match</span><button type="button" class="query-card-open" data-route="messages" data-target-id="${escapeHtml(item.resourceId)}" data-route-target="${escapeHtml(JSON.stringify(item.target))}"><span>Open</span>${icon("chevronRight")}</button></footer>
    </article></li>`;
}