import type { ReactNode } from "react";

import { useTranslations } from "use-intl";

import { LEGAL_PAGES } from "../domain/legal-pages";

function LegalLink({ href, children }: { href: string; children: ReactNode }) {
  return (
    <a href={href} target="_blank" rel="noopener" className="text-foreground underline underline-offset-4">
      {children}
    </a>
  );
}

/** Строка внизу экрана входа: продолжая, человек принимает условия использования и политику конфиденциальности. */
export function TermsNote() {
  const t = useTranslations("identity");
  return (
    <p className="text-center text-muted-foreground text-xs">
      {t.rich("signIn.terms", {
        terms: (chunks) => <LegalLink href={LEGAL_PAGES.terms}>{chunks}</LegalLink>,
        privacy: (chunks) => <LegalLink href={LEGAL_PAGES.privacy}>{chunks}</LegalLink>,
      })}
    </p>
  );
}
