/**
 * One named content entry exposed by the Profiles application query.
 */
export interface ProfileEntry {
    /**
     * Canonical entry key.
     * @type {string}
     */
    key: string;
    /**
     * Optional reader-facing name.
     * @type {string | undefined}
     */
    name?: string;
    /**
     * Optional structured content representation.
     * @type {string | undefined}
     */
    content?: string;
    /**
     * Optional raw text representation.
     * @type {string | undefined}
     */
    text?: string;
}

/**
 * Available operational profile names.
 */
export interface ProfilesPayload {
    /**
     * Compact profile summaries addressable by the read endpoint.
     * @type {ProfileSummary[]}
     */
    profiles: ProfileSummary[];
}

/**
 * Compact operational profile metadata.
 */
export interface ProfileSummary {
    /**
     * Stable incremental identifier.
     * @type {number}
     */
    id: number;
    /**
     * Canonical profile name.
     * @type {string}
     */
    name: string;
    /**
     * Command that retrieves the full profile.
     * @type {string}
     */
    retrieve_command: string;
    /**
     * Concise guidance describing when the profile should be selected.
     * @type {string}
     */
    use_when: string;
}

/**
 * Read response for one operational profile.
 */
export interface ProfileReadPayload {
    /**
     * Structured entries when the profile exposes multiple fields.
     * @type {ProfileEntry[] | undefined}
     */
    entries?: ProfileEntry[];
    /**
     * Raw profile document when returned as a single body.
     * @type {string | undefined}
     */
    text?: string;
}
