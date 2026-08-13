"""Regression tests for reusable utility discovery and command aliases."""

from __future__ import annotations

import argparse
from pathlib import Path

import pytest

from brain.presentation.actions.snippets import command_list_snippets as action
from brain.presentation.commands.snippets import command_list_snippets as command


@pytest.mark.parametrize(
    ("filename", "source", "expected"),
    (
        ("utility", "#!/usr/bin/env bash\n# Shell utility specification.\n", "Shell utility specification."),
        (
            "utility.js",
            "#!/usr/bin/env node\n// JavaScript utility specification.\n",
            "JavaScript utility specification.",
        ),
        ("utility.cmd", "@echo off\nREM Batch utility specification.\n", "Batch utility specification."),
    ),
)
def test_script_description_follows_scripting_language_comments(
    tmp_path: Path,
    filename: str,
    source: str,
    expected: str,
) -> None:
    """Interpret comments using the detected scripting language."""
    script_path = tmp_path / filename
    script_path.write_text(source, encoding="utf-8")

    assert action._script_description(script_path) == expected


def test_markdown_description_skips_index_and_reads_first_prose_block(
    tmp_path: Path,
) -> None:
    """Ignore section names and list entries before the first prose paragraph."""
    readme = tmp_path / "README.md"
    readme.write_text(
        "# Utility\n\n## Index\n- [Overview](#overview)\n- [Usage](#usage)\n\n"
        "## Overview\nFirst description line.\nSecond description line.\n",
        encoding="utf-8",
    )

    assert action._markdown_description(readme) == (
        "First description line. Second description line."
    )


def test_folder_description_prefers_root_readme(tmp_path: Path) -> None:
    """Use the root README before documentation or scripts."""
    
    utility = tmp_path / "utility"
    (utility / "documentation").mkdir(parents=True)
    (utility / "README.md").write_text("# Utility\nRoot specification.\n", encoding="utf-8")
    (utility / "documentation" / "README.md").write_text(
        "# Documentation\nDocumentation specification.\n",
        encoding="utf-8",
    )
    (utility / "utility.py").write_text("\"\"\"Script specification.\"\"\"\n", encoding="utf-8")

    assert action._folder_description(utility) == "Root specification."


def test_folder_description_does_not_bypass_existing_root_readme(tmp_path: Path) -> None:
    """Do not inspect secondary sources when the root README exists."""
    
    utility = tmp_path / "utility"
    documentation = utility / "documentation"
    documentation.mkdir(parents=True)
    (utility / "README.md").write_text("# Heading only\n", encoding="utf-8")
    (documentation / "README.md").write_text(
        "# Documentation\nSecondary specification.\n",
        encoding="utf-8",
    )
    (utility / "utility.py").write_text("\"\"\"Script specification.\"\"\"\n", encoding="utf-8")

    assert action._folder_description(utility) == ""


def test_folder_description_prefers_documentation_readme_over_root_script(
    tmp_path: Path,
) -> None:
    """Inspect secondary documentation before falling back to a root script."""
    
    utility = tmp_path / "utility"
    documentation = utility / "documentation"
    documentation.mkdir(parents=True)
    (utility / "utility.js").write_text(
        "// Root script specification.\n",
        encoding="utf-8",
    )
    (documentation / "README.md").write_text(
        "# Documentation\nSecondary documentation specification.\n",
        encoding="utf-8",
    )

    assert action._folder_description(utility) == "Secondary documentation specification."


def test_folder_description_uses_documentation_readme(tmp_path: Path) -> None:
    """Use documentation README when the root README is absent."""
    
    utility = tmp_path / "utility"
    documentation = utility / "documentation"
    documentation.mkdir(parents=True)
    (documentation / "README.md").write_text(
        "# Documentation\nDocumentation specification.\n",
        encoding="utf-8",
    )

    assert action._folder_description(utility) == "Documentation specification."


def test_folder_description_falls_back_to_root_script(tmp_path: Path) -> None:
    """Use a supported root script when neither README provides prose."""
    
    utility = tmp_path / "utility"
    utility.mkdir()
    (utility / "utility.py").write_text("\"\"\"Script specification.\"\"\"\n", encoding="utf-8")

    assert action._folder_description(utility) == "Script specification."


def test_list_utilities_is_a_parser_alias() -> None:
    """Keep one canonical command identity for both accepted spellings."""
    
    assert command.SCHEMA.name == "list-snippets"
    assert command.SCHEMA.aliases == ["list-utilities"]
    scope_argument = next(
        argument for argument in command.SCHEMA.arguments if "--scope" in argument.flags
    )
    assert scope_argument.default == "all"


def test_list_snippets_combines_agent_snippets_and_consumer_scripts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Expose top-level utilities from both authorized consumer sources."""

    agent_home = tmp_path / "agent-home"
    workspace_root = tmp_path / "consumer"
    snippets_dir = agent_home / "snippets"
    scripts_dir = workspace_root / "$agent" / "scripts"
    snippets_dir.mkdir(parents=True)
    scripts_dir.mkdir(parents=True)
    (snippets_dir / "shared-tool").mkdir()
    (scripts_dir / "consumer-tool").mkdir()

    monkeypatch.setattr(action, "get_agent_home", lambda: agent_home)
    monkeypatch.setattr(action, "get_workspace_root", lambda: workspace_root)
    monkeypatch.setattr(action, "log_step", lambda *_args, **_kwargs: None)
    args = argparse.Namespace(color=False, filter=None, query=None, scope="all")

    assert action.handle(args) == 0
    assert [Path(item["path"]).name for item in args.json_payload["snippets"]] == [
        "consumer-tool",
        "shared-tool",
    ]
    assert all(set(item) == {"description", "path"} for item in args.json_payload["snippets"])
    output = capsys.readouterr().out
    assert output.index("## Local Utilities") < output.index("## Shared Snippets")


def test_list_snippets_succeeds_when_only_consumer_scripts_exist(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Do not require the legacy snippets directory when scripts exist."""

    workspace_root = tmp_path / "consumer"
    scripts_dir = workspace_root / "$agent" / "scripts"
    scripts_dir.mkdir(parents=True)
    (scripts_dir / "local-tool.py").write_text(
        '#!/usr/bin/env python\n# Author: Example\n"""Readable local utility specification."""\n',
        encoding="utf-8",
    )

    monkeypatch.setattr(action, "get_agent_home", lambda: tmp_path / "missing-agent")
    monkeypatch.setattr(action, "get_workspace_root", lambda: workspace_root)
    monkeypatch.setattr(action, "log_step", lambda *_args, **_kwargs: None)
    args = argparse.Namespace(color=False, filter="local", query=None, scope="local")

    assert action.handle(args) == 0
    assert args.json_payload["scope"] == "local"
    assert args.json_payload["count"] == 1
    assert Path(args.json_payload["snippets"][0]["path"]).name == "local-tool.py"
    assert set(args.json_payload["snippets"][0]) == {"description", "path"}
    assert args.json_payload["snippets"][0]["description"] == (
        "Readable local utility specification."
    )
