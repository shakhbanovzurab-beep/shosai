import { PageMeta } from "@/app/root/page-meta";
import { PlansScreen } from "@/features/admin-plans/ui/plans-screen";

export function Component() {
  return (
    <>
      <PageMeta
        title="Тарифы и промокоды"
        description="Управление тарифами Leo, их ценами и лимитами, а также промокодами."
      />
      <PlansScreen />
    </>
  );
}
