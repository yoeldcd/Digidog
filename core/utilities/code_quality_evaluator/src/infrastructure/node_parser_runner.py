"""Run the pinned TypeScript ESTree parser over source supplied on stdin.

The runner deliberately keeps the subprocess boundary small: the executable and
parser entrypoint are absolute, the source is sent only through standard input,
and the returned JSON is bounded and source-redacted on failures.
"""

from __future__ import annotations

import json
import subprocess
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType
from typing import Final

NODE_EXECUTABLE: Final[Path] = Path(r"C:\Program Files\nodejs\node.exe")
"""Pinned absolute Node executable used for parser invocations."""

_PROJECT_ROOT: Final[Path] = Path(__file__).resolve().parents[2]
TYPESCRIPT_ESTREE_ENTRYPOINT: Final[Path] = (
    _PROJECT_ROOT
    / "node_modules"
    / "@typescript-eslint"
    / "typescript-estree"
    / "dist"
    / "index.js"
)
"""Pinned absolute @typescript-eslint/typescript-estree 8.66.0 entrypoint."""

_MAX_OUTPUT_BYTES: Final[int] = 262_144
_MAX_SOURCE_BYTES: Final[int] = 4_000_000


def _freeze(value: object) -> object:
    """Recursively freeze JSON values before exposing parser facts.

    Args:
        value: JSON-compatible value returned by the parser process.

    Returns:
        object: Immutable mapping, tuple, or scalar representation.
    """

    if isinstance(value, dict):
        return MappingProxyType(
            {str(key): _freeze(item) for key, item in value.items()}
        )

    if isinstance(value, list):
        return tuple(_freeze(item) for item in value)

    return value


