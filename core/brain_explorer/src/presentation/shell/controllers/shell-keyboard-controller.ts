/**
 * Handles global keyboard interactions owned by the persistent application shell.
 *
 * @module presentation/shell/controllers/shell-keyboard-controller
 */

/**
 * Focus and select the shell search field when the registered shortcut is pressed.
 *
 * The controller receives its host explicitly and therefore owns no DOM lifecycle
 * or global listener registration; the shell component remains responsible for
 * attaching and detaching the stable event callback.
 *
 * @param {HTMLElement} host Shell Custom Element containing the global search input.
 * @param {KeyboardEvent} event Native keyboard interaction dispatched by `window`.
 */
export function handleShellSearchShortcut(host: HTMLElement, event: KeyboardEvent): void {
    if (!event.ctrlKey || !event.altKey || event.key.toLowerCase() !== "s") return;
    event.preventDefault();
    const searchInput = host.querySelector<HTMLInputElement>("[data-role='global-shell-search']");
    searchInput?.focus();
    searchInput?.select();
}
