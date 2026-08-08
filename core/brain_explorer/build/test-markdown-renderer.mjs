/**
 * @author Yoel David <yoeldcd@gmail.com>
 * @see https://x.com/SAY6267
 */

import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { renderMarkdown } from "../src/presentation/shared/utils/html.ts";

const flattened = renderMarkdown("1. Primero 2. Segundo 3. Tercero");
assert.match(flattened, /<ol><li>Primero<\/li><li>Segundo<\/li><li>Tercero<\/li><\/ol>/);

const syntax = renderMarkdown("[Acción narrativa] (acotación) {estado}");
assert.match(syntax, /narrative-square/);
assert.match(syntax, /narrative-round/);
assert.match(syntax, /narrative-curly/);
assert.match(syntax, /narrative-delimiter/);
assert.match(syntax, /narrative-content/);

const protectedSyntax = renderMarkdown("`[narrativa]` `(acotación)` `{estado}`");
assert.match(protectedSyntax, /narrative-square/);
assert.match(protectedSyntax, /narrative-round/);
assert.match(protectedSyntax, /narrative-curly/);
assert.doesNotMatch(protectedSyntax, /<code>/);

const blocks = renderMarkdown("## Título\n\n> Cita\n\n- [x] Hecho\n- Pendiente\n\n| A | B |\n|---|---|\n| 1 | 2 |");
assert.match(blocks, /<h2>Título<\/h2>/);
assert.match(blocks, /<blockquote>/);
assert.match(blocks, /task-list-item/);
assert.match(blocks, /<table>/);

const safe = renderMarkdown("`[código]` [sitio](https://example.com) <script>alert(1)</script>");
assert.match(safe, /narrative-square/);
assert.match(safe, /href="https:\/\/example\.com"/);
assert.doesNotMatch(safe, /<script>/);

const image = renderMarkdown("The evidence is ![Task visual reference](/api/backlog/image?taskId=t666).");
assert.match(image, /<img src="\/api\/backlog\/image\?taskId=t666" alt="Task visual reference" loading="lazy">/);
assert.doesNotMatch(image, /<a href=/, "Image tags must never fall through to the link renderer.");
const spacedImage = renderMarkdown("The evidence is ! [Task visual reference](/api/backlog/image?taskId=t666).");
assert.match(spacedImage, /<img src="\/api\/backlog\/image\?taskId=t666"/, "Persisted image tags tolerate accidental whitespace after the bang.");

const previousLocalStorage = Object.getOwnPropertyDescriptor(globalThis, "localStorage");
Object.defineProperty(globalThis, "localStorage", {
    configurable: true,
    value: {
        getItem(key) {
            return key === "active_project_path" ? "D:/workspace" : null;
        }
    }
});
try {
    const agentImage = renderMarkdown("![Agent](./$agent/pictures/task.png)");
    assert.match(agentImage, /<img src="\/api\/workspace\/image\?path=\.%2F%24agent%2Fpictures%2Ftask\.png&amp;workspaceRoot=D%3A%2Fworkspace" alt="Agent" loading="lazy">/);

    const fileImage = renderMarkdown("![File](file:///D:/workspace/pictures/task.png)");
    assert.match(fileImage, /<img src="\/api\/workspace\/image\?path=file%3A%2F%2F%2FD%3A%2Fworkspace%2Fpictures%2Ftask\.png&amp;workspaceRoot=D%3A%2Fworkspace" alt="File" loading="lazy">/);

    const windowsImage = renderMarkdown("![Windows](D:\\workspace\\pictures\\task.png)");
    assert.match(windowsImage, /<img src="\/api\/workspace\/image\?path=D%3A%5Cworkspace%5Cpictures%5Ctask\.png&amp;workspaceRoot=D%3A%2Fworkspace" alt="Windows" loading="lazy">/);

    const enclosedWindowsImage = renderMarkdown("![Picture](<D:/workspace/pictures/Angi design.png>)");
    assert.match(enclosedWindowsImage, /<img src="\/api\/workspace\/image\?path=D%3A%2Fworkspace%2Fpictures%2FAngi%20design\.png&amp;workspaceRoot=D%3A%2Fworkspace" alt="Picture" loading="lazy">/);
    assert.doesNotMatch(enclosedWindowsImage, /narrative-square|narrative-round/, "Parsed image tags must not fall through to narrative closures.");

    const escapedAttributes = renderMarkdown('![Task <visual>]($agent/pictures/task.png "Reference & proof")');
    assert.match(escapedAttributes, /alt="Task &lt;visual&gt;" title="Reference &amp; proof"/);

    const remoteImage = renderMarkdown('![Remote](https://cdn.example.test/image.png "Remote & title")');
    assert.match(remoteImage, /<img src="https:\/\/cdn\.example\.test\/image\.png" alt="Remote" title="Remote &amp; title" loading="lazy">/);

    const dataImage = renderMarkdown("![Data](data:image/png;base64,AAAA)");
    assert.match(dataImage, /<img src="data:image\/png;base64,AAAA" alt="Data" loading="lazy">/);

    const blobImage = renderMarkdown("![Blob](blob:https://example.test/opaque-id)");
    assert.match(blobImage, /<img src="blob:https:\/\/example\.test\/opaque-id" alt="Blob" loading="lazy">/);

    assert.doesNotMatch(agentImage + remoteImage, /crossorigin=/, "Image markup must not force anonymous CORS.");
    const unsafeImage = renderMarkdown("![Unsafe](javascript:alert(1))");
    assert.doesNotMatch(unsafeImage, /<img /, "Unsafe image schemes must be rejected.");

    const localLinks = renderMarkdown("[File](file:///D:/workspace/pictures/task.png) [Windows](D:\\workspace\\pictures\\task.png) [Agent](./$agent/pictures/task.png)");
    assert.doesNotMatch(localLinks, /<a href=/, "Local paths are accepted only by image Markdown.");
} finally {
    if (previousLocalStorage) {
        Object.defineProperty(globalThis, "localStorage", previousLocalStorage);
    } else {
        delete globalThis.localStorage;
    }
}

