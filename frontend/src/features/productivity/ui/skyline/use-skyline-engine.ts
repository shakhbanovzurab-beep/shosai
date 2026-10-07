"use client";

import * as React from "react";

import type { ContributionDay } from "../../domain/skyline/contributions";
import type { SkylineModel } from "../../domain/skyline/stats";
import { type EngineHandle, mountEngine } from "./engine/mount";
import type { EngineConfig } from "./engine/state";

export type SkylineView = "2d" | "3d";

export type SkylineRefs = {
  rootRef: React.RefObject<HTMLDivElement | null>;
  stageRef: React.RefObject<HTMLDivElement | null>;
  canvasRef: React.RefObject<HTMLCanvasElement | null>;
  tipRef: React.RefObject<HTMLDivElement | null>;
};

type Options = {
  refs: SkylineRefs;
  model: SkylineModel;
  view: SkylineView;
  duration: number;
  heightScale: number;
  orbit: boolean;
  locale: string;
  onCellClick?: (day: ContributionDay) => void;
  describe: (i: number) => string;
};

/** Mounts the canvas engine once and feeds it the latest props through a ref. */
export function useSkylineEngine({
  refs,
  model,
  view,
  duration,
  heightScale,
  orbit,
  locale,
  onCellClick,
  describe,
}: Options) {
  const { rootRef, stageRef, canvasRef, tipRef } = refs;
  const [width, setWidth] = React.useState(0);
  const [active, setActive] = React.useState(-1);
  const [legendLevel, setLegendLevel] = React.useState(-1);
  const [announce, setAnnounce] = React.useState("");
  const [swatches, setSwatches] = React.useState<string[]>([]);

  const engine = React.useRef<EngineHandle | null>(null);

  const config: EngineConfig = {
    model,
    duration,
    heightScale,
    orbit,
    legendLevel,
    locale,
    target: view === "3d" ? 1 : 0,
    onCellClick,
    setActive,
    setWidth,
    setSwatches,
    setAnnounce,
    describe,
  };
  const cfg = React.useRef(config);
  React.useLayoutEffect(() => {
    cfg.current = config;
  });

  React.useEffect(() => {
    const root = rootRef.current;
    const stage = stageRef.current;
    const canvas = canvasRef.current;
    const tip = tipRef.current;
    const ctx = canvas?.getContext("2d");
    if (!root || !stage || !canvas || !tip || !ctx) return;
    const handle = mountEngine({ root, stage, canvas, tip, ctx }, cfg);
    engine.current = handle;
    return () => {
      handle.destroy();
      engine.current = null;
    };
  }, [rootRef, stageRef, canvasRef, tipRef]);

  // The engine reads view and legend level through cfg; these effects only tell it to look again.
  // biome-ignore lint/correctness/useExhaustiveDependencies: dependencies are the trigger
  React.useEffect(() => {
    engine.current?.kick();
  }, [view, legendLevel]);

  // biome-ignore lint/correctness/useExhaustiveDependencies: dependencies are the trigger
  React.useEffect(() => {
    engine.current?.load();
  }, [model, heightScale, locale]);

  // The tooltip's width is needed to keep it inside the card; measure it when its text changes.
  // biome-ignore lint/correctness/useExhaustiveDependencies: re-measure when the data changes
  React.useLayoutEffect(() => {
    const tip = tipRef.current;
    if (tip && active >= 0) engine.current?.tipWidth(tip.offsetWidth);
  }, [active, model, tipRef]);

  return {
    width,
    active,
    announce,
    swatches,
    legendLevel,
    setLegendLevel,
  };
}
