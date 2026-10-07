import { File, FileArchive, FileChartColumn, FileCode, FileImage, FilePen, FileSliders, FileText } from "lucide-react";

import type { FileKind } from "../domain/contract";

export const fileIcons = {
  archive: FileArchive,
  design: FilePen,
  document: FileText,
  image: FileImage,
  other: File,
  pdf: File,
  presentation: FileSliders,
  spreadsheet: FileChartColumn,
  text: FileCode,
} satisfies Record<FileKind, typeof File>;
