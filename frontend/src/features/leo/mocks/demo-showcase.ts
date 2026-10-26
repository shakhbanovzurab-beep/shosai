import type { Scenario } from "./demo-scenarios";

/*
 * Витрина ответа Leo для `npm run dev` («showcase» в вопросе): длинный ответ с кодом, формулами, диаграммами
 * Mermaid и таблицей, шаги с поисками и источниками. На ней видно, как панель рисует каждый блок, как держит
 * прокрутку у конца, пока ответ пишется, и как выглядит состояние «думает».
 */

const FENCE = "```";

const ANSWER = [
  "## Release plan, at a glance",
  "",
  "Here is the **rollout** with the numbers behind it, so you can check every step.",
  "",
  "### The math",
  "",
  "Weekly active people grow as $U(t) = U_0 \\cdot e^{kt}$, so after a month",
  "",
  "$$",
  "U(30) = 120 \\cdot e^{0.05 \\cdot 30} \\approx 537",
  "$$",
  "",
  "and the trial converts at \\(\\frac{18}{120} = 15\\%\\). A price of $15 a seat stays a price, not a formula.",
  "",
  "### The code",
  "",
  `${FENCE}ts`,
  "type Plan = { name: string; seats: number; price: number };",
  "",
  "// The month's revenue of every plan.",
  "export function monthly(plans: Plan[]): number {",
  "  return plans.reduce((sum, plan) => sum + plan.seats * plan.price, 0);",
  "}",
  FENCE,
  "",
  `${FENCE}python`,
  "def churn(active: int, lost: int) -> float:",
  '    """Share of people lost this month."""',
  "    return lost / active if active else 0.0",
  FENCE,
  "",
  "### The flow",
  "",
  `${FENCE}mermaid`,
  "flowchart LR",
  "  A[Question] --> B{Needs data?}",
  "  B -- yes --> C[Search notes]",
  "  B -- no --> D[Answer]",
  "  C --> D",
  FENCE,
  "",
  `${FENCE}mermaid`,
  "sequenceDiagram",
  "  participant P as Person",
  "  participant L as Leo",
  "  P->>L: Ask about the release",
  "  L-->>P: The plan with its sources",
  FENCE,
  "",
  "| Step | Owner | Due |",
  "|---|---|---|",
  "| Pilot | Mara | Nov 3 |",
  "| Rollout | Jonas | Nov 17 |",
  "",
  "That is the whole plan; ask me to change any step.",
].join("\n");

export const SHOWCASE: Scenario = {
  steps: [
    { action: "search_knowledge", detail: "release plan", result: "Found 3", ms: 900 },
    { action: "search_meetings", detail: "Weekly sync", result: "Found 2", ms: 700 },
    { action: "web_search", detail: "seat pricing benchmarks", result: "Found 4", ms: 1100 },
  ],
  sources: [
    {
      id: "m-weekly",
      kind: "meeting",
      // i18n-ignore: демо-данные; источники сервер пишет на языке человека
      title: "Weekly sync",
      space: "Lumen",
      locator: "12:40",
      quote: "",
      highlight: [],
    },
    {
      id: "n-plan",
      kind: "note",
      // i18n-ignore: демо-данные; источники сервер пишет на языке человека
      title: "Release plan",
      space: "Lumen",
      locator: null,
      quote: "",
      highlight: [],
    },
    {
      id: "https://example.com/pricing",
      kind: "web",
      // i18n-ignore: демо-данные; источники сервер пишет на языке человека
      title: "example.com — Seat pricing",
      space: "Web",
      locator: null,
      quote: "",
      highlight: [],
    },
  ],
  answer: ANSWER,
};
