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
    /**
     * Whether the query is currently awaiting a server response.
     * @type {boolean | undefined}
     */
    loading?: boolean;
    /**
     * Whether the server completed the query successfully.
     * @type {boolean | undefined}
     */
    ok?: boolean;
    /**
     * Normalized answer and evidence rendered by the Query layout.
     * @type {QueryResultData | undefined}
     */
    data?: QueryResultData;
    /**
     * Human-readable request failure detail.
     * @type {string | undefined}
     */
    stderr?: string;
}

/**
 * Evidence bucket grouped by its source family and retrieval mechanism.
 */
export interface QueryGroup {
    /**
     * Canonical source family shared by all bucket items.
     * @type {string}
     */
    source: string;
    /**
     * Retrieval mechanism shared by all bucket items.
     * @type {string}
     */
    mechanism: string;
    /**
     * Evidence items retained in server relevance order.
     * @type {QueryEvidence[]}
     */
    items: QueryEvidence[];
}
