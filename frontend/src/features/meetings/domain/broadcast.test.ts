import { describe, expect, it } from "vitest";

import { mayManageCohosts, mayModerate, onAir, SPEAKERS_MAX, type StageMember, stageIsFull } from "./broadcast";

const member = (principal: string, role: StageMember["role"], on = true): StageMember => ({
  principal,
  identity: `${principal}__1`,
  name: principal,
  role,
  onAir: on,
});

describe("broadcast rules", () => {
  it("lets the host and co-hosts moderate, and only the host name co-hosts", () => {
    expect([mayModerate("host"), mayModerate("cohost"), mayModerate("speaker"), mayModerate(null)]).toEqual([
      true,
      true,
      false,
      false,
    ]);
    expect([mayManageCohosts("host"), mayManageCohosts("cohost")]).toEqual([true, false]);
  });

  it("counts ten speakers besides the host as a full stage", () => {
    const speakers = Array.from({ length: SPEAKERS_MAX }, (_, index) => member(`s${index}`, "speaker"));
    expect(stageIsFull([member("h", "host"), ...speakers.slice(1)])).toBe(false);
    expect(stageIsFull([member("h", "host"), ...speakers])).toBe(true);
  });

  it("shows the audience the stage on air, the host first", () => {
    const stage = [member("s", "speaker"), member("c", "cohost", false), member("h", "host")];
    expect(onAir(stage).map((item) => item.principal)).toEqual(["h", "s"]);
  });
});
