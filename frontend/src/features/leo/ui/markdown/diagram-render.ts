import type { MermaidConfig } from "mermaid";

/*
 * Диаграммы Mermaid в ответе Leo — в цветах и шрифте кабинета: тема `base`, её переменные — из токенов темы на
 * странице, поэтому диаграмма следует светлой и тёмной теме и пресету. Режим `strict`: подписи — текст SVG без HTML,
 * клики и ссылки выключены, разметку чистит DOMPurify. SVG встаёт в страницу узлами, без строки HTML.
 */

// Свои тема и вид у каждого типа диаграмм: Mermaid 12 ставит многим тему `redux-color` и вид `neo`.
const OURS = { theme: "base", look: "classic" } as const;

const BASE: MermaidConfig = {
  startOnLoad: false,
  securityLevel: "strict",
  htmlLabels: false,
  ...OURS,
  // Раскладка dagre: ELK, раскладка Mermaid 12 по умолчанию, весит 440 КБ gzip и в сборку не входит
  // (tooling/mermaid-without-elk.ts).
  layout: "dagre",
  suppressErrorRendering: true,
  // Ограничения разбора: модель не раздует страницу диаграммой на тысячи узлов.
  maxTextSize: 20_000,
  maxEdges: 300,
  // Плотнее, чем по умолчанию: ответ уже страницы, а схема должна читаться без лупы.
  flowchart: { ...OURS, nodeSpacing: 30, rankSpacing: 36, padding: 10, diagramPadding: 4 },
  state: { ...OURS, layout: "dagre" },
  swimlane: OURS,
  agentflow: OURS,
  sequence: OURS,
  class: OURS,
  er: OURS,
  requirement: OURS,
  usecase: OURS,
  venn: OURS,
};

// Мельче этой доли своего размера диаграмма не сжимается: текст 13 px остаётся не меньше 10 px.
const MIN_SCALE = 0.75;

// Токены кабинета, из которых собирается тема диаграммы.
const TOKENS = ["card", "foreground", "muted", "muted-foreground", "border", "accent", "primary"] as const;
const CHART = ["chart-1", "chart-2", "chart-3", "chart-4", "chart-5"] as const;

/** Тема диаграммы: тёмная ли она и цвета, приведённые к hex, — Mermaid сам считает из них оттенки. */
export interface DiagramTheme {
  readonly dark: boolean;
  readonly font: string;
  readonly colors: Readonly<Record<(typeof TOKENS)[number] | (typeof CHART)[number], string>>;
}

const byte = (value: number) => value.toString(16).padStart(2, "0");

/**
 * Тема по токенам на странице сейчас. Цвет oklch холст отдаёт обратно как есть, поэтому он закрашивает пиксель
 * в sRGB и читает его: так получается hex, который Mermaid разбирает. Полупрозрачный токен (граница тёмной темы)
 * ложится на фон карточки — каким его и видно.
 */
export function pageTheme(dark: boolean): DiagramTheme {
  const style = getComputedStyle(document.documentElement);
  const canvas = document.createElement("canvas");
  canvas.width = 1;
  canvas.height = 1;
  const probe = canvas.getContext("2d", { willReadFrequently: true });
  const card = style.getPropertyValue("--card").trim();
  const hex = (token: string) => {
    const value = style.getPropertyValue(`--${token}`).trim();
    if (probe === null || value === "") return value;
    probe.fillStyle = card;
    probe.fillRect(0, 0, 1, 1);
    probe.fillStyle = value;
    probe.fillRect(0, 0, 1, 1);
    const [red, green, blue] = probe.getImageData(0, 0, 1, 1).data;
    return `#${byte(red)}${byte(green)}${byte(blue)}`;
  };
  const colors = Object.fromEntries([...TOKENS, ...CHART].map((token) => [token, hex(token)]));
  return { dark, font: getComputedStyle(document.body).fontFamily, colors: colors as DiagramTheme["colors"] };
}

function variablesOf({ dark, font, colors: c }: DiagramTheme): Record<string, string | boolean> {
  return {
    darkMode: dark,
    fontFamily: font,
    fontSize: "13px",
    useGradient: false,
    dropShadow: "none",
    background: c.card,
    primaryColor: c.muted,
    mainBkg: c.muted,
    nodeBorder: c.border,
    primaryTextColor: c.foreground,
    primaryBorderColor: c.border,
    secondaryColor: c.accent,
    tertiaryColor: c.card,
    lineColor: c["muted-foreground"],
    textColor: c.foreground,
    titleColor: c.foreground,
    edgeLabelBackground: c.card,
    clusterBkg: c.card,
    clusterBorder: c.border,
    actorBkg: c.muted,
    actorBorder: c.border,
    actorTextColor: c.foreground,
    signalColor: c["muted-foreground"],
    signalTextColor: c.foreground,
    labelBoxBkgColor: c.muted,
    noteBkgColor: c.accent,
    noteBorderColor: c.border,
    noteTextColor: c.foreground,
    activationBkgColor: c.accent,
    ...Object.fromEntries(CHART.map((token, index) => [`pie${index + 1}`, c[token]])),
  };
}

type Mermaid = typeof import("mermaid").default;

let library: Promise<Mermaid> | null = null;
let queue: Promise<unknown> = Promise.resolve();
let drawn = 0;

// Сама библиотека — с первой диаграммой; не загрузилась — следующая диаграмма пробует снова.
function mermaidLibrary(): Promise<Mermaid> {
  library ??= import("mermaid").then(
    (module) => module.default,
    (error: unknown) => {
      library = null;
      throw error;
    },
  );
  return library;
}

/** SVG диаграммы по её тексту; ошибка разбора — отказ промиса. Рисунки идут по одному: тема у Mermaid общая. */
export function renderDiagram(source: string, theme: DiagramTheme): Promise<string> {
  drawn += 1;
  const id = `leo-diagram-${drawn}`;
  const run = queue.then(async () => {
    const mermaid = await mermaidLibrary();
    mermaid.initialize({ ...BASE, darkMode: theme.dark, fontFamily: theme.font, themeVariables: variablesOf(theme) });
    return (await mermaid.render(id, source)).svg;
  });
  queue = run.catch(() => undefined);
  return run;
}

/**
 * Ставит SVG в узел вместо прежнего содержимого; не SVG — false. Диаграмма вписывается в ширину ответа, но не
 * мельче `MIN_SCALE` своего размера: дальше она прокручивается вбок, а не сжимается до нечитаемого текста.
 */
export function placeDiagram(svg: string, into: HTMLElement): boolean {
  const root = new DOMParser().parseFromString(svg, "image/svg+xml").documentElement;
  if (!(root instanceof SVGSVGElement)) return false;
  const { width } = root.viewBox.baseVal;
  if (width > 0) {
    root.setAttribute("width", "100%");
    root.removeAttribute("height");
    root.style.maxWidth = `${Math.ceil(width)}px`;
    root.style.minWidth = `${Math.ceil(width * MIN_SCALE)}px`;
  }
  into.replaceChildren(document.importNode(root, true));
  return true;
}
