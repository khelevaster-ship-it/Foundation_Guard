import { test } from "node:test";
import assert from "node:assert/strict";
import { makeWorld, step } from "../sim/world.js";

test("tide_rises", () => {
  let w = makeWorld(1);
  for (let i = 0; i < 50; i++) w = step(w);
  assert.ok(w.tide > 40);
});

test("same_world_every_time", () => {
  let a = makeWorld(7), b = makeWorld(7);
  for (let i = 0; i < 500; i++) { a = step(a); b = step(b); }
  assert.deepEqual(a, b);
});
