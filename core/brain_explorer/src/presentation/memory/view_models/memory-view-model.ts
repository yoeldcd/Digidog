/**
 * Navigation and tree projection contracts for the Memory presentation feature.
 *
 * @module presentation/memory/view_models/memory-view-model
 */

/**
 * Closed workspace mode selected by Memory navigation and actions.
 */
export type MemoryMode = "browse" | "read" | "edit" | "domains";
/**
 * Validated deferred navigation target accepted by the Memory layout.
 */
export interface MemoryTarget {
    /**
     * Exact dotted memory-entry path to focus.
     * @type {string | undefined}
     */
    path?: string;
    /**
     * Exact dotted memory domain to focus.
     * @type {string | undefined}
     */
    domain?: string;
    /**
     * Workspace mode requested by the originating feature.
     * @type {MemoryMode | undefined}
     */
    mode?: MemoryMode;
}
/**
 * Mutable accumulator used to project dotted memory paths into a hierarchy.
 */
export interface MemoryNode {
    /**
     * Visible label for the current path segment.
     * @type {string}
     */
    label: string;
    /**
     * Complete dotted path represented by the node.
     * @type {string}
     */
    path: string;
    /**
     * Child nodes keyed by their immediate path segment.
     * @type {Map<string, MemoryNode>}
     */
    children: Map<string, MemoryNode>;
}

/**
 * Narrow an untrusted route-target value to one supported Memory presentation mode.
 *
 * @param {unknown} value Candidate value received from shared navigation state.
 * @returns {boolean} True only for one of the four closed Memory modes.
 */
function isMemoryMode(value: unknown): value is MemoryMode {
    return value === "browse" || value === "read" || value === "edit" || value === "domains";
}

/**
 * Normalize untrusted shell route state into the Memory target contract.
 *
 * @param {Record<string, unknown> | null} value Unknown route record previously stored by another feature.
 * @returns {MemoryTarget | null} Narrowed target, or null when no route record was supplied.
 */
export function memoryTarget(value: Record<string, unknown> | null): MemoryTarget | null {
    if (!value) return null;
    const mode = isMemoryMode(value.mode) ? value.mode : undefined;
    return {
        ...(typeof value.path === "string" ? { path: value.path } : {}),
        ...(typeof value.domain === "string" ? { domain: value.domain } : {}),
        ...(mode ? { mode } : {})
    };
}
