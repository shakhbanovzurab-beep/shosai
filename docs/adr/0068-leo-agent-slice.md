# ADR 0068 — Leo's agent slice: sources, conversations, the admin's Leo, Markdown, rules before Jev, feedback and LangGraph's place

- **Status:** accepted by the owner on 2026-10-23 ([agent plan](../plan/slices/agent.md) §2): AG-D1, AG-D2, AG-D4, AG-D5, AG-D7, AG-D8 and AG-D11 as written; AG-D3, AG-D6 and AG-D10 with the owner's amendments; AG-D13 and AG-D14 added by the owner; AG-D9 accepted on condition of AG-D12. **AG-D12 (where turns run) is open** and is decided with the owner before the plan's step 5a; this record is amended then.
- **Packages:** `agent` (owner); notes, files and tasks (sources and preview wording of their tools); identity (`improve_models` read, `identity.consent.changed`, an operator audit action); studio (`prompt_skills`; model routes and prompts later); files (the `leo_attachment` purpose); chats (AG-R1, AG-R2); decisions (binds routing and friction); the cabinet's `leo`, `settings`, `studio` and `productivity` features.
- **Context documents:** [agent plan](../plan/slices/agent.md); [Leo architecture](../design/leo/ARCHITECTURE.md) §3.3, §6.3, §7.3–§7.4, §8, §10–§13, §17 Q-2; [ARCHITECTURE.md](../design/ARCHITECTURE.md) §5, §7, §8, §10, §12, §16; [SLICE_MAP](../plan/SLICE_MAP.md) §2.4, §4.2.14–19, SM-12; [DATA_MAPPING](../plan/DATA_MAPPING.md) §5.1, §5.12, §5.16; ADR 0023–0033, 0039, 0049, 0053, 0063.

## Context

The Leo architecture fixes the agent's shape: threads in the home database, runs with one terminal event and resume, the Action Gateway, toolsets owned by slices, a budgeted context. Planning the `agent` slice against the new cabinet and the slices already built left questions it did not settle: how an answer's sources reach the screen with their space; what happens to past conversations and to a workspace's threads when membership ends; which models and prompts Leo uses before `studio`; what Leo does in the admin panel, which the owner wants kept; which library renders streamed Markdown (CLAUDE.md "Undecided"); what the decision points do before `decisions`; which evaluation suites gate CI; how a release treats turns in flight; which parts of the architecture have no consumer yet; who owns a prompt's skills; how people rate answers; and where LangGraph's role ends.

## Decision

