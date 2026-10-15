import { PageMeta } from "@/app/root/page-meta";
import { AdminSignInScreen } from "@/features/admin-sign-in/ui/admin-sign-in-screen";

export function Component() {
  return (
    <>
      <PageMeta title="Вход в админку" />
      <AdminSignInScreen />
    </>
  );
}
