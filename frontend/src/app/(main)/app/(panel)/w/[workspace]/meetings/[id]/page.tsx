import type { Metadata } from "next";
import { getTranslations } from "next-intl/server";

import { TeamMeetingScreen } from "@/features/workspace";

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("workspace");
  return { title: t("meta.meeting"), robots: { index: false } };
}

interface PageProps {
  params: Promise<{ id: string }>;
}

export default async function Page({ params }: PageProps) {
  const { id } = await params;
  return <TeamMeetingScreen meetingId={decodeURIComponent(id)} />;
}
