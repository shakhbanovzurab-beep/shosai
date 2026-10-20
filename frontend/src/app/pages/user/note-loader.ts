import { data, type LoaderFunctionArgs } from "react-router";

import { loadMeeting } from "@/features/notes/model/meeting-resource";
import { ApiError } from "@/lib/api/errors";

/** Встреча по адресу с сервера; чужая или неизвестная — страница «не найдено». */
export async function loader({ params }: LoaderFunctionArgs) {
  try {
    return await loadMeeting(params.id ?? "");
  } catch (error) {
    if (error instanceof ApiError && (error.status === 404 || error.status === 422)) throw data(null, { status: 404 });
    throw error;
  }
}
