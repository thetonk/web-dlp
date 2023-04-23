import re

class Format():
    def __init__(self, id, url,ext,res=None, filesize=None, v_ext=None, a_ext=None, acodec = None, vcodec = None, container = None):
        self.ID = id
        self.URL = url
        self.EXTENSION = ext
        self.RESOLUTION = res
        self.FILESIZE = filesize
        self.video_ext = v_ext
        self.audio_ext = a_ext
        self.acodec = acodec
        self.vcodec = vcodec
        self.container = container
    
    def getResolution(self):
        if self.RESOLUTION is not None:
            sizes = re.findall("\d+",self.RESOLUTION)
            print(sizes)
            if len(sizes) >= 2:
                width = sizes[0]  #sugar, i know
                height = sizes[1]
                return width, height
        else:
            return None

    def stringify(self) -> str:
        res = self.RESOLUTION
        aext = self.audio_ext
        vext = self.video_ext
        acodec = self.acodec
        vcodec = self.vcodec
        container = self.container
        filesize = self.FILESIZE
        if filesize is None:
            filesize = '-'
        if res is None:
            res = '-'
        if aext is None:
            aext = '-'
        if vext is None:
            vext = '-'
        if acodec is None:
            acodec = '-'
        if vcodec is None:
            vcodec = '-'
        if container is None:
            container = '-'
        return ("{:10} "*10).format(self.ID,self.URL,self.EXTENSION, res, filesize, vext, aext, acodec,vcodec,container)

class Video():
    def __init__(self, title, URL, resolutions, thumbnail) -> None:
        self.TITLE = title
        self.URL = URL
        self.RESOLUTIONS = resolutions
        self.THUMBNAIL = thumbnail
    