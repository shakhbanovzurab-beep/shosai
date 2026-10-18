import { describe, expectTypeOf, it } from "vitest";

import type { components } from "@/lib/api/generated/schema";

import type { FileFolder, FileItem, FilesResponse, UploadResponse } from "./contract";

type Schemas = components["schemas"];

// Контракт кабинета и ответы бэкенда (files, шаг 4) совпадают поле в поле: расхождение ломает typecheck.
describe("file manager contract", () => {
  it("matches the backend's responses", () => {
    expectTypeOf<Schemas["FileItem"]>().toEqualTypeOf<FileItem>();
    expectTypeOf<Schemas["FileFolder"]>().toEqualTypeOf<FileFolder>();
    expectTypeOf<Schemas["FilesResponse"]>().toEqualTypeOf<FilesResponse>();
    expectTypeOf<Schemas["UploadResponse"]>().toEqualTypeOf<UploadResponse>();
  });
});
