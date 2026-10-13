# Shosai

Shosai is an AI workspace. It brings a person's knowledge, meetings, documents, tasks, calendar, communications and AI into one system, so they can keep what they know, understand information and automate routine work.

**Design it as a Swiss army knife.** Every new capability is another blade of one tool, not a separate tool. Features share the user's context and strengthen each other. They integrate through contracts, events and shared context, never through one feature reaching into another's internals.

`shosai` is a full, rethought rewrite of the earlier `whisperer` project. The product was renamed from Whisperer to Shosai ([ADR 0037](../docs/adr/0037-rebrand-whisperer-to-shosai.md)); the draft keeps its old name and path. Rules below describe the target state. Carry over behaviour and lessons from the old code; do not assume its file or function names exist here.

## Philosophy

Whisperer → Shosai is not a rebrand. It rethinks the whole platform: its philosophy, its user experience and its architecture.

Shosai is a digital Japanese study — 書斎 (*shosai*), a room for focused work, reflection and solitude, where a person does not have to hold the whole operational side of their life in their head.

> **Shosai is a personal workspace with memory and initiative. It takes on the operational load so the person can focus on what truly needs their thinking.**

This principle decides product, interface, architecture and priorities. When a choice is unclear, choose what lowers the user's operational load and protects their attention.

### The core idea

The person thinks. Shosai remembers, connects and helps act.

Shosai relieves the user of having to:

- **Remember** — agreements, promises, ideas, facts, deadlines and the context of conversations.
- **Track** — unfinished tasks, commitments, changes and next steps.
- **Connect** — information from meetings, emails, documents, notes, knowledge and projects.
- **Watch** — what needs attention, what is blocked, what was forgotten, what is due.
- **Organise** — turn scattered information into one coherent system of work.
- **Coordinate** — move from thought to decision, from decision to action, from action to result.

Shosai must not turn the user's life into endless management of Shosai itself. Less manual organising, less re-entering data, fewer switches between tools and less reminding the AI of context — each of these is a measure of success.

### The user experience

1. **A quiet space.** No visual noise, no stream of notifications, no interface that has to be tended. The user opens Shosai to work, not to organise work.
2. **Memory that works by itself.** Shosai keeps context, extracts what matters and links it to its sources. The user never has to explain again what was discussed and why it matters.
3. **One whole picture.** Meetings, tasks, knowledge, email and projects are not separate apps but parts of one system. The links between them are what let Shosai understand a situation rather than merely store data.
4. **Action without micromanagement.** The AI does safe routine work on its own, proposes the actions that are needed and asks for confirmation only where confirmation truly matters.

### Leo

Leo is not a chatbot or an on-demand assistant. Leo is the intelligent core of Shosai: it understands context, notices unfinished commitments, connects events and helps carry work through to a result. Its initiative always comes with reliability, transparency and user control — the user can see what Leo did and why, and can correct or stop it.

### Give attention back

Shosai does not try to automate every second of the user's life. Its job is not to take attention but to give it back. A feature that demands attention without returning more of it does not belong in Shosai.

## Rewrite from the draft

| Directory | Role |
|---|---|
| `/root/whisperer` | **The draft.** The old working project. A reference only: read it to learn behaviour, UI, API and WebSocket contracts, and lessons. Do not modify it. |
| `/root/shosai` | **The final version.** All work happens here. |

**Scope.** Only the draft's `backend/` and `frontend/` and the files tied to them: Dockerfiles, Compose files, `deploy/` configuration, CI workflows, and `specs/` and `docs/` as a source of requirements. Out of scope: the macOS, iOS, Linux and Windows clients, `pwa-app/`, `shared/` (the Swift `WhispererKit`), `hubspot-app/`, `content-factory/`, `article/`. Never decrypt or read `secrets/`.

