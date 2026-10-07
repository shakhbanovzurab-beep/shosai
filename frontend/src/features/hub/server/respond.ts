import { NextResponse } from "next/server";

import { getTranslations } from "next-intl/server";

import { forwardToBackend } from "@/server/backend-proxy";

import { HUB_NAME_MAX, HUB_NAME_MIN, type Loaded } from "../domain/contract";
import type { HubErrorCode } from "../domain/errors";

/* Shared plumbing of the Hub's route handlers: errors with codes, the backend first, then the demo. */

/** A refusal's words in the request's interface language (the `hubApi` catalog), as a backend would answer. */
async function wordsFor(code: HubErrorCode) {
  const t = await getTranslations("hubApi");
  if (code === "name_too_short") return t("errors.name_too_short", { min: HUB_NAME_MIN });
  if (code === "name_too_long") return t("errors.name_too_long", { max: HUB_NAME_MAX });
  return t(`errors.${code}`);
}

/**
 * `{ "detail": { "code", "message" } }`. The client words the code itself; the message, in the request's
 * interface language, is for any other reader of the API.
 */
export const fail = async (code: HubErrorCode, status: number) =>
  NextResponse.json({ detail: { code, message: await wordsFor(code) } }, { status });

export const notFound = () => fail("not_found", 404);

export const readJson = (request: Request) => request.json().catch(() => null) as Promise<unknown>;

const FAULT = /(?:^|;\s*)hub_demo_fault=(partial|error)/;

/**
 * The demo can act out a partial answer or an outage, so the screens' states can be seen without a
 * broken backend: set the `hub_demo_fault` cookie to "partial" or "error". Only the demo reads it.
 */
export function demoFault(request: Request): "partial" | "error" | null {
  const match = FAULT.exec(request.headers.get("cookie") ?? "");
  return match ? (match[1] as "partial" | "error") : null;
}

/** A block's data; under the "partial" fault only part of it arrives, and it says so. */
export function loaded<T>(request: Request, data: T, trim: (data: T) => T) {
  const partial = demoFault(request) === "partial";
  return NextResponse.json<Loaded<T>>({ data: partial ? trim(data) : data, partial });
}

/** The first half of a list, for a partial answer. */
export const half = <T>(items: T[]) => items.slice(0, Math.ceil(items.length / 2));

/**
 * The common start of every Hub route: the backend's answer when BACKEND_API_URL is set, otherwise
 * the demo's. Under the "error" fault, reads fail the way an outage would.
 */
export async function withBackend(
  request: Request,
  path: string,
  run: () => Response | Promise<Response>,
): Promise<Response> {
  const upstream = await forwardToBackend(request, `/v1${path}`);
  if (upstream) return upstream;
  if (request.method === "GET" && demoFault(request) === "error") return fail("unknown", 503);
  return run();
}

export type IdCtx = { params: Promise<{ id: string }> };
export type SessionCtx = { params: Promise<{ id: string; sessionId: string }> };
export type MaterialCtx = { params: Promise<{ id: string; materialId: string }> };

export const e = encodeURIComponent;
