import { PageMeta } from "@/app/root/page-meta";
import { IssueScreen } from "@/features/admin-errors/ui/issue-screen";
import { useParams } from "@/lib/navigation";

export function Component() {
  const { id = "" } = useParams<{ id: string }>();
  return (
    <>
      <PageMeta title="Ошибка" />
      <IssueScreen id={id} />
    </>
  );
}
