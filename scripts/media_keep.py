"""Persist the text a video node already exposes: subtitles now, ASR only when there are none.

The video flow reads the player frame anyway (for the rate menu), so `allsubtitle` comes free.
Keeping the SRT — or, when `[asr] enabled`, a 90-second-chunk transcript — means a later review
card never has to visit the node again, and never pays for the same audio twice.

    python scripts/media_keep.py keep --evidence runs/<task>/evidence.json \
        --subs-dir runs/<task>/subs/<course> --asr-dir runs/<task>/asr/<course> --asr-enabled

`--dry-run` prints the decision without touching the network.
"""

import argparse
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ASR = ROOT / 'scripts' / 'asr_mimo.py'


def load_subtitle_module():
    path = ROOT / 'scripts' / 'subtitle_evidence.py'
    spec = importlib.util.spec_from_file_location('subtitle_evidence', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def http_urls(values):
    return [value for value in (values or []) if isinstance(value, str) and value.lower().startswith('http')]


def plan(evidence):
    """Decide what this node can give us: an SRT URL, an MP4 to transcribe, or nothing."""
    subtitles = http_urls((evidence.get('subs') or {}).get('srt'))
    if subtitles:
        return {'mode': 'srt', 'url': subtitles[0]}
    media = evidence.get('media') or {}
    videos = http_urls(media.get('mp4') or evidence.get('mp4'))
    if videos:
        return {'mode': 'asr', 'url': videos[0]}
    return {'mode': 'skip', 'reason': 'no-subtitle-and-no-mp4'}


def keep(evidence_path, subs_dir=None, asr_dir=None, asr_enabled=False,
         chunk_seconds=90, key_file=None, dry_run=False):
    evidence = json.loads(Path(evidence_path).read_text(encoding='utf-8'))
    section = evidence.get('section') or Path(evidence_path).stem
    decision = plan(evidence)
    report = {'section': section, 'mode': decision['mode'], 'wrote': None, 'skipped': None}

    if decision['mode'] == 'srt':
        target = Path(subs_dir or '.') / (section + '.srt')
        if target.exists():
            report['skipped'] = 'subtitle-already-saved'
            return report
        if dry_run:
            report['skipped'] = 'dry-run'
            return report
        module = load_subtitle_module()
        text = module.download(decision['url'], 25.0)
        module.write_atomic(target, module.decode_bytes(text))
        report['wrote'] = str(target)
        return report

    if decision['mode'] == 'asr':
        if not asr_enabled:
            report['skipped'] = 'asr-disabled'
            return report
        target = Path(asr_dir or '.') / (section + '.txt')
        if target.exists():
            report['skipped'] = 'transcript-already-saved'
            return report
        if dry_run:
            report['skipped'] = 'dry-run'
            return report
        command = [sys.executable, str(ASR), '--source', decision['url'],
                   '--chunk-seconds', str(chunk_seconds), '--out', str(target)]
        if key_file:
            command += ['--key-file', str(key_file)]
        subprocess.run(command, check=True)
        report['wrote'] = str(target)
        return report

    report['skipped'] = decision['reason']
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest='command', required=True)
    command = sub.add_parser('keep', help='Save this node\'s subtitles, or transcribe when there are none')
    command.add_argument('--evidence', required=True, help='Node evidence.json that carries subs/media')
    command.add_argument('--subs-dir', help='Where <section>.srt goes')
    command.add_argument('--asr-dir', help='Where <section>.txt goes')
    command.add_argument('--asr-enabled', action='store_true', help='Allow the ASR fallback')
    command.add_argument('--chunk-seconds', type=float, default=90.0)
    command.add_argument('--key-file', help='MiMo key file for asr_mimo.py')
    command.add_argument('--dry-run', action='store_true')
    args = parser.parse_args(argv)

    if args.command == 'keep':
        if args.subs_dir:
            Path(args.subs_dir).mkdir(parents=True, exist_ok=True)
        if args.asr_dir and args.asr_enabled:
            Path(args.asr_dir).mkdir(parents=True, exist_ok=True)
        report = keep(args.evidence, subs_dir=args.subs_dir, asr_dir=args.asr_dir,
                      asr_enabled=args.asr_enabled, chunk_seconds=args.chunk_seconds,
                      key_file=args.key_file, dry_run=args.dry_run)
        print(json.dumps(report, ensure_ascii=False))
        return 0
    return 2


if __name__ == '__main__':
    sys.exit(main())
