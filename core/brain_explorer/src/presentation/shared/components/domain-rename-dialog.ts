/**
 * Shared dialog rendering and interaction for canonical domain renaming.
 *
 * @module presentation/shared/components/domain-rename-dialog
 */

import { escapeHtml } from "../utils/html.ts";
import { icon } from "../utils/icons.ts";

/**
 * Render the shared domain-renaming surface used by structural trees.
 *
 * @param {string} id Unique dialog identifier within its host view.
 * @returns {string} Inert dialog markup ready for event binding.
 */
export function renderDomainRenameDialog(id: string): string {
    return `<dialog id="${escapeHtml(id)}" class="domain-rename-dialog">
        <form method="dialog" class="domain-rename-card" data-role="domain-rename-form">
            <header class="domain-rename-header">
                <span class="domain-rename-icon">${icon("edit")}</span>
                <div><strong>Rename domain</strong><small>Move this domain and all its subdomains</small></div>
                <button class="icon-action" value="cancel" title="Close" aria-label="Close">${icon("close")}</button>
            </header>
            <label class="domain-rename-field"><span>Current domain</span>
                <input data-role="domain-rename-source" readonly>
            </label>
            <label class="domain-rename-field"><span>New canonical domain</span>
                <input data-role="domain-rename-target" autocomplete="off" spellcheck="false" required>
            </label>
            <p class="domain-rename-status" data-role="domain-rename-status" aria-live="polite">Descendant paths keep their relative suffixes.</p>
            <footer class="domain-rename-actions">
                <button class="ghost-action" value="cancel">Cancel</button>
                <button class="primary-action" value="confirm">Rename domain</button>
            </footer>
        </form>
    </dialog>`;
}

/**
 * Ask for a canonical replacement path through the Explorer-styled dialog.
 *
 * @param {ParentNode} host View containing the rendered dialog.
 * @param {string} id Unique dialog identifier within the host.
 * @param {string} source Existing canonical domain path.
 * @returns {Promise<string | null>} Trimmed target path, or null when cancelled or unchanged.
 */
export function requestDomainRename(host: ParentNode, id: string, source: string): Promise<string | null> {
    const dialog = host.querySelector<HTMLDialogElement>(`#${id}`);
    const sourceInput = dialog?.querySelector<HTMLInputElement>("[data-role='domain-rename-source']");
    const targetInput = dialog?.querySelector<HTMLInputElement>("[data-role='domain-rename-target']");
    if (!dialog || !sourceInput || !targetInput) return Promise.resolve(null);

    sourceInput.value = source;
    targetInput.value = source;
    dialog.returnValue = "cancel";
    dialog.showModal();
    targetInput.focus();
    targetInput.select();

    return new Promise(resolve => {
        dialog.addEventListener("close", () => {
            const target = targetInput.value.trim();
            resolve(dialog.returnValue === "confirm" && target && target !== source ? target : null);
        }, { once: true });
    });
}
