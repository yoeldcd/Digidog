/**
 * @author Yoel David <yoeldcd@gmail.com>
 * @see https://x.com/SAY6267
 */

import assert from "node:assert/strict";

import { notificationText } from "../src/presentation/shared/utils/notification-message.ts";

const memoryNotice = notificationText(
    {
        ok: true,
        data: {
            ok: true,
            domain: "profiles",
            key: "academical_paper_critical",
            path: "D:/memory/profiles/academical_paper_critical.md",
        },
    },
    "POST",
    "POST /api/memory/entry",
);
assert.deepEqual(memoryNotice, {
    title: "Changes saved",
    message: "Memory “profiles.academical_paper_critical” was saved.",
});

const taskNotice = notificationText(
    {
        ok: true,
        data: {
            command: "set-task-status",
            task: { id: "t42", title: "Revisar contrato", status: "DONE" },
        },
    },
    "POST",
    "POST /api/backlog/task",
);
assert.equal(taskNotice.message, "Task “Revisar contrato” was completed.");

const jsonErrorNotice = notificationText(
    { ok: false, error: '{"ok":false,"error":"raw"}' },
    "POST",
    "POST /api/memory/entry",
);
assert.equal(
    jsonErrorNotice.message,
    "The operation could not be completed. Review the data and try again.",
);
assert.equal(jsonErrorNotice.message.startsWith("{"), false);
