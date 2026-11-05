FROM python:3.12-slim

# Install system dependencies, FFmpeg & Node.js for solving YouTube JS challenges
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    curl \
    nodejs \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY . .

# Create storage directories
RUN mkdir -p downloads uploads

ENV PORT=5500
EXPOSE 5500

CMD ["python", "app.py"]

