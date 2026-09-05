FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt ./
RUN uv pip install --no-cache-dir -r requirements.txt
COPY omni_proxy/ ./omni_proxy/
COPY config.example.json ./config.json
EXPOSE 8081

CMD ["python", "-m", "omni_proxy", "--config", "/app/config.json"]
