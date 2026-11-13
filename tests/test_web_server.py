from functools import partial
from http.server import ThreadingHTTPServer
from threading import Thread
from urllib.request import urlopen
from urllib.error import HTTPError
import json
import pytest
from web_server import Handler, image_files


def test_image_files_ignore_heic_duplicates_and_sort_numbers(tmp_path):
    for name in ('img10.png','img2.png','img2.HEIC','img2.jpg','secret.txt'):
        (tmp_path/name).write_bytes(b'test')
    assert [p.name for p in image_files(tmp_path)]==['img2.png','img10.png']


def test_server_serves_only_selected_images_and_web_assets(tmp_path):
    picture=tmp_path/'sample.png'
    picture.write_bytes(b'image-content')
    server=ThreadingHTTPServer(('127.0.0.1',0),partial(Handler,images=[picture]))
    thread=Thread(target=server.serve_forever,daemon=True)
    thread.start()
    base=f'http://127.0.0.1:{server.server_port}'
    try:
        with urlopen(base+'/api/images') as response:
            assert json.load(response)=={'images':[{'title':'sample','url':'/photos/0'}]}
        with urlopen(base+'/photos/0') as response:
            assert response.read()==b'image-content'
        for path in ('/.git/config','/../README.md','/photos/-1','/photos/../secret','/vendor/package.json'):
            with pytest.raises(HTTPError) as error:
                urlopen(base+path)
            assert error.value.code==404
    finally:
        server.shutdown()
        server.server_close()
        thread.join()
