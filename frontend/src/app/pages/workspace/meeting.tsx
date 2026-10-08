import { useTranslations } from "use-intl";

import { PageMeta } from "@/app/root/page-meta";
import { TeamMeetingScreen } from "@/features/workspace/ui/meetings/meeting-screen";
import { useParams } from "@/lib/navigation";

export function Component() {
  const t = useTranslations("workspace");
  const { id = "" } = useParams<{ id: string }>();
  return (
    <>
      <PageMeta title={t("meta.meeting")} />
      <TeamMeetingScreen meetingId={id} />
    </>
  );
}
