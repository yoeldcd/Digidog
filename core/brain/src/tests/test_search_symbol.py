# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Unit test suite for brain search-symbol CLI command, AST symbol parser, and symbols config."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from brain.application.knowledge.models.dtos.runtime_config import BrainConfigsDTO, SymbolsConfigDTO
from brain.application.symbols import search_symbols
from brain.domain.symbols import SymbolKind, SymbolLocationDTO, SymbolSearchQuery
from brain.presentation.actions.utilities.command_search_symbol import handle as handle_search_symbol


def test_symbols_config_dto_defaults() -> None:
    """Verify SymbolsConfigDTO default values and BrainConfigsDTO integration."""
    config = SymbolsConfigDTO()
    assert config.enabled is True
    assert config.default_language == "python"
    assert config.model.model == "google/gemini-2.5-flash"
    assert config.model.max_tokens == 2000

    brain_configs = BrainConfigsDTO()
    assert brain_configs.symbols.enabled is True
    assert brain_configs.symbols.default_language == "python"


def test_symbol_search_service_python_ast(tmp_path: Path) -> None:
    """Test AST symbol extraction for classes, functions, and methods."""
    sample_code = '''"""Sample module docstring."""

class SampleClass:
    """Sample class docstring."""

    def sample_method(self, value: int) -> str:
        """Sample method docstring."""
        return str(value)

def sample_function(name: str) -> None:
    """Sample function docstring."""
    pass
'''
    file_path = tmp_path / "sample.py"
    file_path.write_text(sample_code, encoding="utf-8")

    # Query all symbols
    query_all = SymbolSearchQuery(name_pattern="", path=str(file_path), kind=SymbolKind.ALL)
    symbols = search_symbols(query_all)
    assert len(symbols) == 3

    names = {s.name for s in symbols}
    assert names == {"SampleClass", "sample_method", "sample_function"}

    # Query only class
    query_class = SymbolSearchQuery(name_pattern="SampleClass", path=str(file_path), kind=SymbolKind.CLASS)
    class_symbols = search_symbols(query_class)
    assert len(class_symbols) == 1
    assert class_symbols[0].name == "SampleClass"
    assert class_symbols[0].kind == SymbolKind.CLASS
    assert class_symbols[0].signature == "class SampleClass"
    assert class_symbols[0].docstring_summary == "Sample class docstring."

    # Query only method
    query_method = SymbolSearchQuery(name_pattern="sample_method", path=str(file_path), kind=SymbolKind.METHOD)
    method_symbols = search_symbols(query_method)
    assert len(method_symbols) == 1
    assert method_symbols[0].name == "sample_method"
    assert method_symbols[0].kind == SymbolKind.METHOD
    assert method_symbols[0].parent_symbol == "SampleClass"
    assert "def sample_method" in method_symbols[0].signature


def test_cli_search_symbol_action_handler(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Test CLI handle execution with text and JSON formats."""
    sample_code = "class TestTarget:\n    pass\n"
    file_path = tmp_path / "target.py"
    file_path.write_text(sample_code, encoding="utf-8")

    class DummyArgs:
        name = "TestTarget"
        language = "python"
        path = str(file_path)
        kind = "all"
        json = True

    args = DummyArgs()
    status = handle_search_symbol(args)  # type: ignore[arg-type]
    assert status == 0

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert payload["ok"] is True
    assert payload["command"] == "search-symbol"
    assert payload["count"] == 1
    assert payload["symbols"][0]["name"] == "TestTarget"
    assert payload["symbols"][0]["kind"] == "class"
