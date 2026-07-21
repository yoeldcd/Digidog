import { spawn } from "node:child_process";
import { createHash } from "node:crypto";
import { mkdir, readdir, readFile, writeFile } from "node:fs/promises";
import { extname, relative, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import typescript from "typescript";

const PROJECT_ROOT = resolve(fileURLToPath(new URL("..", import.meta.url)));
const SOURCE_ROOT = resolve(PROJECT_ROOT, "src");
const SEMANTIC_HELPER = resolve(PROJECT_ROOT, "build/resolve-jsdoc-model.py");
const CACHE_PATH = resolve(PROJECT_ROOT, ".tmp/jsdoc-semantics-cache.json");
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

async function listTypeScriptModules(directory) {
    const entries = await readdir(directory, { withFileTypes: true });
    const paths = [];
    for (const entry of entries.sort((left, right) => left.name.localeCompare(right.name))) {
        const path = resolve(directory, entry.name);
        if (entry.isDirectory()) paths.push(...await listTypeScriptModules(path));
        else if (entry.isFile() && extname(entry.name) === ".ts") paths.push(path);
    }
    return paths;
}

function symbolName(node, sourceFile) {
    if ("name" in node && node.name) return node.name.getText(sourceFile);
    if (typescript.isConstructorDeclaration(node)) return "constructor";
    return typescript.SyntaxKind[node.kind];
}

function ownerName(node, sourceFile) {
    let parent = node.parent;
    while (parent) {
        if ((typescript.isClassDeclaration(parent) || typescript.isInterfaceDeclaration(parent)) && parent.name) {
            return parent.name.getText(sourceFile);
        }
        parent = parent.parent;
    }
    return "module";
}

function jsDocFor(node) {
    return typescript.getJSDocCommentsAndTags(node).filter(item => typescript.isJSDoc(item)).at(-1) || null;
}

function typeText(checker, node) {
    const type = checker.getTypeAtLocation(node);
    return checker.typeToString(type, node, typescript.TypeFormatFlags.NoTruncation);
}

function returnTypeText(checker, node) {
    const signature = checker.getSignatureFromDeclaration(node);
    return signature
        ? checker.typeToString(checker.getReturnTypeOfSignature(signature), node, typescript.TypeFormatFlags.NoTruncation)
        : "unknown";
}

function parameterTag(node, parameter, sourceFile) {
    const name = parameter.name.getText(sourceFile);
    return typescript.getJSDocCommentsAndTags(node)
        .filter(item => typescript.isJSDoc(item))
        .flatMap(doc => [...(doc.tags || [])])
        .find(tag => typescript.isJSDocParameterTag(tag) && tag.name.getText(sourceFile) === name) || null;
}

function returnTag(node) {
    return typescript.getJSDocCommentsAndTags(node)
        .filter(item => typescript.isJSDoc(item))
        .flatMap(doc => [...(doc.tags || [])])
        .find(tag => tag.kind === typescript.SyntaxKind.JSDocReturnTag) || null;
}

function typeTag(node) {
    return typescript.getJSDocCommentsAndTags(node)
        .filter(item => typescript.isJSDoc(item))
        .flatMap(doc => [...(doc.tags || [])])
        .find(tag => tag.kind === typescript.SyntaxKind.JSDocTypeTag) || null;
}

function missingParameters(node, sourceFile) {
    if (!typescript.isFunctionLike(node)) return [];
    return node.parameters.filter(parameter => {
        const name = parameter.name.getText(sourceFile);
        return !typescript.getJSDocParameterTags(parameter).some(tag => tag.name.getText(sourceFile) === name);
    });
}

function shouldDocumentReturn(node, sourceFile) {
    if (!typescript.isFunctionLike(node)
        || typescript.isConstructorDeclaration(node)
        || typescript.isSetAccessorDeclaration(node)) return false;
    const hasReturnTag = typescript.getJSDocCommentsAndTags(node).some(item => (
        typescript.isJSDoc(item)
        && item.tags?.some(tag => tag.kind === typescript.SyntaxKind.JSDocReturnTag)
    ));
    if (hasReturnTag) return false;
    const returnType = node.type?.getText(sourceFile).trim();
    if (returnType) return returnType !== "void" && returnType !== "never";
    let hasValueReturn = false;
    const visit = child => {
        if (typescript.isReturnStatement(child) && child.expression) hasValueReturn = true;
        if (!hasValueReturn) typescript.forEachChild(child, visit);
    };
    if (node.body) typescript.forEachChild(node.body, visit);
    return hasValueReturn;
}

function insertionPoint(node, sourceFile) {
    const start = node.getStart(sourceFile);
    const lineStart = sourceFile.text.lastIndexOf("\n", start - 1) + 1;
    const prefix = sourceFile.text.slice(lineStart, start);
    return /^\s*$/.test(prefix)
        ? { position: lineStart, indent: prefix }
        : { position: start, indent: "", inline: true };
}

function normalizedFragment(node, sourceFile) {
    const raw = node.getText(sourceFile).trim();
    return raw.length <= 6000 ? raw : `${raw.slice(0, 6000)}\n/* fragment truncated */`;
}

function signatureFor(node, sourceFile) {
    const fragment = node.getText(sourceFile).trim();
    const bodyStart = fragment.indexOf("{");
    return (bodyStart >= 0 ? fragment.slice(0, bodyStart) : fragment).slice(0, 1200).trim();
}

function semanticRequest({ id, file, kind, symbol, owner, signature, fragment, parameters, returns }) {
    const fingerprint = createHash("sha256").update(JSON.stringify({ signature, fragment, parameters, returns })).digest("hex").slice(0, 16);
    return { id: `${id}:${fingerprint}`, file, kind, symbol, owner, signature, fragment, parameters, returns };
}

function collectModuleWork(modulePath, sourceText, sourceFile, checker) {
    const file = relative(PROJECT_ROOT, modulePath).replaceAll("\\", "/");
    const work = [];
    const typeInsertions = [];
    const firstStatement = sourceFile.statements[0];
    if (firstStatement && !jsDocFor(firstStatement)) {
        const outline = sourceFile.statements
            .slice(0, 30)
            .map(statement => signatureFor(statement, sourceFile))
            .join("\n")
            .slice(0, 6000);
        work.push({
            type: "module",
            node: firstStatement,
            request: semanticRequest({
                id: `${file}:module`, file, kind: "module", symbol: "<module>", owner: "module",
                signature: file, fragment: outline, parameters: [], returns: false,
            }),
        });
    }
    const visit = node => {
        if (DOCUMENTED_KINDS.has(node.kind)) {
            const doc = jsDocFor(node);
            const missing = missingParameters(node, sourceFile).map(parameter => parameter.name.getText(sourceFile));
            const returns = shouldDocumentReturn(node, sourceFile);
            const parameterTypes = Object.fromEntries(
                typescript.isFunctionLike(node)
                    ? node.parameters.map(parameter => [parameter.name.getText(sourceFile), typeText(checker, parameter)])
                    : [],
            );
            const resolvedReturnType = typescript.isFunctionLike(node)
                && !typescript.isConstructorDeclaration(node)
                && !typescript.isSetAccessorDeclaration(node)
                ? returnTypeText(checker, node)
                : null;
            const resolvedPropertyType = typescript.isPropertyDeclaration(node) || typescript.isPropertySignature(node)
                ? typeText(checker, node)
                : null;
            if (doc && typescript.isFunctionLike(node)) {
                for (const parameter of node.parameters) {
                    const tag = parameterTag(node, parameter, sourceFile);
                    if (tag && !tag.typeExpression) {
                        typeInsertions.push({ position: tag.name.getStart(sourceFile), text: `{${typeText(checker, parameter)}} ` });
                    }
                }
                const tag = returnTag(node);
                if (tag && !tag.typeExpression && resolvedReturnType) {
                    const start = tag.getStart(sourceFile);
                    const keyword = sourceText.slice(start, tag.end).match(/^@returns?\b/)?.[0];
                    if (keyword) typeInsertions.push({ position: start + keyword.length, text: ` {${resolvedReturnType}}` });
                }
            }
            if (doc && resolvedPropertyType && !typeTag(node)) {
                const lineStart = sourceText.lastIndexOf("\n", doc.pos - 1) + 1;
                const indent = sourceText.slice(lineStart, doc.pos).match(/^\s*/)?.[0] || "";
                typeInsertions.push({ position: doc.end - 2, text: `\n${indent} * @type {${resolvedPropertyType}}\n${indent} ` });
            }
            if (!doc || missing.length || returns) {
                const symbol = symbolName(node, sourceFile);
                work.push({
                    type: doc ? "tags" : "declaration",
                    node,
                    doc,
                    missing,
                    returns,
                    parameterTypes,
                    resolvedReturnType,
                    resolvedPropertyType,
                    request: semanticRequest({
                        id: `${file}:${node.getStart(sourceFile)}:${symbol}`,
                        file,
                        kind: typescript.SyntaxKind[node.kind],
                        symbol,
                        owner: ownerName(node, sourceFile),
                        signature: signatureFor(node, sourceFile),
                        fragment: normalizedFragment(node, sourceFile),
                        parameters: missing,
                        returns,
                    }),
                });
            }
        }
        typescript.forEachChild(node, visit);
    };
    typescript.forEachChild(sourceFile, visit);
    return { file, sourceFile, work, typeInsertions };
}

function loadModelConfig() {
    return new Promise((resolvePromise, reject) => {
        const child = spawn("py", [SEMANTIC_HELPER], {
            cwd: PROJECT_ROOT,
            stdio: ["ignore", "pipe", "inherit"],
        });
        let output = "";
        child.stdout.setEncoding("utf8");
        child.stdout.on("data", chunk => { output += chunk; });
        child.on("error", reject);
        child.on("close", code => {
            if (code !== 0) {
                reject(new Error(`Semantic helper exited with code ${code}.`));
                return;
            }
            try {
                resolvePromise(JSON.parse(output));
            } catch (error) {
                reject(new Error(`Model-config helper returned invalid JSON: ${error.message}`));
            }
        });
    });
}

async function readSemanticCache() {
    try {
        const payload = JSON.parse(await readFile(CACHE_PATH, "utf8"));
        return payload && typeof payload === "object" ? payload : {};
    } catch (error) {
        if (error.code === "ENOENT") return {};
        throw error;
    }
}

async function writeSemanticCache(cache) {
    await mkdir(resolve(CACHE_PATH, ".."), { recursive: true });
    await writeFile(CACHE_PATH, JSON.stringify(cache, null, 2), "utf8");
}

function parseModelObject(text) {
    const stripped = String(text).trim();
    const fenced = stripped.match(/```(?:json)?\s*(\{[\s\S]*?\})\s*```/i);
    const object = fenced?.[1] || stripped.match(/\{[\s\S]*\}/)?.[0];
    if (!object) throw new Error("Gemma returned no JSON object.");
    const payload = JSON.parse(object);
    if (!payload || typeof payload !== "object" || Array.isArray(payload)) throw new Error("Gemma returned a non-object payload.");
    return payload;
}

function renderPrompt(template, request) {
    const fields = {
        file: request.file,
        kind: request.kind,
        symbol: request.symbol,
        owner: request.owner,
        signature: request.signature,
        parameters: JSON.stringify(request.parameters),
        returns: JSON.stringify(request.returns),
        fragment: request.fragment,
    };
    const normalizedTemplate = template.replaceAll("{{", "{").replaceAll("}}", "}");
    return Object.entries(fields).reduce((prompt, [name, value]) => prompt.replaceAll(`{${name}}`, value), normalizedTemplate);
}

function validateSemanticResponse(request, response) {
    if (typeof response.summary !== "string" || !response.summary.trim()) throw new Error("Response summary must be a non-empty string.");
    if (!response.parameters || typeof response.parameters !== "object" || Array.isArray(response.parameters)) {
        throw new Error("Response parameters must be an object.");
    }
    const parameters = {};
    for (const name of request.parameters) {
        if (typeof response.parameters[name] !== "string" || !response.parameters[name].trim()) {
            throw new Error(`Missing semantic description for parameter ${name}.`);
        }
        parameters[name] = response.parameters[name].trim();
    }
    if (request.returns && (typeof response.returns !== "string" || !response.returns.trim())) {
        throw new Error("Missing semantic return description.");
    }
    return {
        id: request.id,
        summary: response.summary.trim(),
        parameters,
        returns: typeof response.returns === "string" ? response.returns.trim() : null,
    };
}

async function requestOneSemantic(modelConfig, template, request) {
    const payload = {
        model: modelConfig.model,
        temperature: modelConfig.temperature,
        max_tokens: 900,
        messages: [
            {
                role: "system",
                content: "You analyze TypeScript semantics and return strict JSON fields for a deterministic documentation tool. Never write JSDoc, comment delimiters, tags, Markdown, or prose outside the JSON object.",
            },
            { role: "user", content: renderPrompt(template, request) },
        ],
    };
    let lastError;
    for (let attempt = 1; attempt <= 3; attempt += 1) {
        try {
            const response = await fetch(`${modelConfig.base_url.replace(/\/$/, "")}/chat/completions`, {
                method: "POST",
                headers: {
                    Authorization: `Bearer ${modelConfig.api_key}`,
                    "Content-Type": "application/json",
                },
                body: JSON.stringify(payload),
            });
            const responseText = await response.text();
            if (!response.ok) throw new Error(`OpenRouter HTTP ${response.status}: ${responseText.slice(0, 500)}`);
            const completion = JSON.parse(responseText);
            return validateSemanticResponse(request, parseModelObject(completion.choices?.[0]?.message?.content));
        } catch (error) {
            lastError = error;
        }
    }
    throw new Error(`Gemma failed to describe ${request.id}: ${lastError?.message}`);
}

async function requestSemantics(requests) {
    if (!requests.length) return new Map();
    const [modelConfig, template, cache] = await Promise.all([
        loadModelConfig(),
        readFile(resolve(PROJECT_ROOT, "build/templates/jsdoc-semantics.prompt.txt"), "utf8"),
        readSemanticCache(),
    ]);
    if (!modelConfig.model.includes("gemma-4")) throw new Error(`Configured text model is not Gemma 4: ${modelConfig.model}`);
    const results = new Map();
    const pending = [];
    for (const request of requests) {
        const cached = cache[request.id];
        if (cached) results.set(request.id, validateSemanticResponse(request, cached));
        else pending.push(request);
    }
    let completed = requests.length - pending.length;
    for (let index = 0; index < pending.length; index += 4) {
        const batch = pending.slice(index, index + 4);
        const responses = await Promise.all(batch.map(request => requestOneSemantic(modelConfig, template, request)));
        for (const response of responses) {
            results.set(response.id, response);
            cache[response.id] = response;
            completed += 1;
            console.error(`[${completed}/${requests.length}] ${response.id}`);
        }
        await writeSemanticCache(cache);
    }
    return results;
}

function cleanSentence(value, field) {
    if (typeof value !== "string" || !value.trim()) throw new Error(`Missing semantic ${field}.`);
    const cleaned = value.replaceAll("/**", "").replaceAll("*/", "").replace(/^[-*#\s]+/, "").trim();
    return /[.!?]$/.test(cleaned) ? cleaned : `${cleaned}.`;
}

function descriptionForParameter(semantic, name) {
    return cleanSentence(semantic.parameters?.[name], `parameter ${name}`);
}

function declarationDoc(item, semantic, sourceFile, indent) {
    const lines = ["/**", ` * ${cleanSentence(semantic.summary, "summary")}`];
    if (typescript.isFunctionLike(item.node)) {
        for (const parameter of item.node.parameters) {
            const name = parameter.name.getText(sourceFile);
            lines.push(` * @param {${item.parameterTypes[name]}} ${name} ${descriptionForParameter(semantic, name)}`);
        }
        if (item.returns) lines.push(` * @returns {${item.resolvedReturnType}} ${cleanSentence(semantic.returns, "return description")}`);
    }
    if (item.resolvedPropertyType) lines.push(` * @type {${item.resolvedPropertyType}}`);
    lines.push(" */");
    return lines.map(line => `${indent}${line}`).join("\n") + "\n";
}

function normalizeJSDocBlocks(sourceText) {
    return sourceText.replace(/^([ \t]*)\/\*\*[\s\S]*?\*\/[ \t]*/gm, (block, openingIndent, offset, completeSource) => {
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
        const normalized = [];
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
            normalized.push(line);
        }
        for (let index = 1; index < normalized.length - 1; index += 1) {
            if (!normalized[index].trim()) {
                normalized[index] = `${openingIndent} *`;
                continue;
            }
            const contentMatch = normalized[index].match(/^\s*\*(.*)$/);
            if (contentMatch) normalized[index] = `${openingIndent} *${contentMatch[1]}`;
        }
        normalized.pop();
        while (normalized.length > 1 && ["", "*"].includes(normalized.at(-1).trim())) normalized.pop();
        normalized.push(`${openingIndent} */`);
        return normalized.join("\n") + declarationBreak;
    });
}

function formatModule(sourceText, moduleWork, semantics) {
    const insertions = [...moduleWork.typeInsertions];
    for (const item of moduleWork.work) {
        const semantic = semantics.get(item.request.id);
        if (!semantic) throw new Error(`No semantic response for ${item.request.id}.`);
        if (item.type === "module") {
            const point = insertionPoint(item.node, moduleWork.sourceFile);
            const text = `/**\n * ${cleanSentence(semantic.summary, "module summary")}\n */\n`;
            insertions.push({ position: point.position, text });
            continue;
        }
        if (item.type === "declaration") {
            const point = insertionPoint(item.node, moduleWork.sourceFile);
            const generated = declarationDoc(item, semantic, moduleWork.sourceFile, point.indent);
            insertions.push({
                position: point.position,
                text: point.inline ? `${generated.trim().replaceAll("\n", " ")} ` : generated,
            });
            continue;
        }
        const lineStart = sourceText.lastIndexOf("\n", item.doc.pos - 1) + 1;
        const indent = sourceText.slice(lineStart, item.doc.pos).match(/^\s*/)?.[0] || "";
        const tags = [
            ...item.missing.map(name => ` * @param {${item.parameterTypes[name]}} ${name} ${descriptionForParameter(semantic, name)}`),
            ...(item.returns ? [` * @returns {${item.resolvedReturnType}} ${cleanSentence(semantic.returns, "return description")}`] : []),
        ];
        insertions.push({ position: item.doc.end - 2, text: `\n${tags.map(tag => indent + tag).join("\n")}\n${indent} ` });
    }
    let formatted = sourceText;
    for (const insertion of insertions.sort((left, right) => right.position - left.position)) {
        formatted = formatted.slice(0, insertion.position) + insertion.text + formatted.slice(insertion.position);
    }
    return normalizeJSDocBlocks(formatted).replace(/^([ \t]*) \*\/\n\1 +(?=\S)/gm, "$1 */\n$1");
}

const modulePaths = await listTypeScriptModules(SOURCE_ROOT);
const configPath = typescript.findConfigFile(PROJECT_ROOT, typescript.sys.fileExists, "tsconfig.json");
if (!configPath) throw new Error("TypeScript configuration not found.");
const configFile = typescript.readConfigFile(configPath, typescript.sys.readFile);
if (configFile.error) throw new Error(typescript.flattenDiagnosticMessageText(configFile.error.messageText, "\n"));
const parsedConfig = typescript.parseJsonConfigFileContent(configFile.config, typescript.sys, PROJECT_ROOT);
const program = typescript.createProgram({ rootNames: parsedConfig.fileNames, options: parsedConfig.options });
const checker = program.getTypeChecker();
const modules = [];
for (const modulePath of modulePaths) {
    const sourceText = await readFile(modulePath, "utf8");
    const sourceFile = program.getSourceFile(modulePath);
    if (!sourceFile) throw new Error(`TypeScript program omitted ${modulePath}.`);
    modules.push({ modulePath, sourceText, ...collectModuleWork(modulePath, sourceText, sourceFile, checker) });
}
const requests = modules.flatMap(module => module.work.map(item => item.request));
if (requests.length) console.error(`Requesting semantic fields for ${requests.length} recognized code fragment(s).`);
const semantics = requests.length ? await requestSemantics(requests) : new Map();
let changedModules = 0;
for (const module of modules) {
    const formatted = formatModule(module.sourceText, module, semantics);
    if (formatted !== module.sourceText) {
        await writeFile(module.modulePath, formatted, "utf8");
        changedModules += 1;
    }
}
console.log(requests.length
    ? `JSDoc formatting complete: ${changedModules} module(s) changed from ${requests.length} semantic response(s).`
    : `JSDoc formatting complete: ${changedModules} module(s) normalized; no semantic requests were required.`);
