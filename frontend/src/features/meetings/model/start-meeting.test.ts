import { describe, expect, it } from "vitest";

import { roomPathOf } from "./start-meeting";

describe("roomPathOf", () => {
  it("opens the invitation's room inside the cabinet", () => {
    expect(roomPathOf("https://shosai.tech/meet/AbCdEf123456")).toBe("/app/meet/AbCdEf123456");
  });
});
