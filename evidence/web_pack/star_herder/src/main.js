import { makeHerd, step } from "./sim/herd.js";
const ctx = document.getElementById("c").getContext("2d");
let herd = makeHerd(42, 30);
let frames = 0;
function frame() {
  herd = step(herd);
  ctx.fillStyle = "#000"; ctx.fillRect(0, 0, 320, 200);
  ctx.fillStyle = "#ff0";
  for (const s of herd) ctx.fillRect(s.x, s.y, 2, 2);
  frames++;
  window.__frames = frames;
  requestAnimationFrame(frame);
}
frame();
