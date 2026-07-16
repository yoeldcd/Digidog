# Maintain the technical documentation of projects unified, updated, and accessible through interactive HTML wikis

**IMPORTANT**

COMPILE WIKI ONLY UNLESS USER REQUEST. IS A EXPENSIVE COMMAND.

---

## Documentation Directory Structure

The documentation folder lives in `<Project_PATH>/documentation/`. If it does not exist, create it.

Documentation must be structured by **domains** representing the nature of the project (e.g `backend`, `frontend/`, `shared`, `documentation/general/`).

## Domain-Based File Naming and Structure

Files must follow the `<domain>-<topic>.md` naming convention (e.g., `backend-architecture.md`, `frontend-ui-events.md`). **Every file MUST begin with a `# H1 Title`**.

The `<topic>` part must use one of the normalized documentation types defined in this guide, accepeted onlly `architecture`, `design-patterns`, `interfaces`, `models-dto`, `endpoints`, `cli-commands`, `ui-events`, `visual-design`, `ui-design`, `deployment`, or `security`.

## Navigable Header System

To do able the compilation of `**.md` files as navegable HTML wiki: Write documentation `**.md` files as structured heading system where any section is associated an codebase elements declaration, respecting docfile associated to described element nature.

* Every codebase element must be documented:

  * modules
  * package
  * class (properties & methods)
  * interfaces
  * models & DTO class
  * services
  * components
  * cli command (flag, parameter group)
  * functions
  * events
  * route
  * configurations key
  * environment variable
  * workflows
  * other important files

* Tables may index these elements, but the canonical declaration must live under a heading.

* Emphatize these elements and symbols in the plain text using `**bold_blocks**`, backsticks `command_write_files.py`

### Header Rules

* Use exactly one `# H1 Title` per file. The H1 defines the page-level concept.
* Use `##` sections for major user tasks, system areas, command groups, architectural layers, or model families.
* Use `###` sections for concrete navigable entities: commands, files, modules, classes, interfaces, models, components, services, endpoints, events, jobs, configuration groups, or public functions.
* Use `####` sections for subordinate navigable entities: command flags, parameters, method variants, model fields that need explanation, event payload fields, error cases, lifecycle hooks, or implementation details that are referenced from multiple places.
* Put the exact reference term in the heading when that term should be linkable. Use heading shapes like:

```md
### `command-name`
### `SomeClass`
#### `someMethod()`
#### `--flag-name`
### `src/runtime/index.ts`
```

* Headings must be unique enough inside a page to be useful as anchors. If two entities share a name, qualify the heading with its owner:

```md
#### `Parser.build()`
#### `Renderer.build()`
```

* Do not hide important entities only inside paragraphs. If another document might reference it, promote it to a heading.

### Entity Section Contract

Each navigable entity section must start with a plain explanation before listing parameters.

For commands, use this minimum shape:

```md
### `command-name`

**What It Does:** One or two sentences describing the command's responsibility.

**Use It When:** The practical situation where this command is the right tool.

**Result:** What changes, what is printed, what files are touched, or what state is produced.

| Parameter | Required | Default | Description |
|---|---|---|---|
| `--flag` | No | `value` | Concrete behavior, not only type information. |
```

For files, classes, services, functions, and methods, use this minimum shape:

```md
### `path/or/SymbolName`

**What It Does:** The responsibility this entity owns.

**Used By:** Main callers, commands, pages, or workflows that depend on it.

**Contract:** Inputs, outputs, side effects, errors, persistence, or events.
```

## Spec DocFiles Catalog

This catalog show overview of spec documents structures. **GENERATE ONLY the docfiles aligned to project nature & structure.**

### General Overview (`README.md`) (REQUIRED)

```md (DONT INCLUDE TEMPLATTING ${for_block} IN FINAL TEXTs)
# {project_name}

## Index:
- [Overview](#overview)
- [Domains Taxonomy](#domains-taxonomy)
- [Getting Started](#getting-started)

## Overview:
High-level description of the project, its core value proposition, and main goals.

## Domains Taxonomy:
Brief list of the main directories / sub-projects in the codebase.
${for each (domain ... domains) => {
{domain}/
${for each (subdomain ... subdomains) => {
  └── {subdomain}/
}}
}}

## Getting Started:
Quick instructions to run the project locally.

### Installation:
```bash
```

### Dev Commands

```bash
```

```

### 1. Architecture (`*-architecture.md`)

```md (DONT INCLUDE TEMPLATTING ${for_block} IN FINAL TEXTs)
# {domain} Architecture

## Index:
- [Overview](#overview)
- [Component Diagram](#component-diagram)
- [Infrastructure & Decisions](#infrastructure--decisions)

## Overview:
High-level summary of the domain's purpose.

## Component Diagram: 
A `mermaid` code block visually representing the infrastructure, component relationships, or data flow.
${for each (domain ... subdomains) => {
  ## `{domain}.{subdomian}.subs...`
  
  ### Infrastructure: 
  [#### components]
  [#### services]
  [#### databases]
  [#### external dependencies.]

  ### Key Decisions:
  ${for each (decision ... decisions) => {
     #### Context
     #### Alternatives Considered
     #### Chosen Solution.
  }}
}}
```

