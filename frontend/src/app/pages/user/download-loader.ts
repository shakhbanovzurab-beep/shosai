import { fetchDesktopDownloads } from "@/features/download/api/downloads-api";

/** Релизы обеих платформ читаются до показа страницы, чтобы карточки не мелькали пустыми. */
export const loader = fetchDesktopDownloads;
