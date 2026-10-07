import { NextResponse } from "next/server";

import { forwardToBackend } from "@/server/backend-proxy";

import type { StudioContext } from "../domain/contract";
import { getContext, saveContext } from "./demo-context";
import { refuse } from "./problems";
import { contextBodySchema, firstIssue, readJson } from "./prompt-schemas";

const PATH = "/v1/studio/context";

/** /api/studio/context */
export const contextRoute = {
  async GET(request: Request) {
    const upstream = await forwardToBackend(request, PATH);
    if (upstream) return upstream;
    return NextResponse.json<StudioContext>(getContext());
  },

  async PUT(request: Request) {
    const upstream = await forwardToBackend(request, PATH);
    if (upstream) return upstream;
    const body = contextBodySchema.safeParse(await readJson(request));
    if (!body.success) return refuse(firstIssue(body.error), 422);
    return NextResponse.json<StudioContext>(saveContext(body.data.content.trim()));
  },
};
