import { useTranslations } from "use-intl";

import { PageMeta } from "@/app/root/page-meta";
import { RoomScreen } from "@/features/meetings/ui/room/room-screen";
import { useParams } from "@/lib/navigation";

/** Комната Shosai по ссылке `/app/meet/{token}`: вошедший человек или гость, вне панели кабинета. */
export function Component() {
  const t = useTranslations("meetingRoom");
  const { token = "" } = useParams<{ token: string }>();
  return (
    <>
      <PageMeta title={t("metaTitle")} />
      <RoomScreen key={token} token={token} />
    </>
  );
}