1. **Sources come from the tools (AG-D1).** `ToolResult` gains `sources` (`SourceRef`: kind, id, title, the workspace or none, locator, quote). Read tools fill it; the agent numbers each new source in the order results arrive and the model cites by `[n]`. The stream's `sources` event carries the cumulative list after each tool step, its numbers fixed within a run; the answer keeps it. The space is named by the agent. Highlighted words wait for a measured step.
2. **Past conversations (AG-D2).** The panel opens the context's latest thread; "New chat" starts a new one; a "Recent chats" menu lists the context's threads with rename and delete.
3. **A workspace's threads when membership ends (AG-D3, amended by the owner).** They are hidden at once (every list, history read and turn checks active membership) and erased 7 days later unless the membership is active again; a workspace deleted for good erases them at once. `read_result` re-checks the spaces of a stored result on every read.
4. **Before studio (AG-D4).** The agent's settings name its model routes per tier, utility and vision; the system policy and the native proxy's `responses` prompt are English text in the slice; `leo_model` accepts `auto` only.
5. **Leo in the admin panel (AG-D5).** The same agent with an operator principal on `/v1/admin/agent/*` behind the admin session, threads in the EU home, read-only toolsets over platform aggregates only — no person's content, no writes, no memory — answering in Russian.
6. **Streaming Markdown (AG-D6, with the owner's conditions).** The cabinet renders Leo's answers with its own incremental renderer on `marked`'s lexer, already shipped through `@tiptap/markdown`; finished blocks memoised, the tail re-lexed per frame. Raw HTML from a model is never rendered; a link renders only with `https`, `http`, `mailto` or a cabinet path, and anything else is plain text; images and other remote resources are never loaded; tests cover unfinished Markdown cut at every point (lists, tables, fenced code, emphasis, links) and XSS (dangerous schemes in every encoding, HTML tags and attributes, autolinks). `ai-elements`, `streamdown` and the Vercel AI SDK are not used. This closes CLAUDE.md's "Undecided" entry and Leo §17 Q-2.
7. **Rules before Jev (AG-D7).** Routing: the core toolset, the surface's toolsets, toolsets used in the thread's last three turns and, while they fit segment 2's 4 000 tokens, every other toolset the person's switches and plan allow; the rest are named in `load_toolset`. Friction: "warning, approve on screen only" when the run's taint is external or worse or the write is irreversible, standard otherwise. `decisions` binds both later and may only add friction. This replaces Leo §6.3's fallback of a warning on every card.
8. **Evaluation gates (AG-D8).** CI runs the deterministic suites on every push: trajectories against a scripted model, injection corpora per untrusted channel, the Action Gateway's property tests, budgets and prefix stability, token counts. The live suites (real-model tool choice, 16-language parity, the LLM judge, donated cases) run by `shosai agent eval` before a prompt, model or toolset change is released.
9. **Releases (AG-D9, conditional).** If turns stay in the API process, the API's stop grace is 200 s and a stopping process finishes its runs. Replaced if AG-D12 picks worker processes.
10. **Parts without a consumer (AG-D10, amended by the owner).** `workspace.search` comes with knowledge, `ask_user` with a cabinet UI for it, mentions with a composer that has them, the secret vault with the first tool that needs a secret, diff previews with the first tool that edits text, file artifacts with their first producer, platform playbooks with proactive. `chart` and `image` artifacts are built with their first consumer, the analytics of Leo in the admin panel. `client.action set_theme` is dropped. Steps carry the tool's name as their activity code; the cabinet's hand-kept list of activity ids goes.
11. **Skills (AG-D11).** Agent keeps `agent_skills`, serves `/v1/agent/skills*` and offers `SkillReader`; `prompt_skills` moves to studio, which composes a prompt with its skills. Leo uses a person's skills through studio's prompt for its role, always wrapped as untrusted.
12. **Where turns run (AG-D12): open.** Options: A — in the API process (Leo §12); B — on a dedicated `agent` queue served by its own worker processes, the API only serving the stream from the run's log. The plan compares them (§2.1) and proposes B.
13. **Feedback on answers (AG-D13, the owner's).** "Useful" and "Not useful" under every finished answer, one press, no form. The rating lives in `agent_feedback` in the person's home and is seen by the person; the operator sees only counts and rates by model, tier, toolset, channel and language. A rated turn becomes an evaluation case only with the person's `improve_models` consent at the time of rating and only when none of its sources is in a workspace; the case (the turn as the model saw it, the name masked, no attachment text) is copied into `agent_eval_cases` in the person's home, read where it lives by the live suites and by the owner on the host through `shosai agent eval cases`, each read audited, never shown in the admin panel, and erased with its rating, the consent (identity's additive `identity.consent.changed`), its thread or the account, or after 12 months.
14. **LangGraph's boundary (AG-D14, the owner's).** LangGraph is the frame of a turn: the loop model ⇄ tools, the pause for approval and its resume, and the state passed between nodes. Its ready-made savers, prebuilt agents, `ToolNode`, model clients and memory or store are not used. Rights, the Action Gateway, sources, taint, every model call (through F6's provider port), storage and deletion are Shosai's own, the saver included, over LangGraph's public interface. import-linter allows `langgraph` only in `agent.infrastructure`. If the saver outgrows one file or needs LangGraph's internals, that is a separate decision brought to the owner.

## Alternatives considered

| Option | Why not |
|---|---|
| Sources written by the model in its answer | It can invent a source or a space; nothing checks it |
| No list of past conversations, a left thread erased after 30 days | Keeps for a month what the person cannot reach |
| A workspace's threads erased at once, or kept read-only | At once loses a week's grace after a mistaken removal; read-only keeps company data the person may no longer see |
| A temporary model catalogue in the agent before studio | A second catalogue to keep in step and retire |
| The admin's widget without tools | A chat that cannot see the platform the admin asks about |
| `streamdown`, `ai-elements` or the Vercel AI SDK for rendering | New dependencies around a problem the cabinet's existing lexer solves; less control over sanitisation |
| A warning on every card until Jev | Teaches people to ignore warnings |
| Live-model suites in CI on every push | A provider key and spend in CI, flaky gates |
| Donating every rated conversation, or none | The first ignores consent and company data; the second leaves Leo without real cases |
| LangGraph's prebuilt agent, `ToolNode` and savers | They would own tool dispatch, state storage and model calls, which rights, money and deletion depend on |

## Consequences

- Notes', files' and tasks' read tools gain `sources`; their write tools gain wording of their previews in 16 languages; core's tool contract gains `sources`, `artifacts`, `step_detail` and `PreviewTexts`, all additive.
- The cabinet's Leo panel, cards, "Needs you", Settings › Leo and Studio's skills dialog move to the API; the conversation leaves the browser's storage.
- Identity gains an `improve_models` read, the `identity.consent.changed` event and an audit action for reading an evaluation case — additive.
- Studio's plan owns `prompt_skills` and binds `ModelRoutes` and `PromptResolver` for the agent.
- The Leo architecture (§3.3, §6.3, §8.2, §8.4, §10, §11.4, §13.2, §13.3, §17), SLICE_MAP, the target architecture §8, DATA_MAPPING and CLAUDE.md are amended with this record.

## Revisit when

- AG-D12 is decided (before step 5a): this record, Leo §12 and the target architecture §4.2, §5 and §17 are amended.
- `decisions` is calibrated for `turn.route` and `action.friction`.
- A measured eval shows highlighted words in sources or syntax highlighting in code blocks are worth their cost.
- The saver outgrows AG-D14's bound.
