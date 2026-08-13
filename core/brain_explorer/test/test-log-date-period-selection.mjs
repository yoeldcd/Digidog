import assert from "node:assert/strict";
import { logDatePeriodSelection } from "../src/presentation/logs/validators/log-date-period-selection.ts";

assert.deepEqual(logDatePeriodSelection("logs-date:2026"), { from: "01-01-2026", to: "31-12-2026", label: "2026" });
assert.deepEqual(logDatePeriodSelection("logs-date:2026-07"), { from: "01-07-2026", to: "31-07-2026", label: "Julio 2026" });
assert.deepEqual(logDatePeriodSelection("logs-date:2024-02"), { from: "01-02-2024", to: "29-02-2024", label: "Febrero 2024" });
assert.deepEqual(logDatePeriodSelection("logs-date:2026-07-18"), { from: "18-07-2026", to: "18-07-2026", label: "18 Julio 2026" });
assert.equal(logDatePeriodSelection("logs-date-entry:invalid"), null);

console.log("Log date-period selection contract passed.");
