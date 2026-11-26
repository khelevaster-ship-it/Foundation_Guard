import { describe, test, expect } from "vitest";
import { makeHerd, step } from "./herd.js";

describe("herd", () => {
  test("same_herd_every_time", () => {
    expect(makeHerd(5, 10)).toEqual(makeHerd(5, 10));
  });
  test("stars_drift_right", () => {
    const h = makeHerd(5, 3);
    expect(step(h)[0].x).toBe((h[0].x + 1) % 320);
  });
});
