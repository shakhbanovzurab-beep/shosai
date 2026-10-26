"use client";

import { usePathname } from "@/lib/navigation";

import { type LeoContext, PERSONAL_CONTEXT } from "../domain/context";
import { useAgentChat } from "../model/use-agent-chat";
import { LeoWidget } from "./leo-widget";

/** Leo на настоящем API: в Personal, в workspace или на платформе в админке; разговор ведёт сервер. */
export function AgentLeo({ context = PERSONAL_CONTEXT }: { readonly context?: LeoContext }) {
  const pathname = usePathname();
  const chat = useAgentChat({ page: pathname, context });
  return <LeoWidget chat={chat} context={context} />;
}
