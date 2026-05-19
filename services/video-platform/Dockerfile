FROM python:3.12-slim

WORKDIR /app

COPY services/video-platform/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY services/video-platform/app ./app

ENV PYTHONUNBUFFERED=1

CMD ["uvicorn", "app.identity_service:app", "--host", "0.0.0.0", "--port", "8000"]
