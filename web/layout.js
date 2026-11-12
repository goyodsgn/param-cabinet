// Parametric base cabinet layout, computed in the browser.
// Mirrors compute_layout() in cabinet_reference.py (the Python model is the source of truth;
// tests/test_web_layout.py checks that both give the same layout).

export const P0 = {
  t: 18, back_t: 10, divider_t: 18, door_t: 22, gap: 2, door_max_w: 600,
  cup_d: 35, cup_depth: 12, cup_x: 22.5, cup_end: 100,
  shelf_t: 30, min_gap: 320, shelf_clear: 1,
  leg_h: 100, leg_d: 40, leg_inset: 30, leg_max: 600,
  top_mode: "inset", back_mode: "onset", door_layout: null,
};

export function hingeCount(h) {
  return h <= 900 ? 2 : h <= 1600 ? 3 : 4;
}

export function minDoors(W, max = P0.door_max_w) {
  return Math.max(1, Math.ceil(W / max));
}

function hingeSides(n) {
  const s = Array.from({ length: n }, (_, i) => (i % 2 === 0 ? "left" : "right"));
  if (n % 2 === 1 && n > 1) s[n - 1] = "right";
  return s;
}

function doorSides(p, groups) {
  const n = groups.reduce((a, b) => a + b, 0);
  if (groups.every((g) => g === 1)) return hingeSides(n);
  const cell = p.W / n;
  const out = [];
  let i = 0;
  for (const g of groups) {
    if (g === 2) out.push("left", "right");
    else out.push((i + 0.5) * cell <= p.W / 2 + 1e-9 ? "left" : "right");
    i += g;
  }
  return out;
}

function legAxis(p, length) {
  const lo = p.leg_inset + p.leg_d / 2;
  const hi = length - lo;
  const span = hi - lo;
  const n = span <= 0 ? 1 : Math.ceil(span / p.leg_max) + 1;
  if (n === 1) return [length / 2];
  return Array.from({ length: n }, (_, i) => lo + (i * (hi - lo)) / (n - 1));
}

/** Door arrangement choices for n doors: all single, pairs, or one single door on the left/right. */
export function layoutOptions(n) {
  const opts = [{ key: "single", groups: Array(n).fill(1) }];
  if (n >= 2 && n % 2 === 0) opts.push({ key: "pair", groups: Array(n / 2).fill(2) });
  if (n >= 3 && n % 2 === 1) {
    const pairs = Array((n - 1) / 2).fill(2);
    opts.push({ key: "left", groups: [1, ...pairs] });
    opts.push({ key: "right", groups: [...pairs, 1] });
  }
  return opts;
}

export function computeLayout(o) {
  const p = { ...P0, ...o };
  const g = p.gap;
  const Dc = p.D - p.door_t - p.gap;
  const Hc = p.H - p.leg_h;
  const z0 = p.leg_h;
  const innerBack = Dc - p.back_t;
  const innerBottom = z0 + p.t;
  const innerTop = z0 + Hc - (p.top_mode === "none" ? 0 : p.t);
  const clearH = innerTop - innerBottom;

  const groups = p.door_layout && p.door_layout.length ? p.door_layout.slice() : Array(minDoors(p.W, p.door_max_w)).fill(1);
  const n = groups.reduce((a, b) => a + b, 0);
  const cell = p.W / n;
  const doorW = cell - 2 * g;
  const doorH = Hc - 2 * g;
  const nh = hingeCount(doorH);
  const sides = doorSides(p, groups);
  const doors = sides.map((side, i) => {
    const x = i * cell + g;
    const z = z0 + g;
    let hz;
    if (nh === 1) hz = [z + doorH / 2];
    else {
      const lo = z + p.cup_end, hi = z + doorH - p.cup_end;
      hz = Array.from({ length: nh }, (_, k) => lo + (k * (hi - lo)) / (nh - 1));
    }
    return { x, z, w: doorW, h: doorH, side, hingeZ: hz };
  });

  const joints = [];
  let acc = 0;
  for (const c of groups.slice(0, -1)) { acc += c; joints.push(acc); }
  const dividers = joints.map((j) => [j * cell - p.divider_t / 2, j * cell + p.divider_t / 2]);
  const edges = [p.t, ...dividers.flat(), p.W - p.t];
  const bays = [];
  for (let i = 0; i < edges.length; i += 2) bays.push([edges[i], edges[i + 1]]);

  const k = Math.max(0, Math.floor((clearH - p.min_gap) / (p.min_gap + p.shelf_t)));
  const space = (clearH - k * p.shelf_t) / (k + 1);
  const shelfZ = Array.from({ length: k }, (_, i) => innerBottom + space * (i + 1) + p.shelf_t * i);

  const xs = legAxis(p, p.W), ys = legAxis(p, Dc);
  const legs = [];
  for (const x of xs) for (const y of ys) legs.push([x, y]);

  return { p, Dc, Hc, z0, innerBack, innerBottom, innerTop, clearH, groups, n, doorW, doorH, nh, doors,
    dividers, bays, nShelves: k, shelfZ, legs, legsX: xs.length, legsY: ys.length };
}
