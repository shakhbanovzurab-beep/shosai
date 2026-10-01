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
import { matchesTemplate } from "../replay/path-template.ts";

export const DRAFT_OPENAPI_FILE = path.resolve(PARITY_ROOT, "..", "contracts", "draft", "openapi.json");

interface Operation {
  readonly responses?: Readonly<Record<string, { content?: Readonly<Record<string, { schema?: object }>> }>>;
}
interface OpenApi {
  readonly paths: Readonly<Record<string, Readonly<Record<string, Operation>>>>;
  readonly components?: object;
}

function isDomainRefusal(body: JsonValue): boolean {
  return typeof body === "object" && body !== null && !Array.isArray(body) && typeof body["detail"] === "string";
}

/**
 * Формат `time` Pydantic пишет для `datetime.time` и отдаёт время без пояса
 * («22:00:00»); `time` в ajv-formats требует пояс по RFC 3339. Проверка следует
 * за черновиком: пояс необязателен.
 */
const PYDANTIC_TIME = /^([01]\d|2[0-3]):[0-5]\d(:[0-5]\d(\.\d+)?)?(Z|[+-]([01]\d|2[0-3]):[0-5]\d)?$/i;

export class DraftContract {
  private readonly spec: OpenApi;
  private readonly ajv = addFormats
    .default(new Ajv2020({ strict: false, allErrors: true }))
    .addFormat("time", PYDANTIC_TIME);
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
    // 422 FastAPI описывает только как ошибку валидации тела (detail — массив).
    // Доменные отказы черновика — HTTPException(422, detail="код"): строка. Эта
    // форма в OpenAPI не попадает, но это настоящий ответ черновика.
    if (status === 422 && isDomainRefusal(body)) return [];
    const schema = operation.responses?.[String(status)]?.content?.["application/json"]?.schema;
    if (schema === undefined) return [];
    const validate = this.ajv.compile({ ...schema, components: this.spec.components });
    if (validate(body)) return [];
    return (validate.errors ?? []).map((error) => `${error.instancePath || "/"} ${error.message ?? "не соответствует"}`);
  }
}
