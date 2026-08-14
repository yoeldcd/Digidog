<!-- Unauthorized: worker -->
# Brain Commands

You are able to invoke the Environment Brain CLI (requiring elevated shell_permission's). Ensure it exists running:

## cli_checking_commands

```powershell
if (-not (Test-Path -LiteralPath {LOCAL_BRAIN_SCRIPT})) {
    py {AGENT_HOME}/core/core_cli.py create-brain (Get-Location).Path
}
```

To invoke CLI Commands follow pattern `py {LOCAL_BRAIN_SCRIPT} <COMMAND> --authority <AUTHORITY>` like `py {LOCAL_BRAIN_SCRIPT} help --authority root`.

### communication_command

The CLI-based Avatar Messaging System, supports embedded Markdown content (tables, links, images).

`py {LOCAL_BRAIN_SCRIPT} avatar-message $MESSAGE_CONTENT [--emotion EMOTION] [--file FILE_PATH] --timeout 300 --json`.

* Mandatory `--timeout` define await time in seconds until user response (use same process deadtime). Minimun is 300 seconds.
* Use `--file` to show asset document after spoken text. Only `.md` support.
* Message stdout will continue blocked until message emmited, for syncrhronous working.

```powershell
$ASSET_DOCUMENT = 'relative/document.md'
$MESSAGE_CONTENT = @'
Voy a inspeccionar primero el contexto necesario para la tarea...
![Mira esta evidencia](absolute_path/image.png)
'@
py {LOCAL_BRAIN_SCRIPT} avatar-message $MESSAGE_CONTENT --emotion focused --file $ASSET_DOCUMENT --json
```

### task_reporting_command

The CLI-based Avatar Reporting System, supports embedded Markdown content (tables, links, images).

`py {LOCAL_BRAIN_SCRIPT} task-repport --task-id TASK_ID --text "" --timeout 300 --autority <> --json`.

* Mandatory `--timeout` define await time in seconds until user response (use same process deadtime). Minimun is 300 seconds.
* Message stdout will continue blocked until message emmited, for syncrhronous working.

```powershell
py {LOCAL_BRAIN_SCRIPT} task-repport --task-id TASK_ID --text "I modify does..." --timeout 300 --json --autority root
```

## context_commands

`py {LOCAL_BRAIN_SCRIPT} get-context [--domain domain.subdomain] [--json]`. The flag `--domain` provide a `log-index` based acotation.

## query_commands

Access to context information quering: `py {LOCAL_BRAIN_SCRIPT} query "question or keywords" [--source <SOURCE>] [--scope <SCOPE>] [--mechanism <MECHANISM>] [--deep] [--json]`.

### Context Query ~ SCOPE

* `global`: shared agent knowledge.
* `local`: local workspace facts.
* `all`: cross-scope merged.

### Context Query ~ MECHANISM

* `text`: literal word/phrase matches.
* `vector`: semantic meaning across different words.
* `graph`: entity/fact/decision relationships.
* `all`: combined retrieval paths (default).
* `--deep`: deep understanding & question decomposition.

---

## memory_commands
  
* Query flag: `py {LOCAL_BRAIN_SCRIPT} query "ask?" --source memory`
* Memory Tree: `memory-structure --json`
* Retrieve: `get-memory-entry domain.key --json` returns RAW documents on terminal items
* Add Fact: `set-memory-entry domain.subdom.key "content"`

## knowledge_graph_commands

* Query flag: `py {LOCAL_BRAIN_SCRIPT} query "ask?" --source knowledge`
* Consolidate: `dream [--scope all|global|local] [--domain DOMAIN] [--source-path PATH] [--limit N] [--force] [--min-confidence FLOAT] [--prune] --json`

## messages_commands

* Query flag: `py {LOCAL_BRAIN_SCRIPT} query "ask?" --source messages`
* Inspect: `list-messages --json`
* Present: `avatar-message "text" [--emotion <EMOTION>] [--file <FILE_PATH>] --json`

## pictures_commands

* Query flag: `py {LOCAL_BRAIN_SCRIPT} query "ask?" --source pictures`
* Inspect: `list-pictures --json`
* Append Visual: `registre-image --image-file FULLPATH_TO_IMAGE | --image-data "BASE64String" --scope local|global --domain a.b.c [--description "Markdown"] [--index] --json`

## changelogs_commands

(TYPES: feature, fix, refactor, performance, improvement, documentation, maintenance):

* Query flag: `py {LOCAL_BRAIN_SCRIPT} query "ask?" --source logs`
* See change history : `log-index --json`
* Retrieve: `read-log LOG_ID --json`
* Registre entry: `append-log DOMAIN "Title" <TYPE> --why "Why change required..." --desc "What exactly you do..." --impact "What improved..."`
* Update entry: `edit-log TIMESTAMP DOMAIN "Title" <TYPE> --why "Why?" --desc "What?" --impact "Impact?"`

## diary_commands

* Query flag: `py {LOCAL_BRAIN_SCRIPT} query "ask?" --source diary`
* Read diary: `read-diary [DATE] [--time HH:MM]`
* Write diary entry: `write-diary -t "Title" "Entry"`

## policies_commands

* Register new rule: `registre-policie "Policy text" --json`
* Inspect active policies: `show-policies --json`
* Deprecate rule: `deprecate-policie --id rec## --json`

## profiles_commands

Adopt specialized profile behavior aligned to working task on demand.

* Discover Profiles: `list-profiles`
* Adopte a profile: `read-profile NAME`

## utilities_commands

Use or made reusable utilities & helper to solve recurrent tasks on demand.

* Discover Utilities: `list-snippets`
* Read its `README.md` before use.

## task_commands

* Inspect backlog: `task-list`
* Retrieve a task: `read-task tID`
* Registre a task: `add-task domain.subdomain "Outcome" -d "Description" -p PRIORITY`
* Starting a task: `set-task-status tID WORKING`
* Deleting a task: `delete-task tID` under demand.

```powershell
py {LOCAL_BRAIN_SCRIPT} add-task domain.subdomain "Observable outcome" -d "Scope and validation" -p HIGH --json
py {LOCAL_BRAIN_SCRIPT} set-task-status t123 WORKING --json
```

## completion_commands

After user explicitly work acceptance, register the changes:

* **When IS NOT A TASK**: `append-log domain.subdomain "Title" TYPE "Why change required..." "What exactly you do..." "What improved..."`.
* **When IS A TASK**: `complete-work TASK_ID TYPE "What exactly you do...(e.g: Fixed the feature X in module Y)" --stage path/a path/b ... --json`
