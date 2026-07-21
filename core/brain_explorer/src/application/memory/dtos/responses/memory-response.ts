/**
 * Response payload returned by the Memory read-entry application query.
 */
export interface MemoryEntryPayload {
    /**
     * Markdown content when the requested canonical entry exists.
     * @type {string | undefined}
     */
    content?: string;
}
