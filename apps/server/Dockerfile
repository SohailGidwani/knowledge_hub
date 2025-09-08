## Docker image for the API service
# - Installs Python dependencies
# - Copies application code into /app
# - Starts the Flask app with Gunicorn on port 8000

FROM python:3.11-slim

# System deps (optional: for building wheels faster)
RUN apt-get update && apt-get install -y build-essential && rm -rf /var/lib/apt/lists/*

WORKDIR /app  # All paths below are relative to /app

# Install Python dependencies first to leverage Docker layer caching
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY . /app 

ENV FLASK_APP=app:create_app 
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Start the server (listens on 0.0.0.0:8000)
CMD ["gunicorn", "-b", "0.0.0.0:8000", "app:create_app()"]