_NODE_SCRIPT_TEMPLATE: Final[str] = r"""
const parser = require(PARSER_ENTRYPOINT);
const isTypeScript = LANGUAGE === "typescript";
let source = "";

function lineOf(value) {
  return value && value.loc && value.loc.start && Number.isInteger(value.loc.start.line)
    ? value.loc.start.line : 1;
}

function endLineOf(value) {
  return value && value.loc && value.loc.end && Number.isInteger(value.loc.end.line)
    ? value.loc.end.line : lineOf(value);
}

function nameOf(node) {
  if (!node) return "";
  if (node.id && node.id.name) return String(node.id.name);
  if (node.id && node.id.value) return String(node.id.value);
  if (node.key && node.key.name) return String(node.key.name);
  if (node.key && node.key.value) return String(node.key.value);
  if (node.name && typeof node.name === "string") return node.name;
  return "";
}

function commentSections(value) {
  const sections = [];
  const matches = String(value || "").matchAll(/@([A-Za-z][A-Za-z0-9_-]*)/g);
  for (const match of matches) {
    const section = String(match[1]).toLowerCase();
    if (!sections.includes(section)) sections.push(section);
  }
  return sections.slice(0, 32);
}

function buildSummary(ast, text) {
  const declarationTypes = new Set([
    "ClassDeclaration", "FunctionDeclaration", "VariableDeclaration",
    "ImportDeclaration", "ExportNamedDeclaration", "ExportDefaultDeclaration",
    "ExportAllDeclaration", "EnumDeclaration", "InterfaceDeclaration",
    "TypeAliasDeclaration", "TSInterfaceDeclaration", "TSTypeAliasDeclaration",
    "TSEnumDeclaration", "TSModuleDeclaration", "TSDeclareFunction",
    "TSDeclareMethod", "TSMethodSignature", "TSPropertySignature",
    "TSAbstractMethodDefinition", "TSImportEqualsDeclaration",
    "TSNamespaceExportDeclaration", "AbstractClassDeclaration", "ClassExpression"
  ]);
  const statementTypes = new Set([
    "ExpressionStatement", "ReturnStatement", "ThrowStatement", "BreakStatement",
    "ContinueStatement", "DebuggerStatement", "VariableDeclaration",
    "FunctionDeclaration", "ClassDeclaration", "IfStatement", "ForStatement",
    "ForInStatement", "ForOfStatement", "WhileStatement", "DoWhileStatement",
    "SwitchStatement", "TryStatement", "WithStatement", "LabeledStatement",
    "ImportDeclaration", "ExportNamedDeclaration", "ExportDefaultDeclaration",
    "TSInterfaceDeclaration", "TSTypeAliasDeclaration", "TSEnumDeclaration",
    "TSModuleDeclaration", "TSDeclareFunction"
  ]);
  const controlTypes = new Set([
    "IfStatement", "ForStatement", "ForInStatement", "ForOfStatement",
    "WhileStatement", "DoWhileStatement", "SwitchStatement", "TryStatement",
    "CatchClause", "WithStatement"
  ]);
  const operationTypes = new Set([
    "CallExpression", "NewExpression", "MemberExpression", "OptionalCallExpression",
    "OptionalMemberExpression", "BinaryExpression", "LogicalExpression",
    "AssignmentExpression", "UpdateExpression", "UnaryExpression", "ConditionalExpression",
    "AwaitExpression", "YieldExpression", "ChainExpression", "TaggedTemplateExpression"
  ]);
  const comments = [];
  for (const comment of (ast.comments || []).slice(0, 10000)) {
    const value = String(comment.value || "");
    const isJsdoc = comment.type === "Block" && value.trim().startsWith("*");
    const sections = commentSections(value);
    const description = value.replace(/^\s*\*+/, "").replace(/@[A-Za-z][A-Za-z0-9_-]*[^\n]*/g, "").trim();
    comments.push({
      line: lineOf(comment), end_line: endLineOf(comment), is_jsdoc: isJsdoc,
      has_description: Boolean(description), sections
    });
  }
  const nearestDocumentation = (line) => {
    for (let index = comments.length - 1; index >= 0; index -= 1) {
      const comment = comments[index];
      if (!comment.is_jsdoc || comment.end_line >= line) continue;
      if (line - comment.end_line <= 2) return comment;
      break;
    }
    return null;
  };
  const declarations = [];
  const nodes = [];
  const statements = [];
  const nodeTypes = [];
  const semicolonLines = [];
  const seenNodeTypes = new Set();
  const operationLocations = (node) => {
    const locations = [];
    const visit = (value, isRoot) => {
      if (!value || typeof value !== "object") return;
      if (!isRoot && statementTypes.has(value.type)) return;
      if (operationTypes.has(value.type)) locations.push(lineOf(value));
      for (const key of Object.keys(value)) {
        if (key === "loc" || key === "range" || key === "tokens" || key === "comments") continue;
        const child = value[key];
        if (Array.isArray(child)) child.forEach((item) => visit(item, false));
        else visit(child, false);
      }
    };
    visit(node, true);
    return locations;
  };
  const visit = (node) => {
    if (!node || typeof node !== "object" || typeof node.type !== "string") return;
    const kind = String(node.type);
    if (!seenNodeTypes.has(kind)) { seenNodeTypes.add(kind); nodeTypes.push(kind); }
    const line = lineOf(node);
    const endLine = endLineOf(node);
    if (declarationTypes.has(kind)) {
      const documentation = nearestDocumentation(line);
      declarations.push({
        kind, name: nameOf(node), line, end_line: endLine,
        documented: Boolean(documentation),
        documentation_sections: documentation ? documentation.sections : [],
        private: nameOf(node).startsWith("_")
      });
    }
    if (statementTypes.has(kind)) {
      const operations = operationLocations(node);
      statements.push({
        kind, line, end_line: endLine, operation_count: operations.length,
        operation_lines: operations.slice(0, 128)
      });
    }
    if (controlTypes.has(kind)) {
      const bodyLines = [];
      for (const key of ["body", "consequent", "alternate", "handler", "finalizer"]) {
        const value = node[key];
        if (Array.isArray(value)) value.forEach((item) => bodyLines.push(lineOf(item)));
        else if (value && typeof value === "object") bodyLines.push(lineOf(value));
      }
      if (bodyLines.some((bodyLine) => bodyLine === line)) {
        nodes.push({ kind, line, end_line: endLine, one_line_suite: true });
      }
    }
    if (declarationTypes.has(kind) || kind.endsWith("Statement")) {
      nodes.push({ kind, line, end_line: endLine, one_line_suite: false });
    }
    for (const key of Object.keys(node)) {
      if (key === "loc" || key === "range" || key === "tokens" || key === "comments") continue;
      const child = node[key];
      if (Array.isArray(child)) child.forEach(visit); else visit(child);
    }
  };
  visit(ast);
  for (const token of (ast.tokens || [])) {
    if (token.value === ";") semicolonLines.push(lineOf(token));
  }
  const lines = String(text).split(/\r?\n/).map((value, index) => ({
    line: index + 1, length: value.length, blank: value.trim().length === 0,
    indent: (value.match(/^\s*/) || [""])[0].length
  }));
  return {
    language: isTypeScript ? "typescript" : "javascript",
    node_types: nodeTypes.slice(0, 10000), declarations: declarations.slice(0, 10000),
    comments: comments.slice(0, 10000), nodes: nodes.slice(0, 10000),
    statements: statements.slice(0, 10000), semicolon_lines: semicolonLines.slice(0, 10000),
    lines: lines.slice(0, 10000)
  };
}

process.stdin.setEncoding("utf8");
process.stdin.on("data", (chunk) => { source += chunk; });
process.stdin.on("end", () => {
  try {
    const options = {
      comment: true, loc: true, range: true, tokens: true,
      jsx: true, sourceType: "module", errorOnUnknownASTType: true
    };
    if (isTypeScript) options.jsx = true;
    const ast = parser.parse(source, options);
    process.stdout.write(JSON.stringify({ ok: true, summary: buildSummary(ast, source) }));
  } catch (error) {
    const location = error && (error.location || error.loc) || {};
    const start = location.start || location;
    process.stdout.write(JSON.stringify({
      ok: false, error: {
        kind: "syntax_error",
        line: Number.isInteger(start.line) ? start.line : 1,
        column: Number.isInteger(start.column) ? start.column + 1 : 1
      }
    }));
    process.exitCode = 2;
  }
});
"""