### 2. Design Patterns (`*-design-patterns.md`)

```md (DONT INCLUDE TEMPLATTING ${for_block} IN FINAL TEXTs)
# {domain} Design Patterns

## Index:
- [Overview](#overview)
- [Core Patterns](#core-patterns)
- [Anti-Patterns](#anti-patterns)

${for each (domain ... subdomains) => {
  ## `{domain}.{subdomian}.subs...`
  ### Pattern Category
  #### Pattern Declaration
  Detail the pattern and explain *why* it is used in this domain.
  ### Anti-Patterns: 
  List practices that must be avoided within this domain and why.
  ### Implementation Examples: 
  Provide a brief, canonical language-specific code block demonstrating the correct usage of the pattern.
}}
```

### 3. Functiona Interfaces & Contracts (`*-interfaces.md`)

```md (DONT INCLUDE TEMPLATTING ${for_block} IN FINAL TEXTs)
# {domain} Interfaces & Contracts

## Index:
- [Interface Index](#interface-index)
- [Functional Interfaces](#functional-interfaces)
- [Service Contracts](#service-contracts)
- [Repository Contracts](#repository-contracts)

## Interface Index:
List Language-specific code blocks defining primary object shapes.

${for each (domain ... subdomains) => {
  ## `{domain}.{subdomian}.subs...`
  ### Functiona Interfaces
  ### Service Contracts:
  Document the expected inputs and outputs of domain services. Must list methods, parameter types, and return types.
  ### Repository Contracts:
  Document data-access layer interfaces.
}}
```

### 4. Domain Models & DTOs (`*-models-dto.md`)

```md (DONT INCLUDE TEMPLATTING ${for_block} IN FINAL TEXTs)
# {domain} Models & DTOs

## Index:
- [Overview](#overview)
- [Domain Models](#domain-models)
- [Data Transfer Objects (DTOs)](#data-transfer-objects-dtos)

## Overview:
High-level summary of the domain models and DTOs.

${for each (domain ... subdomains) => {
  ## `{domain}.{subdomian}.subs...`

  ### Domain Models:
  ${for each (model ... models) => {
     #### `{model_name}`
     What business entity this model represents.
     
     | Field Name | Data Type | Required (Yes/No) | Constraints / Description |
     |---|---|---|---|
  }}

  ### Data Transfer Objects (DTOs):
  ${for each (dto ... dtos) => {
     #### `{dto_name}`
     Purpose of the DTO (e.g., input validation, API request/response payload).
     
     | Field Name | Data Type | Required (Yes/No) | Constraints / Description |
     |---|---|---|---|
  }}
}}
```

### 5. API Endpoints (`*-endpoints.md`)

```md (DONT INCLUDE TEMPLATTING ${for_block} IN FINAL TEXTs)
# {domain} API Endpoints

## Index:
- [Base Configuration & Auth](#base-configuration--auth)
- [Endpoints Matrix](#endpoints-matrix)
- [Endpoint Details](#endpoint-details)

## Base Configuration & Auth:
Base URL: `<BASE_URL>`
Auth Method: e.g. Bearer Token, API Key

${for each (domain ... subdomains) => {
  ## `{domain}.{subdomian}.subs...`

  ### Endpoint Index:
  | Method | Path | Auth Required | Description |
  |---|---|---|---|

  ### Endpoint Details:
  ${for each (endpoint ... endpoints) => {
     #### `{Method} {Path}`
     Detailed explanation of the endpoint's behavior.
     
     **Request Headers:**
     ```http
     ```
     
     **Request Payload Schema:**
     ```json
     ```
     
     **Response Payload Schema (Success 2xx):**
     ```json
     ```
     
     **Error Responses (4xx/5xx):**
     | Code | Status | Description |
     |---|---|---|
  }}
}}
```

### 6. CLI Commands (`*-cli-commands.md`)

*Use this instead of endpoints.md for command-line tools.*

```md (DONT INCLUDE TEMPLATTING ${for_block} IN FINAL TEXTs)
# {domain} CLI Commands

## Index:
- [CLI Architecture](#cli-architecture)
- [Global Flags](#global-flags)
- [Commands Index](#commands-index)
- [Command Details](#command-details)

## CLI Architecture:
Overview of command parser composition.

## Global Flags:
| Flag | Type | Description |
|---|---|---|

${for each (domain ... subdomains) => {
  ## `{domain}.{subdomian}.subs...`

  ### Commands Index:
  | Command | Arguments | Flags | Description |
  |---|---|---|---|

  ### Command Details:
  ${for each (command ... commands) => {
     #### `{command_name}`
     **What It Does:** ...
     **Use It When:** ...
     **Result:** ...
     
     **Arguments & Flags:**
     | Parameter | Required | Default | Description |
     |---|---|---|---|
  }}
}}
```

