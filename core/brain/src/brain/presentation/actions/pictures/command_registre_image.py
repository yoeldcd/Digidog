"""Register one picture through the application registration contract."""

from __future__ import annotations

import argparse
import json
from collections.abc import Mapping
from dataclasses import asdict, is_dataclass
from typing import Any

from brain.presentation.terminal import render_placeholders


COMMAND_NAME = "registre-image"


def register_picture(**kwargs: Any) -> Any:
    """Resolve and invoke the application-level picture registration use case.

    Keeping this import behind a narrow presentation adapter prevents the CLI
    action from depending on infrastructure details while the application
    registration service remains independently testable.

    Args:
        **kwargs: Registration fields accepted by the application contract:
            ``image_file``, ``image_data``, ``scope``, ``domain``,
            ``description``, and ``index``.

    Returns:
        Any: Application registration result, normally a picture mapping or
            picture record exposing ``as_mapping``.
    """
    from brain.application.pictures.registration import register_picture as register_use_case

    return register_use_case(**kwargs)


def _serialize_result(result: Any) -> Any:
    """Convert an application result into JSON-compatible public data.

    Args:
        result: Result returned by the application registration use case.

    Returns:
        Any: Mapping, dataclass dictionary, or scalar representation suitable
            for the command JSON envelope.
    """
    if hasattr(result, "as_mapping") and callable(result.as_mapping):
        return result.as_mapping()
    if is_dataclass(result) and not isinstance(result, type):
        return asdict(result)
    if isinstance(result, Mapping):
        return dict(result)
    if hasattr(result, "__dict__"):
        return dict(vars(result))
    return result


def _validate_arguments(args: argparse.Namespace) -> tuple[str, str, str, str, str, bool]:
    """Validate the public command boundary before invoking the use case.

    Args:
        args: Parsed CLI namespace containing image source, scope, domain,
            description, indexing, and output options.

    Returns:
        tuple[str, str, str, str, str, bool]: Normalized image file, image
            data, scope, domain, description, and indexing values.

    Raises:
        ValueError: If both or neither image sources are supplied, or the scope
            is outside the canonical ``local``/``global`` values.
    """
    image_file = str(getattr(args, "image_file", "") or "").strip()
    image_data = str(getattr(args, "image_data", "") or "").strip()
    scope = str(getattr(args, "scope", "") or "").strip().lower()
    domain = str(getattr(args, "domain", "") or "").strip()
    description = str(getattr(args, "description", "") or "")
    index = bool(getattr(args, "index", False))
    if bool(image_file) == bool(image_data):
        raise ValueError("Provide exactly one of --image-file or --image-data.")
    if scope not in {"local", "global"}:
        raise ValueError("--scope must be either local or global.")
    if not domain:
        raise ValueError("--domain is required.")
    return image_file, image_data, scope, domain, description, index


def handle(args: argparse.Namespace) -> int:
    """Register an image and expose one stable command result envelope.

    Args:
        args: Parsed ``registre-image`` options.

    Returns:
        int: Zero after successful registration; one after validation or use-case
            failure. The semantic payload is always placed on ``args`` for the
            JSON dispatch layer.
    """
    try:
        image_file, image_data, scope, domain, description, index = _validate_arguments(args)
        result = register_picture(
            image_file=image_file,
            image_data=image_data,
            scope=scope,
            domain=domain,
            description=description,
            index=index,
        )
        payload = {
            "ok": True,
            "command": COMMAND_NAME,
            "picture": _serialize_result(result),
        }
        exit_code = 0
    except Exception as exc:
        payload = {"ok": False, "command": COMMAND_NAME, "error": str(exc)}
        exit_code = 1

    args.json_payload = payload
    if getattr(args, "json", False):
        print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))
    elif payload["ok"]:
        picture = payload["picture"]
        relative_path = picture.get("relative_path", "registered image") if isinstance(picture, Mapping) else "registered image"
        print(render_placeholders(f"__GREEN__Registered image__RESET__: {relative_path}", getattr(args, "color", False)))
    else:
        print(render_placeholders(f"__RED__Error: {payload['error']}__RESET__", getattr(args, "color", False)))
    return exit_code
