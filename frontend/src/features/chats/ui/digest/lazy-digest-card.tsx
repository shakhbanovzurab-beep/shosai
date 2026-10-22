"use client";

import { type ComponentProps, lazy, Suspense } from "react";

import { DigestSkeleton } from "./digest-states";

// Дайджест в ответе Leo бывает редко: его код грузится, только когда он есть, а до того — каркас карточки.
const ChatDigestCard = lazy(() => import("./chat-digest-card").then((module) => ({ default: module.ChatDigestCard })));

export function LazyChatDigestCard(props: ComponentProps<typeof ChatDigestCard>) {
  return (
    <Suspense fallback={<DigestSkeleton label={props.label} />}>
      <ChatDigestCard {...props} />
    </Suspense>
  );
}
