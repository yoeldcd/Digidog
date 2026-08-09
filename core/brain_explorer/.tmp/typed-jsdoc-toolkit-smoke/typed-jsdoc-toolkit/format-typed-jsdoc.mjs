import { readdir, readFile, writeFile } from "node:fs/promises";
import { extname, relative, resolve } from "node:path";
import typescript from "typescript";

const DOCUMENTED_KINDS = new Set([
    typescript.SyntaxKind.ClassDeclaration,
    typescript.SyntaxKind.InterfaceDeclaration,
    typescript.SyntaxKind.TypeAliasDeclaration,
    typescript.SyntaxKind.EnumDeclaration,
    typescript.SyntaxKind.FunctionDeclaration,
    typescript.SyntaxKind.MethodDeclaration,
    typescript.SyntaxKind.GetAccessor,
    typescript.SyntaxKind.SetAccessor,
    typescript.SyntaxKind.Constructor,
    typescript.SyntaxKind.PropertyDeclaration,
    typescript.SyntaxKind.PropertySignature,
    typescript.SyntaxKind.MethodSignature,
]);

function option(name, fallback) {
    const prefix = `--${name}=`;
    const token = process.argv.slice(2).find(value => value.startsWith(prefix));
    return token ? token.slice(prefix.length) : fallback;
}

const PROJECT_ROOT = resolve(option("project-root", process.cwd()));
const SOURCE_ROOT = resolve(PROJECT_ROOT, option("source-root", "src"));
const TSCONFIG_PATH = resolve(PROJECT_ROOT, option("tsconfig", "tsconfig.json"));
const JSON_OUTPUT = process.argv.includes("--json");

async function listTypeScriptModules(directory) {
    const entries = await readdir(directory, { withFileTypes: true });
    const modules = [];
    for (const entry of entries.sort((left, right) => left.name.localeCompare(right.name))) {
        const path = resolve(directory, entry.name);
        if (entry.isDirectory()) modules.push(...await listTypeScriptModules(path));
        else if (entry.isFile() && extname(entry.name) === ".ts") modules.push(path);
    }
    return modules;
}

function docsFor(node) {
    return typescript.getJSDocCommentsAndTags(node).filter(item => typescript.isJSDoc(item));
}

function declarationDoc(node) {
    return docsFor(node).at(-1) || null;
}

function typeText(checker, node) {
    return checker.typeToString(checker.getTypeAtLocation(node), node, typescript.TypeFormatFlags.NoTruncation);
}

function returnTypeText(checker, node) {
    const signature = checker.getSignatureFromDeclaration(node);
    return signature
        ? checker.typeToString(checker.getReturnTypeOfSignature(signature), node, typescript.TypeFormatFlags.NoTruncation)
        : "unknown";
}

function parameterTag(node, parameter, sourceFile) {
    const name = parameter.name.getText(sourceFile);
    return docsFor(node)
        .flatMap(doc => [...(doc.tags || [])])
        .find(tag => typescript.isJSDocParameterTag(tag) && tag.name.getText(sourceFile) === name) || null;
}

function returnTag(node) {
    return docsFor(node)
        .flatMap(doc => [...(doc.tags || [])])
        .find(tag => tag.kind === typescript.SyntaxKind.JSDocReturnTag) || null;
}

function typeTag(node) {
    return docsFor(node)
        .flatMap(doc => [...(doc.tags || [])])
        .find(tag => tag.kind === typescript.SyntaxKind.JSDocTypeTag) || null;
}

