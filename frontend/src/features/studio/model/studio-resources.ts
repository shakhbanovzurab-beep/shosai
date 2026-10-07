"use client";

import { usePollingResource } from "@/hooks/use-polling-resource";
import { createPollingResource } from "@/lib/polling-resource";

import { studioApi } from "../api/studio-api";

export const contextResource = createPollingResource(studioApi.getContext);
/** The subscription's models and each role's settings; also read by Settings › Leo and the admin panel. */
export const modelsResource = createPollingResource(studioApi.listModels);
export const promptsResource = createPollingResource(studioApi.listPrompts);
export const skillsResource = createPollingResource(studioApi.listSkills);

export const useStudioContext = () => usePollingResource(contextResource);
export const usePrompts = () => usePollingResource(promptsResource);
export const useStudioModels = () => usePollingResource(modelsResource);
export const useSkills = () => usePollingResource(skillsResource);
