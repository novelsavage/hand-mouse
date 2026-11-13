"""Loopback-only HTML exhibition server. Photos remain outside the repository."""
import argparse
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
import mimetypes
from pathlib import Path
import re
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parent


def image_files(folder):
    if folder is None:
        return []
    priority = {'.png':0,'.jpg':1,'.jpeg':1,'.webp':2,'.gif':3,'.bmp':4}
    selected = {}
    for path in Path(folder).iterdir():
        if path.is_file() and path.suffix.lower() in priority:
            key = path.stem.casefold()
            if key not in selected or priority[path.suffix.lower()] < priority[selected[key].suffix.lower()]:
                selected[key] = path
    return sorted(selected.values(),key=lambda p:[int(t) if t.isdigit() else t.casefold() for t in re.split(r'(\d+)',p.name)])


class Handler(SimpleHTTPRequestHandler):
    def __init__(self,*args,images=(),**kwargs):
        self.images=images
        super().__init__(*args,directory=str(ROOT/'web'),**kwargs)

    def end_headers(self):
        self.send_header('X-Content-Type-Options','nosniff')
        self.send_header('Cache-Control','no-cache')
        self.send_header('Permissions-Policy','camera=(self), microphone=()')
        super().end_headers()

    def do_GET(self):
        self.respond(head=False)

    def do_HEAD(self):
        self.respond(head=True)

    def respond(self,head=False):
        route=urlsplit(self.path).path
        if route=='/api/images':
            payload=json.dumps({'images':[{'title':p.stem,'url':f'/photos/{i}'} for i,p in enumerate(self.images)]},ensure_ascii=False).encode()
            self.send_response(200)
            self.send_header('Content-Type','application/json; charset=utf-8')
            self.send_header('Content-Length',str(len(payload)))
            self.end_headers()
            if not head:self.wfile.write(payload)
            return
        if route.startswith('/photos/'):
            try:
                i=int(route.removeprefix('/photos/'))
                if i<0:raise ValueError()
                path=self.images[i]
            except (ValueError,IndexError):
                self.send_error(404)
                return
        elif route=='/model.task':
            path=ROOT/'models/hand_landmarker.task'
        elif route.startswith('/vendor/'):
            relative=route.removeprefix('/vendor/')
            # Serve just the installed MediaPipe runtime assets, not the whole repository.
            if not re.fullmatch(r'wasm/vision_wasm_(?:nosimd_)?internal\.(?:js|wasm)',relative):
                self.send_error(404)
                return
            path=ROOT/'node_modules/@mediapipe/tasks-vision'/relative
        else:
            allowed={'/':'index.html','/index.html':'index.html','/app.js':'app.js','/gesture.js':'gesture.js',
                     '/style.css':'style.css','/tracking-worker.js':'tracking-worker.js'}
            if route not in allowed:
                self.send_error(404)
                return
            path=ROOT/'web'/allowed[route]
        try:
            file=path.open('rb')
        except OSError:
            self.send_error(404)
            return
        with file:
            self.send_response(200)
            self.send_header('Content-Type',mimetypes.guess_type(path.name)[0] or 'application/octet-stream')
            self.send_header('Content-Length',str(path.stat().st_size))
            self.end_headers()
            if not head:
                from shutil import copyfileobj
                try:copyfileobj(file,self.wfile)
                except (BrokenPipeError,ConnectionResetError):pass


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--images',type=Path)
    parser.add_argument('--port',type=int,default=8765)
    args=parser.parse_args()
    if not (ROOT/'web/tracking-worker.js').is_file():
        parser.error('先に npm ci && npm run build を実行してください。')
    try:files=image_files(args.images)
    except OSError as exc:parser.error(str(exc))
    if not (ROOT/'models/hand_landmarker.task').is_file():
        from urllib.request import urlretrieve
        path=ROOT/'models/hand_landmarker.task'
        path.parent.mkdir(exist_ok=True)
        temporary=path.with_suffix('.download')
        print('手認識モデルをダウンロードします。',flush=True)
        urlretrieve('https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task',temporary)
        temporary.replace(path)
    server=ThreadingHTTPServer(('127.0.0.1',args.port),partial(Handler,images=files))
    print(f'Hand Gallery: http://localhost:{server.server_port} ({len(files)} images)',flush=True)
    try:server.serve_forever()
    except KeyboardInterrupt:pass
    finally:server.server_close()


if __name__=='__main__':
    main()
