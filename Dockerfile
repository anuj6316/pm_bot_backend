FROM python:3.12-slim

RUN apt-get update && apt-get install -y \
    redis-server supervisor curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY . .

RUN pip install -r requirements.txt && \
    pip install daphne supervisor

RUN chmod -R 777 /app /tmp

EXPOSE 7860

CMD ["supervisord", "-c", "/app/supervisord.conf"]
