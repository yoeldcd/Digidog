/**
 * Build a deterministic fallback node identifier from graph context.
 *
 * The identifier mirrors the legacy canvas contract: labels are normalized only
 * by lower-casing, while an empty label falls back to the supplied stable index.
 *
 * @param {string} domain Canonical domain that owns the visible graph node.
 * @param {string} label Human-readable entity or class label.
 * @param {number} index Stable fallback index used only when the label is empty.
 * @returns {string} Presentation-only node identifier shared by records and relations.
 */
export function knowledgeNodeId(domain: string, label: string, index = 0): string {
    return `node:${domain}:${String(label || index).toLowerCase()}`;
}

/**
 * Shorten a graph label to fit a constrained canvas or source-tree surface.
 *
 * @param {string} label Full label supplied by normalized knowledge data.
 * @param {number} limit Maximum rendered character count, including the ellipsis.
 * @returns {string} Original text when it fits, otherwise a stable ellipsis-truncated label.
 */
export function shortKnowledgeLabel(label: string, limit = 14): string {
    const text = String(label || "");
    return text.length > limit ? `${text.slice(0, Math.max(1, limit - 1))}...` : text;
}
