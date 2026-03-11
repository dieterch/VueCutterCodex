# syntax=docker/dockerfile:1
#FROM python:3.11.8
FROM python:3.11.8-slim
WORKDIR /code
RUN apt-get update && apt-get -y install curl cifs-utils ffmpeg mc htop
RUN curl -fsSL https://deb.nodesource.com/setup_21.x | bash - && apt-get install -y nodejs
RUN apt-get clean autoclean && apt-get autoremove --yes && rm -rf /var/lib/{apt,dpkg,cache,log}/
COPY ./VueCutter .
RUN pip install -r requirements.txt
EXPOSE 5200
COPY ./VueCutter .
CMD ["bash","start.sh"]
