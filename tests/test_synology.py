import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import requests
from report_delivery.synology import SynologyClient


class Response:
    status_code = 200
    def __init__(self, data): self.data = data
    def json(self): return {'success': True, 'data': self.data}


class Session:
    def __init__(self): self.content = None
    def post(self, url, *, data, **kwargs):
        if data['api'] == 'SYNO.API.Auth':
            return Response({'sid': 'test-session'})
        if data['api'] == 'SYNO.FileStation.Upload':
            # Multipart SID must be a query parameter on this API.
            if kwargs.get('params') != {'_sid': 'test-session'} or data['path'] != '/reports':
                raise AssertionError('Incorrect multipart request contract')
            filename, stream, _ = kwargs['files']['file']
            self.content = (filename, stream.read())
            return Response({})
        if data['api'] == 'SYNO.FileStation.List':
            if data['offset'] == '0':
                return Response({'files': [{'name': 'unrelated', 'path': '/reports/unrelated'}]*100})
            return Response({'files': [{'name': '202601短视频数据源.xlsx',
                'path': '/reports/202601短视频数据源.xlsx',
                'additional': {'size': 3, 'time': {'mtime': 9999999999}}}]})
        raise AssertionError('Unexpected API call')
    def close(self): pass


class SynologyTests(unittest.TestCase):
    def test_multipart_payload_and_paginated_readback(self):
        session = Session()
        with patch('report_delivery.synology.requests.Session', return_value=session):
            with SynologyClient('https://nas.example.com', 'demo', 'not-a-real-password') as client:
                with tempfile.TemporaryDirectory() as directory:
                    path = Path(directory)/'202601短视频数据源.xlsx'
                    path.write_bytes(b'abc')
                    client.put('/reports/202601短视频数据源.xlsx', path)
                    self.assertEqual(session.content, ('202601短视频数据源.xlsx', b'abc'))
                self.assertEqual(client.stat('/reports/202601短视频数据源.xlsx'),
                    {'path': '/reports/202601短视频数据源.xlsx', 'size': 3, 'mtime': 9999999999})

    def test_network_error_does_not_echo_credentials_or_session_url(self):
        session = Session()
        session.post = lambda *args, **kwargs: (_ for _ in ()).throw(requests.exceptions.SSLError('private-session-url'))
        with patch('report_delivery.synology.requests.Session', return_value=session):
            with self.assertRaisesRegex(RuntimeError, '^NAS request failed: SSLError$'):
                with SynologyClient('https://nas.example.com', 'demo', 'private-password'):
                    pass

    def test_plain_http_and_embedded_credentials_are_rejected(self):
        for base in ('http://nas.example.com', 'https://name:secret@nas.example.com', 'https://nas.example.com/path?sid=x'):
            with self.assertRaises(ValueError):
                SynologyClient(base, 'demo', 'not-real')
