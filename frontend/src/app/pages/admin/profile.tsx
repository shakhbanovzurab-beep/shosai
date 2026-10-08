import { PageMeta } from "@/app/root/page-meta";
import { ProfileScreen } from "@/features/admin-profile/ui/profile-screen";

export function Component() {
  return (
    <>
      <PageMeta
        title="Профиль"
        description="Профиль сотрудника: личные данные, сведения о работе, отпуска, документы и линия подчинения."
      />
      <ProfileScreen />
    </>
  );
}
