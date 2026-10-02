/** Правила архитектуры фронтенда (план F2, §3.2). Допустимо ноль нарушений каждого. */
export type RuleId =
  | "layers"
  | "slice-contracts"
  | "shell-knows-no-slice"
  | "pure-model"
  | "ui-without-http"
  | "no-raw-http"
  | "query-keys-in-keys-modules"
  | "lazy-in-manifests"
  | "no-barrels"
  | "no-cycles";

/** Одно нарушение: правило, модуль, строка и что именно не так. */
export interface Violation {
  readonly rule: RuleId;
  readonly path: string;
  readonly line: number;
  readonly detail: string;
}
