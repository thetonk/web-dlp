from flask import Flask, after_this_request, send_file, render_template, request
from werkzeug.middleware.proxy_fix import ProxyFix
from flask_socketio import SocketIO
from yt_dlp import YoutubeDL
from yt_dlp.utils import DownloadError
from multimedia_processor import Format, Video
from functools import partial #this is the first time im using this, seems promising!
from celery import Celery
import json, os, shutil, subprocess, re, logging

REDIS_PASSWORD = os.getenv("REDIS_PASSWORD","redis-password")
REDIS_HOST = os.getenv("REDIS_HOST", "127.0.0.1")
REDIS_PORT = os.getenv("REDIS_PORT", 6379)
app = Flask(__name__, static_url_path="", static_folder="web", template_folder="templates")
#this is to fix the client ip addresses on flask logs behind reverse proxy, to use the XFF header instead
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1,x_host=1)
app.logger.setLevel(logging.DEBUG)
socketio = SocketIO(app)
app.config['SECRET_KEY'] = os.getenv("FLASK_SECRET_KEY","my-secret-key")
#celery config
app.config['CELERY_BROKER_URL'] = os.getenv("CELERY_BROKER_URL",f'redis://:{REDIS_PASSWORD}@{REDIS_HOST}:{REDIS_PORT}/0')
app.config['CELERY_RESULT_BACKEND'] = os.getenv("CELERY_RESULT_BACKEND",f'redis://:{REDIS_PASSWORD}@{REDIS_HOST}:{REDIS_PORT}/0')
celery = Celery(app.name, broker=app.config['CELERY_BROKER_URL'])
celery.conf.update(app.config)

def convertToMP4(input: str, output: str):
    subprocess.call(f"ffmpeg -i \"{input}\" -map 0 -c copy \"{output}\"", shell=True)

def emptyOutputFolder():
    for file in os.listdir("web/outputs"): #cleanup outputs folder
        os.remove("web/outputs/"+file)

def progressHook(task, downloadStatus):
    if downloadStatus["status"] == "downloading":
        percent_color = downloadStatus["_percent_str"]
        percentage = re.findall(r"\d+\.\d+%", percent_color)[0] #clear coloring
        task.update_state(state="PROGRESS", meta={"percent":percentage})

@celery.task(bind=True)
def videoDownload(self, links : list, checked : bool, transfertoNC : bool, video : bool):
    if video:
        ydl_options = {
            "outtmpl" : "web/outputs/%(title)s.%(ext)s",
        }

    else:
        ydl_options = {
            'writethumbnail': True,
            'format': 'bestaudio/best',
            'outtmpl': 'web/outputs/%(title)s.%(ext)s',
            'postprocessors': [
                {
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    "preferredquality":"192"
                },
                {'key': 'EmbedThumbnail'},
                {'key': 'FFmpegMetadata'},
            ]
        }
    self.update_state(state="PROGRESS", meta={"info": "started downloading!"})
    try:
        with YoutubeDL(ydl_options) as ydl:
            for link in links:
                ydl.download(link)
                self.update_state(state="PROGRESS", meta={"info":f"{link} downloaded successfully!"})
        if video:
            for file in os.listdir("web/outputs"):
                if not file.endswith(".mp4"):
                    #start conversion with ffmpeg
                    path = f"web/outputs/{file}"
                    app.logger.info(f"path: {path}")
                    convertToMP4(path, f"web/outputs/{os.path.splitext(file)[0]}.mp4")
                    os.remove(path)
                    self.update_state(state="PROGRESS", meta={"info":f"{file} converted to mp4!"})

        shutil.make_archive("web/downloads/out", "zip", "web/outputs")

        if transfertoNC and not video:
            subprocess.call("scripts/finalizer.sh", shell=True)
            self.update_state(state="PROGRESS", meta={"info": "Files transferred to nextcloud!"})
        return {"status":"completed"}
    except Exception as e:
        return {"error": str(e)}
    finally:
        emptyOutputFolder()

