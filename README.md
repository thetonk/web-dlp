# Web-dlp
![web-dlp](Images/web-dlp.png "web-dlp screenshot")
A simple web interface for [yt-dlp](https://github.com/yt-dlp/yt-dlp), with extra compatibility for [Nextcloud](https://nextcloud.com/) file system and [Nextcloud Music](https://nextcloud.com/) app.

## Features
- All video sources within the official [list](https://github.com/yt-dlp/yt-dlp/blob/master/supportedsites.md) are supported.
- Mass download videos and convert to either mp3 or mp4 format at the best quality possible.
- Transfer downloads to your local nextcloud instance and update all the required databases automatically.
- Multi-threading support.
- Easy deployment with docker.

## Configuring the docker-compose.yml file
### I. Ports
Set to your preferred port. Default port is **6030**.
### II. Environment variables
Environment variables. They are pretty self-explanatory.
- `TZ` : Sets your timezone
- `OCC_PATH`: Your path to the nextcloud occ script
- `NC_USER` : Your nextcloud user
- `NC_MUSIC_DIRECTORY`: Your nextcloud music directory path, as shown to your nextcloud instance

### III. Volumes
This project requires 2 volumes;
- Volume for your nextcloud music folder. This time use the ENTIRE path, not the one shown on your nextcloud instance
```yml
- /path/to/your/nextcloud/music/folder:/ytdlpFolder/Library
```
- Volume for configuration and all necessary files. They're needed for transferring to nextcloud. See the [next](#optional-transferring-to-nextcloud) section for more.
```yml
- /dockerData/ytdlpweb/config:/config
```

## (Optional) Transferring to Nextcloud
This is the kinda tricky part, but rewarding. It may get automated on future releases. The steps are as such:
1. Go to the config folder and create a [FIFO file](https://man7.org/linux/man-pages/man7/fifo.7.html) aka pipe, named _mypipe_ (use name AS IS). Provide root priviledges if needed. This pipe will be the communication between the container and the host system.

```shell
# cd /dockerData/ytdlpweb/config
# mkfifo mypipe
```
2. Create a script that forever reads the pipe and make it executable. For extra security, create it as root.
```sh
$ nano pipescript.sh
#!/bin/sh
while true; do eval "$(cat /dockerData/ytdlpweb/config/mypipe)"; done
$ chmod +x pipescript.sh
```
3. Add the script to root's crontab so it starts on startup
```sh
$ sudo crontab -e
@reboot /dockerData/ytdlpweb/config/pipescript.sh
```
Aaaaand that's it!

## Installation
1. Clone this repository

```sh
$ git clone https://github.com/thetonk/web-dlp.git
```
2. Build docker image. Provide root priviledges if required

```sh
$ docker build -t ytdlpweb .
```
3. Deploy the previously created image using the properly configured _docker-compose.yml_ file

```sh
$ docker compose up
```