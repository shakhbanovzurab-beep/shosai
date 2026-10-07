import { checkMessage, type LanguageRules } from "./message-rules";
import assert from "node:assert/strict";
import { describe, it } from "node:test";

const rules = (language: string, extra: Partial<LanguageRules> = {}): LanguageRules => ({
  language,
  doNotTranslate: ["Leo", "Notion"],
  avoid: [],
  sameAsEnglish: new Set(),
  notAllowed: ['"'],
  ...extra,
});

const FILES = "{count, plural, one {# file} other {# files}}";

describe("checkMessage", () => {
  it("accepts a faithful translation", () => {
    const ru = "{count, plural, one {# файл} few {# файла} many {# файлов} other {# файла}}";
    assert.deepEqual(checkMessage(FILES, ru, rules("ru")), []);
  });

  it("asks for every plural category the language has, and only those", () => {
    const ru = "{count, plural, one {# файл} other {# файлов}}";
    assert.deepEqual(checkMessage(FILES, ru, rules("ru")), [
      "{count, plural} lacks “few”",
      "{count, plural} lacks “many”",
    ]);
    const ja = "{count, plural, one {#件} other {#件}}";
    assert.deepEqual(checkMessage(FILES, ja, rules("ja")), ["{count, plural} has “one”, which ja doesn’t use"]);
  });

  it("allows exact matches on top of the categories", () => {
    const ja = "{count, plural, =0 {ファイルなし} other {#件のファイル}}";
    assert.deepEqual(checkMessage(FILES, ja, rules("ja")), []);
  });

  it("compares arguments with English", () => {
    const problems = checkMessage("Hello, {name}", "Hallo, {nom}", rules("de"));
    assert.deepEqual(problems, ["lacks {name:text}", "has {nom:text}, English doesn’t"]);
  });

  it("keeps select options as codes", () => {
    const en = "{kind, select, file {File} folder {Folder} other {Item}}";
    const de = "{kind, select, datei {Datei} ordner {Ordner} other {Element}}";
    assert.match(checkMessage(en, de, rules("de"))[0], /select \{kind\} options/);
  });

  it("reports empty and invalid messages", () => {
    assert.deepEqual(checkMessage("Save", "  ", rules("fr")), ["is empty"]);
    assert.match(checkMessage("Save", "{oops", rules("fr"))[0], /isn’t valid ICU/);
    assert.match(checkMessage(FILES, "{count, plural, one {x}}", rules("fr"))[0], /MISSING_OTHER_CLAUSE/);
  });

  it("flags text left in English unless the glossary allows it", () => {
    assert.match(checkMessage("Couldn’t save the file", "Couldn’t save the file", rules("fr"))[0], /same as English/);
    assert.match(checkMessage("Status", "Status", rules("ja"))[0], /same as English/);
    assert.deepEqual(checkMessage("Status", "Status", rules("fr")), []);
    assert.deepEqual(checkMessage("CRM", "CRM", rules("ja")), []);
    assert.deepEqual(checkMessage("Status", "Status", rules("ja", { sameAsEnglish: new Set(["Status"]) })), []);
    assert.deepEqual(checkMessage("{value}°", "{value}°", rules("fr")), []);
    assert.deepEqual(checkMessage("Notion", "Notion", rules("fr")), []);
  });

  it("keeps do-not-translate names", () => {
    assert.deepEqual(checkMessage("Ask Leo", "Спросить Лео", rules("ru")), ["must keep “Leo” as is"]);
    assert.deepEqual(checkMessage("Ask Leo", "Leonardo에게 질문", rules("ko")), ["must keep “Leo” as is"]);
  });

  it("accepts a German genitive of a name", () => {
    assert.deepEqual(checkMessage("Leo’s answers", "Leos Antworten", rules("de")), []);
  });

  it("ignores an avoided word that the English text itself contains", () => {
    const avoid = [{ term: "owner", use: "Inhaber" }];
    assert.deepEqual(checkMessage("owner/repo", "owner/repo", rules("de", { avoid })), []);
  });

  it("lets particles in other scripts follow a name directly", () => {
    assert.deepEqual(checkMessage("Ask Leo", "Leo에게 질문", rules("ko")), []);
    assert.deepEqual(checkMessage("Ask Leo", "Leoに質問", rules("ja")), []);
  });

  it("enforces the glossary's avoided words, in any case and form", () => {
    const avoid = [{ term: "дашборд", use: "панель" }];
    assert.deepEqual(checkMessage("Dashboard", "Дашборда нет", rules("ru", { avoid })), [
      "uses “дашборд”; the glossary says “панель”",
    ]);
  });

  it("lets a quoted name from another product's interface use an avoided word", () => {
    const avoid = [{ term: "アプリケーション", use: "アプリ" }];
    const ja = rules("ja", { avoid });
    assert.deepEqual(checkMessage("Drag it to Applications", "「アプリケーション」フォルダへ", ja), []);
    assert.deepEqual(checkMessage("Open the app", "アプリケーションを開く", ja), [
      "uses “アプリケーション”; the glossary says “アプリ”",
    ]);
  });

  it("doesn’t look for avoided words inside do-not-translate names", () => {
    const it = rules("it", {
      doNotTranslate: ["Google Workspace"],
      avoid: [{ term: "workspace", use: "spazio di lavoro" }],
    });
    assert.deepEqual(checkMessage("Connect Google Workspace", "Collega Google Workspace", it), []);
    assert.match(checkMessage("Open the workspace", "Apri il workspace", it)[0], /spazio di lavoro/);
  });

  it("checks typography in the words, not in ICU syntax", () => {
    assert.deepEqual(checkMessage("Saving…", "Saving...", rules("en")), ["uses ... instead of …"]);
    assert.deepEqual(checkMessage("Couldn’t save", "Couldn't save", rules("en")), ["uses ' instead of ’"]);
    assert.deepEqual(checkMessage("“{name}”", '"{name}"', rules("ru")), ['uses ", not used in ru']);
    const ar = rules("ar", { notAllowed: [",", "?"] });
    assert.deepEqual(
      checkMessage(
        FILES,
        "{count, plural, zero {لا ملفات} one {ملف} two {ملفان} few {# ملفات} many {# ملفًا} other {# ملف}}",
        ar,
      ),
      [],
    );
    assert.deepEqual(checkMessage("Rain, {now}", "مطر, {now}", ar), ["uses ,, not used in ar"]);
  });

  it("knows French spacing, Hindi danda and full-width CJK punctuation", () => {
    assert.match(checkMessage("Delete?", "Supprimer ?", rules("fr"))[0], /no-break space/);
    assert.deepEqual(checkMessage("Delete?", "Supprimer ?", rules("fr")), []);
    assert.match(checkMessage("Saved.", "सहेजा गया.", rules("hi"))[0], /।/);
    assert.match(checkMessage("Rain, {now}", "雨,{now}", rules("zh-Hant"))[0], /full-width/);
  });
});
