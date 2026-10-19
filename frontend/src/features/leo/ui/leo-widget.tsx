"use client";

import * as React from "react";

import { AnimatePresence, domMax, LazyMotion, MotionConfig, m, type Transition } from "framer-motion";
import { ThinkingOrb } from "thinking-orbs";
import { useTranslations } from "use-intl";

import { useDirection } from "@/components/ui/direction";
import { Kbd } from "@/components/ui/kbd";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { usePathname } from "@/lib/navigation";

import { type LeoContext, PERSONAL_CONTEXT } from "../domain/context";
import { useLeoQuestions } from "../model/leo-questions";
import { useLeoChat } from "../model/use-leo-chat";
import { type LeoDraft, LeoPanel } from "./leo-panel";
import { leoPlace } from "./leo-place";

// One spring drives every layout change, so the window, its content and its corners move as a single piece.
const MORPH: Transition = { type: "spring", bounce: 0.14, duration: 0.55 };
const FADE: Transition = { ease: [0.23, 1, 0.32, 1], duration: 0.22 };

/**
 * Leo, floating on every page; `context` says whether it works in Personal, a workspace or a hub.
 * `notice` is shown before the first question, e.g. a topic of the hub going in circles.
 */
export function LeoWidget({
  context = PERSONAL_CONTEXT,
  notice = null,
}: {
  readonly context?: LeoContext;
  readonly notice?: React.ReactNode;
}) {
  const pathname = usePathname();
  const [open, setOpen] = React.useState(false);
  const [expanded, setExpanded] = React.useState(false);
  const launcherRef = React.useRef<HTMLButtonElement>(null);
  const chat = useLeoChat({ page: pathname, context });
  const [draft, setDraft] = React.useState<LeoDraft | null>(null);

  // Вопрос из ⌘K: свободный Leo отвечает сразу; занятый — вопрос ждёт в поле ввода, отправит его человек.
  useLeoQuestions((question) => {
    setOpen(true);
    if (chat.isBusy) setDraft({ id: crypto.randomUUID(), text: question });
    else void chat.send(question);
  });

  const close = React.useCallback(() => {
    setOpen(false);
    setDraft(null);
    // The launcher may only mount in this update (closing from full screen), so focus it on the next frame.
    requestAnimationFrame(() => launcherRef.current?.focus());
  }, []);

  React.useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key.toLowerCase() === "i" && (event.metaKey || event.ctrlKey) && !event.altKey && !event.shiftKey) {
        event.preventDefault();
        setOpen((value) => !value);
      }
    };
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, []);

  const isFullScreen = open && expanded;

  const t = useTranslations("leo");
  // The launcher sits at the end of the reading line, so its tooltip opens towards the page.
  const rtl = useDirection() === "rtl";

  return (
    <div className="fixed end-4 bottom-4 z-50 flex flex-col items-end gap-3 sm:end-6 sm:bottom-6">
      <LazyMotion features={domMax} strict>
        <MotionConfig reducedMotion="user" transition={MORPH}>
          <AnimatePresence>
            {isFullScreen && (
              <m.div
                key="leo-backdrop"
                aria-hidden="true"
                className="fixed inset-0 z-40 bg-background/60 backdrop-blur-md"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                transition={FADE}
              />
            )}
          </AnimatePresence>

          <AnimatePresence>
            {open && (
              <m.div
                key="leo-panel"
                layout
                className={expanded ? "fixed inset-0 z-50" : "relative z-50 origin-bottom-right rtl:origin-bottom-left"}
                initial={{ opacity: 0, scale: 0.92, y: 12, filter: "blur(4px)" }}
                animate={{ opacity: 1, scale: 1, y: 0, filter: "blur(0px)" }}
                exit={{ opacity: 0, scale: 0.92, y: 12, filter: "blur(4px)" }}
                transition={{ default: FADE, layout: MORPH }}
              >
                <LeoPanel
                  chat={chat}
                  draft={draft}
                  place={leoPlace(t, context, notice)}
                  pathname={pathname}
                  expanded={expanded}
                  onToggleExpanded={() => setExpanded((value) => !value)}
                  onCollapse={() => setExpanded(false)}
                  onClose={close}
                />
              </m.div>
            )}
          </AnimatePresence>

          <AnimatePresence initial={false}>
            {isFullScreen ? null : (
              <m.div
                key="leo-launcher"
                initial={{ opacity: 0, scale: 0.6 }}
                animate={{ opacity: 1, scale: 1 }}
                exit={{ opacity: 0, scale: 0.6 }}
                transition={FADE}
              >
                <Tooltip>
                  <TooltipTrigger asChild>
                    <button
                      ref={launcherRef}
                      type="button"
                      onClick={() => (open ? close() : setOpen(true))}
                      aria-label={t(open ? "launcher.close" : "launcher.open")}
                      aria-expanded={open}
                      aria-controls="leo-panel"
                      aria-keyshortcuts="Meta+I Control+I"
                      className="flex size-12 items-center justify-center rounded-full border bg-card/40 shadow-lg outline-none backdrop-blur-md transition-transform hover:scale-105 focus-visible:ring-3 focus-visible:ring-ring/50 active:scale-95"
                    >
                      <span className="flex [&_canvas]:size-10!" aria-hidden="true">
                        <ThinkingOrb state="solving" size={64} />
                      </span>
                    </button>
                  </TooltipTrigger>
                  <TooltipContent side={rtl ? "right" : "left"}>
                    {t(open ? "launcher.tooltipClose" : "launcher.tooltipOpen")} <Kbd>⌘I</Kbd>
                  </TooltipContent>
                </Tooltip>
              </m.div>
            )}
          </AnimatePresence>
        </MotionConfig>
      </LazyMotion>
    </div>
  );
}
