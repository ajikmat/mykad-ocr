/** Guided auto-capture heuristics (CONTEXT.md).
 *
 * Deliberately NOT card recognition: we only check that something
 * card-edge-shaped sits on the guide frame, the image is sharp, and the
 * scene is steady. Whether it's actually a MyKad is the OCR Service's call.
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
  /** variance of edge strength inside the guide ("image is sharp") */
  sharpnessMin: 180,
  /** mean per-pixel diff vs previous frame ("holding steady") —
   *  loose on purpose: normal hand tremor must still pass */
  steadyMaxDiff: 14,
  /** good ticks accumulated before auto-capture (~150 ms each).
   *  Progress is forgiving: a wobbly tick pauses it, only losing the
   *  card/focus decays it — see scanner.tick() */
  ticksToLock: 4,
  /** minimum gradient variance of the CAPTURED crop; below this the
   *  capture is discarded as motion-blurred and scanning resumes */
  captureSharpMin: 120,
};

/** Variance of gradient magnitude over a grayscale image — the blur
 *  measure shared by live detection and the post-capture quality gate.
 *  Pure math, unit-testable without a DOM. */
export function gradientVariance(
  gray: Uint8ClampedArray,
  w: number,
  h: number,
): number {
  let sum = 0;
  let sumSq = 0;
  let n = 0;
  for (let y = 1; y < h - 1; y++) {
    for (let x = 1; x < w - 1; x++) {
      const i = y * w + x;
      const gx = gray[i + 1] - gray[i - 1];
      const gy = gray[i + w] - gray[i - w];
      const e = Math.abs(gx) + Math.abs(gy);
      sum += e;
      sumSq += e * e;
      n++;
    }
  }
  const mean = n ? sum / n : 0;
  return n ? sumSq / n - mean * mean : 0;
}

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

    // steadiness vs previous frame
    let steady = false;
    if (this.prev && this.prev.length === gray.length) {
      let diff = 0;
      for (let i = 0; i < gray.length; i += 4) {
        diff += Math.abs(gray[i] - this.prev[i]);
      }
      steady = diff / (gray.length / 4) <= DETECT.steadyMaxDiff;
    }
    this.prev = gray.slice();

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

    // mean edge strength in a thin band along the guide border
    const band = 2;
    let bandSum = 0;
    let bandN = 0;
    for (let y = gy0; y <= gy1; y++) {
      for (let x = gx0; x <= gx1; x++) {
        if (x < 0 || y < 0 || x >= w || y >= h) continue;
        const onBorder =
          Math.abs(x - gx0) <= band || Math.abs(x - gx1) <= band ||
          Math.abs(y - gy0) <= band || Math.abs(y - gy1) <= band;
        if (onBorder) {
          bandSum += edge[y * w + x];
          bandN++;
        }
      }
    }
    const bandMean = bandN ? bandSum / bandN : 0;

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

  reset(): void {
    this.prev = null;
  }
}
