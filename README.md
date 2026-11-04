# FloChat

**Your Live Chat, Always Within Reach.**

FloChat is a cross-platform, GitHub-distributed, terminal-launched utility that helps you
prepare, review, and submit **authorized comments** to YouTube Live Chat from a compact
floating control panel — instead of repeatedly switching apps to hunt for a comment box.

> **Current status: Phase 01 (Foundation) complete.** FloChat is a working CLI foundation with
> an honest capability report. There is **no** YouTube OAuth, **no** live chat discovery, **no**
> comment submission, **no** overlay, and **no** background service yet. Nothing in this
> repository claims otherwise. See [Phase 01 Completion Report](#phase-01-completion-report).

---

## Table of Contents

1. [Project Identity](#project-identity)
2. [Purpose](#purpose)
3. [Supported Platforms](#supported-platforms)
4. [Architecture](#architecture)
5. [Technology Choices](#technology-choices)
6. [Core Component Responsibilities](#core-component-responsibilities)
7. [Platform Adapter Responsibilities](#platform-adapter-responsibilities)
8. [Lifecycle: Persistent, Manual, and Background](#lifecycle-persistent-manual-and-background)
9. [YouTube Integration Boundaries](#youtube-integration-boundaries)
10. [Local Storage and Data Model](#local-storage-and-data-model)
11. [Security Standards](#security-standards)
12. [Privacy Standards](#privacy-standards)
13. [Comment Submission Safety](#comment-submission-safety)
14. [UI Design System](#ui-design-system)
15. [Error Handling and Application States](#error-handling-and-application-states)
16. [Development Standards](#development-standards)
17. [Installation and Launch Direction](#installation-and-launch-direction)
18. [Verification Results](#verification-results)
19. [Phase 01 Completion Report](#phase-01-completion-report)
20. [Repository File Inventory](#repository-file-inventory)
21. [Known Limitations](#known-limitations)
22. [Pending Work and Approved Roadmap](#pending-work-and-approved-roadmap)

---

## Project Identity

| Property | Value |
| --- | --- |
| Name | FloChat |
| Tagline | Your Live Chat, Always Within Reach. |
| Product type | Cross-platform, GitHub-distributed, terminal-launched utility/tool |
| Distribution | Source in a Git repository; cloned and launched from the terminal with platform-specific commands and scripts |
| Primary interface | The terminal (installation and launch) |
| Shared implementation | One Python core |
| Platform-specific layer | Thin native adapters per operating system |
| Version | 0.1.0 (Phase 01) |
| Licence | Not selected yet — required before Phase 08 release |

FloChat is **not** a conventional mobile app, website, web app, or desktop-first standalone
product. A native companion component (for example an Android APK providing a floating
overlay) may later be required for operating-system features such as always-on-top panels.
That companion is an **implementation dependency**, not a change to FloChat's product
identity: the terminal remains the installation and launch interface.

---

## Purpose

A YouTube Live giveaway host may ask participants to enter by commenting with their
username. The usual workflow is clumsy: leave what you are doing, find the stream, find the
comment box, type, hope you did not mistype, and check whether it appeared.

FloChat reduces that to a deliberate, visible workflow:

1. Enter a username once.
2. Prepare the comment.
3. Preview the exact text that would be sent.
4. Select the intended eligible YouTube Live Chat.
5. Review the target and the text.
6. **Explicitly approve that single submission.**
7. Receive a confirmed result, or a clear explanation of why it failed.

Example comment: `My username is @Sarthak123`

The product prioritises **convenience, user control, transparency, and compliance** with
YouTube's policies. Convenience never overrides control or compliance.

FloChat is not a marketing or engagement tool, and it does not generate traffic, automate
repetition, or bypass any platform restriction.

---

## Supported Platforms

FloChat targets four platforms, each launched from the terminal:

| Platform | Terminal environment | Shell | Status in Phase 01 |
| --- | --- | --- | --- |
| Android | Termux and compatible terminal environments | `bash` (Termux) | Core runs anywhere Python 3.10+ runs; **Termux not verified this phase** |
| Windows | PowerShell, Windows Terminal | PowerShell / `cmd` | Core is platform-neutral; **not verified this phase** |
| Linux | GNOME Terminal, Konsole, xterm, Alacritty, Kitty, foot, Tilix | `bash` / `zsh` | **Verified in a Linux x86_64 sandbox** (see [Verification](#verification-results)) |
| macOS | Terminal, iTerm2, and compatible shells | `zsh` / `bash` | Core is platform-neutral; **not verified this phase** |

Platform detection reports what is true on the machine it runs on. It does not assume an
adapter exists, and it deliberately reports `unknown` for anything it cannot establish (for
example filesystem case sensitivity on Linux). Detection of Android relies on Termux markers
(`PREFIX`, `TERMUX_VERSION`) or `/system/build.prop`; a non-Termux Android terminal is flagged
as unverified rather than silently trusted.

---

## Architecture

FloChat uses a **shared core with explicit platform-adapter boundaries**. The core never
imports a native toolkit, and adapters never contain business logic. This keeps the comment
workflow identical on every platform while allowing each OS to supply overlays, permissions,
and secure storage in its own way.

```
Terminal (user)
     │
     ▼
┌──────────────────────────────────────────────────────────────┐
│ CLI boundary            src/flochat/cli.py                    │
│   argparse command surface, exit codes, JSON envelope         │
└───────────────────────────┬──────────────────────────────────┘
                            ▼
┌──────────────────────────────────────────────────────────────┐
│ Application controller  src/flochat/controller.py             │
│   the only place where boundaries are combined                │
└───┬──────────┬───────────┬──────────────┬───────────────┬────┘
    ▼          ▼           ▼              ▼               ▼
 config     state      lifecycle      comments         database
 (config)  (state)     (lifecycle)    (comments)      (database)
    │                                     │
    │                                     ▼
    │                              youtube (boundary)
    ▼
 platform ──► adapters (Android / Windows / Linux / macOS)
               errors  (shared error hierarchy)
```

### Repository layout (actual, not aspirational)

```
FloChat/
├── .env.example                 # environment template, secrets-free
├── .gitignore                   # credential, database, and build exclusions
├── README.md                    # the single central documentation file
├── pyproject.toml               # package, dependency, and Ruff configuration
├── src/
│   └── flochat/
│       ├── __init__.py          # package identity and version
│       ├── adapters.py          # platform adapter contract + four adapter descriptors
│       ├── cli.py               # terminal entry point, exit codes, JSON output
│       ├── comments.py          # comment manager boundary + validation
│       ├── config.py            # configuration loading, validation, logging setup
│       ├── controller.py        # application controller
│       ├── database.py          # SQLite boundary and schema
│       ├── errors.py            # error hierarchy
│       ├── lifecycle.py         # manual/persistent session management
│       ├── platform.py          # platform and capability detection
│       ├── state.py             # application states and status reports
│       └── youtube.py           # OAuth, API, live chat, and API-error boundaries
└── scripts/
    └── check_repository.py      # repository orientation and secret guard
```

There is intentionally **no** `docs/`, `documentation/`, `reports/`, `examples/`, or `tests/`
folder, and no placeholder modules. Every file above is imported or executed by Phase 01.
Folders for future work will be created in the phase that needs them.

### Separation rules

1. **CLI → Controller.** The CLI parses arguments and renders output. It never implements
   behaviour. A future floating panel or companion app calls `Controller` instead of the CLI.
2. **Controller → boundaries.** Only `controller.py` imports configuration, platform,
   lifecycle, storage, and YouTube together.
3. **Core → no native code.** Nothing under `src/flochat` imports Kotlin, C#, Qt, or Swift.
   Adapters describe requirements; they never claim a capability that has not been verified.
4. **Boundaries are real, not stubs.** Each boundary either does something truthful or raises
   a clear "not implemented in this phase" error. There is no code that pretends to succeed.

---

## Technology Choices

| Component | Choice | Phase 01 decision |
| --- | --- | --- |
| Shared core | Python ≥ 3.10 | **Implemented** |
| CLI framework | `argparse` (standard library) | **Implemented**; Typer is approved for Phase 02 |
| Data validation | Pydantic 2 | **Implemented** |
| Local database | SQLite via `sqlite3` | **Implemented** (schema only; no comment writes) |
| Code quality | Ruff (lint + format), standard-library `ast` syntax check | **Implemented** |
| Repository guard | `scripts/check_repository.py` (standard library) | **Implemented** |
| Automated tests | Pytest | **Deferred** — see [Verification](#verification-results) |
| Android adapter / overlay | Kotlin | Boundary only |
| Windows adapter / overlay | C# / WinUI | Boundary only |
| Linux adapter / overlay | Python / Qt where compatible | Boundary only |
| macOS adapter / overlay | Swift / AppKit | Boundary only |
| Credential protection | Platform secure storage (Android Keystore, Windows Credential Manager, Secret Service, macOS Keychain) | Boundary only |

### Dependency policy

Phase 01 installs exactly **one** runtime dependency: `pydantic>=2.6,<3`. It is used for
configuration validation with precise, user-facing errors, which the security and reliability
standards require.

Deliberate exclusions and why:

* **Typer** — approved for the CLI, but adopting it before the real command surface exists
  would add dependencies for no Phase 01 benefit. The `argparse` surface is designed so that
  Phase 02 can move to Typer without changing command names, exit codes, or the JSON envelope.
* **Google API client libraries** — belong to Phase 04, when there is OAuth and API code that
  actually needs them.
* **Pytest** — no test suite exists yet, so it is not installed (see the testing rule in the
  completion report).
* **GUI/native toolkits** — belong to Phase 06.

Rule for later phases: add a dependency only when the current phase needs it, and document why
in this file.

---

## Core Component Responsibilities

### CLI — `src/flochat/cli.py` (implemented)

* Entry point for the `flochat` console script and `python -m flochat.cli`.
* Commands: `version`, `status`, `platform`, `config show`, `config validate`, `start`, `stop`.
* `--json` emits a stable machine-readable envelope for scripts and future interfaces.
* Exit codes: `0` success, `1` failure/pending, `2` invalid usage or configuration,
  `3` unsupported platform or required permission.
* Does not implement behaviour; delegates to the controller.

### Controller — `src/flochat/controller.py` (implemented)

* Builds configuration, platform information, and a session manager.
* Combines boundaries into the reports behind `status`, `platform`, `config`, `start`, `stop`.
* Performs a real database open/verify/close cycle during `status` so the reported health is
  observed, not assumed.
* Maps persistent mode to `permission_required` with the adapter's actual permission list.

### Configuration — `src/flochat/config.py` (implemented)

* Precedence: `FLOCHAT_*` environment variables → `<data dir>/config.json` → built-in defaults.
* Strict schema: unknown keys are rejected rather than silently ignored.
* Refuses configuration files containing credential field names.
* Paths must be absolute, so a relative path cannot silently resolve inside the repository.
* `configure_logging()` sets up a single stderr handler on the `flochat` logger.
* Environment variables are used (in addition to a file) because they survive `sudo` on Linux
  and macOS, and avoid the `$env:` scoping pitfall in PowerShell.

### State and status — `src/flochat/state.py` (implemented)

* The single vocabulary of application states (see
  [Error Handling](#error-handling-and-application-states)).
* `StatusReport` carries state, detail, notes, and a `confirmed` flag. `ok` is true **only**
  when the state is success **and** the result was confirmed — the project rule against
  reporting unverified success is enforced in the type, not in prose.

### Lifecycle — `src/flochat/lifecycle.py` (implemented for manual mode)

* `SessionManager` owns the current session: `start`, `stop`, `note_interruption`, `recover`.
* Manual mode is a real, working session object scoped to the terminal process.
* Persistent mode reports `permission_required` and lists what is missing; it never claims
  background availability.
* `recover()` never restores a session and never resubmits anything; it explains what the user
  must do next.

### Comment manager — `src/flochat/comments.py` (boundary + safe validation)

* `normalize_text()` strips invisible/bidirectional control characters and collapses accidental
  whitespace, so the previewed string is exactly the submitted string.
* `normalize_handle()` / `is_valid_handle()` validate YouTube-style handles (`@` plus 3–30
  characters from letters, digits, `.`, `-`, `_`).
* `validate_comment()` reports empty text, length overflow, unsupported control characters, and
  excessive blank lines. A clean result is a local check only — YouTube can still refuse.
* `ensure_approved()` raises if approval is not explicitly `True`. Every future submission path
  must call it.
* `submit()` is not implemented and raises `NotSupportedYetError` naming Phase 04. It refuses
  to pretend.

Approval manager and safety engine: the guard (`ensure_approved`) and the storage columns
(`state`, `approved_at`, `submitted_at`) exist now; the full approval and safety engines are
Phase 05 by design.

### Database — `src/flochat/database.py` (boundary + schema, implemented)

See [Local Storage and Data Model](#local-storage-and-data-model).

### YouTube integration — `src/flochat/youtube.py` (boundaries only)

See [YouTube Integration Boundaries](#youtube-integration-boundaries).

### Shared errors — `src/flochat/errors.py` (implemented)

A single catchable hierarchy, each error carrying an `AppState` so the CLI can print a status
instead of a traceback: `ConfigurationError`, `PlatformError`, `StorageError`,
`OrientationError`, `AuthenticationRequiredError`, `SessionExpiredError`,
`PermissionRequiredError`, `ApprovalRequiredError`, `LiveChatUnavailableError`,
`NetworkInterruption`, `NotSupportedYetError`.

---

## Platform Adapter Responsibilities

Every adapter implements the same contract (`PlatformAdapter` in `adapters.py`) and reports an
`AdapterReport` whose `implemented` flag is **False** in Phase 01. That flag may only become
`True` in a later phase, after verification on real hardware.

| Adapter | Planned overlay technology | OS requirements the adapter must satisfy | Secure storage target | Phase 01 state |
| --- | --- | --- | --- | --- |
| Android | Kotlin native overlay | `SYSTEM_ALERT_WINDOW` ("Display over other apps"), `FOREGROUND_SERVICE` with a persistent notification, battery-optimisation exemption (explained and revocable), notification permission (Android 13+) | Android Keystore via companion APK | Boundary only |
| Windows | C# / WinUI always-on-top panel | SmartScreen reputation for distributed binaries, no administrator elevation | Windows Credential Manager (DPAPI) | Boundary only |
| Linux | Python / Qt panel where the compositor allows | Always-on-top depends on the compositor; Wayland restrictions differ from X11 | Secret Service / libsecret where available | Boundary only |
| macOS | Swift / AppKit floating panel or menu bar | Gatekeeper notarisation; Accessibility or Screen Recording only if a feature genuinely needs it | macOS Keychain | Boundary only |

Adapter responsibilities once implemented:

* Report capabilities truthfully (never a capability the OS did not grant).
* Request permissions with an explanation, and handle refusal without crashing.
* Keep sensitive values in platform secure storage, never in configuration files or logs.
* Surface interruptions to the core; never silently "fix" a failure by retrying a submission.

The core expresses platform differences only through capability reports, which is why the
`status` command can say "the Linux adapter is not implemented" while still working perfectly.

---

## Lifecycle: Persistent, Manual, and Background

FloChat is architected for both persistent availability and manual control. Phase 01 implements
manual mode and reports persistent mode honestly as requiring work that does not exist yet.

### A. Persistent Mode (planned — Phase 06)

Intended: FloChat stays available in the background where the OS permits, the bubble/panel is
reachable when allowed, and session recovery may be offered.

Phase 01 reality: `flochat start --mode persistent` returns `permission_required` (exit code 3)
and lists the overlay, background-service, and battery-optimisation requirements that Phase 06
must satisfy and verify on each device.

### B. Manual Mode (implemented)

* The user explicitly starts FloChat: `flochat start`.
* The user controls the active session and can stop it: `flochat stop`.
* Stopping ends the session cleanly and discards any pending approval. Nothing is submitted on
  stop.
* Session state is scoped to the terminal process; Phase 01 has no daemon, so there is no
  ambiguous "maybe still running" state.

### C. Background Operation (planned — Phase 06)

Intended: authorized YouTube API operations do not depend on YouTube being in the foreground,
and background lifecycle events (suspend, resume, network change) are handled explicitly.

Phase 01 reality: not implemented. No adapter, no service, no wake-up behaviour, and no
reboot recovery exists. Android force-stop, process termination, and battery optimisation are
documented constraints, not solved problems.

### Interruption and recovery rules

* Reconnection **never** triggers a submission. `SessionManager.recover()` only reports state.
* An interruption moves the session to `temporary_interruption` and keeps it paused until the
  user acts.
* Interruptions are recorded on the session (`interruptions`) so a later phase can present them.

### Honest limitation statement

FloChat does **not** promise guaranteed background operation on every device or OS. The
implementation must account for: OS background restrictions, Android battery optimisation,
permission requirements, process termination, force-stop, reboot, expired OAuth sessions,
network interruptions, disconnected chats, ended live streams, and API quota limits. FloChat
will never claim it can keep operating after the OS has terminated its process unless the
relevant platform implementation has been tested and verified.

**Persistent availability does not mean automatic or unattended submission. Every individual
comment submission requires explicit user approval.**

---

## YouTube Integration Boundaries

`src/flochat/youtube.py` defines four boundaries. **No network request is made in Phase 01.**

| Boundary | Responsibility | Phase 01 behaviour |
| --- | --- | --- |
| `OAuthBoundary` | Official Google OAuth (authorization code flow with PKCE). Reads credential **paths**, never credential values, and never prints them. | Reports `authentication_required`. A configured token path is reported as "present, validity unverified". |
| `YouTubeClientBoundary` | Official YouTube Data API v3 client, quota-aware. | Reports `pending`; `list_live_chats()` returns an empty list because there is no client and no session. |
| `LiveChatIdentificationBoundary` | Resolve the live chat for a stream; detect chat closure and ended streams. | Reports `live_chat_unavailable`. |
| `ApiErrorBoundary` | Map API/network failures to FloChat states. | Mappings prepared but unused: `quota_exceeded` and `rate_limited` → `temporary_interruption`, `unauthorized` → `authentication_required`, `forbidden` → `permission_required`, `live_chat_ended` → `disconnected`, `chat_not_found` → `live_chat_unavailable`. |

Approved integration direction, binding for later phases:

* Official Google OAuth only. FloChat never sees or stores a Google account password.
* Official YouTube Data API only. No scraping, no undocumented endpoints, no browser
  automation, no CAPTCHA handling, no cookie manipulation.
* Quota is a first-class constraint: exhaustion is reported as a temporary interruption with a
  clear explanation, never worked around.
* Expired or revoked authorization yields `session_expired` or `authentication_required`, and
  the user is asked to sign in again.
* A live chat that ends produces `disconnected` / `live_chat_unavailable`, not a silent no-op.

---

## Local Storage and Data Model

SQLite via the standard library `sqlite3`. No ORM, no migrations framework, no extra
dependency in Phase 01.

**Location** — the platform data directory:

| Platform | Default location |
| --- | --- |
| Windows | `%APPDATA%\FloChat\` |
| macOS | `~/Library/Application Support/FloChat/` |
| Linux | `$XDG_CONFIG_HOME/flochat/` or `~/.config/flochat/` |
| Android (Termux) | `$XDG_CONFIG_HOME/flochat/` or `~/.config/flochat/` |

Overridable with `FLOCHAT_HOME` (data directory) or `FLOCHAT_DB` (database file). Both must be
absolute paths.

**Versioning** — `PRAGMA user_version` holds the schema version (currently `1`). Opening a file
with a newer version than this build supports fails with an explicit error rather than
corrupting data.

**Schema (version 1)** — comment history is the only table, and Phase 01 writes no rows into it.
Phase 04/05 will populate it.

| Column | Type | Notes |
| --- | --- | --- |
| `id` | INTEGER PK | Local row identity |
| `live_chat_id` | TEXT NOT NULL | Target chat |
| `live_chat_title` | TEXT | Display context only |
| `draft_text` | TEXT NOT NULL | Text as the user typed it |
| `comment_text` | TEXT NOT NULL | Exact approved text (basis for duplicate detection) |
| `state` | TEXT NOT NULL | `prepared`, `approved`, `submitted`, `confirmed`, `failed` |
| `created_at` | TEXT NOT NULL | ISO 8601 UTC |
| `approved_at` | TEXT | Set only on explicit approval |
| `submitted_at` | TEXT | Set only when a submission was attempted |
| `youtube_comment_id` | TEXT | Set only when the API confirmed the comment |

Index: `(live_chat_id, submitted_at)` — the query shape Phase 05 needs for duplicate detection
and cooldown enforcement.

**Data rules:** no credentials, no OAuth tokens, and no Google account identifiers are stored in
this database. Comment history is user-owned and local; Phase 03 will provide browsing and
deletion.

---

## Security Standards

### Authentication

* Official Google OAuth only; FloChat never collects or stores Google account passwords.
* No hardcoded credentials anywhere in the source tree.
* API secrets and private tokens are never committed.
* OAuth material is referenced **by path** (`FLOCHAT_CLIENT_SECRET`, `FLOCHAT_TOKEN_FILE`),
  and those paths must point outside the repository.

### Credential storage

* Prefer operating-system secure storage: Android Keystore, Windows Credential Manager, macOS
  Keychain, Secret Service/libsecret.
* Avoid plaintext credential storage. Where a token file is unavoidable today, it is a
  user-supplied path excluded by `.gitignore`, and Phase 04 must document the storage decision
  explicitly.
* Configuration files carry paths and settings only. `config.py` actively refuses a
  configuration file containing credential field names (`client_secret`, `password`,
  `access_token`, `refresh_token`, `api_key`, …).

### API security

* Official YouTube APIs only; no bypassing of platform restrictions.
* Handle OAuth expiry and revoked permissions as explicit states.
* Respect API quota limits and report exhaustion honestly.

### Repository security

* `.gitignore` excludes `.env*`, OAuth client secrets, token files, keys, certificates, local
  databases, logs, and build output — while keeping `.env.example` tracked.
* `.env.example` contains documented variable names and comments only, never real values.
* `scripts/check_repository.py` scans the working tree for Google access tokens, refresh
  tokens, OAuth client secrets, API keys, and private-key blocks, and fails if any appears.
* No credentials, API keys, or tokens were added during Phase 01 — verified by that scan.

### Runtime hygiene

* Logs go to stderr and must never contain credential values.
* Errors are presented as states, not as tracebacks with embedded data.
* FloChat requires no administrator/root privileges on any target platform.

---

## Privacy Standards

* **Store only what is necessary:** the comment history rows described above, plus the
  configuration you write yourself.
* **Explain what is stored:** this section plus the schema table are that explanation.
* **Keep history under user control:** local-only storage, no sync, with browsing and deletion
  arriving in Phase 03.
* **No unnecessary telemetry:** FloChat sends no analytics, crash reports, or usage data. The
  only outbound traffic that will ever exist is what the official YouTube API requires for an
  operation you started.
* **No third-party sharing:** comment text is sent to YouTube only when you approve a
  submission.
* Nothing in Phase 01 transmits anything over the network; the integration boundaries make no
  requests.

---

## Comment Submission Safety

These principles are binding for the whole project and are reflected in code, not just prose.

**Prohibited behaviour**

1. No unattended, repeated commenting.
2. No hidden comment submissions.
3. No automatic repeated identical comments.
4. No spam-generation behaviour.
5. No CAPTCHA bypass.
6. No unofficial or unauthorized API usage.
7. No hidden browser automation to circumvent platform restrictions.
8. No automatic submission after reconnecting.
9. No submission without the user's explicit approval.

**Required architecture**

* Duplicate-comment detection (schema indexed for it; enforcement in Phase 05).
* Submission cooldowns (`cooldown_seconds`, default 30, bounded 5–600; enforcement in Phase 05).
* Comment validation (implemented locally in `comments.validate_comment`).
* Preview before submission (the approved text is stored verbatim and re-usable for preview).
* Explicit confirmation for every submission (`ensure_approved` raises unless approval is `True`).
* Clear submission status (`StatusReport` with a `confirmed` flag; success requires confirmation).
* Error reporting through the shared state vocabulary.
* Pause, stop, and disconnect controls (stop implemented; pause/disconnect arrive with sessions
  in later phases).

**Default behaviour:** one intentional submission per giveaway entry. FloChat is a convenience
layer for a deliberate action, not an engagement machine. Users must follow the giveaway host's
rules and YouTube's policies, and are responsible for what they submit.

---

## UI Design System

FloChat's visual identity is clean, professional, and Apple-inspired: premium, refined, and
practical. **Phase 01 documents the system; it does not build a full visual interface.** The
only interface shipped in Phase 01 is the terminal, which follows the same restrained
principles (calm labels, plain-language states, no decorative output).

### Colour

| Token | Value | Use |
| --- | --- | --- |
| `surface.primary` | `#FFFFFF` | Panel background |
| `surface.secondary` | `#F5F5F7` | Grouped sections, input wells |
| `surface.tertiary` | `#EDEDF0` | Pressed/selected rows |
| `text.primary` | `#1D1D1F` | Primary text (charcoal, near-black) |
| `text.secondary` | `#6E6E73` | Labels, metadata |
| `text.tertiary` | `#8E8E93` | Disabled, hints |
| `accent.primary` | `#0071E3` | Single primary action, selection |
| `accent.subtle` | `#E8F1FD` | Accent wash for selected state |
| `border.hairline` | `#D2D2D7` | 1 px borders and dividers |
| `state.success` | `#1D8A46` | Confirmed submission only |
| `state.warning` | `#B25E00` | Interrupted, pending attention |
| `state.danger` | `#C4362B` | Failure, blocked submission |

Light-first theme. Dark mode is optional and deferred; if added, tokens are redefined, never
hardcoded at call sites.

### Typography

* One system sans stack per platform (SF Pro on Apple, Segoe UI Variable on Windows, Roboto on
  Android, Inter/system on Linux).
* Scale: `13/16` metadata, `15/20` body and inputs, `17/22` panel title, `20/26` section header.
* Weights: regular (400) and semibold (600) only. No all-caps labels, no italics for emphasis.

### Spacing and layout

* 4 px base grid: `4, 8, 12, 16, 20, 24`.
* Panel padding 16 px; 12 px between controls; 20 px between groups.
* Floating panel: 320 px wide, content-driven height, 8 px from screen edges, safe-area aware.
* Compact and professional — never full-screen, never modal-by-default for the main workflow.

### Shape, borders, and elevation

* Corner radii: `10` px for the panel, `8` px for controls, `6` px for inputs.
* Borders: 1 px hairline. Shadow (light mode): `0 8px 24px rgba(0,0,0,0.08)` plus
  `0 1px 2px rgba(0,0,0,0.06)`. No coloured glows.
* No glassmorphism, no gradients as decoration, no decorative illustration.

### Motion

* 180 ms ease-out for panel and expansion transitions; 120 ms for press feedback.
* Motion conveys state change only (panel open/close, pending → confirmed).
* Respect the OS "reduce motion" setting; disable non-essential transitions when it is on.

### Icons and controls

* One icon family at a single weight, 16/20 px optical sizes; icons support text, never replace it
  for destructive actions.
* Minimum touch target 44×44 pt on mobile, 32×32 px on desktop.
* Primary actions use the accent colour once per view; destructive actions are never the default.

### Required states for every component

Default, hover, pressed, focused (visible focus ring), disabled, loading, success, error.

### Accessibility

Contrast ≥ 4.5:1 for text; focusability for every control; accessible labels matching visible
text; no colour-only status signalling.

### Explicitly avoided

Childish or neon colours, excessive gradients, unnecessary glass effects, cluttered layouts,
random decorative elements, oversized controls, and unnecessary animations.

---

## Error Handling and Application States

The vocabulary lives in `AppState` (`src/flochat/state.py`) and is the only way FloChat reports
condition.

| State | Meaning | Terminal exit code |
| --- | --- | --- |
| `success` | Completed **and confirmed** | 0 |
| `failure` | Operation failed; detail explains why | 1 |
| `pending` | Awaiting explicit user approval | 1 |
| `authentication_required` | Sign-in needed | 1 |
| `permission_required` | OS or API permission needed | 3 |
| `unsupported_platform` | Platform/terminal cannot do this | 3 |
| `temporary_interruption` | Paused; will not act until you resume | 1 |
| `disconnected` | Session disconnected | 1 |
| `session_expired` | Session expired; sign in again | 1 |
| `live_chat_unavailable` | Live chat unavailable or ended | 1 |

Rules:

1. **No silent failures.** Every failure path produces a `StatusReport` with a state and a
   human-readable detail.
2. **No unconfirmed success.** `StatusReport.ok` requires `confirmed=True`; operations that
   cannot be confirmed report `confirmed: False`.
3. **No unhandled crashes for expected conditions.** Configuration, storage, platform, and
   approval problems are typed errors caught at the CLI boundary and rendered as states.
4. **Indistinguishable problems stay distinguishable.** "Authentication required" and
   "permission required" are separate states because the remedy is different.
5. **Planned conditions are designed before they occur.** API error mappings exist now, so
   Phase 04 has a target instead of inventing one mid-implementation.

Reliability expectations for later phases: graceful shutdown, recoverable network failures,
expired sessions, invalid configuration, refused overlay permissions, and platform-specific
restrictions must each map to a state above — and an operation is never reported as successful
unless its result was confirmed.

---

## Development Standards

**Naming.** Modules are lowercase nouns matching one responsibility (`lifecycle`, `database`).
Classes are `PascalCase`; protocols/ABCs end in `Adapter` or `Boundary`; functions are
`snake_case` verbs; constants are `UPPER_SNAKE`. No abbreviations that save fewer characters
than they cost in clarity.

**Structure.** One responsibility per module. Boundaries in `src/flochat` never import native
code. The controller is the only composition point. Imports are grouped standard-library,
third-party, first-party.

**Types.** `from __future__ import annotations` everywhere; full annotations on public
functions; `StatusReport` and typed dataclasses instead of loose dicts inside the core (dicts
appear only at the CLI/JSON edge).

**Validation.** Configuration is validated at load time with explicit messages. User text is
normalised and validated before storage. Paths must be absolute. Unknown configuration keys are
errors.

**Errors.** Raise a subclass of `FloChatError` with a message and an actionable hint. Never leak
credential values into messages or logs. Never `except Exception: pass`.

**Formatting and linting.** Ruff with `line-length = 100`, `target-version = "py310"`, and rules
`E, F, W, I, UP, B, SIM, RUF`; `ruff format` for layout. Docstrings explain *why* a boundary
exists and what it refuses to do.

**Dependencies.** Standard library first. Add a package only when the current phase needs it,
and record the reason in this file.

**Security.** No credential values in code, logs, or configuration samples. Security-relevant
behaviour is stated in the docstring of the code that enforces it.

**Scope discipline.** No premature abstraction, no feature outside the current phase, no
placeholder module "for later". If something is planned, it is documented here — not stubbed in
code that pretends to work.

Commands:

```bash
ruff check .            # lint
ruff format --check .   # formatting
python scripts/check_repository.py   # structure, placeholders, secrets, README coverage
```

---

## Installation and Launch Direction

Phase 01 is launchable **from source**. Platform installers and packaged binaries belong to
Phase 02 (CLI & Installation) and Phase 08 (Final Release); none exist yet.

### Common requirements

* Python 3.10 or newer, with `venv` available.
* A terminal on a supported platform.
* No administrator/root privileges required.

### Linux / macOS / Termux (bash, zsh)

```bash
git clone <repository-url> FloChat
cd FloChat
python3 -m venv .venv
. .venv/bin/activate          # Termux, Linux, macOS
pip install --upgrade pip
pip install -e .
flochat --version
```

Termux: install Python first (`pkg install python`), then follow the same steps.

### Windows (PowerShell)

```powershell
git clone <repository-url> FloChat
cd FloChat
python -m venv .venv
.\.venv\Scripts\Activate.ps1    # use Activate.bat in cmd.exe
pip install --upgrade pip
pip install -e .
flochat --version
```

If script execution is blocked by policy, use `.\.venv\Scripts\python.exe -m flochat.cli` or
adjust the policy for the current user only.

### Optional configuration

```bash
cp .env.example .env      # Windows: Copy-Item .env.example .env
```

`.env` is git-ignored and must never contain credentials — only variables such as
`FLOCHAT_MODE`, `FLOCHAT_LOG_LEVEL`, `FLOCHAT_HOME`, `FLOCHAT_DB`, `FLOCHAT_CLIENT_SECRET`
(path only), and `FLOCHAT_TOKEN_FILE` (path only). Environment variables take precedence over
`config.json` in the platform data directory.

### First run

```bash
flochat status          # version, platform, adapter state, config, session, auth, database
flochat platform        # detected platform plus all four adapter capability reports
flochat config show     # effective vs persisted configuration
flochat start           # manual session (Phase 01 scope)
flochat stop            # clean stop; nothing is submitted
flochat --json status   # machine-readable envelope
```

`flochat start --mode persistent` intentionally returns `permission_required` and exit code 3:
background availability is Phase 06 work.

---

## Verification Results

Everything below was executed in the Phase 01 environment: a **Linux x86_64 sandbox**
(Debian-based, Python 3.11.2, SQLite 3.40.1, Ruff 0.17.3, Pydantic 2.14.2, non-interactive
shell).

| # | Check | Method | Result |
| --- | --- | --- | --- |
| 1 | Lint | `ruff check .` | **Pass** — "All checks passed!" |
| 2 | Formatting | `ruff format --check .` | **Pass** — no reformatting needed |
| 3 | Python syntax | `python scripts/check_repository.py` (parses every module with `ast`) | **Pass** |
| 4 | Import / packaging | `pip install -e .` then `flochat --version` | **Pass** — prints `FloChat 0.1.0` |
| 5 | CLI surface | `flochat --help`, `--version` | **Pass** — all commands and exit codes documented in help |
| 6 | Status report | `flochat status` | **Pass** — correct platform (`linux`), capabilities `overlay: False`, `secure_storage: False`, auth `authentication_required`, adapter `implemented: False` |
| 7 | Platform report | `flochat platform` | **Pass** — four adapters reported, all `implemented: False`, matching adapter `not_implemented`, others `unavailable` |
| 8 | Database schema | `flochat status` (real open → `PRAGMA quick_check` → close) | **Pass** — `schema_version: 1`, table `comment_history`, `integrity: ok`, `healthy: True`, `0` rows |
| 9 | Manual session | `flochat start` then `flochat stop` | **Pass** — `success`, `confirmed: yes`; stop reports cleanly |
| 10 | Persistent mode honesty | `flochat start --mode persistent` | **Pass** — `permission_required`, exit code 3, lists overlay/service requirements instead of claiming success |
| 11 | Config validation | `flochat config validate` | **Pass** — valid configuration accepted |
| 12 | Invalid config handling | `FLOCHAT_MODE=chaos flochat status` | **Pass** — `failure` state, message names the field and allowed values, exit code 2, no traceback |
| 13 | Repository orientation | `python scripts/check_repository.py` | **Pass** — allow-listed top level, no extra Markdown, no placeholders, no empty folders |
| 14 | Secret exposure | Same guard; patterns for Google access/refresh tokens, `GOCSPX-` client secrets, `AIza` API keys, private-key blocks across all text files | **Pass** — zero matches |
| 15 | Git cleanliness | `git status --ignored` review | **Pass** — only intended files tracked; `.venv`, caches, local databases ignored |

### What was **not** verified (stated honestly)

* **Windows, macOS, and Android/Termux were not executed.** The architecture and detection logic
  cover them, and the core is platform-neutral, but no runtime compatibility claim is made for
  platforms that were not tested here.
* **No real YouTube API call, OAuth flow, live chat lookup, or comment submission was performed**
  — none is implemented in Phase 01.
* **No overlay, background service, permission prompt, or reboot behaviour was tested** — no such
  code exists yet.
* **No automated test suite was run**, because none exists (see the testing-rule note below).

---

## Phase 01 Completion Report

### 1. Phase 01 status

**Complete.** All Phase 01 objectives are met: repository inspected, minimal architecture
established, shared-core and adapter boundaries defined, configuration and development standards
set, lifecycle designed and partially implemented (manual mode), YouTube boundaries defined,
security/privacy standards established, design system documented, README consolidated, and the
work verified in the available environment. No Phase 02 work was started.

### 2. Repository structure

`src/flochat/` (shared core, 11 modules) + `scripts/check_repository.py` + four root
configuration/documentation files. Full tree in [Architecture](#architecture); file-by-file
purposes in [Repository File Inventory](#repository-file-inventory).

### 3. Files created

| File | Purpose |
| --- | --- |
| `pyproject.toml` | Package metadata, one runtime dependency (Pydantic), `flochat` console script, Ruff configuration |
| `.gitignore` | Prevents committing credentials, tokens, keys, local databases, logs, and build output |
| `.env.example` | Secrets-free environment template with documented variable names |
| `README.md` | Replaced the placeholder; single central documentation and Phase 01 completion record |
| `src/flochat/__init__.py` | Package identity, version, and Phase 01 scope note |
| `src/flochat/state.py` | Ten application states, `StatusReport` with enforced confirmation |
| `src/flochat/errors.py` | Error hierarchy mapped to application states |
| `src/flochat/platform.py` | Platform detection, capability reporting, data-directory resolution |
| `src/flochat/adapters.py` | Adapter contract plus Android/Windows/Linux/macOS descriptors, all `implemented: False` |
| `src/flochat/config.py` | Strict configuration loading/validation, logging setup, secret-field refusal |
| `src/flochat/database.py` | SQLite boundary, schema version 1, integrity and health checks |
| `src/flochat/comments.py` | Comment manager boundary, normalisation, validation, approval guard, refusing `submit()` |
| `src/flochat/lifecycle.py` | Manual session lifecycle, persistent-mode honesty, interruption/recovery reporting |
| `src/flochat/youtube.py` | OAuth, API client, live chat identification, and API error boundaries (no requests) |
| `src/flochat/controller.py` | Application controller combining all boundaries into reports and lifecycle actions |
| `src/flochat/cli.py` | `argparse` CLI, six commands, documented exit codes, JSON envelope |
| `scripts/check_repository.py` | Repository orientation and credential guard (structure, placeholders, secrets, README coverage) |

### 4. Files modified

| File | Change |
| --- | --- |
| `README.md` | The only pre-existing file (9 bytes, content `# FloChat`). Replaced with the full Phase 01 documentation and completion record. No other pre-existing content existed to preserve. |

No other existing files were deleted, renamed, or overwritten. The initial commit contained no
source code, configuration, tests, or additional documentation.

### 5. Purpose of each change

The single purpose behind every change: give FloChat a foundation where (a) the comment
workflow can be built in later phases without rework, (b) no part of the system can claim
success it has not confirmed, and (c) the repository stays minimal. Concretely: boundaries exist
so future work has one place to land; states exist so failures are legible; the guard script
exists so clutter and credentials cannot slip in unnoticed.

### 6. Technology and architecture decisions

* **Python shared core + native adapters** — one workflow, platform-specific OS features.
* **`argparse` now, Typer in Phase 02** — no dependency before the command surface exists;
  command names, exit codes, and JSON envelope are stable across the change.
* **Pydantic for configuration** — precise validation errors are a reliability and security
  requirement, and this is the only runtime dependency.
* **SQLite via `sqlite3`, `PRAGMA user_version`** — no ORM or migration framework until there is
  a real schema change to migrate.
* **Single-vocabulary states with an enforced confirmation flag** — the "no unverified success"
  rule is enforced by the type, not by convention.
* **Adapter capability reports rather than stubs** — the system can honestly say what is missing
  on this machine, which is what later phases need to build and verify against.

### 7. Security and privacy standards

Documented in [Security Standards](#security-standards) and
[Privacy Standards](#privacy-standards): official OAuth only, no passwords collected, no
hardcoded or committed credentials, path-only secret references, OS secure storage as the target,
no plaintext credential storage, `.gitignore` plus an automated credential scan, no telemetry,
local-only comment history, and no network traffic whatsoever in Phase 01.

### 8. UI design system

Documented in [UI Design System](#ui-design-system): light-first surfaces, charcoal text, one
restrained blue accent, a defined type scale, a 4 px spacing grid, controlled radii, hairline
borders, soft shadows, purposeful motion that respects reduce-motion, accessibility minimums, and
an explicit list of avoided visual clichés. No visual interface was built in Phase 01.

### 9. Verification performed and actual results

Fifteen checks executed, all passing, in a Linux x86_64 sandbox — see
[Verification Results](#verification-results) for the table and for the explicit list of things
that were **not** verified. Summary: lint and formatting clean; every module parses; the package
installs and runs; all six commands exercise successfully; the database schema is created and
verified healthy; invalid configuration and persistent mode both fail honestly with the right
exit codes; the repository guard reports no clutter and no credentials.

### 10. Pending work

* Phase 02 — CLI & Installation: Typer CLI, platform installers/launch scripts, first-run
  guidance. (Not started.)
* Phase 03 — Comment Manager: drafting, preview, history browsing and deletion.
* Phase 04 — YouTube Integration: official OAuth (PKCE), live chat discovery, submission with
  confirmed results, quota and error handling.
* Phase 05 — Safety Engine: approval flow, duplicate detection, cooldowns, per-comment
  confirmation enforcement beyond the current guard.
* Phase 06 — Floating & Background Engine: the four native adapters, overlays, persistent mode,
  interruption and recovery handling.
* Phase 07 — Cross-Platform Testing: real verification on Android/Termux, Windows, Linux, macOS.
* Phase 08 — Final Release: packaging, licence, release preparation. Release requires explicit
  owner approval.

Also pending and outside any phase as written: choosing a licence before release.

### 11. Known limitations

See [Known Limitations](#known-limitations) — the summary is that Phase 01 ships no YouTube
functionality, no overlay, no background service, and no installer; three target platforms are
architecturally supported but unverified; and Android's background restrictions remain an
explicitly unsolved problem, not a promised feature.

### 12. No-unnecessary-artefacts confirmation

Confirmed: no `docs/`, `documentation/`, `reports/`, `examples/`, or `tests/` folder was created;
no extra Markdown file exists (root `README.md` is the only one); no placeholder or empty
module, folder, or file exists; no duplicate configuration file exists; no sample/dummy data was
added; and no future-phase code was written. `scripts/check_repository.py` enforces these rules
and currently reports a clean repository.

**Testing rule note.** No test directory or test file was created, and no pytest suite was
installed or run, because Phase 01 has no logic whose correctness is not better verified directly
through the CLI (and the guidance was to create tests only when genuinely required). The checks
in [Verification Results](#verification-results) were actually executed — none are claimed
without having run. Phase 03, which introduces real comment logic, is where a focused test suite
becomes worthwhile.

---

## Repository File Inventory

Complete and current. Every file below is tracked, non-empty, and used by Phase 01.

| Path | Type | Phase 01 role |
| --- | --- | --- |
| `README.md` | Documentation | Single central documentation and completion record |
| `pyproject.toml` | Configuration | Packaging, dependency, console script, Ruff rules |
| `.gitignore` | Configuration | Credential, database, log, and build exclusions |
| `.env.example` | Configuration template | Documented environment variables, no values |
| `src/flochat/__init__.py` | Source | Package identity and version |
| `src/flochat/state.py` | Source | Application states and `StatusReport` |
| `src/flochat/errors.py` | Source | Error hierarchy |
| `src/flochat/platform.py` | Source | Platform/capability detection |
| `src/flochat/adapters.py` | Source | Adapter contract and four descriptors |
| `src/flochat/config.py` | Source | Configuration and logging |
| `src/flochat/database.py` | Source | SQLite boundary and schema |
| `src/flochat/comments.py` | Source | Comment boundary, validation, approval guard |
| `src/flochat/lifecycle.py` | Source | Session lifecycle and modes |
| `src/flochat/youtube.py` | Source | YouTube integration boundaries |
| `src/flochat/controller.py` | Source | Application controller |
| `src/flochat/cli.py` | Source | Terminal entry point |
| `scripts/check_repository.py` | Tooling | Repository and credential guard |

Not tracked by design: `.venv/` (local virtual environment), `__pycache__/`, `.ruff_cache/`,
`*.egg-info/`, local `*.sqlite3` databases, and any `.env`.

---

## Known Limitations

1. **No YouTube functionality exists.** No OAuth flow, no API client, no live chat discovery, no
   submission. Every such operation reports "not implemented" and names its phase.
2. **No overlay and no background service.** Persistent mode cannot be satisfied; `start` in
   persistent mode reports `permission_required` and exit code 3.
3. **No installers or packages.** Installation is from source via `pip install -e .` only.
4. **Only Linux was executed.** Windows, macOS, and Android/Termux are architecturally supported
   but unverified in this environment.
5. **Android background constraints are unsolved.** Battery optimisation, force-stop, and OEM
   process killers can end FloChat; nothing here claims otherwise.
6. **Sessions are process-scoped.** There is no daemon, so state does not survive the terminal
   process and no panel/bubble can exist yet.
7. **Credential storage is designed, not implemented.** No secure-storage integration ships in
   Phase 01; configuration references credential paths only.
8. **No automated test suite.** Verification was performed by executing the CLI and the guard
   script directly.
9. **No licence chosen.** Required before any release.
10. **Quota behaviour is mapped, not observed.** API error mappings are prepared from documented
    behaviour and have not been exercised against the live API.

---

## Pending Work and Approved Roadmap

FloChat has exactly **eight** approved phases. This roadmap is fixed: phases are not added,
removed, renamed, or expanded, and no phase begins before the previous one is approved.

| Phase | Name | Scope | Status |
| --- | --- | --- | --- |
| 01 | Foundation | Architecture, boundaries, standards, documentation, verification | **Complete** |
| 02 | CLI & Installation | Typer CLI, platform installers and launch scripts | Not started |
| 03 | Comment Manager | Drafting, preview, history browsing/deletion | Not started |
| 04 | YouTube Integration | Official OAuth (PKCE), live chat discovery, submission with confirmed results | Not started |
| 05 | Safety Engine | Approval flow, duplicate detection, cooldowns, per-comment confirmation | Not started |
| 06 | Floating & Background Engine | Native adapters, overlays, persistent mode, interruption/recovery | Not started |
| 07 | Cross-Platform Testing | Verified behaviour on Android/Termux, Windows, Linux, macOS | Not started |
| 08 | Final Release | Packaging, licence, release preparation | Not started |

**Repository and release restrictions in force:** the repository is not published, no release or
installer is created or published, repository visibility is unchanged, and no external
publishing has occurred. Publishing and release require explicit owner approval.

---

FloChat — Your Live Chat, Always Within Reach.