@celery.task(bind=True)
def resolutionDownload(self, url, height):
    print(f"Downloading resolution height {height} from URL {url}")
    partial_progressHook = partial(progressHook,self)
    ydl_opts = {"format":f"bestvideo[height={height}]+bestaudio", "outtmpl": "web/outputs/out.%(ext)s", "progress_hooks":[partial_progressHook]}
    self.update_state(state="PROGRESS", meta={"info":"started download!"})
    try:
        with YoutubeDL(ydl_opts) as ydl:
            ydl.download(url)
            self.update_state(state="PROGRESS",meta={"info": "download complete"})
        file = os.listdir("web/outputs")[0]
        path = f"web/outputs/{file}"
        if not file.endswith(".mp4"):
            convertToMP4(path, "web/downloads/out.mp4")
            self.update_state(state="PROGRESS", meta={"info":"convert finished"})
        else:
            #in order to move and replace the file if already exists, absolute path must be provided.
            workingDir = os.getcwd()
            shutil.move(os.path.join(workingDir,path), os.path.join(workingDir,"web/downloads"))
        return {"status": "completed"}

    except DownloadError:
        try:
            print("Downloading fallback video and audio combined")
            ydl_opts = {"format":f"best[height={height}]", "outtmpl": "web/outputs/out.%(ext)s", "progress_hooks":[partial_progressHook]}
            with YoutubeDL(ydl_opts) as ydl:
                ydl.download(url)
                self.update_state(state="PROGRESS",meta={"info": "download complete"})
            file = os.listdir("web/outputs")[0]
            path = f"web/outputs/{file}"
            if not file.endswith(".mp4"):
                convertToMP4(path, "web/downloads/out.mp4")
                self.update_state(state="PROGRESS", meta={"info":"convert finished"})
            else:
                #in order to move and replace the file if already exists, absolute path must be provided.
                workingDir = os.getcwd()
                shutil.move(os.path.join(workingDir,path), os.path.join(workingDir,"web/downloads"))
            return {"status": "completed"}
        except Exception as e:
            return {"error": f"{e}"}
    except Exception as e:
        return {"error": f"{e}"}
    finally:
        emptyOutputFolder()

@app.route("/")
def home():
    app.logger.info(request.headers)
    return send_file("web/index.html")

@app.route("/success")
def success():
    zip = request.args.get("zip", default=1,type=int)
    title = request.args.get("title",type=str)
    return render_template("success.html", zip = zip, filename=title)

@app.route("/error")
def error():
    return send_file("web/failure.html")

@app.route("/download")
def download():
    #filename = request.args.get("file",type=str).strip()
    if request.args.get("zip", default=1,type=int) == 1:
        @after_this_request
        def removefiles(response):
            os.remove("web/downloads/out.zip")
            app.logger.info(response)
            return response
        return send_file("web/downloads/out.zip", as_attachment=True)
    else:
        @after_this_request
        def removefiles(response):
            os.remove("web/downloads/out.mp4")
            app.logger.info(response)
            return response
        return send_file(f"web/downloads/out.mp4", as_attachment=True)

