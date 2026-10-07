import ts from "typescript";

/*
 * Rules for source that is already localized (LOCALIZED_SOURCES): its words come from the catalogs, its
 * layout works right to left, and dates and numbers follow the interface language. A line (or the line
 * above it) carrying `i18n-ignore: <reason>` is skipped, for the rare case a rule doesn't fit.
 */

const TEXT_ATTRIBUTES = new Set(["aria-label", "aria-description", "aria-placeholder", "title", "placeholder", "alt"]);
const COPY_PROPERTY = /^(title|label|description|placeholder|message|text|hint|tooltip|heading|subtitle|caption)$/i;
const TOAST_METHODS = new Set(["success", "error", "info", "warning", "message", "loading", "promise"]);
const LETTERS = /\p{L}{2,}/u;
const CODE = /^[a-z][a-z0-9]*([_-][a-z0-9]+)+$/;
const PHYSICAL_CLASS =
  /^(?:[\w-]+:)*-?(?:m[lr]|p[lr]|scroll-[mp][lr]|left|right|border-[lr]|rounded-(?:[lr]|tl|tr|bl|br)|text-(?:left|right)|float-(?:left|right)|clear-(?:left|right))(?:-|$)/;
const CENTERING = /^(?:[\w-]+:)*(?:left|right)-1\/2$/;
const DIRECTIONAL_ICONS =
  /^(ArrowLeft|ArrowRight|ArrowUpRight|ArrowUpLeft|ArrowDownRight|ArrowDownLeft|ChevronLeft|ChevronRight|ChevronsLeft|ChevronsRight|CornerDownRight|CornerDownLeft|CornerUpRight|CornerUpLeft|PanelLeft\w*|PanelRight\w*|Undo2?|Redo2?|Reply|ReplyAll|Forward|LogIn|LogOut|ExternalLink|MoveLeft|MoveRight|SendHorizontal|ListIndentIncrease|ListIndentDecrease)(Icon)?$/;
const DATE_FNS_FORMATTERS = new Set([
  "format",
  "formatDistance",
  "formatDistanceToNow",
  "formatDistanceStrict",
  "formatRelative",
  "formatDuration",
]);

export interface SourceProblem {
  line: number;
  message: string;
}

const isStringy = (node: ts.Node): node is ts.StringLiteral | ts.NoSubstitutionTemplateLiteral =>
  ts.isStringLiteral(node) || ts.isNoSubstitutionTemplateLiteral(node);

/** The literal text a string or template expression carries, for the "is this copy?" question. */
function literalText(node: ts.Node | undefined): string | null {
  if (!node) return null;
  if (ts.isJsxExpression(node)) return literalText(node.expression);
  if (isStringy(node)) return node.text;
  if (ts.isTemplateExpression(node))
    return [node.head.text, ...node.templateSpans.map((s) => s.literal.text)].join("…");
  return null;
}

// A bare "left" / "right" is a value (a Radix side picked from the direction), not a class.
const physicalClasses = (text: string) =>
  text
    .split(/\s+/)
    .filter((token) => PHYSICAL_CLASS.test(token) && !CENTERING.test(token) && token !== "left" && token !== "right");

function jsxTagName(node: ts.JsxOpeningLikeElement) {
  return ts.isIdentifier(node.tagName) ? node.tagName.text : "";
}

function hasRtlClass(node: ts.JsxOpeningLikeElement) {
  return node.attributes.properties.some(
    (attribute) =>
      ts.isJsxAttribute(attribute) &&
      attribute.name.getText() === "className" &&
      /\brtl:/.test(attribute.initializer?.getText() ?? ""),
  );
}

function isToastCall(node: ts.CallExpression) {
  const callee = node.expression;
  if (ts.isIdentifier(callee)) return callee.text === "toast";
  return (
    ts.isPropertyAccessExpression(callee) &&
    ts.isIdentifier(callee.expression) &&
    callee.expression.text === "toast" &&
    TOAST_METHODS.has(callee.name.text)
  );
}

