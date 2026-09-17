import {
  defineComponent,
  h,
  onBeforeUnmount,
  onMounted,
  ref,
  type PropType,
} from "vue";
import {
  createMykadScanner,
  type Labels,
  type MykadScanner as CoreScanner,
  type RejectReason,
  type ScanResult,
} from "mykad-scan-core";

export type { MykadFields, RejectReason, ScanResult } from "mykad-scan-core";
export { VERSION } from "mykad-scan-core";

/**
 * <MykadScanner proxy-url="/api/scan-mykad" @result="onResult" />
 *
 * Thin wrapper: all behavior lives in mykad-scan-core. The component fills
 * its parent, so give the parent a height.
 */
export const MykadScanner = defineComponent({
  name: "MykadScanner",
  props: {
    proxyUrl: { type: String, required: true },
    autoCapture: { type: Boolean, default: true },
    labels: { type: Object as PropType<Partial<Labels>>, default: undefined },
    maxUploadBytes: { type: Number, default: undefined },
  },
  emits: {
    result: (_r: ScanResult) => true,
    reject: (_reason: RejectReason) => true,
    error: (_e: Error) => true,
  },
  setup(props, { emit, expose }) {
    const el = ref<HTMLElement>();
    let scanner: CoreScanner | null = null;

    onMounted(() => {
      scanner = createMykadScanner({
        proxyUrl: props.proxyUrl,
        autoCapture: props.autoCapture,
        labels: props.labels,
        maxUploadBytes: props.maxUploadBytes,
        onResult: (r) => emit("result", r),
        onReject: (reason) => emit("reject", reason),
        onError: (e) => emit("error", e),
      });
      scanner.mount(el.value!);
    });

    onBeforeUnmount(() => {
      scanner?.destroy();
      scanner = null;
    });

    expose({
      captureNow: () => scanner?.captureNow(),
      resume: () => scanner?.resume(),
      submitImage: (image: Blob) => scanner?.submitImage(image),
    });

    return () =>
      h("div", { ref: el, style: { width: "100%", height: "100%" } });
  },
});

export default MykadScanner;
