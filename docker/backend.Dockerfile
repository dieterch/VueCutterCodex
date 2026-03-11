FROM python:3.11-slim

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg cifs-utils curl \
    && rm -rf /var/lib/apt/lists/*

COPY ./VueCutter/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY ./VueCutter /app
COPY ./docker /app/docker

RUN mkdir -p /app/dist/static \
    && cp -r /app/vue-cutter/public/static/. /app/dist/static/

EXPOSE 5200

CMD ["/app/docker/backend-entrypoint.sh"]