const styles = await readFile(new URL("../src/styles/views.css", import.meta.url), "utf8");
assert.match(styles, /\.rich-markdown ol,[\s\S]*display:\s*grid/);
assert.match(styles, /\.rich-markdown li\s*\{[\s\S]*display:\s*list-item/);
const markdownImageStyles = styles.match(/\.rich-markdown img\s*\{([^}]*)\}/)?.[1] ?? "";
assert.match(markdownImageStyles, /display:\s*block/);
assert.match(markdownImageStyles, /width:\s*auto/);
assert.match(markdownImageStyles, /max-width:\s*min\(100%,\s*70dvw\)/);
assert.match(markdownImageStyles, /max-height:\s*60dvh/);
assert.match(markdownImageStyles, /height:\s*auto/);
assert.match(markdownImageStyles, /margin:\s*\.8rem\s+auto/);
assert.match(markdownImageStyles, /object-fit:\s*contain/);
assert.match(styles, /\.narrative-square\s*\{[^}]*color:/);
assert.match(styles, /\.narrative-round\s*\{[^}]*color:/);
assert.match(styles, /\.narrative-curly\s*\{[^}]*color:/);
for (const className of ["square", "round", "curly"]) {
    const block = styles.match(new RegExp(`\\.narrative-${className}\\s*\\{([^}]*)\\}`))?.[1] ?? "";
    assert.doesNotMatch(block, /background|box-shadow|border/, `${className} closures must remain text-only.`);
}

const enrichedConsumers = [
    "../src/presentation/messages/layouts/messages-view.ts",
    "../src/presentation/logs/layouts/logs-view.ts",
    "../src/presentation/memory/layouts/memory-view.ts",
    "../src/presentation/profiles/layouts/profiles-view.ts",
    "../src/presentation/query/layouts/memory-result-renderer.ts",
    "../src/presentation/query/layouts/knowledge-result-renderer.ts",
    "../src/presentation/query/layouts/message-result-renderer.ts",
    "../src/presentation/query/layouts/log-result-renderer.ts",
    "../src/presentation/query/layouts/backlog-result-renderer.ts",
    "../src/presentation/knowledge/renderers/knowledge-inspector-renderer.ts",
    "../src/presentation/backlog/layouts/backlog-pip.ts",
    "../src/presentation/shared/components/description-card.ts",
];
for (const relativePath of enrichedConsumers) {
    const source = await readFile(new URL(relativePath, import.meta.url), "utf8");
    assert.match(source, /renderMarkdown\(/, `${relativePath} must use the shared enriched-content renderer.`);
}

console.log("markdown renderer contract passed");
