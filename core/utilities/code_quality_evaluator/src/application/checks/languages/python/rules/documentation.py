"""Python docstring, section, and declaration documentation rules."""

from __future__ import annotations

import ast
import re

from src.domain.models import DocumentationPolicy, Evidence, LanguageQualityPolicy

from .evidence import evidence

_SECTION_PATTERN = re.compile(r"^\s*(Args|Returns|Raises|Attributes)\s*:\s*$")
_ENTRY_PATTERN = re.compile(r"^\s*([*A-Za-z_]\w*)\s*(?:\([^)]*\))?\s*:")


def _parent_map(tree: ast.AST) -> dict[int, ast.AST]:
    """Build an in-memory parent lookup.

    Args:
        tree: Parsed Python tree.

    Returns:
        dict[int, ast.AST]: Object identity keys mapped to parent nodes.
    """

    parents: dict[int, ast.AST] = {}

    for parent in ast.walk(tree):
        for child in ast.iter_child_nodes(parent):
            parents[id(child)] = parent

    return parents


def _is_nested(node: ast.AST, parents: dict[int, ast.AST]) -> bool:
    """Return whether a declaration is nested in a declaration body.

    Args:
        node: Declaration under inspection.
        parents: Parent lookup produced by :func:`_parent_map`.

    Returns:
        bool: ``True`` when a callable or class ancestor is present.
    """

    parent = parents.get(id(node))

    while parent is not None:
        if isinstance(parent, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            return True

        parent = parents.get(id(parent))

    return False


def _declarations(
    tree: ast.Module,
    documentation: DocumentationPolicy | None,
) -> tuple[ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef, ...]:
    """Select declarations according to private and nested visibility policy.

    Args:
        tree: Parsed Python module.
        documentation: Optional documentation policy.

    Returns:
        tuple[ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef, ...]:
            Source-ordered declarations selected for checks.
    """

    declarations = tuple(
        node
        for node in ast.walk(tree)
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
    )
    parents = _parent_map(tree)
    selected: list[ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef] = []

    for declaration in declarations:
        is_nested = (
            documentation is not None
            and not documentation.include_nested
            and _is_nested(declaration, parents)
        )

        if is_nested:
            continue

        if documentation is not None and not documentation.include_private:
            is_constructor = declaration.name == "__init__"
            include_constructor = is_constructor and documentation.require_constructor

            if declaration.name.startswith("_") and not include_constructor:
                continue

        selected.append(declaration)

    return tuple(sorted(selected, key=lambda node: (node.lineno, node.col_offset)))


def _section_lines(docstring: str) -> dict[str, tuple[str, ...]]:
    """Extract recognized documentation sections and body lines.

    Args:
        docstring: Callable or class docstring text.

    Returns:
        dict[str, tuple[str, ...]]: Section names mapped to body lines.
    """

    sections: dict[str, list[str]] = {}
    current: str | None = None

    for line in docstring.splitlines():
        match = _SECTION_PATTERN.match(line)

        if match:
            section_name = match.group(1)
            current = section_name
            sections.setdefault(section_name, [])
            continue

        if current is not None:
            sections[current].append(line)

    return {name: tuple(lines) for name, lines in sections.items()}


def _documented_names(lines: tuple[str, ...]) -> tuple[str, ...]:
    """Extract argument or attribute names from section lines.

    Args:
        lines: Body lines for one documentation section.

    Returns:
        tuple[str, ...]: Names in source order.
    """

    names: list[str] = []

    for line in lines:
        match = _ENTRY_PATTERN.match(line)

        if match is None:
            continue

        names.append(match.group(1).lstrip("*"))

    return tuple(names)


def _raised_names(function: ast.FunctionDef | ast.AsyncFunctionDef) -> tuple[str, ...]:
    """Return unique explicitly raised exception names.

    Args:
        function: Callable declaration to inspect.

    Returns:
        tuple[str, ...]: Exception names in source order.
    """

    names: list[str] = []

    def visit(node: ast.AST, is_root: bool = False) -> None:
        """Visit a node while excluding nested declaration scopes.

        Args:
            node: AST node currently visited.
            is_root: Whether ``node`` is the supplied callable.

        Returns:
            None: Names are accumulated in the enclosing scope.
        """

        if not is_root and isinstance(
            node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
        ):
            return

        if isinstance(node, ast.Raise) and node.exc is not None:
            expression = node.exc.func if isinstance(node.exc, ast.Call) else node.exc

            if isinstance(expression, ast.Name):
                name = expression.id

            elif isinstance(expression, ast.Attribute):
                name = expression.attr

            else:
                name = "<exception>"

            if name not in names:
                names.append(name)

        for child in ast.iter_child_nodes(node):
            visit(child)

    visit(function, is_root=True)

    return tuple(names)


def _is_dataclass(class_node: ast.ClassDef) -> bool:
    """Return whether a class has a ``dataclass`` decorator.

    Args:
        class_node: Class declaration.

    Returns:
        bool: ``True`` when a dataclass decorator is present.
    """

    for decorator in class_node.decorator_list:
        candidate = decorator.func if isinstance(decorator, ast.Call) else decorator

        if isinstance(candidate, ast.Name) and candidate.id == "dataclass":
            return True

        if isinstance(candidate, ast.Attribute) and candidate.attr == "dataclass":
            return True

    return False


def _dataclass_fields(class_node: ast.ClassDef) -> tuple[str, ...]:
    """Return annotated and simple assignment field names.

    Args:
        class_node: Dataclass declaration.

    Returns:
        tuple[str, ...]: Field names in declaration order.
    """

    names: list[str] = []

    for statement in class_node.body:
        if isinstance(statement, ast.AnnAssign) and isinstance(
            statement.target, ast.Name
        ):
            names.append(statement.target.id)

        elif isinstance(statement, ast.Assign):
            names.extend(
                target.id
                for target in statement.targets
                if isinstance(target, ast.Name)
            )

    return tuple(names)


def _requires_docstring(
    declaration: ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef,
    documentation: DocumentationPolicy | None,
) -> bool:
    """Return whether one declaration requires a docstring.

    Args:
        declaration: Class or callable declaration.
        documentation: Optional documentation policy.

    Returns:
        bool: ``True`` when the configured requirement is enabled.
    """

    if documentation is None:
        return True

    if isinstance(declaration, ast.ClassDef):
        return documentation.require_classes

    if declaration.name == "__init__":
        return documentation.require_constructor

    return documentation.require_callables


def documentation_evidence(
    tree: ast.Module,
    policy: LanguageQualityPolicy | None,
    path: str,
) -> tuple[Evidence, ...]:
    """Collect missing, stale, or incomplete documentation evidence.

    Args:
        tree: Parsed Python module.
        policy: Optional language policy controlling required sections.
        path: Relative source path.

    Returns:
        tuple[Evidence, ...]: Source-ordered documentation findings.
    """

    documentation = policy.documentation if policy is not None else None
    findings: list[Evidence] = []

    if (
        documentation is not None
        and documentation.require_module
        and ast.get_docstring(tree) is None
    ):
        findings.append(evidence(path, 1, "module docstring missing"))

    for declaration in _declarations(tree, documentation):
        docstring = ast.get_docstring(declaration)
        requires_docstring = _requires_docstring(declaration, documentation)

        if requires_docstring and docstring is None:
            findings.append(
                evidence(
                    path, declaration.lineno, f"docstring missing: {declaration.name}"
                )
            )

        sections = _section_lines(docstring or "")

        if isinstance(declaration, (ast.FunctionDef, ast.AsyncFunctionDef)):
            expected_parameters = [
                *declaration.args.posonlyargs,
                *declaration.args.args,
                *declaration.args.kwonlyargs,
            ]
            expected_names = tuple(
                parameter.arg
                for parameter in expected_parameters
                if parameter.arg not in {"self", "cls"}
            )

            if declaration.args.vararg is not None:
                expected_names += (declaration.args.vararg.arg,)

            if declaration.args.kwarg is not None:
                expected_names += (declaration.args.kwarg.arg,)

            documented_names = _documented_names(sections.get("Args", ()))

            if documentation is not None and documentation.require_exact_args:
                missing_names = tuple(
                    name for name in expected_names if name not in documented_names
                )
                stale_names = tuple(
                    name for name in documented_names if name not in expected_names
                )

                for name in (*missing_names, *stale_names):
                    findings.append(
                        evidence(
                            path,
                            declaration.lineno,
                            f"Args name mismatch: {declaration.name}.{name}",
                        )
                    )

            if (
                documentation is not None
                and documentation.require_returns
                and declaration.name != "__init__"
                and "Returns" not in sections
            ):
                findings.append(
                    evidence(
                        path,
                        declaration.lineno,
                        f"Returns section missing: {declaration.name}",
                    )
                )

            raised_names = _raised_names(declaration)

            if (
                documentation is not None
                and documentation.require_raises_for_explicit_raise
                and raised_names
            ):
                documented_raises = _documented_names(sections.get("Raises", ()))

                for name in raised_names:
                    if name not in documented_raises:
                        findings.append(
                            evidence(
                                path,
                                declaration.lineno,
                                f"Raises entry missing: {declaration.name}.{name}",
                            )
                        )

            if documentation is not None:
                for section in documentation.required_sections:
                    if declaration.name == "__init__" and section == "Returns":
                        continue

                    if section not in sections:
                        findings.append(
                            evidence(
                                path,
                                declaration.lineno,
                                f"documentation section missing: {section}",
                            )
                        )

        if (
            isinstance(declaration, ast.ClassDef)
            and documentation is not None
            and documentation.require_dataclass_attributes
            and _is_dataclass(declaration)
        ):
            documented_attributes = _documented_names(sections.get("Attributes", ()))
            field_names = _dataclass_fields(declaration)

            for name in field_names:
                if name not in documented_attributes:
                    findings.append(
                        evidence(
                            path,
                            declaration.lineno,
                            f"Attributes entry missing: {declaration.name}.{name}",
                        )
                    )

            for name in documented_attributes:
                if name not in field_names:
                    findings.append(
                        evidence(
                            path,
                            declaration.lineno,
                            f"Attributes name mismatch: {declaration.name}.{name}",
                        )
                    )

    return tuple(findings)


__all__ = ["documentation_evidence"]
