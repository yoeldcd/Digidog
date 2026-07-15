"""Architecture contracts for the split avatar presentation packages."""

from pathlib import Path

from brain.infrastructure.voice import daemon
from brain.presentation.avatar.qt.window import QtAvatarWindow
from brain.presentation.avatar.tk.window import AvatarWindow
from brain.presentation.avatar.window.backend import resolve_avatar_window_class
from brain.presentation.avatar.window.main import SOURCE_ROOT


def test_avatar_root_contains_packages_instead_of_toolkit_prefixed_modules() -> None:
    avatar_root = SOURCE_ROOT / "brain" / "presentation" / "avatar"
    assert {path.name for path in avatar_root.iterdir() if path.is_dir()} >= {
        "window", "qt", "tk", "interactivity",
    }
    assert not any(avatar_root.glob("qt_*.py"))
    assert not (avatar_root / "window.py").exists()
    assert not (avatar_root / "animated_gif.py").exists()


def test_backend_contract_resolves_both_relocated_toolkits() -> None:
    assert resolve_avatar_window_class({"BRAIN_AVATAR_UI": "qt"}) is QtAvatarWindow
    assert resolve_avatar_window_class({"BRAIN_AVATAR_UI": "tk"}) is AvatarWindow


def test_daemon_launches_the_relocated_window_entrypoint() -> None:
    source = Path(daemon.__file__).read_text(encoding="utf-8")
    assert '"avatar" / "window" / "main.py"' in source
