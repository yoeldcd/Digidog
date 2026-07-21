import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";

import {
    descriptionEntityValues,
    parseDescriptionSections,
    renderDescriptionCard
} from "../src/presentation/shared/components/description-card.ts";

const source = "**Subjects:** Yoi and Angi. **Setting:** A desk with a laptop.\n**Visible Objects:** - Laptop. - Cup.";
const sections = parseDescriptionSections(source);

assert.deepEqual(sections.map(section => section.title), ["Subjects", "Setting", "Visible Objects"]);
assert.equal(sections[0].body, "Yoi and Angi.");
assert.equal(sections[1].body, "A desk with a laptop.");
assert.match(sections[2].body, /Laptop/);

const rendered = renderDescriptionCard(source, { title: "Image analysis" });
assert.match(rendered, /class="description-card"/);
assert.match(rendered, /<details class="description-card-section" open>/);
assert.match(rendered, /3 sections/);
assert.match(rendered, /<span>Subjects<\/span>/);
assert.match(rendered, /class="description-entity-badge"/);
assert.match(rendered, /data-entity-label="Yoi"/);
assert.match(rendered, /data-entity-label="Angi"/);
assert.doesNotMatch(rendered, /<script/i);

assert.deepEqual(descriptionEntityValues(sections[0]), ["Yoi", "Angi"]);
const mainSubjects = parseDescriptionSections("**Main Subjects:** Yoi, Angi.")[0];
assert.deepEqual(descriptionEntityValues(mainSubjects), ["Yoi", "Angi"]);
assert.match(renderDescriptionCard("**Main Subjects:** Yoi, Angi."), /data-entity-label="Yoi"[\s\S]*data-entity-label="Angi"/);
assert.deepEqual(descriptionEntityValues({ id: "tags-1", title: "Semantic Tags", body: "familiarity, love." }), ["familiarity", "love"]);
const listSection = parseDescriptionSections("**Visible Objects:** - Laptop. - Cup.")[0];
assert.equal(listSection.body, "- Laptop.\n- Cup.");
assert.match(renderDescriptionCard("**Visible Objects:** - Laptop. - Cup."), /<ul><li>Laptop\.<\/li><li>Cup\.<\/li><\/ul>/);

const plain = parseDescriptionSections("One uninterrupted description.");
assert.deepEqual(plain.map(section => section.title), ["Description"]);

const styles = await readFile(new URL("../src/styles/views.css", import.meta.url), "utf8");
assert.match(styles, /\.description-card\s*\{[^}]*min-width:\s*0[^}]*max-width:\s*100%[^}]*overflow:\s*hidden/s);
assert.match(styles, /\.description-card-body\s*\{[^}]*max-height:\s*20rem[^}]*overflow:\s*auto[^}]*overflow-wrap:\s*anywhere/s);
assert.match(styles, /\.node-inspector\s*\{[^}]*grid-auto-rows:\s*max-content/s);
assert.match(styles, /\.description-card-body\s*\{[^}]*font-size:\s*15px/s);
assert.match(styles, /\.description-entity-badge\s*\{[^}]*border-radius:\s*999px/s);

console.log("Description card contract passed.");
