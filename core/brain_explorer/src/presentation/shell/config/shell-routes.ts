/**
 * Defines the immutable navigation registry used by the Brain Explorer shell.
 *
 * Keeping route composition outside the Web Component prevents the shell layout
 * from owning application configuration and gives routing consumers one typed,
 * independently testable source of truth.
 *
 * @module presentation/shell/config/shell-routes
 */

import { BacklogView } from "../../backlog/layouts/backlog-view.ts";
import { DashboardView } from "../../dashboard/layouts/dashboard-view.ts";
import { KnowledgeView } from "../../knowledge/layouts/knowledge-view.ts";
import { LogsView } from "../../logs/layouts/logs-view.ts";
import { MemoryView } from "../../memory/layouts/memory-view.ts";
import { MessagesView } from "../../messages/layouts/messages-view.ts";
import { PicturesView } from "../../pictures/layouts/pictures-view.ts";
import { ProfilesView } from "../../profiles/layouts/profiles-view.ts";
import { QueryView } from "../../query/layouts/query-view.ts";
import { SettingsView } from "../../settings/layouts/settings-view.ts";
import { WikisView } from "../../wikis/layouts/wikis-view.ts";
import type { ShellRouteViewModel } from "../view_models/app-shell-view-model.ts";
import type { RouteId } from "../../../application/shell/contracts/shell-contracts.ts";

/**
 * Route displayed when persisted navigation state is absent or invalid.
 *
 * The value satisfies the route contract without widening its literal route id,
 * which lets callers use it as both a fallback and the first registry entry.
 */
export const DEFAULT_SHELL_ROUTE = {
    id: "dashboard",
    label: "Project",
    icon: "home",
    element: DashboardView.selector
} satisfies ShellRouteViewModel;

/**
 * Ordered route registry rendered by the persistent application shell.
 *
 * Entries with `nav: false` remain routable but are intentionally omitted from
 * primary navigation because another interaction, such as search, opens them.
 */
export const SHELL_ROUTES: readonly ShellRouteViewModel[] = [
    DEFAULT_SHELL_ROUTE,
    { id: "messages", label: "Messages", icon: "messageCircle", element: MessagesView.selector },
    { id: "memory", label: "Memory", icon: "database", element: MemoryView.selector },
    { id: "knowledge", label: "Knowledge", icon: "graph", element: KnowledgeView.selector },
    { id: "pictures", label: "Pictures", icon: "camera", element: PicturesView.selector },
    { id: "query", label: "Results", icon: "search", element: QueryView.selector, nav: false },
    { id: "profiles", label: "Profiles", icon: "users", element: ProfilesView.selector },
    { id: "logs", label: "Logs", icon: "document", element: LogsView.selector },
    { id: "backlog", label: "Backlog", icon: "checkSquare", element: BacklogView.selector },
    { id: "wikis", label: "Wikis", icon: "book", element: WikisView.selector },
    { id: "settings", label: "Settings", icon: "settings", element: SettingsView.selector }
] satisfies ShellRouteViewModel[];

/**
 * Narrow a raw DOM attribute to an application route registered by the shell.
 *
 * @param {string | null} value Untrusted route value read from an element attribute.
 * @returns {boolean} True only when `value` is a non-null member of the immutable registry.
 */
export function isShellRouteId(value: string | null): value is RouteId {
    return value !== null && SHELL_ROUTES.some(route => route.id === value);
}
