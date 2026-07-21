/**
 * Render the inert loading placeholder used by Memory content operations.
 *
 * The function owns markup composition only. Callers retain responsibility for
 * deciding when the loading state is visible and for supplying trusted UI copy.
 *
 * @param {string} label Human-readable operation currently preparing Memory content.
 * @returns {string} Static HTML for the standardized animated loading indicator.
 */
export function renderMemoryLoadingState(label: string): string {
    return `
        <div class="loading-state">
            <span></span>
            <strong>${escapeHtml(label)}</strong>
        </div>
    `;
}
import { escapeHtml } from "../../shared/utils/html.ts";
