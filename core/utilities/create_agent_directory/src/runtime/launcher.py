"""Compose CLI adapters, application use cases, and infrastructure collaborators."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path

from src.adapters.cli import CliCommand, CliParser, CliPresenter, CliRequest, CliResourceLoader
from src.application.create_agent import CreateAgentDirectoryInput, CreateAgentDirectoryUseCase
from src.application.update_agent import UpdateAgentInput, UpdateAgentUseCase
from src.infrastructure.agent_runtime import (
    build_executor_factory,
    build_render_values,
    create_lifecycle,
    path_exists,
    publish_staging,
    read_target_identity,
    resolve_source_root,
    resolve_target_root,
    rollback_staging,
    sibling_staging_path,
    update_lifecycle,
)


def _create_use_case(source_root: Path) -> CreateAgentDirectoryUseCase:
    """Build the create-agent use case with runtime dependencies.

    Args:
        source_root: Canonical source directory for creation operations.

    Returns:
        CreateAgentDirectoryUseCase: Configured creation use case.
    """

    executor_factory = build_executor_factory(source_root)

    return CreateAgentDirectoryUseCase(
        source_root,
        path_exists,
        sibling_staging_path,
        build_render_values,
        executor_factory,
        create_lifecycle,
        publish_staging,
        rollback_staging,
    )


def _update_use_case(source_root: Path, target_root: Path) -> UpdateAgentUseCase:
    """Build the update-agent use case with runtime dependencies.

    Args:
        source_root: Canonical source directory for synchronization.
        target_root: Target directory to update.

    Returns:
        UpdateAgentUseCase: Configured update use case.
    """

    executor_factory = build_executor_factory(source_root)

    return UpdateAgentUseCase(
        source_root,
        target_root,
        path_exists,
        Path.is_file,
        read_target_identity,
        executor_factory,
        build_render_values,
        update_lifecycle,
    )


def _execute(request: CliRequest, source_root: Path, labels: Mapping[str, str]) -> object:
    """Execute a parsed create or update request.

    Args:
        request: Parsed command request.
        source_root: Canonical source directory used by the selected use case.
        labels: Localized error labels for required arguments.

    Returns:
        object: Result returned by the selected application use case.

    Raises:
        ValueError: If required arguments for the selected command are missing.
    """

    if request.command is CliCommand.CREATE:
        if request.parent_path is None or request.agent_name is None or request.user_name is None:
            raise ValueError(labels["create_required"])

        create_input = CreateAgentDirectoryInput(
            request.parent_path,
            request.agent_name,
            request.user_name,
        )
        use_case = _create_use_case(source_root)

        return use_case.execute(create_input)

    if request.target_path is None:
        raise ValueError(labels["update_required"])

    target_root = resolve_target_root(request.target_path)
    use_case = _update_use_case(source_root, target_root)
    update_input = UpdateAgentInput(target_root)

    return use_case.execute(update_input)


def main(argv: Sequence[str], invoked_file: Path) -> int:
    """Parse, execute, and present one CLI request.

    Args:
        argv: Command-line arguments excluding the executable name.
        invoked_file: Path of the launcher file used to resolve source roots.

    Returns:
        int: Process status code returned by the presenter.
    """

    json_mode = "--json" in argv

    try:
        source_root = resolve_source_root(Path(invoked_file))
        resource_path = source_root / "core/utilities/create_agent_directory/files/cli_messages.json"
        labels = CliResourceLoader(resource_path).load()
        parser = CliParser(labels)
        presenter = CliPresenter(labels)
        request = parser.parse(argv)
        result = _execute(request, source_root, labels)
        output = presenter.present(result, request.json_mode)
        print(output)

        return 0
    except Exception as error:
        presenter = CliPresenter()
        output, status = presenter.present_error(error, json_mode)
        print(output)

        return status