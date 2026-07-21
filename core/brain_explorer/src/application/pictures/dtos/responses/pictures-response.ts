/**
 * Registry-backed picture record returned by the Pictures feature.
 */
export interface PictureRecord {
    /**
     * Stable registry identifier.
     * @type {string}
     */
    id: string;
    /**
     * Workspace-relative canonical path.
     * @type {string}
     */
    relative_path: string;
    /**
     * Server-resolved absolute path.
     * @type {string}
     */
    absolute_path: string;
    /**
     * Canonical dotted ownership domain.
     * @type {string}
     */
    domain: string;
    /**
     * Leaf filename.
     * @type {string}
     */
    filename: string;
    /**
     * Lowercase file extension.
     * @type {string}
     */
    extension: string;
    /**
     * Detected media type.
     * @type {string}
     */
    mime_type: string;
    /**
     * File size in bytes.
     * @type {number}
     */
    size_bytes: number;
    /**
     * Filesystem modification timestamp in nanoseconds.
     * @type {number}
     */
    mtime_ns: number;
    /**
     * Stable content digest.
     * @type {string}
     */
    content_hash: string;
    /**
     * Intrinsic pixel width.
     * @type {number}
     */
    width: number;
    /**
     * Intrinsic pixel height.
     * @type {number}
     */
    height: number;
    /**
     * Current human or generated description.
     * @type {string}
     */
    description: string;
    /**
     * Provenance of the current description.
     * @type {string}
     */
    description_source: string;
    /**
     * Description update timestamp.
     * @type {string}
     */
    described_at: string;
    /**
     * Whether the registry record remains active.
     * @type {boolean}
     */
    active: boolean;
}

/**
 * Picture registry listing and aggregate domain counts.
 */
export interface PicturesPayload {
    /**
     * Registered active pictures.
     * @type {PictureRecord[]}
     */
    pictures: PictureRecord[];
    /**
     * Direct picture count by canonical domain.
     * @type {Record<string, number>}
     */
    domains: Record<string, number>;
    /**
     * Server scan diagnostics.
     * @type {Record<string, unknown>}
     */
    scan: Record<string, unknown>;
}

/**
 * Result of saving or generating one picture description.
 */
export interface PictureDescriptionPayload {
    /**
     * Updated authoritative picture record.
     * @type {PictureRecord}
     */
    picture: PictureRecord;
    /**
     * Vector-index mutation diagnostics.
     * @type {Record<string, unknown>}
     */
    vectors: Record<string, unknown>;
}
