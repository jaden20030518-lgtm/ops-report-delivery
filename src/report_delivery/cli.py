"""Small explicit CLI: prepare, verify, preview, then opt in to upload."""
import argparse
from datetime import datetime
from getpass import getpass
import json
import os
from pathlib import Path
import sys

from .core import check_manifest, plan, process, verify
from .delivery import deliver
from .demo import run_demo
from .synology import SynologyClient, validate_origin


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    demo = sub.add_parser('demo', help='Run an offline synthetic demonstration')
    demo.add_argument('--out', default='demo-output')
    dates = sub.add_parser('plan', help='Calculate the Beijing-time month-to-yesterday window')
    dates.add_argument('--at', help='Timezone-aware timestamp for date-rule demonstration')
    prepare = sub.add_parser('process', help='Back up, transform and verify an existing export')
    prepare.add_argument('source')
    prepare.add_argument('--out', required=True)
    prepare.add_argument('--start', required=True)
    prepare.add_argument('--end', required=True)
    check = sub.add_parser('verify', help='Re-read all rows and check stored hashes')
    check.add_argument('manifest')
    upload = sub.add_parser('upload', help='Preview by default; use --execute to send')
    upload.add_argument('manifest')
    upload.add_argument('--config', required=True)
    upload.add_argument('--execute', action='store_true')
    args = parser.parse_args()
    try:
        if args.command == 'demo':
            result = run_demo(args.out)
        elif args.command == 'plan':
            result = plan(datetime.fromisoformat(args.at) if args.at else None)
        elif args.command == 'process':
            result = process(args.source, args.out, args.start, args.end)
        elif args.command == 'verify':
            path = Path(args.manifest)
            record = check_manifest(path)
            result = verify(path.parent/record['source_file'], path.parent/record['output_file'],
                            record['start_date'], record['end_date'])
            result['status'] = 'verified'
        else:
            config = json.loads(Path(args.config).read_text(encoding='utf-8'))
            endpoint = validate_origin(config['base_url'])
            # Local validation happens before credentials are requested or any network access.
            preview = deliver(args.manifest, config['remote_folder'], endpoint=endpoint)
            if not args.execute or preview['status'] == 'uploaded':
                result = preview
            else:
                record = check_manifest(args.manifest)
                if record['demo'] or not record['ready_for_upload']:
                    raise ValueError('Demo or unverified files cannot be uploaded')
                account = os.environ.get('REPORT_NAS_ACCOUNT')
                password = os.environ.get('REPORT_NAS_PASSWORD')
                if not account or not password:
                    if not sys.stdin.isatty():
                        raise ValueError('Use interactive credentials or secret-injected environment variables')
                    print('NAS account: ', end='', file=sys.stderr, flush=True)
                    account = input()
                    password = getpass('NAS password: ')
                with SynologyClient(config['base_url'], account, password,
                                    ca_bundle=config.get('ca_bundle', True)) as storage:
                    result = deliver(args.manifest, config['remote_folder'], storage,
                                     execute=True, endpoint=endpoint)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (ValueError, RuntimeError, OSError, KeyError) as error:
        print(json.dumps({'status': 'failed', 'reason': str(error)}, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
