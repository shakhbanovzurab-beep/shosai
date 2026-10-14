import { useLoaderData } from "react-router";
import { useTranslations } from "use-intl";

import { PageMeta } from "@/app/root/page-meta";
import { safeNext } from "@/features/identity/domain/next-path";
import { LoginPanel } from "@/features/identity/ui/login-panel";
import { SocialConsentPanel } from "@/features/identity/ui/social-consent-panel";
import { useSearchParams } from "@/lib/navigation";

import type { LoginEntry } from "./login-loader";

export function Component() {
  const t = useTranslations("identity");
  const entry = useLoaderData<LoginEntry>();
  const next = safeNext(useSearchParams().get("next"));
  if (entry.kind === "consent") {
    return (
      <>
        <PageMeta title={t("social.consentMetaTitle")} />
        <SocialConsentPanel ticket={entry.ticket} provider={entry.provider} />
      </>
    );
  }
  const socialRefusal =
    entry.kind === "refused" ? { problem: entry.problem, requestId: null, retryAfterSeconds: null } : null;
  return (
    <>
      <PageMeta title={t("signIn.metaTitle")} />
      <LoginPanel next={next} socialRefusal={socialRefusal} />
    </>
  );
}
