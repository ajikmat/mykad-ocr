# mykad-scan-vue

Vue 3 wrapper for [mykad-scan-core](../core/README.md) — ~80 lines; all
behavior lives in core.

```vue
<script setup>
import { MykadScanner } from "mykad-scan-vue";

function fill({ fields }) {
  form.name = fields.name ?? "";
  form.ic = fields.icNumber;
  // ... your Review-and-Correct form
}
</script>

<template>
  <div style="height: 420px">
    <MykadScanner proxy-url="/api/scan-mykad"
                  @result="fill" @reject="onReject" @error="onError" />
  </div>
</template>
```

Props: `proxyUrl` (required), `autoCapture`, `labels`, `maxUploadBytes`.
Events: `result`, `reject`, `error`. Exposed methods (via template ref):
`captureNow()`, `resume()`, `submitImage(blob)`.
