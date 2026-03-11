FROM python:3.12-slim

WORKDIR /app

# Install Node.js for frontend build
RUN apt-get update && apt-get install -y --no-install-recommends nodejs npm \
    && rm -rf /var/lib/apt/lists/*

# Python dependencies
COPY pyproject.toml .
COPY backend/ backend/
RUN pip install --no-cache-dir .

# Frontend build
COPY frontend/ frontend/
RUN cd frontend && npm install && npm run build

EXPOSE 8000

CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
