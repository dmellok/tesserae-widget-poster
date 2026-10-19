/* Poster: a framed print, drawn here from what the server sent.
   Drawn styles are generated from d.seed; museum and painted styles lay the
   words around d.pic. Everything is laid out in the cell's own pixels so a
   poster keeps its proportions upright, lying down and on a small cell. */

const esc = (s) => String(s == null ? '' : s).replace(/[&<>"]/g,
  (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));

function rng(seed) {
  let a = (Number(seed) >>> 0) || 1;
  return () => {
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}
const pick = (r, list) => list[Math.floor(r() * list.length) % list.length];
const f1 = (n) => Math.round(n * 10) / 10;

/* The largest size, up to maxH, at which `text` fits maxW, for a face whose
   average glyph is `ratio` of the size wide. */
function fit(text, ratio, maxW, maxH) {
  const n = Math.max(1, String(text || '').length);
  return Math.max(6, Math.min(maxH, maxW / (n * ratio)));
}

/* A box positioned in poster pixels. */
const box = (x, y, w, h, extra = '') =>
  `position:absolute;left:${f1(x)}px;top:${f1(y)}px;width:${f1(w)}px;height:${f1(h)}px;${extra}`;

function svg(W, H, inner, extra = '') {
  return `<svg class="pp-svg" width="${W}" height="${H}" viewBox="0 0 ${W} ${H}" ${extra}>${inner}</svg>`;
}

function daysLeft(d) {
  const y = Number(d.year) || 2026;
  const leap = (y % 4 === 0 && y % 100 !== 0) || y % 400 === 0;
  return (leap ? 366 : 365) - (Number(d.doy) || 0);
}

/* ------------------------------------------------------------------ */
/* Drawn: Ausstellung (Bauhaus patterns)                               */
/* ------------------------------------------------------------------ */

const BAUHAUS = [
  ['#e09a33', '#d55a3c', '#5b8db8', '#2a2723'],
  ['#d9a441', '#b5442e', '#2f5d7c', '#1d1b19'],
  ['#e6b33e', '#c8553d', '#4f7cac', '#2b2a28'],
];

const FAMILIES = {
  dots(r, P) {
    let s = '';
    const shift = Math.floor(r() * 4);
    for (let y = 0; y < 8; y++) for (let x = 0; x < 6; x++) {
      s += `<circle cx="${60 + x * 96}" cy="${50 + y * 80}" r="34" fill="${P[(y + x * 3 + shift + (r() < 0.25 ? 1 : 0)) % 4]}"/>`;
    }
    return s;
  },
  rings(r, P) {
    const o = Math.floor(r() * 3);
    const c = [P[o % 3], P[(o + 1) % 3], P[(o + 2) % 3]];
    let s = `<circle cx="300" cy="270" r="240" fill="${c[0]}"/><circle cx="300" cy="270" r="170" fill="${c[1]}"/><circle cx="300" cy="270" r="105" fill="${c[2]}"/>`;
    for (let i = 0; i < 4; i++) s += `<circle cx="${120 + i * 120}" cy="610" r="28" fill="${P[i]}"/>`;
    return s;
  },
  waves(r, P) {
    const amp = 40 + r() * 50, ph = r() * 6, cx = 200 + r() * 200;
    let s = '';
    for (let i = 0; i < 22; i++) {
      let p = '';
      for (let x = 0; x <= 600; x += 8) {
        const y = 20 + i * 29 + amp * Math.sin(x / 90 + ph) * Math.exp(-((x - cx) ** 2) / 40000) * Math.sin(i / 7 + 0.3);
        p += `${x ? 'L' : 'M'}${x},${f1(y)}`;
      }
      s += `<path d="${p}" fill="none" stroke="${P[3]}" stroke-width="12"/>`;
    }
    return s;
  },
  quarters(r, P) {
    const S = 100;
    let s = '';
    for (let y = 0; y < 6; y++) for (let x = 0; x < 6; x++) {
      const x0 = x * S, y0 = y * S + 30, k = Math.floor(r() * 4);
      const cx = x0 + (k & 1 ? S : 0), cy = y0 + (k & 2 ? S : 0);
      const ax = x0 + (k & 1 ? 0 : S), by = y0 + (k & 2 ? 0 : S);
      const sweep = k === 1 || k === 2 ? 0 : 1;
      s += `<path d="M${cx},${cy} L${ax},${cy} A${S},${S} 0 0 ${sweep} ${cx},${by} Z" fill="${P[3]}"/>`;
    }
    return s;
  },
  stripes(r) {
    const G = pick(r, [
      ['#1f6b4f', '#55a35d', '#183b6e', '#a9cf62'],
      ['#7a2e2a', '#d0703c', '#e8b04a', '#2b2a28'],
      ['#183b6e', '#5b8db8', '#a7c4dc', '#2a2723'],
    ]);
    let s = '', x = 0;
    while (x < 600) {
      const w = 4 + r() * 16;
      s += `<rect x="${f1(x)}" y="0" width="${f1(w)}" height="660" fill="${pick(r, G)}"/>`;
      x += w + 2 + r() * 5;
    }
    return s;
  },
  squares(r) {
    const C = pick(r, [
      ['#b6574a', '#d98a5c', '#e9c1b8', '#8fb5c2', '#f7f2ea'],
      ['#3d5a80', '#6f8fb0', '#98c1d9', '#e0c59a', '#f7f2ea'],
      ['#5a3e5d', '#a65e6e', '#e39b7b', '#f2d0a9', '#fbf3e6'],
    ]);
    let s = '';
    const dx = (r() - 0.5) * 30, dy = (r() - 0.5) * 30;
    for (let i = 0; i < 5; i++) {
      const m = i * 55;
      s += `<rect x="${f1(m + dx * i / 4)}" y="${f1(m + 20 + dy * i / 4)}" width="${600 - 2 * m}" height="${620 - 2 * m}" fill="${C[i]}" stroke="#5a4a44" stroke-width="1.5"/>`;
    }
    return s;
  },
};

function ausstellung(d, o) {
  const { W, H, land, r } = o;
  const P = pick(r, BAUHAUS);
  const fam = pick(r, Object.keys(FAMILIES));
  const art = FAMILIES[fam](r, P);
  let ax, ay, aw, ah, tx, ty, tw;
  if (land) {
    ah = H * 0.8; aw = Math.min(W * 0.52, ah * 0.91); ax = W * 0.07; ay = H * 0.1;
    tx = ax + aw + W * 0.06; tw = W - tx - W * 0.07; ty = H * 0.72;
  } else {
    ax = W * 0.12; ay = H * 0.08; aw = W * 0.76; ah = H * 0.66;
    tx = ax; tw = aw; ty = H * 0.79;
  }
  const fs = Math.min(fit(d.title, 0.62, tw * 0.62, Math.min(W, H) * 0.06), Math.min(W, H) * 0.06);
  return `
    <div class="pp-bg" style="background:#ebe5d6"></div>
    <svg class="pp-svg" style="${box(ax, ay, aw, ah)}" viewBox="0 0 600 660" preserveAspectRatio="xMidYMid meet">${art}</svg>
    <div style="${box(tx, ty, tw, 0, `border-top:${f1(Math.max(1, Math.min(W, H) * 0.004))}px solid #262320`)}"></div>
    <div style="${box(tx, ty + Math.min(W, H) * 0.025, tw * 0.7, fs * 2.4, `font:300 ${f1(fs)}px/1.05 Jost,sans-serif;letter-spacing:.05em;text-transform:uppercase;color:#262320`)}">${esc(d.title)}</div>
    <div style="${box(tx + tw * 0.6, ty + Math.min(W, H) * 0.025, tw * 0.4, fs * 1.4, `font:300 ${f1(fs)}px/1.05 Jost,sans-serif;letter-spacing:.05em;text-align:right;color:#262320`)}">${esc(d.sub)}</div>`;
}

/* ------------------------------------------------------------------ */
/* Drawn: Swiss                                                        */
/* ------------------------------------------------------------------ */

function swiss(d, o) {
  const { W, H, land, r } = o;
  const m = Math.min(W, H);
  const ink = '#141414', red = pick(r, ['#e2231a', '#e94e1b', '#0057b8']), ground = '#f1efe9';
  const title = String(d.title || '').toLowerCase();
  const tw = land ? W * 0.56 : W * 0.9;
  const fs = fit(title, 0.56, tw, (land ? H * 0.3 : H * 0.2));
  const titleTop = H - fs * 1.08 - H * 0.04;
  let R = m * (0.36 + r() * 0.08);
  const cx = land ? W * (0.62 + r() * 0.12) : W * (0.48 + r() * 0.2);
  const cy = land ? H * (0.42 + r() * 0.1) : H * (0.34 + r() * 0.08);
  if (!land) R = Math.min(R, titleTop - m * 0.05 - cy);
  const r2 = R * (0.34 + r() * 0.12);
  const ang = r() * Math.PI * 2;
  const cx2 = cx + Math.cos(ang) * R * 0.95, cy2 = cy + Math.sin(ang) * R * 0.95;
  let grid = '';
  for (let i = 1; i < 6; i++) grid += `<line x1="${f1(W * i / 6)}" y1="0" x2="${f1(W * i / 6)}" y2="${H}" stroke="${ink}" stroke-opacity=".12" stroke-width="1"/>`;
  const art = svg(W, H, `${grid}<circle cx="${f1(cx)}" cy="${f1(cy)}" r="${f1(R)}" fill="${ink}"/>
    <circle cx="${f1(cx2)}" cy="${f1(cy2)}" r="${f1(r2)}" fill="${red}" style="mix-blend-mode:multiply"/>
    <line x1="0" y1="${f1(cy + R * 0.2)}" x2="${W}" y2="${f1(cy + R * 0.2)}" stroke="${red}" stroke-width="${f1(m * 0.012)}"/>`);

  const mono = m * 0.026;
  const info = [
    esc(d.sub),
    `Week ${esc(d.date.week)}`,
    `Day ${esc(d.date.doy)}`,
    `${daysLeft(d.date)} days left in the year`,
  ].join('<br>');
  return `
    <div class="pp-bg" style="background:${ground}"></div>${art}
    <div style="${box(W * 0.05 - mono * 0.4, H * 0.05 - mono * 0.3, 0, 0, `width:auto;height:auto;padding:${f1(mono * 0.3)}px ${f1(mono * 0.4)}px;background:${ground};font:400 ${f1(mono)}px/1.35 'IBM Plex Mono',monospace;color:${ink}`)}">${info}</div>
    <div style="${box(W * 0.045, H - fs * 1.08 - H * 0.04, tw, fs * 1.1, `font:900 ${f1(fs)}px/1 'Inter Tight',sans-serif;letter-spacing:-.045em;color:${ink};white-space:nowrap`)}">${esc(title)}</div>`;
}

/* ------------------------------------------------------------------ */
/* Drawn: Constructivist                                               */
/* ------------------------------------------------------------------ */

function constructivist(d, o) {
  const { W, H, land, r } = o;
  const m = Math.min(W, H);
  const red = '#c8322b', ink = '#1b1a18', ground = pick(r, ['#ebe0c9', '#e9dcc0', '#efe6d4']);
  const a = -(18 + r() * 22);
  const diag = Math.hypot(W, H);
  const cx = W * (0.55 + r() * 0.2), cy = H * (land ? 0.42 : 0.34);
  const R = m * (0.22 + r() * 0.08);
  let bars = '';
  for (let i = 0; i < 3; i++) {
    const y = cy + R * (0.9 + i * 0.32);
    bars += `<rect x="${f1(-diag)}" y="${f1(y)}" width="${f1(diag * 3)}" height="${f1(m * (0.012 + i * 0.006))}" fill="${ink}" transform="rotate(${f1(a)} ${f1(cx)} ${f1(cy)})"/>`;
  }
  const art = svg(W, H, `
    <rect x="${f1(-diag)}" y="${f1(cy - m * 0.11)}" width="${f1(diag * 3)}" height="${f1(m * 0.22)}" fill="${red}" transform="rotate(${f1(a)} ${f1(cx)} ${f1(cy)})"/>
    <circle cx="${f1(cx)}" cy="${f1(cy)}" r="${f1(R)}" fill="${ink}"/>
    <circle cx="${f1(cx - R * 1.7)}" cy="${f1(cy + R * 1.9)}" r="${f1(R * 0.32)}" fill="${red}"/>${bars}`);
  const title = String(d.title || '').toUpperCase();
  const tw = land ? W * 0.5 : W * 0.86;
  const fs = fit(title, 0.45, tw, H * (land ? 0.26 : 0.17));
  const ty = H - H * 0.07 - fs * 1.2 - m * 0.06;
  return `
    <div class="pp-bg" style="background:${ground}"></div>${art}
    <div style="${box(W * 0.06, ty, tw + fs * 0.3, fs * 1.15, `background:${ink};transform:rotate(-4deg);transform-origin:left bottom`)}"></div>
    <div style="${box(W * 0.06 + fs * 0.15, ty + fs * 0.04, tw, fs * 1.1, `font:400 ${f1(fs)}px/1.08 Anton,Impact,sans-serif;color:#f3ead7;transform:rotate(-4deg);transform-origin:left bottom;white-space:nowrap`)}">${esc(title)}</div>
    <div style="${box(W * 0.06 - m * 0.01, H - H * 0.07 - m * 0.01, 0, 0, `width:auto;height:auto;padding:${f1(m * 0.01)}px ${f1(m * 0.012)}px;background:${ground};font:600 ${f1(m * 0.032)}px/1 Jost,sans-serif;letter-spacing:.3em;text-transform:uppercase;color:${red}`)}">${esc(d.sub)}</div>`;
}

/* ------------------------------------------------------------------ */
/* Drawn: Ridgeline                                                    */
/* ------------------------------------------------------------------ */

function ridgeline(d, o) {
  const { W, H, land, r } = o;
  const m = Math.min(W, H);
  const lines = land ? 34 : 46;
  const x0 = W * (land ? 0.3 : 0.18), x1 = W - x0;
  const top = H * (land ? 0.14 : 0.12), bottom = H * (land ? 0.74 : 0.76);
  const step = (bottom - top) / lines;
  const bumps = [];
  let s = '';
  for (let i = 0; i < lines; i++) {
    const peaks = [];
    for (let k = 0; k < 4; k++) peaks.push([0.35 + r() * 0.3, 0.03 + r() * 0.05, r() * (0.5 + 0.5 * r())]);
    bumps.push(peaks);
  }
  for (let i = 0; i < lines; i++) {
    const base = top + (i + 1) * step;
    let p = `M${f1(x0)},${f1(base)}`;
    for (let x = x0; x <= x1; x += Math.max(2, (x1 - x0) / 140)) {
      const t = (x - x0) / (x1 - x0);
      let y = 0;
      for (const [c, wdt, h] of bumps[i]) y += h * Math.exp(-((t - c) ** 2) / (2 * wdt * wdt));
      y += (r() - 0.5) * 0.04 * Math.exp(-((t - 0.5) ** 2) / 0.02);
      p += ` L${f1(x)},${f1(base - y * step * 7)}`;
    }
    p += ` L${f1(x1)},${f1(base)}`;
    s += `<path d="${p} L${f1(x1)},${f1(base + step)} L${f1(x0)},${f1(base + step)} Z" fill="#0b0b0b"/><path d="${p}" fill="none" stroke="#f4f1ea" stroke-width="${f1(Math.max(1, m * 0.0035))}" stroke-linejoin="round"/>`;
  }
  const title = String(d.title || '').toUpperCase();
  const fs = fit(title, 0.75, W * 0.6, m * 0.05);
  return `
    <div class="pp-bg" style="background:#0b0b0b"></div>${svg(W, H, s)}
    <div style="${box(0, H * 0.82, W, fs * 1.4, `text-align:center;font:600 ${f1(fs)}px/1.2 'Inter Tight',sans-serif;letter-spacing:.32em;color:#f4f1ea`)}">${esc(title)}</div>
    <div style="${box(0, H * 0.82 + fs * 1.6, W, m * 0.04, `text-align:center;font:400 ${f1(m * 0.024)}px/1 'IBM Plex Mono',monospace;letter-spacing:.14em;color:#a9a59c;text-transform:uppercase`)}">${esc(d.sub)}</div>`;
}

/* ------------------------------------------------------------------ */
/* Drawn: Memphis                                                      */
/* ------------------------------------------------------------------ */

function memphis(d, o) {
  const { W, H, land, r } = o;
  const m = Math.min(W, H);
  const C = ['#f25f8b', '#ffcf3f', '#2ec4b6', '#3a86ff', '#1d1d1d'];
  const ground = pick(r, ['#f6efe4', '#fde8ea', '#e6f3ef']);
  const tb = land
    ? { x: W * 0.28, y: H * 0.34, w: W * 0.44, h: H * 0.32 }
    : { x: W * 0.12, y: H * 0.4, w: W * 0.76, h: H * 0.2 };
  const clear = (x, y, pad) => x > tb.x - pad && x < tb.x + tb.w + pad && y > tb.y - pad && y < tb.y + tb.h + pad;
  let s = '', tries = 0, placed = 0;
  const n = land ? 26 : 30;
  while (placed < n && tries < 400) {
    tries++;
    const x = r() * W, y = r() * H, sz = m * (0.04 + r() * 0.08);
    if (clear(x, y, sz)) continue;
    placed++;
    const c = pick(r, C), rot = f1(r() * 360), sw = f1(m * 0.012);
    switch (Math.floor(r() * 7)) {
      case 0: s += `<circle cx="${f1(x)}" cy="${f1(y)}" r="${f1(sz / 2)}" fill="${c}"/>`; break;
      case 1: s += `<circle cx="${f1(x)}" cy="${f1(y)}" r="${f1(sz / 2)}" fill="none" stroke="${c}" stroke-width="${sw}"/>`; break;
      case 2: s += `<path d="M${f1(x)},${f1(y - sz / 2)} L${f1(x + sz / 2)},${f1(y + sz / 2)} L${f1(x - sz / 2)},${f1(y + sz / 2)} Z" fill="${c}" transform="rotate(${rot} ${f1(x)} ${f1(y)})"/>`; break;
      case 3: {
        let p = `M${f1(x - sz)},${f1(y)}`;
        for (let k = 1; k <= 8; k++) p += ` Q${f1(x - sz + (k - 0.5) * sz / 4)},${f1(y + (k % 2 ? -1 : 1) * sz / 3)} ${f1(x - sz + k * sz / 4)},${f1(y)}`;
        s += `<path d="${p}" fill="none" stroke="${c}" stroke-width="${sw}" stroke-linecap="round" transform="rotate(${rot} ${f1(x)} ${f1(y)})"/>`; break;
      }
      case 4: {
        let p = `M${f1(x - sz)},${f1(y)}`;
        for (let k = 1; k <= 6; k++) p += ` L${f1(x - sz + k * sz / 3)},${f1(y + (k % 2 ? -1 : 1) * sz / 4)}`;
        s += `<path d="${p}" fill="none" stroke="${c}" stroke-width="${sw}" stroke-linejoin="miter" transform="rotate(${rot} ${f1(x)} ${f1(y)})"/>`; break;
      }
      case 5: for (let a = 0; a < 3; a++) for (let b = 0; b < 3; b++) s += `<circle cx="${f1(x + a * sz / 3)}" cy="${f1(y + b * sz / 3)}" r="${f1(m * 0.006)}" fill="${C[4]}"/>`; break;
      default: s += `<path d="M${f1(x - sz / 2)},${f1(y)} A${f1(sz / 2)},${f1(sz / 2)} 0 0 1 ${f1(x + sz / 2)},${f1(y)} Z" fill="${c}" transform="rotate(${rot} ${f1(x)} ${f1(y)})"/>`;
    }
  }
  const title = String(d.title || '').toUpperCase();
  const fs = fit(title, 0.78, tb.w * 0.86, tb.h * 0.42);
  const off = m * 0.018;
  return `
    <div class="pp-bg" style="background:${ground}"></div>${svg(W, H, s)}
    <div style="${box(tb.x + off, tb.y + off, tb.w, tb.h, `background:${C[4]}`)}"></div>
    <div style="${box(tb.x, tb.y, tb.w, tb.h, `background:#fff;border:${f1(m * 0.008)}px solid ${C[4]};box-sizing:border-box;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:${f1(m * 0.012)}px`)}">
      <div style="font:400 ${f1(fs)}px/1 Bungee,sans-serif;color:${C[0]}">${esc(title)}</div>
      <div style="font:600 ${f1(m * 0.03)}px/1 Jost,sans-serif;letter-spacing:.2em;text-transform:uppercase;color:${C[4]}">${esc(d.sub)}</div>
    </div>`;
}

/* ------------------------------------------------------------------ */
/* Drawn: Sunburst                                                     */
/* ------------------------------------------------------------------ */

const SUNSETS = [
  { sky: '#f3dfb8', sun: '#e8743b', rays: '#efcf9f', hills: ['#d0a65c', '#7d8b4e', '#3f5a3c'], ink: '#2b2a26' },
  { sky: '#d8e4dc', sun: '#e3a33b', rays: '#c6d8cd', hills: ['#79a69a', '#3f6f6a', '#24423f'], ink: '#1e2d2b' },
  { sky: '#f4d9cf', sun: '#d4573b', rays: '#edc6b9', hills: ['#c88e6b', '#8c5a45', '#4b3029'], ink: '#2d1f1b' },
];

function sunburst(d, o) {
  const { W, H, land, r } = o;
  const m = Math.min(W, H);
  const P = pick(r, SUNSETS);
  const aw = land ? W * 0.6 : W, ah = land ? H : H * 0.74;
  const hz = ah * 0.62, sx = aw * (0.35 + r() * 0.3), sr = Math.min(aw, ah) * 0.22;
  let rays = '';
  const nr = 18;
  for (let i = 0; i < nr; i++) {
    if (i % 2) continue;
    const a0 = Math.PI + (i / nr) * Math.PI, a1 = Math.PI + ((i + 1) / nr) * Math.PI, L = Math.hypot(aw, ah);
    rays += `<path d="M${f1(sx)},${f1(hz)} L${f1(sx + Math.cos(a0) * L)},${f1(hz + Math.sin(a0) * L)} L${f1(sx + Math.cos(a1) * L)},${f1(hz + Math.sin(a1) * L)} Z" fill="${P.rays}"/>`;
  }
  let hills = '';
  P.hills.forEach((c, k) => {
    const base = hz + (k * ah * 0.11);
    let p = `M0,${f1(ah)} L0,${f1(base)}`;
    const ph = r() * 6, amp = ah * (0.05 + r() * 0.05), fr = 1.5 + r() * 2;
    for (let x = 0; x <= aw; x += aw / 60) p += ` L${f1(x)},${f1(base - amp * (0.6 + 0.4 * Math.sin(x / aw * fr * Math.PI + ph)) - amp * 0.4 * Math.sin(x / aw * 7 + ph * 2))}`;
    hills += `<path d="${p} L${f1(aw)},${f1(ah)} Z" fill="${c}"/>`;
  });
  const art = `<svg class="pp-svg" style="${box(0, 0, aw, ah)}" viewBox="0 0 ${f1(aw)} ${f1(ah)}">
    <rect width="${f1(aw)}" height="${f1(ah)}" fill="${P.sky}"/>${rays}
    <circle cx="${f1(sx)}" cy="${f1(hz)}" r="${f1(sr)}" fill="${P.sun}"/>${hills}</svg>`;
  const title = String(d.title || '');
  let tx, ty, tw, th;
  if (land) { tx = aw + W * 0.04; tw = W - tx - W * 0.04; ty = H * 0.3; th = H * 0.4; }
  else { tx = W * 0.07; tw = W * 0.86; ty = ah + H * 0.03; th = H - ah - H * 0.06; }
  const fs = fit(title, 0.62, tw, th * 0.5);
  return `
    <div class="pp-bg" style="background:${P.sky}"></div>${art}
    <div style="${box(tx, ty, tw, th, `display:flex;flex-direction:column;justify-content:center;gap:${f1(m * 0.015)}px;color:${P.ink}`)}">
      <div style="font:400 ${f1(fs)}px/1 'Alfa Slab One',serif;white-space:nowrap">${esc(title)}</div>
      <div style="font:500 ${f1(m * 0.03)}px/1.2 Jost,sans-serif;letter-spacing:.24em;text-transform:uppercase">${esc(d.sub)}</div>
    </div>`;
}

/* ------------------------------------------------------------------ */
/* Museum prints                                                       */
/* ------------------------------------------------------------------ */

function gallery(d, o) {
  const { W, H, land } = o;
  const m = Math.min(W, H);
  const ground = d.style === 'ukiyoe' ? '#efe7d6' : '#f4f2ed';
  const a = d.art || {};
  let ax, ay, aw, ah, lx, ly, lw, lh;
  if (land) { ax = W * 0.05; ay = H * 0.07; aw = W * 0.58; ah = H * 0.86; lx = ax + aw + W * 0.04; lw = W - lx - W * 0.05; ly = H * 0.5; lh = H * 0.43; }
  else { ax = W * 0.08; ay = H * 0.06; aw = W * 0.84; ah = H * 0.7; lx = ax; lw = aw; ly = ay + ah + H * 0.04; lh = H - ly - H * 0.04; }
  const name = String(a.artist || '').replace(/\s*\(.*$/, '');
  const fs = fit(name, 0.52, land ? lw : lw * 0.5, m * 0.055);
  const small = Math.max(8, m * 0.019);
  const pic = d.pic
    ? `<img src="${d.pic}" alt="" style="${box(ax, ay, aw, ah, 'object-fit:contain;object-position:center')}">`
    : `<div style="${box(ax, ay, aw, ah, 'background:#e4e0d7')}"></div>`;
  const label = land
    ? `<div style="${box(lx, ly, lw, lh, `display:flex;flex-direction:column;justify-content:flex-end;gap:${f1(m * 0.012)}px;color:#222`)}">
         <div style="font:600 ${f1(fs)}px/1.05 'Inter Tight',sans-serif;letter-spacing:-.01em">${esc(name)}</div>
         <div style="font:400 ${f1(small * 1.15)}px/1.4 'Inter Tight',sans-serif">${esc(a.title)}${a.date ? ', ' + esc(a.date) : ''}</div>
         <div style="font:400 ${f1(small)}px/1.4 'Inter Tight',sans-serif;color:#666">${esc(a.medium)}<br>${esc(a.credit)}</div></div>`
    : `<div style="${box(lx, ly, lw * 0.5, lh, `font:600 ${f1(fs)}px/1.05 'Inter Tight',sans-serif;color:#222`)}">${esc(name)}</div>
       <div style="${box(lx + lw * 0.52, ly, lw * 0.48, lh, `text-align:right;font:400 ${f1(small)}px/1.4 'Inter Tight',sans-serif;color:#333`)}">${esc(a.title)}${a.date ? ', ' + esc(a.date) : ''}<br><span style="color:#777">${esc(a.credit)}</span></div>`;
  return `<div class="pp-bg" style="background:${ground}"></div>${pic}${label}`;
}

/* ------------------------------------------------------------------ */
/* Painted                                                             */
/* ------------------------------------------------------------------ */

/* The picture, or while it is painted a hatched panel saying so. */
function picture(d, x, y, w, h, extra = '', size = 'cover') {
  if (d.pic) return `<div style="${box(x, y, w, h, `background:url(${d.pic}) center/${size} no-repeat;${extra}`)}"></div>`;
  const m = Math.min(w, h);
  return `<div style="${box(x, y, w, h, `background:repeating-linear-gradient(135deg,rgba(0,0,0,.05) 0 2px,transparent 2px 12px);display:flex;align-items:center;justify-content:center;${extra}`)}">
    <span style="font:400 ${f1(Math.max(9, m * 0.035))}px/1.3 'IBM Plex Mono',monospace;color:#6b6457;text-align:center;padding:8%">${esc((d.notices && d.notices[0]) || `Painting ${(d.subject || {}).name || ''}…`)}</span></div>`;
}

/* The place name for a headline: before a comma, without "National Park". */
/* Fade a picture's edges into the paper (both axes). */
const FADE = (pct) => `-webkit-mask-image:linear-gradient(to bottom,transparent,#000 ${pct}%,#000 ${100 - pct}%,transparent),linear-gradient(to right,transparent,#000 ${pct}%,#000 ${100 - pct}%,transparent);-webkit-mask-composite:source-in;mask-image:linear-gradient(to bottom,transparent,#000 ${pct}%,#000 ${100 - pct}%,transparent),linear-gradient(to right,transparent,#000 ${pct}%,#000 ${100 - pct}%,transparent);mask-composite:intersect;`;

function shortName(s) {
  const name = String((s && s.name) || '');
  return name.split(',')[0].replace(/\s+National Park$/i, '').replace(/-Lake St Clair/i, '').trim();
}
function secondLine(s) {
  if (s.label) return s.label;
  const name = String(s.name || '');
  if (name.includes(',')) return name.split(',').slice(1).join(',').trim();
  if (/National Park$/i.test(name)) return 'National Park';
  return s.desc || '';
}

function woodblock(d, o) {
  const { W, H } = o;
  const m = Math.min(W, H);
  const s = d.subject || {};
  const ja = String(s.ja || '');
  const ink = '#1d1a16', red = '#b13b25';
  const vs = Math.min(m * 0.075, (H * 0.62) / Math.max(1, ja.length) / 1.12);
  const label = ja
    ? `<div style="${box(W - m * 0.07 - vs * 1.2, H * 0.06, vs * 1.3, H * 0.8, `writing-mode:vertical-rl;font:800 ${f1(vs)}px/1.1 'Shippori Mincho',serif;letter-spacing:.12em;color:${ink}`)}">${esc(ja)}<span style="display:block;width:${f1(Math.max(1, m * 0.005))}px;height:${f1(vs * 1.6)}px;background:${ink};margin:${f1(vs * 0.25)}px auto 0"></span></div>`
    : '';
  const sealW = m * 0.06;
  const seal = `<div style="${box(W - m * 0.07 - vs * 1.2 - sealW * 1.5, H * 0.065, sealW, sealW * 1.5, `border:${f1(m * 0.005)}px solid ${red};color:${red};font:800 ${f1(sealW * 0.46)}px/1.05 'Shippori Mincho',serif;writing-mode:vertical-rl;display:flex;align-items:center;justify-content:center;box-sizing:border-box`)}">${esc(d.date.kanji)}</div>`;
  const cap = `${s.name || ''} · ${d.date.day} ${d.date.month} ${d.date.year}`;
  return `
    <div class="pp-bg" style="background:#efe3c8"></div>${picture(d, 0, 0, W, H)}${label}${seal}
    <div style="${box(W * 0.05, H - m * 0.06, W * 0.7, m * 0.04, `font:400 ${f1(Math.max(8, m * 0.022))}px/1 'IBM Plex Mono',monospace;letter-spacing:.06em;color:#5d5547;white-space:nowrap`)}">${esc(cap)}</div>`;
}

function travel(d, o) {
  const { W, H, land, r } = o;
  const m = Math.min(W, H);
  const s = d.subject || {};
  const ink = pick(r, ['#2f7a45', '#1f4e79', '#b13b25']);
  const red = ink === '#b13b25' ? '#1f4e79' : '#b13b25';
  const head = shortName(s).toUpperCase();
  const second = secondLine(s);
  const facts = String(s.facts || '');
  const yr = String(s.year || '');
  const ground = '#f2e5c7';
  if (land) {
    const pw = W * d.region[0];
    const tw = W - pw - W * 0.06;
    const fs = fit(head, 0.47, tw, H * 0.28);
    return `<div class="pp-bg" style="background:${ground}"></div>${picture(d, W - pw, 0, pw, H, FADE(6))}
      <div style="${box(W * 0.04, H * 0.06, tw, H * 0.88, `display:flex;flex-direction:column;gap:${f1(m * 0.025)}px`)}">
        <div style="font:400 ${f1(fs)}px/.92 Anton,Impact,sans-serif;color:${ink}">${esc(head)}</div>
        <div style="font:700 ${f1(m * 0.03)}px/1.2 'IBM Plex Mono',monospace;letter-spacing:.2em;text-transform:uppercase;color:${red}">${esc(second)}</div>
        <div style="flex:1"></div>
        <div style="font:500 ${f1(Math.max(8, m * 0.022))}px/1.4 'IBM Plex Mono',monospace;text-transform:uppercase;color:#3c3326">${esc(facts)}</div>
        ${yr ? `<div style="font:400 ${f1(m * 0.2)}px/.85 Anton,Impact,sans-serif;color:${ink}">${esc(yr)}</div>` : ''}
      </div>`;
  }
  const top = H * 0.155;
  const ph = H * d.region[1];
  const fs = fit(head, 0.47, W * 0.9, top * 0.86);
  const by = top + ph + H * 0.02;
  const ys = yr ? Math.min(W * 0.2, (H - by) * 0.8) : 0;
  return `<div class="pp-bg" style="background:${ground}"></div>${picture(d, 0, top, W, ph, FADE(6))}
    <div style="${box(W * 0.05, H * 0.02, W * 0.9, top, `display:flex;align-items:center;justify-content:center;font:400 ${f1(fs)}px/.92 Anton,Impact,sans-serif;color:${ink};white-space:nowrap`)}">${esc(head)}</div>
    <div style="${box(W * 0.06, by, W * (yr ? 0.5 : 0.88), H - by - H * 0.03, `display:flex;flex-direction:column;gap:${f1(m * 0.015)}px`)}">
      <div style="font:700 ${f1(m * 0.03)}px/1.2 'IBM Plex Mono',monospace;letter-spacing:.2em;text-transform:uppercase;color:${red}">${esc(second)}</div>
      <div style="font:500 ${f1(Math.max(8, m * 0.022))}px/1.4 'IBM Plex Mono',monospace;text-transform:uppercase;color:#3c3326">${esc(facts)}</div>
    </div>
    ${yr ? `<div style="${box(W * 0.56, H - ys - H * 0.035, W * 0.38, ys, `text-align:right;font:400 ${f1(ys)}px/1 Anton,Impact,sans-serif;color:${ink}`)}">${esc(yr)}</div>` : ''}`;
}

function deco(d, o) {
  const { W, H, land } = o;
  const m = Math.min(W, H);
  const s = d.subject || {};
  const navy = '#1d2b3a', cream = '#efe3c6', gold = '#d9a441';
  const head = shortName(s).toUpperCase();
  const second = secondLine(s);
  const inset = m * 0.025;
  if (land) {
    const pw = W * d.region[0];
    const tw = W - pw - W * 0.08;
    const fs = fit(head, 0.62, tw, H * 0.2);
    return `<div class="pp-bg" style="background:${navy}"></div>${picture(d, inset, inset, pw - inset, H - inset * 2, `outline:${f1(m * 0.004)}px solid ${gold};outline-offset:${f1(-inset * 0.5)}px`)}
      <div style="${box(pw + W * 0.04, H * 0.1, tw, H * 0.8, `display:flex;flex-direction:column;justify-content:center;gap:${f1(m * 0.03)}px;text-align:center`)}">
        <div style="font:500 ${f1(m * 0.035)}px/1 Jost,sans-serif;letter-spacing:.5em;color:${gold}">SEE</div>
        <div style="font:400 ${f1(fs)}px/1.05 'Poiret One',sans-serif;letter-spacing:.08em;color:${cream}">${esc(head)}</div>
        <div style="height:${f1(Math.max(1, m * 0.004))}px;background:${gold};margin:0 20%"></div>
        <div style="font:500 ${f1(m * 0.03)}px/1.3 Jost,sans-serif;letter-spacing:.3em;text-transform:uppercase;color:${gold}">${esc(second)}</div>
      </div>`;
  }
  const ph = H * d.region[1];
  const fs = fit(head, 0.62, W * 0.86, (H - ph) * 0.34);
  return `<div class="pp-bg" style="background:${navy}"></div>${picture(d, inset, inset, W - inset * 2, ph - inset, `outline:${f1(m * 0.004)}px solid ${gold};outline-offset:${f1(-inset * 0.5)}px`)}
    <div style="${box(0, ph, W, H - ph, `display:flex;flex-direction:column;align-items:center;justify-content:center;gap:${f1(m * 0.02)}px;text-align:center`)}">
      <div style="font:500 ${f1(m * 0.03)}px/1 Jost,sans-serif;letter-spacing:.5em;color:${gold}">SEE</div>
      <div style="font:400 ${f1(fs)}px/1 'Poiret One',sans-serif;letter-spacing:.08em;color:${cream};white-space:nowrap">${esc(head)}</div>
      <div style="font:500 ${f1(m * 0.026)}px/1.2 Jost,sans-serif;letter-spacing:.32em;text-transform:uppercase;color:${gold}">${esc(second)}</div>
    </div>`;
}

function riso(d, o) {
  const { W, H, land } = o;
  const m = Math.min(W, H);
  const s = d.subject || {};
  const pink = '#ff48b0', teal = '#0078bf';
  const head = String(s.name || '').toUpperCase();
  const tw = land ? W * 0.9 : W * 0.92;
  const fs = fit(head, 0.47, tw, H * (land ? 0.3 : 0.2));
  const ty = H - fs * 1.05 - m * 0.1;
  const t = (c, dx, dy) => `<div style="${box(W * 0.04 + dx, ty + dy, tw, fs * 1.1, `font:400 ${f1(fs)}px/1 Anton,Impact,sans-serif;color:${c};mix-blend-mode:multiply;white-space:nowrap`)}">${esc(head)}</div>`;
  const row = [`No. ${d.date.doy}`, s.desc || '', `${d.date.day} ${d.date.month} ${d.date.year}`].filter(Boolean);
  return `<div class="pp-bg" style="background:#f4f0e6"></div>${picture(d, 0, 0, W, H)}
    ${t(pink, 0, 0)}
    <div style="${box(W * 0.04, H - m * 0.07, W * 0.92, m * 0.04, `display:flex;justify-content:space-between;gap:${f1(m * 0.02)}px;font:500 ${f1(Math.max(8, m * 0.022))}px/1 'IBM Plex Mono',monospace;text-transform:uppercase;color:${teal};mix-blend-mode:multiply;white-space:nowrap;overflow:hidden`)}">${row.map((x) => `<span>${esc(x)}</span>`).join('')}</div>`;
}

function botanical(d, o) {
  const { W, H, land } = o;
  const m = Math.min(W, H);
  const s = d.subject || {};
  const ink = '#3a3227';
  const latin = s.name || '';
  const common = s.common || s.label || '';
  const rule = Math.max(1, m * 0.003);
  const [rw, rh] = d.region || [0.84, 0.7];
  let px, py, pw, ph, lx, ly, lw, lh;
  if (land) { pw = W * rw; ph = H * rh; px = W * 0.06; py = (H - ph) / 2; lx = px + pw + W * 0.05; lw = W - lx - W * 0.06; ly = py; lh = ph; }
  else { pw = W * rw; ph = H * rh; px = (W - pw) / 2; py = H * 0.07; lx = px; lw = pw; ly = py + ph + H * 0.025; lh = H - ly - H * 0.05; }
  const fs = fit(latin, 0.42, lw, m * 0.065);
  const frame = `<div style="${box(W * 0.03, H * 0.03, W * 0.94, H * 0.94, `border:${f1(rule)}px solid ${ink};box-sizing:border-box;outline:${f1(rule)}px solid ${ink};outline-offset:-${f1(m * 0.012)}px`)}"></div>`;
  return `<div class="pp-bg" style="background:#efe6d2"></div>${frame}${picture(d, px, py, pw, ph)}
    <div style="${box(lx, ly, lw, lh, `display:flex;flex-direction:column;justify-content:${land ? 'center' : 'flex-start'};align-items:center;text-align:center;gap:${f1(m * 0.012)}px;color:${ink}`)}">
      <div style="font:600 ${f1(m * 0.024)}px/1 'Cormorant Garamond',serif;letter-spacing:.2em">PL. ${esc(d.date.doy)}</div>
      <div style="font:italic 500 ${f1(fs)}px/1.05 'Cormorant Garamond',serif">${esc(latin)}</div>
      ${common ? `<div style="font:600 ${f1(m * 0.026)}px/1.2 'Cormorant Garamond',serif;letter-spacing:.18em;text-transform:uppercase">${esc(common)}</div>` : ''}
      ${land && s.facts ? `<div style="font:400 ${f1(Math.max(8, m * 0.02))}px/1.5 'IBM Plex Mono',monospace;color:#6b6457;margin-top:${f1(m * 0.02)}px">${esc(s.facts)}</div>` : ''}
    </div>`;
}

function linocut(d, o) {
  const { W, H, land } = o;
  const m = Math.min(W, H);
  const s = d.subject || {};
  const ink = '#161412', accent = '#c7562a';
  const head = String(s.name || '').toUpperCase();
  const [rw, rh] = d.region || [0.86, 0.68];
  const small = Math.max(8, m * 0.021);
  if (land) {
    const pw = W * rw, ph = H * rh, px = W * 0.05, py = (H - ph) / 2;
    const lx = px + pw + W * 0.05, lw = W - lx - W * 0.05;
    const fs = fit(head, 0.72, lw, H * 0.16);
    return `<div class="pp-bg" style="background:#efe8da"></div>${picture(d, px, py, pw, ph)}
      <div style="${box(lx, py, lw, ph, `display:flex;flex-direction:column;justify-content:flex-end;gap:${f1(m * 0.02)}px;color:${ink}`)}">
        <div style="font:400 ${f1(fs)}px/1 'Alfa Slab One',serif">${esc(head)}</div>
        <div style="height:${f1(m * 0.012)}px;width:30%;background:${accent}"></div>
        <div style="font:500 ${f1(small)}px/1.45 'IBM Plex Mono',monospace;text-transform:uppercase">${esc(s.facts || s.desc || '')}</div>
      </div>`;
  }
  const pw = W * rw, ph = H * rh, px = (W - pw) / 2, py = H * 0.06;
  const fs = fit(head, 0.72, pw, H * 0.09);
  const ty = py + ph + H * 0.03;
  return `<div class="pp-bg" style="background:#efe8da"></div>${picture(d, px, py, pw, ph)}
    <div style="${box(px, ty, pw, H - ty - H * 0.04, `display:flex;flex-direction:column;gap:${f1(m * 0.016)}px;color:${ink}`)}">
      <div style="font:400 ${f1(fs)}px/1 'Alfa Slab One',serif;white-space:nowrap">${esc(head)}</div>
      <div style="height:${f1(m * 0.012)}px;width:24%;background:${accent}"></div>
      <div style="font:500 ${f1(small)}px/1.45 'IBM Plex Mono',monospace;text-transform:uppercase">${esc(s.facts || s.desc || '')}</div>
    </div>`;
}

const STYLES = {
  ausstellung, swiss, constructivist, ridgeline, memphis, sunburst,
  gallery, ukiyoe: gallery, woodblock, travel, deco, riso, botanical, linocut,
};

/* @font-face inside a shadow root is not honoured everywhere, so the faces
   go into the document once (shadow trees inherit them), and the render waits
   for them so a screenshot never catches the fallback face. */
async function useFonts(css) {
  if (!css || typeof document === 'undefined') return;
  let h = 0;
  for (let i = 0; i < css.length; i += 997) h = (h * 31 + css.charCodeAt(i)) | 0;
  const id = `poster-fonts-${(h >>> 0).toString(36)}-${css.length}`;
  if (!document.getElementById(id)) {
    const el = document.createElement('style');
    el.id = id;
    el.textContent = css;
    document.head.appendChild(el);
  }
  const fams = new Set();
  for (const m of css.matchAll(/font-family:'([^']+)';font-style:(\w+);font-weight:([\d ]+)/g)) fams.add(`${m[2]} ${m[3].split(' ')[0]} 20px '${m[1]}'`);
  for (const m of css.matchAll(/font-family:'([^']+)';font-weight:(\d+)/g)) fams.add(`normal ${m[2]} 20px '${m[1]}'`);
  try {
    await Promise.race([
      Promise.all([...fams].map((f) => document.fonts.load(f, 'AZaz09ワ'))),
      new Promise((res) => setTimeout(res, 3000)),
    ]);
  } catch (e) { /* the fallback face is still a poster */ }
}

export default async function render(shadow, ctx) {
  const d = (ctx && ctx.data) || {};
  const cell = (ctx && ctx.cell) || {};
  const rect = shadow.host && shadow.host.getBoundingClientRect ? shadow.host.getBoundingClientRect() : { width: 0, height: 0 };
  const W = Math.round(cell.w || rect.width || d.w || 600);
  const H = Math.round(cell.h || rect.height || d.h || 800);
  const land = W > H * 1.05;
  if (!d.style) {
    shadow.innerHTML = '<div style="display:flex;align-items:center;justify-content:center;height:100%;font:14px sans-serif;color:#777">No poster yet.</div>';
    return;
  }
  d.date = d.date || {};
  await useFonts(d.font_css || '');
  const draw = STYLES[d.style] || ausstellung;
  let body;
  try {
    body = draw(d, { W, H, land, r: rng(d.seed) });
  } catch (err) {
    body = `<div style="padding:16px;font:13px monospace;color:#a00">${esc(err && err.message)}</div>`;
  }
  // A finished poster stays clean; a note only shows while there is no picture.
  const needsPic = d.kind !== 'drawn';
  const note = needsPic && !d.pic && d.notices && d.notices.length && d.kind === 'museum'
    ? `<div style="${box(W * 0.05, H * 0.45, W * 0.9, 60, `text-align:center;font:400 ${f1(Math.max(9, Math.min(W, H) * 0.025))}px/1.4 'IBM Plex Mono',monospace;color:#6b6457`)}">${esc(d.notices[0])}</div>`
    : '';
  shadow.innerHTML = `<style>
    :host{display:block;width:100%;height:100%}
    .pp{position:relative;width:${W}px;height:${H}px;overflow:hidden}
    .pp-bg{position:absolute;inset:0}
    .pp-svg{position:absolute;left:0;top:0;display:block;overflow:hidden}
    .pp *{box-sizing:border-box;margin:0}
  </style><div class="pp">${body}${note}</div>`;
}
