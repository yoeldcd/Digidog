# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Recursive architecture guards for the avatar and voice package split."""

from __future__ import annotations

import ast
from collections import defaultdict
from pathlib import Path

from brain.infrastructure.voice.daemon import daemon
from brain.presentation.avatar.qt.runtime.window import QtAvatarWindow
from brain.presentation.avatar.tk.avatar import AvatarWindow
from brain.presentation.avatar.window.backend import resolve_avatar_window_class
from brain.presentation.avatar.window.main import SOURCE_ROOT

BRAIN_ROOT = SOURCE_ROOT / "brain"
AVATAR_ROOT = BRAIN_ROOT / "presentation" / "avatar"
INFRASTRUCTURE_AVATAR_ROOT = BRAIN_ROOT / "infrastructure" / "avatar"
VOICE_ROOT = BRAIN_ROOT / "infrastructure" / "voice"
TOOLKIT_ROOTS = {"qt": AVATAR_ROOT / "qt", "tk": AVATAR_ROOT / "tk"}
REQUIRED_SUBPACKAGES = {
    "qt": {"avatar", "bubble", "controls", "markdown", "runtime"},
    "tk": {"avatar", "bubble", "controls", "quota", "runtime"},
}
ALLOWED_ROOT_SHIMS = {
    "qt": {
        "avatar_renderer.py", "backend_adapter.py", "bubble_chrome.py",
        "bubble_geometry.py", "controls.py", "controls_bottom.py",
        "controls_center.py", "controls_geometry.py", "controls_top.py",
        "document_styling.py", "markdown_bubble.py", "markdown_document.py",
        "message_controller.py", "quota_controller.py", "window.py",
        "window_geometry.py",
    },
    "tk": set(),
}
VOICE_SHIMS: set[str] = set()
SHARED_CONTRACT_MODULES = (
    AVATAR_ROOT / "communication" / "projection" / "daemon_status.py",
    AVATAR_ROOT / "interactivity" / "history_controller.py",
    AVATAR_ROOT / "interactivity" / "interaction_controller.py",
    AVATAR_ROOT / "interactivity" / "presentation_state.py",
    AVATAR_ROOT / "interactivity" / "quota_view_model.py",
)


def _python_files(root: Path) -> list[Path]:
    return sorted(path for path in root.rglob("*.py") if "$agent" not in path.parts)


def _tree(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _module_name(path: Path) -> str:
    parts = list(path.relative_to(BRAIN_ROOT.parent).with_suffix("").parts)
    if parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def _imports(path: Path) -> set[str]:
    current = _module_name(path)
    package = current if path.name == "__init__.py" else current.rpartition(".")[0]
    imports: set[str] = set()
    for node in ast.walk(_tree(path)):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                base = package.split(".")
                base = base[: len(base) - node.level + 1]
                if node.module:
                    base.extend(node.module.split("."))
                imports.add(".".join(base))
            elif node.module:
                imports.add(node.module)
    return imports


def _is_import_only_shim(path: Path) -> bool:
    for node in _tree(path).body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            continue
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant):
            continue
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            value = node.value
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            if (
                all(isinstance(target, ast.Name) and target.id == "__all__" for target in targets)
                and isinstance(value, (ast.List, ast.Tuple))
                and all(isinstance(item, ast.Constant) and isinstance(item.value, str) for item in value.elts)
            ):
                continue
        return False
    return True


def _import_graph(paths: list[Path]) -> dict[str, set[str]]:
    modules = {_module_name(path) for path in paths}
    graph: dict[str, set[str]] = defaultdict(set)
    for path in paths:
        source = _module_name(path)
        for imported in _imports(path):
            if imported in modules:
                graph[source].add(imported)
    return graph


def _cycles(graph: dict[str, set[str]]) -> list[tuple[str, ...]]:
    found: set[tuple[str, ...]] = set()
    active: list[str] = []
    visited: set[str] = set()

    def visit(node: str) -> None:
        if node in active:
            cycle = active[active.index(node):]
            found.add(min(tuple(cycle[i:] + cycle[:i]) for i in range(len(cycle))))
            return
        if node in visited:
            return
        active.append(node)
        for dependency in graph.get(node, ()):
            visit(dependency)
        active.pop()
        visited.add(node)

    for node in graph:
        visit(node)
    return sorted(found)


def test_avatar_root_contains_packages_instead_of_toolkit_prefixed_modules() -> None:
    assert {path.name for path in AVATAR_ROOT.iterdir() if path.is_dir()} >= {
        "window", "qt", "tk", "interactivity", "communication",
    }
    assert not any(AVATAR_ROOT.glob("qt_*.py"))
    assert not (AVATAR_ROOT / "window.py").exists()
    assert not (AVATAR_ROOT / "animated_gif.py").exists()


def test_every_avatar_and_voice_production_module_is_under_500_physical_lines() -> None:
    oversized = {}
    for root in (AVATAR_ROOT, VOICE_ROOT):
        for path in _python_files(root):
            count = len(path.read_text(encoding="utf-8").splitlines())
            if count >= 500:
                oversized[str(path.relative_to(BRAIN_ROOT))] = count
    assert not oversized, oversized


