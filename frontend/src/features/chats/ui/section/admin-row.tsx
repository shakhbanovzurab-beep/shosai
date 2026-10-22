"use client";

import { MessengerTile } from "@/components/brand/messenger-mark";

import type { ChatConnection, ChatSettings } from "../../domain/contract";
import { ProblemFix } from "../fixes/problem-fix";
import { ChatMenu } from "./chat-menu";
import { ChatRowBody, ChatRowMeta, ChatRowProblem, ChatRowRoot, ChatRowTitle } from "./chat-row";

/** Строка чата для владельца и админов: то же, что у всех, плюс действие, которое чинит проблему, и меню. */
export function AdminConnectionRow({
  workspaceId,
  settings,
  connection,
}: {
  workspaceId: string;
  settings: ChatSettings;
  connection: ChatConnection;
}) {
  return (
    <ChatRowRoot>
      <MessengerTile messenger={connection.messenger} />
      <ChatRowBody>
        <ChatRowTitle connection={connection} />
        <ChatRowMeta connection={connection} />
        <ChatRowProblem connection={connection}>
          <ProblemFix workspaceId={workspaceId} settings={settings} connection={connection} />
        </ChatRowProblem>
      </ChatRowBody>
      <ChatMenu workspaceId={workspaceId} settings={settings} connection={connection} />
    </ChatRowRoot>
  );
}
