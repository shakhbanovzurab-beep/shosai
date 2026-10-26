import { formatBytes } from "@/i18n/format-units";
import { DEFAULT_LANGUAGE } from "@/lib/language";

import type { LeoEvent } from "../domain/protocol";
import type { LeoRequest, LeoTurn } from "../domain/request";
import { type PlannedStep, pickScenario, type Scenario } from "./demo-scenarios";
import { type KnowledgeScope, knowledgeNote, knowledgeScope, knowledgeStepText } from "./knowledge";

const NOT_CONNECTED = "Not connected yet";

// Keyword → source steps. Used by the placeholder planner until a real model chooses its own tools.
const SOURCE_RULES: { pattern: RegExp; steps: (query: string) => PlannedStep[] }[] = [
  {
    pattern: /\b(web|internet|online|google|news|latest|price|weather)\b/i,
    steps: (query) => [
      { action: "web_search", detail: query, result: NOT_CONNECTED, ms: 1400 },
      { action: "web_read", detail: "Top results", result: NOT_CONNECTED, ms: 1100 },
    ],
  },
  {
    pattern: /\b(meeting|meetings|call|transcript)\b/i,
    steps: (query) => [{ action: "search_meetings", detail: query, result: NOT_CONNECTED, ms: 900 }],
  },
  {
    pattern: /\b(mail|email|emails|inbox|reply)\b/i,
    steps: (query) => [{ action: "search_mail", detail: query, result: NOT_CONNECTED, ms: 900 }],
  },
  {
    pattern: /\b(calendar|schedule|today|tomorrow|week|free|event)\b/i,
    steps: () => [{ action: "search_calendar", detail: "Next 7 days", result: NOT_CONNECTED, ms: 700 }],
  },
  {
    pattern: /\b(task|tasks|todo|kanban|board|overdue|focus)\b/i,
    steps: (query) => [{ action: "search_tasks", detail: query, result: NOT_CONNECTED, ms: 700 }],
  },
  {
    pattern: /\b(file|files|document|pdf|folder)\b/i,
    steps: (query) => [{ action: "search_files", detail: query, result: NOT_CONNECTED, ms: 800 }],
  },
  {
    pattern: /\b(prompt|prompts|model|models|context)\b/i,
    steps: (query) => [{ action: "search_prompts", detail: query, result: NOT_CONNECTED, ms: 700 }],
  },
];

/** Knowledge Leo may read in this context; a hub or an unknown workspace falls back to a placeholder. */
function knowledgeStep(query: string, scope: KnowledgeScope): PlannedStep {
  if (!scope) return { action: "search_knowledge", detail: query, result: NOT_CONNECTED, ms: 800 };
  return { action: "search_knowledge", ...knowledgeStepText(scope), ms: 900 };
}

function planSteps({ messages, page, files, locale }: LeoRequest, scope: KnowledgeScope): PlannedStep[] {
  const query = messages[messages.length - 1].content.slice(0, 80);
  const fileSteps = files.map(
    (file): PlannedStep => ({
      action: "read_file",
      detail: `${file.name} · ${formatBytes(locale ?? DEFAULT_LANGUAGE, file.size)}`,
      result: "Received",
      ms: 700,
    }),
  );
  const sources = SOURCE_RULES.filter((rule) => rule.pattern.test(query)).flatMap((rule) => rule.steps(query));

  return [
    { action: "analyze_request", detail: page ? `On ${page}` : undefined, ms: 500 },
    ...fileSteps,
    { action: "think", ms: 1300 },
    ...(sources.length > 0 || fileSteps.length > 0 ? sources : []),
    ...(scope || (sources.length === 0 && fileSteps.length === 0) ? [knowledgeStep(query, scope)] : []),
    { action: "synthesize", ms: 900 },
  ];
}

function composeAnswer({ messages, files }: LeoRequest, steps: PlannedStep[], scope: KnowledgeScope) {
  const question = messages[messages.length - 1].content || "your files";
  const sources = steps.filter((step) => step.result === NOT_CONNECTED).length;
  const filesNote =
    files.length > 0 ? ` I received **${files.length} ${files.length === 1 ? "file" : "files"}** as well.` : "";

  const sourcesNote = sources > 0 ? `, including **${sources} data ${sources === 1 ? "source" : "sources"}**` : "";
  const closing = scope
    ? "Reading inside files isn’t connected yet; once it is, I’ll answer from them and cite each one."
    : "My tools aren't connected to real data yet, so I can't give you an actual answer. Once the agent backend is wired up, every search and action will show up above exactly like this.";
  return [
    `I worked through **${steps.length} steps** for "${question}"${sourcesNote}.${filesNote}`,
    ...(scope ? ["", knowledgeNote(scope)] : []),
    "",
    closing,
  ].join("\n");
}

/** Шаги сценария между разбором вопроса и сборкой ответа. */
const scenarioSteps = (scenario: Scenario): PlannedStep[] => [
  { action: "analyze_request", ms: 500 },
  { action: "think", ms: 900 },
  ...scenario.steps,
  { action: "synthesize", ms: 700 },
];

const sleep = (ms: number, signal: AbortSignal) =>
  new Promise<void>((resolve) => {
    const timeout = setTimeout(resolve, ms);
    signal.addEventListener("abort", () => {
      clearTimeout(timeout);
      resolve();
    });
  });

// Placeholder agent: replays a plausible plan. Replace with the real agent loop, emitting the same events.
/**
 * The placeholder agent. A real model writes its steps' details and its answer in `turn.answerLanguage`;
 * this demo has no model, so its canned text stays English whatever language is asked for.
 */
export async function* runAgent(request: LeoTurn, signal: AbortSignal): AsyncGenerator<LeoEvent> {
  const startedAt = Date.now();
  // The permission check happens here, before anything is planned: Leo only sees what the account may use.
  const scope = knowledgeScope(request);
  const scenario = pickScenario(request.messages[request.messages.length - 1].content);
  const steps = scenario ? scenarioSteps(scenario) : planSteps(request, scope);

  for (const [index, step] of steps.entries()) {
    const id = `step-${index}`;
    yield { type: "step_start", id, action: step.action, detail: step.detail };
    await sleep(step.ms, signal);
    if (signal.aborted) return;
    yield { type: "step_end", id, status: "done", durationMs: step.ms, result: step.result };
  }

  if (scenario?.sources) yield { type: "sources", sources: scenario.sources };
  if (scenario?.artifact) yield { type: "artifact", artifact: scenario.artifact() };
  const writeStartedAt = Date.now();
  yield { type: "step_start", id: "step-answer", action: "write_answer" };
  const answer = scenario ? scenario.answer : composeAnswer(request, steps, scope);
  for (const token of answer.match(/\S+\s*|\n/g) ?? []) {
    await sleep(30, signal);
    if (signal.aborted) return;
    yield { type: "text", delta: token };
  }
  yield { type: "step_end", id: "step-answer", status: "done", durationMs: Date.now() - writeStartedAt };
  if (scenario?.proposal) yield { type: "proposal", proposal: scenario.proposal() };
  yield { type: "done", durationMs: Date.now() - startedAt };
}