def test_toolkit_roots_contain_only_initializers_and_import_only_compatibility_shims() -> None:
    for toolkit, root in TOOLKIT_ROOTS.items():
        root_modules = {path.name for path in root.glob("*.py")}
        assert root_modules <= ALLOWED_ROOT_SHIMS[toolkit] | {"__init__.py"}
        non_shims = [path.name for path in root.glob("*.py") if path.name != "__init__.py" and not _is_import_only_shim(path)]
        assert not non_shims, {toolkit: non_shims}


def test_repeated_prefix_families_are_grouped_into_required_cohesive_subpackages() -> None:
    for toolkit, root in TOOLKIT_ROOTS.items():
        packages = {path.name for path in root.iterdir() if path.is_dir() and (path / "__init__.py").is_file()}
        assert REQUIRED_SUBPACKAGES[toolkit] <= packages
        for name in REQUIRED_SUBPACKAGES[toolkit]:
            implementations = [path for path in (root / name).glob("*.py") if path.name != "__init__.py"]
            assert len(implementations) >= 2, f"{toolkit}/{name} is an artificial one-file package"
    assert (VOICE_ROOT / "messaging" / "message_queue.py").is_file()
    assert (VOICE_ROOT / "messaging" / "message_session.py").is_file()
    assert not (VOICE_ROOT / "message").exists()
    assert not (VOICE_ROOT / "message_queue.py").exists()
    assert not (VOICE_ROOT / "message_session.py").exists()


def test_infrastructure_avatar_and_voice_use_vertical_packages() -> None:
    """Keep infrastructure capability roots free of flat implementation modules."""
    avatar_packages = {"configuration", "process"}
    voice_packages = {"audio", "catalog", "daemon", "messaging", "narration", "service"}

    assert {path.name for path in INFRASTRUCTURE_AVATAR_ROOT.iterdir() if path.is_dir()} >= avatar_packages
    assert {path.name for path in VOICE_ROOT.iterdir() if path.is_dir()} >= voice_packages
    assert {path.name for path in INFRASTRUCTURE_AVATAR_ROOT.glob("*.py")} == {"__init__.py"}
    assert {path.name for path in VOICE_ROOT.glob("*.py")} == {"__init__.py"}
    assert all(len(list(path.glob("*.py"))) < 10 for path in INFRASTRUCTURE_AVATAR_ROOT.iterdir() if path.is_dir())
    assert all(len(list(path.glob("*.py"))) < 10 for path in VOICE_ROOT.iterdir() if path.is_dir())


def test_shared_avatar_contracts_have_no_gui_toolkit_dependencies() -> None:
    forbidden = ("PySide", "PyQt", "tkinter", "brain.presentation.avatar.qt", "brain.presentation.avatar.tk")
    violations = {
        str(path.relative_to(BRAIN_ROOT)): sorted(name for name in _imports(path) if name.startswith(forbidden))
        for path in SHARED_CONTRACT_MODULES
        if any(name.startswith(forbidden) for name in _imports(path))
    }
    assert not violations, violations


def test_backends_do_not_import_each_other_and_internal_import_graph_is_acyclic() -> None:
    violations = {}
    for toolkit, root in TOOLKIT_ROOTS.items():
        opposite = f"brain.presentation.avatar.{('tk' if toolkit == 'qt' else 'qt')}"
        for path in _python_files(root):
            imported = sorted(name for name in _imports(path) if name.startswith(opposite))
            if imported:
                violations[str(path.relative_to(BRAIN_ROOT))] = imported
    assert not violations, violations
    target_files = (
        _python_files(AVATAR_ROOT)
        + _python_files(INFRASTRUCTURE_AVATAR_ROOT)
        + _python_files(VOICE_ROOT)
    )
    assert not _cycles(_import_graph(target_files))


def test_canonical_production_modules_do_not_import_legacy_shims() -> None:
    legacy_modules = {
        _module_name(root / name) for root in TOOLKIT_ROOTS.values()
        for name in ALLOWED_ROOT_SHIMS[root.name]
    } | {_module_name(VOICE_ROOT / name) for name in VOICE_SHIMS}
    shim_paths = {
        root / name for root in TOOLKIT_ROOTS.values()
        for name in ALLOWED_ROOT_SHIMS[root.name]
    } | {VOICE_ROOT / name for name in VOICE_SHIMS}
    violations = {}
    target_files = _python_files(AVATAR_ROOT) + _python_files(INFRASTRUCTURE_AVATAR_ROOT) + _python_files(VOICE_ROOT)

    for path in target_files:
        if path in shim_paths:
            continue
        imported = sorted(_imports(path) & legacy_modules)
        if imported:
            violations[str(path.relative_to(BRAIN_ROOT))] = imported
    assert not violations, violations


def test_backend_contract_resolves_both_relocated_toolkits() -> None:
    assert resolve_avatar_window_class({"BRAIN_AVATAR_UI": "qt"}) is QtAvatarWindow
    assert resolve_avatar_window_class({"BRAIN_AVATAR_UI": "tk"}) is AvatarWindow


def test_daemon_launches_the_relocated_window_entrypoint() -> None:
    source = Path(daemon.__file__).read_text(encoding="utf-8")
    assert '"avatar" / "window" / "main.py"' in source
