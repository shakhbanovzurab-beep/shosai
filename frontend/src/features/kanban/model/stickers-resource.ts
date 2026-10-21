"use client";

import { usePollingResource } from "@/hooks/use-polling-resource";
import { createPollingResource } from "@/lib/polling-resource";

import { stickersApi } from "../api/stickers-api";

/** Свои поля человека со всех досок: для «С других досок» и для того, что очистит удаление. */
export const ownedStickersResource = createPollingResource(stickersApi.list);

export const useOwnedStickers = () => usePollingResource(ownedStickersResource);
