import { searchValue } from "@/app/pages/search-record";
import { PageMeta } from "@/app/root/page-meta";
import { parseDashboardTab } from "@/features/admin-dashboard/domain/dashboard-tabs";
import { DashboardScreen } from "@/features/admin-dashboard/ui/dashboard-screen";
import { useSearchParams } from "@/lib/navigation";

export function Component() {
  return (
    <>
      <PageMeta title="Дашборд" />
      <DashboardScreen tab={parseDashboardTab(searchValue(useSearchParams(), "tab"))} />
    </>
  );
}
