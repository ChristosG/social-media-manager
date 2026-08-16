FROM nvidia/cuda:12.4.1-runtime-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive PIP_NO_CACHE_DIR=1
RUN apt-get update && apt-get install -y --no-install-recommends \
        python3 python3-pip python3-venv git ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /opt
RUN git clone --depth 1 https://github.com/comfyanonymous/ComfyUI.git
WORKDIR /opt/ComfyUI

# Torch built for CUDA 12.4 — forward-compatible with the CUDA 13 host driver.
RUN pip3 install torch torchvision --index-url https://download.pytorch.org/whl/cu124 \
 && pip3 install -r requirements.txt
# torchaudio from the default index links against CUDA 13; pin the cu124 build to match torch.
RUN pip3 install --no-deps --force-reinstall torchaudio --index-url https://download.pytorch.org/whl/cu124

EXPOSE 8188
# Overridden by compose `command:`; sane default here.
CMD ["python3", "main.py", "--listen", "0.0.0.0", "--port", "8188"]
