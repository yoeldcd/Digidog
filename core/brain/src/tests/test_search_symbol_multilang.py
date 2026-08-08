# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Unit test suite for multi-language search-symbol support (JS/TS, PS1, Batch, Python)."""

from __future__ import annotations

from pathlib import Path

from brain.application.symbols import (
    DEFAULT_PARSER_REGISTRY,
    BaseSymbolParser,
    BatchSymbolParser,
    JsTsSymbolParser,
    PowerShellSymbolParser,
    PythonSymbolParser,
    search_symbols,
)
from brain.domain.symbols import SymbolKind, SymbolSearchQuery


def test_parser_strategy_contracts() -> None:
    """Verify that all parser strategies inherit BaseSymbolParser and declare properties."""
    parsers = DEFAULT_PARSER_REGISTRY.get_all_parsers()
    assert len(parsers) == 4

    for parser in parsers:
        assert isinstance(parser, BaseSymbolParser)
        assert len(parser.supported_extensions) >= 1
        assert len(parser.language_name) >= 1

    assert PythonSymbolParser().language_name == "python"
    assert JsTsSymbolParser().language_name == "typescript"
    assert PowerShellSymbolParser().language_name == "powershell"
    assert BatchSymbolParser().language_name == "batch"


def test_js_ts_symbol_parsing(tmp_path: Path) -> None:
    """Test JavaScript and TypeScript class, interface, function, and method parsing."""
    ts_code = """/**
 * User service class.
 */
export class UserService {
    public async getUser(id: string): Promise<User> {
        return { id };
    }
}

export interface User {
    id: string;
}

export function createService(): UserService {
    return new UserService();
}

const formatUser = (user: User) => {
    return user.id;
};
"""
    file_path = tmp_path / "service.ts"
    file_path.write_text(ts_code, encoding="utf-8")

    # Search classes and interfaces
    query_class = SymbolSearchQuery(name_pattern="", path=str(file_path), language="typescript", kind=SymbolKind.CLASS)
    class_symbols = search_symbols(query_class)
    assert len(class_symbols) == 2
    class_names = {s.name for s in class_symbols}
    assert class_names == {"UserService", "User"}

    # Search functions
    query_func = SymbolSearchQuery(name_pattern="", path=str(file_path), language="typescript", kind=SymbolKind.FUNCTION)
    func_symbols = search_symbols(query_func)
    assert len(func_symbols) == 2
    func_names = {s.name for s in func_symbols}
    assert func_names == {"createService", "formatUser"}

    # Search method
    query_method = SymbolSearchQuery(name_pattern="getUser", path=str(file_path), language="typescript", kind=SymbolKind.METHOD)
    method_symbols = search_symbols(query_method)
    assert len(method_symbols) == 1
    assert method_symbols[0].name == "getUser"
    assert method_symbols[0].parent_symbol == "UserService"


def test_powershell_symbol_parsing(tmp_path: Path) -> None:
    """Test PowerShell function and filter parsing."""
    ps_code = """# Initialize environment settings
function Init-Environment {
    param([string]$HomeDir)
    Write-Host "Initializing..."
}

# Filter active processes
filter Filter-ActiveProcess {
    return $_.Responding
}
"""
    file_path = tmp_path / "script.ps1"
    file_path.write_text(ps_code, encoding="utf-8")

    query = SymbolSearchQuery(name_pattern="", path=str(file_path), language="powershell")
    symbols = search_symbols(query)
    assert len(symbols) == 2

    names = {s.name for s in symbols}
    assert names == {"Init-Environment", "Filter-ActiveProcess"}
    assert symbols[0].docstring_summary == "Initialize environment settings"


def test_batch_symbol_parsing(tmp_path: Path) -> None:
    """Test Windows Batch label procedure parsing."""
    bat_code = """@echo off

:: Procedure to setup environment
:SetupEnv
echo Setting up...
goto :EOF

REM Procedure to cleanup temporary files
:CleanupTemp
del /q .tmp\\*
goto :EOF
"""
    file_path = tmp_path / "build.bat"
    file_path.write_text(bat_code, encoding="utf-8")

    query = SymbolSearchQuery(name_pattern="", path=str(file_path), language="batch")
    symbols = search_symbols(query)
    assert len(symbols) == 2

    names = {s.name for s in symbols}
    assert names == {"SetupEnv", "CleanupTemp"}
    assert symbols[0].signature == ":SetupEnv"
    assert symbols[0].docstring_summary == "Procedure to setup environment"


def test_multilang_directory_search(tmp_path: Path) -> None:
    """Test automatic multi-language symbol search across a mixed directory."""
    (tmp_path / "app.py").write_text("class PyApp:\n    pass\n", encoding="utf-8")
    (tmp_path / "app.ts").write_text("class TsApp {}\n", encoding="utf-8")
    (tmp_path / "run.ps1").write_text("function Start-App {}\n", encoding="utf-8")
    (tmp_path / "start.bat").write_text(":StartApp\n", encoding="utf-8")

    query_all = SymbolSearchQuery(name_pattern="App", path=str(tmp_path), language="all")
    symbols = search_symbols(query_all)
    assert len(symbols) == 4

    names = {s.name for s in symbols}
    assert names == {"PyApp", "TsApp", "Start-App", "StartApp"}


def test_automatic_language_inference_by_extension(tmp_path: Path) -> None:
    """Verify language auto-inference by file extension when language flag is omitted."""
    from brain.application.symbols import infer_language_from_extension
    from brain.presentation.actions.utilities.command_search_symbol import handle as handle_search_symbol

    assert infer_language_from_extension("script.py") == "python"
    assert infer_language_from_extension("app.js") == "javascript"
    assert infer_language_from_extension("service.ts") == "typescript"
    assert infer_language_from_extension("module.ps1") == "powershell"
    assert infer_language_from_extension("build.bat") == "batch"
    assert infer_language_from_extension("unknown.xyz") is None

    # Test automatic symbol resolution without explicit language flag on a JS file
    js_file = tmp_path / "index.js"
    js_file.write_text("function handleRequest(req) { return req; }\n", encoding="utf-8")

    query = SymbolSearchQuery(name_pattern="handleRequest", path=str(js_file), language="")
    symbols = search_symbols(query)
    assert len(symbols) == 1
    assert symbols[0].name == "handleRequest"

    # Test CLI handle with default empty language on PowerShell file
    ps_file = tmp_path / "deploy.ps1"
    ps_file.write_text("function Deploy-App { Write-Host 'Deploying' }\n", encoding="utf-8")

    class DummyArgs:
        name = "Deploy-App"
        language = ""
        path = str(ps_file)
        kind = "all"
        json = True

    args = DummyArgs()
    status = handle_search_symbol(args)  # type: ignore[arg-type]
    assert status == 0
    payload = getattr(args, "json_payload", {})
    assert payload["ok"] is True
    assert payload["count"] == 1
    assert payload["symbols"][0]["name"] == "Deploy-App"
