"""A verified report can be sent once; uncertain delivery requires inspection."""
import json
import time
from pathlib import Path, PurePosixPath

from .core import check_manifest, run_lock, save_json, sha256


def target_path(folder, name):
    path = PurePosixPath(folder)
    if (not folder.startswith('/') or folder == '/' or '..' in folder.split('/')
            or '\\' in folder or str(path) != folder):
        raise ValueError('Remote folder must be an explicit normalized absolute directory')
    return str(path/name)


def deliver(manifest, folder, storage=None, *, execute=False, endpoint=None):
    manifest = Path(manifest)
    endpoint = endpoint or getattr(storage, 'origin', None)
    with run_lock(manifest.parent):
        record = check_manifest(manifest)
        target = target_path(folder, record['output_file'])
        if record['status'] == 'uploaded':
            evidence = record.get('upload_verification', {})
            if evidence.get('remote_path') != target or evidence.get('endpoint') != endpoint:
                raise ValueError('Completed run belongs to a different delivery target')
            return {**record, 'reused': True}
        if not execute:
            return {'status': 'planned', 'remote_path': target, 'bytes': record['output_bytes'],
                    'endpoint': endpoint, 'demo': record['demo'], 'network_accessed': False}
        if record['demo'] or record.get('ready_for_upload') is not True:
            raise ValueError('Demo data or unverified results cannot be uploaded')
        if storage is None:
            raise ValueError('An authenticated storage adapter is required')
        attempt = manifest.parent/'upload-attempt.json'
        if attempt.exists():
            raise RuntimeError('Previous upload attempt exists; inspect remote state before retrying')
        previous = storage.stat(target)
        started = int(time.time())
        save_json(attempt, {'status': 'submitting', 'target': target, 'endpoint': endpoint,
                            'output_sha256': record['output_sha256'], 'started_unix': started})
        output = manifest.parent/record['output_file']
        storage.put(target, output)
        remote = storage.stat(target)
        if (not remote or remote.get('path') != target or remote.get('size') != record['output_bytes']
                or not isinstance(remote.get('mtime'), (int, float)) or remote['mtime'] < started-3):
            raise RuntimeError('Remote path, size or fresh modification time was not confirmed')
        if sha256(output) != record['output_sha256']:
            raise RuntimeError('Local file changed during upload')
        record.update(status='uploaded', ready_for_upload=False, upload_verification={
            'method': 'Synology File Station API', 'remote_path': target, 'endpoint': endpoint,
            'remote_size_bytes': remote['size'], 'remote_modified_unix': remote['mtime'],
            'previous_size_bytes': previous['size'] if previous else None,
            'remote_hash_checked': False})
        save_json(manifest, record)
        save_json(attempt, {'status': 'uploaded', 'target': target, 'endpoint': endpoint, 'started_unix': started})
        return record
