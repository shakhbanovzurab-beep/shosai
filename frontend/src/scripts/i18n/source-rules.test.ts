import { describe, it } from "vitest";

import { scanSource } from "./source-rules";
import assert from "node:assert/strict";

const scan = (code: string) => scanSource("x.tsx", code).map((problem) => problem.message);

describe("scanSource", () => {
  it("finds hardcoded copy in JSX, attributes, toasts and copy objects", () => {
    assert.deepEqual(scan(`const a = <p>No files yet</p>;`), ["hardcoded text “No files yet”"]);
    assert.deepEqual(scan(`const a = <input placeholder="Search…" />;`), ["hardcoded placeholder “Search…”"]);
    assert.deepEqual(scan(`toast.error("Couldn’t save");`), ["hardcoded toast “Couldn’t save”"]);
    // biome-ignore lint/suspicious/noTemplateCurlyInString: the scanned source itself holds a template literal
    assert.deepEqual(scan("toast(`Moved ${n} files`);"), ["hardcoded toast “Moved … files”"]);
    assert.deepEqual(scan(`const item = { title: "Download the app" };`), ["hardcoded title “Download the app”"]);
  });

  it("lets do-not-translate names stand alone", () => {
    assert.deepEqual(scanSource("x.tsx", "const a = <span>Leo</span>;", ["Leo"]), []);
    assert.equal(scanSource("x.tsx", "const a = <span>Ask Leo</span>;", ["Leo"]).length, 1);
  });

  it("leaves translated text, symbols and code alone", () => {
    assert.deepEqual(scan(`const a = <p title={t("title")}>{t("empty")} · {count}</p>;`), []);
    assert.deepEqual(scan(`const a = <span>⌘I</span>;`), []);
    assert.deepEqual(scan(`const id = "kanban-board"; const href = "/app/kanban";`), []);
    assert.deepEqual(scan(`const side = rtl ? "right" : "left";`), []);
    assert.deepEqual(scan(`send({ type: "error", message: "agent_failed" });`), []);
  });

  it("finds physical direction classes but not centring", () => {
    assert.deepEqual(scan(`const a = <div className="ml-2 sm:pr-4 text-left" />;`), [
      "physical class “ml-2”; use the logical one (ms/me, ps/pe, start/end, text-start…)",
      "physical class “sm:pr-4”; use the logical one (ms/me, ps/pe, start/end, text-start…)",
      "physical class “text-left”; use the logical one (ms/me, ps/pe, start/end, text-start…)",
    ]);
    assert.deepEqual(scan(`const a = <div className="ms-2 pe-4 text-start left-1/2 -translate-x-1/2" />;`), []);
    assert.deepEqual(scan(`const a = cn("border-r", open && "rounded-l-md");`).length, 2);
  });

  it("finds physical sides, fixed locales and English-only formatting", () => {
    assert.match(scan(`const a = <Sheet side="right" />;`)[0], /side="right" is physical/);
    assert.match(scan(`new Intl.NumberFormat("en-US");`)[0], /fixed locale/);
    assert.match(scan(`value.toLocaleString();`)[0], /toLocaleString\(\) ignores/);
    assert.match(scan(`import { format, addDays } from "date-fns";`)[0], /date-fns format/);
  });

  it("asks directional icons to mirror", () => {
    assert.match(scan(`const a = <ArrowLeft className="size-4" />;`)[0], /ArrowLeft points one way/);
    assert.deepEqual(scan(`const a = <ChevronRight className="size-4 rtl:-scale-x-100" />;`), []);
  });

  it("reads .ts files without JSX", () => {
    assert.deepEqual(scanSource("x.ts", "export const pick = <T,>(items: T[]) => items[0];"), []);
    assert.deepEqual(scanSource("x.ts", "export const first = <T>(items: T[]): T => items[0];"), []);
  });

  it("skips a line marked i18n-ignore", () => {
    const code = `// i18n-ignore: canvas text, drawn per direction below\nctx.textAlign = "left";`;
    assert.deepEqual(scan(code), []);
  });
});
