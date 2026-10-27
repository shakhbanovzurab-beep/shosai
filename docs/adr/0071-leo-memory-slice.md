# ADR 0071 — The memory slice: candidates under the answer, calibrated auto-save, facts that follow their source

- **Status:** accepted by the owner on 2026-10-27 ([memory plan](../plan/slices/memory.md) §2): MM-D2, MM-D3 and MM-D5 as written; MM-D1, MM-D4, MM-D6, MM-D7 and MM-D8 with the owner's amendments.
- **Packages:** `memory` (owner); agent (the amended `MemoryRecall` and `ProfileFacts`, a new `PersonWords` port, segment 4's boundary, the taint rule, the candidate's line in the panel); decisions (`memory.admit` in shadow, the person's answers as outcomes, the auto-save gate); notes (step 24 closed by memory's subscription); chats (facts from team chats); studio (the personal context takes the draft's personalization instructions); M1 (the draft's memory and personalization).
- **Context documents:** [memory plan](../plan/slices/memory.md); [Leo architecture](../design/leo/ARCHITECTURE.md) §6.3–§6.4, §7, §10, §13; [ARCHITECTURE.md](../design/ARCHITECTURE.md) §8.1, §16.4; [ADR 0030](0030-leo-memory-v2.md); [ADR 0033](0033-vectors-pgvector-for-memory-qdrant-for-knowledge-and-meetings.md); [ADR 0062](0062-team-chats-through-leo-on-demand.md); [ADR 0068](0068-leo-agent-slice.md) AG-D3; [ADR 0069](0069-decision-layer-slice.md).

## Context

ADR 0030 set memory's shape: admitted facts with provenance and supersession, candidates the person confirms, untrusted rendering and switches on every path. Planning the slice against the code, the new cabinet and the draft left questions it did not settle:

- **Learning before calibration.** Leo §6.3's fallback for `memory.admit` stores only explicit requests; the policy needs its sets and two weeks of shadow before it acts, so Leo would learn nothing for weeks.
- **What the cabinet shows.** There is no personalization screen; the summary's box has nowhere to put an answer; candidates live only on the memory page.
- **Lifetimes.** A fact from a workspace, a meeting or a team chat could outlive the person's access to its source.
- **Mechanics.** No embedding model is chosen; a global HNSW filtered to one person loses results; a per-run wrapper boundary in segment 4 would defeat the prompt cache; wrapped memory would taint almost every turn.
- **Migration.** The draft's memory has no provenance and stores raw commands.

## Decision

1. **Admission (MM-D1, amended by the owner).** Explicit requests become active facts; every other durable statement becomes a candidate, never used until accepted — at most 3 a day per person, gone after 30 days unanswered, never asked again near something the person forgot or turned down. Candidates are shown quietly: one line under the Leo answer they came from and the list in Settings › Memory, never a notification. Admission runs per turn, right after it, so the line can stand under its answer.
   - From the moment decisions ships the policy, `memory.admit` runs in shadow on every statement; the person's answer — Remember, Don't remember, an edit — is its outcome and its online calibration (Leo §6.4).
   - **Auto-save** of confident statements that are not sensitive opens only when the policy agrees with people **≥ 95% in every language with at least 200 answered statements it would have saved, over the last 90 days** (at least one language qualifying), after its synthetic and reference gates and its shadow. Then those are saved without asking — visible and correctable — and only doubtful and sensitive statements stay candidates. A daily check closes auto-save when a qualifying language falls below 95% over 28 days; 1 in 20 statements the policy would save is still asked, so agreement stays measured.
