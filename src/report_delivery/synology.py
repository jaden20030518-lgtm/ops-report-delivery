"""Configurable File Station adapter; it contains no organization defaults."""
import json
from pathlib import Path, PurePosixPath
from urllib.parse import urlparse

import requests


def validate_origin(base_url):
    parsed = urlparse(base_url)
    if (parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password
            or parsed.path not in ('', '/') or parsed.query or parsed.fragment or parsed.params):
        raise ValueError('NAS URL must be an HTTPS origin without credentials or query parameters')
    return 'https://'+parsed.netloc.lower()


class SynologyClient:
    def __init__(self, base_url, account, password, *, ca_bundle=True):
        self.origin = validate_origin(base_url)
        if not account or not password:
            raise ValueError('NAS credentials are required')
        if ca_bundle is not True and (not isinstance(ca_bundle, str) or not Path(ca_bundle).is_file()):
            raise ValueError('CA bundle must be a local certificate file; TLS verification cannot be disabled')
        self.url = self.origin+'/webapi/entry.cgi'
        self.session = requests.Session()
        self.verify = ca_bundle
        self.sid = None
        self.credentials = (account, password)

    def __enter__(self):
        try:
            account, password = self.credentials
            response = self._call({'api': 'SYNO.API.Auth', 'version': '6', 'method': 'login',
                                   'account': account, 'passwd': password, 'session': 'FileStation', 'format': 'sid'})
            self.sid = response.get('sid')
            if not self.sid:
                raise RuntimeError('NAS login returned no session')
            return self
        except Exception:
            self.session.close()
            raise
        finally:
            self.credentials = None

    def __exit__(self, *_):
        try:
            if self.sid:
                self.session.post(self.url, data={'api': 'SYNO.API.Auth', 'version': '6',
                    'method': 'logout', 'session': 'FileStation', '_sid': self.sid},
                    timeout=(5, 5), verify=self.verify, allow_redirects=False)
        except requests.RequestException:
            pass
        finally:
            self.sid = None
            self.session.close()

    def _call(self, data, files=None):
        try:
            response = self.session.post(self.url, data=data, files=files,
                params={'_sid': self.sid} if files else None,
                timeout=(10, 45), verify=self.verify, allow_redirects=False)
        except requests.RequestException as error:
            # Exception text can contain a SID-bearing request URL. Never echo it.
            raise RuntimeError(f'NAS request failed: {type(error).__name__}') from None
        if response.status_code != 200:
            raise RuntimeError(f'NAS returned HTTP {response.status_code}')
        try:
            body = response.json()
        except ValueError:
            raise RuntimeError('NAS returned an invalid JSON response') from None
        if body.get('success') is not True:
            code = body.get('error', {}).get('code')
            safe_code = code if isinstance(code, int) else 'unknown'
            raise RuntimeError(f'NAS API error {safe_code}')
        return body.get('data') or {}

    def stat(self, path):
        if not self.sid:
            raise RuntimeError('NAS session is not authenticated')
        target = PurePosixPath(path)
        for offset in range(0, 10000, 100):
            data = self._call({'api': 'SYNO.FileStation.List', 'version': '2', 'method': 'list',
                'folder_path': json.dumps(str(target.parent), ensure_ascii=False),
                'additional': json.dumps(['size', 'time']), 'offset': str(offset),
                'limit': '100', '_sid': self.sid})
            files = data.get('files', [])
            for item in files:
                if item.get('path') == path and item.get('name') == target.name:
                    extra = item.get('additional', {})
                    return {'path': path, 'size': extra.get('size', item.get('size')),
                            'mtime': extra.get('time', {}).get('mtime')}
            if len(files) < 100:
                return None
        raise RuntimeError('NAS listing exceeds inspection limit')

    def put(self, path, local):
        if not self.sid or PurePosixPath(path).name != Path(local).name:
            raise ValueError('Upload session or target filename does not match')
        with Path(local).open('rb') as stream:
            self._call({'api': 'SYNO.FileStation.Upload', 'version': '3', 'method': 'upload',
                'path': str(PurePosixPath(path).parent), 'create_parents': 'false',
                'overwrite': 'overwrite', '_sid': self.sid}, files={'file': (
                    Path(local).name, stream, 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')})
