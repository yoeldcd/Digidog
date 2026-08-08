import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";

const view = await readFile(new URL("../src/presentation/logs/layouts/logs-view.ts", import.meta.url), "utf8");
const dateProjector = await readFile(new URL("../src/presentation/logs/projectors/log-date-tree-projector.ts", import.meta.url), "utf8");
const groupProjector = await readFile(new URL("../src/presentation/logs/projectors/log-entry-group-projector.ts", import.meta.url), "utf8");
const tree = await readFile(new URL("../src/presentation/shared/components/structure-tree.ts", import.meta.url), "utf8");
const styles = await readFile(new URL("../src/styles/views.css", import.meta.url), "utf8");
const renameDialog = await readFile(new URL("../src/presentation/shared/components/domain-rename-dialog.ts", import.meta.url), "utf8");
const backlogView = await readFile(new URL("../src/presentation/backlog/layouts/backlog-view.ts", import.meta.url), "utf8");
const apiClient = await readFile(new URL("../src/infrastructure/shared/http/clients/brain-api-client.ts", import.meta.url), "utf8");

assert.match(view, /#treeMode(?:: LogsTreeMode)? = "domain"/);
assert.match(view, /id: "tree-domain"[^\n]*active: this\.#treeMode === "domain"/);
assert.match(view, /id: "tree-date"[^\n]*active: this\.#treeMode === "date"/);
assert.match(view, /#dateTreeNodes\(\)/);
assert.match(dateProjector, /LOG_MONTH_LABELS/);
assert.match(view, /projectLogDateTree\(this\.#indexEntries\)/);
assert.match(view, /sortDirection: this\.#treeMode === "date" \? "desc" : "asc"/);
assert.doesNotMatch(dateProjector, /presentation: "log"/, "Temporal branches must not expose unit logs as tree domains.");
assert.match(dateProjector, /children: groups/, "Temporal navigation must stop at calendar periods.");
assert.match(view, /if \(selection\.clickedCaret\) return;/, "Caret expansion must not hydrate log content.");
assert.match(view, /toggleOnBranchSelect: false/, "Branch selection and expansion must remain separate gestures.");
assert.match(view, /new Set<string>\(\[ALL_LOGS_PATH\]\)/, "Domain mode must open with the All logs root expanded.");
assert.match(view, /#expandDatePath\(selection\.path, true\)/, "Selecting a calendar period must reveal its subhierarchy.");
assert.match(view, /#loadLogs\(false, false\)/, "Calendar selection must reuse the API response cache.");
assert.match(view, /if \(selection\.branch\) this\.#expandedNodes\.add\(selection\.path\)/, "Selecting a domain branch must reveal its children.");
assert.match(view, /<details class="log-entry-card" data-log-entry data-log-domain=/);
assert.match(view, /targetEntry\.open = true[\s\S]*log-entry-summary[\s\S]*scrollIntoView/);
assert.doesNotMatch(view, /<details class="log-entry-card"\s+open/);
assert.match(view, /class="log-date-badge"/);
assert.match(view, /log-entry-chevron[\s\S]*log-entry-heading[\s\S]*log-date-badge/);
assert.match(view, /projectLogEntryGroups\(entries, this\.#logSeparatorMode\(\)\)/);
assert.match(view, /this\.#from \|\| this\.#to \|\| this\.#treeMode === "date"/);
assert.match(view, /hasSubdomain \? "domain" : "date"/);
assert.match(groupProjector, /mode === "domain"[\s\S]*localeCompare/);
assert.match(view, /data-separator="\$\{group\.mode\}"/);
assert.match(view, /<details class="subdomain-group log-entry-group" open/,
    "Log separators must reuse the Backlog collapsible group contract.");
assert.match(view, /<summary class="subdomain-group-header">[\s\S]*icon\("chevronRight"\)[\s\S]*subdomain-task-count[\s\S]*subdomain-line-separator/,
    "Log separators must preserve the Backlog header hierarchy, count, and rule.");
assert.match(view, /<div class="subdomain-group-content">/,
    "Log entries must be owned by the same collapsible content container as Backlog tasks.");
assert.doesNotMatch(styles, /\.log-group-separator/,
    "Logs must not maintain a visually divergent separator implementation.");
assert.match(styles, /\.subdomain-group:not\(\[open\]\) > \.subdomain-group-content\s*\{[^}]*display:\s*none !important/s,
    "The shared Backlog separator contract must hide grouped content when collapsed.");
assert.match(view, /class="log-entry-tags"/);
assert.match(view, /class="log-entry-body"/);

assert.match(tree, /aria-pressed=/);
assert.match(tree, /sortKey \|\| left\.label/);
assert.match(styles, /\.log-entry-summary\s*\{[^}]*grid-template-columns:\s*auto minmax\(0, 1fr\) minmax\(92px, 118px\)/s);
assert.match(styles, /\.log-date-badge\s*\{[^}]*white-space:\s*nowrap/s);
assert.match(styles, /\.log-entry-body\s*\{[^}]*grid-template-columns:\s*repeat\(auto-fit/s);
assert.match(styles, /\.log-entry-card\[open\] \.log-entry-chevron/);
assert.match(styles, /\.structure-tree-toolbar \.icon-action\.is-active/);
assert.match(view, /actions: isEntry \? \[\] : \[\{ id: "rename-domain"/,
    "Unit-log leaves must not expose the domain mutation action.");
assert.match(view, /const result = await this\.#api\.renameLogDomain[\s\S]*if \(!result\.ok\) return;/,
    "Log selection must only move after a successful server mutation.");
assert.match(backlogView, /const result = await this\.#api\.renameBacklogDomain[\s\S]*if \(!result\.ok\) return;/,
    "Backlog selection must only move after a successful server mutation.");
assert.match(view, /remapExpandedDomains\(this\.#expandedNodes, node\.path, target\)/);
assert.match(backlogView, /remapExpandedDomains\(this\.#expandedNodes, node\.path, target\)/);
assert.match(renameDialog, /class="domain-rename-dialog"/);
assert.match(renameDialog, /dialog\.returnValue === "confirm"/);
assert.match(apiClient, /request\("\/api\/logs\/domain", \{ method: "POST"/);
assert.match(apiClient, /request\("\/api\/backlog\/domain", \{ method: "POST"/);
assert.match(styles, /\.domain-rename-dialog\s*\{[\s\S]*width: clamp\(420px, 50dvw, 720px\)/);

console.log("Logs tree and collapsible-card contract passed.");