2. **No personalization table (MM-D2).** The profile core is pinned facts and preferences, Studio's personal context and Settings › Leo. At migration the draft's occupation and non-default style knobs become pinned facts "Added in Settings"; its instructions go to Studio's personal context.
3. **The summary's box is memory's own (MM-D3).** It answers a question from the person's facts and applies the changes the message asks for — remember, update, forget — each returned with Undo for 24 hours (`restore`).
4. **Facts follow their source (MM-D4, amended by the owner).** A fact keeps its source's space: hidden when the person leaves the workspace, erased after 7 days unless membership is restored, erased at once with a deleted workspace. A meeting's fact goes with the meeting. A team chat's fact lives by the chat's rules (ADR 0062): erased at the chat's disconnection or when its message passes the workspace's retention, and as a workspace's fact on leaving. A fact from a conversation with Leo stays when that conversation is deleted.
5. **Meeting recollections by event (MM-D5).** Memory subscribes to `notes.meeting.notes_ready` (first revision) instead of a port notes calls; it reads Leo's summary, the key points and the participants, extracts at most 5 statements about the owner, people and goals — never decisions, promises, tasks or opinions — and every one is a candidate labelled `meeting:speech` with its evidence.
6. **Embeddings (MM-D6, amended by the owner).** Exact nearest neighbours over the person's own current facts through a b-tree on the person, no HNSW; `halfvec(1024)`. `baai/bge-m3` is compared with `qwen/qwen3-embedding-8b` and `openai/text-embedding-3-small` on a 16-language set and the best worst-language recall@12 is pinned — **only after the comparison's cost is stated and the owner approves the budget**.
7. **Trust of a fact (MM-D7, amended by the owner).** Only facts the person confirmed — an explicit request, "Remember", their edit or a fact they added — leave the run's taint as it is. A fact saved automatically keeps its source's provenance and taint and marks the run at least external. Segment 4's facts are wrapped with a boundary computed as an HMAC with a server secret over the block: stable for the prompt cache while the facts are unchanged, impossible to guess.
8. **The draft's memory at migration (MM-D8, amended by the owner).** Non-forgotten facts and procedures of people with memory on are carried: the ones the person asked for as active facts, the rest as candidates from "your earlier memory", which never join the daily candidates or the line under an answer and wait in a separate list in Settings › Memory; episodes are dropped.

## Alternatives considered

| Option | Why not |
|---|---|
| Leo §6.3's fallback as written: only explicit requests until the policy is active | Leo learns nothing from conversations or meetings for weeks |
| Auto-save as soon as decisions promotes the policy | The offline gates prove the policy on made-up text; the person's own answers are the measure of whether a fact may be saved without asking |
| Candidates on the memory page only | The person has to go looking; a line under the answer is where the statement was made, and as quiet |
| Keep `leo_personalization` and design a screen for it | New UI for settings the new design dropped; the knobs fit as editable preferences |
| The summary's box as a Leo turn with cards | A panel opening over the settings dialog for a correction the person already typed |
| Facts outlive their source | A former employer's meeting or a disconnected chat would live on in a person's memory |
| The `record_recollections` port called by notes | A stage in notes' pipeline for what an event already says |
| HNSW per ADR 0033 | A filter to one person after the graph walk returns too few facts; exact search is complete and fast at these sizes |
| A per-run random boundary in segment 4 | Every turn would miss the prefix cache for everything after the profile core |
| Wrapped memory raises taint like any labelled text | Almost every turn would be tainted: web search behind a card, warnings on every write |
| Carry the draft's memory as it was used | No provenance, other people's claims as the owner's facts, raw commands as memories |

## Consequences

- Leo learns from the first day without using anything the person has not confirmed; the policy earns auto-save on the person's own answers.
- One extraction per turn (≈ $9.5 a day at 10 000 DAU) and one per meeting (≈ $4.5); memory ≈ $17 a day in all.
- The agent changes in narrow places: two ports amended and consulted, one new port, segment 4's HMAC boundary, a taint rule per fact, a toolset and a slot for the candidate's line.
- Decisions' step 10 gains the shadow on every statement and the online gate with its daily check.
- Notes' step 24 needs no code in notes. Chats owes a disconnection event and a reader of its retention.
- The target architecture's memory row and the Leo architecture's §6.3, §7, §10 and §13 are amended.

## Revisit when

- No language reaches 200 answered statements in 90 days: the minimum is revisited with the numbers.
- Candidate acceptance stays under 70% (ADR 0030) or auto-save closes repeatedly.
- Facts per person pass 5 000, or recall passes 20 ms p95 in a home (ADR 0033).
- Proactive's `/v1/ws/user` can push the candidate's line instead of the panel's read after a turn.
