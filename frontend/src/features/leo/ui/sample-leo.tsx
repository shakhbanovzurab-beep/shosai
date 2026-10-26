"use client";

import type * as React from "react";

import { usePathname } from "@/lib/navigation";

import { type LeoContext, PERSONAL_CONTEXT } from "../domain/context";
import { useLeoChat } from "../model/use-leo-chat";
import { LeoWidget } from "./leo-widget";

/** Leo на примерном `/api/leo`: хаб — до своего шага (agent, шаг 20). */
export function SampleLeo({
  context = PERSONAL_CONTEXT,
  notice = null,
}: {
  readonly context?: LeoContext;
  readonly notice?: React.ReactNode;
}) {
  const pathname = usePathname();
  const chat = useLeoChat({ page: pathname, context });
  return <LeoWidget chat={chat} context={context} notice={notice} />;
}
