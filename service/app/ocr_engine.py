"""PaddleOCR wrapper: loads the model once, returns positioned text boxes.

Supports both the PaddleOCR 3.x (predict) and 2.x (ocr) APIs. Input is an
in-memory image array — no file paths, no temp files (Zero-retention).
"""

_engine = None


def get_engine():
    global _engine
    if _engine is None:
        _engine = _Engine()
    return _engine


class _Engine:
    def __init__(self):
        from paddleocr import PaddleOCR
        try:  # PaddleOCR 3.x
            self._ocr = PaddleOCR(
                lang="en",
                use_doc_orientation_classify=False,
                use_doc_unwarping=False,
                use_textline_orientation=True,
            )
        except TypeError:  # PaddleOCR 2.x
            self._ocr = PaddleOCR(lang="en", use_angle_cls=True,
                                  show_log=False)

    def run(self, img):
        """BGR image array → list of {text, conf, y, x0, x1}, top-to-bottom."""
        boxes = []
        if hasattr(self._ocr, "predict"):  # 3.x
            for res in self._ocr.predict(img):
                d = self._unwrap(res)
                texts = d.get("rec_texts") or []
                scores = d.get("rec_scores") or [1.0] * len(texts)
                polys = d.get("rec_polys")
                if polys is None or len(polys) != len(texts):
                    polys = d.get("dt_polys")
                if polys is None or len(polys) != len(texts):
                    polys = [None] * len(texts)
                for i, (text, score, poly) in enumerate(
                        zip(texts, scores, polys)):
                    boxes.append(self._box(text, score, poly, i))
        else:  # 2.x
            result = self._ocr.ocr(img, cls=True)
            for line in (result[0] or []):
                poly, (text, score) = line
                boxes.append(self._box(text, score, poly, len(boxes)))
        boxes.sort(key=lambda b: b["y"])
        return boxes

    @staticmethod
    def _unwrap(res):
        if isinstance(res, dict):
            return res
        j = getattr(res, "json", None)
        if isinstance(j, dict):
            return j.get("res", j)
        raise TypeError("unrecognized PaddleOCR result object")

    @staticmethod
    def _box(text, score, poly, index):
        if poly is not None:
            ys = [float(p[1]) for p in poly]
            xs = [float(p[0]) for p in poly]
            return {"text": str(text), "conf": float(score),
                    "y": sum(ys) / len(ys), "x0": min(xs), "x1": max(xs)}
        return {"text": str(text), "conf": float(score),
                "y": float(index), "x0": 0.0, "x1": 0.0}
