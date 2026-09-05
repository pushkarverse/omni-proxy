FROM python:3.12-slim

WORKDIR /app

# Copy project files and metadata
COPY pyproject.toml README.md ./
COPY omni_apis/ ./omni_apis/
COPY config.example.json ./config.json

# Install uv and use it to install the application
RUN pip install --no-cache-dir uv && \
    uv pip install --system --no-cache .

EXPOSE 8081

# Run the FastAPI server using Uvicorn
CMD ["uvicorn", "omni_apis.api:app", "--host", "0.0.0.0", "--port", "8081"]
