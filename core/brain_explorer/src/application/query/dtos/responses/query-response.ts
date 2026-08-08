/**
 * Rich content nested beneath a source-specific response envelope.
 *
 * The contract preserves the content fields emitted by source-specific
 * backends, including explicit temporal aliases used by message, picture,
 * diary, and log search DTOs.
 */
export interface QueryEvidenceExcerpt {
    /** Human-readable title associated with the content block. */
    readonly title?: string;

    /** Compact human-readable evidence excerpt. */
    readonly excerpt?: string;

    /** Longer content body when the backend provides one. */
    readonly body?: string;

    /** Source-local section, line, or location hint. */
    readonly location?: string;

    /** Optional source entity identifier. */
    readonly id?: string | number;

    /** Explicit calendar date emitted by source-specific DTOs. */
    readonly date?: string;

    /** Explicit clock time emitted by source-specific DTOs. */
    readonly time?: string;

    /** Canonical timestamp emitted by source-specific DTOs. */
    readonly timestamp?: string;

    /** Snake-case creation timestamp compatibility alias. */
    readonly created_at?: string;

    /** Camel-case creation timestamp compatibility alias. */
    readonly createdAt?: string;

    /** Snake-case update timestamp compatibility alias. */
    readonly updated_at?: string;

    /** Camel-case update timestamp compatibility alias. */
    readonly updatedAt?: string;

    /** Snake-case description timestamp compatibility alias. */
    readonly described_at?: string;

    /** Camel-case description timestamp compatibility alias. */
    readonly describedAt?: string;
}

/**
 * Alias for the normalized content contract used by query evidence.
 */
export type QueryEvidenceContent = QueryEvidenceExcerpt;

/**
 * Feature-oriented evidence payload that may address a source entity.
 *
 * Source-specific DTO fields are retained as optional aliases so transport
 * normalization does not discard backend metadata before view-model mapping.
 */
export interface QueryEvidenceData extends QueryEvidenceExcerpt {
    /** Source family emitted by a source-specific search DTO. */
    readonly source_type?: string;

    /** Camel-case source family compatibility alias. */
    readonly sourceType?: string;

    /** Source command emitted by message or diary search DTOs. */
    readonly source_command?: string;

    /** Camel-case source command compatibility alias. */
    readonly sourceCommand?: string;

    /** Source phase emitted by message search DTOs. */
    readonly source_phase?: string;

    /** Camel-case source phase compatibility alias. */
    readonly sourcePhase?: string;

    /** Memory category or source domain. */
    readonly category?: string;

    /** Relative source path emitted by picture search DTOs. */
    readonly relative_path?: string;

    /** Camel-case relative source path compatibility alias. */
    readonly relativePath?: string;

    /** Source filename emitted by picture search DTOs. */
    readonly filename?: string;

    /** Source file extension emitted by picture search DTOs. */
    readonly extension?: string;

    /** Source MIME type emitted by picture search DTOs. */
    readonly mime_type?: string;

    /** Camel-case source MIME type compatibility alias. */
    readonly mimeType?: string;

    /** File modification timestamp in nanoseconds. */
    readonly mtime_ns?: number;

    /** Camel-case file modification timestamp compatibility alias. */
    readonly mtimeNs?: number;

    /** Immutable source-specific metadata map. */
    readonly metadata?: Readonly<Record<string, unknown>>;
}

/**
 * Canonical or compatibility source-location reference.
 *
 * Both snake-case transport names and camel-case compatibility aliases are
 * retained because backend adapters can expose either representation.
 */
export interface QueryEvidenceSourceReference {
    /** Knowledge or runtime scope that owns the source. */
    readonly scope?: string;

    /** Source family emitted by the backend. */
    readonly source_type?: string;

    /** Camel-case source family compatibility alias. */
    readonly sourceType?: string;

    /** Logical source domain. */
    readonly domain?: string;

    /** CLI command that reads this source. */
    readonly read_command?: string;

    /** Camel-case read command compatibility alias. */
    readonly readCommand?: string;

