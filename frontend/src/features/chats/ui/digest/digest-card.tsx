"use client";

import { useTranslations } from "use-intl";

import type { ChatDigest } from "../../domain/digest-contract";
import { DIGEST_SECTIONS, digestContent } from "../../domain/digest-rules";
import { CoverageNotes, DigestHeader } from "./digest-header";
import { DigestSectionView } from "./digest-section";
import { DigestFrame } from "./digest-states";

/** Нечего показать: сообщений за период не было или отмечать в них нечего. */
function NothingToNote({ digest, content }: { digest: ChatDigest; content: "no_messages" | "nothing_found" }) {
  const t = useTranslations("chatsDigest");
  const chat = digest.chat.messenger === "slack" ? `#${digest.chat.title}` : digest.chat.title;
  return (
    <p className="text-muted-foreground text-sm">
      {content === "no_messages"
        ? t.rich("states.noMessages", { chat: () => <bdi>{chat}</bdi> })
        : t("states.nothingFound", { count: digest.coverage.messages_read })}
    </p>
  );
}

/** Карточка дайджеста (план CHATS-frontend §3.8): шапка, оговорки, разделы — пустые не показываются. */
export function DigestCard({ digest, label }: { digest: ChatDigest; label: string }) {
  const content = digestContent(digest);
  return (
    <DigestFrame label={label}>
      <DigestHeader digest={digest} />
      <CoverageNotes digest={digest} />
      {content === "items" ? (
        DIGEST_SECTIONS.map((section) => <DigestSectionView key={section} digest={digest} section={section} />)
      ) : (
        <NothingToNote digest={digest} content={content} />
      )}
    </DigestFrame>
  );
}
