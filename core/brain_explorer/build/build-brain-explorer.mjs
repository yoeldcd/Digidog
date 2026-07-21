/**
 * @author Yoel David <yoeldcd@gmail.com>
 * @see https://x.com/SAY6267
 */

import { copyFile, mkdir, readFile, writeFile } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import typescript from "typescript";

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const SRC_DIR = resolve(ROOT, "src");
const DIST_DIR = resolve(ROOT, "dist");
const ENTRY_TS = resolve(SRC_DIR, "app.ts");
const ENTRY_CSS = resolve(SRC_DIR, "styles", "brain-explorer.css");
const ENTRY_HTML = resolve(SRC_DIR, "index.html");

const modules = new Map();
/**
 * Ordered source-module chain currently being expanded by the static bundler.
 */
const activeModuleStack = [];
let moduleCounter = 0;

await mkdir(DIST_DIR, { recursive: true });
await writeFile(resolve(DIST_DIR, "brain-explorer.js"), await bundleEntry(ENTRY_TS), "utf8");
await writeFile(resolve(DIST_DIR, "brain-explorer.css"), compactCss(await bundleCss(ENTRY_CSS)), "utf8");
await copyFile(ENTRY_HTML, resolve(DIST_DIR, "index.html"));
await writeFile(resolve(DIST_DIR, "brain-explorer.bundle.json"), `${JSON.stringify(bundleManifest(), null, 2)}\n`, "utf8");

async function bundleEntry(path) {
    const moduleId = await bundleModule(path);
    return `"use strict";\n${[...modules.values()].map(record => record.code).join("\n")}\n${moduleId}();\n`.replace(/[ \t]+$/gm, "");
}

async function bundleModule(path) {
    const normalizedPath = normalizeModulePath(path);
    const cycleStart = activeModuleStack.indexOf(normalizedPath);
    if (cycleStart >= 0) {
        const cycle = [...activeModuleStack.slice(cycleStart), normalizedPath]
            .map(modulePath => modulePath.replace(`${SRC_DIR.replace(/\\/g, "/")}/`, "src/"));
        throw new Error(`Circular runtime dependency detected: ${cycle.join(" -> ")}`);
    }
    if (modules.has(normalizedPath)) {
        return modules.get(normalizedPath).id;
    }

    activeModuleStack.push(normalizedPath);
    const id = `__brainExplorerModule${moduleCounter++}`;
    modules.set(normalizedPath, { id, code: "" });
    try {
        const source = typescript.transpileModule(await readFile(normalizedPath, "utf8"), {
            fileName: normalizedPath,
            compilerOptions: {
                target: typescript.ScriptTarget.ES2022,
                module: typescript.ModuleKind.ESNext,
                allowImportingTsExtensions: true
            }
        }).outputText;
        const imports = [];
        const withoutImports = source.replace(/import\s*\{([\s\S]*?)\}\s*from\s*["']([^"']+)["'];?/g, (_match, names, specifier) => {
            imports.push({ names, path: resolveImport(normalizedPath, specifier) });
            return "";
        });
        const resolvedImports = [];
        for (const item of imports) {
            resolvedImports.push({ names: item.names, id: await bundleModule(item.path) });
        }
        const { code, exports } = stripExports(withoutImports);
        const importLines = resolvedImports.map(item => `const { ${destructureNames(item.names)} } = ${item.id}();`).join("\n");
        const exportLine = exports.length ? `return { ${exports.map(name => `${name}: ${name}`).join(", ")} };` : "return {};";
        modules.get(normalizedPath).code = `const ${id}=(()=>{let cache;return()=>{if(cache)return cache;\n${importLines}\n${code}\ncache=(()=>{${exportLine}})();return cache;};})();`;
        return id;
    } finally {
        activeModuleStack.pop();
    }
}

function stripTypeDeclarations(source) {
    return source
        .replace(/export\s+interface\s+[A-Za-z_$][\w$]*\s*\{[\s\S]*?\}\s*/g, "")
        .replace(/export\s+type\s+[A-Za-z_$][\w$]*\s*=\s*[\s\S]*?;\s*/g, "");
}

function stripExports(source) {
    const exports = new Set();
    let code = source.replace(/export\s+(class|function|async function)\s+([A-Za-z_$][\w$]*)/g, (_match, kind, name) => {
        exports.add(name);
        return `${kind} ${name}`;
    });
    code = code.replace(/export\s+(const|let|var)\s+([A-Za-z_$][\w$]*)/g, (_match, kind, name) => {
        exports.add(name);
        return `${kind} ${name}`;
    });
    code = code.replace(/export\s*\{([^}]+)\};?/g, (_match, names) => {
        parseNameList(names).forEach(item => exports.add(item.exported));
        return "";
    });
    return { code, exports: [...exports] };
}

function destructureNames(names) {
    return parseNameList(names).map(item => item.local === item.exported ? item.exported : `${item.exported}: ${item.local}`).join(", ");
}

function parseNameList(names) {
    return names
        .split(",")
        .map(name => name.trim())
        .filter(Boolean)
        .map(name => {
            const [exported, local = exported] = name.split(/\s+as\s+/).map(part => part.trim());
            return { exported, local };
        });
}

function resolveImport(fromPath, specifier) {
    const cleanSpecifier = specifier.split("?")[0];
    return normalizeModulePath(resolve(dirname(fromPath), cleanSpecifier));
}

function normalizeModulePath(path) {
    return resolve(path).replace(/\\/g, "/");
}

async function bundleCss(path, seen = new Set()) {
    const normalizedPath = normalizeModulePath(path);
    if (seen.has(normalizedPath)) {
        return "";
    }
    seen.add(normalizedPath);
    const source = await readFile(normalizedPath, "utf8");
    const parts = [];
    let cursor = 0;
    const importPattern = /@import\s+url\(["']?([^"')]+)["']?\);/g;
    let match = importPattern.exec(source);
    while (match) {
        parts.push(source.slice(cursor, match.index));
        parts.push(await bundleCss(resolve(dirname(normalizedPath), match[1]), seen));
        cursor = match.index + match[0].length;
        match = importPattern.exec(source);
    }
    parts.push(source.slice(cursor));
    return parts.join("\n");
}

function compactCss(source) {
    return source
        .replace(/\/\*[\s\S]*?\*\//g, "")
        .replace(/\s+/g, " ")
        .replace(/\s*([{}:;,>])\s*/g, "$1")
        .trim() + "\n";
}

function bundleManifest() {
    return {
        name: "brain_explorer",
        kind: "compiled-static-web-bundle",
        entrypoints: {
            html: "index.html",
            script: "brain-explorer.js",
            stylesheet: "brain-explorer.css"
        },
        generatedBy: "build/build-brain-explorer.mjs",
        sourceEntry: "src/app.ts"
    };
}
