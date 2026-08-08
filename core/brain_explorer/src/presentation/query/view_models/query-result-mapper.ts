/** Canonical query response mapper for presentation consumers. */
import type { QueryEvidence, QueryResultData } from "../../../application/query/dtos/responses/query-response.ts";
import type { QueryEvidenceViewModel } from "./query-view-model.ts";

/** Immutable mapped response state. */
export interface MappedQueryResponse {
    readonly response: string;
    readonly items: readonly QueryEvidenceViewModel[];
    readonly page: number;
    readonly pageSize: number;
    readonly totalItems: number;
    readonly totalPages: number;
    readonly hasPrevious: boolean;
    readonly hasNext: boolean;
    readonly countsBySource: Readonly<Record<string, number>>;
}

/** Map canonical items and pagination metadata, retaining nested aliases safely. */
export function mapQueryResponse(data: QueryResultData | QueryEvidence[]): MappedQueryResponse {
    const payload: QueryResultData = Array.isArray(data) ? { items: data } : data;
    const rawItems: readonly QueryEvidence[] = payload.items ?? payload.results ?? payload.matches ?? [];
    const pageSize: number = payload.pageSize ?? 25;
    const totalItems: number = payload.totalItems ?? rawItems.length;
    const totalPages: number = payload.totalPages ?? Math.max(1, Math.ceil(totalItems / pageSize));
    const page: number = payload.page ?? 1;
    const items: readonly QueryEvidenceViewModel[] = rawItems.map((item, index) => {
        const content = item.content ?? {};
        const data = item.data ?? {};
        const nested = item.content ?? item.data ?? {};
        const reference = item.sourceRef ?? item.source_ref ?? {};
        const source = item.source ?? item.source_type ?? item.sourceType ?? reference.source_type ?? reference.sourceType ?? "unknown";
        const id = item.id ?? data.id ?? content.id ?? `${item.path ?? reference.path ?? source}:${index}`;
        const dataRecord = data as Readonly<Record<string, unknown>>;
        const sourceType = String(item.source_type ?? item.sourceType ?? reference.source_type ?? source);
        const rawTitle = String(item.title ?? nested.title ?? reference.title ?? item.path ?? item.kind ?? "Result");
        const title = normalizedEvidenceTitle(rawTitle, sourceType);
        const rawMarkdown = String(item.body ?? item.excerpt ?? item.text ?? nested.body ?? nested.excerpt ?? item.description ?? "No excerpt available");
        const rawDate = evidenceDate(item, dataRecord, nested, sourceType);
        const parsedDate = parseEvidenceDate(rawDate);
        const markdown = stripDuplicatedDateHeading(rawMarkdown, sourceType);
        const resourceId = String(id);
        const target = queryTarget(
            source,
            data as Readonly<Record<string, unknown>>,
            reference as Readonly<Record<string, unknown>>,
            resourceId,
            title,
            String(rawDate || ""),
        );

        return { id: `${source}:${id}`, resourceId, target, source, mechanism: item.mechanism ?? "unknown", title, markdown, origin: { source, mechanism: item.mechanism ?? "unknown", scope: item.scope ?? reference.scope ?? "", sourceType, domain: item.domain ?? reference.domain ?? "", title }, navigation: { path: item.path ?? reference.path ?? item.location ?? nested.location ?? "", readCommand: reference.read_command ?? reference.readCommand ?? "", structure: reference.structure ?? [], lineNumber: reference.line_number ?? reference.lineNumber ?? null }, date: parsedDate ? { comparable: parsedDate.toISOString(), display: parsedDate.toLocaleString() } : null, rank: item.rank ?? null, order: index };
    });
    return { response: payload.response ?? "", items, page, pageSize, totalItems, totalPages, hasPrevious: payload.hasPrevious ?? page > 1, hasNext: payload.hasNext ?? page < totalPages, countsBySource: payload.countsBySource ?? {} };
}

