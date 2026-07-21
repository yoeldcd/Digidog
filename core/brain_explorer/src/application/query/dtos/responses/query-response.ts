/**
 * Text excerpt nested beneath a source-specific response envelope.
 */
export interface QueryEvidenceExcerpt {
    /**
     * Compact human-readable evidence excerpt.
     * @type {string | undefined}
     */
    excerpt?: string;
}

/**
 * Feature-oriented evidence payload that may address a source entity.
 */
export interface QueryEvidenceData extends QueryEvidenceExcerpt {
    /**
     * Stable feature entity identifier used by route actions.
     * @type {string | undefined}
     */
    id?: string;
}

/**
 * Canonical or compatibility source-location reference.
 */
export interface QueryEvidenceSourceReference {
    /**
     * Canonical source path suitable for attribution.
     * @type {string | undefined}
     */
    path?: string;
}

/**
 * Traceable evidence item returned by the global query endpoint.
 */
export interface QueryEvidence {
    /**
     * Canonical source family.
     * @type {string | undefined}
     */
    source?: string;
    /**
     * Retrieval mechanism.
     * @type {string | undefined}
     */
    mechanism?: string;
    /**
     * Canonical source path.
     * @type {string | undefined}
     */
    path?: string;
    /**
     * Human-readable result title.
     * @type {string | undefined}
     */
    title?: string;
    /**
     * Full textual result body.
     * @type {string | undefined}
     */
    text?: string;
    /**
     * Compact textual excerpt.
     * @type {string | undefined}
     */
    excerpt?: string;
    /**
     * Server-defined result classification.
     * @type {string | undefined}
     */
    kind?: string;
    /**
     * Human or generated description.
     * @type {string | undefined}
     */
    description?: string;
    /**
     * Retrieval relevance score.
     * @type {number | undefined}
     */
    rank?: number;
    /**
     * Nested content envelope from text-oriented sources.
     * @type {QueryEvidenceExcerpt | undefined}
     */
    content?: QueryEvidenceExcerpt;
    /**
     * Nested data envelope from feature-oriented sources.
     * @type {QueryEvidenceData | undefined}
     */
    data?: QueryEvidenceData;
    /**
     * Normalized source reference.
     * @type {QueryEvidenceSourceReference | undefined}
     */
    sourceRef?: QueryEvidenceSourceReference;
    /**
     * Compatibility source reference.
     * @type {QueryEvidenceSourceReference | undefined}
     */
    source_ref?: QueryEvidenceSourceReference;
    /**
     * Canonical dotted ownership domain.
     * @type {string | undefined}
     */
    domain?: string;
}

/**
 * Object-shaped global query payload returned by the server.
 */
export interface QueryResultData {
    /**
     * Synthesized natural-language answer.
     * @type {string | undefined}
     */
    response?: string;
    /**
     * Ranked evidence under the canonical key.
     * @type {QueryEvidence[] | undefined}
     */
    results?: QueryEvidence[];
    /**
     * Ranked evidence under the compatibility key.
     * @type {QueryEvidence[] | undefined}
     */
    matches?: QueryEvidence[];
}

/**
 * Payload variants accepted from the global query endpoint.
 */
export type QueryResponse = QueryResultData | QueryEvidence[];
