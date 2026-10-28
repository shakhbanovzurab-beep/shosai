import { FEATURES, type PlatformConfig } from "./contract";

const onOff = (enabled: boolean) => (enabled ? "вкл." : "выкл.");

/** Конфигурация простым текстом, по факту на строку, — для сравнения версий бок о бок. */
export function configToText(config: PlatformConfig): string[] {
  const { safety } = config;
  const lines = [
    "## Системный промт",
    ...config.system_prompt.split("\n"),
    "",
    "## Правила безопасности",
    ...safety.rules.map((rule, index) => `${index + 1}. [${onOff(rule.enabled)}] ${rule.text}`),
    "",
    "## Запрещённые темы",
    ...safety.blocked_topics.map((topic) => `- ${topic}`),
  ];
  for (const feature of FEATURES) {
    const prompt = config.features[feature.id];
    lines.push("", `## Функция «${feature.label}» (${onOff(prompt.enabled)})`, ...prompt.content.split("\n"));
  }
  return lines;
}

export type DiffRow =
  | { kind: "same"; left: string; right: string }
  | { kind: "changed"; left: string | null; right: string | null };

const MAX_CELLS = 4_000_000;

/**
 * Line diff (longest common subsequence) laid out side by side: unchanged lines face each other,
 * and each run of removals is paired row by row with the run of additions that replaces it.
 */
export function diffLines(left: string[], right: string[]): DiffRow[] {
  const n = left.length;
  const m = right.length;
  if (n * m > MAX_CELLS) return pairRuns(left, right);

  // lcs[i][j] = LCS length of left[i..] and right[j..], flattened.
  const width = m + 1;
  const lcs = new Uint32Array((n + 1) * width);
  for (let i = n - 1; i >= 0; i--) {
    for (let j = m - 1; j >= 0; j--) {
      lcs[i * width + j] =
        left[i] === right[j]
          ? lcs[(i + 1) * width + j + 1] + 1
          : Math.max(lcs[(i + 1) * width + j], lcs[i * width + j + 1]);
    }
  }

  const rows: DiffRow[] = [];
  let removed: string[] = [];
  let added: string[] = [];
  const flush = () => {
    rows.push(...pairRuns(removed, added));
    removed = [];
    added = [];
  };
  let i = 0;
  let j = 0;
  while (i < n || j < m) {
    if (i < n && j < m && left[i] === right[j]) {
      flush();
      rows.push({ kind: "same", left: left[i], right: right[j] });
      i++;
      j++;
    } else if (j < m && (i === n || lcs[i * width + j + 1] >= lcs[(i + 1) * width + j])) {
      added.push(right[j++]);
    } else {
      removed.push(left[i++]);
    }
  }
  flush();
  return rows;
}

function pairRuns(removed: string[], added: string[]): DiffRow[] {
  return Array.from({ length: Math.max(removed.length, added.length) }, (_, index) => ({
    kind: "changed" as const,
    left: removed[index] ?? null,
    right: added[index] ?? null,
  }));
}