def _script(language: str) -> str:
    """Render the fixed parser script with an absolute package path.

    Args:
        language: Literal parser mode, either ``javascript`` or ``typescript``.

    Returns:
        str: Node.js source with no caller-controlled values.

    Raises:
        ValueError: If the language is not one of the fixed parser modes.
    """

    if language not in {"javascript", "typescript"}:
        raise ValueError("unsupported node parser language")

    parser_entrypoint = json.dumps(str(TYPESCRIPT_ESTREE_ENTRYPOINT))
    language_literal = json.dumps(language)

    return _NODE_SCRIPT_TEMPLATE.replace(
        "PARSER_ENTRYPOINT", parser_entrypoint
    ).replace("LANGUAGE", language_literal)


@dataclass(frozen=True, slots=True)
class NodeParserOutcome:
    """Represent one bounded, source-redacted parser process outcome.

    Attributes:
        succeeded: Whether ESTree parsing and summary generation succeeded.
        error_kind: Bounded parser error classification, when parsing failed.
        error_line: One-based syntax error line, when known.
        error_column: One-based syntax error column, when known.
        payload: Parsed summary mapping retained for the language parser.
        stdout_length: Number of bytes emitted by the child process.
        stderr_length: Number of bytes emitted by the child process; stderr text
            is never retained or returned.
    """

    succeeded: bool
    error_kind: str | None = None
    error_line: int | None = None
    error_column: int | None = None
    payload: Mapping[str, object] = field(
        default_factory=lambda: MappingProxyType({}), repr=False
    )
    stdout_length: int = 0
    stderr_length: int = 0

    @property
    def available(self) -> bool:
        """Return whether a usable parser summary is available.

        Args:
            No arguments are accepted beyond the immutable outcome instance.

        Returns:
            bool: True when parsing and summary generation succeeded.
        """

        return self.succeeded

    @property
    def message(self) -> str:
        """Return a bounded execution classification without diagnostics.

        Args:
            No arguments are accepted beyond the immutable outcome instance.

        Returns:
            str: Redacted completion or failure classification.
        """

        return (
            "parser completed"
            if self.succeeded
            else (self.error_kind or "parser unavailable")
        )


