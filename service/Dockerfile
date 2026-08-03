FROM python:3.11-slim
WORKDIR /srv
# OpenCV/ONNX runtime libs
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 libgomp1 \
    && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
# Warm-up: verifies the bundled OCR models load (no network needed).
RUN python -c "from rapidocr_onnxruntime import RapidOCR; RapidOCR()"
COPY app ./app
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]