@app.route("/select-resolution", methods=["GET","POST"])
def res():
    links = request.form['links'].split()
    app.logger.info(f"{links[0]}")
    resolutions = []
    title = None
    thumbnail = None
    ydl_options = {"listformats": True, }
    with YoutubeDL(ydl_options) as ydl:
        vinfo = ydl.extract_info(links[0])
    if 'thumbnail' in vinfo:
        thumbnail = vinfo['thumbnail']
    if 'title' in vinfo:
        title = vinfo['title']
    if 'formats' in vinfo:
        app.logger.info("FORMATS FOUND!")
        formats = vinfo["formats"]
        for format in formats:
            id = format["format_id"]
            url = format["url"]
            ext = None
            res = None
            filesize = None
            video_ext = None
            audio_ext = None
            acodec,vcodec,container = None, None, None
            if 'ext' in format:
                ext = format["ext"]
            if 'video_ext' in format:
                video_ext = format["video_ext"]
            if 'audio_ext' in format:
                audio_ext = format["audio_ext"]
            if 'resolution' in format:
                res = format["resolution"]
            if 'acodec' in format:
                acodec = format["acodec"] 
            if 'vcodec' in format:
                vcodec = format["vcodec"]
            if 'container' in format:
                container = format["container"]
            if 'filesize_approx' in format:
                filesize = format["filesize_approx"]
            f = Format(id, url,ext,res,filesize,video_ext,audio_ext, acodec, vcodec,container)
            app.logger.info(f.stringify())
            k = f.getResolution() #width x height
            if k not in resolutions and k is not None:
                if int(k[1]) >= 144: #clear storyline thumbnails
                    resolutions.append(k)
            #print(k)
    elif 'entries' in vinfo:
        app.logger.info("ENTRY FOUND!")
        entry = vinfo['entries'][0]
        id = entry['id']
        url = entry["url"]
        resolution = entry['resolution']
        size= '-'
        ext = entry['ext']
        if 'thumbnail' in entry:
            thumbnail  = entry['thumbnail']
        fo = Format(id,url,ext,resolution,size)
        app.logger.info(fo.stringify())
        k = fo.getResolution() #width x height
        if k not in resolutions and k is not None:
            if int(k[1]) >= 144:
                resolutions.append(k)
        #print(k)
    video = Video(title, links[0],resolutions, thumbnail)
    app.logger.info(f"TITLE: {video.TITLE}, URL: {video.URL}, RESOLUTIONS: {video.RESOLUTIONS}, THUMBNAIL: {video.THUMBNAIL}")
    return render_template("resolutions.html",video=video)

@socketio.on("start-process")
def fun(jsonobj):
    app.logger.info(f"{jsonobj} of type {type(jsonobj)}")
    links = jsonobj["links"].split()
    downloadTask = videoDownload.apply_async(args=[links, jsonobj["check"], jsonobj["checkNC"], jsonobj["containVideo"]])
    while not downloadTask.ready():
        print("Download status ", downloadTask.status)
        #return control to flask server, prevent freezing
        socketio.sleep(1)
    if downloadTask.info.get("error") is None:
        status = downloadTask.info.get("status")
        app.logger.info(f"[{status}] ")
        socketio.emit('processing-finished', json.dumps({'data': 'finished processing!'}))
    else:
        print(downloadTask.info.get("error"))
        socketio.emit("processing-failed")

@socketio.on("start-res-dl")
def dl(jsonobj):
    height = int(jsonobj['h'])
    url = jsonobj['url']
    downloadTask = resolutionDownload.apply_async(args=[url, height])
    while not downloadTask.ready():
        print("Download status", downloadTask.status)
        if downloadTask.info is not None:
            if downloadTask.info.get("percent") is not None:
                percent = downloadTask.info.get("percent")
                socketio.emit("progress-update", percent)
        #return control to flask server, prevent freezing
        socketio.sleep(1)
    if downloadTask.info.get("error") is None:
        socketio.emit('processing-finished', json.dumps({'data': 'finished processing!'}))
    else:
        print(downloadTask.info.get("error"))
        socketio.emit("processing-failed")

#app.run("0.0.0.0", port=5000)
if not os.path.isdir("web/outputs"):
    app.logger.info("creating outputs directory")
    os.mkdir("web/outputs")
if not os.path.isdir("web/downloads"):
    app.logger.info("creating downloads directory")
    os.mkdir("web/downloads")

if __name__ == "__main__":
    socketio.run(app,"0.0.0.0", 6030, log_output=True, allow_unsafe_werkzeug=True)
