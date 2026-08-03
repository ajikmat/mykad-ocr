FROM python:3.11-slim

WORKDIR /srv

# OpenCV/Paddle runtime libs
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Bake the OCR models into the image so the container needs no internet
# access at runtime (the server may not have outbound connectivity).
RUN python -c "from paddleocr import PaddleOCR; PaddleOCR(lang='en', \
use_doc_orientation_classify=False, use_doc_unwarping=False, \
use_textline_orientation=True)" || \
    python -c "from paddleocr import PaddleOCR; PaddleOCR(lang='en', use_angle_cls=True, show_log=False)"

COPY app ./app

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
