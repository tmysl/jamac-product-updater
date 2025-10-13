FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy project files
COPY pyproject.toml ./
COPY uv.lock* ./

# Install uv
RUN pip install uv

# Install Python dependencies
RUN uv sync --frozen

# Copy application files
COPY . .

# Create directory for uploads (optional, can use temp)
RUN mkdir -p /tmp/uploads

# Expose port
EXPOSE 5001

# Set environment variables
ENV FLASK_APP=app.py
ENV PYTHONUNBUFFERED=1

# Run the application with uv
CMD ["uv", "run", "python", "app.py"]
