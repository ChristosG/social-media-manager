FROM python:3.12-slim

# Create non-root user
RUN groupadd -r emailsvc && useradd -r -g emailsvc -d /app -s /sbin/nologin emailsvc

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN chown -R emailsvc:emailsvc /app

USER emailsvc

EXPOSE 8025

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8025"]
