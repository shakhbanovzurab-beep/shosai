// Проверка синтетических ответов по OpenAPI черновика (D1, contracts/draft/).
//
// Синтетический ответ пишется руками там, где стенд записи не может его
// получить. Чтобы он не стал выдумкой, метод и путь обязаны существовать в
// контракте черновика, а тело — подходить под схему, если этот статус там описан.

import { readFileSync } from "node:fs";
import path from "node:path";

import { Ajv2020 } from "ajv/dist/2020.js";
import addFormats from "ajv-formats";

import { PARITY_ROOT } from "../config.ts";
import type { JsonValue } from "../fixtures/format.ts";

export const DRAFT_OPENAPI_FILE = path.resolve(PARITY_ROOT, "..", "contracts", "draft", "openapi.json");

interface Operation {
  readonly responses?: Readonly<Record<string, { content?: Readonly<Record<string, { schema?: object }>> }>>;
}
interface OpenApi {
  readonly paths: Readonly<Record<string, Readonly<Record<string, Operation>>>>;
  readonly components?: object;
}

/** Путь подходит под шаблон: те же сегменты, `{параметр}` — любой непустой сегмент. */
function matchesTemplate(template: string, requestPath: string): boolean {
  const expected = template.split("/");
  const actual = requestPath.split("/");
  if (expected.length !== actual.length) return false;
  return expected.every((segment, index) => {
    const value = actual[index] ?? "";
    return segment.startsWith("{") && segment.endsWith("}") ? value !== "" : segment === value;
  });
}

export class DraftContract {
  private readonly spec: OpenApi;
  private readonly ajv = addFormats.default(new Ajv2020({ strict: false, allErrors: true }));
  constructor(file: string = DRAFT_OPENAPI_FILE) {
    this.spec = JSON.parse(readFileSync(file, "utf8")) as OpenApi;
  }

  /** Описание операции или null, если такого метода и пути у черновика нет. */
  operation(method: string, requestPath: string): Operation | null {
    const template = Object.keys(this.spec.paths).find((candidate) => matchesTemplate(candidate, requestPath));
    if (template === undefined) return null;
    return this.spec.paths[template]?.[method.toLowerCase()] ?? null;
  }

  /** Ошибки соответствия тела схеме; пусто — соответствует или статус не описан. */
  bodyProblems(operation: Operation, status: number, body: JsonValue): string[] {
    const schema = operation.responses?.[String(status)]?.content?.["application/json"]?.schema;
    if (schema === undefined) return [];
    const validate = this.ajv.compile({ ...schema, components: this.spec.components });
    if (validate(body)) return [];
    return (validate.errors ?? []).map((error) => `${error.instancePath || "/"} ${error.message ?? "не соответствует"}`);
  }
}
