FROM python:3.12-slim

ENV PIP_NO_CACHE_DIR=1
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY flux_api.py .

EXPOSE 8000
CMD ["uvicorn", "flux_api:app", "--host", "0.0.0.0", "--port", "8000"]
