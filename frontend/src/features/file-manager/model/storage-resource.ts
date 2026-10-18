"use client";

import { usePollingResource } from "@/hooks/use-polling-resource";
import { createPollingResource } from "@/lib/polling-resource";

import { filesApi } from "../api/files-api";

/*
 * The person's storage and Leo's bytes against the plan (FL-D2, FL-D10), for File Manager's meter and the
 * banners of both screens. Uploads, copies and deletions refresh it.
 */
export const storageResource = createPollingResource(() => filesApi.storage());

export const useStorage = () => usePollingResource(storageResource);
