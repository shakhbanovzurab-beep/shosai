"use client";

import { useState } from "react";

import { Slider } from "@/components/ui/slider";

import type { AppRelease } from "../domain/contract";
import { setRollout } from "../model/apps-store";

/**
 * Staged rollout of a published stable build: the share of installs the updater offers it to.
 * Saved when the thumb is released; keyed by the saved value, so a failed save snaps back.
 */
export function RolloutControl({ release }: { release: AppRelease }) {
  const [value, setValue] = useState(release.rollout_percent);
  const [saving, setSaving] = useState(false);

  const commit = (next: number) => {
    if (next === release.rollout_percent) return;
    setSaving(true);
    void setRollout(release, next)
      .then((ok) => {
        if (!ok) setValue(release.rollout_percent);
      })
      .finally(() => setSaving(false));
  };

  return (
    <fieldset className="flex w-36 items-center gap-3">
      <legend className="sr-only">Поэтапная раскатка версии {release.version}</legend>
      <Slider
        value={[value]}
        min={0}
        max={100}
        step={5}
        disabled={saving}
        onValueChange={([next]) => setValue(next ?? value)}
        onValueCommit={([next]) => void commit(next ?? value)}
      />
      <output className="w-9 shrink-0 text-right text-xs tabular-nums" aria-live="polite">
        {value}%
      </output>
    </fieldset>
  );
}
