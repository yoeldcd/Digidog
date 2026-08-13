/**
 * Audit TypeScript modules and exported symbols for missing code dependents.
 *
 * The TypeScript compiler already reports unused private/local declarations when
 * `noUnusedLocals` and `noUnusedParameters` are enabled. This companion audit
 * closes the compiler's intentional gap for exported declarations and orphaned
 * modules, which are otherwise assumed to be consumed by an external package.
 */

import { readFile } from "node:fs/promises";
import { dirname, relative, resolve, sep } from "node:path";
import { fileURLToPath } from "node:url";
import typescript from "typescript";

const repositoryRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const configPath = resolve(repositoryRoot, "tsconfig.json");
const configText = await readFile(configPath, "utf8");
const config = typescript.parseConfigFileTextToJson(configPath, configText);
if (config.error) throw new Error(typescript.flattenDiagnosticMessageText(config.error.messageText, "\n"));
const parsedConfig = typescript.parseJsonConfigFileContent(config.config, typescript.sys, repositoryRoot);
const program = typescript.createProgram(parsedConfig.fileNames, parsedConfig.options);
const checker = program.getTypeChecker();
const sourceRoot = resolve(repositoryRoot, "src");
const normalizedSourceRoot = sourceRoot.toLocaleLowerCase();
const entryModules = new Set([resolve(sourceRoot, "app.ts")]);
const sourceFiles = program.getSourceFiles().filter(file => (
    resolve(file.fileName).toLocaleLowerCase().startsWith(normalizedSourceRoot) && !file.isDeclarationFile
));
const sourceFileByPath = new Map(sourceFiles.map(file => [resolve(file.fileName), file]));
const moduleDependents = new Map(sourceFiles.map(file => [resolve(file.fileName), new Set()]));
const exportedSymbols = new Map();
const referenceCounts = new Map();
const duplicateExports = [];

/**
 * Return a stable, repository-relative path for diagnostics.
 */
function displayPath(path) {
    return relative(repositoryRoot, path).split(sep).join("/");
}

/**
 * Resolve aliases introduced by imports and exports to their declared symbol.
 */
function canonicalSymbol(symbol) {
    return symbol && (symbol.flags & typescript.SymbolFlags.Alias) ? checker.getAliasedSymbol(symbol) : symbol;
}

/**
 * Return whether an identifier is the declaration site of its parent node.
 */
function isDeclarationName(identifier) {
    return "name" in identifier.parent && identifier.parent.name === identifier;
}

for (const sourceFile of sourceFiles) {
    const seenNames = new Map();
    for (const statement of sourceFile.statements) {
        if (!typescript.canHaveModifiers(statement)) continue;
        const exported = typescript.getModifiers(statement)?.some(modifier => modifier.kind === typescript.SyntaxKind.ExportKeyword);
        if (!exported || !("name" in statement) || !statement.name || !typescript.isIdentifier(statement.name)) continue;
        const name = statement.name.text;
        const previousLine = seenNames.get(name);
        const line = sourceFile.getLineAndCharacterOfPosition(statement.name.getStart()).line + 1;
        if (previousLine !== undefined) duplicateExports.push(`${displayPath(sourceFile.fileName)}:${line} duplicates exported ${name} from line ${previousLine}`);
        else seenNames.set(name, line);
        const symbol = canonicalSymbol(checker.getSymbolAtLocation(statement.name));
        if (symbol) {
            exportedSymbols.set(symbol, { name, file: sourceFile.fileName, line });
            referenceCounts.set(symbol, 0);
        }
    }
    for (const statement of sourceFile.statements) {
        if (!typescript.isImportDeclaration(statement) || !typescript.isStringLiteral(statement.moduleSpecifier)) continue;
        const resolvedModule = typescript.resolveModuleName(
            statement.moduleSpecifier.text,
            sourceFile.fileName,
            parsedConfig.options,
            typescript.sys,
        ).resolvedModule;
        if (!resolvedModule) continue;
        const target = resolve(resolvedModule.resolvedFileName);
        if (sourceFileByPath.has(target)) moduleDependents.get(target)?.add(resolve(sourceFile.fileName));
    }
}

/**
 * Recursively count semantic identifier references to audited exported symbols.
 */
function countReferences(node) {
    if (typescript.isIdentifier(node) && !isDeclarationName(node)) {
        const symbol = canonicalSymbol(checker.getSymbolAtLocation(node));
        if (symbol && referenceCounts.has(symbol)) referenceCounts.set(symbol, (referenceCounts.get(symbol) || 0) + 1);
    }
    typescript.forEachChild(node, countReferences);
}
sourceFiles.forEach(countReferences);

const orphanModules = [...moduleDependents]
    .filter(([path, dependents]) => !entryModules.has(path) && dependents.size === 0)
    .map(([path]) => displayPath(path));
const unusedExports = [...exportedSymbols]
    .filter(([symbol]) => (referenceCounts.get(symbol) || 0) === 0)
    .map(([, declaration]) => `${displayPath(declaration.file)}:${declaration.line} exported ${declaration.name}`);
const failures = [
    ...duplicateExports.map(item => `duplicate-export: ${item}`),
    ...orphanModules.map(item => `orphan-module: ${item}`),
    ...unusedExports.map(item => `unused-export: ${item}`),
];

if (failures.length) {
    console.error(`Dead-code audit failed with ${failures.length} violation(s):`);
    failures.forEach(failure => console.error(`- ${failure}`));
    process.exitCode = 1;
} else {
    console.log(`Dead-code audit passed: ${sourceFiles.length} modules and ${exportedSymbols.size} exports have dependents.`);
}