### 7. UI Events & State (`*-ui-events.md`)

```md (DONT INCLUDE TEMPLATTING ${for_block} IN FINAL TEXTs)
# {domain} UI Events & State

## Index:
- [Global State & Events](#global-state- & -events)
- [Component Event Triggers](#component-event-triggers)
- [State Mutations Matrix](#state-mutations-matrix)

## Global State & Events:
System-wide events and state context.

${for each (domain ... subdomains) => {
  ## `{domain}.{subdomian}.subs...`

  ### Component Event Triggers:
  ${for each (component ... components) => {
     #### `{component_name}`
     Visual elements triggering state actions.
  }}

  ### State Mutations Matrix:
  | Event Name | Trigger Condition | Payload Emitted | Resulting State Change |
  |---|---|---|---|
}}
```

### 8. Visual & UI Design (`*-visual-design.md` or `*-ui-design.md`)

```md (DONT INCLUDE TEMPLATTING ${for_block} IN FINAL TEXTs)
# {domain} Visual & UI Design

## Index:
- [Design System & Typography](#design-system--typography)
- [Global Colors (HSL)](#global-colors-hsl)
- [Component Visual Specs](#component-visual-specs)

## Design System & Typography:
Font families, weights, rem/px mappings, CSS tokens.

## Global Colors (HSL):
HSL color palette overrides.

${for each (domain ... subdomains) => {
  ## `{domain}.{subdomian}.subs...`

  ### Component Visual Specs:
  ${for each (component ... components) => {
     #### `{component_name}`
     Specs for visual states:
     - **Idle / Default**: ...
     - **Hover**: ...
     - **Active / Pressed**: ...
     - **Disabled**: ...
     - **Error**: ...
     - **Success**: ...
  }}
}}
```

### 9. Deployment Guide (`*-deployment.md`)

```md (DONT INCLUDE TEMPLATTING ${for_block} IN FINAL TEXTs)
# {domain} Deployment Guide

## Index:
- [Prerequisites](#prerequisites)
- [Environment Configuration](#environment-configuration)
- [Build & Setup Steps](#build--setup-steps)
- [Deployment Verification](#deployment-verification)
- [Rollback Procedures](#rollback-procedures)

## Prerequisites:
Required tooling, dependencies, and environment versions.

${for each (domain ... subdomains) => {
  ## `{domain}.{subdomian}.subs...`

  ### Environment Configuration:
  | Variable Name | Required | Default Value | Description |
  |---|---|---|---|

  ### Build & Setup Steps:
  ${for each (step ... steps) => {
    1. Action: ...
       ```bash
       ```
  }}

  ### Deployment Verification:
  Commands to verify deployment state.
}}

## Rollback Procedures:
Steps to safely restore previous version.
```

### 10. Security Model (`*-security.md`)

```md (DONT INCLUDE TEMPLATTING ${for_block} IN FINAL TEXTs)
# {domain} Security Model

## Index:
- [Authentication Model](#authentication-model)
- [Authorization Matrix](#authorization-matrix)
- [Data Privacy Constraints](#data-privacy-constraints)

## Authentication Model:
Authentication flow details.

${for each (domain ... subdomains) => {
  ## `{domain}.{subdomian}.subs...`

  ### Authorization Matrix:
  | Resource / Action | Administrator | Developer | User | Guest |
  |---|---|---|---|---|

  ### Data Privacy Constraints:
  PII / Encryption at transit or rest specifics.
}}
```

---

## Documentation Generation Workflow

To render Markdown files as a premium, navigable HTML wiki, do the following:

1. Ensure the project contains `$agent/scripts/documentation_utils/documentation_cli.js`. If missing, clone it from snippets `documentation_utils`.
2. Check documentation before generating: `node '$agent/scripts/documentation_utils/documentation_cli.js' check <Project_PATH>/documentation`
3. Compile the documentation running: `node '$agent/scripts/documentation_utils/documentation_cli.js' generate <Project_PATH>/documentation --log-domain <LOG_DOMAIN>`
   It generates a navigable live Markdown wiki on output dir `<Project_PATH>/documentation/wiki`
   Use log domain named associated to documented sources in log index: `$agent/scripts/brain.py log-index`
4. Serve the generated wiki when live Markdown fetching is needed: `node '$agent/scripts/documentation_utils/documentation_cli.js' serve <Project_PATH>/documentation`

**IMPORTANT**

COMPILE **WIKI ONLY UNLESS USER REQUEST**. IS A EXPENSIVE COMMAND.

The wiki output directory is always `<Project_PATH>/documentation/wiki`. If the flag `--log-domain` is omitted, the generator falls back to heuristic pattern matching from the source project name.

## NOTICE

**These rules apply to general documentation, or per sub-projects documentation. Do not include live memory logs (changelog, backlog, agent-logs) in the static wiki documentation; those are managed exclusively by `brain.py`.**
