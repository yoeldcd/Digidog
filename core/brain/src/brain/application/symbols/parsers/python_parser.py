# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Python AST symbol parser implementation."""

from __future__ import annotations

import ast
import os

from brain.application.symbols.parsers.base_parser import BaseSymbolParser
from brain.domain.symbols.models import SymbolKind, SymbolLocationDTO


class PythonSymbolParser(BaseSymbolParser):
    """Concrete symbol parser strategy for Python (.py) source code using standard ast."""

    @property
    def supported_extensions(self) -> tuple[str, ...]:
        """Return tuple of supported Python file extensions.

        Returns:
            tuple[str, ...]: ('.py', '.pyw')
        """
        return (".py", ".pyw")

    @property
    def language_name(self) -> str:
        """Return lower-case language identifier.

        Returns:
            str: 'python'
        """
        return "python"

    def parse_symbols(
        self,
        filepath: str,
        name_pattern: str = "",
        kind_filter: SymbolKind = SymbolKind.ALL,
    ) -> tuple[SymbolLocationDTO, ...]:
        """Parse one Python file with ast visitor and extract symbol contracts.

        Args:
            filepath (str): Target Python source file path.
            name_pattern (str): Name substring or pattern filter (case-insensitive).
            kind_filter (SymbolKind): Specific symbol category filter.

        Returns:
            tuple[SymbolLocationDTO, ...]: Discovered symbol locations.
        """
        if not os.path.isfile(filepath):
            return ()

        try:
            with open(filepath, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
            tree = ast.parse(content, filename=filepath)
        except Exception:
            return ()

        pattern_lower = name_pattern.strip().lower()
        symbols: list[SymbolLocationDTO] = []

        class SymbolVisitor(ast.NodeVisitor):
            """AST NodeVisitor collecting class, function, and method symbol contracts."""

            def __init__(self) -> None:
                """Initialize visitor with empty parent class state."""
                self.current_class: str = ""

            def visit_ClassDef(self, node: ast.ClassDef) -> None:
                """Visit a class definition node.

                Args:
                    node (ast.ClassDef): AST class definition node.
                """
                old_class = self.current_class
                self.current_class = node.name

                if kind_filter in (SymbolKind.ALL, SymbolKind.CLASS):
                    if not pattern_lower or pattern_lower in node.name.lower():
                        doc = ast.get_docstring(node) or ""
                        summary = doc.splitlines()[0].strip() if doc else ""
                        bases = [self._format_node(b) for b in node.bases]
                        base_str = f"({', '.join(bases)})" if bases else ""
                        sig = f"class {node.name}{base_str}"

                        symbols.append(
                            SymbolLocationDTO(
                                name=node.name,
                                kind=SymbolKind.CLASS,
                                filepath=filepath,
                                start_line=node.lineno,
                                end_line=getattr(node, "end_lineno", node.lineno),
                                signature=sig,
                                docstring_summary=summary,
                                parent_symbol=old_class,
                            )
                        )

                self.generic_visit(node)
                self.current_class = old_class

            def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
                """Visit a synchronous function definition node.

                Args:
                    node (ast.FunctionDef): AST function node.
                """
                self._handle_function(node)
                self.generic_visit(node)

            def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
                """Visit an asynchronous function definition node.

                Args:
                    node (ast.AsyncFunctionDef): AST async function node.
                """
                self._handle_function(node)
                self.generic_visit(node)

            def _handle_function(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
                """Extract function or method symbol DTO from function node.

                Args:
                    node (ast.FunctionDef | ast.AsyncFunctionDef): AST function node.
                """
                is_method = bool(self.current_class)
                symbol_kind = SymbolKind.METHOD if is_method else SymbolKind.FUNCTION

                if kind_filter not in (SymbolKind.ALL, symbol_kind):
                    return

                if pattern_lower and pattern_lower not in node.name.lower():
                    return

                doc = ast.get_docstring(node) or ""
                summary = doc.splitlines()[0].strip() if doc else ""
                sig = self._build_function_signature(node)

                symbols.append(
                    SymbolLocationDTO(
                        name=node.name,
                        kind=symbol_kind,
                        filepath=filepath,
                        start_line=node.lineno,
                        end_line=getattr(node, "end_lineno", node.lineno),
                        signature=sig,
                        docstring_summary=summary,
                        parent_symbol=self.current_class,
                    )
                )

            def _format_node(self, node: ast.AST) -> str:
                """Format an AST node into a string representation.

                Args:
                    node (ast.AST): Target AST node.

                Returns:
                    str: String representation.
                """
                if isinstance(node, ast.Name):
                    return node.id
                if isinstance(node, ast.Attribute):
                    return f"{self._format_node(node.value)}.{node.attr}"
                return ast.unparse(node) if hasattr(ast, "unparse") else "..."

            def _build_function_signature(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
                """Build human-readable function signature string.

                Args:
                    node (ast.FunctionDef | ast.AsyncFunctionDef): Function node.

                Returns:
                    str: Formatted signature.
                """
                prefix = "async def " if isinstance(node, ast.AsyncFunctionDef) else "def "
                args_list: list[str] = []

                for arg in node.args.args:
                    args_list.append(arg.arg)

                if node.args.vararg:
                    args_list.append(f"*{node.args.vararg.arg}")

                for kwonly in node.args.kwonlyargs:
                    args_list.append(kwonly.arg)

                if node.args.kwarg:
                    args_list.append(f"**{node.args.kwarg.arg}")

                ret_str = ""
                if node.returns:
                    ret_str = f" -> {self._format_node(node.returns)}"

                return f"{prefix}{node.name}({', '.join(args_list)}){ret_str}"

        visitor = SymbolVisitor()
        visitor.visit(tree)
        return tuple(symbols)


def extract_python_symbols_from_file(
    filepath: str,
    name_pattern: str = "",
    kind_filter: SymbolKind = SymbolKind.ALL,
) -> tuple[SymbolLocationDTO, ...]:
    """Convenience helper delegating to PythonSymbolParser.

    Args:
        filepath (str): Target Python source file path.
        name_pattern (str): Name pattern filter.
        kind_filter (SymbolKind): Symbol category filter.

    Returns:
        tuple[SymbolLocationDTO, ...]: Discovered symbol locations.
    """
    return PythonSymbolParser().parse_symbols(filepath, name_pattern, kind_filter)
