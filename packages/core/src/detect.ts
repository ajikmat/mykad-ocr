/** Guided auto-capture heuristics (CONTEXT.md).
 *
 * Deliberately NOT card recognition: we only check that something
 * card-edge-shaped sits on the guide frame, the image is sharp, and the
 * scene is steady. Whether it's actually a MyKad is the OCR Service's call.
 *
 * This is the 0.1.0 detector (validated on real devices in normal indoor
 * light) with two ergonomic changes that do NOT alter its light
 * requirements: the border band is tried at several inset/outset offsets
 * so the card doesn't have to fit the zone exactly, and the steadiness
 * tolerance is relaxed for hand tremor (steadiness was never the
 * false-positive guard — card presence is).
 *
 * All thresholds are exported for tuning against real devices; the manual
 * shutter button is always available as the backstop.
 */

export const DETECT = {
  /** downscaled analysis width in px */
  width: 160,
  /** mean edge strength on the guide border ("a card edge is there") */
  edgeBandMin: 22,
  /** border edges must beat interior edges by this factor */
  bandVsInner: 1.1,
  /** the border band (half-width 2) is evaluated at each of these
   *  inset(-)/outset(+) offsets and the best match wins — tolerates the
   *  card being held slightly smaller or larger than the zone */
  bandOffsets: [-4, -2, 0, 2, 4],
  /** variance of edge strength inside the guide ("image is sharp") */
  sharpnessMin: 180,
  /** mean per-pixel diff vs previous frame ("holding steady") —
   *  relaxed vs 0.1.0's 7 so normal hand tremor passes */
  steadyMaxDiff: 11,
  /** good ticks before auto-capture (~150 ms each). An unsteady-but-framed
   *  tick pauses the count; losing the card resets it — see scanner.tick() */
  ticksToLock: 5,
};

export interface NormalizedRect {
  x: number;
  y: number;
  w: number;
  h: number;
}

export interface DetectTick {
  cardPresent: boolean;
  steady: boolean;
  sharp: boolean;
}

/** The 0.1.0 detection math on a grayscale frame — pure and testable.
 *  The CardDetector class wraps this with the canvas plumbing. */
export function analyzeFrame(
  gray: Uint8ClampedArray,
  w: number,
  h: number,
  guide: NormalizedRect,
  prev: Uint8ClampedArray | null,
): DetectTick {
  // steadiness vs previous frame
  let steady = false;
  if (prev && prev.length === gray.length) {
    let diff = 0;
    for (let i = 0; i < gray.length; i += 4) {
      diff += Math.abs(gray[i] - prev[i]);
    }
    steady = diff / (gray.length / 4) <= DETECT.steadyMaxDiff;
  }

  // gradient magnitude (cheap sobel-ish)
  const edge = new Float32Array(w * h);
  for (let y = 1; y < h - 1; y++) {
    for (let x = 1; x < w - 1; x++) {
      const i = y * w + x;
      const gx = gray[i + 1] - gray[i - 1];
      const gy = gray[i + w] - gray[i - w];
      edge[i] = Math.abs(gx) + Math.abs(gy);
    }
  }

  const gx0 = Math.round(guide.x * w);
  const gy0 = Math.round(guide.y * h);
  const gx1 = Math.round((guide.x + guide.w) * w);
  const gy1 = Math.round((guide.y + guide.h) * h);

  // mean edge strength in a thin band along the guide border, tried at
  // each offset (negative = ring shrunk inward, positive = grown outward);
  // the best-aligned ring represents the card
  const band = 2;
  let bandMean = 0;
  for (const off of DETECT.bandOffsets) {
    const bx0 = gx0 - off;
    const by0 = gy0 - off;
    const bx1 = gx1 + off;
    const by1 = gy1 + off;
    let bandSum = 0;
    let bandN = 0;
    for (let y = by0 - band; y <= by1 + band; y++) {
      for (let x = bx0 - band; x <= bx1 + band; x++) {
        if (x < 1 || y < 1 || x >= w - 1 || y >= h - 1) continue;
        const onBorder =
          Math.abs(x - bx0) <= band || Math.abs(x - bx1) <= band ||
          Math.abs(y - by0) <= band || Math.abs(y - by1) <= band;
        const inRect =
          x >= bx0 - band && x <= bx1 + band &&
          y >= by0 - band && y <= by1 + band;
        if (onBorder && inRect) {
          bandSum += edge[y * w + x];
          bandN++;
        }
      }
    }
    const m = bandN ? bandSum / bandN : 0;
    if (m > bandMean) bandMean = m;
  }

  // interior edge stats (shrunk 20%): mean for contrast, variance for focus
  const ix0 = Math.round(gx0 + 0.2 * (gx1 - gx0));
  const ix1 = Math.round(gx1 - 0.2 * (gx1 - gx0));
  const iy0 = Math.round(gy0 + 0.2 * (gy1 - gy0));
  const iy1 = Math.round(gy1 - 0.2 * (gy1 - gy0));
  let sum = 0;
  let sumSq = 0;
  let n = 0;
  for (let y = Math.max(1, iy0); y < Math.min(h - 1, iy1); y++) {
    for (let x = Math.max(1, ix0); x < Math.min(w - 1, ix1); x++) {
      const e = edge[y * w + x];
      sum += e;
      sumSq += e * e;
      n++;
    }
  }
  const innerMean = n ? sum / n : 0;
  const innerVar = n ? sumSq / n - innerMean * innerMean : 0;

  return {
    cardPresent:
      bandMean >= DETECT.edgeBandMin &&
      bandMean >= innerMean * DETECT.bandVsInner,
    sharp: innerVar >= DETECT.sharpnessMin,
    steady,
  };
}

export class CardDetector {
  private canvas = document.createElement("canvas");
  private ctx = this.canvas.getContext("2d", { willReadFrequently: true })!;
  private prev: Uint8ClampedArray | null = null;

  /** Analyze one video frame. `guide` is the guide rect in normalized
   *  video coordinates (0..1). */
  analyze(video: HTMLVideoElement, guide: NormalizedRect): DetectTick {
    const vw = video.videoWidth;
    const vh = video.videoHeight;
    if (!vw || !vh) return { cardPresent: false, steady: false, sharp: false };

    const w = DETECT.width;
    const h = Math.round((w * vh) / vw);
    this.canvas.width = w;
    this.canvas.height = h;
    this.ctx.drawImage(video, 0, 0, w, h);
    const rgba = this.ctx.getImageData(0, 0, w, h).data;

    const gray = new Uint8ClampedArray(w * h);
    for (let i = 0; i < w * h; i++) {
      const j = i * 4;
      gray[i] = (rgba[j] * 3 + rgba[j + 1] * 4 + rgba[j + 2]) >> 3;
    }

    const tick = analyzeFrame(gray, w, h, guide, this.prev);
    this.prev = gray.slice();
    return tick;
  }

  reset(): void {
    this.prev = null;
  }
}
