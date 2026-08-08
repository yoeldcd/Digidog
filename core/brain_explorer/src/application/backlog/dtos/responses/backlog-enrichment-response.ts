/**
 * Typed response contracts for profile-aware backlog enrichment.
 *
 * @module backlog-enrichment-response
 */
import type { BacklogTask } from "./backlog-response.ts";

/**
 * Model execution metadata exposed after enriching one task.
 */
export interface BacklogEnrichmentMetadata {
    /**
     * Primary profile used to frame the task specification.
     * @type {string}
     */
    profile: string;
    /**
     * Number of nested guideline documents included in the request.
     * @type {number}
     */
    guidelineCount: number;
    /**
     * Whether the model received the task's visual reference.
     * @type {boolean}
     */
    usedImage: boolean;
    /**
     * Configured multimodal model identifier.
     * @type {string}
     */
    model: string;
}

/**
 * Typed data envelope returned by the backlog enrichment mutation.
 */
export interface BacklogEnrichmentPayload {
    /**
     * Updated persistent task.
     * @type {BacklogTask}
     */
    task: BacklogTask;
    /**
     * Non-sensitive model execution metadata.
     * @type {BacklogEnrichmentMetadata}
     */
    enrichment: BacklogEnrichmentMetadata;
}

/**
 * Typed data envelope returned for a non-persistent task draft.
 */
export interface BacklogDraftEnrichmentPayload {
    /**
     * Enriched Markdown placed back into the task editor.
     * @type {string}
     */
    description: string;
    /**
     * Non-sensitive model execution metadata.
     * @type {BacklogEnrichmentMetadata}
     */
    enrichment: BacklogEnrichmentMetadata;
}
