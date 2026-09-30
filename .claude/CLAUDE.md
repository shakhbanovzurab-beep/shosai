# Whisperer

Whisperer is an AI workspace. It brings a person's knowledge, meetings, documents, tasks, calendar, communications and AI into one system, so they can keep what they know, understand information and automate routine work.

**Design it as a Swiss army knife.** Every new capability is another blade of one tool, not a separate tool. Features share the user's context and strengthen each other. They integrate through contracts, events and shared context, never through one feature reaching into another's internals.

`whisperer-v2` is a full, rethought rewrite of the earlier `whisperer` project. Rules below describe the target state. Carry over behaviour and lessons from the old code; do not assume its file or function names exist here.

## Order of authority

When instructions conflict, the higher one wins:

1. A direct instruction from the user in the current conversation.
2. This file.
3. A skill that this file names as mandatory (see [Mandatory skills](#mandatory-skills)).
4. Any other skill.
5. General habit.

A skill's commands are replaced by this file's commands where they differ. Example: the `react-doctor` skill says `npx react-doctor@latest`; here the rule is `npm run doctor`.

## Language

| What | Language |
|---|---|
| This file, skills, anything else a coding agent reads as instructions | English |
| Everything a language model reads in the product (see [Prompts](#prompts-and-model-facing-text)) | English |
| Code comments and docstrings | Russian — they are for the engineer |
| Log messages | Russian; field names and event keys are English identifiers |
| Text shown to users (UI, emails, HTTP errors) | The user's language, through i18n |

Do not write comments in English because this file is in English.

## Production by default

All code written for Whisperer is production code. Every change must be ready to run in production once its checks pass.

Not allowed: temporary solutions, a `TODO` instead of an implementation, "fix later", demo or MVP shortcuts, technical debt without a stated reason, experimental architecture without need.

Every change must be safe, measurable and of real engineering value. No changes for looks, no technology swaps without an objective gain, no refactoring without an architectural reason.

## Architecture

**Feature-first vertical slices are the only allowed structure, in both `backend/` and `frontend/`.**

- A slice holds everything its feature needs. Backend: models, schemas, services, endpoints. Frontend: components, hooks, state, API calls. The two sides mirror each other by feature name.
- Clean Architecture sets the direction of dependencies **inside** a slice: domain logic does not depend on the framework, the database or transport.
- Slices talk to each other only through explicit contracts: a public interface, an event, or the HTTP API. `import-linter` enforces the boundaries on the backend.

**File length.** A hand-written source file is at most **300 lines in `backend/`** and **200 lines in `frontend/`**, counting every line. Generated files and lock files are exempt. Split the file by responsibility before it reaches the limit.

### Engineering principles

| Principle | What it means in code |
|---|---|
| Async first | I/O is `async`; nothing blocks the event loop. |
| API first / contract first | The OpenAPI contract is designed before the implementation and is the source for clients. |
| Feature first / vertical slice | Organise by business feature, not by technical layer. |
| Boundaries first | Decide a slice's public surface before writing its internals. |
| Dependency injection | Dependencies are passed in, not imported as globals or created inline. |
| Strong typing | Full type annotations; no untyped escape hatches. |
| SOLID, Clean Architecture | Small single-purpose units; dependencies point inward. |
| Explicit over magic | No hidden behaviour, implicit globals or import-time side effects. |
| Event-driven where justified | Use events when producers and consumers must be decoupled, not by default. |
| Idempotency by design | A repeated request, job or event produces the same result. |
| Backward compatibility, reversible changes | See [Compatibility](#compatibility). Every change can be rolled back. |
| Fail fast, fail explicitly | Reject invalid state at the boundary; never continue silently. |
| Error handling by design | See [Error handling](#error-handling). |
| Data integrity first | Constraints live in PostgreSQL, not only in application code. |
| Testing by design | Code is written to be testable; tests ship with it. |
| Security first | See [Security](#security). |
| Performance by design | See [Performance](#performance). |
| Observability by default | See [Logging and observability](#logging-and-observability). |

## Technology stack

"Latest stable" is the rule for choosing a version when a dependency is added. After that the exact version is pinned in the lock file or image tag and changes only through a deliberate upgrade (see [Dependencies](#dependencies)).

| Area | Technology | Version | Purpose |
|---|---|---|---|
| **Backend** | Python | 3.14 | Backend language |
| | FastAPI | latest stable | Async API |
| | Pydantic | v2 | Schemas, validation, DTOs |
| | pydantic-settings | latest stable | Configuration |
| | SQLAlchemy (async) | 2.x | ORM and database access |
| | Alembic | latest stable | Migrations |
| | uv | latest stable | Package and project management |
| | HTTPX | latest stable | Outbound HTTP calls |
| | import-linter | latest stable | Architecture boundary checks |
| **Frontend** | React | 19.3 | UI |
| | TypeScript | latest stable | Typing |
| | Vite | latest stable | Build and dev tooling |
| | npm | — | Package management and scripts |
| **Data** | PostgreSQL | latest supported | Source of truth |
| | Qdrant | latest stable | Vector database, RAG |
| | Redis | latest stable | Cache, locks, rate limits, ephemeral state |
| | S3-compatible storage | — | Files, recordings, documents |
| **Async work** | TaskIQ | latest stable | Background jobs and workers |
| **AI** | Leo | — | Whisperer's AI agent |
| | LangGraph | latest stable | Agent orchestration, stateful workflows |
| | MCP | latest spec | Tool and external-agent integration |
| **Observability** | structlog | latest stable | Structured logging |
| | OpenTelemetry | latest stable | Tracing and metrics |
| | Prometheus | latest stable | Metrics storage and alerting |
| | Loki | latest stable | Log storage and search |
| | Tempo | latest stable | Trace storage |
| | Grafana | latest stable | Dashboards for metrics, logs and traces |
| **Testing** | pytest, pytest-cov | latest stable | Tests and coverage |
| | Hypothesis | latest stable | Property-based tests |
| **Code quality** | Ruff | latest stable | Lint and formatting |
| | mypy | latest stable | Static typing |
| | Radon, Vulture | latest stable | Complexity, dead code |
| **Security** | Bandit, Semgrep | latest stable | Security and code-pattern checks |
| | pip-audit | latest stable | Dependency vulnerabilities |
| **Infrastructure** | Docker, Docker Compose | latest stable | Containers; local and single-server orchestration |
| | NGINX | latest stable | Reverse proxy, TLS, static assets |
| | GitHub Actions | — | CI/CD |
| **Contracts and docs** | OpenAPI | 3.x | Contract between backend, frontend and clients |
| | ADR | — | Record of architectural decisions |

## Mandatory skills

Load and follow these skills whenever you work in the zone. This is not optional.

| Zone | Skills |
|---|---|
| Backend (`backend/`) | `fastapi` |
| Frontend (`frontend/`) | `vercel-react-best-practices`, `vercel-composition-patterns`, `vercel-react-view-transitions`, `web-design-guidelines` |
| Docker and Compose | `docker-project-foundations`, `docker-build-strategies`, `docker-compose-patterns`, `docker-destructive-guardrails` |
| Python code health | `python-doctor` |
| React code health | `react-doctor` |
| Public pages, SEO, AI search visibility | [docs/seo/STRATEGY.md](../docs/seo/STRATEGY.md) and the `seo-*` skills mapped in its section 17 |

The `docker-agent-*` and `docker-sandboxes-*` skills apply only if Docker Agent or Docker Sandboxes are actually used.

The FastAPI skill is the primary engineering standard for the backend. Where it conflicts with habit, the skill wins.

## Backend

### Performance focus

CPU, memory, the event loop, PostgreSQL, Redis, SQLAlchemy, network I/O, connection pools, TaskIQ, concurrency, locks, serialization, horizontal scaling.

Judge every architectural decision on performance, scalability, fault tolerance and operational readiness.

## Frontend

The frontend is one workspace. The user never feels a switch between features; each capability reads as the natural continuation of the previous one. The interface is fast, consistent and predictable, and keeps cognitive load low.

### UX principles

- Simplicity over feature count.
- Consistency over originality.
- The fewest actions to reach a result.
- Every new capability fits the existing interface. It never feels like a separate app.
- The interface helps the user focus on work, not on learning the interface.
- Every action is fast, clear and predictable.
- Any added complexity must have measurable value for the user.

### React practices

Follow the Vercel skills. The rules that matter most here:

- **Data fetching.** No request waterfalls; run independent requests in parallel.
- **Bundle.** No barrel files. Import directly; load heavy modules dynamically.
- **Rendering.** Do not add `useMemo` or `useCallback` without a profile that shows the need. Hoist static values and heavy subtrees out of render.
- **Composition.** No components driven by many boolean flags. Build with composition, `children` slots and compound components instead of deep prop drilling. Keep data and logic containers separate from presentational components.
- **AI output.** Streamed model output renders smoothly, without layout shift, and stays accessible.

The frontend is a Vite single-page app. Guidance in the Vercel skills that assumes Next.js or React Server Components does not apply unless server rendering is adopted (see [Undecided](#undecided)).

### Performance focus

Bundle size, re-renders, memory, network requests, lazy loading, code splitting, FPS, scalability of the interface, and Core Web Vitals. Targets: LCP ≤ 2.5 s, INP ≤ 200 ms, CLS ≤ 0.1.

## Performance

Whisperer is designed for an audience of millions, deployed on a single server for now. Performance is an architectural requirement, not a later optimization phase.

**Bottleneck audit is always on.** While building any feature, look for the places that will not hold under load and remove them.

Optimize against a measurement, not a feeling. A performance change states what was measured before and after. This is what separates required performance work from the "changes for looks" that are not allowed.

## Engineering rules

### API design

HTTP APIs follow the FastAPI skill and REST conventions: predictable URLs, uniformity, strict typing, correct status codes, idempotency where needed, pagination for large collections, one error format across the API, full OpenAPI compatibility.

### Compatibility

Do not change a public API, event, contract or data model without clear need and a migration plan. A change is either backward compatible or comes with a safe migration strategy. Public APIs are stable and documented.

### Naming

Names are clear, unambiguous and carry business meaning. A name explains the purpose of the thing without a comment.

Never: `utils2`, `helpers_new`, `service_final`, `temp`, `test123`, `data2`, `new_service`.

### Error handling

Handle every error explicitly. Never use a bare `except`, swallow an exception or ignore an error.

Every error is logged, carries enough information to diagnose, reveals nothing confidential to the user, and is handled at the right level of the application.

### Logging and observability

Every new feature is observable: structured logs in one format, correct log levels, metrics, tracing, OpenTelemetry where applicable.

Never use `print()` in place of the logging system.

### Configuration

All configuration comes from environment variables, loaded through `pydantic-settings`. No configuration in source code, no secrets in Git, no undocumented local settings. Every new variable is documented with its purpose.

### Dependencies

- Use stable versions only.
- Before a major or minor upgrade: read the changelog, check breaking changes, confirm compatibility with other dependencies, run the full test suite.
- Never upgrade "to latest" without that analysis.
- Before adding a library, check that an existing dependency does not already do the job.

### Documentation

A significant architectural change updates the project documentation in the same task. Record architectural decisions as ADRs.

## Prompts and model-facing text

**Everything a language model reads is written in English only.**

A Russian instruction is a language signal: the model takes it as a cue to answer in Russian. An English-speaking user then gets Russian fragments, and the agent's behaviour depends on the language of the instruction rather than the language of the person. Weaker models also follow English instructions more precisely.

**What counts as a prompt** — wider than it seems:

- system instructions for every channel and role;
- the `name` and `description` of every tool;
- the `description` of every parameter and every `enum` value;
- **what a tool returns** — labels, statuses and hints inside the result. The model reads a tool result exactly like a prompt and repeats it to the user. This is the item most often missed;
- error texts returned to the model;
- service markers the server inserts into a thread;
- MCP server instructions, which an external client's model reads;
- prompts for auxiliary models (vision, transcription, translation, mind maps, catalog descriptions).

**What is not a prompt:** comments, docstrings, logs, and text shown to users through i18n.

**Instruction language is not output language.** The prompt is English; the language the model must answer in is a separate product decision stated explicitly in the prompt, for example "answer in the language of the user's latest message".

Language names written in their own language (`Русский`, `日本語`) are legitimate values, not instructions. Do not "fix" them because a search for non-Latin characters finds them. The same holds for Russian entries in multilingual keyword lists: Russian is one of the platform's 16 languages.

**No branch of logic depends on language.** Keyword lists, word-based regular expressions and comparisons with literals such as "yes" and "no" cover all 16 platform languages or do not exist. Otherwise the agent's abilities differ by the user's language.

**Enforced by a test, not by trust.** A test asserts that every model-facing string is English. A new prompt is registered in that test in the same commit that adds it. The list is maintained by hand, so an unregistered prompt is unprotected.

## Testing

New behaviour ships with tests. If a test is genuinely not feasible, say so and give the reason; do not skip it silently.

Tests are reproducible, independent of each other and have no effect on other tests.

### Test database

- Integration tests use a separate PostgreSQL server with the `pgvector` extension.
- Connection parameters come only from environment variables.
- **Never run tests against a production database.** Treat `DATABASE_URL` in `backend/.env` as production. Tests use their own variables and must refuse to start if the target is not a test database.
- Several prepared test databases exist so agents can run in parallel. Before a run, claim one that no other agent is using.

### Clean up after every run

Return the test database to its initial state. Leave nothing behind: no test users, organizations, documents, files, tasks, events, messages or temporary records.

If a run changes the schema (DDL, Alembic changes, tables, indexes, extensions, functions, triggers, views), roll all of it back. The schema afterwards must match the initial state exactly.

The test environment is always ready for the next run with no manual step. If cleanup is impossible, tell the user explicitly.

## Checks

Three levels, in this order. Do not repeat a lower level's work at a higher one.

**1. After each stage of development**

- The project builds and the application starts.
- No import errors.
- Typing is intact.
- No regressions.
- The new code fits the architecture.

**2. Before declaring the work finished**

- All existing tests pass.
- Migrations are correct, if any changed.
- The test database is clean.
- Self-review is done (see [Self-review](#self-review)).

**3. Code health gates — once, after the task is complete**

Not after every edit. The changed zone decides what runs:

| Changed files | Run |
|---|---|
| Only `backend/` | Backend gate |
| Only `frontend/` | Frontend gate |
| Both | Backend gate, then frontend gate |
| Neither | Nothing |

| Gate | Command, from the zone's directory | Pass condition |
|---|---|---|
| Backend | `uv run python-doctor . --score` | prints `100` |
| | `uv run mypy .` | no errors, in strict mode |
| Frontend | `npm run doctor -- --score` | prints `100` |

`npm run doctor` gives the full report. Both doctors run at the version pinned in the project (`pyproject.toml`, `package.json`). Never call `npx react-doctor@latest` or a globally installed doctor: an unpinned version makes the gate unreproducible.

Code is not finished until every gate that applies passes. Fix the code rather than silencing rules. If a gate cannot be passed, list the remaining findings and why instead of reporting the target as met.

No hook automates these gates yet. Run them yourself.

## Self-review

Before finishing an implementation, review your own change for: architecture, performance, security, readability, typing, error handling, duplication, feature-first structure, compliance with this file, and compliance with the mandatory skills.

## Git workflow

Development is linear and happens **only on `main`**.

- **Commit only after the user says «Принято».** No commits without that explicit approval.
- Never create a branch or a git worktree.
- One logically complete task is one atomic commit. Do not combine independent changes.

### Push is part of the commit

**A commit is done only after `git push origin main`.** Local `main` must equal `origin/main` when a task ends. Production is built from the working tree, so an unpushed commit is code running in production that exists nowhere else.

```bash
git add <paths>
git commit <paths>
git push origin main
git status -sb      # expect "## main...origin/main" with no "ahead"
```

- Push immediately after committing, not at the end of the day.
- **Commit only your own paths, listed explicitly.** `git add .`, `git add -A` and `git commit -a` are forbidden: parallel sessions have unfinished work in the same tree.
- `--force` and `--force-with-lease` on `main` are forbidden.
- If the push is rejected, run `git pull --rebase origin main` and push again. Never merge.

## Security

Security is a requirement of every feature.

Never:

- log passwords, API keys, JWTs, access tokens or refresh tokens;
- hardcode a secret or keep one in source code;
- put secrets, passwords or connection parameters in this file;
- disable a security check for convenience.

Secrets live only in environment variables.

## Docker hygiene

Keep the Docker environment tidy without losing the ability to roll back quickly.

- Do not remove a Docker resource without knowing whether the project uses it.
- No aggressive cleanup (`docker system prune -a`, removing all images or volumes) without clear need.
- Before removing anything, confirm it is unused and not needed for a fast rollback.
- After a successful migration or refactoring, remove only what is obsolete and certainly unused: old containers, dangling images, networks, build cache.
- Always keep a way back to the previous stable version.

The `docker-destructive-guardrails` skill defines the confirmation rules.

## Undecided

These points are open. Do not assume an answer; check the old `whisperer` codebase first, then ask.

- **Rendering of public pages.** The SEO strategy requires server rendering or static generation and real `404` responses; the stack is a client-rendered Vite app.
- **Vector storage.** The stack names Qdrant; the test infrastructure names `pgvector`.
- **AI interface libraries.** `ai-elements`, `streamdown` and the Vercel AI SDK were considered but are neither installed nor in the stack.
- **Redis or a Redis-compatible server**, and the TaskIQ broker.
- **The shared error format and pagination style** for the API.

<!-- REPOWISE:START — Do not edit below this line. Auto-generated by Repowise. -->
## Codebase Intelligence for whisperer-v2 (Repowise)

Indexed by [Repowise](https://repowise.dev). Last indexed: 2026-09-30 (commit 7c2c003). Confidence: 100%.Scope: standard index · template content · full Git. Missing or unavailable evidence is not a negative finding. Run `repowise update --full` to continue the model-backed upgrade (cost is previewed before generation).Machine-readable scope: `{"analysis": {"skipped": [], "unavailable": []}, "content_provenance": "template", "dropped_files": {"generated": {"count": 0, "paths": [], "truncated": false}}, "file_pages": {"configured_cap": null, "effective_cap": null, "eligible": 0, "generated": 0, "omitted": 0}, "git_commit_cap": 500, "git_history_coverage": {"complete_through_depth": 3, "deep_commits": 0, "deep_files": 0, "eligible_files": 0, "fallback_files": 0, "files_with_history": 0, "global_commits": 3, "per_file_limit": 500, "recent_files": 0, "retained_commits": 0, "unavailable_files": 0, "workers": 1}, "git_tier": "full", "provider": {"embedder": "mock", "model": null, "model_cost_possible": false, "name": null, "reused": false}, "run_mode": "standard", "search": {"full_text": "available", "next_command": "repowise reindex", "semantic": "unavailable"}, "upgrade": {"completed_stages": [], "next_stage": "generation", "retryable": true, "status": "pending"}, "version": 1}`

### How to work in this repo

- **Trust the index.** `verified: true` and `_meta.complete` mean the bytes were checked against the live tree, so never re-read them. Re-read only what `bounds: "approximate"` or `_meta.stale_warning` names. `confidence` rates the prose, not the evidence: on `low` read the `fallback_targets` or `best_guesses` the reply names, and run `repowise update` and ask again if `_meta.hint` says the index is behind HEAD. `index_behind: true` alone is informational.
- **A zero carries its basis.** An empty `callers`/`callees`/`used_by` comes with a `*_basis` saying how much of that language's calls the graph resolved, so read it before concluding nothing calls a symbol. `_meta.scope_hint` names the areas the answer did not touch.
- **Pre-edit, not instead-of-edit.** These tools decide *which* files to read and edit. Claude Code requires a raw Read of any file you will Edit, and that Read is correct and expected.
- **Noisy commands** (tests, builds, `git log`/`diff`, searches, listings): prefer `repowise distill <cmd>` — same command, exit code preserved, errors-first output. A `[repowise#<ref>: N lines omitted]` marker is recoverable via `repowise expand <ref>` (add `-q <regex>` to filter); never re-run the command to see omitted output.
- **Recording a decision** you had to reason out: `repowise decision add --title T --decision D` records it without prompting and prints the id (`--format json` to parse it back). It lands `proposed`, for a person to confirm.

### Tools

| Tool | When and why |
|------|--------------|
| `get_answer(question)` | First call for any how/where/why question. Cite `confidence: "high"` or `grounding: "extracted"` directly; `degraded` means judge by `retrieval_quality`. `symbol_bodies` has live bodies. |
| `get_context(targets=[...])` | Triage card for files/modules/symbols: docs, signatures, hotspot, fix history. No source bytes — `include=["skeleton"]` for the whole file verified, `["callers"|"decisions"]` for depth. Batch targets. |
| `get_symbol(id, depth?)` | **Follow-up, not an entry point** — one verified body for an id a prior response named (`path.py::Name`, `path.py:140-180`, `repowise#<hex>`). Never walk a file symbol by symbol; Read it. |
| `search_codebase(query)` | Hybrid search, auto-routed by query shape; force with `mode=symbol|path|concept|hybrid`. A hit whose `sources` are `[fts]` only has no semantic agreement, so verify it. |
| `get_why(query, targets?)` | Why the code is shaped this way: decision records, git archaeology, rationale comments. Call before a refactor or a pattern divergence. |
| `get_risk(targets, changed_files?, include?)` | File history and structural reach. PR mode leads with `directive`; its 0-10 structural heuristic is uncalibrated, not a probability. Read typed test recommendations and coverage state first. |
| `get_change_risk(revspec?, extensions?, exclude_patterns?)` | Deterministic live-diff review signal for a commit or range. Lead with benchmarked percentile/classification; the 0-10 diff-shape score is supporting, not a probability. `get_risk` scores paths. |
| `get_health(targets?, include?)` | Defect / maintainability / performance scores and findings, plus documentation the code no longer supports. Self-check the files you touched before finishing. |
| `get_dead_code(tier?, min_confidence?, safe_only?)` | Confidence-tiered unreachable files / unused exports / zombie packages. For cleanup sweeps, not targeted fixes. |
| `get_overview()` | Architecture map. Call once, first, in an unfamiliar repo; skip it after that. |

### Architecture
**Files:** 2 | **Lines:** 1283
whisperer-v2 is a json codebase of 2 files. ---
*Built from the code's structure. It states what is there, not why it is that
way. The explanatory prose is a separate, model-written layer.*

<!-- REPOWISE:END -->
