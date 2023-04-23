FROM python:3.9-slim-bullseye
WORKDIR /ytdlpFolder
LABEL Maintainer="Spyros, the ultimate spaghett creator"
LABEL Version="1.4.1"
COPY . .
ENV DEBIAN_FRONTEND=noninteractive
EXPOSE 6030
RUN mkdir web/downloads
RUN apt update && apt install -y ffmpeg && rm -rf /var/lib/apt/lists/*
RUN pip3 install -r requirements.txt
CMD ["python3", "main.py"]