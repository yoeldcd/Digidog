/** Normalize local source-tab selection against the sources in a new response. */

/**
 * Keep a valid source selection, otherwise reveal all available results.
 *
 * @param activeSource - Current local source-tab selection.
 * @param presentSources - Sources represented by the latest response.
 * @returns The existing selection when present, otherwise `all`.
 */
export function normalizeActiveQuerySource(
    activeSource: string,
    presentSources: readonly string[],
): string {
    if (activeSource === "all" || presentSources.includes(activeSource)) {
        return activeSource;
    }

    return "all";
}