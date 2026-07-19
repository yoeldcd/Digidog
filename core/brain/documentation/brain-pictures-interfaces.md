<!-- Author: Yoel David <yoeldcd@gmail.com> | X: https://x.com/SAY6267 -->

# Brain Picture Intelligence & img2text

## Index

- [Purpose](#purpose)
- [Runtime Configuration Contract](#runtime-configuration-contract)
- [Recognition Guidance](#recognition-guidance)
- [Picture Lifecycle](#picture-lifecycle)
- [CLI Contracts](#cli-contracts)
- [Explorer API Contracts](#explorer-api-contracts)
- [Persistence and Search](#persistence-and-search)
- [Knowledge Graph Projection](#knowledge-graph-projection)
- [Failure and Security Behavior](#failure-and-security-behavior)
- [Operational Examples](#operational-examples)

## Purpose

Digidog treats images as canonical knowledge sources. The picture subsystem discovers files under the agent
picture directory, stores durable metadata and descriptions, optionally generates descriptions through an
OpenAI-compatible vision model, indexes the resulting text for retrieval, and projects evidence-bound entities
and relations into the global knowledge graph.

The displayed image remains the source artifact. Model output is descriptive metadata and never replaces or
rewrites the image. Manual descriptions and model descriptions share the same persistence contract, while the
`description_source` field records whether the current value came from `manual` input or `image_model`.

## Runtime Configuration Contract

Picture behavior is configured by the `pictures` object in `core/configs/brain_configs.json`. The runtime validates
this object with `PicturesConfigDTO`; unknown properties are rejected. The following is a generic schema mockup,
not a copy of any live agent configuration:

```json
{
  "pictures": {
    "guidance": {
      "tags": {
        "example-label": "Apply only when an explicit, observable criterion is visible."
      },
      "characters": {
        "Example Character": "Distinctive visible traits used only when the image clearly matches."
      }
    },
    "image_model": {
      "model": "provider/vision-model",
      "base_url": "https://provider.example/v1",
      "api_key": "$VISION_API_KEY",
      "temperature": 0.1,
      "max_tokens": 1200,
      "enabled": false
    },
    "supported_extensions": [
      ".png",
      ".jpg",
      ".jpeg",
      ".webp",
      ".gif",
      ".bmp"
    ]
  }
}
```

`image_model` uses the shared `StageModelConfigDTO` contract:

| Field | Contract |
|---|---|
| `model` | Provider model identifier sent in the request body. |
| `base_url` | OpenAI-compatible API root; the client calls `/chat/completions`. |
| `api_key` | Secret value or environment reference such as `$VISION_API_KEY`. |
| `temperature` | Sampling temperature from `0.0` through `2.0`. |
| `max_tokens` | Maximum output tokens from `128` through `20000`. |
| `enabled` | External img2text calls are rejected when `false`; manual descriptions still work. |

The factory seed intentionally uses an empty guidance map and a disabled generic image model. A developer must
choose a compatible provider/model, configure the referenced environment variable, and enable the stage before
model-backed description is available.

## Recognition Guidance

Guidance has two supported collections:

- `characters` maps a stable character name to distinguishing, observable visual traits.
- `tags` maps a semantic label to the visible evidence required to apply it.

The prompt builder sorts configured entries, adds them after the caller's base prompt, and gives the model four
binding rules: use exact names only on a clear match, apply tags only when their criteria are satisfied, never
force a configured label, and avoid hidden relationships, emotions, or sensitive-attribute inference.

Guidance improves naming consistency; it is not an assertion that an identity or tag exists in every image.
Character recognition requires the configured name to appear explicitly as a complete token in the returned
description. Tag recognition is stricter: the configured name must appear in a Markdown `Semantic Tags:` field.
This prevents ordinary prose from accidentally producing tag relations.

Guidance mutations load and validate the complete brain configuration, trim required values, reject sections
other than `tags` or `characters`, and replace the JSON file atomically through a temporary file.

## Picture Lifecycle

1. `scan-images` recursively discovers supported image files and reads their hash, MIME type, dimensions, size,
   timestamp, relative path, and folder-derived domain.
2. The scanner recognizes additions, content changes, moves, unchanged files, and deletions. Moves preserve the
   stable picture identifier and existing description.
3. A content change invalidates a model-generated description because it may no longer describe the source.
   Manual descriptions are retained. Any affected vector fingerprint is cleared.
4. `describe-image` accepts manual text or calls the configured img2text model. Batch modes isolate failures per
   file so one failed request does not discard successful descriptions.
5. Changed descriptive text is synchronized into the picture vector index and projected into canonical graph
   entities and relations.

The default model prompt requests factual subjects, setting, activity, visible objects, colors, mood, and legible
text for semantic search, while explicitly prohibiting sensitive-attribute inference. A `--prompt` override
replaces that base instruction but still receives configured recognition guidance.

The img2text request embeds the source as a MIME-qualified base64 data URL and sends a multimodal user message to
the configured OpenAI-compatible `/chat/completions` endpoint. The request timeout is 60 seconds.

## CLI Contracts

Commands are available through the workspace wrapper, for example `py '$agent/scripts/brain.py' COMMAND --json`.

| Command | Purpose |
|---|---|
| `picture-status` | Scan and report registry health, domains, description counts, extensions, and model state. |
| `list-pictures` | List, search, or filter active registry records; accepts `--id`, `--domain`, `--query`, `--all`, and `--limit`. |
| `scan-images` / `scan-pictures` | Synchronize the image filesystem; `--describe` fills empty descriptions and `--index` refreshes vectors. |
| `describe-image` / `describe-picture` | Save manual text for one picture or invoke img2text when text is omitted. |
| `list-picture-guidance [section]` | Return both guidance collections or only `tags`/`characters`. |
| `set-picture-guidance SECTION NAME DESCRIPTION` | Create or replace one guidance entry. |
| `delete-picture-guidance SECTION NAME` | Delete an existing guidance entry. |

`describe-image` supports one-picture and batch modes. `--all` regenerates descriptions for every active image;
`--undescribed` and its compatibility alias `--undescribeds` process only empty descriptions. Batch flags are
mutually exclusive and cannot be combined with a picture identifier or manual description.

## Explorer API Contracts

Brain Explorer exposes bounded local endpoints over the same registry and description services:

| Endpoint | Contract |
|---|---|
| `GET /api/pictures` | Returns records; supports `picture_id`, `domain`, `q`, `refresh`, and `structure_only`. |
| `GET /api/pictures/file` | Streams a registered image through the server's validated picture-file route. |
| `POST /api/pictures/description` | Accepts `pictureId`, optional `description`, and optional `prompt`; then refreshes vectors. |

Every Explorer record includes a validated absolute path for copy/open actions. The server resolves that path
under the configured picture root and rejects a registry path that escapes the directory. The image details view
uses the same canonical record for its preview, collapsible Markdown analysis sections, entity/tag badges, manual
editing, model regeneration, and navigation to the dedicated Pictures section.

## Persistence and Search

The canonical picture registry is SQLite-backed. Each active record contains a stable ID, relative path, domain,
filename, extension, MIME type, size, modification time, content hash, dimensions, description,
`description_source`, description timestamp, vector fingerprint, activity state, and creation/update timestamps.

Descriptions survive ordinary rescans and file moves. Updating a description clears its vector fingerprint so the
next synchronization cannot reuse a stale semantic vector. Query integration returns picture references with a
read command of the form `list-pictures --id ID --json`, allowing search results to resolve back to their
canonical source.

## Knowledge Graph Projection

Each described active image is projected into the global graph with a canonical source path of
`pictures/RELATIVE_PATH` and the following structure:

```text
MISC.Description --describes--> FILE.Picture
FILE.Picture --depicts--> MISC.Noun
FILE.Picture --has_tag--> MISC.Tag
```

The `FILE.Picture` and `MISC.Description` entities retain the current description. Recognized character nouns use
the configured character description; recognized tags use the configured tag criterion. Before reprojection,
relations owned by that picture source are removed so obsolete `depicts` and `has_tag` assertions do not linger.

Character guidance itself is also canonical knowledge. Each configured character produces a
`MISC.Description --describes--> MISC.Noun` association under the stable configuration source
`configs/brain_configs.json#pictures.guidance.characters`. The noun's canonical name equals the guidance key; the
description entity contains the visual recognition text. This association does not claim that the character
appears in any image. An image receives `depicts` only after explicit evidence appears in its generated or manual
description.

## Failure and Security Behavior

- A disabled model produces a clear error and does not prevent manual descriptions.
- An unresolved or missing environment-referenced API key rejects the external call.
- HTTP failures propagate as per-picture failures; batch processing continues with later images.
- Empty provider output is rejected instead of being stored as a valid description.
- The API key is sent only in the authorization header and should remain an environment reference in JSON.
- Picture paths are resolved below the canonical picture root before Explorer exposes an absolute path.
- Guidance descriptions should contain observable recognition criteria, never credentials or private prompt data.

## Operational Examples

Inspect the subsystem before enabling a provider:

```powershell
py '$agent/scripts/brain.py' picture-status --json
py '$agent/scripts/brain.py' list-picture-guidance --json
py '$agent/scripts/brain.py' list-pictures --limit 20 --json
```

Manage generic guidance:

```powershell
py '$agent/scripts/brain.py' set-picture-guidance tags "example-label" "Apply only when the defining object is clearly visible." --json
py '$agent/scripts/brain.py' set-picture-guidance characters "Example Character" "Distinctive visible traits for this identity." --json
py '$agent/scripts/brain.py' delete-picture-guidance tags "example-label" --json
```

Scan, describe, and inspect:

```powershell
py '$agent/scripts/brain.py' scan-images --index --json
py '$agent/scripts/brain.py' describe-image PICTURE_ID "Manual factual Markdown description." --json
py '$agent/scripts/brain.py' describe-image PICTURE_ID --prompt "Describe visible evidence in structured Markdown." --json
py '$agent/scripts/brain.py' describe-image --undescribed --json
```
