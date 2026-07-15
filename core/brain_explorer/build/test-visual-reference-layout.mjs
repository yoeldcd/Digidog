import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";

const viewSource = await readFile(new URL("../src/presentation/components/backlog-view.ts", import.meta.url), "utf8");
const styles = await readFile(new URL("../src/styles/views.css", import.meta.url), "utf8");

assert.doesNotMatch(
    viewSource,
    /imgUploadZone\.style\.display\s*=\s*["']grid["']/,
    "The visual-reference controller must not override its flex layout with an inline grid."
);
assert.match(
    viewSource,
    /fileInput\.disabled\s*=\s*hasImage/,
    "The native file chooser must be disabled while an image is loaded."
);
assert.match(
    viewSource,
    /previewArea\.classList\.contains\(["']has-image["']\)\s*\|\|\s*fileInput\?\.disabled/,
    "Loaded canvas clicks must never invoke the native file chooser."
);
assert.match(
    styles,
    /\.visual-reference-upload\s*\{[^}]*display:\s*flex;[^}]*height:\s*100%;/s,
    "The upload region must consume the full available dialog height."
);
assert.match(
    styles,
    /\.image-preview-area\s*\{[^}]*flex:\s*1 1 0;[^}]*height:\s*100%;/s,
    "The empty dropzone must fill the remaining upload region."
);
assert.match(
    styles,
    /\.marking-container\s*\{[^}]*width:\s*100%;[^}]*height:\s*100%;/s,
    "The marking canvas must own its dimensions independently of the image."
);
assert.match(
    styles,
    /\.marking-container\s*>\s*img\s*\{[^}]*width:\s*100%;[^}]*height:\s*100%;[^}]*object-fit:\s*contain;/s,
    "The image must fit inside the canvas without determining its height."
);

const toolbarStart = viewSource.indexOf('<div class="marking-toolbar">');
const toolbarEnd = viewSource.indexOf("</div>", toolbarStart);
const toolbarMarkup = viewSource.slice(toolbarStart, toolbarEnd);
const toolbarActions = [
    "change-mark-color",
    "delete-selected-mark",
    "change-mark-shape",
    "change-mark-label"
];
assert.ok(toolbarStart >= 0, "The marking toolbar must exist.");
assert.deepEqual(
    toolbarActions.map(action => toolbarMarkup.indexOf(action)).every((position, index, positions) => position >= 0 && (index === 0 || position > positions[index - 1])),
    true,
    "Mark controls must be ordered as color, delete, shape, then label."
);
assert.match(viewSource, /<option value="label">LABEL<\/option>/, "LABEL must be an independent marking tool.");
assert.match(viewSource, /fileInput\.disabled\s*=\s*hasImage/, "The native file chooser must remain disabled while editing marks.");
assert.match(viewSource, /mark\.type\s*!==\s*"label"/, "Standalone labels must not consume geometric mark numbers.");
assert.match(viewSource, /selected\?\.type\s*===\s*"label"/, "The label field may edit only a selected LABEL mark.");
assert.doesNotMatch(viewSource, /data-action="clear-marks"/, "The editor must not expose destructive clear-all behavior.");
assert.match(styles, /\.mark-delete-control:not\(:disabled\):hover\s*\{[^}]*color:\s*var\(--danger\)/s, "The enabled delete icon must use the red hover treatment.");
assert.match(styles, /\.marking-toolbar\s*\{[^}]*grid-template-columns:\s*auto auto minmax\(130px, 180px\) minmax\(180px, 1fr\)/s, "The label control must receive the remaining toolbar space.");

console.log("visual reference layout contract passed");
