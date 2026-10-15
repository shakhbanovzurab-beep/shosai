import { PageMeta } from "@/app/root/page-meta";
import { UserScreen } from "@/features/admin-users/ui/user-screen";
import { useParams } from "@/lib/navigation";

export function Component() {
  const { id = "" } = useParams<{ id: string }>();
  return (
    <>
      <PageMeta title="Пользователь" />
      <UserScreen id={id} />
    </>
  );
}
