import assert from "node:assert/strict";

import { KnowledgeGraphNormalizer } from "../src/presentation/knowledge/normalizers/knowledge-graph-normalizer.ts";

const ids = [];
const normalizer = new KnowledgeGraphNormalizer({
    mode: "all",
    scope: "global",
    nodeId(domain, label, index = 0) {
        const id = `${domain}:${label}:${index}`;
        ids.push(id);
        return id;
    },
});

const graph = normalizer.collect({
    entities: [{ name: "Yoi", source_path: "memory/relationships/family.md", description: "Father" }],
    classes: [{ id: "cls:person", name: "Person" }],
    relations: [{ source: "Yoi", target: "Person", predicate: "is_a" }],
});

assert.equal(graph.records.length, 2, "All mode must preserve both entities and classes.");
assert.equal(graph.records[0]?.domain, "relationships.family", "Memory paths must retain their canonical dotted domain.");
assert.equal(graph.records[0]?.visualType, "entity", "Entity payloads must retain entity rendering semantics.");
assert.equal(graph.records[1]?.visualType, "class", "Class payloads must retain class rendering semantics.");
assert.equal(graph.relations.length, 1, "Explicit relation arrays must remain visible.");
assert.equal(graph.relations[0]?.label, "is_a", "Relation predicates must remain the visible label.");
assert.ok(ids.length >= 3, "Missing record and endpoint identifiers must use the shared stable-id contract.");

const entityOnly = new KnowledgeGraphNormalizer({
    mode: "entities",
    scope: "local",
    nodeId: (domain, label, index = 0) => `${domain}:${label}:${index}`,
}).collect({
    entities: [
        { id: "entity:one", name: "One" },
        { id: "cls:ignored", name: "Ignored class", entity_type: "class" },
    ],
});

assert.deepEqual(entityOnly.records.map(record => record.label), ["One"], "Entity mode must continue excluding class-shaped records.");
assert.equal(entityOnly.records[0]?.knowledgeScope, "local", "The active scope must remain the fallback for records without scope metadata.");

const fallbackRelation = normalizer.collect({ relations: [{ label: "incomplete" }] });
assert.equal(fallbackRelation.relations.length, 1, "Explicit relation-array items must retain the legacy fallback endpoint behavior.");
assert.equal(fallbackRelation.relations[0]?.fromLabel, "Origen 1", "Missing source labels must retain their localized fallback.");
assert.equal(fallbackRelation.relations[0]?.toLabel, "Destino 1", "Missing target labels must retain their localized fallback.");

console.log("knowledge graph normalizer contract passed");
