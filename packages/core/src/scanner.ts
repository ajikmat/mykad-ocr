/** The scanner: camera view, guide overlay, auto-capture loop, manual
 *  shutter, upload fallback. Framework-agnostic — Vue/React wrappers just
 *  mount this into a div. */

import { submitScan } from "./api.js";
import { captureFrame, elementRectToVideoRect } from "./capture.js";
import { CardDetector, DETECT } from "./detect.js";
import { DEFAULT_LABELS } from "./labels.js";
import type {
  Labels,
  MykadScanner,
  MykadScannerOptions,
} from "./types.js";

const MYKAD_ASPECT = 85.6 / 53.98;
const TICK_MS = 150;
const REJECT_RESUME_MS = 1800;

type State =
  | "idle"
  | "starting"
  | "scanning"
  | "locking"
  | "uploading"
  | "done"
  | "camera-unavailable";

export function createMykadScanner(options: MykadScannerOptions): MykadScanner {
  return new Scanner(options);
}

class Scanner implements MykadScanner {
  private opts: MykadScannerOptions;
  private labels: Labels;
  private state: State = "idle";

  private container: HTMLElement | null = null;
  private root!: HTMLDivElement;
  private video!: HTMLVideoElement;
  private frame!: HTMLDivElement;
  private status!: HTMLDivElement;
  private shutterBtn!: HTMLButtonElement;
  private uploadInput!: HTMLInputElement;

  private stream: MediaStream | null = null;
  private detector = new CardDetector();
  private timer: number | null = null;
  private lockTicks = 0;
  private resumeTimer: number | null = null;

  constructor(options: MykadScannerOptions) {
    this.opts = options;
    this.labels = { ...DEFAULT_LABELS, ...options.labels };
  }

  // ------------------------------------------------------------ public API

  mount(container: HTMLElement): void {
    if (this.container) throw new Error("scanner already mounted");
    this.container = container;
    injectStylesOnce();
    this.buildDom();
    void this.startCamera();
  }

  captureNow(): void {
    if (this.state !== "scanning" && this.state !== "locking") return;
    void this.capture();
  }

  submitImage(image: Blob): void {
    void this.submit(image);
  }

  resume(): void {
    if (!this.container || this.state === "scanning") return;
    if (this.stream) {
      this.setState("scanning", this.labels.guide);
      this.startLoop();
    } else {
      void this.startCamera();
    }
  }

  destroy(): void {
    this.stopLoop();
    if (this.resumeTimer) window.clearTimeout(this.resumeTimer);
    this.stopCamera();
    this.root?.remove();
    this.container = null;
    this.state = "idle";
  }

  // ---------------------------------------------------------------- camera

  private async startCamera(): Promise<void> {
    this.setState("starting", "");
    try {
      this.stream = await navigator.mediaDevices.getUserMedia({
        video: {
          facingMode: "environment",
          width: { ideal: 1920 },
          height: { ideal: 1080 },
        },
        audio: false,
      });
      this.video.srcObject = this.stream;
      await this.video.play();
      this.root.classList.remove("mks-no-camera");
      this.setState("scanning", this.labels.guide);
      this.detector.reset();
      this.startLoop();
    } catch {
      // permission denied / no camera — the upload fallback carries on
      this.root.classList.add("mks-no-camera");
      this.setState("camera-unavailable", this.labels.cameraUnavailable);
    }
  }

  private stopCamera(): void {
    this.stream?.getTracks().forEach((t) => t.stop());
    this.stream = null;
    if (this.video) this.video.srcObject = null;
  }

  // ------------------------------------------------------------- scan loop

  private startLoop(): void {
    if (!(this.opts.autoCapture ?? true)) return;
    this.stopLoop();
    this.lockTicks = 0;
    this.timer = window.setInterval(() => this.tick(), TICK_MS);
  }

  private stopLoop(): void {
    if (this.timer !== null) {
      window.clearInterval(this.timer);
      this.timer = null;
    }
  }

  private tick(): void {
    if (this.state !== "scanning" && this.state !== "locking") return;
    const guide = this.guideRectInVideo();
    if (!guide) return;
    const t = this.detector.analyze(this.video, guide);
    if (t.cardPresent && t.sharp && t.steady) {
      this.lockTicks++;
      this.setState("locking", this.labels.holdSteady);
      if (this.lockTicks >= DETECT.ticksToLock) void this.capture();
    } else {
      this.lockTicks = 0;
      if (this.state === "locking") {
        this.setState("scanning", this.labels.guide);
      }
    }
  }

  // ---------------------------------------------------- capture and submit

  private async capture(): Promise<void> {
    const guide = this.guideRectInVideo();
    if (!guide) return;
    this.stopLoop();
    try {
      const blob = await captureFrame(
        this.video,
        guide,
        this.opts.maxUploadBytes ?? 1_000_000,
      );
      await this.submit(blob);
    } catch (e) {
      this.fail(e);
    }
  }

  private async submit(image: Blob): Promise<void> {
    this.setState("uploading", this.labels.processing);
    try {
      const outcome = await submitScan(this.opts.proxyUrl, image);
      if (outcome.kind === "result") {
        this.setState("done", this.labels.success);
        this.stopCamera(); // privacy: no reason to keep the camera running
        this.opts.onResult(outcome.result);
      } else {
        this.opts.onReject?.(outcome.reason);
        this.showRejectionThenResume();
      }
    } catch (e) {
      this.fail(e);
      this.showRejectionThenResume();
    }
  }

