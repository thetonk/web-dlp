from flask import Flask, after_this_request, send_file
from flask_socketio import SocketIO
from yt_dlp import YoutubeDL
from yt_dlp.utils import DownloadError
import threading, json, os, shutil, subprocess

app = Flask(__name__, static_url_path="", static_folder="web")
socketio = SocketIO(app)

def youtubeDownload(links : list, checked : bool, transfertoNC : bool, video : bool):
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

    with YoutubeDL(ydl_options) as ydl:
        if checked:
            print("MULTITHREADING!")
            threads = []
            for link in links:
                thread = threading.Thread(target=ydl.download, args=(link,))
                thread.start()
                threads.append(thread)
            for thread in threads:
                thread.join()
        else:
            ydl.download(links)
        
        if video:
            for file in os.listdir("web/outputs"):
                if not file.endswith(".mp4"):
                    #start conversion with ffmpeg
                    path = f"web/outputs/{file}"
                    print(path)
                    subprocess.call(f"ffmpeg -i \"{path}\" -map 0 -c copy \"web/outputs/{os.path.splitext(file)[0]}.mp4\" ", shell=True)
                    os.remove(path)
    
    shutil.make_archive("web/downloads/out", "zip", "web/outputs")

    if transfertoNC and not video:
        os.system('scripts/finalizer.sh ')

    for file in os.listdir("web/outputs"): #cleanup outputs folder
        os.remove("web/outputs/"+file)
    
@app.route("/")
def home():
    return send_file("web/index.html")

@app.route("/success")
def success():
    return send_file("web/success.html")

@app.route("/error")
def error():
    return send_file("web/failure.html")

@app.route("/download")
def download():
    @after_this_request
    def removefiles(response):
        os.remove("web/downloads/out.zip")
        print(response)
        return response
    return send_file("web/downloads/out.zip", as_attachment=True)

#@app.route("/upload", methods=["POST"])
#def upload():
#    print(request.form.get("links").split())
#    links = request.form.get("links").split()
#    print("returning!")
#    thread = threading.Thread(target=func)
#    thread.start()
#    thread.join()
#    return "done"

@socketio.on("start-process")
def fun(jsonobj):
    print(jsonobj)
    print(type(jsonobj))
    try:
        youtubeDownload(jsonobj["links"].split(), jsonobj["check"], jsonobj["checkNC"], jsonobj["containVideo"])
        socketio.emit('processing-finished', json.dumps({'data': 'finished processing!'}))
    
    except DownloadError as d:
        print(d)
        socketio.emit("processing-failed")

#app.run("0.0.0.0", port=5000)
socketio.run(app, "0.0.0.0", 6030)