**Goal.** Build Shosai from scratch to the [philosophy](#philosophy), this file, the [target architecture](#target-architecture) and the [Leo architecture](../docs/design/leo/ARCHITECTURE.md), with the **new web design** in `frontend/` as the product and visual reference ([ADR 0022](../docs/adr/0022-new-web-design-replaces-draft-parity.md)). Parity with the draft is not a goal, neither in looks nor in behaviour: a feature is designed from what Shosai's user needs, not from what the draft did.

**The draft is a reference, not a specification.** Consult it when it helps: business rules worth keeping, edge cases it already solved, lessons from its bugs, provider quirks. Do not copy its code, structure or data model, and do not keep a behaviour only because the draft had it.

**One exception: shipped native clients.** The macOS and Windows clients already shipped keep working without an update (nfr-12), so the HTTP and WebSocket contract they use (the native routes in [contracts/](../contracts/README.md)) is preserved, if need be through a thin compatibility layer over the new design.

**Versions.** Use the versions in the [stack table](#technology-stack). Anything not listed there gets the latest stable version at the moment it is added. The draft's versions are outdated and are never carried over.

**Order.** Features can be rewritten in any order; there is no required sequence.

**Plan and status.** The work is split into packages in [docs/plan/REWRITE_PLAN.md](../docs/plan/REWRITE_PLAN.md); each package's state is in [docs/plan/STATUS.md](../docs/plan/STATUS.md); each package has a launch prompt in [docs/plan/prompts/](../docs/plan/prompts/). The v2 test domain is **https://one.whisperer.one**.

### Hosting constraints now

The target architecture places data in two homes: PostgreSQL in Russia and in the EU, one S3 bucket in Russia for both homes ([ADR 0014](../docs/adr/0014-one-object-store-in-russia.md)), plus a managed Redis-compatible store (Valkey) in the EU. **The owner is adding these resources; until F4 connects them, they are not available to development.**

- Code implements the target architecture as written, including home-aware data access. Do not simplify the design to fit today's hosting.
- Develop and test against local containers.
- Do not choose another provider or a workaround for the missing resources without asking the user.

## Target architecture

[docs/design/ARCHITECTURE.md](../docs/design/ARCHITECTURE.md) is the target architecture, fixed by the owner, with a diagram in [docs/design/architecture.html](../docs/design/architecture.html). It is normative: where it and an implementation disagree, the implementation is wrong, or the document is updated first.

It defines product scope, non-functional targets, topology (one compute plane in the EU, two data homes in Russia and the EU), the process model and code layout, data placement and residency, tenancy and access control, the data model, invariants, interfaces, critical flows, async work, resilience, observability, delivery and the full technology stack.

Read the relevant section before you design or change a feature, a data model, an interface, an async flow or anything that touches residency, access or money. Keep the invariants (§9) and the engineering rules (§14) in every change.

## Order of authority

When instructions conflict, the higher one wins:

1. A direct instruction from the user in the current conversation.
2. This file.
3. A skill that this file names as mandatory (see [Mandatory skills](#mandatory-skills)).
4. Any other skill.
5. General habit.

A skill's commands are replaced by this file's commands where they differ. Example: the `react-doctor` skill says `npx react-doctor@latest`; here the rule is `npm run doctor`.

On architecture — components, data placement, interfaces, invariants — the [target architecture](#target-architecture) is normative. If this file and that document disagree, do not pick one silently: point out the conflict and ask.

## Language

| What | Language |
|---|---|
| This file, skills, anything else a coding agent reads as instructions | English |
| Everything a language model reads in the product (see [Prompts](#prompts-and-model-facing-text)) | English |
| Docstrings (Python) | English — tools publish them: FastAPI into OpenAPI, Pydantic into JSON schemas, MCP and agent frameworks into tool descriptions |
| Code comments, including TypeScript doc comments | Russian — they are for the engineer |
| Log messages | Russian; field names and event keys are English identifiers |
| Text shown to users (UI, emails, HTTP errors) | The user's language, through i18n |

Do not write comments in English because this file is in English. A test in each Python project checks that every docstring is English.

## Production by default

All code written for Shosai is production code. Every change must be ready to run in production once its checks pass.

Not allowed: temporary solutions, a `TODO` instead of an implementation, "fix later", demo or MVP shortcuts, technical debt without a stated reason, experimental architecture without need.

Every change must be safe, measurable and of real engineering value. No changes for looks, no technology swaps without an objective gain, no refactoring without an architectural reason.

## Architecture

**Feature-first vertical slices are the only allowed structure, in `backend/`, `frontend/` and `site/`.**

- A slice holds everything its feature needs. Backend: models, schemas, services, endpoints. Frontend: components, hooks, state, API calls. The two sides mirror each other by feature name.
- Clean Architecture sets the direction of dependencies **inside** a slice: domain logic does not depend on the framework, the database or transport.
- Slices talk to each other only through explicit contracts: a public interface, an event, or the HTTP API. `import-linter` enforces the boundaries on the backend.

**File length.** A hand-written source file is at most **300 lines in `backend/`** and **200 lines in `frontend/` and `site/`**, counting every line. Generated files and lock files are exempt ([what counts as generated](#ci)). Split the file by responsibility before it reaches the limit.

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

This table is the base. The complete stack — drivers, managed services, AI providers, payments, frontend libraries, native clients, pinned versions — is in §18 of the [target architecture](#target-architecture).

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
| | Vite | latest stable | Build and dev tooling of the cabinet (`frontend/`) |
| | Next.js | latest stable | Public site (`site/`): server rendering, static generation |
| | npm | — | Package management and scripts |
| **Data** | PostgreSQL | latest supported | Source of truth |
| | Qdrant | latest stable | Vector database, RAG |
| | Redis | latest stable | Cache, locks, rate limits, ephemeral state |
| | S3-compatible storage | — | Files, recordings, documents |
| **Async work** | TaskIQ | latest stable | Background jobs and workers |
| **AI** | Leo | — | Shosai's AI agent |
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

- **Load them first.** Invoke each skill of a zone with the Skill tool before you read draft code for that zone, design for it or write in it — not after the code is written.
- **Apply them.** Before finishing, check your change against every loaded skill, the same way you check it against this file.
- **Report them.** Every final report lists the skills loaded in the session and names any recommendation you did not follow, with the reason.
- **A skill that fails to load** is a blocker: say so; do not continue in that zone without it.
- **Enforced by a hook.** [.claude/hooks/require_skills.py](hooks/require_skills.py) blocks, until the zone's skills are loaded in the session:
  - edits of files in `backend/`, `frontend/` and Docker files (Dockerfiles, Compose files, `.dockerignore`);
  - shell commands that change or run something in those zones — including `cd backend && …`, redirections into zone files and scripts fed to an interpreter through a heredoc;
  - every `docker` command that changes state;
  - the quality gates: `python-doctor` and `mypy` in `backend/` need the `python-doctor` skill, `react-doctor` in `frontend/` needs `react-doctor`.

  Read-only commands (`ls`, `cat`, `grep`, `git diff`, `docker ps` and the like) and the draft in `/root/whisperer` are not blocked. The hook cannot see inside a script file that writes into a zone without naming the zone on the command line; doing that to get around it is forbidden. Its behaviour is fixed by [tests](hooks/test_require_skills.py) that CI runs.

| Zone | Skills |
|---|---|
| Backend (`backend/`) | `fastapi` |
| Frontend (`frontend/`, `site/`) | `vercel-react-best-practices`, `vercel-composition-patterns`, `vercel-react-view-transitions`, `web-design-guidelines` |
| Docker and Compose | `docker-project-foundations`, `docker-build-strategies`, `docker-compose-patterns`, `docker-destructive-guardrails` |
| Python code health | `python-doctor` |
| React code health | `react-doctor` |
| Architecture, data model, interfaces, async flows | [docs/design/ARCHITECTURE.md](../docs/design/ARCHITECTURE.md) (document, not a skill) |
| Leo: agent, decisions, memory, proactivity, errands, agent tools of any slice | [docs/design/leo/ARCHITECTURE.md](../docs/design/leo/ARCHITECTURE.md) (document, not a skill) and the `agent-architecture` skill |
| Public pages, SEO, AI search visibility | [docs/seo/STRATEGY.md](../docs/seo/STRATEGY.md) and the `seo-*` skills mapped in its section 17 |

The `docker-agent-*` and `docker-sandboxes-*` skills apply only if Docker Agent or Docker Sandboxes are actually used.

The FastAPI skill is the primary engineering standard for the backend. Where it conflicts with habit, the skill wins.

## Backend

### Performance focus

CPU, memory, the event loop, PostgreSQL, Redis, SQLAlchemy, network I/O, connection pools, TaskIQ, concurrency, locks, serialization, horizontal scaling.

Judge every architectural decision on performance, scalability, fault tolerance and operational readiness.

## Frontend

Two web applications ([ADR 0021](../docs/adr/0021-public-site-on-nextjs-cabinet-on-vite.md)), on one design system:

- **Cabinet** — `frontend/`, a Vite single-page app and PWA: everything a signed-in user and an administrator work in. Not indexable.
- **Public site** — `site/`, Next.js: landing, pricing, documentation, blog, legal pages, help centre and public pages of shared links. Server-rendered or statically generated, under [docs/seo/STRATEGY.md](../docs/seo/STRATEGY.md).

Neither application owns an API, business logic, a database connection or a queue: the backend is FastAPI only. A Next.js route handler, server action or middleware only renders, redirects or proxies.

The cabinet is one workspace. The user never feels a switch between features; each capability reads as the natural continuation of the previous one. The interface is fast, consistent and predictable, and keeps cognitive load low.

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

Guidance in the Vercel skills that assumes Next.js or React Server Components applies to `site/` only, not to `frontend/`.

### Performance focus

Bundle size, re-renders, memory, network requests, lazy loading, code splitting, FPS, scalability of the interface, and Core Web Vitals. Targets: LCP ≤ 2.5 s, INP ≤ 200 ms, CLS ≤ 0.1.

## Performance

Shosai is designed for 10 000 DAU, verified by calculation up to 100 000 DAU (the design point in §3 of the [target architecture](#target-architecture)). It runs as one compute plane on Docker Compose with managed services. Performance is an architectural requirement, not a later optimization phase.

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

**What is not a prompt:** comments, logs, and text shown to users through i18n. Docstrings are English by the [language rule](#language); one that a tool turns into a schema or a tool description is also a prompt and is registered like one.

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
- **Never run tests against a production database.** Treat `DATABASE_URL` in `backend/.env` as production. Tests read only `TEST_*` variables (`TEST_HOME_RU_DATABASE_URL` and the others in [ADR 0009](../docs/adr/0009-test-databases-claimed-by-advisory-lock.md)) and must refuse to start if the target is not a test database.
- Several prepared test databases exist so agents can run in parallel. Before a run, claim one that no other agent is using; the harness does it as ADR 0009 describes.

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

### CI

[.github/workflows/ci.yml](../.github/workflows/ci.yml) runs on every push to `main`. It repeats the gates above and adds checks the agent does not run by hand. A red CI on `main` is fixed before any other work.

| Job | Runs | Checks |
|---|---|---|
| Repository rules | always | File length limits; no `.env` file tracked by git ([scripts/ci/check_repository.py](../scripts/ci/check_repository.py)) |
| Semgrep | always | `p/default` rules over the whole repository except `.claude/` |
| Contracts | always | `uv sync --locked`, Ruff format and lint, mypy strict, pytest (harness, consistency of the draft API baseline, rendered documents in sync), python-doctor 100 — see [contracts/README.md](../contracts/README.md) |
| Backend | once `backend/pyproject.toml` exists | `uv sync --locked`, Ruff format and lint, mypy strict, import-linter, pytest with coverage, python-doctor 100, pip-audit |
| Frontend | once `frontend/package.json` exists | `npm ci`, type check, tests, build, react-doctor 100 |

What the projects must provide for CI to pass:

- **Backend:** `uv.lock`; dev dependencies `ruff`, `mypy`, `import-linter`, `pytest`, `pytest-cov`, `python-doctor`, `pip-audit`; import-linter contracts. Tests read databases and services only from `TEST_*` variables (ADR 0009) — CI provides the `compose.dev.yaml` services there.
- **Frontend:** `package-lock.json`; `.nvmrc` with the Node version; npm scripts `typecheck`, `test` (single run, not watch mode), `build` and `doctor`.
- **Contracts:** after a change under `contracts/`, run `uv run shosai-contracts render` if `draft/*.json` changed, then `uv run pytest` and `uv run python-doctor . --score` there.

For the file length limit, generated code is exempt: files under a `generated/` or `__generated__/` directory, Alembic migrations (`alembic/versions/`, `migrations/versions/`), and files with an `@generated` marker in their first five lines.

## Self-review

Before finishing an implementation, review your own change for: fit with the [philosophy](#philosophy) (does it lower the user's operational load and give attention back?), architecture, performance, security, readability, typing, error handling, duplication, feature-first structure, compliance with this file, and compliance with the mandatory skills.

## Git workflow

Development is linear and happens **only on `main`**.

- **Commit only after the user says «Принято».** No commits without that explicit approval.
- Never create a branch or a git worktree.
- One logically complete task is one atomic commit. Do not combine independent changes.

### Push is part of the commit

**A commit is done only after `git push origin main`.** Local `main` must equal `origin/main` when a task ends. Production images are built by CI from a pushed green commit, never on a production host, so an unpushed commit never reaches production and exists on one machine only.

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

- **AI interface libraries.** `ai-elements`, `streamdown` and the Vercel AI SDK were considered. The target architecture adopts Tailwind CSS but none of these three.

<!-- REPOWISE:START — Do not edit below this line. Auto-generated by Repowise. -->
## Codebase Intelligence for shosai (Repowise)

Indexed by [Repowise](https://repowise.dev). Last indexed: 2026-09-30 (commit 01ddcba). Confidence: 100%.Scope: standard index · template content · full Git. Missing or unavailable evidence is not a negative finding. Run `repowise update --full` to continue the model-backed upgrade (cost is previewed before generation).Machine-readable scope: `{"analysis": {"skipped": [], "unavailable": []}, "content_provenance": "template", "dropped_files": {"generated": {"count": 0, "paths": [], "truncated": false}}, "file_pages": {"configured_cap": null, "effective_cap": null, "eligible": 0, "generated": 0, "omitted": 0}, "git_commit_cap": 500, "git_history_coverage": {"complete_through_depth": 5, "deep_commits": 0, "deep_files": 0, "eligible_files": 0, "fallback_files": 0, "files_with_history": 0, "global_commits": 5, "per_file_limit": 500, "recent_files": 0, "retained_commits": 0, "unavailable_files": 0, "workers": 1}, "git_tier": "full", "provider": {"embedder": "mock", "model": null, "model_cost_possible": false, "name": null, "reused": false}, "run_mode": "standard", "search": {"full_text": "available", "next_command": "repowise reindex", "semantic": "unavailable"}, "upgrade": {"completed_stages": [], "next_stage": "generation", "retryable": true, "status": "pending"}, "version": 1}`

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
**Files:** 4 | **Lines:** 3465
shosai is a markdown codebase of 4 files. ---
*Built from the code's structure. It states what is there, not why it is that
way. The explanatory prose is a separate, model-written layer.*

<!-- REPOWISE:END -->
