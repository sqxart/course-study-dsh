"""Download the subtitles each node capture pointed at, into `subs/<course>/<section>.srt`.

The capture driver records the player's `allsubtitle` list while the node is open, so the
download itself needs no second browser visit: the `.srt` URLs live on the media CDN.
Sections whose capture has no subtitle entry are simply skipped — the review document
marks those `本节无字幕`.

    python scripts/bank_subs.py --nodes runs/bank/nodes/course-example \\
        --out runs/bank/subs/course-example
"""

import argparse
import importlib.util
import json
import sys
import time
from pathlib import Path

DELAY_SECONDS = 1.0
RETRY_DELAY_SECONDS = 3.0


def load_subtitle_module():
    path = Path(__file__).with_name('subtitle_evidence.py')
    spec = importlib.util.spec_from_file_location('subtitle_evidence', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def subtitle_urls(capture):
    """The SRT URLs the driver saw, tolerating older captures without the field."""
    subs = capture.get('subs') or {}
    urls = subs.get('srt') or []
    return [url for url in urls if isinstance(url, str) and url.lower().startswith('http')]


def collect(nodes_dir):
    found, missing = [], []
    for path in sorted(Path(nodes_dir).glob('*.json')):
        try:
            capture = json.loads(path.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            continue
        if capture.get('kind') != 'quiz-bank-capture':
            continue
        urls = subtitle_urls(capture)
        if urls:
            found.append((capture.get('section') or path.stem, urls))
        else:
            missing.append(capture.get('section') or path.stem)
    return found, missing


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--nodes', required=True, help='Directory of quiz-bank captures')
    parser.add_argument('--out', required=True, help='Directory for <section>.srt files')
    parser.add_argument('--expect', help='Expected section list; reports sections without subtitles')
    parser.add_argument('--delay', type=float, default=DELAY_SECONDS, help='Seconds between downloads')
    args = parser.parse_args(argv)

    module = load_subtitle_module()
    found, missing = collect(args.nodes)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    saved, skipped, failed = 0, 0, []
    for section, urls in found:
        target = out_dir / (section + '.srt')
        if target.exists():
            skipped += 1
            continue
        url = urls[0]
        try:
            text = module.download(url, 25.0)
        except Exception as error:  # noqa: BLE001 - one bad URL must not stop the batch
            time.sleep(RETRY_DELAY_SECONDS)
            try:
                text = module.download(url, 25.0)
            except Exception as again:  # noqa: BLE001
                failed.append('{0}: {1}'.format(section, again))
                continue
        module.write_atomic(target, text)
        saved += 1
        time.sleep(args.delay)
    expected = None
    if args.expect:
        expected = json.loads(Path(args.expect).read_text(encoding='utf-8'))
    print('SECTIONS_WITH_SUBTITLE={0} SAVED={1} SKIPPED={2} FAILED={3} NO_SUBTITLE={4}'.format(
        len(found), saved, skipped, len(failed), len(missing)))
    if expected is not None:
        have = {section for section, _ in found}
        absent = [code for code in expected if code not in have]
        if absent:
            print('NO_SUBTITLE_SECTIONS={0} {1}'.format(len(absent), ' '.join(absent[:40])))
    for line in failed:
        print('FAILED ' + line, file=sys.stderr)
    return 0


if __name__ == '__main__':
    sys.exit(main())
