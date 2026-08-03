# Scan Proxy — Laravel reference

The one endpoint each consuming project adds to its own backend
(SPEC.md §6). Copy `ScanMykadController.php` into `app/Http/Controllers/`.

## 1. Config

`config/services.php`:

```php
'mykad_ocr' => [
    'url' => env('MYKAD_OCR_URL', 'http://127.0.0.1:8000'),
],
```

`.env`:

```
MYKAD_OCR_URL=http://127.0.0.1:8000
```

Point it at wherever the OCR Service container runs. Same server →
`127.0.0.1`; another machine → its internal IP (and firewall the port so
only the app servers can reach it).

## 2. Route

Projects where the user is logged in:

```php
Route::post('/api/scan-mykad', ScanMykadController::class)
    ->middleware(['auth']);
```

The anonymous-user project — no session to lean on, so throttle instead:

```php
Route::post('/api/scan-mykad', ScanMykadController::class)
    ->middleware(['throttle:10,1']);   // 10 scans/minute per IP
```

Worst-case abuse of the anonymous route is wasted CPU on the OCR box —
no data is at risk — and the throttle contains it.

## 3. Frontend

Point the Capture Library at the route and you're done:

```js
createMykadScanner({ proxyUrl: "/api/scan-mykad", onResult: ... })
```

Same-origin, so there is no CORS configuration anywhere.

## Rules that keep this PDPA-clean

- Never log the uploaded image or the extracted field values.
- Don't store the image; Laravel's tmp upload is auto-removed.
- Never expose `MYKAD_OCR_URL` to the browser or move this call
  client-side — the browser must only ever know `/api/scan-mykad`.
