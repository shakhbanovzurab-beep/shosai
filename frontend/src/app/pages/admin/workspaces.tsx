import { PageMeta } from "@/app/root/page-meta";
import { WorkspacesScreen } from "@/features/admin-workspaces/ui/workspaces-screen";

export function Component() {
  return (
    <>
      <PageMeta title="Пространства" description="Рабочие пространства команд: места, оплата, активность и доступ." />
      <WorkspacesScreen />
    </>
  );
}