/** Normalize timestamps embedded by source adapters into localizable Date values. */
function parseEvidenceDate(rawDate: string): Date | null {
    if (!rawDate) return null;

    const direct = Date.parse(rawDate);
    if (!Number.isNaN(direct)) return new Date(direct);

    const dayFirst = rawDate.match(/^(\d{2})-(\d{2})-(\d{4})(?:\s+(.+))?$/);
    if (!dayFirst) return null;

    const [, day, month, year, time = "00:00"] = dayFirst;
    const normalized = `${year}-${month}-${day} ${time}`;
    const parsed = Date.parse(normalized);
    return Number.isNaN(parsed) ? null : new Date(parsed);
}

/** Select the canonical date fields exposed by message, log, and diary payloads. */
function evidenceDate(item: QueryEvidence, data: Readonly<Record<string, unknown>>, nested: QueryEvidence["content"] | QueryEvidence["data"], sourceType: string): string {
    if (sourceType === "diary") {
        const date = String(data.date || "");
        const time = String(data.time || "");
        return `${date} ${time}`.trim();
    }

    return String(item.date ?? item.timestamp ?? item.created_at ?? item.createdAt ?? item.updated_at ?? item.updatedAt ?? data.created_at ?? data.createdAt ?? data.timestamp ?? nested?.date ?? nested?.timestamp ?? "");
}

/** Remove transport timestamps from human-facing evidence titles. */
function normalizedEvidenceTitle(rawTitle: string, sourceType: string): string {
    if (sourceType === "messages") {
        return rawTitle.replace(/\s+at\s+\d{4}-\d{2}-\d{2}[T ][^\s]+$/i, "").trim() || "Avatar message";
    }

    if (sourceType === "diary" || sourceType === "logs") {
        return rawTitle.replace(/^\s*\d{2}-\d{2}-\d{4}(?:\s+\d{1,2}:\d{2}(?::\d{2})?\s*(?:am|pm)?)?\s*[-–—:]?\s*/i, "").trim() || (sourceType === "diary" ? "Diary entry" : "Log entry");
    }

    return rawTitle;
}

/** Avoid repeating a log or diary timestamp already promoted to the header badge. */
function stripDuplicatedDateHeading(markdown: string, sourceType: string): string {
    if (sourceType !== "diary" && sourceType !== "logs") return markdown;

    return markdown.replace(/^\s*(?:#{1,6}\s*)?\d{2}-\d{2}-\d{4}(?:\s+\d{1,2}:\d{2}(?::\d{2})?\s*(?:am|pm)?)?\s*(?:\r?\n|$)/i, "").trimStart();
}

/** Build a canonical semantic target owned and interpreted by the destination layout. */
function queryTarget(source: string, data: Readonly<Record<string, unknown>>, reference: Readonly<Record<string, unknown>>, id: string, title: string, rawDate: string): Readonly<Record<string, unknown>> {
    if (source === "memory") {
        const rawPath = String(data.path || reference.domain || "");
        return { path: rawPath.replace(/^memory\//, "").replace(/\.md$/, "").replaceAll("/", "."), domain: String(reference.domain || "") };
    }
    if (source === "knowledge") return { nodeId: String(data.entity_id || data.record_id || ""), relationId: String(data.relation_id || ""), entityLabel: title };
    if (source === "messages") {
        const timestamp = String(data.created_at || data.timestamp || rawDate || "");
        return { messageId: String(data.id || id), sessionId: String(data.session_id || ""), chatId: String(data.chat_id || ""), date: timestamp.slice(0, 10) };
    }
    if (source === "pictures") return { pictureId: String(data.id || id) };
    if (source === "logs") {
        const timestamp = String(data.timestamp || rawDate || "");
        const [date = "", ...timeParts] = timestamp.split(" ");
        return { domain: String(reference.domain || data.domain || ""), date, time: timeParts.join(" ") };
    }
    if (source === "backlog") return { taskId: String(data.id || id || title.match(/t\d+/i)?.[0] || "") };
    return { id };
}