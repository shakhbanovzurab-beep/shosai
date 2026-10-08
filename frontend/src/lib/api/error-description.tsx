import type { ReactNode } from "react";

import { Copy } from "lucide-react";
import { toast } from "sonner";
import { useTranslations } from "use-intl";

import { copyText } from "@/lib/copy-text";
import { errorMessage } from "@/lib/errors";

import { ApiError } from "./errors";

// Вторая строка тоста по ADR 0008: id запроса для поддержки, приглушённо и моноширинно, копируется по клику.
function RequestIdLine({ message, requestId }: Readonly<{ message: string; requestId: string }>) {
  const t = useTranslations("common");
  const copy = () =>
    copyText(requestId).then(
      () => toast.success(t("errors.requestIdCopied")),
      () => undefined,
    );
  return (
    <span className="flex flex-col gap-1">
      <span>{message}</span>
      <button
        type="button"
        onClick={() => void copy()}
        aria-label={t("errors.copyRequestId")}
        className="inline-flex items-center gap-1 self-start font-mono text-muted-foreground text-xs hover:text-foreground"
      >
        {t("errors.requestId", { id: requestId })}
        <Copy aria-hidden="true" className="size-3" />
      </button>
    </span>
  );
}

/**
 * Описание тоста об ошибке: текст ошибки, а для сбоя сервера или кода без слов в интерфейсе — ещё и id запроса,
 * чтобы пользователь мог передать его поддержке (ADR 0008, §16.2).
 */
export function apiErrorDescription(error: unknown): ReactNode {
  if (error instanceof ApiError && error.showsRequestId && error.requestId !== null)
    return <RequestIdLine message={error.message} requestId={error.requestId} />;
  return errorMessage(error);
}
