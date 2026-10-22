import { useTranslations } from "use-intl";

import { PageMeta } from "@/app/root/page-meta";
import { MessengerLinkHint } from "@/features/chats/ui/hint/link-hint";
import { TeamHomeScreen } from "@/features/workspace/ui/home/home-screen";

export function Component() {
  const t = useTranslations("workspace");
  return (
    <>
      <PageMeta title={t("meta.home")} />
      <TeamHomeScreen>
        <MessengerLinkHint />
      </TeamHomeScreen>
    </>
  );
}
