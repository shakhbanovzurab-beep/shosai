import { data, type LoaderFunctionArgs } from "react-router";

import { findMeetingNote } from "@/features/notes/data/meeting-notes";

/** Заметка по адресу; неизвестный id — страница «не найдено». */
export function loader({ params }: LoaderFunctionArgs) {
  const note = findMeetingNote(params.id ?? "");
  if (!note) throw data(null, { status: 404 });
  return note;
}
