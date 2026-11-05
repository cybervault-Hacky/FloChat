# FloChat

**Your Live Chat, Always Within Reach.**

FloChat is a cross-platform, GitHub-distributed, terminal-launched utility that helps you
prepare, review, and submit **authorized comments** to YouTube Live Chat from a compact
floating control panel — instead of repeatedly switching apps to hunt for a comment box.

> **Current phase: Phase 08 — Final Release (final approved phase).**
> **PHASE 08 — NOT RELEASE READY**
> The final [Phase 08 certification report](#phase-08-final-release-audit--certification-report)
> records **931 unique passing assertions, zero final assertion failures**, unchanged native
> verification gaps, and the unresolved **owner-selected project licence** release blocker.
> No distribution or public release is authorized or certified. Version remains **0.1.0**.
> The product description below is intended scope, not evidence of working native panels.
> Historical reports retain their original phase-specific claims/counts; the final report and
> current usage/platform sections govern this build. There is no phase after Phase 08.

> **PHASE 06 — IMPLEMENTED, NATIVE VERIFICATION PENDING**
> The shared background owner, authenticated local IPC and unchanged central submission gate
> execute on Linux. Desktop Qt and Android Kotlin UI sources are present; **no real floating
> window or Android build has been verified here**. QtWidgets is blocked by missing native GL/EGL,
> xkbcommon and D-Bus libraries; no display exists. Android lacks SDK/JDK/Gradle tools. Windows/macOS runtimes are not available.
> No real Google authentication or comments were used in tests. Nothing posts automatically.
> Read the authoritative [Phase 06 implementation and limitations](#phase-06-floating--background-engine).
> Earlier phase reports are historical snapshots; they do not certify new native behavior.

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
17. [Installation and Launch](#installation-and-launch)
18. [CLI Reference](#cli-reference)
19. [Troubleshooting](#troubleshooting)
20. [Phase 01 Verification Results](#phase-01-verification-results)
21. [Phase 01 Completion Report](#phase-01-completion-report)
22. [Repository File Inventory](#repository-file-inventory)
23. [Known Limitations](#known-limitations)
24. [Pending Work and Approved Roadmap](#pending-work-and-approved-roadmap)
25. [Phase 02 Verification Results](#phase-02-verification-results)
26. [Phase 02 Completion Report](#phase-02-completion-report)
27. [Local Comment Manager](#local-comment-manager)
28. [Phase 03 Verification Results](#phase-03-verification-results)
29. [Phase 03 Completion Report](#phase-03-completion-report)
30. [Google OAuth and YouTube Setup](#google-oauth-and-youtube-setup)
31. [Phase 04 Verification Results](#phase-04-verification-results)
32. [Phase 04 Completion Report](#phase-04-completion-report)
33. [Phase 05 Safety Engine](#phase-05-safety-engine)
34. [Phase 05 Completion Report](#phase-05-completion-report)
35. [Phase 06 Floating & Background Engine](#phase-06-floating--background-engine)
36. [Phase 06 Completion Report](#phase-06-completion-report)
37. [Phase 06 Completion & Hardening — 2026-11-05](#phase-06-completion--hardening--2026-11-05)
38. [Phase 07 Testing & Completion Report](#phase-07-cross-platform-testing--completion-report)
39. [Phase 08 Final Release Audit & Certification Report](#phase-08-final-release-audit--certification-report)

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
| Version | 0.1.0; Phase 08 audited, NOT RELEASE READY |
| Licence | **Unselected — blocks release.** Owner must select and authorize appropriate terms |

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

| Platform | Terminal environment | Shell | Runtime verification status |
| --- | --- | --- | --- |
| Android | Termux; Kotlin companion for overlays | `bash` (Termux) | BLOCKED |
| Windows | PowerShell, Windows Terminal | PowerShell / `cmd` | BLOCKED |
| Linux core/CLI | Linux x86_64 sandbox; native desktop separately blocked | `bash` | PASS — REAL RUNTIME |
| macOS | Terminal, iTerm2, and compatible shells | `zsh` / `bash` | BLOCKED |

Platform detection reports what is true on the machine it runs on. It does not assume an
adapter exists, and it deliberately reports `unknown` for anything it cannot establish (for
example filesystem case sensitivity on Linux). Detection of Android relies on Termux markers
(`PREFIX`, `TERMUX_VERSION`) or `/system/build.prop`; a non-Termux Android terminal is flagged
as unverified rather than silently trusted.

---

## Architecture

FloChat uses a **shared core with explicit platform-adapter boundaries**. Submission business
logic is independent of native widgets. Runtime diagnostics optionally import Qt to test
loadability; the optional panel imports widgets only when explicitly opened. Native clients
contain no Google submission logic. The current owner path is CLI/controller → authenticated
IPC → CoreRuntime → one SessionManager/SafetyEngine/YouTube/CommentManager/SQLite context.
The diagram below shows the original boundary decomposition; the Phase 06 section describes
the live owner and both thin client implementations.

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
├── install.sh                   # installer: Android/Termux, Linux, macOS
├── start.sh                     # launcher for the same three platforms
├── install.ps1                  # installer: Windows PowerShell
├── start.ps1                    # launcher: Windows PowerShell
├── .env.example                 # environment template, secrets-free
├── .gitignore                   # credential, database, and build exclusions
├── README.md                    # the single central documentation file
├── pyproject.toml               # package, dependency, and Ruff configuration
├── src/
│   └── flochat/
│       ├── __init__.py          # package identity and version
│       ├── adapters.py          # platform adapter contract + four adapter descriptors
│       ├── cli.py               # terminal entry point, exit codes, JSON output
│       ├── comments.py          # local Comment Manager + submission gate
│       ├── config.py            # configuration loading, validation, logging setup
│       ├── controller.py        # application controller
│       ├── database.py          # SQLite boundary and schema
│       ├── dependencies.py      # runtime dependency declaration and diagnosis
│       ├── doctor.py            # environment diagnosis behind `flochat doctor`
│       ├── errors.py            # error hierarchy
│       ├── ipc.py               # bounded authenticated local transport
│       ├── runtime.py           # one explicit shared background owner
│       ├── panel.py             # one optional Qt desktop client
│       ├── safety.py            # exact one-use approval and final API gate
│       ├── lifecycle.py         # manual/persistent session management
│       ├── platform.py          # platform and capability detection
│       ├── roadmap.py           # approved phases and the implemented CLI surface
│       ├── settings.py          # effective settings and their provenance
│       ├── state.py             # application states and status reports
│       └── youtube.py           # official readonly REST, PKCE OAuth, keyring and safe errors
├── native/android/              # Gradle/manifest + Bridge, SetupActivity, OverlayService
└── scripts/
    ├── verify_platforms.py       # Foundation/install/Phase 07 + final Phase 08 regressions
    ├── verify_runtime.py         # real IPC/lifecycle; optional real Qt offscreen group
    ├── verify_safety.py          # central safety regressions; Google writes mocked
    ├── check_repository.py      # repository, dead-code, and credential guard
    ├── verify_comments.py       # isolated, executable local/regression checks
    ├── verify_youtube.py        # mocked integration + real local migration checks
    └── install_lib.sh           # shared installer helpers for the Unix scripts
```

There is intentionally **no** `docs/`, `documentation/`, `reports/`, `examples/`, or `tests/`
folder, and no placeholder modules. Every file above serves the current implementation or verification workflow.
Folders for future work will be created in the phase that needs them.

### Separation rules

1. **CLI/controller → shared owner.** Native clients use authenticated IPC, not a second controller or engine.
2. **CoreRuntime → boundaries.** One database-bound SessionManager/SafetyEngine and existing
   CommentManager/YouTube integration own the workflow. CLI local editing reuses those boundaries.
3. **Native clients → presentation only.** One Qt desktop client serves Windows, Cocoa and Linux;
   Kotlin supplies only Android overlay/permission/Keystore/IPC presentation. No second write route.
4. **Truthful capabilities.** Source presence, Python dependency installation, widget loadability,
   authenticated attachment and actual native verification are distinct observations.

---

## Technology Choices

| Component | Choice | Current implementation / evidence |
| --- | --- | --- |
| Shared core | Python ≥ 3.10 | **Implemented** |
| CLI framework | `argparse` (standard library) | **Implemented**; Typer deliberately not adopted in Phase 02 (see [Phase 02 report](#phase-02-completion-report)) |
| Data validation | Pydantic 2 | **Implemented** (configuration validation) |
| Installation | Bash (`install.sh`) and PowerShell (`install.ps1`) | **Implemented**; Linux executed, others syntax-checked |
| Local database | SQLite via `sqlite3` | **Implemented** (local data, selection and usage and safety metadata; schema v4) |
| Code quality | Ruff (lint + format), standard-library `ast` syntax check | **Implemented** |
| Repository guard | `scripts/check_repository.py` (standard library) | **Implemented** |
| Automated verification | Executable stdlib script | **Implemented** — see [Phase 03 results](#phase-03-verification-results); no pytest required |
| Android adapter / overlay | Kotlin overlay + foreground service | Source present; APK/device verification blocked |
| Windows adapter / overlay | Shared optional Qt desktop client | Native verification blocked; no WinUI/C# duplicate |
| Linux adapter / overlay | Shared optional Qt desktop client | Native/headless GUI blocked; real core/IPC exercised |
| macOS adapter / overlay | Same Qt client using Cocoa platform plugin | Native verification blocked; no Swift duplicate |
| Credential protection | Platform secure storage (Android Keystore, Windows Credential Manager, Secret Service, macOS Keychain) | Boundary only |

### Dependency policy

Historical Phase 01 installed exactly **one** runtime dependency: `pydantic>=2.6,<3`. It is used for
configuration validation with precise, user-facing errors, which the security and reliability
standards require. Phase 04 adds only the justified OAuth, HTTP and keyring packages listed
in the [Phase 04 dependency table](#phase-04-dependencies).

Current release-audit requirements in `pyproject.toml` supersede historical dependency tables:
requests >=2.33.0,<3; build-time setuptools >=84.1.0; installer pip >=26.2. The other direct
runtime constraints are unchanged. See the final dependency/advisory review below.

Original exclusions and their current disposition:

* **Typer** — listed in the Phase 01 table as the Phase 02 direction. Phase 02 kept `argparse`
  deliberately: the phase's work is installation, and adopting Typer would add a dependency and
  rewrite a verified CLI surface without serving that goal. Command names, exit codes, and the
  JSON envelope stay stable, so a later migration remains possible.
* **Google OAuth libraries** — now used in Phase 04. REST uses a small requests-based client
  against official endpoints rather than adding a discovery-based Google API package.
* **Pytest** — the executable stdlib verification script is sufficient for Phase 03; no extra
  testing dependency is needed.
* **GUI/native toolkit** — Phase 06 uses optional PySide6-Essentials for the one desktop client. Android uses the OS Kotlin UI, not another desktop framework.

Rule for later phases: add a dependency only when the current phase needs it, and document why
in this file.

---

## Core Component Responsibilities

### CLI — `src/flochat/cli.py` (implemented)

* Entry point for the `flochat` console script and `python -m flochat.cli`.
* Eighteen top-level commands, 42 leaf actions. Existing commands are preserved; `username`,
  `comment`, `drafts`, and `history` provide 16 additional local actions.
* The complete parser leaf-action list is checked by `doctor` against `roadmap.py`.
* `--json` emits a stable machine-readable envelope for scripts and future interfaces.
* Exit codes: `0` success, `1` failure/pending, `2` invalid usage or configuration,
  `3` unsupported platform or required permission, `4` incomplete environment.
  `state_exit_code()` is the single source
  of truth for that mapping, so the documented table cannot drift from real behaviour.
* Does not implement behaviour; delegates to the controller.

### Controller — `src/flochat/controller.py` (implemented)

* Builds configuration, platform information, and a session manager.
* Combines boundaries into the reports behind `status`, `platform`, `config`, `start`, `stop`.
* Performs a real database open/verify/close cycle during `status` so the reported health is
  observed, not assumed.
* Maps persistent mode to `permission_required` with the adapter's actual permission list.
* Asks all four YouTube boundaries for their state, so none of them is an unexercised stub.

### Configuration — `src/flochat/config.py` (implemented)

* Precedence: `FLOCHAT_*` environment variables → `<data dir>/config.json` → built-in defaults.
* Strict schema: unknown keys are rejected rather than silently ignored.
* Refuses configuration files containing credential field names.
* Paths must be absolute, so a relative path cannot silently resolve inside the repository.
* `configure_logging()` sets up a single stderr handler on the `flochat` logger.
* Environment variables provide explicit per-process overrides; `.env` is not auto-loaded.
  No sudo inheritance is assumed or required; installers refuse root.

### State and status — `src/flochat/state.py` (implemented)

* The single vocabulary of application states (see
  [Error Handling](#error-handling-and-application-states)).
* `StatusReport` carries state, detail, notes, and a `confirmed` flag. `ok` is true **only**
  when the state is success **and** the result was confirmed — the project rule against
  reporting unverified success is enforced in the type, not in prose.
* `flochat state` prints the whole vocabulary with its exit code, so the states are
  inspectable rather than only documented.

### Lifecycle — `src/flochat/lifecycle.py` (shared manual/persistent owner)

* CoreRuntime binds one SessionManager to the existing SafetyEngine; native clients do not instantiate one.
* Explicit persistent availability keeps only the local owner process available, where the OS permits.
* Manual owner detachment/lost lease stops availability. Standalone legacy snapshots cannot submit.
* Recovery stops the session and verifies account/chat only on explicit request; no approval restoration.

### Comment manager — `src/flochat/comments.py` (implemented locally)

* `CommentManager` owns username, editor, draft, preview, and history operations. Each uses
  the existing database transaction boundary. No manager operation calls `submit()`.
* `normalize_text()` normalizes CRLF/CR and trims outer whitespace only; interior spacing,
  indentation, blank lines and Unicode joiners are preserved. Preview never rewrites text.
* Local validation rejects empty text and unsafe control/surrogate characters, without an
  artificial length or blank-line limit. Counts are Unicode code points, not visual glyphs.
* `SubmissionRequest`, `ensure_approved()` and `submit()` remain the single submission
  boundary. Bare boolean approval still refuses. An active SafetyEngine must visibly
  confirm, bind and revalidate each individual request before an official API write.
* The guarded submission path retains the configured local length policy (default 200). That
  existing submission policy is **not** a constraint on local editing and is not a claim that
  locally valid text will be accepted by YouTube.

See [Local Comment Manager](#local-comment-manager) for the real terminal workflow. The full
approval UI, duplicate detection and safety engine are now implemented in Phase 05 below.

### Roadmap — `src/flochat/roadmap.py` (implemented)

* The eight approved phases, the current phase, and the CLI surface this build provides.
* `flochat version`, `flochat status`, and the `doctor` `cli_surface` check all read it, so the
  code cannot drift from what it claims to offer. Phase 01 had a hand-maintained list here that
  already disagreed with the parser.

### Settings — `src/flochat/settings.py` (implemented, read-only)

* Reports every effective setting with the layer that supplied it: environment, config file, or
  default.
* Provenance is computed from the file's actual keys rather than inferred from the final value,
  so a value equal to the default is still attributed correctly.
* Writes nothing. Phase 02 exposes settings for inspection only.

### Doctor — `src/flochat/doctor.py` (implemented)

* Nineteen checks covering platform, Python, runtime versions, all five dependencies, package origin,
  isolation, venv support, SQLite, storage, configuration, launch scripts, the submission safety
  gate, optional OAuth setup/backend, the CLI surface, and documentation.
* A check that cannot run reports `skip` with a reason; it is never reported as healthy.
* Runs even when configuration is invalid, because that is when it is needed.

### Dependencies — `src/flochat/dependencies.py` (implemented)

* Declares the runtime dependency for diagnosis and checks it before the heavier modules import,
  so a missing package yields an explanation and a fix command instead of a traceback.
* `pyproject.toml` remains the installation source of truth; this module is the diagnostic one.

### Database — `src/flochat/database.py` (boundary + schema, implemented)

See [Local Storage and Data Model](#local-storage-and-data-model).

### YouTube integration — `src/flochat/youtube.py` (implemented, live unverified)

See [YouTube Integration Boundaries](#youtube-integration-boundaries).

### Shared errors — `src/flochat/errors.py` (implemented)

A single catchable hierarchy, each error carrying an `AppState` so the CLI can print a status
instead of a traceback: `FloChatError` (base), `ConfigurationError`, `PlatformError`
(`unsupported_platform`), `StorageError`, `ApprovalRequiredError` (`pending`), and
`NotSupportedYetError`.

Every class here is raised by shipped code. Error classes for conditions that no Phase 01 code
can produce (expired session, revoked permission, and so on) are deliberately **not** declared
yet: their states exist in `AppState`, and Phase 04 adds the classes alongside the API code that
raises them. This follows the Phase 01 rule against placeholder code.

---

## Platform Adapter Responsibilities

Every adapter implements the same reporting contract. `implemented=True` now means the
implementation exists, **not** that its native behavior passed verification. `AVAILABLE`
means launch prerequisites were detected, not verified overlay stacking or vault success.
Capability verification flags remain false until genuine native evidence exists.

| Target | Actual implementation | Permission / security boundary |
| --- | --- | --- |
| Android | Kotlin overlay / special-use foreground service | Explicit overlay and notifications, Keystore pairing, no accessibility or battery-exemption bypass |
| Windows | Shared Qt window / native titlebar | Current-user DPAPI capability, local named pipe, no elevation or startup task |
| Linux | Same Qt window / native titlebar | Checked user-only Unix socket, compositor may ignore topmost hint |
| macOS | Same Qt window / Cocoa plugin | Unix socket, no Accessibility/Screen Recording/Automation workaround |

Adapters report refusals and restrictions; all consent/final checks and official writes stay
in the shared Python core. Google credential vaults remain subject to the earlier approved
OS-backend policy; Android pairing storage does not enable Termux OAuth.

---

## Lifecycle: Persistent, Manual, and Background

Phase 06 provides explicit persistent availability and manual control through one local
owner. Neither mode permits unattended commenting.

### A. Persistent Mode (implemented; native verification pending)

`panel start --core-only --mode persistent` starts only availability. A session still needs
an explicit Start; every comment needs its own core-issued review and exact typed phrase.
Detachment leaves the persistent owner stopped and available, not continuously submitting.
No installer registers a service, boot receiver, login item or startup task.

### B. Manual Mode (implemented)

The user explicitly starts/stops the session. A manual owner's panel/terminal detach or
15-second lost lease terminates availability. Stop invalidates pending consent immediately;
a potentially transmitted request is not falsely reported recalled. Status needs a fresh
authenticated response, not a PID/socket file.

### C. Background Operation (implemented core; native restrictions pending)

The shared owner uses bounded local IPC and one serialized work queue. It is a normal user
process, not an OS survival guarantee. Android uses a visible, non-sticky foreground service
for controls only; its process and Termux can still be suspended or killed.

### Interruption and recovery rules

* Reconnection, restart, Resume and explicit Recover never submit or restore approval.
* Monotonic and wall-time lease/expiry checks stop stale sessions before heartbeat renewal.
* Core-issued one-use review binds exact text, account, chat, stream, grant and session.
* Stop, pause, cancellation, attachment/mode/editor changes invalidate previously queued
  activation intent; only a fresh explicit Start/Resume may reactivate the stopped/paused state.
* Unknown/in-flight outcomes retain durable metadata and duplicate/cooldown protection;
  human chat inspection is required and no automatic retry exists.

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

`YouTubeIntegration` extends the former descriptive boundaries with explicit, read-only official
REST calls, installed-app PKCE OAuth, guarded OS keyring storage, request accounting, and
redacted error mapping. `CredentialStore` permits approved Secret Service/macOS/Windows
backends only; `YouTubeError` never exposes raw server bodies or OAuth exceptions.

`channels.list(mine=true)` retrieves available channel summaries; `liveBroadcasts.list(mine=true)`
lists one page of owned broadcasts; `videos.list(id=...)` inspects an explicitly supplied video
and its `activeLiveChatId`. Access is whatever the official authorized operation permits, not a
promise of access to private videos or all chats. No scraping, undocumented endpoints, cookies,
OOB login or browser automation. Ordinary `status`, `doctor`, and local editing make no network
requests. Use explicit `youtube ...` commands for integration.

Readonly authorization cannot post. Phase 05 adds `liveChatMessages.insert` only inside
SafetyEngine; no general YouTube write command or bare boolean submission is enabled.
See [Phase 05 setup and usage](#phase-05-safety-engine).

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

**Versioning** — `PRAGMA user_version` holds the schema version (currently **4**). Opening a file
with a newer version than this build supports fails with an explicit error rather than
corrupting data.

**Schema version 2** added `username_profile`, `editor`, `drafts`, and `local_history` to the
original `comment_history` table. An additive transaction migrates version 1 without altering
or deleting any existing rows. Unknown newer versions, unversioned non-empty files, corrupt
files, altered constraints, missing tables, and partial schemas fail clearly and roll back.
Recognized table/index structure is checked as well as `quick_check` and foreign-key integrity.
Version 3 adds only non-secret `youtube_selection` and daily `youtube_usage` tables through
an additive transaction; versions 1/2 data remain intact. Manually customized schemas are
unsupported; back up before upgrading. See the local table
summary in [Database behavior](#database-behavior). Schema 4 adds `safety_attempts`,
`safety_events` and `safety_clock`; these persist metadata/protection, not historical text.

**Original `comment_history` table (retained unchanged):** Phase 03 never populates this
future integration table. Its existing rows, if any, are preserved; browsing Phase 03 history
only reads `local_history`, never mislabels this as submission history.

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
| `youtube_comment_id` | TEXT | Historical legacy column; Phase 05 uses its own metadata ledger |

Index: `(live_chat_id, submitted_at)` — the query shape Phase 05 needs for duplicate detection
and cooldown enforcement.

**Data rules:** no passwords, OAuth tokens or client-secret values are stored in this database.
Only the selected target's YouTube account-channel ID is retained for future identity binding. User-written text may of course contain personal information.
Local event history has browsing and deletion now; drafts and the editor contain the text.

---

## Security Standards

### Authentication

* Official Google OAuth only; FloChat never collects or stores Google account passwords.
* No hardcoded credentials anywhere in the source tree.
* API secrets and private tokens are never committed.
* The Desktop client file is referenced **by path** (`FLOCHAT_CLIENT_SECRET`) outside the
  clone. `FLOCHAT_TOKEN_FILE` is rejected for authentication; tokens use OS keyring only.

### Credential storage

* Current OAuth credentials use approved OS keyring APIs only: Secret Service, Windows
  Credential Vault, or macOS Keychain. Unsupported, locked, plaintext, null and chained fallback
  backends fail closed. Termux OAuth is blocked pending a supported native flow/storage solution.
* The downloaded Desktop OAuth client JSON is owner-supplied configuration outside the clone;
  restrict its file permissions. Tokens and refresh tokens are never stored as JSON files.
* `FLOCHAT_TOKEN_FILE` is retained only as a rejected legacy option, not a plaintext fallback.
  FloChat does not import, overwrite or delete legacy files.
* Configuration files carry paths/settings only and reject credential fields. Set
  `FLOCHAT_CLIENT_SECRET` to the **path**, never a client-secret value. See Phase 04 setup.

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

* **Store only what is necessary:** one profile, one editor, saved drafts and metadata-only
  local/safety events and attempt-protection records, plus configuration you write yourself. No text snapshots in event history.
* **Explain what is stored:** this section plus the schema table are that explanation.
* **Keep history under user control:** local-only storage, no sync; `history list` and
  `history clear --yes` are implemented. Clearing event history does not delete drafts, the editor, or safety attempt protection records.
* **No unnecessary telemetry:** FloChat sends no analytics, crash reports, or usage data. The
  only outbound traffic that will ever exist is what the official YouTube API requires for an
  operation you started.
* **No third-party sharing of local comments:** individual posting requires a foreground session and fresh bound per-comment approval.
* Explicit YouTube operations transmit only the OAuth data, channel/video IDs and API
  parameters needed for authorization/discovery. Only an individually approved submission
  transmits its exact approved comment text; local editing never transmits draft contents.
  Installation contacts the package registry; local comment operations require no network.

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

* Persistent account/chat/content duplicate prevention in Phase 05.
* Submission cooldowns (`cooldown_seconds`, default 30, bounded 5–600; enforcement in Phase 05).
* Comment validation (implemented locally in `comments.validate_comment`).
* Preview before submission (the approved text is stored verbatim and re-usable for preview).
* Explicit terminal confirmation for each exact submission; a boolean alone is insufficient.
* Clear submission status (`StatusReport` with a `confirmed` flag; success requires confirmation).
* Error reporting through the shared state vocabulary.
* Explicit pause, stop and disconnect controls; none grants or restores approval.

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
| `pending` | Waiting on user input or on a later phase | 1 |
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

## Installation and Launch

Installation/launch source exists for Android (Termux), Linux and macOS, plus PowerShell
scripts for Windows. **Only Linux installation has executed successfully here.** The terminal remains the only installation
and launch interface.

**Verified vs unverified, up front:** the Linux installer was executed end to end in this
environment and is verified. The Termux, macOS, and Windows installers are **not** runtime
verified here (see [Phase 02 verification](#phase-02-verification-results)). Their logic is
shared or syntax-checked, but no claim of working installation is made for platforms that were
not executed.

### Repository URL

Use the literal placeholder `https://github.com/OWNER/REPOSITORY.git` below, replacing
`OWNER/REPOSITORY` with the owner-authorized repository. No actual origin is disclosed here.
The installers locate the local checkout and do not need a clone URL. To detect this checkout's
actual configured origin locally, use `git remote get-url origin`; it makes no network request.
Inspect that value locally (an origin can contain credentials); do not paste private URLs/tokens
into logs or chat. Source copies without `.git` can still install without an origin.

### Requirements

| Requirement | Detail |
| --- | --- |
| Python | 3.10 or newer, with `venv` and `ensurepip` available |
| Git | Needed to clone; the installer reports it if missing but does not install it |
| Network | Needed for declared Python dependencies; Android build additionally needs normal Google/Maven/Gradle access |
| Packaging tools | pip >=26.2; isolated setuptools >=84.1.0; stop if secure bootstrap fails |
| Privileges | None. The installer refuses to run as root and never uses `sudo` |
| Disk | One `.venv`; optional Qt is substantially larger and also needs native OS libraries |

Nothing is installed system-wide, no system Python is modified, and no environment variable is
written to your shell profile.

### Android (Termux)

```bash
pkg install git python
git clone https://github.com/OWNER/REPOSITORY.git FloChat
cd FloChat
./install.sh
./start.sh
```

`install.sh` detects Termux from `$PREFIX` or `$TERMUX_VERSION` and reports the platform as
Android. It creates `.venv`, installs FloChat, and verifies the CLI runs.

**What Termux does and does not give you:** Termux is a terminal. It does not provide floating
overlays, a persistent background service, or Android notification integration. Those require a
native companion application and belong to Phase 06. Phase 02 installs and launches the terminal
CLI only, and makes no attempt to bypass Android restrictions.

### Linux

```bash
git clone https://github.com/OWNER/REPOSITORY.git FloChat
cd FloChat
./install.sh
./start.sh
```

The installer identifies the distribution from `/etc/os-release`, checks for Python 3.10+ and a
working `venv`, and prints the package-manager command for your distribution if something is
missing. It never assumes `apt`. It does not run any privileged command; if a system package is
needed, it tells you what to run and stops.

Debian/Ubuntu users may need `sudo apt-get install python3-venv` first. Fedora users may need
`sudo dnf install python3`. The installer detects the gap and names it rather than failing
obscurely.

### macOS

```bash
git clone https://github.com/OWNER/REPOSITORY.git FloChat
cd FloChat
./install.sh
./start.sh
```

The installer checks the macOS version and architecture (`sw_vers`, `uname -m`). It works with
the Python from python.org or a Homebrew Python, but **does not require Homebrew** and does not
install it. If only the Command Line Tools Python is present and it lacks `venv`, the installer
says so and points at the system Python from python.org.

No macOS overlay, menu-bar item, or accessibility permission is part of Phase 02.

### Windows (PowerShell)

```powershell
git clone https://github.com/OWNER/REPOSITORY.git FloChat
cd FloChat
.\install.ps1
.\start.ps1
```

If local policy blocks unsigned PowerShell scripts, do **not** bypass or change execution
policy. Use the Python entry point without running a script, if your organization permits it:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade 'pip>=26.2'
.\.venv\Scripts\python.exe -m pip install -e .
.\.venv\Scripts\python.exe -m flochat.cli doctor
```

Stop if the tool/dependency installation fails. The scripts need PowerShell 5.1+ and Python
3.10+, never elevate or change execution policy. Windows runtime remains BLOCKED, including
this alternative path. PowerShell 7's read-only `$IsWindows` regression stays fixed.

### After installation

```bash
./start.sh              # launch the CLI from the clone
./start.sh doctor       # diagnose this installation
./start.sh settings     # show effective settings and their origin
```

`start.sh` / `start.ps1` only launch. They never install or modify anything, and they explain
what is wrong if the environment is missing, incomplete, or unimportable.

### Updating

```bash
git pull
./install.sh            # reuses .venv and refreshes the installed package
```

Re-running the installer is safe and repeatable: it reuses a healthy `.venv`, repairs an
incomplete one only after telling you what to remove, and never deletes your data directory,
configuration, or comment history.

### Uninstalling

Stop the shared owner before removing its environment (`./start.sh panel stop`; if it reports
no trustworthy endpoint, inspect `panel status` rather than killing unrelated processes).
For connected accounts, explicitly remove FloChat's OS-keyring grant **before** deleting the
venv: `./start.sh youtube disconnect --yes` (optionally `--revoke` to request Google revocation).
That grant is shared by this user's FloChat clones. A failed deletion is not a cleanup success.
Native companions must be stopped/uninstalled separately through normal Android settings.

Removing `.venv` removes the local Python environment; deleting the clone removes source, not
external data. Inspect `flochat settings` first: custom `FLOCHAT_HOME`/`FLOCHAT_DB` override the
following defaults. Back up anything wanted, then delete **only** the confirmed FloChat path:

* Linux/Termux: `$XDG_CONFIG_HOME/flochat` or `~/.config/flochat`.
* macOS: `~/Library/Application Support/FloChat`.
* Windows: `%APPDATA%\FloChat`.

Do not blindly delete arbitrary custom directories. Editor, drafts, profile and protection
records are removed if their database is deleted. Client JSON outside the clone and Google
account grants are separate; venv/data deletion alone does not revoke/delete them. No startup
service, login item or system package was registered. SQLite deletion is not forensic erasure.

### Configuration

```bash
cp .env.example .env      # Windows: Copy-Item .env.example .env
```

`.env` is git-ignored and must never contain credentials — only variables such as
`FLOCHAT_MODE`, `FLOCHAT_LOG_LEVEL`, `FLOCHAT_HOME`, `FLOCHAT_DB`, `FLOCHAT_CLIENT_SECRET`
(path only). Leave legacy `FLOCHAT_TOKEN_FILE` unset. `.env` is **not auto-loaded**; export
variables in your shell. Environment variables take precedence over
`config.json` in the platform data directory. `flochat settings` shows which layer supplied each
value.

---

## CLI Reference

`flochat` provides **18 top-level commands and 42 leaf actions**. All of them are listed in
`src/flochat/roadmap.py`, and `flochat doctor` fails if the parser and that list ever disagree.

| Command | Purpose | Exit code |
| --- | --- | --- |
| `flochat --help` | Show usage and the honest current scope | 0 |
| `flochat --version` | Print version and current phase | 0 |
| `flochat version` | Version, tagline, and phase as a report | 0 |
| `flochat start [--mode manual\|persistent]` | Start shared core/session, never approve or post | 0 on observed success; nonzero on failure |
| `flochat stop` | Stop new actions; cannot recall an in-flight write | 0 stopped, 1 pending/error |
| `flochat status` | Local diagnostics; inspect nested database/runtime health, not only exit 0 | 0 report produced, 2 invalid config |
| `flochat state` | The full state vocabulary with exit codes | 0 |
| `flochat settings` | Effective settings and where each value came from | 0 |
| `flochat doctor` | Diagnose the installation | 0 healthy, 1 problems, 3 unsupported |
| `flochat platform` | Detected platform and all four adapter reports | 0 |
| `flochat config show` | Effective vs persisted configuration | 0 |
| `flochat config validate` | Validate configuration | 0, 2 if invalid |

The 16 local actions are documented in the [local CLI table](#local-cli-reference); seven
YouTube actions are in the [YouTube CLI table](#youtube-cli-reference). `safety` opens the
interactive shared-owner console; `panel start/serve/view/stop/status/pair`, `session` and `mode`
are documented in Phase 06. `session` accepts start/pause/resume/stop/status/recover.
`config` without an action currently defaults to its read-only report; it does not mutate data.

Add `--json` before the command for machine-readable output: `flochat --json status`.

Exit codes are consistent across commands: `0` success, `1` failure or a problem found, `2`
invalid usage or configuration, `3` unsupported platform or required permission, `4` incomplete
environment (missing or outdated dependencies).

### `flochat doctor`

`doctor` is the command to run when something is wrong. It observes, and reports what it found:

| Check | What it establishes |
| --- | --- |
| `platform` | Whether this is one of the four supported terminals; flags Android without Termux |
| `python` | Version is 3.10+, and `sys.executable` really exists |
| `runtime` | FloChat, Python, and SQLite versions plus the interpreter path |
| `dependency:pydantic` | Present, and major version 2 |
| `package` | FloChat imports, and from which path |
| `environment` | Whether an isolated environment is active; fails on a bare repo run |
| `venv_support` | Python can create a venv with pip |
| `sqlite` | Version meets the minimum |
| `storage` / `database` | The data directory is writable and the database opens and passes its check |
| `configuration` | The config file parses and there are no credential fields |
| `launch_scripts` | Installer and launcher scripts are present |
| `safety_gate` | Unapproved submissions are still blocked; approved ones still refuse to send |
| `cli_surface` | Parser commands and declared operations agree |
| `documentation` | The README documents the current phase |

Findings are `ok`, `warn`, `fail`, or `skip`. `skip` means a check could not be performed and
says why; it is never reported as healthy. Exit 0 is local CLI health, not native/Google certification.
`doctor` is read-only apart from applying the database schema on valid configuration; invalid
configuration skips storage entirely and exits nonzero. It runs even when configuration is invalid — that is exactly when it is
needed.

---

## Troubleshooting

Every installer failure prints three lines: what failed, why it may have failed, and what to do
next. The table below covers the failures that actually occur.

| Symptom | Cause | Safe next step |
| --- | --- | --- |
| `Refusing to install as root.` | `install.sh` was run with `sudo` or as root | Re-run without `sudo`. A root-owned `.venv` breaks normal use |
| `No Python 3.10 or newer was found.` | Python missing, or only an older version on `PATH` | Termux: `pkg install python`. Debian/Ubuntu: `sudo apt-get install python3`. macOS: install from python.org |
| `This Python cannot create virtual environments with pip.` | `venv`/`ensurepip` missing (`python3-venv` not installed) | Debian/Ubuntu: `sudo apt-get install python3-venv`. Then re-run the installer |
| `Could not create the Python environment.` | `venv` module broken, or no write permission in the clone | Check the `venv` hint the installer prints; ensure you own the clone directory |
| `Installing FloChat failed.` | No network, proxy blocking PyPI, or DNS failure | Check `pip config list` and your proxy; then re-run. Offline installs need a local wheel |
| `The existing environment at ... is incomplete.` | An earlier install was interrupted, or the folder was moved | `rm -rf .venv` then re-run the installer. The installer will not silently reuse it |
| `FloChat is not installed in this directory.` | `start.sh` run before `install.sh`, or from another directory | `cd` into the clone, run `./install.sh` |
| `FloChat installed but does not run.` | A dependency is missing from the environment | Run `./start.sh doctor`; the installer prints the CLI's real error output |
| `FloChat cannot start because required Python packages ...` (exit 4) | `pydantic` missing or not version 2 | `python -m pip install 'pydantic>=2.6,<3'` in `.venv`, or re-run the installer |
| `Invalid configuration (...)` (exit 2) | A malformed or credential-bearing `config.json` | Fix or delete the named file. `flochat settings` shows the expected shape, and `flochat doctor` still runs |
| `This operating system is not supported by install.sh` (exit 3) | Not Android, Linux, or macOS | On Windows use `install.ps1`. Other systems are out of scope |
| PowerShell: `... cannot be loaded because running scripts is disabled` | Execution policy blocks unsigned scripts | Use the documented direct Python entry point if allowed; do not bypass/change policy |
| PowerShell: `No Python 3.10 or newer was found` | Python not on `PATH` | Reinstall Python with "Add python.exe to PATH" ticked, reopen PowerShell |
| `doctor` reports `environment` fail | FloChat is running from the repo without `.venv` | Use `./start.sh`, or install with `./install.sh` |
| Android: overlay or background features absent | Termux provides a terminal only | Expected. Overlays are Phase 06 and need a companion app |

If none of these apply, run `./start.sh doctor`. Review output before sharing: paths, OS
information and identifiers can be personal, even though credential values are not intentionally
printed. Do not share pairing codes, full client JSON or raw third-party debug dumps.

## Phase 01 Verification Results

Historical Phase 01 snapshot. Phase 03 intentionally changes local whitespace/Unicode and
length handling; the current verification script checks the updated contract separately.

These remain true and are re-checked by the Phase 02 regression suite below. Everything here was
originally executed in the Phase 01 environment: a **Linux x86_64 sandbox**
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
| 15 | Boundary behaviour suite | 46 assertions executed in-process (see below) | **Pass** — 46/46 |
| 16 | Fresh-clone build | `git clone` → `pip install -e .` → `ruff check .` → guard script | **Pass** — installs, lints, and passes the guard with no leftovers |
| 17 | Git cleanliness | `git status --porcelain --ignored` review | **Pass** — only intended files tracked; `.venv`, caches, `*.egg-info`, local databases ignored |
| 18 | Dead code | Guard script AST scan over 114 definitions | **Pass** — zero unreferenced definitions |
| 19 | Guard is not vacuous | Injected an unused function, re-ran the guard, then reverted | **Pass** — guard failed as intended, then reported clean again |
| 20 | Exit-code consistency | Compared `flochat state` output against the exit codes the CLI actually returns | **Pass** — one mapping table drives both |

**Boundary behaviour suite (check 15).** Executed directly with the interpreter rather than
through a test framework, because Phase 01 has no test directory. All 46 assertions passed:

* Confirmation rule: `StatusReport.of(SUCCESS)` is not `ok`; confirmed success is `ok`; all ten
  states exist and each has a message; `pending` is never treated as success.
* Comment safety: zero-width characters are stripped and whitespace collapsed; empty and
  over-length comments are rejected while 200 characters is accepted; `submit()` blocks empty
  text and a missing chat before it ever reaches the approval check; unapproved submissions raise
  `ApprovalRequiredError`; truthy non-booleans (`1`, `"yes"`, `[1]`) are **not** accepted as
  consent; even a fully valid, approved request raises `NotSupportedYetError` naming Phase 04.
* Configuration: credential fields, relative paths, and unknown keys are each refused with a
  precise message; `FLOCHAT_HOME` relocates both the database and `config.json`.
* Storage: schema version 1, `integrity: ok`, `comment_history` present with zero rows, and a
  database written by a newer schema version is refused.
* Lifecycle: manual start/stop succeed and stop is idempotent; an interruption is non-terminal;
  persistent start and recovery report `permission_required`; manual recovery reports `pending`
  and never resubmits.
* Boundaries: OAuth reports not configured, the API client reports `pending`, live chat reports
  `live_chat_unavailable`, `requests_sent == 0`, every documented error code is classified,
  quota maps to interruption, forbidden maps to permission, an unknown code maps to failure, and a
  present token is reported as `configured`/`pending` rather than authorized.
* Adapters: four adapters described, none claiming implementation or overlay capability, and the
  matching adapter is selected for this platform.

Also verified during this phase: an uncreatable data directory yields a `StorageError` state
instead of a traceback, and malformed JSON plus a credential field in `config.json` are each
refused with a clear message and exit code 2.

### Hardening pass (after the initial commit)

The first commit was audited rather than assumed correct. An AST scan found **24 definitions
referenced only at their own definition site** — placeholder code for planned features, which the
Phase 01 rules forbid. All were removed or made genuinely reachable, and the rule is now enforced
automatically:

* **Removed as speculative:** `InterfaceKind`, `KNOWN_TERMINALS`, `PlatformInfo.has_terminal`,
  `config_path`, `LOG_LEVELS`, `Session.interruptions`, `SessionManager.note_interruption`,
  `AppState.is_terminal`, `AppState.needs_user_action`, `PlatformAdapter.ensure_available`,
  `Database.utc_now`, plus five error classes that no shipped code could raise
  (`AuthenticationRequiredError`, `SessionExpiredError`, `PermissionRequiredError`,
  `NetworkInterruption`, `OrientationError`).
* **Collapsed instead of stubbed:** `comments.prepare`, `is_valid_handle`, and `normalize_handle`
  were folded into a single safe entry point, `submit(SubmissionRequest)`, whose guard order is
  the guarantee. Handle validation was removed because the example comment is free text with a
  handle in it, not a handle-only field — validating it as a bare handle would have rejected
  valid input.
* **Made reachable rather than deleted:** the YouTube boundaries are all exercised by `status`
  (new `youtube` section, including `requests_sent: 0`), `ApiErrorBoundary.coverage()` classifies
  every documented code at runtime so the table cannot rot, and the state vocabulary became
  inspectable through the new `flochat state` command.
* **Two real bugs found in this pass:** `errors.py` lost `NotSupportedYetError` during pruning
  (caught by an import check, not by the linter — Ruff alone was not sufficient verification), and
  the `state` table documented `permission_required` as exit 1 while the CLI returned 3. Both are
  fixed; a single `state_exit_code()` mapping now drives the table, the reports, and the process
  exit code.
* **New guard check:** `_check_dead_code` fails the repository guard when any definition is
  referenced only once, so this standard cannot silently regress in later phases.

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
| `src/flochat/errors.py` | Error hierarchy mapped to application states (only errors that are raised) |
| `src/flochat/platform.py` | Platform detection, capability reporting, data-directory resolution |
| `src/flochat/adapters.py` | Adapter contract plus Android/Windows/Linux/macOS descriptors, all `implemented: False` |
| `src/flochat/config.py` | Strict configuration loading/validation, logging setup, secret-field refusal |
| `src/flochat/database.py` | SQLite boundary, schema version 1, integrity and health checks |
| `src/flochat/comments.py` | Comment safety boundary: normalisation, validation, approval guard, single refusing entry point |
| `src/flochat/lifecycle.py` | Manual session lifecycle, persistent-mode honesty, interruption/recovery reporting |
| `src/flochat/youtube.py` | OAuth, API client, live chat identification, and API error boundaries (no requests) |
| `src/flochat/controller.py` | Application controller combining all boundaries into reports and lifecycle actions |
| `src/flochat/cli.py` | `argparse` CLI: 7 top-level commands, 8 invocable actions, single exit-code mapping, JSON envelope |
| `scripts/check_repository.py` | Repository guard: structure, placeholders, secrets, dead code, README coverage, syntax |

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

Twenty checks executed, all passing, in a Linux x86_64 sandbox — see
[Verification Results](#phase-01-verification-results) for the table and for the explicit list of things
that were **not** verified. Summary: lint and formatting clean; every module parses and imports;
the package installs from a fresh clone and runs; all 8 command actions exercise successfully; the
database schema is created and verified healthy; invalid configuration and persistent mode both
fail honestly with the right exit codes; the repository guard reports no clutter, no credentials,
and no dead code — and was proven capable of failing when a violation is injected.

A post-commit hardening pass resolved all 24 dead definitions (removing the speculative ones and
making the rest genuinely reachable), collapsed three stub-like comment
helpers into one guarded entry point, wired every YouTube boundary into `status`, added the
`flochat state` command, fixed two real defects found by auditing (a lost error class and an
exit-code table that contradicted behaviour), and added an automated dead-code check to the
guard. Details in [Verification Results](#phase-01-verification-results).

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
in [Verification Results](#phase-01-verification-results) were actually executed — none are claimed
without having run. Phase 03, which introduces real comment logic, is where a focused test suite
becomes worthwhile.

---

## Repository File Inventory

Historical inventory as of Phase 04; the architecture tree and final Phase 08 report include
the later safety/runtime/platform verifier files. Every file below is non-empty and referenced by the
implementation or the approved workflow; the repository guard enforces both.

| Path | Type | Role |
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
| `src/flochat/comments.py` | Source | Local Comment Manager, validation and intact submission guard |
| `src/flochat/lifecycle.py` | Source | Session lifecycle and modes |
| `src/flochat/youtube.py` | Source | YouTube integration boundaries |
| `src/flochat/controller.py` | Source | Application controller |
| `src/flochat/cli.py` | Source | Terminal entry point, exit codes, JSON envelope |
| `src/flochat/roadmap.py` | Source | Approved phases and the implemented CLI surface |
| `src/flochat/settings.py` | Source | Effective settings and their provenance |
| `src/flochat/doctor.py` | Source | Environment diagnosis for `flochat doctor` |
| `src/flochat/dependencies.py` | Source | Runtime dependency declaration and diagnosis |
| `install.sh` | Installation | Installer: Android/Termux, Linux, macOS |
| `start.sh` | Launcher | Launch and diagnose the environment |
| `install.ps1` | Installation | Installer: Windows PowerShell |
| `start.ps1` | Launcher | Launch and diagnose the environment (Windows) |
| `scripts/check_repository.py` | Tooling | Repository, dead-code, and credential guard |
| `scripts/verify_comments.py` | Verification | Executable local, migration, CLI and safety regressions in temporary storage |
| `scripts/verify_youtube.py` | Verification | Mocked OAuth/API/keyring plus real local storage/CLI checks; no live service requests |
| `scripts/install_lib.sh` | Tooling | Shared installer helpers for the Unix scripts |

Not tracked by design: `.venv/` (local virtual environment), `__pycache__/`, `.ruff_cache/`,
`*.egg-info/`, local `*.sqlite3` databases, and any `.env`.

---

## Known Limitations

1. **Release blocked by missing owner-selected project licence.** No licence grant, legal
   clearance, binary distribution, publication or public release is certified.
2. **Linux core/CLI/SQLite/local IPC/install executed; native GUI not runtime verified.** No
   Qt offscreen, X11 or Wayland workflow passed. Required native libraries/display are absent.
3. **Windows/macOS/Android native runtimes unverified.** Static source/grammar inspection is
   not execution. Android APK has not been built; no emulator, physical device or real Termux
   runtime passed. Do not market these as runtime-certified platforms.
4. **Real Google OAuth/YouTube behavior not verified.** Consent, callback, refresh, account/chat
   permissions, quota and insert responses are mocked. No real automated comment was sent.
5. **Termux Google authorization is unsupported and fails closed.** Android Keystore stores
   only the companion's local IPC pairing capability, not Google tokens. No plaintext fallback.
6. **Background availability is not OS survival.** No boot/login task, unattended posting,
   session/approval restoration or write retry. OS restrictions can end either process.
7. **One grant per OS user, shared by clones.** Account/scope changes require explicit disconnect
   and new consent. Write scope is broad account permission, not a per-comment OAuth scope.
8. **Storage is local, not encrypted SQLite.** Editor/drafts/profile contain user content;
   histories are metadata-only but reveal timing/IDs/counts. Fingerprints permit guessing.
   Deletion is logical, not forensic erasure. Protect the OS account/files/backups.
9. **Trusted local owner boundary.** Same-user/root compromise, modified Python/SQLite, another
   API client and distributed/network-filesystem coordination are outside the guarantees.
10. **Unknown writes require human chat inspection.** Stop cannot recall transmission;
    durable unknown/reserved attempts block future posting until explicit review. Same-content
    protection remains. No automated reconciliation, bulk send, repeat mode or duplicate override.
11. **Source-clone delivery only; no signed/native release artifacts.** Core wheel build smoke
    passed privately, but no wheel/APK, signing/notarization or release package is delivered.
12. **Installation needs trusted dependency access.** No offline bundle/lockfile is delivered.
    Runtime ranges are bounded major versions, not a reproducibility or vulnerability-free claim.
    Packaging now requires pip >=26.2 and isolated setuptools >=84.1.0.
13. **Local UI/terminal limits remain.** No undo; stdout/shell history may expose explicitly
    displayed text. API length limit is server-authoritative; configured default 200 is local
    policy. Topmost flags and accessibility are not platform-certified. See final report.

---

## Pending Work and Approved Roadmap

FloChat has exactly **eight** approved phases. This roadmap is fixed: phases are not added,
removed, renamed, or expanded, and no phase begins before the previous one is approved.

| Phase | Name | Scope | Status |
| --- | --- | --- | --- |
| 01 | Foundation | Architecture, boundaries, standards, documentation, verification | **Complete** |
| 02 | CLI & Installation | CLI enhancement, platform installers and launch scripts, dependency management | **Complete** |
| 03 | Comment Manager | Usernames, editing, drafts, preview, local history | **Complete locally** |
| 04 | YouTube Integration | Official OAuth, account and chat discovery, readonly API; posting held for Phase 05 safety | **Implemented; live verification blocked** |
| 05 | Safety Engine | Approval flow, duplicate detection, cooldowns, per-comment confirmation | **Implemented; live write unverified** |
| 06 | Floating & Background Engine | Native adapters, overlays, persistent mode, interruption/recovery | **Implementation present; native delivery/verification blocked** |
| 07 | Cross-Platform Testing | Verified behaviour on Android/Termux, Windows, Linux, macOS | Tested; platform verification partially blocked |
| 08 | Final Release | Final audit, packaging/licence/release gate | **Audited — NOT RELEASE READY; project licence unresolved** |

**Repository and release restrictions in force:** the repository is not published, no release or
installer is uploaded or published, repository visibility is unchanged, and no external
publishing has occurred. Publishing and release require explicit owner approval.

---

FloChat — Your Live Chat, Always Within Reach.

---

## Phase 02 Verification Results

Environment: **Linux x86_64 sandbox**, Debian 12, bash 5.2.15, Python 3.11.2, SQLite 3.40.1,
Ruff 0.17.3, Pydantic 2.14.2, non-interactive shell. PowerShell was **not** installed here; the
`.ps1` files were parsed with a real PowerShell grammar instead.

### What was actually executed, and what was not

| Platform | Installer | Level of verification |
| --- | --- | --- |
| Linux | `install.sh` | **Actually executed.** Clean install, repeat install, broken-environment, root, unsupported-OS, and wrong-directory paths all run |
| Android/Termux | `install.sh` | **Simulated only.** Termux detection exercised via `PREFIX`/`TERMUX_VERSION`; no real Termux device. Runtime **NOT EXECUTED** |
| macOS | `install.sh` | **Syntax and static only.** Shares the Linux code path; runtime **NOT EXECUTED** |
| Windows | `install.ps1` | **Syntax parsed only** with a tree-sitter PowerShell grammar. No PowerShell runtime. **NOT EXECUTED** |

No simulator result is described as a real installation test.

### Check results

| # | Check | Method | Result |
| --- | --- | --- | --- |
| 1 | Bash syntax | `bash -n` on `install.sh`, `start.sh`, `scripts/install_lib.sh` | **Pass** |
| 2 | POSIX syntax | `dash -n` on the same three files | **Pass** (parse only; `install.sh` requires bash features at runtime) |
| 3 | PowerShell syntax | tree-sitter-powershell parse of `install.ps1` and `start.ps1`; any ERROR or missing node fails | **Pass** — both clean, no errors |
| 4 | Python syntax and lint | `ruff check .`, `ruff format --check .` | **Pass** — "All checks passed", no reformatting needed |
| 5 | Linux clean install | `./install.sh` in a fresh copy of the tree | **Pass, executed** — venv created, package installed, `Verified: FloChat 0.1.0 (Phase 02 - CLI & Installation)` |
| 6 | Repeat install | Second `./install.sh` | **Pass, executed** — reports "Reusing the existing environment", no rebuild |
| 7 | Launch after install | `./start.sh --version`, `./start.sh doctor`, bare `./start.sh` | **Pass, executed** — 0, 0, and help respectively |
| 8 | Missing `python3-venv` handling | Simulated by removing `bin/python` from `.venv` | **Pass, executed** — installer exits 1 naming the incomplete environment and the exact `rm -rf` remedy, without reusing or deleting it |
| 9 | `start.sh` with broken env | `bin/python` removed | **Pass, executed** — exit 2, explains cause and remedy |
| 10 | `start.sh` with no env | `.venv` moved aside | **Pass, executed** — exit 2, points at `install.sh` |
| 11 | Root refusal | `id` shim reporting uid 0 | **Pass, executed** — exit 2, refuses, explains why |
| 12 | Unsupported OS | `uname` shim reporting FreeBSD | **Pass, executed** — exit 3, names the supported set and points Windows users at `install.ps1` |
| 13 | Wrong directory | `install.sh` copied away from `scripts/` | **Pass, executed** — exit 2, names the missing library and says to clone the whole repository |
| 14 | Termux detection | `PREFIX`/`TERMUX_VERSION` set | **Pass, simulated** — reports Android (Termux) and states overlays are Phase 06 |
| 15 | Dependencies declared | `flochat.doctor` dependency check vs `pyproject.toml` | **Pass** — one runtime dependency, `pydantic>=2.6,<3`, present and version 2 |
| 16 | Missing dependency handling | `PYTHONPATH` shim raising `ImportError` for `pydantic` | **Pass, executed** — exit 4, names the package, prints the exact `pip install` fix, no traceback |
| 17 | Invalid configuration | `{"mode":"nonsense"}` in `config.json` | **Pass, executed** — `settings`/`status` exit 2 naming the field; `doctor` still runs and reports the failure as `fail` |
| 18 | Unwritable data directory | `FLOCHAT_HOME=/proc/flochat-nope` | **Pass, executed** — `doctor` reports a `database` fail with the observed OS error |
| 19 | CLI consistency | All eight required actions plus exit codes | **Pass** — `--help`, `--version`, `start`, `stop`, `status`, `state`, `settings`, `doctor` all exit 0; unknown command and bad `--mode` exit 2; persistent `start` exits 3 |
| 20 | No duplicate registrations | `doctor` `cli_surface` check comparing parser to `roadmap.py` | **Pass** — 9 commands, 10 declared actions, no mismatch |
| 21 | Phase 01 regression suite | 31 in-process assertions | **Pass** — 31/31 |
| 22 | Dead-code audit | AST reference counting in the repository guard | **Pass** — 199 definitions, zero unreferenced |
| 23 | Guard still fails on violations | Injecting an unused function in Phase 01; guard also flagged new dead code in Phase 02 | **Pass** — detects and names each one |
| 24 | Credential scan | Guard patterns for Google access/refresh tokens, `GOCSPX-`, `AIza`, private keys | **Pass** — zero matches across all text files |
| 25 | Repository cleanliness | Guard top-level allow-list, extra-Markdown, placeholder, empty-folder checks | **Pass** — clean |

### Phase 01 regressions re-checked

The 31-assertion suite confirms Phase 01 behaviour survived Phase 02: unconfirmed success is
still not `ok`, unapproved submissions are still blocked, truthy non-booleans are still not
consent, `submit()` still refuses to send, persistent mode still reports `permission_required`,
recovery still never resubmits, no adapter claims implementation or overlay capability, and the
YouTube boundaries still send zero requests.

### Dead-code findings this phase

The Phase 01 guard counted *text* occurrences, so a docstring word and an unrelated same-named
function could hide a dead definition. It now counts real AST references and follows import
aliases. That immediately exposed seven definitions Phase 01 had missed:

| Definition | Resolution |
| --- | --- |
| `platform.describe()` | Now feeds the `runtime` doctor check |
| `StatusReport.of()` | Now used by the new `approval_report()` |
| `SessionManager.recover()` | Now reached through `flochat status` → `recovery` |
| `doctor.diagnose()` / `doctor.render()` | Wired into the `doctor` command (the old scan had mistaken an alias import for a reference) |
| `AndroidAdapter.secure_storage_note()` and its siblings | Now reported per adapter as `secure_storage_target` |
| `comments.submit()` | Now exercised by the `safety_gate` doctor check, so the guarantee is verified on every run instead of only asserted in prose |

Two Phase 01 dead definitions were removed outright rather than wired: the hand-maintained
`implemented_operations` / `deferred_operations` lists in the controller, which are now generated
from `src/flochat/roadmap.py`.

---

## Phase 02 Completion Report

### 1. Status

**Complete.** CLI enhanced, installers implemented and verified as far as this environment
allows, dependencies managed, README updated. No Phase 03 work was started.

### 2. CLI changes

| Change | Detail |
| --- | --- |
| Added `flochat settings` | Read-only. Shows effective settings, the origin of each value (environment / config file / default), the config file path, and the exact variable to change |
| Added `flochat doctor` | 14 checks with `ok`/`warn`/`fail`/`skip`, an actionable numbered list, and JSON output |
| Fixed `status` drift | `implemented_operations` and `deferred_operations` are generated from `roadmap.py`; Phase 01's hand-written list omitted `state` |
| Fixed `version` phase label | Was hardcoded to "Phase 01 - Foundation" |
| Added recovery and gate to `status` | `recovery` and `submission_gate` sections |
| Added exit code 4 | Incomplete environment (missing or outdated dependencies) |
| Dependency guard | Missing `pydantic` now produces an explanation and a fix command, not an `ImportError` traceback |
| `doctor` survives bad config | Uses a defaults-only controller so a broken `config.json` is reported instead of blocking the diagnostic |

`argparse` was kept. The Phase 01 technology table named Typer as the Phase 02 direction, but
adopting it would add a runtime dependency, rewrite the CLI, change `--help`, and re-verify every
action without improving the installation work this phase is actually about. §8 forbids adding
packages without a genuine need. This is recorded as a deliberate deviation.

### 3. Installation scripts created

| File | Purpose |
| --- | --- |
| `install.sh` | Installer for Android/Termux, Linux, macOS: platform detection, root refusal, project and Git checks, Python 3.10+ discovery, venv support check, environment creation or safe reuse, dependency install, verify-by-running, honest platform limits |
| `start.sh` | Launcher for the same three platforms. Only launches; diagnoses a missing, broken, or unimportable environment with a remedy |
| `scripts/install_lib.sh` | Shared bash helpers sourced by `install.sh`: messaging, failure reporting, interpreter discovery, venv checks, install and verification |
| `install.ps1` | Windows installer: PowerShell version check, Python discovery including the `py` launcher, venv creation or reuse, install, verify, execution-policy guidance without changing policy |
| `start.ps1` | Windows launcher, mirroring `start.sh` |

The three Unix installers share one implementation through `install_lib.sh` rather than
duplicating logic three times.

### 4. Dependency management changes

* Runtime dependencies remain exactly one package: `pydantic>=2.6,<3`. Nothing was added for
  Phase 02.
* `src/flochat/dependencies.py` declares that dependency for *diagnosis*, so a missing or old
  version is explained rather than crashing. `pyproject.toml` stays the source of truth for
  installation.
* Development tooling (`ruff`) remains in the optional `dev` extra and is never installed by the
  installers.
* Installers always use an isolated `.venv`, never system Python, and never install a second
  package manager.
* Installation is repeatable: a healthy environment is reused, a broken one is reported with the
  exact removal command, and no data directory is touched.

### 5. Supported platform detail

| Platform | Detection | Python discovery | Privileges |
| --- | --- | --- | --- |
| Android/Termux | `$PREFIX` containing `com.termux`, or `$TERMUX_VERSION` | `python3`, `python3.10`–`python3.13`, `python` | No `sudo`; refuses root |
| Linux | `uname -s` = Linux, distribution from `/etc/os-release` | Same list | No `sudo`; refuses root |
| macOS | `uname -s` = Darwin, version from `sw_vers` | Same list | Refuses root |
| Windows | `$IsWindows` / `$env:OS` | `py -3`, `python`, `python3` | No elevation; never changes execution policy |

### 6. Actual installation verification results

Executed on Linux: clean install, repeat install, launch, and nine failure paths (checks 5–13 and
15–19 above). **Not executed:** Termux, macOS, and Windows runtimes. Termux detection was
simulated; the PowerShell scripts were parsed by a real grammar. No claim is made that those
installers work on real hardware yet.

### 7. Syntax and static-check results

`bash -n` and `dash -n` clean on all three shell files. A tree-sitter PowerShell grammar parsed
both `.ps1` files with no errors or missing nodes. Ruff lint and format clean. The repository
guard parses every Python file.

One caveat worth stating: the grammar rejects a one-line `param(...)` block inside a function
body, which is valid PowerShell. The script uses the conventional multi-line form so the check
stays meaningful rather than being annotated away.

### 8. Phase 01 regression results

31 assertions, 31 passing. See [Phase 01 regressions re-checked](#phase-01-regressions-re-checked).

### 9. Dead-code audit results

199 definitions scanned, zero unreferenced. Seven Phase 01 escapes were found and resolved (see
[Dead-code findings this phase](#dead-code-findings-this-phase)); two hand-maintained duplicate
lists were deleted in favour of generated ones. The guard was strengthened, not weakened, and was
proven to fail on injected dead code.

### 10. Known limitations

1. **Three platforms are unverified at runtime.** Termux, macOS, and Windows installers have not
   been executed. Only Linux is verified.
2. **No offline installation.** `pip` needs network access to fetch `pydantic`.
3. **No package-manager distribution.** Installation is from a clone, as the product identity
   requires; nothing is published to PyPI, Homebrew, or winget.
4. **`settings` is read-only.** There is no `settings set`; you edit the file or set a variable.
5. **No shell integration.** The installers do not add `flochat` to `PATH` or write to your shell
   profile; use `./start.sh` from the clone.
6. **Terminal only.** No overlay, background service, tray icon, or notification exists.
7. **`doctor` without `pydantic` exits 4 before diagnosing the rest.** Diagnosis of a missing
   dependency is the fix for that state, so this ordering is deliberate.
8. **Uninstall guidance is manual.** No `uninstall.sh` was added because the operation is two
   `rm -rf` commands; a script was judged unnecessary.

### 11. Unverified platforms

Android/Termux (detection simulated only), macOS (static checks only), Windows (syntax parsed
only). Phase 07 is the approved phase for real cross-platform runtime verification.

### 12. Remaining blockers

None for Phase 02. Outstanding before release (Phase 08): a licence, and real-hardware testing on
the three unverified platforms.

### 13. Files created and modified

**Created:** `install.sh`, `start.sh`, `install.ps1`, `start.ps1`, `scripts/install_lib.sh`,
`src/flochat/roadmap.py`, `src/flochat/settings.py`, `src/flochat/doctor.py`,
`src/flochat/dependencies.py`.

**Modified:** `src/flochat/cli.py` (two commands, exit code 4, dependency guard, phase label),
`src/flochat/config.py` (public env-variable map, `config_file_path`), `src/flochat/controller.py`
(generated operation lists, `degraded()`, `recovery_report()`, `approval_gate()`),
`src/flochat/comments.py` (`approval_report`), `src/flochat/platform.py` (`describe` returns
interpreter detail), `src/flochat/adapters.py` (`secure_storage_target`),
`scripts/check_repository.py` (AST-based dead-code counting, alias following, new allow-list
entries), `README.md` (this document).

**Not created:** no `docs/`, `documentation/`, `reports/`, `examples/`, or `tests/` folder; no
extra Markdown file; no placeholder script; no duplicate configuration file; no dummy platform
adapter; no separate installation guide. The root `README.md` remains the single documentation
file, and the repository guard enforces that.

### 14. Scope confirmation

No comment editor, saved comments, OAuth, YouTube API calls, submission, overlays, background
engine, session recovery, payments, or unapproved features were implemented. The roadmap remains
eight phases. Nothing was published, released, uploaded, or had its visibility changed, and this
phase's changes were **not committed or pushed** — they are left in the working tree for review,
as instructed.

---

## Local Comment Manager

All commands below work **locally**, with no YouTube account, verification, internet connection,
OAuth, or sending step. Use `./start.sh` instead of `flochat` if the environment is not activated;
on Windows use `.\start.ps1`. Put `--json` **before** the command when scripting. Group commands
without an action print usage and exit 2; there are no ambiguous default mutations.

### Username management

```sh
flochat username set '@Sarthak123'
flochat username show
flochat username set 'ordinary username'
flochat username delete --yes
```

There is one active **local profile**, not a verified YouTube identity. `set` creates or updates
it (including the same value, without creating duplicates). Ordinary names, handles, spaces and
Unicode are allowed; empty names, control characters, tabs and multiline names are rejected.
Outer whitespace is trimmed. Deleting the profile does not rewrite previously prepared text or
saved drafts: those remain your text until you explicitly edit/delete them.

### Comment editor and generation

The terminal editor is a persistent text buffer, not a full-screen graphical editor. Commands
replace its complete text; use a shell or external text editor to compose long/multiline input:

```sh
flochat comment new --text 'Hello, world!'
flochat comment show
flochat comment edit --text 'Hello, नमस्ते 🌍'
flochat comment preview
flochat comment clear --yes
flochat username set '@Sarthak123'
flochat comment generate --template intro
flochat comment edit --text 'My username is @Sarthak123 — thank you!'
```

Templates are three fixed choices, not a template engine:

| Choice | Generated text |
| --- | --- |
| `intro` (default) | `My username is {username}` |
| `hello` | `Hello, my username is {username}` |
| `entry` | `Please consider my entry: {username}` |

Only `generate` reads the saved username into a comment. Generated text is ordinary editable
text; no profile change silently rewrites it. The preview's username field is a snapshot only
for explicit generation/opening of a generated draft. Arbitrary `edit` clears that association
rather than claiming the new text still represents that username.

`new`, `generate`, and `drafts open` refuse to replace a nonempty editor without **`--replace`**.
Save first, or intentionally add that flag. `edit` is the explicit replacement action on the
current buffer and keeps its draft association, so the next `drafts save` updates that draft.
`new` and `generate` start a separate unsaved comment; they do not overwrite the previous draft.
`clear --yes` clears only the editor, not any saved drafts.

For exact multiline UTF-8 input, use `--stdin` instead of `--text`:

```sh
# Unix shells: read from a local file (FloChat never modifies that file)
flochat comment new --stdin --replace < /absolute/path/comment.txt
# Or pipe UTF-8 text from another command
printf 'Hello  world\n\nनमस्ते 👩‍💻\n' | flochat comment new --stdin --replace
```

PowerShell: `Get-Content -Raw -Encoding UTF8 .\comment.txt | .\start.ps1 comment new --stdin --replace`.
When piping Unicode from **Windows PowerShell 5.1**, first set the session's
`$OutputEncoding = [System.Text.UTF8Encoding]::new($false)` so native-command input is UTF-8;
PowerShell 7 defaults to UTF-8. Windows piping is documented but **NOT EXECUTED** here.
Stdin reads to EOF. Invalid UTF-8 fails clearly; do not pipe untrusted shell commands. `--text`
and `--stdin` are mutually exclusive. For text beginning with `-`, use `--text='-example'`.

The buffer survives subsequent CLI processes and restarts in the same configured database.
There is no local length limit. The existing future-submission length setting does **not**
restrict drafts. Character counts are Python Unicode **code points**: a joined emoji or combining
sequence can have multiple code points despite appearing as one glyph.

Input normalization trims outer whitespace and converts CRLF/CR to LF. Interior spaces, tabs,
blank lines, Unicode, bidirectional marks and emoji joiners are retained. C0/C1 controls (other
than LF/TAB) and invalid surrogates are rejected. Text is normalized **on entry**, not during
preview. Shell quoting/encoding happens before FloChat receives text; `--json` preview exposes
the stored string unambiguously. There is no undo buffer; save drafts before replacing text.

### Saved drafts

```sh
flochat drafts save --title 'Giveaway entry'
flochat drafts list
# Copy the full ID printed by save/list, replacing DRAFT_ID below:
flochat drafts open DRAFT_ID --replace
flochat comment edit --text 'Updated local draft text'
flochat drafts save
flochat drafts rename DRAFT_ID 'Updated title'
flochat drafts delete DRAFT_ID --yes
```

Saving an unassociated buffer creates a draft with a UUID, title (default `Untitled draft`),
text, optional generated username snapshot and UTC creation/update timestamps. Saving an opened
or already saved buffer updates **that same ID** and preserves creation time. To create a second
draft, use `comment new --text '...' --replace`, then save. Duplicate titles are allowed: full
IDs disambiguate drafts. Empty text or explicitly empty titles fail without changing data.
Opening copies the exact saved text into the editor. Editing is `open → comment edit → save`.

Deleting a draft retains any currently open text as **unsaved**, with no draft association.
It does not delete other drafts, the profile, or event metadata. Missing IDs are errors, not
false successful deletes. No operation auto-saves, syncs, or submits.

### Preview

`flochat comment preview` displays the complete stored text, optional username snapshot,
character count, local validation problems, saved/unsaved flag, associated draft ID and
`submitted: False`. It says **"This comment has not been submitted."** A valid preview is not
YouTube acceptance, approval, or a successful post. Invalid/empty preview still displays its
problems but exits 1. Preview records a metadata event and does **not** mutate the buffer.
`comment show` inspects the same buffer without adding a history event.

### Local history and deletion

```sh
flochat history list
flochat history list --limit 100
flochat history clear --yes
```

Events include `comment_prepared`, `comment_edited`, `editor_cleared`, `draft_created`,
`draft_edited`, `draft_renamed`, `draft_opened`, `draft_deleted`, and `comment_previewed`.
Each has a UUID, associated draft ID when available, UTC timestamp and character count. Newest
first, default 50, allowed limit 1–1000; use the larger limit for older retained events. No
submission, approval or "posted" event is generated. Profile changes do not retain old usernames
in history. IDs of deleted drafts intentionally remain as historical references, not live FKs.

History is metadata-only: **no copies of text, titles or usernames**. It still reveals timing
and text lengths, so clear it when unwanted. Clear requires `--yes`, reports the deleted count,
and leaves the editor, profile, drafts and original future-integration table untouched.
To remove a particular comment's stored text, delete its draft and clear the editor if it is
open. Delete the profile separately if desired. No command deletes unrelated files. Logical
SQLite deletion is **not a promise of forensic erasure** from pages, journals, backups or disk.

### Database behavior

One configured SQLite file, not a second storage system:

| Table | Purpose / constraints |
| --- | --- |
| `username_profile` | Singleton ID 1; nonempty name, update timestamp |
| `editor` | Singleton ID 1; text, username snapshot, draft FK (`ON DELETE SET NULL`), update time |
| `drafts` | UUID primary key, nonempty title/text, optional username, creation/update times |
| `local_history` | UUID primary key, constrained local event type, optional historical draft ID, UTC time, nonnegative count |
| `comment_history` | Unchanged original table, retained for future integration; no current writes |
| `youtube_selection` | Schema 3: explicit video/chat target, account-channel binding, title and checked-at time; not proof of ongoing access |
| `youtube_usage` | Schema 3: UTC day, operation, logical request-attempt count; no credential or content values |

Each operation uses parameterized values and `BEGIN IMMEDIATE`. Related draft/editor/event
writes commit together; failed writes roll back before success can be returned. Schema creation
and migration are atomic, compatibility is checked before writes, and connections close after
each controller operation. A missing file is initialized automatically. Concurrent writes are
serialized, with SQLite's five-second lock timeout producing a clear storage error if necessary.

New database files request owner-only mode `0600`, new data directories `0700` on POSIX. Existing
file permissions are not silently changed; Windows ACLs are inherited (no claim of POSIX modes
on Windows). Files are **not encrypted**. Keep the data directory private and use device/disk
encryption where needed. Diagnostics show schema health, not usernames or comment contents.
Text printed by explicit editor/draft/preview actions is intentional; no content is logged.
Be aware `--text` arguments may remain in your shell history/process list; prefer `--stdin`
for sensitive text. SQLite journals/WAL/SHM files are git-ignored alongside the database.

### Local CLI reference

| Command | Purpose |
| --- | --- |
| `username set NAME` | Create/update the one local profile |
| `username show` | Show it or a useful empty-state message |
| `username delete --yes` | Confirm profile deletion only |
| `comment new (--text TEXT \| --stdin) [--replace]` | Start a separate comment |
| `comment edit (--text TEXT \| --stdin)` | Replace buffer text, keeping its draft ID |
| `comment show` | Inspect buffer without a history event |
| `comment clear --yes` | Clear the editor only |
| `comment generate [--template intro\|hello\|entry] [--replace]` | Explicit username-based preparation |
| `comment preview` | Exact local preview and metadata event |
| `drafts list` | IDs, titles, counts, creation/update times |
| `drafts save [--title TITLE]` | Save/update the buffer's draft |
| `drafts open ID [--replace]` | Load saved text into editor |
| `drafts rename ID TITLE` | Rename one saved draft |
| `drafts delete ID --yes` | Delete one draft; detach open text |
| `history list [--limit N]` | Newest local events, not submissions |
| `history clear --yes` | Delete only local event metadata |

### Local error handling

Validation errors, missing profile/draft, declined confirmation, refused replacement, storage
failure and invalid history limits exit **1** with actionable messages. Unknown commands, missing
required CLI arguments and invalid choices exit **2**. Existing configuration/environment and
unsupported-platform exit codes are unchanged. No destructive operation prompts or blocks a
script: absence of `--yes` is a refusal and explains how to explicitly confirm. There is no
partial success payload if a transaction fails.

For corrupt/incompatible files, back up the database and use a matching build; do **not** delete
it merely to silence the error. A version-3 database cannot be opened by Phase 02/03 code; after
migration, downgrading requires your pre-upgrade backup. Strict schema checks reject manual
customizations rather than guessing how to repair them. A locked or unwritable file needs its
permissions, owner, disk space, or locking process addressed; `doctor` reports storage problems.

---

## Phase 03 Verification Results

**Executed on Linux x86_64, Python 3.11.2 / SQLite 3.40.1.** These are actual checks of this
implementation, not a proposed test plan. Run from an installed clone:

```sh
.venv/bin/python scripts/verify_comments.py
.venv/bin/python scripts/check_repository.py
.venv/bin/ruff check .
.venv/bin/ruff format --check .
```

Windows equivalents use `.venv\Scripts\python.exe` / `ruff.exe`; those invocations are
**NOT EXECUTED** in this environment. Ruff is an optional development dependency, not installed
by the normal installer. The verification script uses stdlib checks with labeled assertions,
creates temporary storage, invokes real CLI subprocesses and cleans its own temporary tree.
It never uses your configured database or calls the network. There is no `tests/` folder.

| Area | Executed result |
| --- | --- |
| Executable verification suite | **PASS — 140 checks**, zero failures |
| Username | Create/read/update/delete, trimming, Unicode/ordinary names, singleton, invalid/missing name and deletion confirmation |
| Editor | New/edit/clear, replacement refusal, blank/control rejection, Unicode joiner and blank-line preservation, exact counts, >200-character editing |
| Generation | Explicit template action, snapshot, profile changes do not rewrite text, arbitrary editing clears stale username association, missing-profile refusal |
| Drafts | Multiple unique IDs, save/update/open/rename/delete, creation time retained, empty/missing IDs rejected, separate-process/reopen persistence |
| Preview | Exact content/count/validity, saved and dirty states, no mutation, explicit `submitted: false`, empty preview exit 1 |
| History | Local event types, unique IDs, timezone-aware timestamps, limits, retrieval and confirmed clear; no text/username snapshots |
| SQLite | Fresh initialization and repeated initialization, version-1 additive migration with legacy row preserved |
| Failure handling | Corrupt bytes, future version, unversioned unrelated tables, partial migration and altered constraints fail with original file bytes unchanged |
| Atomicity | Injected abort on history insertion **after** draft/editor writes: error surfaced and both earlier writes rolled back |
| Privacy/offline | In-process manager operations run with socket construction and `submit` patched to fail if called; diagnostics checked not to reveal stored profile/text |
| Real permission failure | Initialization under an unwritable directory refused on this non-root POSIX host |
| UTF-8 | Real CLI stdin input preserves Unicode/multiline text; invalid UTF-8 refuses cleanly |
| Existing CLI | All ten Phase 02 actions executed successfully; `--help` / `--version` executed; invalid usage rejected |
| Existing safety | Truthy non-booleans refused as consent; approved requests still raise unimplemented; no API requests or adapter implementation claims |
| Existing settings/doctor | Healthy runs, bad-config settings exit 2 while doctor still runs and reports problems; missing dependency exits 4 without traceback |
| Exit codes | 0/1/2/3/4 all exercised (including persistent mode exit 3) |
| AST guard | **PASS**, 218 definitions scanned, no reported unreferenced public definitions; genuinely unused injected definition detected in a disposable copy |
| Repository/security guard | **Clean**, required files, syntax, credential patterns, extra Markdown/folder and placeholder checks pass |
| Ruff | Lint **PASS**, format **PASS** (19 Python files) |
| Shell syntax | `bash -n` and `dash -n` pass on `install.sh`, `start.sh`, `scripts/install_lib.sh` |
| PowerShell syntax | Both scripts parsed with tree-sitter PowerShell grammar; **not** a PowerShell runtime test |
| Linux installer regression | Fresh full working-tree copy: install exit 0, repeat install reuses venv, launcher + doctor + profile/generate/save/preview workflow exit 0 |

The guard's name-based AST analysis is a useful heuristic, **not a whole-program proof**; private
helper reachability and command paths were also inspected and exercised. It was not weakened,
and no entry-point exemptions were added. Only the required-file list gained the actual
verification script. The separate `doctor` action-list check now checks nested leaf actions,
not merely top-level command names.

### Execution ceiling

| Platform | Phase 03 evidence | Runtime status |
| --- | --- | --- |
| Linux | Local suite, real CLI restarts, migration/rollback, install/repeat/launch | **EXECUTED**, checks above passed |
| Android/Termux | Shared Python/shell implementation inspected; Phase 02 detection simulation remains historical evidence | **NOT EXECUTED** on a device; not fully verified |
| macOS | Shared Python/shell implementation inspected, shell syntax checked | **STATIC-ONLY; NOT EXECUTED** |
| Windows | Shared Python inspected, PowerShell grammar parsed | **STATIC-ONLY; NOT EXECUTED** |

No GUI, account, OAuth, YouTube API, submission, overlay, background engine, cross-platform
runtime campaign, or release verification was attempted. The applicable Phase 01/02 contracts
were rechecked in the new executable suite; the historical ad-hoc 31/46-assertion suites were
**not** relabeled as rerun. Historical installer failure-path results remain historical, not
new Phase 03 executions. Concurrent writers use SQLite transactions, but a multi-process stress
test and power-loss/disk-full tests were **NOT EXECUTED**.

---

## Phase 03 Completion Report

### 1. Completion status

**Complete for the local terminal Comment Manager scope.** All five requested features work
without a YouTube account or network. Real runtime verification is Linux-only. Phase 04 has
not been started. Eight approved phase names/order remain unchanged.

### 2. Audit and preservation

Before implementation, inspected the dirty Git status, source tree, root README, argparse
registration, controller/config/settings/doctor, version-1 SQLite schema/initializer,
`SubmissionRequest`/`submit`, AST guard, dependency configuration and installation scripts.
Phase 02's uncommitted files were present and retained. No reset, checkout, clean, commit, push,
PR, publishing or visibility operation was performed.

Smallest-change plan: extend the existing `comments.py` / `database.py`, dispatch via the
existing controller/CLI, update roadmap/diagnostics and sole README, and retain one useful
executable verification script. No new runtime source module or database file was added to Git.

### 3. Username management

One local profile, create/update through `set`, read/show, confirmed delete, trimming and clear
validation. No duplicate active profiles, no YouTube format enforcement or identity verification.

### 4. Editor

Persistent local buffer with explicit new/edit/clear/show, UTF-8 stdin, Unicode code-point count,
validation and replacement protection. Not a simulated GUI. No artificial local length limit.
Normalization was deliberately corrected from Phase 01's whitespace/joiner stripping to preserve
intentional formatting and exact preview text; the submission dataclass and approval contract
are unchanged, and the submission boundary still refuses every request.

### 5. Drafts

Multiple persistent UUID drafts, titles, full text and timestamps. Save creates or updates the
open draft; open/edit/save modifies it; rename and confirmed deletion work. Deletion detaches
open text as unsaved, not a silent loss of the editor. No synchronization or submission.

### 6. Preview

Exact stored text, optional generated username snapshot, character count, local validation,
saved/unsaved flag, draft ID and explicit not-submitted status. Rendering does not mutate text;
only metadata history is appended. Local validity is not YouTube acceptance.

### 7. Local history

Nine meaningful local event types with UUID, optional draft ID, UTC timestamp and count.
Retrieval is newest-first with configurable limit; confirmed clear deletes only these events.
No duplicate text snapshots or fabricated submission records. No per-event deletion/undo UI.

### 8. Database changes

Schema 2 adds four local tables to the same configured file and retains the original integration
table unchanged. Atomic additive migration, strict recognized schema/integrity checks,
parameterized values, foreign-key detach semantics and transaction rollback. New POSIX files
request private permissions; encryption and forensic secure deletion are not claimed.
The small reference database used during structural comparison exists only in memory, contains
no user data and is closed immediately; it is not a second user-data storage system.

### 9. CLI changes

Four groups / 16 local actions added, for 13 top-level commands / 26 total actions. Existing
commands, argparse, read-only settings, JSON option placement and exit conventions preserved.
`doctor` checks nested command actions and migrated storage without displaying comment content.
`version` and status report Phase 03 through the existing single roadmap source.

### 10. Files created

**Only `scripts/verify_comments.py`**: real repeatable stdlib verification, not a placeholder or
a folder added for appearances. Temporary fixtures and install copies live outside the repo.
No dependency was added; SQLite, UUID, timestamps, stdin and verification use the standard library.

### 11. Files modified in Phase 03

* `src/flochat/comments.py` — real local manager and formatting-preserving validation.
* `src/flochat/database.py` — additive schema, compatibility checks, transactions, private creation.
* `src/flochat/cli.py` — local command registration, stdin input and dispatch/output.
* `src/flochat/controller.py` — configured local manager entry point.
* `src/flochat/roadmap.py` — Phase 03 label/status and 16 action declarations; defer only later work.
* `src/flochat/doctor.py` — complete nested command-surface comparison, current safety wording.
* `src/flochat/platform.py` — accurate terminal/local-manager description.
* `scripts/check_repository.py` — require the verification script; AST implementation unchanged.
* `scripts/install_lib.sh`, `install.ps1` — current capability summary only; install logic reused.
* `.gitignore` — SQLite journal/WAL/SHM exclusions.
* `pyproject.toml` — accurate dependency-policy comment; dependency requirements unchanged.
* `README.md` — usage, current inventory/model, privacy, error behavior, verification and report.

Other dirty files shown by Git are preserved Phase 02 work. The inventory above describes this
phase's changes, not a claim that Phase 02 files are already committed.

### 12. Verification and actual results

**140 executed checks pass**, plus clean lint/format, guard and shell syntax. Linux installation
and repeat/launch workflow pass in a fresh copy. PowerShell grammar parsing passes, not runtime.
See the preceding verification table for exact coverage, failure injection and execution limits.

### 13. Phase 01 / Phase 02 regressions

Existing CLI actions, settings/doctor, configuration-error recovery, installation/reuse,
state/exit mapping, unconfirmed-success rule, manual lifecycle, deferred recovery, dependency
failure and the approval/refusal boundary are rechecked. Zero API requests; no native feature
claims. Intentional Phase 03 text-normalization/local-length changes are documented, not hidden
as unchanged Phase 01 validation behavior.

### 14. Dead-code audit

Repository AST guard passes (218 definitions); no exemptions or relaxed detection. Disposable
orphan injection is detected as a real failure. New local operations and their helpers have
registered/used paths, and are exercised by the repeatable script. No speculative interfaces,
unused config values, feature flags, duplicate persistence systems or dummy adapters added.

### 15. Security and privacy

All values parameterized, related writes atomic, no credentials/OAuth tokens/analytics/cloud
or network client introduced. Local operations never invoke submission. History contains no
content snapshots. Diagnostics and errors do not dump comment contents. Deletion is scoped,
explicit and logical; shell history, OS ACLs, backups and disk encryption remain user concerns.
Credential/repository scans pass. Existing secret exclusions and safety guard are preserved.

### 16. Known limitations

Terminal buffer replacement, no graphical/full-screen editor or undo. One local profile, not
multiple accounts. Character counts are code points, not graphemes. History stores metadata,
not text restoration; up to 1000 newest events can be retrieved per call, without cursor paging.
No automated history retention policy. No local encryption or guaranteed physical erasure.
Strictly recognized schemas only; back up before upgrade, especially before downgrading.
Windows/macOS/real Termux runtime tests and multi-process stress/power-loss tests remain unrun.

### 17. Pending work

No known blocker to the Linux-tested local scope. Real cross-platform verification remains
Phase 07. OAuth/API integration is Phase 04; approval UI/duplicate/cooldown workflows Phase 05;
overlays/background engine Phase 06; licensing/release Phase 08. No later phase was implemented.
A licence is still unselected and required before release.

### 18. Repository discipline and owner review

No `docs/`, `documentation/`, `reports/`, `examples/`, `tests/`, additional README, separate
Markdown guide, placeholder, empty directory, extra configuration or unused module created.
Only the purposeful verification script is new to Phase 03. Generated caches/package metadata
remain ignored, not deliverables. All documentation remains here. **All Phase 02 and Phase 03
changes remain uncommitted and unpushed** on the existing working branch for owner review.

---

## Google OAuth and YouTube Setup

**Implementation is present; live OAuth/API success is NOT VERIFIED.** This environment cannot
reach Google OAuth/YouTube hosts, has no authorized client configuration supplied, and its real
keyring probe selected the unavailable/fail backend. Mocked success below is not live evidence.
Do not put credentials in chat, source code, Git, a draft, or the SQLite database.

### Google Cloud configuration

The owner must configure their own project; FloChat does not create one:

1. In Google Cloud Console, choose/create your project and enable **YouTube Data API v3**.
2. Configure Google Auth Platform/OAuth consent with the appropriate audience and authorized
   test users. Follow Google's testing, production verification and scope policies; testing
   authorizations can expire. Do not bypass the consent screen or Google's restrictions.
3. Create an OAuth client of type **Desktop app**, not Web application, Android client, API key,
   service account or password. Download its JSON **outside the FloChat clone**. Restrict access
   to your OS user (for example `chmod 600 /absolute/private/client_secret.json` on POSIX).
4. FloChat defaults to `https://www.googleapis.com/auth/youtube.readonly`. Only explicit
   `--allow-posting` new consent requests `youtube.force-ssl`; no Gmail, contacts, OpenID or
   email scopes are requested. A Google login/channel does not guarantee chat
   access. Choose the intended Google/Brand account in Google's own consent UI.
5. Prepare an unlocked, supported OS keyring and run the CLI/browser on the **same desktop**.
   There is no password prompt implemented by FloChat and no manual authorization-code paste.

The downloaded configuration must contain `installed`, a nonempty client ID ending in
`.apps.googleusercontent.com`, a nonempty client secret, Google's standard authorization URI
`https://accounts.google.com/o/oauth2/auth` and token URI `https://oauth2.googleapis.com/token`.
Web-client files, malformed JSON, missing fields, non-Google endpoints and files inside the
clone (including symlinks resolving there) are rejected without echoing their values.
The desktop client's bundled secret is not a user password; protect the file nevertheless.

Set the **absolute path**, not its contents:

```sh
# Linux/macOS desktop shell, from the installed clone
export FLOCHAT_CLIENT_SECRET='/absolute/private/client_secret.json'
unset FLOCHAT_TOKEN_FILE
./start.sh youtube connect --local-browser
./start.sh youtube account
```

```powershell
# Windows PowerShell; runtime NOT EXECUTED here
$env:FLOCHAT_CLIENT_SECRET = 'C:\absolute\private\client_secret.json'
Remove-Item Env:FLOCHAT_TOKEN_FILE -ErrorAction SilentlyContinue
.\start.ps1 youtube connect --local-browser
.\start.ps1 youtube account
```

`.env.example` documents these names but `.env` is **not auto-loaded**. Export variables in the
shell. A credential value must never be placed in `config.json`; its path can be supplied by the
existing environment mechanism. Existing local drafts and settings do not require OAuth setup.
Updating an old clone requires rerunning the installer to install Phase 04 dependencies.

### OAuth behavior and platform limits

The official Google `InstalledAppFlow` handles authorization code exchange, CSRF state and
PKCE (`autogenerate_code_verifier=True`). Its callback listens **only on `127.0.0.1`**, on a free
ephemeral port; this is intentionally not a publicly reachable preview server. Desktop installed
clients support the loopback pattern; no fixed public callback, OOB redirect, OAuth restriction
workaround, browser-cookie extraction or browser automation is provided.

`--local-browser` is an explicit acknowledgment that the CLI and browser are on the same desktop.
The browser opens Google's official consent UI. Authorization URLs, state, codes, token bodies,
refresh tokens and secrets are not printed. Browser failure, denial, callback/state failure,
Ctrl-C and callback timeout fail clearly with no connected success. The callback wait is bounded
at 180 seconds, and token exchange at 20 seconds. The browser callback page only says to return
to FloChat; it does **not** claim that keyring storage or account verification succeeded.

Only after a valid readonly grant, a refresh token, a successful official channel lookup, and
successful keyring storage does `connect` report connected. An existing stored grant is not
silently overwritten: use `account` to verify it, or disconnect before changing accounts.
If a grant was created at Google but account verification/keyring saving fails, no local
connection is claimed. Review/remove that grant in Google's account permissions if unwanted.
Closing the browser without returning is treated as cancellation after the bounded wait.

| Environment | Current behavior | Verification |
| --- | --- | --- |
| Linux desktop | Requires working/unlocked Secret Service (D-Bus service + keyring) and local browser | Core mocked; headless sandbox has **no usable keyring**, live OAuth blocked |
| Windows desktop | Requires Windows Credential Vault through keyring and local browser | Code/static checks only; **NOT EXECUTED** |
| macOS desktop | Requires Keychain through keyring and local browser | Code/static checks only; **NOT EXECUTED** |
| Android/Termux | Desktop installed-app loopback login deliberately rejected; no Android Keystore companion exists | Limitation implemented; no device/runtime test |
| SSH, remote container, Arena/browser preview | No supported remote OAuth callback workflow; do not use `--local-browser` to misrepresent a remote browser as local | No remote workaround or forwarding of authorization codes |

Once a supported desktop has a valid stored grant, reads/refresh do not depend on a YouTube app
or tab being visible. This means an explicit foreground CLI command can use the official API;
it is **not** a background service, overlay, guarantee of persistence or proof of live success.

### Credential storage and disconnection

`CredentialStore` accepts only these backend identities:

* `keyring.backends.SecretService.Keyring`
* `keyring.backends.Windows.WinVaultKeyring`
* `keyring.backends.macOS.Keyring`

Plaintext/alternate-file, null/fail, and Chainer backends are refused, even if a chain happens
to contain a secure member. Configure/unlock the appropriate OS service, rather than allowing
a silent fallback. If keyring chooses a chain on an otherwise suitable desktop, choose the
approved backend explicitly using keyring's own configuration, e.g. on Linux:
`export PYTHON_KEYRING_BACKEND=keyring.backends.SecretService.Keyring`. This does not install a
service or unlock it. Never choose a plaintext backend merely to pass a check.

Credentials are one entry per OS user: service `FloChat.YouTubeOAuth`, account `default`.
Different FloChat clones/data directories share that authorization. Secrets remain in the
selected OS store, not SQLite, `.env`, logs or an ordinary token JSON file. Stored token URIs
and scopes are validated before use. Encryption/availability depends on the OS service; real
Keychain/Vault/Secret Service operations were not verified here. `FLOCHAT_TOKEN_FILE` is rejected
for authentication; existing files are left untouched for owner-managed cleanup.

```sh
./start.sh youtube disconnect --yes
# Optional explicit network revocation in addition to local cleanup:
./start.sh youtube disconnect --yes --revoke
```

Local disconnect clears the selected target in the configured database and removes FloChat's
keyring entry. It does not delete usernames, editor text, drafts, history, client JSON or other
keyring entries. If the keyring is locked/unavailable or deletion fails, the command **fails**;
it does not claim credentials were removed. Unlock/reconfigure the original backend and retry.
Other clones' stored selection metadata is not automatically erased, but their shared grant is
removed; those targets are never evidence of ongoing authorization.

Without `--revoke`, Google's grant is **not claimed revoked**. With it, FloChat makes one explicit
HTTPS form POST to Google's official revocation endpoint, then attempts local deletion even if
revocation fails. Only HTTP 200 sets `google_revocation_confirmed: true`. Failure reports an
unconfirmed revocation, exits 1, and still reports local cleanup if it succeeded. For malformed
credentials, use local-only disconnect; inspect Google account permissions manually. Failure to
clear local database selection can also prevent completion—fix storage before retrying.

### YouTube CLI reference

Activate the venv for `flochat`, or use the existing platform launch script. Put `--json` before
the group. Bare `youtube` is a usage error, not an implicit network operation.

| Command | Real operation / behavior |
| --- | --- |
| `youtube status` | Local keyring presence/expiry, stored selection and recent usage; no network, may request OS keyring unlock |
| `youtube connect --local-browser` | Explicit desktop consent + channel verification + secure save |
| `youtube disconnect --yes [--revoke]` | Clear configured selection and remove local grant; optional Google revocation |
| `youtube account` | Authorized `channels.list(part=snippet,mine=true)`; display channel IDs/titles, not email or tokens |
| `youtube streams [--page-token TOKEN]` | Authorized `liveBroadcasts.list(part=snippet,status,mine=true,broadcastType=all,maxResults=50)`; one page, no polling |
| `youtube inspect VIDEO_ID` | Authorized `videos.list(part=snippet,liveStreamingDetails,id=VIDEO_ID)` for an explicitly identified accessible video |
| `youtube select VIDEO_ID` | Fresh video/chat lookup + account lookup, then persist the explicit active target; never posts |

There is no redundant `chats` alias or unsupported `select CHAT_ID`: the caller explicitly
identifies the **video ID**, and the API supplies the chat ID. Copy the video ID reported by
`streams`, or supply a known video ID to `inspect`. Do not supply a full URL. Public/otherwise
accessible videos may be inspected only to the extent the authorized official API permits;
no private-content bypass is attempted. Empty result and denial are distinguishable.

`streams` reports title, video ID, lifecycle, live-chat ID when present, availability,
`active_chat_count` and a next-page token. Ended/pending/chatless broadcasts remain visibly
marked, never misrepresented as active eligible targets. Use the returned token explicitly to
retrieve another page; no hidden page-walking or arbitrary first-stream selection occurs.

`inspect` distinguishes `live_chat_available`, `live_chat_unavailable`, `stream_ended` and missing
or inaccessible video. Successful selection requires an actual start time, no actual end time,
and an `activeLiveChatId`. It also binds selection metadata to the authenticated channel ID.
Ambiguous multiple-channel authorization is refused for selection; reconnect with the intended
Google/Brand account. A failed explicit selection clears its previous target once credentials
have loaded. Inspect/list/connect do not select anything automatically.

A stored selection has video ID, live-chat ID, title, account-channel ID and verification time.
It is **a snapshot**, not a guarantee of ongoing chat availability or permission to post. Phase 05
must revalidate target, identity, text and current per-comment approval before any future write.
No local username/draft text is included in these requests or automatically prepared on login.

### Authorization and error states

`youtube status` deliberately does **not** call a stored grant "connected" without contacting
Google. It reports `not_connected`, `stored_unverified`, `authorization_expired`, or an actionable
authorization/storage error. `youtube account` reports `connected` only after a current response.
Disconnect reports `disconnected`; revoked/invalid grants, access denial and temporary failures
are distinct error codes/states. Invalid-grant responses can mean revoked **or** expired access;
FloChat does not falsely infer which one Google meant. Reconnect after reviewing access.

| Code / case | Outcome |
| --- | --- |
| Missing/invalid client configuration | Clear configuration error before consent; no values echoed |
| Missing stored authorization | `authorization_required`; connect explicitly |
| Expired access token | Bounded official refresh, then save rotated credentials in keyring |
| Expired grant without refresh | `authorization_expired`; no connection claim |
| Invalid/revoked/expired refresh grant or HTTP 401 | `authorization_invalid`; selection invalidated, reconnect required |
| Consent denial / insufficient permission / HTTP 403 | `permission_denied` with consent/project/access guidance |
| Callback cancellation/timeout/state mismatch | Cancelled or invalid authorization; no local successful grant |
| No associated YouTube channel | `account_missing`; review Google/Brand account |
| Missing/inaccessible video / HTTP 404 | `not_found`, not a fabricated ID |
| Closed/disabled live chat / ended stream | `chat_unavailable` / `stream_ended` |
| Invalid arguments / HTTP 400 | `invalid_request` |
| Quota/rate-limit reasons / HTTP 429 | `quota_exceeded` / `rate_limited`; stop/wait/check console |
| HTTP 5xx | Temporary `server` failure |
| Network timeout/interruption | Temporary `timeout` / `network` failure |
| Invalid JSON, missing/wrong fields or malformed response | `invalid_response`; no success/selection |
| Locked/unsupported storage or failed secret write/delete | `secure_storage`; no plaintext fallback or false cleanup claim |

Errors use existing application states and their exit mapping: ordinary integration failures
exit 1; missing/denied required permission exits 3. CLI usage errors remain 2 and dependency
failures 4. Existing exit behavior is preserved. Errors
include a safe code and temporary/permanent flag, never raw response text, headers, authorization codes,
client secrets, access/refresh tokens or full exception strings. Ctrl-C reports cancellation.
Third-party debug logging is temporarily suppressed during sensitive operations and restored;
FloChat's own errors do not log secret payloads.

### Quota, requests and timeouts

No unlimited-request or fixed daily-budget promise. FloChat does **not** invent quota-unit
costs or remaining allowance. Google Cloud's quota console is authoritative for the project.
A UTC-day ledger records logical attempts by operation (`channels.list`, `liveBroadcasts.list`,
`videos.list`, `oauth.refresh`, `oauth.revoke`) before outbound work. Failed attempts count too;
OAuth entries are not YouTube quota units. UTC buckets are not Google's quota reset schedule.
The local status shows the 100 newest day/operation rows; it is not project-wide accounting
across clients/clones. `requests_sent: 0` in local status means that local status performed no
HTTP requests, not that the stored usage ledger is empty.

There is **no automatic polling, API retry loop or write retry**. Listing fetches at most one
50-result page. A valid token is reused; refresh happens only when needed, at most one transport
attempt per refresh operation. Every token/API/revocation HTTP exchange has a 20-second requests
timeout and redirects disabled. This is a transport connect/read timeout, not a hard global
wall-clock SLA. TLS verification remains enabled; environment `.netrc` and proxy injection are
disabled for credential-bearing sessions. Corporate proxy-only networks may need an approved
future configuration; do not disable TLS to bypass failures. Retry only explicitly and sensibly,
not through aggressive shell loops. Quota/rate errors never trigger automatic reconnect/posting.

There is no cross-command account/profile response cache that could be mistaken for current
verification. Local selection is reused only as unverified display metadata. This keeps the
number of requests small without presenting stale data as live authorization or chat status.

### Phase 04 dependencies

| Added constraint | Actual purpose |
| --- | --- |
| `google-auth>=2.38,<3` | Official credentials representation and token refresh transport |
| `google-auth-oauthlib>=1.2,<2` | Google's installed-app PKCE/consent/loopback flow |
| `requests>=2.32.4,<3` | Small fixed-endpoint official REST client with timeouts, no redirects/retries |
| `keyring>=25.6,<26` | Approved OS credential-store access; fail closed if unavailable |

`pydantic>=2.6,<3` remains for configuration. Runtime/dev dependencies stay separate. Installers
still install the one project into its isolated venv and install no extra package manager or
privileged OS software. Google/keyring dependencies include platform-specific/transitive crypto
and Secret Service support: Linux wheels installed here, but Termux/source builds and other
platform installers are **not runtime verified**. No discovery client, browser automation,
Google API key, service account, web server framework, or template engine dependency was added.
`doctor` and the early dependency guard now check all five direct requirements, including their
upper bounds. `doctor` checks optional OAuth client/backend setup without unlocking tokens or
using network; a missing optional setup is `skip`, not a fabricated successful connection.

### Official interface references

The following first-party sources guided endpoint/scope/callback selection (not a live API test):

* [Google's YouTube v3 discovery document](https://github.com/googleapis/google-api-python-client/blob/main/googleapiclient/discovery_cache/documents/youtube.v3.json), retrieved from Google's repository; blob `59c7c6f610cde5e31ef4f0f57beb003ea9d2d18b`, revision `20261019`. Requests use its `https://youtube.googleapis.com/youtube/v3/` root/path combination.
* [Google's installed-app flow source](https://github.com/googleapis/google-cloud-python/blob/main/packages/google-auth-oauthlib/google_auth_oauthlib/flow.py), inspected along with the installed official library; retrieved blob `4e006c2655071087e32a980dfd7e36ed504768da`.
* [Installed-app OAuth guidance](https://developers.google.com/identity/protocols/oauth2/native-app).
* [Channels list](https://developers.google.com/youtube/v3/docs/channels/list), [broadcasts list](https://developers.google.com/youtube/v3/live/docs/liveBroadcasts/list), [videos list](https://developers.google.com/youtube/v3/docs/videos/list).
* [Quota guidance](https://developers.google.com/youtube/v3/getting-started#quota) and [revocation](https://developers.google.com/identity/protocols/oauth2/web-server#tokenrevoke).

The developer-documentation hosts are not reachable from this sandbox. No current numeric quota
cost/reset assumption is embedded in code; use the official docs and your Cloud console when
configuring a real project. The known `liveChatMessages.insert` operation requires a writing
scope, which this phase deliberately does not request or implement.

---

## Phase 04 Verification Results

Executed in a Linux x86_64 sandbox, Python 3.11.2, SQLite 3.40.1. **No real OAuth consent,
callback exchange, token refresh, revocation, channel lookup, stream discovery or live-chat
selection was verified against Google/YouTube.** No real comment was sent.

```sh
.venv/bin/python scripts/verify_youtube.py
.venv/bin/python scripts/verify_comments.py
.venv/bin/python scripts/check_repository.py
.venv/bin/ruff check .
.venv/bin/ruff format --check .
```

`verify_youtube.py` uses synthetic fixture identifiers and mocks approved keyring/OAuth/HTTP
behavior. Socket creation is blocked in that suite; unexpected network calls or YouTube writes
fail the harness. The only mocked POST allowed for specific checks is Google's OAuth revocation,
not `liveChatMessages.insert`. Local SQLite transactions, real CLI parsing/rendering and files
are executed normally in temporary storage. No real OS keyring entry is modified by tests.

| Verification | Result and evidence level |
| --- | --- |
| Integration harness | **307 executed checks**, all passed; external OAuth/API/keyring outcomes **MOCKED** |
| OAuth setup | Missing, malformed/wrong-type client data and non-Google configuration rejected; validated fixture accepted |
| Consent/callback | Mock success, PKCE flag, loopback/ephemeral binding, wait limit, cancellation, timeout, denial, invalid client and state-mismatch failures |
| Platform safeguards | Desktop acknowledgment required; simulated Android callback refused; secure backend failure before consent |
| Credentials | Synthetic secure-store round trip, corrupt payload refusal, expired state, mock refresh rotation/revoked grant, save/delete failures and safe redaction |
| Token transport | Token exchange timeout/no redirects verified; refresh retry attempt blocked after first transport call |
| Accounts | Mock connected channel summary, missing channel, invalid response and API failure |
| Broadcasts/chats | Mock available, pending/ended, empty page, explicit pagination, missing/inaccessible video, bad JSON/fields, selection and no auto-selection |
| Errors/quota | Mock 400/401/403/404/429/503, quota/rate reasons, network interruption and timeout; attempt ledger checked against mock calls |
| Disconnect | Confirmation required; local cleanup distinct from mock Google revocation; failed revocation still attempts local deletion; false cleanup prevented on store error |
| Safety | Unapproved/empty/missing-chat requests blocked; approved request still refuses; no YouTube POST path used or available |
| Privacy | No fixture secrets in CLI errors/output, usage rows or SQLite dump; library logging suppression/restoration checked |
| Schema 2 → 3 | **EXECUTED** with existing username, draft, editor and history rows preserved; partial migration refusal leaves original bytes unchanged |
| Prior phases | `verify_comments.py`: **140 executed checks passed**, including legacy migration, all prior actions, settings, doctor, local CRUD/preview/history, exit codes and submission invariants |
| AST guard | **Clean**, 238 definitions scanned; no detection changes or exemptions. Prior-phase suite still detects a real orphan in a disposable tree |
| Repository/security guard | Required files, secret patterns, Python syntax, folder/Markdown/placeholder policy all clean |
| Ruff | Lint and format clean, 20 Python files |
| Shell syntax | All three shell files pass `bash -n` and `dash -n` |
| PowerShell syntax | Both scripts parsed with tree-sitter grammar; **STATIC-ONLY**, not PowerShell execution |
| Linux fresh install | **EXECUTED** in a full working-tree copy: isolated venv, all dependencies, version, 19-check doctor and local editor/draft smoke workflow pass |
| Linux repeat install | **EXECUTED**: venv safely reused; both verification scripts pass again inside the fresh installed copy |
| Real local keyring probe | **EXECUTED, BLOCKED**: `keyring.backends.fail.Keyring`; `youtube status` exits 1 with `secure_storage`, not connected success |
| Live Google/YouTube tests | **BLOCKED / NOT EXECUTED**: no supplied authorized client/grant, no usable secure backend and Google hosts excluded by sandbox network policy |
| Windows/macOS/real Termux | **NOT EXECUTED** at runtime. Code/PowerShell parsing is not cross-platform OAuth proof |

The count is executed assertions/transport checks, not 307 independent live integrations. No
mock is presented as an actual eligible broadcast/account. Full browser round trips, real OS
keyring encryption/unlock behavior, refresh-token expiry policy, real quota exhaustion and
real-service permissions remain unverified. No multi-process keyring/account switching stress
or crash-between-keyring/database operations test was run. A keyring and SQLite are not a
single distributed transaction; failure is surfaced, never asserted as a complete connection.

---

## Phase 04 Completion Report

### 1. Completion status

**Read-only implementation complete; live integration verification BLOCKED.** Five requested
areas have reachable implementation, controlled mocked coverage and honest failure paths.
This is not a claim that live OAuth/API integration or all-platform compatibility works. Posting
is deliberately disabled pending Phase 05; no Phase 05 implementation was started.

### 2. Audit and preservation

Audited dirty Git status/history, README, CLI/config/settings, schema-2 storage, Comment Manager,
submission/approval guard, error/states, AST guard, dependency policy and installers. The former
YouTube module was descriptive stubs, not a working authenticated client. Reused that module,
existing controller/config/error/SQLite architecture, rather than creating parallel systems.
All Phase 02/03 files and useful behavior were retained. HEAD remains `6f4fe83`; no commit,
reset, clean, branch switch, push, PR, release, visibility change or publishing was performed.

### 3. OAuth implementation

Official Google `InstalledAppFlow`, PKCE/state handling, validated Desktop client file outside
the clone, fixed Google endpoints, readonly scope, local-only callback and bounded exchanges.
Explicit `connect --local-browser`, cancellation/denial handling, secure save only after account
verification, reuse/refresh of an existing token. No passwords, cookies, OOB flow or workarounds.
Android and remote callback limitations fail explicitly rather than claiming compatibility.

### 4. Account connection

Available channel IDs/titles from official authorized `channels.list`. Current verification is
required to call an account connected; local stored authorization is marked unverified/expired.
No unnecessary profile cache. Confirmed local disconnect removes the FloChat keyring entry;
optional Google revocation is reported separately and truthfully.

### 5. Live Chat identification

Owned broadcast listing with explicit pagination and visible lifecycle/chat availability;
explicit video inspection through the official videos resource; active-chat selection bound to
the authorizing account channel and checked-at timestamp. No arbitrary first-stream selection,
fabricated IDs, scraping, private-content bypass, or implied ongoing access guarantee.

### 6. Official API operations

Read-only `channels.list`, `liveBroadcasts.list`, `videos.list`; official OAuth authorize/token
refresh/revocation as needed. The Google discovery document was inspected for resources/scopes.
`liveChatMessages.insert` is known but **not implemented or exposed**; readonly scope cannot
post. `submit(SubmissionRequest)` preserves validation/selected-chat/explicit-approval order
and still refuses after those checks, now explaining the Phase 05 safety dependency.

### 7. API error handling

Whitelisted safe codes/messages map authentication, expiry/revocation ambiguity, permission,
not-found, ended/chatless, invalid request/response, quota/rate, timeout, network and server
failures into existing app states. Raw credentials, headers, authorization codes, server bodies and exception
strings are not rendered. CLI emits safe code/temporary fields and cancellation without a
traceback. No failed API response is returned as a successful account/selection.

### 8. Quota management

Explicit foreground commands only; one page per listing, no automatic polling or API retries.
Daily UTC logical attempt counts, no guessed quota units or remaining-budget claim. Valid
authorization is reused; refresh and revocation are bounded. Quota and rate-limit failures halt
and require owner/user action rather than automatic loops, account cycling or circumvention.

### 9. Credential storage

OS keyring APIs only, strict allowed backend identities, no plaintext or chained fallback.
Fixed service namespace shared across clones, with explicit local deletion and optional
revocation. Legacy token-file option blocks authentication; files are never imported/deleted.
The real sandbox backend is unavailable, so no live storage success is claimed.

### 10. CLI additions and changes

Seven `youtube` actions: `status`, `connect`, `disconnect`, `account`, `streams`, `inspect`,
`select`. Total **14 top-level groups/commands, 33 actions**. Existing argparse and prior commands
remain. Doctor checks all five dependencies plus optional OAuth setup (19 checks on this host).
Default output stream is resolved at call time so CLI output/redaction can be reliably verified.

### 11. Files created

Only **`scripts/verify_youtube.py`**: purposeful repeatable mocked integration and real local
regression verification, not a placeholder. No new runtime module, test folder, configuration
system, credential JSON, database file or extra Markdown was added to Git.

### 12. Files modified in Phase 04

* `src/flochat/youtube.py`: replace former descriptive stubs with actual readonly integration,
  OAuth/keyring storage, safe failures and API usage/selection behavior.
* `src/flochat/database.py`: real additive schema 3, preserving schemas 1/2 data and compatibility checks.
* `src/flochat/controller.py`, `cli.py`: integration entry point, seven actions, sanitized error
  metadata, cancellation and runtime-resolved output stream.
* `src/flochat/dependencies.py`, `doctor.py`: all direct dependency bounds/metadata checked,
  actionable repair and optional client/backend diagnosis with no credential unlock/network.
* `src/flochat/roadmap.py`: Phase 04 implemented/live-blocked status; exact approved phases kept.
* `src/flochat/comments.py`: submission still blocked; missing-integration hint now points to
  pending Phase 05 safety review. No approval bypass or new submission contract.
* `src/flochat/settings.py`: client path guidance and explicit rejected legacy token-file option.
* `src/flochat/state.py`: permission description now covers API as well as OS permission.
* `src/flochat/__init__.py`, `lifecycle.py`: accurate current-scope descriptions, no stale claim
  that readonly API code is absent.
* `pyproject.toml`: four justified direct packages with upper/lower bounds; dev/runtime separation retained.
* `scripts/check_repository.py`: required-file entry only for this verification script; AST guard unchanged.
* `scripts/install_lib.sh`, `install.ps1`: summary wording reflects optional OAuth/read access;
  installation logic reused, no privileged steps added.
* `.env.example`: path-only OAuth guidance, no token-file fallback, explicit export behavior.
* `README.md`: single setup/usage/privacy/inventory/verification/completion record.

Other dirty files are preserved earlier-phase work, not independently committed changes.

### 13. Actual verification

Local schema migration, CLI parsing/output, installation/reuse, prior 140-check suite, code
quality, repository/secret guard and backend refusal were **executed**. Fresh Linux install
and both suites succeeded in the installed copy. Syntax/parsing results are identified above.

### 14. Mocked verification

**307 assertions/checks pass** in the Phase 04 script. Consent/token/account/broadcast/chat,
keyring success, revoked/expired grant, API quota/error and revocation outcomes are mocked.
They prove local behavior around those outcomes, **not real-service compatibility**.

### 15. Existing-phase regressions

Phase 01/02 commands, settings/doctor, states/exit codes, dependency failures and install/reuse;
Phase 03 profile/editor/drafts/preview/history and migrations; exact-True approval and refusal
remain covered by the executed existing suite. No draft or username is automatically transmitted,
prepared, selected or posted on connection/reconnection.

### 16. Dead-code audit

Guard clean over 238 definitions, no exemptions or weakened AST checks. New methods/commands
are genuinely reached; old unimplemented stubs were replaced, not kept as duplicate clients.
The existing verification suite again demonstrates detection of a real unreferenced definition.
As before, name-based AST reachability is a heuristic, not whole-program proof.

### 17. Security and privacy

Fixed HTTPS service endpoints, TLS verification, redirects disabled, bounded transport, no
API writes, no automatic retries, least requested scope, approved credential backends, safe
messages, no sensitive DB columns, parameterized metadata writes and no content telemetry.
Local comments stay local; only explicit authorized discovery/authentication parameters leave
the device. Keyring/selection across clones and local-vs-Google revocation distinctions are
fully documented, along with possible partial external-grant creation if secure save fails.

### 18. Live testing status

**BLOCKED / NOT EXECUTED.** No valid live OAuth client/grant was supplied, Google hosts are not
reachable under this sandbox's network policy, and the real OS store is unusable here. No real
Google Cloud project, consent, account, stream, chat, refresh or revoke operation is claimed.
Owner-authorized testing must happen on a supported local desktop with a real secure store.
Never paste secrets into chat or use real posting for automated tests.

### 19. Known limitations and pending work

Live consent/callback/API/keyring verification remains pending. Windows/macOS/real Termux
runtime testing is pending; Termux OAuth is intentionally unsupported, not simulated as working.
No browser-less/remote/OOB fallback, proxy configuration, account cache or background polling.
One authorization per OS user; multi-account switching requires disconnect/reconnect. Selection
is a staleable snapshot; Phase 05 must complete approval/safety and revalidate before any write.
Cross-platform stress, crash recovery and real quota behavior are not verified. License selection
remains required before Phase 08. No overlays/background, complete Safety Engine, payments,
cloud sync, or later-phase features were implemented.

### 20. Repository discipline and review

No `docs/`, `documentation/`, `reports/`, `examples/`, `tests/`, extra README/Markdown,
placeholder, empty directory, unused auth module, duplicate API/database/config system,
credential artifact or unrelated dependency was created. The only new file in this phase is
its real verification script. Temporary fixtures/install copies are outside the repository;
generated venv/cache metadata stays ignored. **All Phase 02/03/04 work remains uncommitted and
unpushed on the existing branch** for owner review. Nothing was published or released.

---

## Phase 05 Safety Engine

**Historical Phase 05 interface snapshot:** Phase 06 below routes terminal and native reviews
through one live owner and the same approval validator. GUI confirmation is now supported;
terminal-only consent wording here describes the preceding build. Schema 4 protection remains.

### Scope, architecture and trust boundary

Phase 05 only, audited against the actual dirty Phase 02–04 working tree on 2026-11-04.
The existing argparse controller, CommentManager, config, SQLite transactions and official
OAuth/HTTP integration are retained. New runtime module: `src/flochat/safety.py`; new verifier:
`scripts/verify_safety.py`. Installer/lifecycle wording now points to the guarded console rather
than claiming all posting code is disabled. No new dependency, background worker, service, scheduler, overlay,
network endpoint or general-purpose write API. The eight-phase roadmap is unchanged.

Submission flow:

```text
local editor/draft → SafetyEngine.prepare (account/chat/policy verification)
 → SafetyEngine.confirm (terminal check + exact preview + typed unique phrase)
 → comments.submit (one-use bound request)
 → SafetyEngine.execute (final verification + atomic durable reservation)
 → official liveChatMessages.insert (one attempt, no retry)
 → accepted / rejected / outcome unknown metadata
```

`comment preview`, draft opening, readonly OAuth, session start/resume and historical boolean
`approved=True` are **not consent**. The standalone legacy `submit` path still fails closed;
no command sends by simply supplying text or `--yes`. `youtube select` never sends.
Approvals are memory-only and belong to one process/session/action. A trusted local Python
process is assumed: monkeypatching Python, editing SQLite, replacing files or using another
API client is outside this guard's security boundary. A terminal cannot prove biological human
presence; no supplied feature automates input or approval. Do not automate this console.

### Setup and deliberate individual workflow

Only on a supported desktop with the CLI and browser on the **same actual machine**:

```sh
# Readonly authorization remains the default:
flochat youtube connect --local-browser
# To request write access, deliberately remove the old local grant first:
flochat youtube disconnect --yes
flochat youtube connect --local-browser --allow-posting
flochat youtube account
flochat youtube select YOUR_LIVE_VIDEO_ID
# Prepare locally using the existing manager, or open/edit a saved draft:
flochat comment new --text 'Your individually intended comment'
flochat comment preview
flochat safety
```

Inside the console, type `start`, then `submit`. Inspect **the exact text**, its JSON-escaped
representation, Unicode code-point count, content UTF-8 byte count, channel ID/name and selected
video/chat ID/title. Type the displayed `SEND <unique approval ID>` exactly only if intending
that one real attempt. No case-folding, whitespace stripping or generic “yes” is accepted.
Any other answer cancels, invalidates the approval and pauses; no write is attempted.
`resume` does not restore approval: `submit` requires a fresh preview and fresh phrase.

`--allow-posting` requests the official accepted `youtube.force-ssl` scope, not the broader
`youtube` scope. This still grants substantial YouTube account permissions, not permission for
just one chat/comment. It is the narrower accepted scope for insert, **not** a per-message OAuth
scope. Google displays official consent. There is no silent permission upgrade, credential-file
fallback, cookie login, browser automation or Termux desktop-client workaround. Existing stored
authorization requires deliberate disconnect/reconnect before changing accounts **or scopes**.
Reconnect clears selection and cannot reuse an approval. Normal `youtube status` is network-free;
`stored_scopes` describes the local grant, while `posting_enabled: false` means that standalone
status/connect operation is not an approved write session, not that the code lacks the guarded path.

This environment is not a valid local desktop OAuth setup. The commands above describe the
owner's eventual manual workflow; they were **not used here to authenticate or send comments**.

### Foreground session controls and outcomes

The console supports only `start`, `status`, `pause`, `resume`, `stop`, `submit`, `history`,
`resolve ATTEMPT_ID`, `quit`. It starts `IDLE`; no session, approval or submission is restored.
States are `IDLE`, `READY`, `AWAITING_APPROVAL`, `SUBMITTING`, `PAUSED`, `STOPPED`, `ERROR`,
`OUTCOME_UNKNOWN`. JSON results carry `decision`, and attempted results have `accepted` and
`attempt_id`. Clean console exit 0 means the session ended normally, **not** that anything posted;
inspect the individual result. Relevant decisions include `REQUIRES_APPROVAL`, `APPROVED` (audit event),
`BLOCKED`, `INVALID_COMMENT`, `DUPLICATE`, `COOLDOWN_ACTIVE`, `NO_ACCOUNT`, `NO_SELECTED_CHAT`,
`CHAT_UNAVAILABLE`, `SESSION_PAUSED`, `SESSION_STOPPED`, `AUTHORIZATION_REQUIRED`,
`API_UNAVAILABLE`, `SUBMISSION_IN_PROGRESS`, `ACCEPTED`, `REJECTED`, `OUTCOME_UNKNOWN`.
No “success” is inferred from local validation, approval, reservation or HTTP transport alone.

Pause/stop invalidate pending consent; resume/start do not approve. Stop before the atomic
transport-start boundary prevents transmission; an already-started request **cannot be recalled**.
A stop observed in flight retains `SUBMITTING` until an actual result is recorded; an accepted
response is still reported honestly even if stopping. No automatic resume, reconnect, restart,
retry, outcome recovery or next-comment loop exists. The UI is synchronous: commands are read
between bounded operations, not by a background listener. Ctrl-C during final read checks
prevents the subsequent write; interruption while transmitting is conservatively unknown.
Controls affect the current foreground session, not arbitrary other consoles. Legacy top-level
`flochat start/stop` is lifecycle scaffolding, **not** an armed SafetyEngine session.

### Binding, validation and final checks

Each approval expires after 120 monotonic seconds and binds the exact locally normalized text,
authenticated channel, selected chat/video, editor/draft/selection snapshots, grant fingerprint,
request and random one-use ID. It is consumed even when final checks fail. Nothing on disk can
restore usable approval. Final verification repeats credentials/scope/account/live-chat checks,
then compares editor/selection again in a SQLite write transaction before durable reservation.
Changed text (even one character), target, account, grant or selection timestamp requires new
consent. State changes during verification cannot re-arm a stopped session. Later changes do
not redirect or mutate an already-started immutable request.

Existing normalization converts CRLF/CR and trims outer whitespace; it does not collapse interior
spacing or strip Unicode joiners. The exact normalized editor text is the API text; an
unexpectedly non-normalized stored editor is blocked, not silently repaired while sending.
Empty/whitespace-only text, unsafe controls, invalid surrogate Unicode and invalid destination,
account, authorization, unavailable chat or session all fail closed. Unicode code points are not
visual graphemes; UTF-8 content bytes are separately reported, not claimed as HTTP body size.

The existing `max_comment_length` default 200 (configurable 1–1500) is a **local policy**, not an
invented official YouTube maximum. No official numeric text limit was established from the
first-party discovery schema; server validation remains authoritative and can reject otherwise
locally valid input. `messageTextInvalid` is classified as `invalid_comment`. This is a stated
verification limitation, not a claim that all configured lengths are officially supported.

### Duplicate, cooldown, concurrency and unknown policy

* A SHA-256 fingerprint of NFC-normalized, whitespace-collapsed content is used only for duplicate
  comparison, scoped to channel and chat. Actual API text is never canonicalized this way.
  Every reserved attempt, including rejected/unknown attempts, blocks matching content permanently.
  Legacy approved/submitted/confirmed/failed `comment_history` entries are also compared for the
  chat; lacking account identity, they conservatively block matching content for any account.
* No duplicate override or repeat/bulk mode. Different chats/accounts do not count as the same
  duplicate, but the local cooldown applies to all attempts in that database. This cannot detect
  posts made outside FloChat or records removed by editing/replacing/moving the database.
* Existing `cooldown_seconds`: default 30, minimum 5, maximum 600. Invalid values fail closed,
  including bypassed model validation. This is a local minimum spacing policy, **not** an official
  YouTube request allowance or rate-limit guarantee. Failed/reserved attempts count too.
* Wall time and persisted monotonic references both constrain elapsed time; a persisted wall
  high-water mark blocks detected rollback. Same-host restart preserves protection. Monotonic
  reset/reboot is conservative and may block longer until its prior reference catches up;
  there is no unsafe “disable protection” switch. Clock correctness cannot be proven offline.
* A nonblocking OS advisory lock (`flock` on POSIX; `msvcrt` byte locking on Windows) covers final
  verification, reservation, transport and completion. A `BEGIN IMMEDIATE` transaction rechecks
  policy and records a unique consumed approval/reservation atomically. The lock is for
  cooperating processes sharing the same local DB/path, **not** a distributed/network-filesystem
  guarantee or protection against malicious code. Two concurrent Linux processes were executed
  with simulated approvals: exactly one mocked insert was allowed.
* Interrupted durable reservations and uncertain responses block **all** further submissions in
  that database. An orphan `IN_PROGRESS` record is treated as unknown when the lock is available;
  classification is committed before further policy checks, even when those checks block.
  It is never assumed failed or resubmitted.
* Inspect the actual chat/outcome yourself, then use `resolve ATTEMPT_ID` and type
  `REVIEWED ATTEMPT_ID`. This records only your review, **not** acceptance or rejection. The
  session stops; explicit new start/preview/approval is needed for another action, cooldown
  remains and the original content remains duplicate-protected. No automatic reconciliation.

### Official transport, error handling and privacy

One official `POST https://youtube.googleapis.com/youtube/v3/liveChat/messages?part=snippet`
with `snippet.liveChatId`, `type: textMessageEvent` and `textMessageDetails.messageText`.
The first-party Google discovery source was inspected through Google's
[API discovery document](https://github.com/googleapis/google-api-python-client/blob/main/googleapiclient/discovery_cache/documents/youtube.v3.json).
Its insert scopes/method/fields were checked, not inferred from sample browser automation.
The sole insert lives inside SafetyEngine. Credentials stay in approved OS keyring storage;
no write scope is requested by default. No redirects, environment proxy/credential injection
or POST retries; existing TLS verification and 20-second connect/read timeout remain.
This timeout is not a hard total elapsed deadline or an in-flight cancellation guarantee.

Only a successful API response with a nonempty message ID and matching chat/type/exact text is
`ACCEPTED`. Recognized 400/401/403/404/429 responses are `REJECTED` with safe existing API
categories (including auth, permission, unavailable chat, invalid comment, quota and rate limit).
`ConnectTimeout` is rejected-before-transmission. Other transport failures, read timeouts,
interruptions, 5xx/redirects and malformed/inconsistent successful responses are unknown,
not labelled posted or safe to retry. Some non-transmitted failures are deliberately classified
unknown because absence of transmission cannot be proven. Completion-storage failure leaves a
protective reservation instead of falsely claiming success.

Schema **4** adds `safety_attempts`, `safety_events`, `safety_clock` transactionally after validating
existing schema compatibility, preserving schema 1–3 data. Metadata includes IDs, account/chat,
content fingerprint, character count, timestamps, attempt state, category and confirmed API ID.
No approval object, token, header, raw API body or full comment snapshot is stored in these tables.
Existing explicit editor/draft storage still contains your text. Fingerprints/IDs are not
anonymization or encryption and hashes can permit guessing predictable comments.

`history list` now includes `safety_events` alongside the existing local prepared/previewed
history. `history clear --yes` clears event logs, **not** attempt hashes, unknown reservations
or cooldown references. Safety-console `history` shows recent event metadata; `status` includes
attempt metadata needed for review. Account/chat IDs and timestamps are still personal data;
protect your local files. No telemetry, cloud sync or external audit upload is introduced.

### Phase 05 verification evidence

All external services/grants/terminal confirmations in the verifier are synthetic/mocked.
Network socket creation is explicitly forbidden in safety-test processes. Local SQLite,
transactions, CLI and real Linux subprocess locks actually execute; assertions are not live
YouTube service verification. Re-run with the installed environment:

```sh
.venv/bin/python scripts/verify_safety.py
.venv/bin/python scripts/verify_comments.py
.venv/bin/python scripts/verify_youtube.py
.venv/bin/python scripts/check_repository.py
.venv/bin/ruff check .
.venv/bin/ruff format --check .
```

The current executed results and platform/install limitations are itemized below. Windows,
macOS and Android/Termux runtimes, native OS vault success, actual OAuth consent and actual
YouTube writes remain **NOT EXECUTED**. No real comment is sent by automated verification.

## Phase 05 Completion Report

1. **Audit baseline:** inspected actual dirty working tree, existing CommentManager, normalization,
   config, CLI/controller/doctor, schema/migrations, OAuth/vault/HTTP handling and roadmap; did not
   reset earlier Phase 02–04 work. No reliance on the old completion report as proof of new code.
2. **Files:** only one new runtime module and one purposeful verifier. Existing database,
   comments, controller, CLI, YouTube integration, roadmap, doctor, settings, package description,
   ignore rules, repository required-file list and root README were extended in place. No new deps.
3. **Central gate:** `comments.submit` delegates only to an active SafetyEngine with a bound ID;
   legacy standalone calls refuse. Sole insert location is inside the guarded execute path.
4. **Visible review:** the engine itself requires stdin/stdout TTY, renders exact text plus escaped
   representation/destination/counts, reads the unique phrase and rejects generic or piped approval.
5. **Per-comment consent:** 120-second, one-use in-memory approval; never inherited from preview,
   saved draft, start/resume, config, readonly discovery, restart or reconnection.
6. **Binding/final recheck:** exact content/request/account/chat, grant and local snapshots checked
   again before reservation; changes or expiry invalidate and consume approval without a write.
7. **Validation:** existing normalization/Unicode/control rules reused; empty, unsafe, over-local-limit,
   missing destination/account/chat/auth/session cases fail closed. Actual API text stays exact.
8. **Length evidence:** code-point/UTF-8 counts distinct. Existing local 200 default retained; no
   authoritative official numeric text maximum verified. Server remains authoritative.
9. **Duplicates:** persistent channel/chat/canonical-content protection, including legacy attempts;
   no reset through event-history clearing, no override or repeated-comment campaign feature.
10. **Concurrency:** local SQLite atomic reservation and unique consumed approval plus OS lock.
    Linux contention and two actual simultaneous processes executed; exactly one mocked POST.
11. **Cooldown:** validated 5–600 seconds, persisted attempted-time and wall/monotonic checks;
    restart, detected clock rollback/forward-jump safety and invalid-disable configuration exercised.
12. **States:** explicit foreground eight-state engine, initial IDLE; start/resume never approve.
    No persisted session or automatic recovery/start/submit mechanism.
13. **Stop/cancellation:** before-transmission stop blocks POST; mocked in-flight stop does not
    misreport accepted content as cancelled. Synchronous UI and Ctrl-C limitations documented.
14. **Official integration:** insert part/snippet/type/chat/text and official endpoint checked;
    no unofficial endpoint, browser automation, redirects or automatic retry.
15. **Permission consent:** readonly remains default. Explicit force-ssl consent/reconnect only;
    synthetic approved-vault roundtrip and OAuth scope selection executed under mocks.
16. **Success/error truth:** acceptance requires matching response plus message ID. Auth/permission,
    invalid input, chat, quota/rate rejection categories retained; arbitrary bodies never logged.
17. **Unknowns:** timeouts/ambiguous responses/interruption conservatively persist and block;
    explicit real-chat review acknowledgement stops session and never permits same-content retry.
18. **History:** prepared/previewed local events coexist with requested/approved/blocked/attempted/
    accepted/rejected/unknown/reviewed metadata; event clearing cannot erase protection state.
19. **Migration:** schema 4 additive and transactional, pre-migration compatibility check;
    populated schema-3 profile/draft/editor/history/selection/usage preservation executed.
20. **CLI/config:** argparse and old commands preserved; one `safety` console plus explicit OAuth
    opt-in flag. Settings remain readonly; no safety-disable switch or bulk-send command.
21. **Privacy/security:** no credentials/full text in safety metadata, no raw API body/error logging,
    no telemetry or fallback vault. Hash guessing/local-owner tampering limitations explicit.
22. **New tests:** safety verifier currently **184 executed assertions**, API/OAuth/vault/terminal
    portions MOCKED; real local DB/process locking. No live service write or real human approval test.
23. **Regressions:** existing **140 Phase 03** and **307 Phase 04** checks re-executed and PASS,
    with their original local-vs-mocked boundaries preserved. Repository AST/secret/file checks and
    Ruff pass; no broad dead-code exemption was added.
24. **Install/platform:** Linux fresh/repeat install and final foundation/doctor checks are listed
    in the final verification update below. Other OS runtimes and native vaults NOT EXECUTED;
    static syntax/platform simulations do not establish native runtime support.
25. **Remaining verification:** live OAuth, actual permission grants, actual insert responses,
    service-side limits and cross-platform locking/vault/runtime behavior remain unverified.
    No release-readiness or spam-policy-compliance certification is claimed from mocks.
26. **Scope/preservation:** Phase 05 only; no Phase 06 implementation, additional phase, release,
    package upload, PR, commit, push, visibility change or external distribution. Prior dirty work
    preserved. Root README remains the sole project documentation and completion report.


### Final Phase 05 verification update — 2026-11-04

* Final-source isolated fresh and repeat Linux installs: **PASS**, at
  `/tmp/flochat-phase5-final.CvDmvj/repo`. Both actually ran the installer; repeat reused the
  environment. Version reports Phase 05. JSON settings succeeds and doctor reports `ok`.
  Doctor success is local readiness, **not** verification of a working Google grant or service.
* In that installed copy: **184 safety assertions + 140 Phase 03 checks + 307 Phase 04 checks
  PASS**. Safety API writes, OAuth, keyring and terminal approval are synthetic/mocked only.
  Real local SQLite migrations, persistence, advisory locks and competing subprocesses execute.
* Additional current-tree foundation smoke: **24 executed assertions PASS**, covering JSON CLI
  version/status/state/platform/settings/config/doctor, noninteractive safety refusal, invalid
  cooldown values, boolean approval insufficiency and schema-4 integrity. Network prohibited.
* Ruff lint and format: **PASS**, 22 Python files formatted. Repository guard: **clean**,
  259 definitions, 29 required files; AST/secret/structure checks kept, no broad exemption.
* `bash -n` installer/launcher/helpers and `dash -n` launcher/helpers: **PASS, static syntax**.
  Both PowerShell files: **PASS, tree-sitter grammar only**; no native PowerShell runtime.
* Live OAuth/API/OS-vault success and Windows/macOS/Termux runtimes: **NOT EXECUTED**.
  No real comments sent, no release/distribution actions, no commit/push/PR. Branch remains
  `arena/9dc86ddb-flochat`, HEAD unchanged at `6f4fe83`; earlier dirty work remains uncommitted.

---

## Phase 06 Floating & Background Engine

### Actual status and audit

**Implementation present; NOT fully native-verified or ready for a completion certification.**
The repository was dirty. Git status/history, all source/installer/launcher boundaries, root
README, adapter/lifecycle contracts, CLI, migrations, approval creation/consumption, duplicate
and cooldown logic, reservation/process locks, OAuth/keyring transport and AST guard were
inspected before editing. Prior Phase 02–05 work was preserved. Baseline executed before new
code: Phase 03 **140**, Phase 04 **307**, Phase 05 **184** assertions/checks passed. A temporary
pre-change tracked-file patch was kept outside the repo; it was not used to overwrite anything.

The desktop window has **not** been observed working on any OS here. Qt installation succeeded,
but importing QtWidgets fails because `libGL.so.1` is absent; no X11/Wayland compositor exists.
Do not confuse installed bindings, source, grammar validation or core IPC tests with a native UI
runtime pass. Android has no SDK/JDK/Gradle/emulator/device here; its APK is **not built**.

### One shared owner, not four FloChats

```text
terminal safety UI / native Qt desktop client / Kotlin Android overlay
     → bounded authenticated local JSON IPC
     → one CoreRuntime / one bound SessionManager / one SafetyEngine
     → existing CommentManager, SQLite schema 4 and YouTube integration
     → original final validation + reservation + sole official insert
```

`src/flochat/runtime.py` owns availability, UI attachment/leases, serialized operations and the
one engine. `SessionManager.bind` creates that engine once; `transition` controls it. Historical
in-process lifecycle snapshots remain for compatibility, not as an independent active writer.
CLI `start/stop/status/safety` now use the live owner when appropriate. Platform clients contain
no account-token access, DB, duplicate/cooldown logic or YouTube write implementation.

`src/flochat/panel.py` is **one** optional QtWidgets desktop client. Qt uses native platform
windows (Win32, Cocoa, Linux platform plugin). This deliberately chooses the permitted alternative
to separate C#/Swift applications: three native windows do not require three independent UIs,
protocol implementations or engines. It is **not** a tested WinUI/Swift/AppKit NSPanel delivery.
`native/android` is the necessary Kotlin companion: Termux alone cannot create an Android
`TYPE_APPLICATION_OVERLAY` window. It remains a companion to the terminal-launched Python core.

### Commands and installation

Default installers still install the CLI only, preserve their venv/repeat behavior, do not
change system security settings, and do not register startup tasks/services. No hidden native
downloads, permission requests or desktop dependencies were added to normal installation.
GitHub clone URL detection/placeholder behavior is unchanged.

```sh
# From the installed clone, using its Python/venv; desktop owners opt in:
python -m pip install -e '.[desktop]'
flochat panel start --mode manual       # requires a usable real graphical desktop
flochat panel start --mode persistent   # explicit background availability
flochat panel status                    # fresh authenticated owner response, not PID-file trust
flochat panel stop                      # request shutdown; in-flight work cannot be recalled
# Without a graphical UI, explicit core availability and normal terminal controls still work:
flochat panel start --core-only --mode manual
flochat session start
flochat session pause
flochat session resume
flochat session stop
flochat session recover                 # explicit readonly auth/account/chat validation; leaves STOPPED
flochat safety                          # interactive terminal review, same live owner
flochat mode persistent                 # running-owner mode only; invalidates approval/stops session
flochat mode manual
# Debug an owner in the foreground, only after the previous owner has stopped:
flochat panel serve --mode manual
```

`panel view` opens the optional client for an already-running owner. `panel start` explicitly
starts an owner if absent, then opens controls; on Android it starts the core for the companion.
No command implies a session approval. `mode` changes only the current owner; use existing
`FLOCHAT_MODE`/config for the next explicitly requested launch. Settings remain read-only.
A normal console exit or acknowledged shutdown request is not proof a comment posted or an
in-flight transport was recalled. Inspect result `accepted`, session state and attempt history.

Optional dependency: **PySide6-Essentials >=6.8,<7**, providing QtCore/Gui/Widgets, rather than
unneeded Qt WebEngine/Addons. Its binding dependency is installed by pip. No new mandatory Python
dependency. OS native GL, Qt platform-plugin dependencies and desktop access are still required;
FloChat does not install system packages or use sudo. `doctor` reports optional panel readiness
separately; local CLI health does not certify a window, compositor, vault or Google grant.

### Shared panel behavior

The compact light UI uses white/soft-grey surfaces, dark text, restrained blue focus accents,
plain text, native dragging/minimize/close behavior, accessible labels and no decorative assets.
It displays identity, owner availability, exact SafetyEngine session state, last verified account,
selected chat/stream, connection reason, cooldown remaining, editor and attempt metadata.

Controls edit/save through CommentManager, select/open a draft, preview locally, start/pause/
resume/stop, recover a connection, review one action, cancel and open the terminal where possible.
Local editor changes must be saved before review; the core's normalized text, not an unsaved UI
buffer, is approved. The dialog shows the exact text plus escaped representation, account/chat/
video identifiers, title, counts and unique `SEND <ID>` phrase. Generic yes, boolean approval,
modified text, expired review and stale client ownership cannot authorize a submission.

Desktop requests run off the UI thread. No UI action directly writes YouTube. A request in flight
cannot be called cancelled; close requests stop and wait for the actual result when an operation
is busy. Manual close detaches/stops the owner. Persistent close leaves explicitly requested
headless availability, **not** an active consent/session; reopen with `panel start`. There is no
hidden login/startup persistence or guaranteed tray icon. Linux/Windows terminal handoff launches
a known terminal/Python command; macOS opens Terminal and asks the user to run the same clone's
CLI, avoiding Automation permission. Android opens only the known Termux launch intent when allowed.

Local UI payloads are bounded (32,000-character editor buffer, 100 draft labels; 512 KiB IPC
frames). Oversized existing editor text is marked truncated/read-only, not silently saved back.
These are UI/resource bounds, **not** official YouTube comment limits; the existing local send
policy and server validation remain authoritative.

### Lifecycle, persistent/manual operation and interruption

Availability is distinguished from commenting: `NOT_RUNNING`, `RUNNING`, `STOPPING`, `INTERRUPTED`
are runtime reports, not a second SafetyEngine state machine. The eight Phase 05 engine states
remain authoritative. New owners always begin IDLE; attaching controls stops stale consent.
Mode changes, edits, draft opening, pause, stop, detach, takeover, recovery and relevant external
editor/selection changes invalidate approval. SQLite changes from another CLI are refreshed by
the owner between operations. Account/chat/grant are still verified again before a write.

Persistent mode keeps only an explicitly started user process available. It does not approve,
submit, retry, schedule comments, autostart at login/reboot or guarantee OS survival. Manual mode
works with terminal/IPC without any graphical persistence; detaching/losing its panel lease
terminates that owner. `panel stop` shuts down availability; session stop only stops the shared
session, except an unattached manual owner can also finish. Stop received during transport reports
SUBMITTING until actual completion. Top-level stop likewise reports pending, not recalled success.

A 15-second client lease uses monotonic **and wall** references. Lost heartbeats or detected
sleep/clock gaps stop/invalidate the session before a returning heartbeat can refresh it. Approval
expiry now also checks wall-time bounds in addition to monotonic 120 seconds, avoiding a stale
challenge surviving a platform whose monotonic clock excludes suspend. These checks are
conservative; scheduler stalls/clock adjustments can require explicit reopening/review.

No startup recovery restores a pending approval. A stale endpoint/PID file never proves liveness:
status requires an authenticated reply to a fresh nonce. Process termination/reboot is reported
as interrupted or not running. Existing durable IN_PROGRESS/unknown reservations remain protective;
there is no automatic retry. Terminal `safety` supports `resolve ATTEMPT_ID` with the existing
`REVIEWED ATTEMPT_ID` acknowledgment after actual chat inspection; this is not proof of acceptance
and retains duplicate/cooldown protection.

Connection status is explicitly **UNVERIFIED** or **VERIFIED_AT_TIME**, not a fictional continuous
YouTube connection. No periodic YouTube probes run in the background. Failed user operations
report sanitized reasons; `Recover` is a user-requested credential refresh/account/chat recheck,
stops the session and requires fresh start and consent. It never calls insert. After owner
restart, the desktop must reattach/recover explicitly; Android must also re-pair its rotated
capability. UI polling/heartbeats may restore status transport, never session consent or posting.

### IPC security and persistence

* Desktop Linux/macOS use mode-0600 Unix sockets in a checked mode-0700 per-user runtime
  directory. No desktop TCP listener. Windows uses a local named pipe with bounded byte frames,
  **not pickle**. The pipe/DPAPI branches are not runtime-tested here.
* Android requires loopback TCP for cross-UID Termux/companion access: binds **127.0.0.1 only**,
  random port, custom framed protocol, no HTTP server, browser API, public address or remote host.
* Every request/response is HMAC-SHA256 authenticated with a per-run 256-bit random capability.
  Timestamp bounds, unique nonces, bounded replay cache and response-request nonce binding apply.
  Frame, worker, command queue, argument types/keys and command names are bounded/validated.
  Unknown operations, extra `approved` flags, stale instances, invalid MACs and replay are rejected.
* `<database>.panel.json` is ephemeral endpoint metadata, never an approval or second database.
  POSIX owner/mode/no-follow checks protect the capability. Windows stores it current-user DPAPI
  encrypted. A per-canonical-database OS lock prevents competing owner starts; the existing
  separate per-attempt lock/SQLite reservation still controls insert. Keys rotate on restart.
* The native client supplies only the core-issued ID and user-typed phrase, never an approval
  object. SafetyEngine's shared `_approve` validates it and `execute` repeats all final bindings,
  duplicate/cooldown/session/scope checks and atomic consumption. No alternative write route.
* No OAuth credentials, headers or raw Google bodies cross IPC or enter its metadata. Draft text
  intentionally reaches the authenticated local UI; event history remains metadata-only.
  HMAC/base64 is **not encryption**. Local transport confidentiality relies on OS isolation;
  protect the device/user account. `panel pair` intentionally reveals only an IPC capability
  in a private Android terminal, never normal status/JSON/log output.
* Trusted same-user Python/UI processes are the boundary, as in Phase 05. This cannot attest a
  biological human, defend against compromised same-user/root software or prevent a user from
  replacing files or using another API client. No supplied feature automates approval/input.

Existing SQLite **schema 4** is reused unchanged; no migration/new DB was necessary. Profile,
drafts, editor, local/safety history, selection, API usage, unknowns, hashes and cooldowns remain.
Only the endpoint/capability metadata is ephemeral. No approval is stored/restored there.

### Platform setup, permissions and evidence

| Platform / verification scope | Status | Evidence / restriction |
| --- | --- | --- |
| Linux core, CLI, IPC, SQLite | PASS — REAL RUNTIME | Actual sockets/processes/leases/restart; not a GUI result |
| Linux Qt offscreen / headless GUI | BLOCKED | Qt native dependencies absent; even widget import cannot succeed |
| Linux X11 / Wayland floating window | BLOCKED | No display, compositor or Xvfb; stacking/drag/focus unverified |
| Windows implementation / installer source | PASS — STATIC | Shared Qt + pipe/DPAPI paths inspected; PowerShell grammar only |
| Windows native runtime / DPAPI / pipe | BLOCKED | Windows/PowerShell runtime unavailable |
| macOS implementation | PASS — STATIC | Same Qt client, Cocoa plugin paths inspected |
| macOS native runtime / Cocoa / Keychain | BLOCKED | macOS host unavailable |
| Android configuration / manifest / Kotlin | PASS — STATIC | Source/grammar/permissions only, not compilation |
| Android APK build | BLOCKED | No JDK/Gradle/SDK; required Google/Maven/Gradle hosts outside sandbox allowlist |
| Android emulator / device / Termux | BLOCKED | No emulator/device; secure Termux OAuth still fails closed |


Qt's topmost flag is a hint, not an overlay above every app, compositor, secure desktop or
full-screen Space. Wayland/X11 environment is detected/reported, not forced around. Android's
system can hide overlays (including over sensitive screens), adjust their visibility, suspend
Termux or kill either UID; a foreground service/wake lock/battery preference is not immortality.
Do not disable security protections, phantom-process restrictions or OS privacy controls.

Android source build, on the owner's Android development machine:

```sh
# Requires JDK 17, Gradle 8.9, Android SDK/platform 35 and normal Google/Maven access.
# No wrapper binary, SDK or APK is checked into this repository.
gradle -p native/android assembleDebug
# Inspect/sign/install the locally generated debug APK yourself; no binary is published here.
# In Termux (existing core installed):
flochat panel start --core-only --mode persistent
flochat panel pair
```

Open **FloChat Companion**, store that current pairing code, read the overlay explanation,
explicitly grant Display over other apps and (API 33+) notification permission, then explicitly
start controls **while the setup activity is visible**. Pairing is encrypted with an Android
Keystore AES-GCM key; no Google tokens or plaintext fallback. Re-pair after core restart. API 26+
overlay type, API 34 special-use FGS declaration/subtype and target SDK 35 are in the manifest.
Only Internet (local IPC), overlay, foreground/special-use service and notifications are requested;
package visibility queries only Termux for the explicit terminal button. No accessibility,
contacts/storage/device inventory, boot receiver, startup task or battery-exemption permission.
Notification/close controls stop the companion; lost lease stops the session even if Android
kills it without lifecycle callbacks. Battery optimization/Doze and Termux process termination
must be inspected through ordinary OS settings, not bypassed. No indefinite/reboot guarantee.

First-party Android source reviewed through accessible AOSP mirrors:
[Service lifecycle](https://github.com/aosp-mirror/platform_frameworks_base/blob/master/core/java/android/app/Service.java)
and [WindowManager overlay restrictions](https://github.com/aosp-mirror/platform_frameworks_base/blob/master/core/java/android/view/WindowManager.java).
This is source inspection, not evidence the companion passed a platform build or policy review.

### Phase 06 verification results

Run in the project's environment:

```sh
python scripts/verify_runtime.py
python scripts/verify_safety.py
python scripts/verify_comments.py
python scripts/verify_youtube.py
python scripts/check_repository.py
ruff check .
ruff format --check .
```

Current executed results: **83 runtime assertions**, **184 safety checks**, **141 Comment Manager
checks**, **307 YouTube checks**, all PASS for their executed portions. Runtime tests use real
local sockets, authentication, replay checks, SQLite, CLI subprocess access, owner threads,
stop-during-insert and restart. Google writes/auth/terminal intent are **MOCKED/SYNTHETIC**;
no real comment is sent. Sleep/expiry/lease gaps are **SIMULATED**, not device suspend tests.
Qt window tests are an explicitly **BLOCKED** group, not counted as passed UI assertions.

The previous 140-check Comment Manager verifier was deliberately updated for two newly authorized
semantics: persistent start succeeds, and source-present adapters must not claim verified native
capabilities. An explicit owner shutdown cleanup adds one check, yielding 141. No original
local-data/safety/AST regression coverage was removed. Phase 04/05 totals remain 307/184.
Kotlin/Gradle grammar and manifest inspection are **STATIC ONLY**, never an APK build.
Final install/doctor/syntax evidence is recorded below after execution.

## Phase 06 Completion Report

1. **Status:** shared engine/IPC/lifecycle implemented and exercised on Linux; native UI delivery
   remains blocked/unverified. Phase 06 is **not declared fully complete**. No Phase 07 certification.
2. **Shared architecture:** one live owner per canonical DB, one bound SessionManager and
   SafetyEngine; all terminal/native commands share it, not four business-logic implementations.
3. **Floating panel:** compact optional Qt desktop client plus Kotlin overlay source; real
   editor/draft/preview/session/review/cancel/terminal callbacks. No claimed native runtime pass.
4. **Android:** substantive Kotlin setup, overlay/service and encrypted pairing client; APK build,
   device/emulator, permission, keyboard, battery/reboot behavior unverified; OAuth/vault fail-closed.
5. **Windows:** Qt Windows-native window design, named pipe and user DPAPI implementation;
   no C# build or Windows-native runtime was executed. No admin/startup requirement.
6. **Linux:** Unix socket/owner/SQLite/CLI integration executed. QtWidgets/window tests blocked
   by missing native GL/display; topmost, dragging, minimize and X11/Wayland remain unverified.
7. **macOS:** Qt Cocoa alternative avoids separate Swift business/UI duplication. Window levels,
   Spaces, native UI and Keychain behavior not executed; no privacy-permission shortcut.
8. **Persistent mode:** explicit detached availability, no autostart/cron/service registration,
   no independent commenting decisions, no indefinite lifetime promise.
9. **Manual mode:** works with core-only/terminal controls; detach or lost panel lease ends owner.
   No graphical persistence required. Unknown write protection survives either mode.
10. **Lifecycle:** explicit start/pause/resume/stop, mode switch invalidation, graceful owner
    shutdown and stale endpoint detection; availability is distinct from SafetyEngine session state.
11. **Recovery:** explicit readonly credentials/account/chat revalidation; stopped state and fresh
    consent required. Status heartbeat may reconnect transport, never trigger insert or retry.
12. **IPC:** JSON-only bounded authenticated frames, replay/time/instance checks, local transports,
    secret isolation and metadata permissions. Windows/Android transport-native behavior unverified.
13. **Safety integration:** same `_approve` validator and existing execute/reservation/insert gate;
    no native `approved` flag, token access or separate write pathway. No cooldown/duplicate bypass.
14. **Approval verification:** engine regressions plus IPC tests execute one-use/expiry/edit/pause/
    takeover/reconnect/restart/lease invalidation. Added wall/suspend expiry and honest in-flight stop.
15. **Installation:** default installers remain CLI-only; messages explain optional UI. Desktop extra
    and local Android build/setup documented; no automatic permission/system/security modifications.
16. **Files created:** `ipc.py`, `runtime.py`, `panel.py`, `verify_runtime.py`; six required files
    under `native/android` (Gradle build/settings, manifest, Bridge, SetupActivity, OverlayService).
17. **Files modified:** CLI/controller/lifecycle/safety/adapters/roadmap/doctor/package description,
    optional dependencies, required-file guard list, ignore rules, installer messages, existing
    Comment Manager verifier expectations/cleanup and root README. Prior dirty work preserved.
18. **Dependencies:** only optional PySide6-Essentials; Android build-time AGP/Kotlin plugin for
    actual Kotlin source. No extra mandatory Python dep, web server, browser engine or cloud SDK.
19. **Actual platform results:** Linux core/local IPC/SQLite/CLI executed. No actual desktop
    floating window, Android emulator/device, Windows or macOS runtime pass claimed.
20. **Mocked results:** all Google API writes/credentials and user approval inputs synthetic;
    lifecycle interruption timing partly simulated. Tests never send real comments.
21. **Regressions:** 141 Comment Manager, 307 YouTube and 184 Safety checks PASS, plus 51 runtime
    assertions in the earlier run; the hardening run now executes 83. Installation/doctor and
    shell/static grammar results are itemized below.
22. **Dead-code audit:** existing AST algorithm retained, no broad exemptions. New required files
    are explicitly listed; callbacks/IPC handlers are reachable from real UI/CLI or tests.
23. **Security audit:** no OAuth tokens over IPC or in new metadata, no pickle/shell endpoint,
    no raw API-body logging, bounded unauthenticated clients/replays, no disabled platform security.
    Same-user compromise/root and distributed/network-filesystem guarantees remain outside scope.
24. **Known limitations:** no native verification in this sandbox, synchronous core operations can
    delay graceful completion; stop cannot recall transport; timing checks are conservative;
    OS may terminate background availability and window managers may reject topmost behavior.
25. **Unverified behavior:** native builds/windows/permission prompts/dragging/focus/GL/plugin
    compatibility, DPAPI/named pipes, Android Keystore/loopback/service policy and macOS Cocoa/Keychain.
    Live Google consent/write behavior remains pending from earlier phases.
26. **Minimality/restrictions:** only ten purposeful new source/build/verifier files; no extra docs,
    reports, README files, dummy platform directories, binary uploads, new phases, commits, push,
    PR, release or publishing. Root README is the sole documentation/completion report.

### Final Phase 06 verification update — 2026-11-04 (historical)

This retained report describes the earlier workspace, not fresh evidence for this checkout.
Its recorded HEAD `6f4fe83` is not the current HEAD; the hardening audit below observed
`208a6b4`. Earlier temporary paths/native-tool evidence are not assumed to still exist.

* **Fresh and repeat Linux install executed and PASS** in
  `/tmp/flochat-phase6-final.7eDGd9/repo`. Version reports Phase 06, settings succeeds,
  doctor reports local CLI health `ok` with the optional floating panel skipped/unavailable.
  The default install does not silently install Qt. Both installers ran, not a simulated copy test.
* In that installed copy: **51 runtime assertions PASS**, **184 safety PASS**, **141 Comment
  Manager PASS**, **307 YouTube PASS**, repository guard clean. API/OAuth/approval-intent portions
  are mocked/synthetic. The Qt group explicitly reports **BLOCKED**, not a UI pass.
* Additional **10 real Linux process assertions PASS**: production `panel serve`, competing-owner
  refusal, abrupt SIGKILL, stale status, explicit restart with new instance/key, IDLE/no restored
  approval, retained editor data, graceful shutdown and no stale running claim. Only local
  status/editor/session operations were invoked; no auth/API action or comment.
* Additional **25 foundation/CLI/settings/doctor/config assertions PASS**, external HTTP prohibited.
  Included Phase 06 version, JSON views, non-TTY approval refusal and unsafe cooldown rejection.
  An initial attempt used the non-project Python and failed before tests with missing `flochat`;
  it was rerun successfully with `.venv/bin/python`, not counted as a pass on that interpreter.
* Ruff lint/format PASS (26 Python files); repository guard clean (302 definitions, 39 required
  files). AST algorithm/exemptions unchanged; genuine orphan-function negative regression retained.
* Bash/dash shell syntax PASS. Both PowerShell files and five Kotlin/Gradle files parse with
  tree-sitter: **STATIC GRAMMAR ONLY**. Android manifest XML and the exact five-permission set
  inspected/asserted. This is not a Gradle/Android type check, APK build or device/emulator run.
* QtWidgets import attempted and **FAILED/BLOCKED**: native `libGL.so.1` missing; no real display.
  QtCore imports, but that does not establish window support. No fake GL stubs or OS restrictions
  bypasses were introduced. X11/Wayland window behavior remains NOT EXECUTED.
* Android build/emulator/device, Windows/macOS runtimes, named-pipe/DPAPI native execution,
  real OAuth/vault success and actual YouTube insert remain **NOT EXECUTED/BLOCKED**.
* All prior uncommitted work retained; branch `arena/9dc86ddb-flochat`, HEAD still `6f4fe83`.
  No commit, push, PR, native binary upload, release, visibility change or distribution.
  Phase 07 and Phase 08 remain pending. Native verification blockers prevent full Phase 06 closure.


---

## Phase 06 Completion & Hardening — 2026-11-05

**Decision: PHASE 06 — IMPLEMENTED, NATIVE VERIFICATION PENDING**

This is the current report, superseding the November 4 counts/environment claims above.
It is not Phase 07 certification, a release, or a claim that a native floating panel works here.
No real YouTube comments or Google OAuth flows were run.

### Audit and preservation

The actual checkout is branch `arena/9dc86ddb-flochat`, HEAD `208a6b4` (`Initial commit`).
README was already modified and the Phase 02–06 implementation was untracked at audit start.
That work was preserved, not reset or reconciled to the older reported HEAD. A private temporary
baseline was retained for comparison. The safety/runtime/IPC/panel, session/controller/platform,
CLI/install/launch boundaries, Android sources/configuration/permissions, dependency metadata,
regression coverage and repository guard were inspected. No new tracked file, native binary,
SDK, wrapper, second GUI implementation, documentation folder or mandatory dependency was added.
The existing AST algorithm/exemptions and original tests remain intact.

### Necessary changes in this hardening pass

* **Lifecycle ordering:** queued Start/Resume carries the owner's invalidation generation.
  Stop, lease loss, pause/cancel, attachment, mode/editor/draft/recovery invalidation prevents
  old queued activation from undoing the newer control action. The activation check and
  memory transition share the Stop lock. A regression blocks a mocked in-flight insert,
  queues Start, stops the owner and verifies that completion cannot reactivate that intent.
  This does not claim that an already transmitted write was recalled.
* **IPC/parser/resources:** reject duplicate envelope, payload and endpoint JSON keys and
  malformed authentication tags; preserve HMAC/timestamp/nonce/instance/request binding.
  Explicitly close an allocated client socket even if connection fails. Windows short-command
  response polling now uses the short timeout, not the 180-second review/confirm timeout.
* **Startup/cleanup:** failed endpoint publication closes its actual socket and removes only
  its bound socket path; cleanup is idempotent. Launcher success requires a new authenticated
  attachment, not merely a spawned PID. Failed startup reaps the child it created and does
  not terminate a reused owner. Attachment observation is not native/window verification.
* **Review presentation:** core reports actual remaining review lifetime and monotonic
  observation time. Qt/Kotlin ignore status replies older than the displayed review, and UI
  expiry uses remaining lifetime rather than granting another 120 seconds after delivery.
  Qt shows the submission warning, disables confirmation until the exact phrase is typed,
  and reports SUBMITTING while awaiting the actual result. The core remains sole authority.
* **Android lifecycle:** handle a Stop notification intent before creating floating controls;
  it no longer briefly creates/attaches a new overlay after process death. Stop/cancel replies
  do not falsely clear another operation's busy state. Graceful destruction attempts bounded
  detach, then closes registered sockets, including interrupted long calls; queued executors
  are stopped. OS kill is still handled by lease expiry, never a survival guarantee. These
  Kotlin changes passed grammar/source checks only, not a build or runtime test.
* **Install/readiness:** fixed PowerShell 7's read-only `$IsWindows` assignment by using a
  distinct local variable. Bash/dash install hints safely quote spaces, apostrophes and shell
  metacharacters. Removed the unused shell pip wrapper; dependency errors name the actual
  declared set. CLI platform notes no longer falsely say Phase 06 is unimplemented. Qt load
  errors distinguish missing native libraries from merely missing Python bindings.

Changed existing files: `runtime.py`, `ipc.py`, `panel.py`, `safety.py`, `platform.py`,
`scripts/verify_runtime.py`, `scripts/install_lib.sh`, `install.ps1`, Android `Bridge.kt` /
`OverlayService.kt`, and this README. Schema 4 and existing user data remain unchanged.
The one bound SessionManager/SafetyEngine, CommentManager, YouTube client and SQLite remain
in the Python owner; Windows/macOS/Linux share one Qt client; Kotlin is a thin local client.

### Phase 06 verification matrix (historical)

Each Status cell uses one verification label. A static or mocked pass is not a native pass.

| Scope | Status | Current evidence / boundary |
| --- | --- | --- |
| Linux owner, IPC, SQLite, CLI, lifecycle | PASS — REAL RUNTIME | Real local sockets/authentication/processes/leases/restart/cleanup; no GUI claim |
| Foundation/configuration/CLI | PASS — REAL RUNTIME | 25 assertions; external HTTP forbidden |
| Fresh/repeat Linux install and launcher | PASS — REAL RUNTIME | Actual installs into a path containing spaces; local doctor, venv reuse, Qt optional |
| Google/OAuth/vault/write acceptance and safety fault fixtures | PASS — MOCKED | 184 safety, 307 YouTube, plus mocked portions of runtime suite; no live comments |
| Local Comment Manager regression suite | PASS — REAL RUNTIME | 141 checks including migration, persistence, rollback, CLI and guard negative regression |
| Linux Qt headless/offscreen GUI | BLOCKED | Widgets cannot import; no actual headless GUI workflow executed |
| Linux X11 floating window | BLOCKED | No display/server/native dependency stack |
| Linux Wayland floating window | BLOCKED | No display/compositor/native dependency stack |
| Windows source/installer/pipe/DPAPI paths | PASS — STATIC | Python inspection/AST and PowerShell grammar; no native execution |
| Windows native window, IPC and credential vault | BLOCKED | No Windows or PowerShell runtime |
| macOS source/Cocoa/Unix IPC paths | PASS — STATIC | Shared source inspection only |
| macOS native window, Spaces/focus and Keychain | BLOCKED | No macOS host |
| Android Kotlin/Gradle/manifest | PASS — STATIC | Five Kotlin/Gradle files parsed; permission/lifecycle/configuration inspection only |
| Android APK compilation | BLOCKED | JDK 17, Gradle 8.9, SDK/platform 35 absent; build repositories inaccessible under sandbox host policy |
| Android overlay/service/Keystore/Termux device behavior | BLOCKED | No emulator or device; no approved Termux Google credential backend |
| Repository/AST/secret checks, Ruff and shell grammar | PASS — STATIC | Guard clean, 305 definitions / 39 required files; 25 Python files; no exemptions added |

Final-source working-tree suites: **83 runtime + 184 safety + 141 Comment Manager + 307 YouTube**
assertions/checks passed for their executed portions. Runtime includes genuine local transport
and database operations, fault injection/mocked Google operations, and simulated clock-gap tests;
83 is not a count of real GUI assertions. The Qt group is separately **BLOCKED**.

Additionally, **22 real Linux process assertions** passed: production owner startup, competing
owner refusal without metadata replacement, actual SIGKILL/stale status, restart/key rotation,
old-capability rejection, retained editor, IDLE/no restored approval, graceful endpoint/socket
removal, and actual independent protocol-client process death in both modes. Real 15-second
lease expiry left persistent availability stopped/alive and terminated the manual owner. These
clients were protocol actors, **not native GUIs**. All child processes were reaped. No socket
remained in the checked per-user runtime directory. Nonsecret advisory lock files are normal;
an unlocked lock file is not a surviving owner or usable capability.

Final-source fresh and repeat installer runs used
`/tmp/flochat-hardening-final.gpjUYL/repo with spaces`. Both installers actually ran; repeat
reused `.venv`. All four suites and the repository guard passed there too. Default installation
did not install Qt; doctor returned `ok` for local CLI health, not native readiness. The primary
working-tree venv separately installed `.[dev,desktop]` successfully. `pip check` passed.
Eight additional Bash/dash hint-quoting assertions passed. Both PowerShell scripts and five
Kotlin/Gradle files passed tree-sitter grammar only; manifest XML/exact five-permission set,
private service, no boot receiver and disabled backup were checked. An initial foundation
probe expected a more specific exception for a missing engine; it was corrected to the actual
fail-closed base exception and the full 25-assertion run then passed.

### Native blockers and unexecuted workflow

`ldd` on the installed Qt GUI library reports missing **`libGL.so.1`, `libEGL.so.1`,
`libxkbcommon.so.0`, `libdbus-1.so.3`**. No genuine copies were found in the inspected system
library locations. DISPLAY/WAYLAND_DISPLAY, Xorg and Xvfb are absent. The existing desktop extra
installs the official Qt Python package but does not supply those OS libraries. First-party
libglvnd build configuration/GLX dependencies were inspected; a complete graphics/message-bus
source stack was not built. No fake GL libraries, alternate GUI framework, root install,
system changes or security workaround was used. A proper native stack/display is still needed;
an eventual offscreen run must be reported as HEADLESS, not physical desktop verification.

Consequently **no actual GUI approval workflow was executed**: panel opening/attach, editing /
draft/preview, exact account/chat/stream review, typed phrase, mocked approved write/result/reuse
rejection, pause/resume/stop/disconnect and native close remain a combined GUI verification
requirement. Those core operations are exercised through genuine IPC with mocked Google services;
that is not a substitute for widget interaction, focus, drag, stacking or compositor evidence.

Android source specifies AGP 8.7.3, Kotlin 2.0.21, Java/JVM 17, compile/target SDK 35 and min SDK 26.
There is no JDK, Gradle, Android SDK, adb or emulator here, and normal Google/Maven/Gradle download
hosts are outside this sandbox's allowlist. No APK build was invoked and no APK was produced.
Grammar is not type checking or buildability proof. Build with the documented normal toolchain,
then verify explicit permissions, foreground start/stop, notification stop after process death,
Keystore failure, keyboard/focus, dialogs, drag, lifecycle and authenticated loopback on device.
Android still has no Google tokens, direct write path, accessibility permission or plaintext
fallback. Real Windows/macOS window/IPC/vault behavior likewise requires the respective hosts.
No platform limitation has been silently approved as sufficient for full completion.

### Dependency and delivery audit

No mandatory dependency changed. Pydantic validates configuration; google-auth and
google-auth-oauthlib supply official credentials/PKCE refresh; requests supplies bounded REST;
keyring supplies only the approved OS-vault boundary. Installed metadata reports MIT for
Pydantic/keyring and Apache-2.0 for the Google/requests packages. Ruff is development-only (MIT).
Optional PySide6-Essentials/shiboken6 are the single desktop GUI binding, not an alternate engine;
installed 6.12.0 metadata states `LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only`. Packaging or
redistribution must separately satisfy the applicable Qt obligations; none is certified here.

Current PyPI wheel metadata is available for Windows amd64/arm64, macOS universal2 (14.0+),
Linux x86_64 (glibc 2.34+) and aarch64 (glibc 2.39+); current Python bounds are >=3.10,<3.16.
These are current wheel metadata, **not** executed platform compatibility. The declared >=6.8,<7
range may resolve an older compatible wheel, where one exists; unsupported hosts must fail
clearly. No desktop extra is required for Android or the CLI. Gradle/AGP/Kotlin/SDK are Android
build-time requirements, not new Python runtime dependencies. Temporary grammar tooling was
isolated outside the repository. FloChat's own release licence remains pending for Phase 08.

All prior uncommitted changes remain. No commit, push, PR, release, visibility change, package /
installer publication, binary upload or external distribution occurred. Exactly eight named
phases remain; Phase 07 and Phase 08 were not started. The remaining native/environment evidence
prevents declaring Phase 06 complete.


---

## Phase 07 Cross-Platform Testing & Completion Report

**PHASE 07 — TESTED, PLATFORM VERIFICATION PARTIALLY BLOCKED**

Date: **2026-11-05**. Phase 06 remains **PHASE 06 — IMPLEMENTED, NATIVE VERIFICATION PENDING**.
That accepted implementation status was not reclassified as a failure. Exactly eight phases
retain their names; Phase 08 has not begun. This report certifies only the evidence below,
not native compatibility, real Google acceptance, OS-vault success or release readiness.

### Audit, environment and scope

Before the Phase 07 tests, the full working-tree inventory/Git status, root README, existing
verifiers, adapters, installers/launchers, CLI, Comment Manager, YouTube/credential boundary,
SafetyEngine, database, IPC/runtime, Qt client and Android companion were audited. The README
was loaded in full and its current Phase 06 report/architecture/limitations examined. A private
pre-change archive supported comparison; no reset/discard/checkout or removal of prior source
occurred. Initial regressions passed at 141 / 307 / 184 / 83 before defect-specific changes.

| Environment | Actual observation |
| --- | --- |
| OS | Debian GNU/Linux 12, x86_64, Linux kernel 6.1.158+, glibc 2.36 |
| Python / SQLite | Python 3.11.2; SQLite 3.40.1; normal non-root user |
| Node | v22.22.3 exists; not used by FloChat or these tests |
| Qt | Official PySide6-Essentials 6.12.0 installs; QtWidgets import remains blocked |
| Qt native libraries | `libGL.so.1`, `libEGL.so.1`, `libxkbcommon.so.0`, `libdbus-1.so.3` missing according to `ldd` |
| Displays | DISPLAY/WAYLAND_DISPLAY unset; no Xorg or Xvfb executable |
| Credential vault | Discovered `keyring.backends.fail.Keyring`; no session D-Bus address; no credentials read or written |
| Windows / PowerShell | No Windows host; no `pwsh` executable |
| macOS | No macOS host/Cocoa runtime |
| Android | No configured SDK; `java`, `gradle`, `adb`, `emulator`, `sdkmanager` absent from PATH; no usable emulator/device exposed |

The existing `.[dev,desktop]` extra was installed successfully into the local venv. No GUI
framework, mandatory dependency, system package, permission bypass or system configuration
was added. Normal Google/Maven/Gradle download hosts remain outside the sandbox host allowlist.
Android APK build and device runtime are **BLOCKED**; no Gradle invocation, APK or screenshot
was fabricated. The companion still has no independent YouTube write path, accessibility
service, insecure OAuth fallback, boot receiver or silent permission grant.

### Comprehensive Phase 07 verification matrix

This matrix records **target-platform execution**, not the assumption that shared Python code
must behave identically on another OS. Thus Linux successes are not copied into the Windows,
macOS or Android columns. `Installer` static entries describe inspected shell/PowerShell source,
not a completed installation. Linux MOCKED rows execute real shared code and temporary SQLite
but use synthetic account/chat/OAuth/API/approval inputs. No platform cell implies a live post.

| Area | Linux | Windows | macOS | Android |
| --- | --- | --- | --- | --- |
| Installation | PASS — REAL RUNTIME | BLOCKED | BLOCKED | BLOCKED |
| CLI | PASS — REAL RUNTIME | BLOCKED | BLOCKED | BLOCKED |
| Startup | PASS — REAL RUNTIME | BLOCKED | BLOCKED | BLOCKED |
| Configuration | PASS — REAL RUNTIME | BLOCKED | BLOCKED | BLOCKED |
| Comment Manager | PASS — REAL RUNTIME | BLOCKED | BLOCKED | BLOCKED |
| SQLite persistence | PASS — REAL RUNTIME | BLOCKED | BLOCKED | BLOCKED |
| OAuth configuration | PASS — MOCKED | BLOCKED | BLOCKED | BLOCKED |
| YouTube discovery | PASS — MOCKED | BLOCKED | BLOCKED | BLOCKED |
| SafetyEngine | PASS — MOCKED | BLOCKED | BLOCKED | BLOCKED |
| Approval | PASS — MOCKED | BLOCKED | BLOCKED | BLOCKED |
| Duplicate protection | PASS — MOCKED | BLOCKED | BLOCKED | BLOCKED |
| Cooldown | PASS — MOCKED | BLOCKED | BLOCKED | BLOCKED |
| IPC | PASS — REAL RUNTIME | BLOCKED | BLOCKED | BLOCKED |
| Floating panel | BLOCKED | BLOCKED | BLOCKED | BLOCKED |
| Persistent mode | PASS — REAL RUNTIME | BLOCKED | BLOCKED | BLOCKED |
| Manual mode | PASS — REAL RUNTIME | BLOCKED | BLOCKED | BLOCKED |
| Background lifecycle | PASS — REAL RUNTIME | BLOCKED | BLOCKED | BLOCKED |
| Reconnection | PASS — MOCKED | BLOCKED | BLOCKED | BLOCKED |
| Restart recovery | PASS — REAL RUNTIME | BLOCKED | BLOCKED | BLOCKED |
| Crash recovery | PASS — REAL RUNTIME | BLOCKED | BLOCKED | BLOCKED |
| Shutdown | PASS — REAL RUNTIME | BLOCKED | BLOCKED | BLOCKED |
| Security boundaries | PASS — REAL RUNTIME | BLOCKED | BLOCKED | BLOCKED |
| Installer | PASS — REAL RUNTIME | PASS — STATIC | PASS — STATIC | PASS — STATIC |
| Uninstall/cleanup | PASS — REAL RUNTIME | BLOCKED | BLOCKED | BLOCKED |

Linux security-boundary runtime evidence covers local permissions, authenticated IPC, safe
errors and persistence; actual OS-vault/OAuth success remains blocked/not run as specified
below. Native implementation inspection, seven Kotlin/Gradle/PowerShell grammar parses and
Android manifest/permission checks are **PASS — STATIC** only. No Kotlin type check, Windows
pipe/DPAPI execution, Cocoa/Keychain execution or real floating-panel workflow is certified.

### Reproducible tests and exact regression counts

Run from the project venv:

```sh
python scripts/verify_comments.py
python scripts/verify_youtube.py
python scripts/verify_safety.py
python scripts/verify_runtime.py
python scripts/verify_platforms.py
python scripts/check_repository.py
ruff check .
ruff format --check .
python -m pip check
```

`verify_platforms.py` is the one genuinely necessary new test-source file, in the existing
scripts directory. It is not a new test framework or user-facing feature. It runs Linux-only
process/install probes, cleans its TemporaryDirectory, reaps children, and rejects duplicate
assertion IDs. Its stdout separately attributes new foundation, installation and Phase 07
assertions. It never reruns/recounts the other four suites internally. Raw native widget
absence is BLOCKED, not an emulated/mocked window pass. No source tests were removed or weakened.

| Regression ownership | Final unique passing assertions/checks |
| --- | ---: |
| Phase 01 — Foundation | 28 |
| Phase 02 — CLI & Installation | 29 |
| Phase 03 — Comment Manager | 141 |
| Phase 04 — YouTube Integration | 307 |
| Phase 05 — Safety Engine | 184 |
| Phase 06 — Floating & Background Engine | 83 |
| Phase 07-specific probes | 119 |
| **Total passed** | **891** |
| **Final failed assertions** | **0** |

These are mixed real-runtime, mocked and static assertions, **not 891 native runtime tests**.
The new runner contributes 176 of that total (28 + 29 + 119); the four existing suites
contribute 715. Repeated diagnostic/final runs, install repeats, 40 lifecycle cycles, external
syntax/lint/guard gates and matrix cells are not added again to the assertion total.

**Total blocked: 13 planned native scenario groups**, not a guessed number of unexecuted
widget assertions: Linux offscreen Qt, X11, Wayland and native credential vault (4); Windows
PowerShell 5.1, PowerShell 7 and Qt/pipe/DPAPI runtime (3); macOS install/CLI and Qt/Cocoa/Keychain
runtime (2); Android APK, emulator, physical device and real Termux runtime (4).
**Total NOT RUN: 2 separate manual live-service groups** — real Google OAuth consent and a
real YouTube write. They were intentionally not automated or requested from the user.
The runtime verifier's Qt BLOCKED result is already one of those 13 groups, not an extra count.
Matrix cells are coverage indicators, not additional passed/blocked test counts.

### Executed Linux, failure/recovery and concurrency evidence

* **Installation/CLI:** real installer interruption after venv creation (isolated process group
  terminated), safe missing-dependency diagnostics, clean fresh installation, repeat reuse,
  path containing spaces/apostrophe, launch/doctor, damaged venv, ImportError/RuntimeError/OSError
  dependency faults, package uninstall retaining its data, shell syntax and PowerShell 7
  `$IsWindows` regression inspection. All installation copies and fixture environments were
  temporary. No shared/global environment or user data was uninstalled.
* **Foundation:** actual CLI subprocess help/version/start/stop/status/state/settings/doctor,
  config JSON/validation, fixed eight-phase roadmap, argparse, invalid cooldown rejection,
  non-TTY refusal and boolean-consent rejection. Tests check return codes/useful output/no
  application traceback. Startup/stop tests explicitly select persistent mode when required.
* **Comment/data:** all 141 existing Unicode/long/empty/whitespace/profile/draft/edit/rename/
  delete/preview/history/migration/CLI checks remain. Added temporary SQLite lock, interrupted
  transaction rollback, subsequent recovery/reopen, malformed/newer schema rejection without
  byte changes, unavailable parent path, retained editor and metadata-only history checks.
  No production database was touched. Schema remains 4, with no new migration.
* **Safety/API:** all 307 YouTube and 184 Safety checks execute with official transport/OAuth/
  keyring interactions mocked. Existing exact text/account/chat/stream/grant snapshots,
  expiry/one-use/cancel/edit/restart/reconnect, same-account/destination duplicate protection,
  cooldown, subprocess contention/two approved contenders and unknown-outcome protections
  remain. Added DNS/connection reset/read timeout/connect timeout/503/429/quota/corrupt-response
  write fixtures verify exactly one mocked call, durable outcome, consumed approval, restart
  IDLE, no leaked sentinel and no automatic retry. Connect timeout before transmission is
  conservatively rejected; potentially transmitted/ambiguous responses remain OUTCOME_UNKNOWN.
* **IPC/concurrency:** real authenticated sockets, same-capability clients with one review
  owner, competing owner refusal without endpoint replacement, duplicate request/nonce replay,
  wrong instance, missing/unknown fields, unknown command, deep/oversized frames and 0600
  endpoint/socket permissions. Existing frame expiry, invalid MAC, boolean approval flag,
  wrong response request nonce, consumed approval replay and queued activation tests remain.
  There is no independent request-ID field: instance/client identity and fresh request nonce
  bind each authenticated response; adding a user-provided approval boolean cannot authorize.
* **Process/recovery:** production core, disappeared socket, actual SIGKILL, stale metadata,
  explicit restart/instance-key rotation, old capability rejection, retained editor and IDLE /
  no approval restoration. Independent **protocol-client processes, not GUI panels**, were
  killed in both modes. Actual 15-second lease expiry left persistent availability stopped/
  alive and terminated manual availability. Explicit shutdown removed endpoint/socket and all
  tracked child processes were reaped. External CLI clients never renewed another actor's lease.
* **UI delayed state:** eight production Qt callback-logic assertions use AST-extracted actual
  code with stand-ins: late Start, stale review, pre-review status, stale error, current Stop,
  Stop acknowledgement ordering, same-generation old status and late unknown write outcome.
  These are **PASS — MOCKED**, not Qt widgets/headless rendering. Kotlin received the equivalent
  generation/observation fence and passed grammar only. A late confirmation outcome/error is
  still displayed after Stop; it is never hidden as if a transmitted write were recalled.

The required native 15-step panel workflow, real review expiry/control disabling, drag/focus,
stacking and repeated GUI open/close remain BLOCKED. Core/IPC/callback evidence does not replace
that workflow. Neither physical suspend/Doze nor Windows/macOS/Android crash semantics were
simulated and relabeled as native runtime success.

### Failures reproduced, classified and fixed

| Implementation defect | Reproduction / correction |
| --- | --- |
| Deep corrupt endpoint escaped as RecursionError | Bounded-but-deep JSON reproduced the exception. Endpoint/client parsing now returns a safe FloChat error; wire/deep-file regressions pass. |
| Malformed authenticated response escaped as KeyError | Missing `result` reproduced failure. Exact response fields, boolean `ok` and error type are checked before use; malformed reply variants fail closed. |
| Broken dependency escaped as startup traceback | Synthetic damaged binary import raised RuntimeError. Expected import/native-load failures are diagnosed with package/type/remediation, without arbitrary exception content. Three import-failure classes pass. |
| Late action/review replies overwrote newer UI intent | Actual callback reproduction displayed stale READY. Reply generations now fence obsolete presentation; expired/cancelled review replies cannot reopen controls. Core approval authority is unchanged. |
| Same-generation status sampled before Stop ack could display READY | Separate reproduction passed the generation check but rendered older state. Core supplies observation time; UI maintains a Stop/review observation floor, including the Android source counterpart. |
| Snapshot stop_requested flag remained cached false | Pre-change snapshot reproduction showed false with an actually stopped engine. The snapshot now reads the live engine stop flag; the new assertion passes. |

No unresolved critical implementation defect was found in the executed scope. The initial new
process test failed because its ordinary CLI Start used default manual mode and Stop correctly
ended that unattached owner; the test was corrected to explicitly request persistent mode, not
to relax the application assertion. A non-counted vault diagnostic initially used the wrong
constant name; backend discovery was rerun correctly without credential access. Lint/formatting
issues in the new test source were corrected. These development/test defects were not hidden
or counted as application passes. All affected suites were rerun on final source.

Production changes are limited to these corrections in `ipc.py`, `dependencies.py`, `panel.py`,
`runtime.py`, Android `OverlayService.kt`; `roadmap.py` now reports the approved active Phase 07.
The guard adds only the genuine new verifier to REQUIRED_FILES; its AST algorithm/exemptions
are unchanged. One Python owner/SafetyEngine/CommentManager/YouTube/SQLite, one desktop Qt
client and the thin Android companion remain. No new API, GUI framework or CLI architecture.

### Security, resources and cleanup result

No real credential was supplied to the tests, printed, persisted or exposed; no automated
Google comment was sent. Synthetic sensitive sentinels were absent from captured stdout/stderr,
returned errors/outcomes and database dumps. Local/safety history stays metadata-only; ordinary
editor/draft storage intentionally retains the user's text. The repository secret guard,
AST/dead-code/negative regression, syntax checks, Ruff and pip consistency all pass. Native
vault/DPAPI/Keystore confidentiality and real consent are **not certified** here. Found IPC /
import error-handling and stale-presentation defects were corrected; no tested path bypassed
SafetyEngine, created submission authority from IPC failure or automatically retried a write.

A lightweight final-source sample measured **0.304 s core startup**, **+20 KiB RSS**, **0 FD
growth** across 40 protocol-client lifecycle cycles, and **0.00 CPU seconds over a 2-second idle
sample**. Checks bound memory increase below 32 MiB, DB growth below 1 MiB and idle CPU below
0.5 s / 2 s; they are regression sentinels, not a benchmark/long-duration leak certification.
GUI resource tests remain blocked. No benchmarking dependency was introduced.

Temporary test homes, databases, corrupt dependency fixtures, interrupted-install copies,
synthetic pairing data and isolated grammar-tool environments are removed; tracked test children
are reaped. Final checks found no remaining test owner or per-user runtime socket. Normal
nonsecret advisory lock files do not prove liveness and hold no lock after the process exits.
Only the normal optional project venv is retained; no APK/build/screenshot/installer artifact,
extra documentation directory or secret-bearing log was added to the repository.

Git remains branch `arena/9dc86ddb-flochat`, HEAD `208a6b4`. All earlier uncommitted source is
preserved. **No commit, push, PR, publication, release, upload, visibility change or external
installer/binary distribution occurred.** Root README remains the sole report. Remaining
native environmental blockers prevent full cross-platform certification; they do not turn the
accepted Phase 06 status into a failure or authorize Phase 08.


---

## Phase 08 Final Release Audit & Certification Report

**PHASE 08 — NOT RELEASE READY**

Date: **2026-11-05**. This is the **final approved phase**, not the creation of another phase.
The eight phase names/order remain unchanged. This report supersedes historical release and
support claims, without erasing earlier evidence or changing Phase 06/07's accepted statuses.

### Final decision and release blocker

The executed Linux core is internally coherent and the reviewed submission architecture remains
fail-closed under its documented trusted-local-owner model. No known critical unauthorized-write
or credential-exposure defect remains in the executed scope. That is **not sufficient to certify
release**: **FloChat has no owner-selected project licence, licence text or corresponding package
licence declaration**, despite earlier reports explicitly requiring these before release.
An agent must not invent a licence grant or copyright owner. This is one unresolved
**release/legal-configuration blocker**, not a failed runtime assertion or an environmental test.
The owner must authorize appropriate terms and account for third-party redistribution obligations
before release can be reconsidered within Phase 08. Public/general distribution is **not approved**.

Native/Google verification gaps below remain material limitations, not proven implementation
failures and not silently converted into passes. Controlled local evaluation of the tested Linux
core is reasonable under these limits; all-platform/native/live-service certification is not.

### Eight-phase summary

| Phase | Approved name | Final status |
| --- | --- | --- |
| 01 | Foundation | Complete |
| 02 | CLI & Installation | Implementation complete; Linux installer executed, others unverified |
| 03 | Comment Manager | Complete locally; runtime evidence Linux-only |
| 04 | YouTube Integration | Implemented; live OAuth/service verification blocked/not run |
| 05 | Safety Engine | Implemented and tested; real write not run |
| 06 | Floating & Background Engine | **IMPLEMENTED, NATIVE VERIFICATION PENDING** |
| 07 | Cross-Platform Testing | **TESTED, PLATFORM VERIFICATION PARTIALLY BLOCKED** |
| 08 | Final Release | **NOT RELEASE READY** — licence unresolved |

There are no approved phases after Phase 08. No feature expansion, argparse migration, new GUI
framework, second submission engine, new API, telemetry, cloud service or unattended posting was added.

### Audit baseline, environment and preservation

Inspected actual complete file inventory, Git status/HEAD, root README, Python/native source,
configuration/environment paths, schemas/migrations, installed metadata and dependency use,
install/launch scripts, CLI declarations, OAuth/REST/approval paths, IPC/lifecycle and verifiers.
A temporary source archive enabled preservation comparison. Existing dirty Phase 02–07 work
was retained. Only correctness/security/release-metadata changes described below were made.

Environment remained Debian 12/Linux 6.1.158+ x86_64/glibc 2.36; Python 3.11.2, SQLite 3.40.1,
Node 22.22.3 (unused). PySide6/Qt 6.12.0 installed but QtWidgets blocked by absent GL/EGL,
xkbcommon/D-Bus libraries and no DISPLAY/WAYLAND/Xorg/Xvfb. No Windows/macOS host, PowerShell,
JDK/Gradle/SDK/adb/emulator/device. Real keyring backend remains unavailable/fail; Google hosts
are outside the network allowlist. Tooling used isolated temporary environments; no OS package,
root operation, execution-policy change, security bypass or native binary fabrication occurred.

### Correctness/security fixes and evidence

| Finding | Correction and regression |
| --- | --- |
| Invalid UTF-8 or deeply nested config produced raw tracebacks | Controlled ConfigurationError; 64 KiB config bound; invalid path types/NUL/surrogates rejected; files retained unchanged |
| Relative credential-path environment mistake echoed its supplied value | Generic path validation messages, no raw invalid value in settings/doctor/status/state errors |
| Doctor could return exit 0 after rejecting an environment setting and using defaults | Explicit failed configuration finding and nonzero exit; skip storage rather than initialize/migrate an unrelated fallback database |
| Deep JSON from OAuth client/API parsing could escape expected error handling | Safe OAuth/API errors; deep write-response parsing records OUTCOME_UNKNOWN, consumes consent and never retries |
| Ordinary status included live editor/profile text through its runtime snapshot | Ordinary status now reports editor count/redaction metadata only; authenticated UI still receives required editor content |
| Old bundled pip/setuptools and the permitted requests floor carried published advisories | Installer requires pip >=26.2 and fails closed; isolated build setuptools >=84.1.0; requests floor raised to >=2.33.0 in package and diagnostic requirements; installed tools 26.3/84.2.1 |
| Version was duplicated across Python/package/Android metadata | Existing 0.1.0 remains authoritative in flochat.__version__; setuptools dynamic version and Gradle versionName read it; no invented version/tag |

Full regression suites were rerun after the substantive correction batch. The first new final-audit
input test accidentally let the harness's FLOCHAT_DB override its invalid db_path fixture; this
was a test setup error, not evidence of a bad config passing validation. It was corrected to test
the non-overridden path field, retaining all refusal assertions, and the full suite passed again.
The initial broad binary scan's pattern flags were triaged rather than hidden; see security below.

### Exact final verification counts

| Ownership | Unique final passing assertions |
| --- | ---: |
| Phase 01 | 28 |
| Phase 02 | 29 |
| Phase 03 | 141 |
| Phase 04 | 307 |
| Phase 05 | 184 |
| Phase 06 | 83 |
| Phase 07 | 119 |
| Phase 08-specific | 40 |
| **Total passed** | **931** |
| **Final failed assertions** | **0** |

The 40 new checks comprise **28 real local/CLI, 10 mocked, 2 static** assertions. The extended
existing platform verifier contributes 216 (28 + 29 + 119 + 40); the four unchanged suites
contribute 715. No historical/repeated run, lint gate, scan, matrix cell, wheel build or lifecycle
cycle is added to that total. Passing assertions are not 931 native or live-service tests.

**BLOCKED: 13 native scenario groups**, unchanged: Linux offscreen Qt, X11, Wayland, native
vault (4); Windows PowerShell 5.1, PowerShell 7, Qt/pipe/DPAPI (3); macOS install/CLI,
Qt/Cocoa/Keychain (2); Android APK, emulator, physical device, real Termux (4).
**NOT RUN: 2 live-service groups**, real Google OAuth consent and real YouTube write.
The licence blocker is separate from these test counts. The runtime suite's Qt block is already
included, not counted twice. Gates passed: repository/secret/dead-code/syntax guard, Ruff lint
and format, pip consistency, Bash/dash syntax, seven native/script grammar parses and manifest
inspection. Grammar and wheel metadata checks never certify an Android or native UI runtime.

Run the complete verification using a normal isolated development environment:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade 'pip>=26.2'
.venv/bin/python -m pip install -e '.[dev,desktop]'
# Activate .venv, or use its python/ruff explicitly:
.venv/bin/python scripts/verify_comments.py
.venv/bin/python scripts/verify_youtube.py
.venv/bin/python scripts/verify_safety.py
.venv/bin/python scripts/verify_runtime.py
.venv/bin/python scripts/verify_platforms.py
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/check_repository.py
.venv/bin/ruff check --no-cache .
.venv/bin/ruff format --check --no-cache .
.venv/bin/python -m pip check
# Parse each shell file separately:
for f in install.sh start.sh scripts/install_lib.sh; do bash -n "$f"; done
```

Desktop is optional for normal use. Windows equivalents need a real Windows environment;
Phase 07 process/install probes intentionally refuse to simulate another OS as Linux success.
Remove generated caches/metadata before final hygiene checks; venvs are local tools, never release files.

### Final high-value failure injection coverage

All sixteen required cases executed again within the counted existing/new suites, not as a
second set of claimed passes:

| Failure | Executed evidence / safe result |
| --- | --- |
| Malformed IPC | Runtime/platform raw authenticated frames; refusal before dispatch |
| Malformed API response | YouTube/safety fixtures plus new deep JSON; no acceptance, uncertain writes protected |
| Expired approval | Safety mutation cases and wall/monotonic runtime expiry; no POST |
| Replayed approval | Safety/runtime consumed challenge; no second POST |
| Changed comment after approval | Exact request/editor snapshot mismatch; no POST |
| Changed destination after approval | Chat/selection/account/grant final comparison; no POST |
| Unknown YouTube outcome | Timeouts/reset/deep successful-response parse; durable unknown, no retry |
| Duplicate submission | Persistent account/chat/digest reservation and legacy comparison; refusal |
| Cooldown violation | Persisted wall/monotonic policy and real-process contention; refusal |
| Stale capability | Restart rotates actual endpoint key; old authenticated frame rejected |
| Stale owner | Competing process cannot replace owner; wrong instance/old actor refused |
| Corrupted endpoint metadata | Deep/duplicate/malformed metadata; controlled no-trustworthy-endpoint error |
| Broken dependency | ImportError/RuntimeError/OSError injection; safe exit 4, no sentinel/traceback |
| Database failure | Temporary lock/corruption/newer schema/rollback tests; no destructive repair or partial write |
| Process termination | Actual Linux SIGKILL/client death; stale status, lost-lease stop; no approval recovery |
| Restart | Actual new process/instance; IDLE, retained editor, no auto-submit or restored approval |

No live comment was used for failure injection. Native crash/Doze/platform-vault semantics
remain blocked; Linux process evidence is not relabeled as Android/Windows/macOS behavior.

### Final security and submission-path review

* **Credentials:** repository guard plus broader source/generated/venv binary scan inspected
  token/key signatures and accidental env/runtime files. No actual credential material was
  identified. The broad scan flagged **18 PEM header literals** in nine third-party parser/TLS
  source/binary/cache files (no complete key blocks) and one AWS-ID-shaped substring in Ruff's
  concatenated Unicode name table. These **19 pattern candidates** were reviewed as false
  positives, not quietly excluded or reported as real leaks. No candidate values were printed.
  Ordinary source/generated release-tree scan is clean; no .env, client JSON, token dump or
  secret-bearing fixture/log is a deliverable. Pattern scanning is not proof that no possible
  secret can exist. No real vault credentials were read/written by this audit.
* **OAuth:** readonly default vs explicit force-ssl new consent, Google-only client endpoints,
  official InstalledAppFlow PKCE/state checks, loopback-only ephemeral callback/180-second wait,
  20-second transport connect/read timeout, no redirects, cancellation and safe errors reviewed.
  Installed library's callback logging uses logging, suppressed during sensitive calls. Approved
  backend identity is restricted to Secret Service/Windows Vault/macOS Keychain; load/save/delete
  failures never fall back to plaintext. Disconnect selection cleanup/local deletion and optional
  revocation are distinct. Keyring and SQLite are not one distributed transaction; failures are
  surfaced, not described as complete cleanup. Real consent/vault success remains uncertified.
* **Official API:** fixed HTTPS resources only; no browser automation, cookies, scraping, CAPTCHA
  bypass or arbitrary endpoint. Account/chat IDs and response shapes validated; quota/rate errors
  stop, never poll/retry aggressively. TLS remains enabled and trust_env false for credential HTTP.
* **Sole write authority:** CLI/native/IPC -> CoreRuntime -> comments.submit -> SafetyEngine.execute
  -> the single official liveChat/messages POST. The retained standalone SafetyEngine console
  also calls that same gate; it is not a separate transport. No other supplied component inserts.
  Valid session, process ownership, exact normalized text, account/chat/video/selection/editor/grant
  snapshots, write scope, unexpired one-use memory approval, literal consent and final state are
  checked before atomic reservation and transport. Booleans, IPC capability or Ready alone cannot
  authorize. There is no unattended/bulk/repeat scheduler.
* **Uncertain writes:** reservation/consumption commits before transport; malformed success or
  potentially transmitted failure is OUTCOME_UNKNOWN. Crash-left IN_PROGRESS reconciles to unknown
  before another attempt. No reconnect/restart/resume/refresh/background retry. Stop before the
  atomic transport boundary prevents sending; after it, cancellation cannot recall transmission.
  Explicit human outcome review stops the session and does not erase duplicate protection.
* **IPC:** HMAC-SHA256 per-run capability, exact envelopes/commands, timestamp/nonce/replay cache,
  instance/client and response-request nonce binding; bounded messages/queue/clients; user-private
  endpoint/socket and local transports. Malformed responses fail as controlled errors. DPAPI/pipe
  and Android loopback/Keystore are source-reviewed only. HMAC/base64 is not encryption and a
  trusted same-user/root compromise is outside this threat boundary. No Google secrets enter IPC.
* **Background/database:** persistent availability cannot submit by itself. Leases, queue intent
  invalidation and stale UI observation fences remain. One schema-4 database; additive checked
  migrations, parameterized values, BEGIN IMMEDIATE, rollback and separate cooperating-process
  locks. Incompatible/corrupt files are not silently deleted. Strict schema is not protection
  against a malicious owner replacing code/data. Network filesystems are not certified.

### Privacy: actual local storage and diagnostics

| Class | Actual storage/output |
| --- | --- |
| User content | Singleton username, editor full text and optional username/draft link, saved draft titles/text/username/timestamps in SQLite |
| Historical legacy content | Existing comment_history text rows are retained if supplied by an older database; current code does not populate that table |
| Event metadata | local_history and safety_events: IDs, times, event/decision, relevant draft/account/chat/attempt IDs, character counts; no text snapshots |
| Protection metadata | safety_attempts: approval/attempt identity, account/chat, canonical-content hash, count, times, state/category/API ID/resolution; safety_clock high-water time |
| Selection/usage | youtube_selection video/chat/title/channel/time; youtube_usage UTC operation-attempt counters, not official remaining quota |
| Configuration | Optional config.json settings/paths; environment takes precedence; .env not auto-loaded; no credential values permitted |
| Secrets | Owner's external Desktop client JSON; Google credentials only in approved OS keyring, shared per OS user; no plaintext token-file fallback |
| Local IPC | Ephemeral endpoint/per-run capability, private socket, advisory locks; Android pairing encrypted in companion's private preferences via Keystore |
| Diagnostics | Paths/platform/dependency/schema/attempt metadata; ordinary status redacts editor content; settings intentionally shows configured file paths, never file contents |

Authenticated UI/protocol `status` and explicit `panel status` can intentionally display current
editor content needed by controls; do not share those payloads as sanitized bug reports. Ordinary
`status`, `state`, `settings`, `doctor` were checked with synthetic sensitive/error inputs. No
OAuth response/token logging, telemetry, analytics, crash upload, cloud sync or remote history.
Diagnostic paths/IDs and explicit editor output remain personal. Existing DBs are not retroactively
encrypted/permission-repaired. history clear removes event logs, **not** editor/drafts/profile,
legacy content, duplicate/cooldown/unknown protection or keyring secrets. Deletion is not erasure.

### Dependency, licensing and compatibility audit

All five direct dependencies are imported and used; none is safe to remove merely for cosmetics.
Runtime constraints stay bounded by major version, not exact application lockfile pins. Android
AGP 8.7.3/Kotlin 2.0.21 and SDK/JVM requirements are explicit build-time constraints; Gradle build
compatibility remains unverified. No framework/dependency was added to the application.

| Dependency | Installed version | Role / licence metadata |
| --- | --- | --- |
| pydantic | 2.14.2 | Runtime config validation; MIT |
| google-auth | 2.62.1 | Runtime official credentials/refresh; Apache-2.0 |
| google-auth-oauthlib | 1.5.0 | Runtime installed-app PKCE OAuth; Apache-2.0 |
| requests | 2.34.2 | Runtime bounded official HTTPS; Apache-2.0 |
| keyring | 25.7.0 | Runtime approved OS-vault boundary; MIT |
| PySide6-Essentials / shiboken6 | 6.12.0 / 6.12.0 | Optional desktop binding; LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only |
| Ruff | 0.17.3 | Optional development lint/format; MIT |
| pip / setuptools | 26.3 / 84.2.1 | Local install/build tools, not app imports; MIT / MIT |

Transitive installed dependency inventory (no added direct dependency):

| Packages and versions | Why present / licence metadata |
| --- | --- |
| annotated-types 0.8.0; pydantic_core 2.50.2; typing-inspection 0.4.5 | Pydantic validation; MIT |
| typing_extensions 4.16.0 | Shared typing support; PSF-2.0 |
| requests-oauthlib 2.0.0; oauthlib 4.0.1 | Official flow's OAuth HTTP/state/PKCE; ISC / BSD-3-Clause |
| certifi 2026.10.23; charset-normalizer 3.5.2; idna 3.20; urllib3 2.8.0 | TLS roots/HTTP encoding/IDs/transport; MPL-2.0 / MIT / BSD-3-Clause / MIT |
| pyasn1 0.6.5; pyasn1_modules 0.4.2 | Google cryptographic credential support; BSD-2-Clause / BSD |
| SecretStorage 3.5.0; jeepney 0.9.0 | Linux keyring backend/D-Bus; BSD-3-Clause / MIT |
| cryptography 50.0.2; cffi 2.1.1; pycparser 3.12 | Vault cryptography/FFI; Apache-2.0 OR BSD-3-Clause / MIT-0 / BSD-3-Clause |
| importlib_metadata 10.1.0; zipp 4.1.2 | Keyring plugin metadata; Apache-2.0 / MIT |
| jaraco.classes 3.4.0; jaraco.context 6.1.2; jaraco.functools 4.6.0; more-itertools 11.2.1; backports.tarfile 1.2.0 | Keyring helpers; MIT (some installed metadata requires consulting upstream licence files) |

Licences are metadata/source observations, not legal certification. FloChat's own licence is
still unset. A source-clone workflow does not certify third-party binary redistribution rights;
Qt LGPL/GPL obligations, notices, linking/relinking requirements and signing/notarization need
owner review for any later binary distribution. Platform-conditional keyring dependencies differ
on Windows/macOS; Linux's installed list is not their certified dependency closure.

The PyPI per-version JSON advisory snapshot was queried for **34 unique installed third-party
distributions** at audit time. Initially pip 23.0.1 and setuptools 66.1.1 had advisory entries;
these were build/install tools, not an observed FloChat exploit. Updated tools and source minimums
address returned fixed-version floors (pip 26.2, setuptools 84.1.0). Final snapshot returned zero
entries for installed versions. Source endpoints include
`https://pypi.org/pypi/pip/23.0.1/json`,
`https://pypi.org/pypi/setuptools/66.1.1/json` and each installed name/version's equivalent.
Declared direct minimum versions were also checked. requests 2.32.4 returned
GHSA-gc5v-m9x4-r6x2/PYSEC-2026-2275, fixed in 2.33.0; package and diagnostic floors
were raised together to >=2.33.0. Installed requests 2.34.2 was not flagged. The other queried
direct/optional/tool minima returned no entries. Aliases were not counted as independent vulnerabilities. This limited feed/metadata check is
**not** a complete vulnerability audit or a vulnerability-free promise; it excludes a certified
OS/Qt native-library, vendored packaging-tool component and Android build-plugin advisory assessment. Reaudit before any release.

Python >=3.10 is declared; only 3.11.2 executed. Qt wheel/native requirements vary by OS/CPU and
Python; an available wheel is not a working panel. pip check passed, but it proves dependency
constraint consistency only, not support/security. No unused framework or speculative adapter
was removed; the unchanged AST guard and negative orphan test remain effective heuristics.

### Final platform matrix and material limitations

The full 24-area x 4-platform Phase 07 matrix remains applicable; no cell was promoted on source
presence or mocks. Final summary:

| Scope | Linux | Windows | macOS | Android |
| --- | --- | --- | --- | --- |
| Shared core/CLI/SQLite/local IPC | PASS — REAL RUNTIME | BLOCKED | BLOCKED | BLOCKED |
| Native floating GUI/lifecycle | BLOCKED | BLOCKED | BLOCKED | BLOCKED |
| Installer | PASS — REAL RUNTIME | PASS — STATIC | PASS — STATIC | PASS — STATIC |
| Platform source/configuration | PASS — STATIC | PASS — STATIC | PASS — STATIC | PASS — STATIC |
| Native OS credential-vault success | BLOCKED | BLOCKED | BLOCKED | BLOCKED |

Android APK build, emulator, device and real Termux remain BLOCKED. Real Google consent/write
remain NOT RUN on every platform; no extra test groups are inferred from summary matrix cells.
Implemented means source exists; STATIC means inspection/grammar; MOCKED means synthetic
behavior; REAL RUNTIME means actual target execution; BLOCKED means missing prerequisites.
No PHYSICAL DEVICE, EMULATOR or HEADLESS GUI success occurred. The missing licence, current
Known Limitations list, OS/Qt/build/vault gaps, live permissions/quota/write uncertainty, broad
OAuth scope, synchronous transport/cancellation limits and trusted-local-owner boundary are
material. No universal platform-support, spam-policy-compliance or legal certification is made.

### Artifacts, hygiene and Git state

**Actual release-ready distributable artifacts: none.** Existing source, installers and package
configuration are retained as audited implementation, not published/signed artifacts. A real
core-only 0.1.0 wheel was built privately and inspected (20 modules, matching version, no runtime
DB/env/key/APK); it was deleted, not delivered. The wheel does not package a native companion or
claim installer/native UI certification. No APK, tag, release archive or signing certificate exists.
No unnecessary GitHub workflow or release configuration was invented to imply a delivery process.

Temporary homes, DBs, interrupted installations, synthetic credentials, parser environments,
wheel/build outputs, caches, source egg metadata and audit scripts/archive were cleaned. The
local development venv used for checks was removed after verification, not included in delivery.
Test children were reaped and no FloChat test owner/socket remained. Root README is still the
sole report; no docs/reports/examples/phase-08 directory, extra README or scratch test was added.

Branch **arena/9dc86ddb-flochat**, HEAD **208a6b4**, unchanged. Existing README modification and
untracked implementation remain intentionally uncommitted; only README is in the existing HEAD.
A future owner-authorized Git delivery must include reviewed source, not assume this old commit
contains the tested tree. Working-tree hygiene does not mean a clean Git index or published build.
**No commit, push, PR, publication, upload, release, tag or visibility change occurred.**

**Certification conclusion:** core evaluation evidence is strong and reviewed safety boundaries
are intact, but FloChat is **not appropriate for public/general release yet** because project
licensing is unresolved. Owner authorization/licence work and a fresh release review are required;
any eventual platform claims must retain the documented native/live-service verification limits.
