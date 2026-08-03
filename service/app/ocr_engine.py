"""RapidOCR (ONNX Runtime) wrapper: loads the model once, returns positioned
text boxes. Replaces PaddleOCR — same contract: in-memory BGR image array in,
{text, conf, y, x0, x1} boxes out, top-to-bottom. No file paths, no temp
files (Zero-retention).
"""
_engine = None


def get_engine():
    global _engine
    if _engine is None:
        _engine = _Engine()
    return _engine


class _Engine:
    def __init__(self):
        from rapidocr_onnxruntime import RapidOCR
        self._ocr = RapidOCR()

    def run(self, img):
        """BGR image array → list of {text, conf, y, x0, x1}, top-to-bottom."""
        result, _elapse = self._ocr(img)
        boxes = []
        for poly, text, score in (result or []):
            xs = [float(p[0]) for p in poly]
            ys = [float(p[1]) for p in poly]
            boxes.append({"text": str(text), "conf": float(score),
                          "y": sum(ys) / len(ys),
                          "x0": min(xs), "x1": max(xs)})
        boxes.sort(key=lambda b: b["y"])
        return boxes