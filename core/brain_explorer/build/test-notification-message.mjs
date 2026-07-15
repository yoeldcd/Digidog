import assert from "node:assert/strict";

import { notificationText } from "../src/presentation/utils/notification-message.ts";

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
    title: "Cambios guardados",
    message: "Se guardó la memoria “profiles.academical_paper_critical”.",
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
assert.equal(taskNotice.message, "La tarea “Revisar contrato” quedó completada.");

const jsonErrorNotice = notificationText(
    { ok: false, error: '{"ok":false,"error":"raw"}' },
    "POST",
    "POST /api/memory/entry",
);
assert.equal(
    jsonErrorNotice.message,
    "La operación no pudo completarse. Revisa los datos e inténtalo de nuevo.",
);
assert.equal(jsonErrorNotice.message.startsWith("{"), false);