function normalizeJSDocBlocks(sourceText) {
    const normalized = sourceText.replace(/^([ \t]*)\/\*\*[\s\S]*?\*\/[ \t]*/gm, (block, openingIndent, offset, completeSource) => {
        const lineRemainder = completeSource.slice(offset + block.length).match(/^[^\r\n]*/)?.[0] || "";
        const declarationBreak = lineRemainder.trim() ? `\n${openingIndent}` : "";
        if (!block.includes("\n")) {
            const body = block.replace(/^\s*\/\*\*\s*/, "").replace(/\s*\*\/\s*$/, "").trim();
            return `${openingIndent}/**\n${openingIndent} * ${body}\n${openingIndent} */${declarationBreak}`;
        }
        const lines = block.trimEnd().split("\n");
        const openingContent = lines[0].replace(/^\s*\/\*\*\s*/, "").trim();
        lines[0] = `${openingIndent}/**`;
        if (openingContent) lines.splice(1, 0, `${openingIndent} * ${openingContent}`);
        const seenParameters = new Set();
        let returnSeen = false;
        const canonical = [];
        for (const line of lines) {
            const parameterMatch = line.match(/^\s*\*\s*@param\s+(?:\{(?:[^{}]|\{[^{}]*\})*\}\s+)?(\S+)/);
            if (parameterMatch) {
                if (seenParameters.has(parameterMatch[1])) continue;
                seenParameters.add(parameterMatch[1]);
            }
            if (/^\s*\*\s*@returns?\b/.test(line)) {
                if (returnSeen) continue;
                returnSeen = true;
            }
            canonical.push(line);
        }
        for (let index = 1; index < canonical.length - 1; index += 1) {
            const contentMatch = canonical[index].match(/^\s*\*(.*)$/);
            if (contentMatch) canonical[index] = `${openingIndent} *${contentMatch[1]}`;
        }
        canonical.pop();
        while (canonical.length > 1 && ["", "*"].includes(canonical.at(-1).trim())) canonical.pop();
        canonical.push(`${openingIndent} */`);
        return canonical.join("\n") + declarationBreak;
    });
    return normalized.replace(/^([ \t]*) \*\/\n\1 +(?=\S)/gm, "$1 */\n$1");
}

function collectTypeInsertions(sourceText, sourceFile, checker) {
    const insertions = [];
    const visit = node => {
        if (DOCUMENTED_KINDS.has(node.kind)) {
            const doc = declarationDoc(node);
            if (doc && typescript.isFunctionLike(node)) {
                for (const parameter of node.parameters) {
                    const tag = parameterTag(node, parameter, sourceFile);
                    if (tag && !tag.typeExpression) {
                        insertions.push({ position: tag.name.getStart(sourceFile), text: `{${typeText(checker, parameter)}} ` });
                    }
                }
                const tag = returnTag(node);
                if (tag && !tag.typeExpression) {
                    const start = tag.getStart(sourceFile);
                    const keyword = sourceText.slice(start, tag.end).match(/^@returns?\b/)?.[0];
                    if (keyword) insertions.push({ position: start + keyword.length, text: ` {${returnTypeText(checker, node)}}` });
                }
            }
            if (doc && (typescript.isPropertyDeclaration(node) || typescript.isPropertySignature(node)) && !typeTag(node)) {
                const lineStart = sourceText.lastIndexOf("\n", doc.pos - 1) + 1;
                const indent = sourceText.slice(lineStart, doc.pos).match(/^\s*/)?.[0] || "";
                insertions.push({ position: doc.end - 2, text: `\n${indent} * @type {${typeText(checker, node)}}\n${indent} ` });
            }
        }
        typescript.forEachChild(node, visit);
    };
    typescript.forEachChild(sourceFile, visit);
    return insertions;
}

function applyInsertions(sourceText, insertions) {
    let formatted = sourceText;
    for (const insertion of insertions.sort((left, right) => right.position - left.position)) {
        formatted = formatted.slice(0, insertion.position) + insertion.text + formatted.slice(insertion.position);
    }
    return normalizeJSDocBlocks(formatted);
}

const modulePaths = await listTypeScriptModules(SOURCE_ROOT);
const configFile = typescript.readConfigFile(TSCONFIG_PATH, typescript.sys.readFile);
if (configFile.error) throw new Error(typescript.flattenDiagnosticMessageText(configFile.error.messageText, "\n"));
const parsedConfig = typescript.parseJsonConfigFileContent(configFile.config, typescript.sys, PROJECT_ROOT);
const program = typescript.createProgram({ rootNames: parsedConfig.fileNames, options: parsedConfig.options });
const checker = program.getTypeChecker();
let changedModules = 0;
for (const modulePath of modulePaths) {
    const sourceFile = program.getSourceFile(modulePath);
    if (!sourceFile) throw new Error(`TypeScript program omitted ${modulePath}.`);
    const sourceText = await readFile(modulePath, "utf8");
    const formatted = applyInsertions(sourceText, collectTypeInsertions(sourceText, sourceFile, checker));
    if (formatted !== sourceText) {
        await writeFile(modulePath, formatted, "utf8");
        changedModules += 1;
    }
}
const result = { projectRoot: PROJECT_ROOT, sourceRoot: relative(PROJECT_ROOT, SOURCE_ROOT), modules: modulePaths.length, changedModules };
console.log(JSON_OUTPUT ? JSON.stringify(result, null, 2) : `Typed JSDoc formatting complete: ${changedModules} of ${modulePaths.length} module(s) changed.`);