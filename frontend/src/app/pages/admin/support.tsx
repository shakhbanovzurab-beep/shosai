import { PageMeta } from "@/app/root/page-meta";
import { SupportScreen } from "@/features/admin-support/ui/support-screen";
import { useSearchParams } from "@/lib/navigation";

export function Component() {
  // `?ticket=<conversation id>` opens that conversation, e.g. from an issue on the errors page.
  return (
    <>
      <PageMeta title="Поддержка" />
      <SupportScreen initialTicket={useSearchParams().get("ticket")} />
    </>
  );
}
