import type { Metadata } from "next";

import { IssueScreen } from "@/features/admin-errors";

export const metadata: Metadata = {
  title: "Ошибка",
};

export default async function Page({ params }: PageProps<"/admin/errors/[id]">) {
  const { id } = await params;
  return <IssueScreen id={id} />;
}
