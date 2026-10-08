import { PageMeta } from "@/app/root/page-meta";
import { UsersScreen } from "@/features/admin-users/ui/users-screen";

export function Component() {
  return (
    <>
      <PageMeta title="Пользователи" description="Просмотр, фильтрация и управление учётными записями пользователей." />
      <UsersScreen />
    </>
  );
}
