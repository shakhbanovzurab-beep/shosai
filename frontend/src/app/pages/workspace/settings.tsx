import { useTranslations } from "use-intl";

import { PageMeta } from "@/app/root/page-meta";
import { TeamChatsSection } from "@/features/chats/ui/section/team-chats-section";
import { TeamSettingsScreen } from "@/features/workspace/ui/settings/settings-screen";

export function Component() {
  const t = useTranslations("workspace");
  return (
    <>
      <PageMeta title={t("meta.settings")} />
      <TeamSettingsScreen>
        <TeamChatsSection />
      </TeamSettingsScreen>
    </>
  );
}
