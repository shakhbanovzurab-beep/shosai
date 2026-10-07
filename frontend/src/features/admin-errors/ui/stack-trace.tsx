"use client";

import { useState } from "react";

import { cn } from "cn";
import { ChevronRight } from "lucide-react";

import { Card, CardAction, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";

import type { StackFrame } from "../domain/contract";

type Run = { inApp: boolean; frames: { frame: StackFrame; index: number }[] };

/** Consecutive frames of the same kind, so library frames can fold into one row. */
function toRuns(frames: StackFrame[]): Run[] {
  const runs: Run[] = [];
  frames.forEach((frame, index) => {
    const last = runs.at(-1);
    if (last && last.inApp === frame.in_app) last.frames.push({ frame, index });
    else runs.push({ inApp: frame.in_app, frames: [{ frame, index }] });
  });
  return runs;
}

const frameKey = (frame: StackFrame, index: number) => `${index}:${frame.file}:${frame.line}`;

const location = (frame: StackFrame) =>
  `${frame.file}${frame.line ? `:${frame.line}` : ""}${frame.column ? `:${frame.column}` : ""}`;

function FrameRow({ frame, defaultOpen }: { frame: StackFrame; defaultOpen: boolean }) {
  const hasContext = frame.context !== null && frame.context.length > 0;
  const head = (
    <>
      <ChevronRight
        aria-hidden="true"
        className={cn(
          "mt-0.5 size-3.5 shrink-0 text-muted-foreground transition-transform group-data-[state=open]/frame:rotate-90",
          !hasContext && "invisible",
        )}
      />
      <span className="flex min-w-0 flex-col gap-0.5 text-left">
        <span className={cn("break-all", frame.in_app ? "font-medium" : "text-muted-foreground")}>
          {frame.function}
        </span>
        <span className="break-all text-muted-foreground text-xs">{location(frame)}</span>
      </span>
    </>
  );

  if (!hasContext) return <div className="flex gap-2 px-3 py-2">{head}</div>;

  return (
    <Collapsible defaultOpen={defaultOpen} className="group/frame">
      <CollapsibleTrigger className="flex w-full gap-2 px-3 py-2 outline-none hover:bg-muted/50 focus-visible:ring-[3px] focus-visible:ring-ring/50">
        {head}
      </CollapsibleTrigger>
      <CollapsibleContent>
        <pre className="overflow-x-auto border-t bg-muted/40 py-2 text-xs leading-5">
          {frame.context?.map((line) => (
            <div
              key={line.line}
              className={cn("flex px-3", line.line === frame.line && "bg-destructive/10 text-foreground")}
              aria-current={line.line === frame.line ? "true" : undefined}
            >
              <span className="w-12 shrink-0 select-none pr-3 text-right text-muted-foreground">{line.line}</span>
              <code className="whitespace-pre">{line.code || " "}</code>
            </div>
          ))}
        </pre>
      </CollapsibleContent>
    </Collapsible>
  );
}

function SystemRun({ run }: { run: Run }) {
  const count = run.frames.length;
  return (
    <Collapsible className="group/run">
      <CollapsibleTrigger className="flex w-full items-center gap-2 px-3 py-1.5 text-muted-foreground text-xs outline-none hover:bg-muted/50 focus-visible:ring-[3px] focus-visible:ring-ring/50">
        <ChevronRight
          aria-hidden="true"
          className="size-3.5 transition-transform group-data-[state=open]/run:rotate-90"
        />
        {count === 1 ? "1 кадр библиотеки" : `Кадров библиотек: ${count}`}
      </CollapsibleTrigger>
      <CollapsibleContent className="divide-y border-t border-dashed">
        {run.frames.map(({ frame, index }) => (
          <FrameRow key={frameKey(frame, index)} frame={frame} defaultOpen={false} />
        ))}
      </CollapsibleContent>
    </Collapsible>
  );
}

export function StackTrace({
  exceptionType,
  message,
  frames,
}: {
  exceptionType: string;
  message: string;
  frames: StackFrame[];
}) {
  const [showAll, setShowAll] = useState(false);
  const firstInApp = frames.findIndex((frame) => frame.in_app);
  const runs = toRuns(frames);

  return (
    <Card>
      <CardHeader>
        <CardTitle>Стек вызовов</CardTitle>
        <CardDescription>Последнее событие, сверху — место, где возникла ошибка</CardDescription>
        <CardAction>
          <div className="flex items-center gap-2">
            <Switch id="stack-all-frames" size="sm" checked={showAll} onCheckedChange={setShowAll} />
            <Label htmlFor="stack-all-frames" className="font-normal text-muted-foreground">
              Все кадры
            </Label>
          </div>
        </CardAction>
      </CardHeader>
      <CardContent className="flex flex-col gap-3">
        <div className="rounded-lg border bg-muted/40 px-3 py-2 font-mono text-sm">
          <span className="font-semibold">{exceptionType}</span>: <span className="break-words">{message}</span>
        </div>
        {frames.length === 0 ? (
          <p className="text-muted-foreground text-sm">Клиент не прислал стек вызовов.</p>
        ) : (
          <ol className="divide-y overflow-hidden rounded-lg border font-mono text-sm" aria-label="Кадры стека">
            {showAll
              ? frames.map((frame, index) => (
                  <li key={frameKey(frame, index)}>
                    <FrameRow frame={frame} defaultOpen={index === firstInApp} />
                  </li>
                ))
              : runs.map((run) =>
                  run.inApp ? (
                    run.frames.map(({ frame, index }) => (
                      <li key={frameKey(frame, index)}>
                        <FrameRow frame={frame} defaultOpen={index === firstInApp} />
                      </li>
                    ))
                  ) : (
                    <li key={`run-${run.frames[0]?.index}`}>
                      <SystemRun run={run} />
                    </li>
                  ),
                )}
          </ol>
        )}
        <p className="text-muted-foreground text-xs">
          Код приложения выделен; кадры библиотек и системы свёрнуты, пока не включён режим «Все кадры».
        </p>
      </CardContent>
    </Card>
  );
}
