<?php

namespace App\Http\Controllers;

use Illuminate\Http\Request;
use Illuminate\Support\Facades\Http;

/**
 * Scan Proxy (SPEC.md §6): the one endpoint each consuming project adds.
 * Forwards the captured image to the internal OCR Service and returns its
 * response unchanged. The OCR Service is never exposed to the internet —
 * this proxy is the only way browsers reach it.
 *
 * Zero-retention: do not log the image or the extracted values here.
 * Laravel's temporary upload file is removed automatically after the request.
 */
class ScanMykadController extends Controller
{
    public function __invoke(Request $request)
    {
        $request->validate([
            'image' => ['required', 'file', 'mimes:jpeg,jpg,png', 'max:8192'],
        ]);

        $file = $request->file('image');

        $response = Http::timeout(30)
            ->attach('image', fopen($file->getRealPath(), 'r'), 'card.jpg')
            ->post(rtrim(config('services.mykad_ocr.url'), '/') . '/scan');

        return response()->json($response->json(), $response->status());
    }
}