/** Problems in one localized source file. `names` (do-not-translate: "Leo", "MCP"…) never count as copy. */
export function scanSource(path: string, source: string, names: readonly string[] = []): SourceProblem[] {
  // .ts files are read without JSX, so a generic arrow `<T>(x) =>` isn't taken for a tag.
  const kind = path.endsWith(".tsx") ? ts.ScriptKind.TSX : ts.ScriptKind.TS;
  const file = ts.createSourceFile(path, source, ts.ScriptTarget.Latest, true, kind);
  const lines = source.split("\n");
  const problems: SourceProblem[] = [];
  const report = (node: ts.Node, message: string) => {
    const line = file.getLineAndCharacterOfPosition(node.getStart(file)).line;
    if (/i18n-ignore/.test(lines[line] ?? "") || /i18n-ignore/.test(lines[line - 1] ?? "")) return;
    problems.push({ line: line + 1, message });
  };
  // Codes ("agent_failed", "kanban-board") are not copy; neither are do-not-translate names on their own.
  const isCopy = (text: string) =>
    !CODE.test(text.trim()) && LETTERS.test(names.reduce((rest, name) => rest.replaceAll(name, ""), text));
  const copy = (node: ts.Node | undefined, where: string) => {
    const text = node ? literalText(node) : null;
    if (text && isCopy(text)) report(node as ts.Node, `hardcoded ${where} “${text.trim().slice(0, 40)}”`);
  };

  const visit = (node: ts.Node) => {
    if (ts.isJsxText(node) && isCopy(node.text)) report(node, `hardcoded text “${node.text.trim().slice(0, 40)}”`);
    if (ts.isJsxAttribute(node) && TEXT_ATTRIBUTES.has(node.name.getText()))
      copy(node.initializer, node.name.getText());
    if (
      ts.isJsxAttribute(node) &&
      node.name.getText() === "side" &&
      /^"(left|right)"$/.test(node.initializer?.getText() ?? "")
    )
      report(node, `side=${node.initializer?.getText()} is physical; pick it from the text direction`);
    if (ts.isPropertyAssignment(node) && COPY_PROPERTY.test(node.name.getText()) && isStringy(node.initializer))
      copy(node.initializer, `${node.name.getText()}`);
    if (ts.isCallExpression(node) && isToastCall(node)) copy(node.arguments[0], "toast");
    if (isStringy(node) || ts.isTemplateHead(node) || ts.isTemplateMiddle(node) || ts.isTemplateTail(node)) {
      for (const token of physicalClasses(node.text))
        report(node, `physical class “${token}”; use the logical one (ms/me, ps/pe, start/end, text-start…)`);
      if (/^en-(US|GB)$/.test(node.text)) report(node, `fixed locale “${node.text}”; format in the interface language`);
    }
    if (ts.isCallExpression(node) && ts.isPropertyAccessExpression(node.expression)) {
      const method = node.expression.name.text;
      if (method === "toLocaleString" || method === "toLocaleDateString" || method === "toLocaleTimeString")
        report(node, `${method}() ignores the interface language; use useFormatter / getFormatter`);
    }
    if (ts.isImportDeclaration(node) && literalText(node.moduleSpecifier) === "date-fns") {
      const named = node.importClause?.namedBindings;
      if (named && ts.isNamedImports(named))
        for (const element of named.elements)
          if (DATE_FNS_FORMATTERS.has(element.name.text))
            report(element, `date-fns ${element.name.text} writes English; use useFormatter / getFormatter`);
    }
    if ((ts.isJsxOpeningElement(node) || ts.isJsxSelfClosingElement(node)) && DIRECTIONAL_ICONS.test(jsxTagName(node)))
      if (!hasRtlClass(node)) report(node, `${jsxTagName(node)} points one way; mirror it with rtl:-scale-x-100`);
    ts.forEachChild(node, visit);
  };
  visit(file);
  return problems;
}
