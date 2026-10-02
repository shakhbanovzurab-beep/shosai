import type { SourceFile } from "./sourceModules";
import type { RuleId } from "./violations";

/** Дерево-фикстура: путь от `frontend/` → текст модуля. */
export type FixtureTree = Readonly<Record<string, string>>;

/** Нарушение одного правила: дерево, где должно сработать оно и только оно. */
export interface RuleFixture {
  readonly rule: RuleId;
  readonly name: string;
  readonly tree: FixtureTree;
}

/** Превращает дерево-фикстуру в исходники для проверки. */
export const toSources = (tree: FixtureTree): SourceFile[] =>
  Object.entries(tree).map(([path, text]) => ({ path, text }));
