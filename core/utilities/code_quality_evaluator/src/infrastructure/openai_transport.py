"""Official OpenAI-compatible transport adapter with safe failures."""

from __future__ import annotations

import os
from collections.abc import Mapping

from openai import OpenAI

from ..domain.models import ModelSpec


class OpenAITransport:
    """Call an HTTPS OpenAI-compatible endpoint without persistence."""

    def complete(
        self,
        model: ModelSpec,
        system_prompt: str,
        user_prompt: str,
        response_schema: Mapping[str, object],
    ) -> str:
        """Submit prompts and return text, redacting provider failures.

        Args:
            model: Immutable HTTPS model and sampling configuration.
            system_prompt: System instruction sent to the provider.
            user_prompt: User content sent to the provider.
            response_schema: JSON schema mapping requested from the provider.

        Returns:
            str: Provider response content.

        Raises:
            RuntimeError: If credentials, endpoint, provider call, or content is invalid.
        """

        if model.base_url.scheme != "https" or not model.api_key.startswith("$"):
            raise RuntimeError("semantic transport unavailable")

        credential = os.environ.get(model.api_key[1:])

        if not credential:
            raise RuntimeError("semantic transport unavailable")

        try:
            client = OpenAI(
                api_key=credential, base_url=str(model.base_url), timeout=30.0
            )
            completion = client.chat.completions.create(
                model=model.model,
                temperature=model.temperature,
                max_tokens=model.max_tokens,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "name": "semantic_result",
                        "schema": dict(response_schema),
                    },
                },
            )
            content = completion.choices[0].message.content

            if not content:
                raise RuntimeError("semantic transport unavailable")

            return content

        except Exception as error:
            raise RuntimeError("semantic transport unavailable") from error
