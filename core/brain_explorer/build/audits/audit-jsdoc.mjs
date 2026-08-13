/**
 * @file Semantic JSDoc coverage gate for the Brain Explorer TypeScript source tree.
 *
 * The audit uses the TypeScript parser instead of text heuristics so comments are
 * associated with the declarations they actually document. It reports every
 * source module, class, interface, type alias, enum, function, method, accessor,
 * constructor, property, and named parameter that lacks an explicit contract.
 */

import { readdir, readFile } from "node:fs/promises";
import { extname, relative, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import typescript from "typescript";

/**
 * Absolute Brain Explorer project root resolved from this audit module.
 */
const PROJECT_ROOT = resolve(fileURLToPath(new URL("..", import.meta.url)));
/**
 * Absolute TypeScript source root covered by the strict compiler contract.
 */
const SOURCE_ROOT = resolve(PROJECT_ROOT, "src");
/**
 * Declaration kinds that own a distinct documentation contract.
 */
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

/**
 * @typedef {{ file: string, line: number, symbol: string, reason: string }} DocumentationViolation
 */

/**
 * Recursively enumerate TypeScript modules beneath one directory.
 *
 * @param {string} directory Absolute directory currently being traversed.
 * @returns {Promise<string[]>} Absolute `.ts` module paths in deterministic lexical order.
 */
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

/**
 * Return whether TypeScript associates a real JSDoc block with a declaration.
 *
 * @param {import("typescript").Node} node Parsed declaration node.
 * @returns {boolean} True when the declaration owns at least one JSDoc comment.
 */
function hasJsDoc(node) {
    return typescript.getJSDocCommentsAndTags(node).some(item => typescript.isJSDoc(item));
}

/**
 * Produce a stable human-readable declaration identity for diagnostics.
 *
 * @param {import("typescript").Node} node Parsed declaration node.
 * @param {import("typescript").SourceFile} sourceFile Owning source module.
 * @returns {string} Named symbol or normalized syntax-kind label.
 */
function symbolName(node, sourceFile) {
    if ("name" in node && node.name) return node.name.getText(sourceFile);
    if (typescript.isConstructorDeclaration(node)) return "constructor";
    return typescript.SyntaxKind[node.kind];
}

/**
 * Determine whether one named parameter is documented by its callable owner.
 *
 * Inline JSDoc attached directly to a parameter is accepted. Otherwise the
 * callable must own an `@param` tag whose name matches the declared identifier.
 * Destructured parameters require an owner-level `@param` tag but are reported
 * with their exact binding pattern so the omission remains actionable.
 *
 * @param {import("typescript").ParameterDeclaration} parameter Parameter declaration being audited.
 * @param {import("typescript").SignatureDeclaration} owner Callable declaration that owns the parameter.
 * @returns {boolean} True when a direct comment or matching `@param` tag exists.
 */
function parameterIsDocumented(parameter, owner) {
    if (hasJsDoc(parameter)) return true;
    const parameterName = parameter.name.getText();
    return typescript.getJSDocParameterTags(parameter).some(tag => tag.name.getText() === parameterName)
        || typescript.getJSDocCommentsAndTags(owner).some(item => (
            typescript.isJSDoc(item)
            && item.tags?.some(tag => typescript.isJSDocParameterTag(tag) && tag.name.getText() === parameterName)
        ));
}

/**
 * Append one normalized violation at the declaration's one-based source line.
 *
 * @param {DocumentationViolation[]} violations Mutable diagnostic collection.
 * @param {string} file Project-relative source-module path.
 * @param {import("typescript").Node} node Parsed node responsible for the violation.
 * @param {import("typescript").SourceFile} sourceFile Owning source module.
 * @param {string} symbol Stable diagnostic symbol name.
 * @param {string} reason Concrete missing-documentation contract.
 * @returns {void}
 */
function addViolation(violations, file, node, sourceFile, symbol, reason) {
    const line = sourceFile.getLineAndCharacterOfPosition(node.getStart(sourceFile)).line + 1;
    violations.push({ file, line, symbol, reason });
}

/**
 * Return structural or type-contract violations attached to one declaration.
 *
 * @param {import("typescript").Node} node Parsed declaration node.
 * @param {import("typescript").SourceFile} sourceFile Owning source module.
 * @returns {string[]} Multiline and explicit-type diagnostics for the declaration.
 */
function typedMultilineContractViolations(node, sourceFile) {
    const violations = [];
    const docs = typescript.getJSDocCommentsAndTags(node).filter(item => typescript.isJSDoc(item));
    for (const doc of docs) {
        const text = sourceFile.text.slice(doc.pos, doc.end);
        if (!text.includes("\n")) violations.push("JSDoc must use multiline form");
        for (const tag of doc.tags || []) {
            if (typescript.isJSDocParameterTag(tag) && !tag.typeExpression) {
                violations.push(`@param ${tag.name.getText(sourceFile)} is missing an explicit type`);
            }
            if (tag.kind === typescript.SyntaxKind.JSDocReturnTag && !tag.typeExpression) {
                violations.push("@returns is missing an explicit type");
            }
        }
    }
    if ((typescript.isPropertyDeclaration(node) || typescript.isPropertySignature(node))
        && docs.length
        && !docs.some(doc => doc.tags?.some(tag => tag.kind === typescript.SyntaxKind.JSDocTypeTag))) {
        violations.push("property JSDoc is missing @type");
    }
    return violations;
}

/**
 * Return duplicate parameter or return tags attached to one declaration.
 *
 * @param {import("typescript").Node} node Parsed declaration node.
 * @param {import("typescript").SourceFile} sourceFile Owning source module.
 * @returns {string[]} Duplicate tag diagnostics for the declaration.
 */
function duplicateContractTags(node, sourceFile) {
    const duplicates = [];
    const parameters = new Set();
    let returnSeen = false;
    for (const item of typescript.getJSDocCommentsAndTags(node)) {
        if (!typescript.isJSDoc(item)) continue;
        for (const tag of item.tags || []) {
            if (typescript.isJSDocParameterTag(tag)) {
                const name = tag.name.getText(sourceFile);
                if (parameters.has(name)) duplicates.push(`duplicate @param ${name}`);
                parameters.add(name);
            }
            if (tag.kind === typescript.SyntaxKind.JSDocReturnTag) {
                if (returnSeen) duplicates.push("duplicate @returns");
                returnSeen = true;
            }
        }
    }
    return duplicates;
}

/**
 * Audit every declaration and named callable parameter in one parsed module.
 *
 * @param {import("typescript").SourceFile} sourceFile Parsed TypeScript module.
 * @param {string} file Project-relative source-module path.
 * @returns {DocumentationViolation[]} Documentation violations discovered in the module.
 */
function auditSourceFile(sourceFile, file) {
    const violations = [];
    for (const match of sourceFile.text.matchAll(/\/\*\*[^\r\n]*\*\//g)) {
        const position = match.index || 0;
        const line = sourceFile.getLineAndCharacterOfPosition(position).line + 1;
        violations.push({ file, line, symbol: "<comment>", reason: "JSDoc must use multiline form" });
    }
    const firstStatement = sourceFile.statements[0];
    if (firstStatement && !hasJsDoc(firstStatement)) {
        addViolation(violations, file, firstStatement, sourceFile, "<module>", "missing module JSDoc");
    }
    const visit = node => {
        if (DOCUMENTED_KINDS.has(node.kind) && !hasJsDoc(node)) {
            addViolation(violations, file, node, sourceFile, symbolName(node, sourceFile), "missing declaration JSDoc");
        }
        if (DOCUMENTED_KINDS.has(node.kind)) {
            for (const reason of [
                ...typedMultilineContractViolations(node, sourceFile),
                ...duplicateContractTags(node, sourceFile),
            ]) {
                addViolation(violations, file, node, sourceFile, symbolName(node, sourceFile), reason);
            }
        }
        if (DOCUMENTED_KINDS.has(node.kind) && typescript.isFunctionLike(node)) {
            for (const parameter of node.parameters) {
                if (!parameterIsDocumented(parameter, node)) {
                    addViolation(violations, file, parameter, sourceFile, parameter.name.getText(sourceFile), `parameter of ${symbolName(node, sourceFile)} is undocumented`);
                }
            }
        }
        typescript.forEachChild(node, visit);
    };
    typescript.forEachChild(sourceFile, visit);
    return violations;
}

/**
 * Absolute source-module paths audited during this invocation.
 */
const modulePaths = await listTypeScriptModules(SOURCE_ROOT);
/**
 * Complete documentation diagnostics accumulated across all source modules.
 */
const violations = [];
for (const modulePath of modulePaths) {
    const sourceText = await readFile(modulePath, "utf8");
    const sourceFile = typescript.createSourceFile(modulePath, sourceText, typescript.ScriptTarget.Latest, true, typescript.ScriptKind.TS);
    const file = relative(PROJECT_ROOT, modulePath).replaceAll("\\", "/");
    violations.push(...auditSourceFile(sourceFile, file));
}

if (violations.length) {
    console.error(`JSDoc audit failed with ${violations.length} violation(s):`);
    for (const violation of violations) {
        console.error(`- ${violation.file}:${violation.line} ${violation.symbol}: ${violation.reason}`);
    }
    process.exitCode = 1;
} else {
    console.log(`JSDoc audit passed: ${modulePaths.length} TypeScript modules have typed multiline declaration and parameter contracts.`);
}
