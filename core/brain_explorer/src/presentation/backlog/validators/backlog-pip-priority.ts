/**
 * Runtime validation helpers for backlog PiP form values.
 *
 * Browser form controls expose arbitrary strings even when their current HTML
 * options are closed. This validator establishes the runtime boundary required
 * before a string may enter the strongly typed presentation model.
 *
 * @module presentation/backlog/validators/backlog-pip-priority
 */

import type { BacklogPipPriority } from "../view_models/backlog-pip-view-model.ts";

/**
 * Closed set of priority values accepted by the backlog application contract.
 */
const BACKLOG_PIP_PRIORITIES: ReadonlySet<string> = new Set(["HIGH", "MEDIUM", "LOW"]);

/**
 * Determines whether an untrusted browser value is a supported task priority.
 *
 * @param {unknown} value Arbitrary value read from a DOM form control or external caller.
 * @returns {boolean} `true` when `value` belongs to the supported priority union.
 */
export function isBacklogPipPriority(value: unknown): value is BacklogPipPriority {
    return typeof value === "string" && BACKLOG_PIP_PRIORITIES.has(value);
}
