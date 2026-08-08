/**
 * Render lifecycle and grouping contracts for global query results.
 *
 * @module presentation/query/view_models/query-view-model
 */

import type { QueryEvidence, QueryResultData } from "../../../application/query/dtos/responses/query-response.ts";

/**
 * Render lifecycle state for the latest global query.
 */
export interface QueryResult {
    /** Whether the query is currently awaiting a server response. */
    readonly loading?: boolean;

    /** Whether the server completed the query successfully. */
    readonly ok?: boolean;

    /** Normalized answer and evidence rendered by the Query layout. */
    readonly data?: QueryResultData;

    /** Human-readable request failure detail. */
    readonly stderr?: string;
}

/**
 * Comparable and display-ready date values for normalized evidence.
 */
export interface QueryEvidenceDateViewModel {
    /** Stable ISO-like value used for ordering evidence chronologically. */
    readonly comparable: string;

    /** Localized value intended for direct display. */
    readonly display: string;
}

/**
 * Source identity metadata used by normalized evidence cards and groups.
 */
export interface QueryEvidenceOriginViewModel {
    /** Canonical source family. */
    readonly source: string;

    /** Retrieval mechanism that produced the evidence. */
    readonly mechanism: string;

    /** Knowledge or runtime scope that owns the source. */
    readonly scope: string;

    /** Source family emitted by the backend. */
    readonly sourceType: string;

    /** Logical source domain. */
    readonly domain: string;

    /** Human-readable source title. */
    readonly title: string;
}

/**
 * Navigation metadata used to attribute normalized evidence.
 */
export interface QueryEvidenceNavigationViewModel {
    /** Stable source path suitable for attribution or navigation. */
    readonly path: string;

    /** CLI command that reads the source. */
    readonly readCommand: string;

    /** Navigable source structure segments. */
    readonly structure: readonly string[];

    /** Optional source-local line number. */
    readonly lineNumber: number | null;
}

/**
 * Immutable render-ready identity for one query evidence item.
 */
export interface QueryEvidenceViewModel {
    /** Stable evidence identity used for keyed rendering. */
    readonly id: string;

    /** Source-local entity identifier used for route targeting and media URLs. */
    readonly resourceId: string;

    /** Canonical route target interpreted by the destination layout. */
    readonly target: Readonly<Record<string, unknown>>;

    /** Canonical source family. */
    readonly source: string;

    /** Retrieval mechanism that produced the evidence. */
    readonly mechanism: string;

    /** Semantic title shown to the reader. */
    readonly title: string;

    /** Markdown content rendered for the evidence body. */
    readonly markdown: string;

    /** Source identity and ownership metadata. */
    readonly origin: QueryEvidenceOriginViewModel;

    /** Source navigation metadata. */
    readonly navigation: QueryEvidenceNavigationViewModel;

    /** Comparable and display-ready date, when available. */
    readonly date: QueryEvidenceDateViewModel | null;

    /** Backend relevance score, when available. */
    readonly rank: number | null;

    /** Stable order within its source/mechanism/date presentation group. */
    readonly order: number;
}

/**
 * Immutable grouping contract for source → mechanism → date presentation.
 */
export interface QueryEvidenceGroupViewModel {
    /** Canonical source family shared by all group items. */
    readonly source: string;

    /** Retrieval mechanism shared by all group items. */
    readonly mechanism: string;

    /** Comparable/display date shared by the group, when applicable. */
    readonly date: QueryEvidenceDateViewModel | null;

    /** Evidence items retained in normalized presentation order. */
    readonly items: readonly QueryEvidenceViewModel[];

    /** Number of evidence items in the group. */
    readonly count: number;

    /** Stable order of the group within its parent presentation. */
    readonly order: number;
}

/**
 * Evidence bucket grouped by its source family and retrieval mechanism.
 *
 * The property itself is readonly while the backing array remains mutable for
 * the existing QueryView grouping loop; immutable presentation groups use
 * {@link QueryEvidenceGroupViewModel}.
 */
export interface QueryGroup {
    /** Canonical source family shared by all bucket items. */
    readonly source: string;

    /** Retrieval mechanism shared by all bucket items. */
    readonly mechanism: string;

    /** Evidence items retained in server relevance order. */
    readonly items: QueryEvidence[];
}
