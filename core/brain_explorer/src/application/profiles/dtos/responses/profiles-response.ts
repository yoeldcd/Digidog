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
     * Stable profile names addressable by the read endpoint.
     * @type {string[]}
     */
    profiles: string[];
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
