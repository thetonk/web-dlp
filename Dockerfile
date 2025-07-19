FROM python:3.13-alpine
WORKDIR /ytdlpFolder
LABEL Maintainer="Spyros, the ultimate spaghett creator"
LABEL Version="1.4.3"
COPY . .
EXPOSE 6030
RUN mkdir -p web/downloads
RUN apk add --no-cache ffmpeg
RUN pip3 install --no-cache-dir -r requirements.txt
RUN chmod +x scripts/finalizer.sh
CMD ["python3", "main.py"]