    /** Stable source path suitable for attribution. */
    readonly path?: string;

    /** Human-readable source title. */
    readonly title?: string;

    /** Navigable source structure segments. */
    readonly structure?: readonly string[];

    /** Optional source-local line number. */
    readonly line_number?: number | null;

    /** Camel-case line-number compatibility alias. */
    readonly lineNumber?: number | null;
}

/**
 * Traceable evidence item returned by the global query endpoint.
 *
 * The transport contract intentionally keeps both canonical and compatibility
 * aliases so no nested source metadata is lost before normalization.
 */
export interface QueryEvidence {
    /** Canonical source family. */
    readonly source?: string;

    /** Snake-case source family compatibility alias. */
    readonly source_type?: string;

    /** Camel-case source family compatibility alias. */
    readonly sourceType?: string;

    /** Retrieval mechanism. */
    readonly mechanism?: string;

    /** Knowledge or runtime scope. */
    readonly scope?: string;

    /** Canonical source path. */
    readonly path?: string;

    /** Source-local location or section hint. */
    readonly location?: string;

    /** Human-readable result title. */
    readonly title?: string;

    /** Full textual result body. */
    readonly text?: string;

    /** Markdown-ready textual body alias. */
    readonly body?: string;

    /** Compact textual excerpt. */
    readonly excerpt?: string;

    /** Server-defined result classification. */
    readonly kind?: string;

    /** Human or generated description. */
    readonly description?: string;

    /** Optional source entity identifier. */
    readonly id?: string | number;

    /** Retrieval relevance score. */
    readonly rank?: number;

    /** Explicit calendar date emitted by source-specific DTOs. */
    readonly date?: string;

    /** Explicit clock time emitted by source-specific DTOs. */
    readonly time?: string;

    /** Canonical timestamp emitted by source-specific DTOs. */
    readonly timestamp?: string;

    /** Snake-case creation timestamp compatibility alias. */
    readonly created_at?: string;

    /** Camel-case creation timestamp compatibility alias. */
    readonly createdAt?: string;

    /** Snake-case update timestamp compatibility alias. */
    readonly updated_at?: string;

    /** Camel-case update timestamp compatibility alias. */
    readonly updatedAt?: string;

    /** Snake-case description timestamp compatibility alias. */
    readonly described_at?: string;

    /** Camel-case description timestamp compatibility alias. */
    readonly describedAt?: string;

    /** Optional warning generated during backend normalization. */
    readonly warning?: string;

    /** Nested content envelope from text-oriented sources. */
    readonly content?: QueryEvidenceExcerpt;

    /** Nested data envelope from feature-oriented sources. */
    readonly data?: QueryEvidenceData;

    /** Normalized source reference. */
    readonly sourceRef?: QueryEvidenceSourceReference;

    /** Compatibility source reference. */
    readonly source_ref?: QueryEvidenceSourceReference;

    /** Canonical dotted ownership domain. */
    readonly domain?: string;
}

/**
 * Object-shaped global query payload returned by the server.
 */
export interface QueryResultData {
    /** Synthesized natural-language answer. */
    readonly response?: string;

    /** Canonical ranked evidence collection. */
    readonly items?: readonly QueryEvidence[];

    /** One-based page returned by the backend. */
    readonly page?: number;

    /** Number of items requested for the page. */
    readonly pageSize?: number;

    /** Total number of matching items across all pages. */
    readonly totalItems?: number;

    /** Total number of available pages. */
    readonly totalPages?: number;

    /** Whether a previous page exists. */
    readonly hasPrevious?: boolean;

    /** Whether a next page exists. */
    readonly hasNext?: boolean;

    /** Global counts grouped by source family. */
    readonly countsBySource?: Readonly<Record<string, number>>;

    /** Ranked evidence compatibility alias. */
    readonly results?: QueryEvidence[];

    /** Ranked evidence compatibility alias. */
    readonly matches?: QueryEvidence[];
}

/**
 * Payload variants accepted from the global query endpoint.
 */
export type QueryResponse = QueryResultData | QueryEvidence[];
