"use client";

import { usePollingResource } from "@/hooks/use-polling-resource";
import { createPollingResource } from "@/lib/polling-resource";

import { upgradeApi } from "../api/upgrade-api";

export const plansResource = createPollingResource(upgradeApi.plans);

export const usePlans = () => usePollingResource(plansResource);
