import { PageMeta } from "@/app/root/page-meta";
import { AppsScreen } from "@/features/admin-apps/ui/apps-screen";

export function Component() {
  return (
    <>
      <PageMeta
        title="Приложения"
        description="Сборки Leo для macOS и Windows: загрузка, публикация и поэтапная раскатка."
      />
      <AppsScreen />
    </>
  );
}
