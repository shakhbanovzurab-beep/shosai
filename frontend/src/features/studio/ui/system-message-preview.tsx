import { useTranslations } from "use-intl";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

/** Что получает модель и в каком порядке, чтобы человек видел свой контекст на его месте. */
export function SystemMessagePreview({ content }: { content: string }) {
  const t = useTranslations("studio");
  // Контекст — текст самого человека; остальные части приходят позже, поэтому в угловых скобках.
  const messages = [
    { id: "platform", role: t("preview.system"), content: `<${t("preview.platform")}>` },
    { id: "context", role: t("preview.system"), content: content || t("preview.empty") },
    { id: "prompt", role: t("preview.system"), content: `<${t("preview.rolePrompt")}>` },
    { id: "question", role: t("preview.user"), content: `<${t("preview.question")}>` },
  ];

  return (
    <Card className="h-fit shadow-xs">
      <CardHeader>
        <CardTitle>{t("preview.title")}</CardTitle>
        <CardDescription>{t("preview.description")}</CardDescription>
      </CardHeader>
      <CardContent>
        <ol className="flex flex-col gap-2">
          {messages.map((message) => (
            <li
              key={message.id}
              className={
                message.id === "context"
                  ? "rounded-lg border border-primary/40 bg-primary/5 p-3"
                  : "rounded-lg border bg-muted/40 p-3"
              }
            >
              <span className="font-medium font-mono text-muted-foreground text-xs uppercase">{message.role}</span>
              <p dir="auto" className="mt-1 line-clamp-6 whitespace-pre-wrap break-words font-mono text-xs leading-5">
                {message.content}
              </p>
            </li>
          ))}
        </ol>
      </CardContent>
    </Card>
  );
}
