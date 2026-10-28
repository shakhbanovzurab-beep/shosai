import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "@/lib/api/errors";

import { BOARD_SAVE_AFTER_MS, type BoardSave, type BoardScene } from "../domain/board";
import { SAVE_RETRY_MS } from "../domain/board-protocol";
import { BoardSaver, type SaverPort } from "./board-saver";

const scene: BoardScene = { elements: [{ id: "a", version: 1 }], files: {} };
const refusal = (status: number, code: string) => new ApiError(code, status, code);

type Bench = { saver: BoardSaver; reports: BoardSave[]; versions: number[]; save: ReturnType<typeof vi.fn> };

function bench(answers: (number | Error)[]): Bench {
  const reports: BoardSave[] = [];
  const versions: number[] = [];
  const save = vi.fn(async (_scene: BoardScene, version: number) => {
    versions.push(version);
    const answer = answers.shift() ?? version + 1;
    if (answer instanceof Error) throw answer;
    return answer;
  });
  const saver: BoardSaver = new BoardSaver({
    save,
    report: (state) => reports.push(state),
    saved: vi.fn(),
    stale: async () => {
      // Свежая сцена с сервера: её версия становится известной, слитая сцена снова ждёт сохранения.
      saver.adopt(7);
      saver.schedule(scene);
    },
  } satisfies SaverPort);
  return { saver, reports, versions, save };
}

beforeEach(() => {
  vi.useFakeTimers();
  vi.stubGlobal("window", globalThis);
});

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

describe("BoardSaver", () => {
  it("saves once drawing pauses, on the version the board knows", async () => {
    const { saver, reports, versions } = bench([4]);
    saver.adopt(3);
    saver.schedule(scene);
    saver.schedule(scene);
    await vi.advanceTimersByTimeAsync(BOARD_SAVE_AFTER_MS);
    expect(versions).toEqual([3]);
    expect(reports.at(-1)).toBe("saved");
  });

  it("merges the latest after a stale save and waits for a person after a second one", async () => {
    const stale = refusal(409, "scene_stale");
    const { saver, reports, versions } = bench([stale, stale]);
    saver.schedule(scene);
    await vi.advanceTimersByTimeAsync(BOARD_SAVE_AFTER_MS * 2);
    expect(versions).toEqual([0, 7]);
    expect(reports.at(-1)).toBe("conflict");
    await saver.resume();
    await vi.advanceTimersByTimeAsync(BOARD_SAVE_AFTER_MS);
    expect(versions).toEqual([0, 7, 7]);
    expect(reports.at(-1)).toBe("saved");
  });

  it("retries a failed save, and does not retry a scene the server refuses as too large", async () => {
    const { saver, reports, versions } = bench([new Error("offline"), refusal(413, "scene_too_large")]);
    saver.schedule(scene);
    await vi.advanceTimersByTimeAsync(BOARD_SAVE_AFTER_MS);
    expect(reports.at(-1)).toBe("failed");
    await vi.advanceTimersByTimeAsync(SAVE_RETRY_MS);
    expect(reports.at(-1)).toBe("too_large");
    await vi.advanceTimersByTimeAsync(SAVE_RETRY_MS * 2);
    expect(versions).toEqual([0, 0]);
  });
});
