/** The field contract returned by the OCR Service (SPEC.md §3). */
export interface MykadAddress {
  /** Raw printed address lines, top to bottom. */
  lines: string[];
  postcode: string | null;
  city: string | null;
  state: string | null;
}

export interface MykadFields {
  /** Romanized name, wrapped lines joined; Chinese-script line dropped. */
  name: string | null;
  /** Validated 12-digit IC number, formatted XXXXXX-XX-XXXX. */
  icNumber: string;
  /** Derived from the last IC digit — never OCR'd. */
  gender: "M" | "F" | null;
  /** "ISLAM" when printed on the card, otherwise null. Never guessed. */
  religion: "ISLAM" | null;
  address: MykadAddress;
}

export interface ScanResult {
  fields: MykadFields;
  confidence: {
    icNumber?: number;
    name?: number;
    address?: number;
  };
}

export type RejectReason =
  | "NO_IC_FOUND"
  | "IMAGE_UNREADABLE"
  | "IMAGE_TOO_LARGE";

export interface Labels {
  guide: string;
  holdSteady: string;
  processing: string;
  rejected: string;
  /** Shown when an auto-capture is discarded as motion-blurred. */
  blurry: string;
  cameraUnavailable: string;
  captureButton: string;
  uploadButton: string;
  success: string;
}

export interface MykadScannerOptions {
  /** The consuming project's Scan Proxy endpoint, e.g. "/api/scan-mykad". */
  proxyUrl: string;
  onResult: (result: ScanResult) => void;
  onReject?: (reason: RejectReason) => void;
  onError?: (error: Error) => void;
  /** Auto-capture when a card is framed and steady. Default true. */
  autoCapture?: boolean;
  /** Override any UI text (e.g. Malay strings). */
  labels?: Partial<Labels>;
  /** Target upload size after JPEG compression. Default 1 MB. */
  maxUploadBytes?: number;
}

export interface MykadScanner {
  /** Render the scanner UI into a container and start the camera. */
  mount(container: HTMLElement): void;
  /** Trigger a capture immediately (the manual shutter). */
  captureNow(): void;
  /** Submit an image the host obtained itself (file picker, drag-drop…). */
  submitImage(image: Blob): void;
  /** Restart camera + scanning after a result stopped it. */
  resume(): void;
  /** Stop the camera and remove all DOM. */
  destroy(): void;
}
