import { useTranslations } from "use-intl";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

/** What the model actually receives first, so people can see their context in place. */
export function SystemMessagePreview({ content }: { content: string }) {
  const t = useTranslations("studio");
  // The context is the user's own text; the other two stand in for text that arrives later, hence the brackets.
  const messages = [
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
          {messages.map((message, index) => (
            <li
              key={message.id}
              className={
                index === 0
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
