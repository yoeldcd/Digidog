/** Resolve a query source to its application route. */
import type { RouteId } from "../../../application/shell/contracts/shell-contracts.ts";

/** Return a safe route for a source family. */
export function sourceRoute(source: string): RouteId | null {
    const routes: Readonly<Record<string, RouteId>> = { memory: "memory", knowledge: "knowledge", messages: "messages", pictures: "pictures", backlog: "backlog", logs: "logs", profiles: "profiles", wikis: "wikis" };
    return routes[source.toLocaleLowerCase()] ?? null;
}
