import os
import socket
import struct
from django.conf import settings
from ninja.errors import HttpError


def scan_upload(upload):
    host=os.environ.get('CLAMAV_HOST','')
    if not host:
        if settings.PRODUCTION:raise HttpError(503,'Upload scanning is unavailable. Contact IT.')
        return
    try:
        with socket.create_connection((host,int(os.environ.get('CLAMAV_PORT','3310'))),timeout=60) as connection:
            connection.sendall(b'zINSTREAM\0')
            for chunk in upload.chunks(65536):connection.sendall(struct.pack('!I',len(chunk))+chunk)
            connection.sendall(struct.pack('!I',0))
            response=b''
            while b'\0' not in response and len(response)<4096:
                piece=connection.recv(1024)
                if not piece:break
                response+=piece
        if b'FOUND' in response:raise HttpError(400,'The uploaded file was blocked by malware scanning. Choose a clean file.')
        if not response.rstrip(b'\0\n').endswith(b'OK'):raise HttpError(503,'The upload could not be scanned. Retry later.')
    except (OSError,TimeoutError):raise HttpError(503,'Upload scanning is unavailable. Retry later.')
    finally:upload.seek(0)