  private showRejectionThenResume(): void {
    const hasCamera = !!this.stream;
    this.setState(
      hasCamera ? "scanning" : "camera-unavailable",
      this.labels.rejected,
    );
    if (this.resumeTimer) window.clearTimeout(this.resumeTimer);
    this.resumeTimer = window.setTimeout(() => {
      if (this.state === "scanning") {
        this.setStatus(this.labels.guide);
        this.detector.reset();
        this.startLoop();
      } else if (this.state === "camera-unavailable") {
        this.setStatus(this.labels.cameraUnavailable);
      }
    }, REJECT_RESUME_MS);
  }

  private fail(e: unknown): void {
    this.opts.onError?.(e instanceof Error ? e : new Error(String(e)));
  }

  // -------------------------------------------------------------- geometry

  /** Guide rect in normalized video coordinates, or null pre-camera. */
  private guideRectInVideo() {
    if (!this.video.videoWidth) return null;
    const elW = this.root.clientWidth;
    const elH = this.root.clientHeight;
    const g = guideRectInElement(elW, elH);
    return elementRectToVideoRect(this.video, g, elW, elH);
  }

  // ------------------------------------------------------------------- DOM

  private buildDom(): void {
    this.root = document.createElement("div");
    this.root.className = "mks-root";

    this.video = document.createElement("video");
    this.video.className = "mks-video";
    this.video.playsInline = true;
    this.video.muted = true;
    this.video.setAttribute("playsinline", "");

    this.frame = document.createElement("div");
    this.frame.className = "mks-frame";

    this.status = document.createElement("div");
    this.status.className = "mks-status";

    const controls = document.createElement("div");
    controls.className = "mks-controls";

    this.shutterBtn = document.createElement("button");
    this.shutterBtn.type = "button";
    this.shutterBtn.className = "mks-btn mks-btn-capture";
    this.shutterBtn.textContent = this.labels.captureButton;
    this.shutterBtn.addEventListener("click", () => this.captureNow());

    const uploadLabel = document.createElement("label");
    uploadLabel.className = "mks-btn mks-btn-upload";
    uploadLabel.textContent = this.labels.uploadButton;
    this.uploadInput = document.createElement("input");
    this.uploadInput.type = "file";
    this.uploadInput.accept = "image/*";
    this.uploadInput.className = "mks-upload-input";
    this.uploadInput.addEventListener("change", () => {
      const file = this.uploadInput.files?.[0];
      if (file) void this.submit(file);
      this.uploadInput.value = "";
    });
    uploadLabel.appendChild(this.uploadInput);

    controls.append(this.shutterBtn, uploadLabel);
    this.root.append(this.video, this.frame, this.status, controls);
    this.container!.appendChild(this.root);
    this.layoutFrame();
    new ResizeObserver(() => this.layoutFrame()).observe(this.root);
  }

  private layoutFrame(): void {
    const g = guideRectInElement(this.root.clientWidth, this.root.clientHeight);
    Object.assign(this.frame.style, {
      left: `${g.x}px`,
      top: `${g.y}px`,
      width: `${g.w}px`,
      height: `${g.h}px`,
    });
  }

  private setState(state: State, statusText: string): void {
    this.state = state;
    this.root.dataset.state = state;
    this.setStatus(statusText);
    this.shutterBtn.disabled =
      state !== "scanning" && state !== "locking";
  }

  private setStatus(text: string): void {
    this.status.textContent = text;
  }
}

/** Guide rect in element pixel coordinates: centered card shape,
 *  sized to the container, nudged up to leave room for the controls. */
function guideRectInElement(elW: number, elH: number) {
  let w = elW * 0.86;
  let h = w / MYKAD_ASPECT;
  const maxH = elH * 0.62;
  if (h > maxH) {
    h = maxH;
    w = h * MYKAD_ASPECT;
  }
  return { x: (elW - w) / 2, y: elH * 0.42 - h / 2, w, h };
}

// ---------------------------------------------------------------------- CSS

const STYLE_ID = "mykad-scan-core-styles";

function injectStylesOnce(): void {
  if (document.getElementById(STYLE_ID)) return;
  const style = document.createElement("style");
  style.id = STYLE_ID;
  style.textContent = `
.mks-root { position: relative; width: 100%; height: 100%; min-height: 320px;
  background: #111; overflow: hidden; border-radius: 12px;
  font-family: system-ui, sans-serif; }
.mks-video { position: absolute; inset: 0; width: 100%; height: 100%;
  object-fit: cover; }
.mks-no-camera .mks-video { display: none; }
.mks-frame { position: absolute; border: 3px solid rgba(255,255,255,.85);
  border-radius: 14px; box-shadow: 0 0 0 9999px rgba(0,0,0,.45);
  transition: border-color .2s; pointer-events: none; }
.mks-root[data-state="locking"] .mks-frame { border-color: #ffc53d; }
.mks-root[data-state="uploading"] .mks-frame,
.mks-root[data-state="done"] .mks-frame { border-color: #52c41a; }
.mks-no-camera .mks-frame { border-style: dashed;
  border-color: rgba(255,255,255,.35); }
.mks-status { position: absolute; left: 0; right: 0; top: 6%;
  text-align: center; color: #fff; font-size: 15px; padding: 0 16px;
  text-shadow: 0 1px 3px rgba(0,0,0,.8); }
.mks-controls { position: absolute; left: 0; right: 0; bottom: 5%;
  display: flex; gap: 12px; justify-content: center; }
.mks-btn { border: 0; border-radius: 999px; padding: 10px 22px;
  font-size: 15px; cursor: pointer; }
.mks-btn-capture { background: #fff; color: #111; font-weight: 600; }
.mks-btn-capture:disabled { opacity: .4; cursor: default; }
.mks-no-camera .mks-btn-capture { display: none; }
.mks-btn-upload { background: rgba(255,255,255,.2); color: #fff; }
.mks-upload-input { display: none; }
`;
  document.head.appendChild(style);
}
