/** Frame capture: crop the guide region out of the live video and compress
 *  to a reasonable upload size. Everything stays in memory. */

import type { NormalizedRect } from "./detect.js";

const MAX_CAPTURE_WIDTH = 1600;
const QUALITY_STEPS = [0.92, 0.8, 0.7, 0.6, 0.5];

/** Map the guide rect (element coordinates) into normalized video
 *  coordinates, accounting for object-fit: cover cropping. */
export function elementRectToVideoRect(
  video: HTMLVideoElement,
  elRect: { x: number; y: number; w: number; h: number },
  elW: number,
  elH: number,
): NormalizedRect {
  const vw = video.videoWidth;
  const vh = video.videoHeight;
  const scale = Math.max(elW / vw, elH / vh);
  const offX = (vw * scale - elW) / 2;
  const offY = (vh * scale - elH) / 2;
  const x = (elRect.x + offX) / scale / vw;
  const y = (elRect.y + offY) / scale / vh;
  const w = elRect.w / scale / vw;
  const h = elRect.h / scale / vh;
  const clamp = (v: number) => Math.min(1, Math.max(0, v));
  return { x: clamp(x), y: clamp(y), w: clamp(w), h: clamp(h) };
}

/** Grab the current frame, crop to `region` (normalized video coords, with
 *  a small margin so a slightly-off card still fits), return a JPEG blob. */
export async function captureFrame(
  video: HTMLVideoElement,
  region: NormalizedRect,
  maxBytes: number,
): Promise<Blob> {
  const vw = video.videoWidth;
  const vh = video.videoHeight;
  const margin = 0.04;
  const x = Math.max(0, (region.x - margin) * vw);
  const y = Math.max(0, (region.y - margin) * vh);
  const w = Math.min(vw - x, (region.w + margin * 2) * vw);
  const h = Math.min(vh - y, (region.h + margin * 2) * vh);

  const outW = Math.min(Math.round(w), MAX_CAPTURE_WIDTH);
  const outH = Math.round((h * outW) / w);
  const canvas = document.createElement("canvas");
  canvas.width = outW;
  canvas.height = outH;
  canvas.getContext("2d")!.drawImage(video, x, y, w, h, 0, 0, outW, outH);
  return compressCanvas(canvas, maxBytes);
}

async function compressCanvas(
  canvas: HTMLCanvasElement,
  maxBytes: number,
): Promise<Blob> {
  let blob: Blob | null = null;
  for (const q of QUALITY_STEPS) {
    blob = await toBlob(canvas, q);
    if (blob && blob.size <= maxBytes) return blob;
  }
  if (!blob) throw new Error("could not encode capture as JPEG");
  return blob;
}

function toBlob(canvas: HTMLCanvasElement, quality: number): Promise<Blob | null> {
  return new Promise((resolve) =>
    canvas.toBlob(resolve, "image/jpeg", quality),
  );
}
