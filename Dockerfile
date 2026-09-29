FROM python:3.10-slim

WORKDIR /code

# System libs: OpenCV runtime (libgl1, libglib2.0-0) + curl (fetch CV models at build time)
RUN apt-get update && apt-get install -y --no-install-recommends \
        libgl1 libglib2.0-0 curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /code/requirements.txt
# Upgrade pip first (the base image's older pip mis-handles some newer wheels and
# falls back to source builds that fail), then install the Python deps. No torch:
# the fine-tuned Flan-T5 gap model is not enabled in this deploy, and the rest of
# the stack (proctoring CV uses onnxruntime) needs no PyTorch.
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir --upgrade -r /code/requirements.txt

# Bake the local CV models into the image so runtime needs no network:
#   YuNet (face detect, ~0.2MB) · SFace (face recognition, ~37MB) · YOLOX-Nano (phone, ~3.5MB)
# Own layer (before COPY .) so code changes don't re-download them.
RUN mkdir -p /code/models && \
    curl -fsSL -o /code/models/face_detection_yunet_2023mar.onnx \
        https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx && \
    curl -fsSL -o /code/models/face_recognition_sface_2021dec.onnx \
        https://github.com/opencv/opencv_zoo/raw/main/models/face_recognition_sface/face_recognition_sface_2021dec.onnx && \
    curl -fsSL -o /code/models/yolox_nano.onnx \
        https://github.com/Megvii-BaseDetection/YOLOX/releases/download/0.1.1rc0/yolox_nano.onnx

COPY . /code

EXPOSE 7860

CMD ["uvicorn", "app_full:app", "--host", "0.0.0.0", "--port", "7860"]
