import { PageMeta } from "@/app/root/page-meta";
import { RolesScreen } from "@/features/admin-roles/ui/roles-screen";

export function Component() {
  return (
    <>
      <PageMeta title="Роли" description="Просмотр уровней доступа и управление ролями и правами в организации." />
      <RolesScreen />
    </>
  );
}
