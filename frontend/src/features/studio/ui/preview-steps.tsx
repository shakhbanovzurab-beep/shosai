import { useFormatter } from "use-intl";

type StepProps = { number: number; title: string; hint: string; children?: React.ReactNode };

/** Номер, название и откуда берётся часть; номер для глаз, порядок читателю даёт сам список. */
function StepHeading({ number, title, hint }: Omit<StepProps, "children">) {
  const format = useFormatter();
  return (
    <div className="flex items-start gap-3">
      <span
        aria-hidden="true"
        className="flex size-5 shrink-0 items-center justify-center rounded-full bg-background font-medium text-muted-foreground text-xs tabular-nums ring-1 ring-border"
      >
        {format.number(number)}
      </span>
      <div className="flex min-w-0 flex-col gap-0.5">
        <span className="font-medium text-sm leading-5">{title}</span>
        <span className="text-muted-foreground text-xs">{hint}</span>
      </div>
    </div>
  );
}

/** Часть, которую добавляет Shosai: человек видит только её место в порядке. */
export function PlacedStep(props: StepProps) {
  return (
    <li className="rounded-lg bg-muted/40 p-3">
      <StepHeading {...props} />
    </li>
  );
}

/** Часть человека: его текст в том виде, в каком он уйдёт модели. */
export function OwnStep({ children, ...heading }: StepProps) {
  return (
    <li className="rounded-lg border-primary border-s-2 bg-muted/40 p-3">
      <StepHeading {...heading} />
      <div className="mt-2 ps-8">{children}</div>
    </li>
  );
}
