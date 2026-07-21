/**
 * Runtime guards for heterogeneous Knowledge CLI payloads.
 */

import type { RawKnowledgeItem } from "../view_models/knowledge-view-model.ts";

/**
 * Determines whether an unknown transport value is a string-keyed object.
 * Arrays are excluded because Knowledge commands treat them as collections.
 *
 * @param {unknown} value Unknown value received from an API response.
 * @returns {boolean} `true` when named properties can be read safely.
 */
export function isRawKnowledgeItem(value: unknown): value is RawKnowledgeItem {
    return typeof value === "object" && value !== null && !Array.isArray(value);
}

/**
 * Keeps only object-like values from a heterogeneous transport array.
 *
 * @param {unknown} values Unknown collection returned by a Knowledge command.
 * @returns {RawKnowledgeItem[]} Strongly narrowed raw records ready for normalization.
 */
export function rawKnowledgeItems(values: unknown): RawKnowledgeItem[] {
    return Array.isArray(values) ? values.filter(isRawKnowledgeItem) : [];
}
