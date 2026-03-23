FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Create data directory for SQLite
RUN mkdir -p /data

# Expose port
EXPOSE 5000

# Run with gunicorn
ENV PORT=5000
CMD ["gunicorn", "app:app", "--bind", "0.0.0.0:5000"]
