import { PageMeta } from "@/app/root/page-meta";
import { ErrorsScreen } from "@/features/admin-errors/ui/errors-screen";

export function Component() {
  return (
    <>
      <PageMeta
        title="Ошибки"
        description="Ошибки платформы Leo и десктоп-клиентов для macOS и Windows, сгруппированные по причине."
      />
      <ErrorsScreen />
    </>
  );
}
