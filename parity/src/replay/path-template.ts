// Шаблон пути API: те же сегменты, `{параметр}` — любой непустой сегмент.
// Общий для подмен состояний и проверки по OpenAPI черновика.

export function matchesTemplate(template: string, requestPath: string): boolean {
  const expected = template.split("/");
  const actual = requestPath.split("/");
  if (expected.length !== actual.length) return false;
  return expected.every((segment, index) => {
    const value = actual[index] ?? "";
    return segment.startsWith("{") && segment.endsWith("}") ? value !== "" : segment === value;
  });
}
