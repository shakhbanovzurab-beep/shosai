"use client";

import { toast } from "sonner";

import { usePollingResource } from "@/hooks/use-polling-resource";
import { errorMessage } from "@/lib/errors";
import { createPollingResource, type ResourceState } from "@/lib/polling-resource";

import { appsApi } from "../api/apps-api";
import type { AppRelease, ReleasePatch, ReleasesResponse } from "../domain/contract";

export const releasesResource = createPollingResource(appsApi.list);

export function useReleases(): ResourceState<ReleasesResponse> {
  return usePollingResource(releasesResource);
}

const replace = (release: AppRelease) =>
  releasesResource.update((data) => ({
    ...data,
    releases: data.releases.map((r) => (r.id === release.id ? release : r)),
  }));

/** Shows a new upload at the top of the history. */
export const addRelease = (release: AppRelease) =>
  releasesResource.update((data) => ({ ...data, releases: [release, ...data.releases] }));

async function patch(release: AppRelease, change: ReleasePatch, success: string, failure: string) {
  try {
    replace(await appsApi.patch(release.id, change));
    toast.success(success);
    return true;
  } catch (error) {
    toast.error(failure, { description: errorMessage(error) });
    return false;
  }
}

export const publishRelease = (release: AppRelease) =>
  patch(release, { status: "published" }, `Версия ${release.version} опубликована`, "Не удалось опубликовать");

export const revokeRelease = (release: AppRelease) =>
  patch(release, { status: "revoked" }, `Версия ${release.version} отозвана`, "Не удалось отозвать");

export const setRollout = (release: AppRelease, percent: number) =>
  patch(
    release,
    { rollout_percent: percent },
    `Раскатка ${release.version}: ${percent}%`,
    "Не удалось изменить раскатку",
  );

export async function deleteDraft(release: AppRelease) {
  try {
    await appsApi.remove(release.id);
    releasesResource.update((data) => ({ ...data, releases: data.releases.filter((r) => r.id !== release.id) }));
    toast.success(`Черновик ${release.version} удалён`);
  } catch (error) {
    toast.error("Не удалось удалить черновик", { description: errorMessage(error) });
  }
}
