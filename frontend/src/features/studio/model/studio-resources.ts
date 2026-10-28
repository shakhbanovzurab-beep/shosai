"use client";

import { usePollingResource } from "@/hooks/use-polling-resource";
import { createPollingResource } from "@/lib/polling-resource";

import { skillsApi } from "../api/skills-api";
import { studioApi } from "../api/studio-api";

export const contextResource = createPollingResource(studioApi.getContext);
/** Модели тарифа человека и настройки каждой роли. */
export const modelsResource = createPollingResource(studioApi.listModels);
export const promptsResource = createPollingResource(studioApi.listPrompts);
export const skillsResource = createPollingResource(skillsApi.list);

export const useStudioContext = () => usePollingResource(contextResource);
export const usePrompts = () => usePollingResource(promptsResource);
export const useStudioModels = () => usePollingResource(modelsResource);
export const useSkills = () => usePollingResource(skillsResource);
