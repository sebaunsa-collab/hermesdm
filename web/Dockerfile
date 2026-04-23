FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy app
COPY server.py .
COPY static/ static/

# Environment defaults
ENV HERMESDM_STATE_DIR=/data/campaigns
ENV HOST=0.0.0.0
ENV PORT=8080

EXPOSE 8080

CMD ["python", "server.py"]