class NodeParserRunner:
    """Execute the pinned parser using shell-disabled stdin-only subprocesses."""

    def run_javascript(self, source: str, timeout: float = 10.0) -> NodeParserOutcome:
        """Parse JavaScript or JSX source through fixed JavaScript options.

        Args:
            source: Complete JavaScript or JSX source held in memory.
            timeout: Maximum parser process duration in seconds.

        Returns:
            NodeParserOutcome: Bounded parser process result.
        """

        return self._run(source, "javascript", timeout)

    def run_typescript(self, source: str, timeout: float = 10.0) -> NodeParserOutcome:
        """Parse TypeScript or TSX source through fixed TypeScript options.

        Args:
            source: Complete TypeScript or TSX source held in memory.
            timeout: Maximum parser process duration in seconds.

        Returns:
            NodeParserOutcome: Bounded parser process result.
        """

        return self._run(source, "typescript", timeout)

    def run(
        self, source: str, language: str = "javascript", timeout: float = 10.0
    ) -> NodeParserOutcome:
        """Run one explicitly selected language parser through the same boundary.

        Args:
            source: Complete source held in memory.
            language: Fixed parser mode, either ``javascript`` or ``typescript``.
            timeout: Maximum parser process duration in seconds.

        Returns:
            NodeParserOutcome: Bounded parser process result.

        Raises:
            ValueError: If the language is not supported.
        """

        if language == "javascript":
            return self.run_javascript(source, timeout=timeout)

        if language == "typescript":
            return self.run_typescript(source, timeout=timeout)

        raise ValueError("unsupported node parser language")

    def _run(self, source: str, language: str, timeout: float) -> NodeParserOutcome:
        """Run one parser invocation without files, caches, or source in argv.

        Args:
            source: Complete source sent only to child standard input.
            language: Fixed parser mode selected by the public methods.
            timeout: Maximum parser process duration in seconds.

        Returns:
            NodeParserOutcome: Bounded success or redacted failure result.

        Raises:
            TypeError: If source is not text.
            ValueError: If timeout is not positive.
        """

        if not isinstance(source, str):
            raise TypeError("source must be text")

        if len(source.encode("utf-8")) > _MAX_SOURCE_BYTES:
            return NodeParserOutcome(False, "source_too_large")

        if timeout <= 0:
            raise ValueError("timeout must be positive")

        if not NODE_EXECUTABLE.is_file() or not TYPESCRIPT_ESTREE_ENTRYPOINT.is_file():
            return NodeParserOutcome(False, "parser_unavailable")

        command = (str(NODE_EXECUTABLE), "-e", _script(language))

        try:
            completed = subprocess.run(
                command,
                input=source,
                text=True,
                capture_output=True,
                shell=False,
                timeout=timeout,
                check=False,
            )

        except subprocess.TimeoutExpired:
            return NodeParserOutcome(False, "timeout")

        except OSError:
            return NodeParserOutcome(False, "parser_unavailable")

        stdout = completed.stdout or ""
        stderr_length = len((completed.stderr or "").encode("utf-8"))
        stdout_length = len(stdout.encode("utf-8"))

        if stdout_length > _MAX_OUTPUT_BYTES:
            return NodeParserOutcome(
                False,
                "output_too_large",
                stdout_length=stdout_length,
                stderr_length=stderr_length,
            )

        try:
            result = json.loads(stdout)

        except (TypeError, ValueError):
            return NodeParserOutcome(
                False,
                "invalid_parser_output",
                stdout_length=stdout_length,
                stderr_length=stderr_length,
            )

        if not isinstance(result, dict) or result.get("ok") is not True:
            error = result.get("error", {}) if isinstance(result, dict) else {}
            line = error.get("line") if isinstance(error, dict) else None
            column = error.get("column") if isinstance(error, dict) else None

            return NodeParserOutcome(
                False,
                "syntax_error" if completed.returncode else "invalid_parser_output",
                line if isinstance(line, int) else 1,
                column if isinstance(column, int) else 1,
                stdout_length=stdout_length,
                stderr_length=stderr_length,
            )

        summary = result.get("summary")

        if not isinstance(summary, dict):
            return NodeParserOutcome(
                False,
                "invalid_parser_output",
                stdout_length=stdout_length,
                stderr_length=stderr_length,
            )

        frozen_summary = _freeze(summary)

        if not isinstance(frozen_summary, Mapping):
            return NodeParserOutcome(
                False,
                "invalid_parser_output",
                stdout_length=stdout_length,
                stderr_length=stderr_length,
            )

        return NodeParserOutcome(
            True,
            payload=frozen_summary,
            stdout_length=stdout_length,
            stderr_length=stderr_length,
        )


__all__ = [
    "NODE_EXECUTABLE",
    "TYPESCRIPT_ESTREE_ENTRYPOINT",
    "NodeParserOutcome",
    "NodeParserRunner",
]
