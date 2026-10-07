import { Suspense } from "react";

import type { Metadata } from "next";
import { getTranslations } from "next-intl/server";

import { HubScreen } from "@/features/hub";

interface PageProps {
  params: Promise<{ hubId: string }>;
}

export async function generateMetadata({ params }: PageProps): Promise<Metadata> {
  const [{ hubId }, t] = await Promise.all([params, getTranslations("hub")]);
  return { title: t("list.title"), alternates: { canonical: `/app/hub/${hubId}` } };
}

export default async function Page({ params }: PageProps) {
  const { hubId } = await params;
  // The open topic lives in `?open=`, read on the client so opening one needs no server round trip.
  return (
    <Suspense>
      <HubScreen hubId={hubId} />
    </Suspense>
  );
}
