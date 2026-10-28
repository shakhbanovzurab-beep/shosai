import { useTranslations } from "use-intl";

import { PageMeta } from "@/app/root/page-meta";
import { BroadcastScreen } from "@/features/meetings/ui/broadcast/broadcast-screen";
import { useParams } from "@/lib/navigation";

/** Трансляция по ссылке `/app/live/{token}`: сцена — в студии, зал — в эфире, вошедший человек или гость. */
export function Component() {
  const t = useTranslations("meetingBroadcast");
  const { token = "" } = useParams<{ token: string }>();
  return (
    <>
      <PageMeta title={t("metaTitle")} />
      <BroadcastScreen key={token} token={token} />
    </>
  );
}
