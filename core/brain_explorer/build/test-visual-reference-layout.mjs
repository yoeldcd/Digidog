/**
 * @author Yoel David <yoeldcd@gmail.com>
 * @see https://x.com/SAY6267
 */

import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";

const viewSource = await readFile(new URL("../src/presentation/backlog/layouts/backlog-view.ts", import.meta.url), "utf8");
const editorSource = await readFile(new URL("../src/presentation/backlog/layouts/visual-reference-editor.ts", import.meta.url), "utf8");
const controllerSource = await readFile(new URL("../src/presentation/backlog/controllers/backlog-visual-reference-controller.ts", import.meta.url), "utf8");
const styles = await readFile(new URL("../src/styles/views.css", import.meta.url), "utf8");

assert.doesNotMatch(
    controllerSource,
    /imgUploadZone\.style\.display\s*=\s*["']grid["']/,
    "The visual-reference controller must not override its flex layout with an inline grid."
);
assert.match(
    controllerSource,
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
    /\.marking-container\s*>\s*canvas\s*\{[^}]*max-width:\s*100%;[^}]*max-height:\s*100%;[^}]*width:\s*auto;[^}]*height:\s*auto;/s,
    "The natural-ratio canvas must fit the editor without stretching."
);
assert.match(editorSource, /<canvas data-role="marking-canvas"/, "The editor must use one canvas for image and mark rendering.");
assert.doesNotMatch(editorSource, /id="marking-svg"/, "A separate SVG overlay must not introduce a second coordinate system.");
assert.match(
    editorSource,
    /this\.#renderCanvas\(false\)[\s\S]*canvas\.toDataURL\("image\/png"\)/,
    "Export must use the same canvas renderer as the interactive preview."
);
assert.match(
    viewSource,
    /reader\.onload\s*=\s*\(\)\s*=>\s*\{[\s\S]*visualReferenceDialog\.showModal\(\);[\s\S]*const result = reader\.result;[\s\S]*typeof result !== "string"[\s\S]*this\.#visualReferenceController\.displayImage\(result\)/,
    "Pasting an image into the task description must open the marking editor with that image loaded."
);

const toolbarStart = editorSource.indexOf('<div class="marking-toolbar">');
const toolbarEnd = editorSource.indexOf("</div>", toolbarStart);
const toolbarMarkup = editorSource.slice(toolbarStart, toolbarEnd);
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
assert.match(editorSource, /<option value="label">LABEL<\/option>/, "LABEL must be an independent marking tool.");
assert.match(controllerSource, /fileInput\.disabled\s*=\s*hasImage/, "The native file chooser must remain disabled while editing marks.");
assert.match(editorSource, /filter\(mark\s*=>\s*mark\.type\s*!==\s*"label"\)/, "Standalone labels must not consume geometric mark numbers.");
assert.match(editorSource, /selected\?\.type\s*!==\s*"label"/, "The label field may edit only a selected LABEL mark.");
assert.doesNotMatch(editorSource, /data-action="clear-marks"/, "The editor must not expose destructive clear-all behavior.");
assert.match(styles, /\.mark-delete-control:not\(:disabled\):hover\s*\{[^}]*color:\s*var\(--danger\)/s, "The enabled delete icon must use the red hover treatment.");
assert.match(styles, /\.marking-toolbar\s*\{[^}]*grid-template-columns:\s*auto auto minmax\(130px, 180px\) minmax\(180px, 1fr\)/s, "The label control must receive the remaining toolbar space.");

console.log("visual reference layout contract passed");
