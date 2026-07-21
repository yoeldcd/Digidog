/**
 * Registered project and its documentation availability in the Wikis query result.
 */
export interface WikiRecord {
    /**
     * Registered project display name.
     * @type {string}
     */
    name: string;
    /**
     * Canonical workspace path owned by the project registry.
     * @type {string}
     */
    path: string;
    /**
     * Whether a documentation wiki is available for reading.
     * @type {boolean}
     */
    hasWiki: boolean;
}

/**
 * Complete project-wiki listing returned by the Wikis application query.
 */
export interface WikisResponse {
    /**
     * Whether the registry query succeeded.
     * @type {boolean}
     */
    ok: boolean;
    /**
     * Registered projects and their current wiki availability.
     * @type {WikiRecord[]}
     */
    wikis: WikiRecord[];
}
