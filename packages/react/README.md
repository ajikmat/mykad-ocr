# mykad-scan-react

React wrapper for [mykad-scan-core](../core/README.md) — ~60 lines; all
behavior lives in core.

```tsx
import { MykadScanner } from "mykad-scan-react";

function SignupCardScan({ onFields }) {
  return (
    <div style={{ height: 420 }}>
      <MykadScanner
        proxyUrl="/api/scan-mykad"
        onResult={({ fields }) => onFields(fields)}
        onReject={(reason) => {}}
        onError={(err) => {}}
      />
    </div>
  );
}
```

Props: `proxyUrl` (required), `onResult` (required), `onReject`, `onError`,
`autoCapture`, `labels`, `maxUploadBytes`, `className`, `style`.
