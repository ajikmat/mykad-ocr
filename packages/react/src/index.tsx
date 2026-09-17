import { useEffect, useRef } from "react";
import {
  createMykadScanner,
  type Labels,
  type MykadScanner as CoreScanner,
  type RejectReason,
  type ScanResult,
} from "mykad-scan-core";

export type { MykadFields, RejectReason, ScanResult } from "mykad-scan-core";
export { VERSION } from "mykad-scan-core";

export interface MykadScannerProps {
  /** The consuming project's Scan Proxy endpoint, e.g. "/api/scan-mykad". */
  proxyUrl: string;
  onResult: (result: ScanResult) => void;
  onReject?: (reason: RejectReason) => void;
  onError?: (error: Error) => void;
  autoCapture?: boolean;
  labels?: Partial<Labels>;
  maxUploadBytes?: number;
  className?: string;
  style?: React.CSSProperties;
}

/**
 * <MykadScanner proxyUrl="/api/scan-mykad" onResult={fill} />
 *
 * Thin wrapper: all behavior lives in mykad-scan-core. The component fills
 * its parent, so give the parent a height.
 */
export function MykadScanner(props: MykadScannerProps) {
  const el = useRef<HTMLDivElement>(null);
  // keep latest callbacks without remounting the scanner on each render
  const latest = useRef(props);
  latest.current = props;

  useEffect(() => {
    const scanner: CoreScanner = createMykadScanner({
      proxyUrl: props.proxyUrl,
      autoCapture: props.autoCapture ?? true,
      labels: latest.current.labels,
      maxUploadBytes: latest.current.maxUploadBytes,
      onResult: (r) => latest.current.onResult(r),
      onReject: (reason) => latest.current.onReject?.(reason),
      onError: (e) => latest.current.onError?.(e),
    });
    scanner.mount(el.current!);
    return () => scanner.destroy();
  }, [props.proxyUrl, props.autoCapture]);

  return (
    <div
      ref={el}
      className={props.className}
      style={{ width: "100%", height: "100%", ...props.style }}
    />
  );
}

export default MykadScanner;
