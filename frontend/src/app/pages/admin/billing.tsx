import { PageMeta } from "@/app/root/page-meta";
import { BillingScreen } from "@/features/admin-billing/ui/billing-screen";

export function Component() {
  return (
    <>
      <PageMeta title="Финансы и биллинг" />
      <BillingScreen />
    </>
  );
}
