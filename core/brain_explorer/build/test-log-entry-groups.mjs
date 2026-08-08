import assert from "node:assert/strict";
import { projectLogEntryGroups } from "../src/presentation/logs/projectors/log-entry-group-projector.ts";

const entries = [
    { id: "1", domain: "brain.ui", date: "22-07-2026", timestamp: 2 },
    { id: "2", domain: "agent", date: "22-07-2026", timestamp: 1 },
    { id: "3", domain: "brain.ui", date: "21-07-2026", timestamp: 0 },
];

const domains = projectLogEntryGroups(entries, "domain");
assert.deepEqual(domains.map(group => group.label), ["agent", "brain.ui"]);
assert.deepEqual(domains[1].entries.map(entry => entry.id), ["1", "3"]);

const dates = projectLogEntryGroups(entries, "date");
assert.deepEqual(dates.map(group => group.label), ["22-07-2026", "21-07-2026"]);
assert.deepEqual(dates[0].entries.map(entry => entry.id), ["1", "2"]);

console.log("log entry grouping contract passed");
