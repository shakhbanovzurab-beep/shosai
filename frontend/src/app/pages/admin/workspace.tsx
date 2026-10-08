import { PageMeta } from "@/app/root/page-meta";
import { WorkspaceScreen } from "@/features/admin-workspaces/ui/workspace-screen";
import { useParams } from "@/lib/navigation";

export function Component() {
  const { id = "" } = useParams<{ id: string }>();
  return (
    <>
      <PageMeta title="Пространство" />
      <WorkspaceScreen id={id} />
    </>
  );
}
