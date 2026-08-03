/** Talk to the consuming project's Scan Proxy (never the OCR Service
 *  directly — the proxy is the only URL this library knows). */

import type { RejectReason, ScanResult } from "./types.js";

export type ScanOutcome =
  | { kind: "result"; result: ScanResult }
  | { kind: "reject"; reason: RejectReason };

export async function submitScan(
  proxyUrl: string,
  image: Blob,
): Promise<ScanOutcome> {
  const form = new FormData();
  form.append("image", image, "card.jpg");
  const res = await fetch(proxyUrl, { method: "POST", body: form });

  let body: unknown = null;
  try {
    body = await res.json();
  } catch {
    /* non-JSON error page */
  }

  if (body && typeof body === "object" && "ok" in body) {
    const b = body as { ok: boolean; reason?: RejectReason } & ScanResult;
    if (b.ok) return { kind: "result", result: { fields: b.fields, confidence: b.confidence ?? {} } };
    if (b.reason === "NO_IC_FOUND" || b.reason === "IMAGE_UNREADABLE" ||
        b.reason === "IMAGE_TOO_LARGE") {
      return { kind: "reject", reason: b.reason };
    }
  }
  throw new Error(`scan request failed (HTTP ${res.status})`);
}
