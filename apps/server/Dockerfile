FROM python:3.11-slim


RUN apt-get update \
&& apt-get install -y --no-install-recommends \
tesseract-ocr \
libtesseract-dev \
&& rm -rf /var/lib/apt/lists/*


WORKDIR /app
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY . /app


ENV FLASK_APP=app:create_app
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1


CMD ["gunicorn", "-b", "0.0.0.0:8000", "app:create_app()"]