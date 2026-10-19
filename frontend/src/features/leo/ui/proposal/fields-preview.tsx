import { CardContent } from "@/components/ui/card";

/** Что именно сделает действие: поля (кому, тема, когда) и, если есть, текст — как его посчитал сервер. */
export function FieldsPreview({ fields, body }: { fields: { label: string; value: string }[]; body: string | null }) {
  return (
    <CardContent className="flex flex-col gap-3">
      <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1.5 text-sm">
        {fields.map((field) => (
          <div key={field.label} className="contents">
            <dt className="text-muted-foreground">{field.label}</dt>
            <dd className="min-w-0 truncate" dir="auto">
              {field.value}
            </dd>
          </div>
        ))}
      </dl>
      {body ? (
        <p
          dir="auto"
          className="max-h-48 overflow-y-auto whitespace-pre-wrap rounded-lg border bg-muted/30 px-3 py-2 text-sm leading-relaxed"
        >
          {body}
        </p>
      ) : null}
    </CardContent>
  );
}
