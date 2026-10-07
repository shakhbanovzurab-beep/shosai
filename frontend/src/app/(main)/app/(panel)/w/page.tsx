import { cookies } from "next/headers";
import { redirect } from "next/navigation";

import type { Metadata } from "next";
import { getTranslations } from "next-intl/server";

import { LAST_WORKSPACE_COOKIE, NEW_WORKSPACE_PATH, workspacePath } from "@/features/workspace";
import { listMyWorkspaces } from "@/features/workspace/server";

export const dynamic = "force-dynamic";

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("workspace");
  return { title: t("meta.workspaces"), robots: { index: false } };
}

/** /app/w: the workspace opened last (or the first), or the "new workspace" page when there is none. */
export default async function Page() {
  const [workspaces, jar] = await Promise.all([listMyWorkspaces(), cookies()]);
  const last = decodeURIComponent(jar.get(LAST_WORKSPACE_COOKIE)?.value ?? "");
  const target = workspaces.find((w) => w.slug === last) ?? workspaces[0];
  redirect(target ? workspacePath(target.slug) : NEW_WORKSPACE_PATH);
}
