import { PageMeta } from "@/app/root/page-meta";
import { UsersScreen } from "@/features/admin-users/ui/users-screen";
import { useSearchParams } from "@/lib/navigation";

export function Component() {
  const query = useSearchParams().get("q") ?? "";
  return (
    <>
      <PageMeta title="Пользователи" description="Поиск людей по почте или имени, их карточки и блокировка." />
      <UsersScreen query={query} />
    </>
  );
}
