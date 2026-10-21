"""Transcribe a course video (or a local audio file) with MiMo ASR.

MiMo exposes ASR through an OpenAI-compatible chat completion:
`POST https://api.xiaomimimo.com/v1/chat/completions` with `model=mimo-v2.5-asr`
and one `input_audio` part carrying base64 mp3/wav. Auth is the `api-key` header.

The course player serves a signed direct MP4 (`s2.cldisk.com/.../sd.mp4?at_=...`), so the
pipeline is: download → ffmpeg to 16 kHz mono mp3 → chunk → base64 per chunk → transcript.

    python scripts/asr_mimo.py --source "<signed mp4 url>" --out runs/<task>/asr/2.1.txt

The API key is read from $MIMO_API_KEY or --key-file (default `local/mimo.key`); it is never
written into the transcript or the log.
"""

import argparse
import base64
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

ENDPOINT = 'https://api.xiaomimimo.com/v1/chat/completions'
MODEL = 'mimo-v2.5-asr'
DEFAULT_KEY_FILE = Path(__file__).resolve().parents[1] / 'local' / 'mimo.key'


def find_tool(name):
    path = shutil.which(name) or shutil.which(name + '.exe')
    if not path:
        raise SystemExit(name + ' not found on PATH')
    return path


def read_key(args):
    if args.api_key:
        return args.api_key.strip()
    env = os.environ.get('MIMO_API_KEY')
    if env:
        return env.strip()
    path = Path(args.key_file)
    if path.is_file():
        return path.read_text(encoding='utf-8').strip()
    raise SystemExit('no API key: set MIMO_API_KEY or write ' + str(path))


def fetch(url, target, timeout=600, referer='https://mooc1.chaoxing.com/'):
    """The media CDN answers 403 without a platform Referer; no cookie is needed."""
    request = urllib.request.Request(url, headers={
        'User-Agent': 'Mozilla/5.0', 'Referer': referer, 'Accept': '*/*'})
    with urllib.request.urlopen(request, timeout=timeout) as response, open(target, 'wb') as handle:
        shutil.copyfileobj(response, handle)
    return os.path.getsize(target)


def to_audio(ffmpeg, source, target, sample_rate=16000):
    command = [ffmpeg, '-y', '-loglevel', 'error', '-i', source, '-vn', '-ac', '1',
               '-ar', str(sample_rate), '-b:a', '64k', target]
    subprocess.run(command, check=True)
    return os.path.getsize(target)


def chunk_audio(ffmpeg, audio, out_dir, seconds):
    duration = probe_duration(ffmpeg, audio)
    pieces = []
    index = 0
    start = 0.0
    while start < duration:
        target = str(Path(out_dir) / 'chunk-{0:03d}.mp3'.format(index))
        subprocess.run([ffmpeg, '-y', '-loglevel', 'error', '-ss', str(start), '-t', str(seconds),
                        '-i', audio, '-c', 'copy', target], check=True)
        pieces.append((target, start))
        index += 1
        start += seconds
    return pieces, duration


def probe_duration(ffmpeg, audio):
    ffprobe = find_tool('ffprobe')
    result = subprocess.run([ffprobe, '-v', 'error', '-show_entries', 'format=duration',
                             '-of', 'default=noprint_wrappers=1:nokey=1', audio],
                            capture_output=True, text=True)
    try:
        return float(result.stdout.strip())
    except ValueError:
        return 0.0


def transcribe(key, audio_path, language='zh', timeout=300):
    payload = {
        'model': MODEL,
        'messages': [{
            'role': 'user',
            'content': [{
                'type': 'input_audio',
                'input_audio': {
                    'data': 'data:audio/mpeg;base64,' + base64.b64encode(
                        Path(audio_path).read_bytes()).decode('ascii'),
                    'format': 'mp3',
                },
            }],
        }],
        'asr_options': {'language': language},
    }
    body = json.dumps(payload).encode('utf-8')
    request = urllib.request.Request(ENDPOINT, data=body, method='POST', headers={
        'Content-Type': 'application/json', 'api-key': key})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        data = json.loads(response.read().decode('utf-8'))
    text = data['choices'][0]['message']['content']
    usage = data.get('usage') or {}
    return text.strip(), usage


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--source', required=True, help='Signed mp4 URL or a local media file')
    parser.add_argument('--out', required=True, help='Transcript path (.txt)')
    parser.add_argument('--chunk-seconds', type=float, default=600, help='Chunk length (default 600)')
    parser.add_argument('--language', default='zh', choices=('zh', 'en', 'auto'))
    parser.add_argument('--api-key', help='MiMo API key (else $MIMO_API_KEY or key file)')
    parser.add_argument('--key-file', default=str(DEFAULT_KEY_FILE))
    parser.add_argument('--keep-audio', action='store_true', help='Keep the intermediate mp3 chunks')
    args = parser.parse_args(argv)

    key = read_key(args)
    ffmpeg = find_tool('ffmpeg')
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix='mimo-asr-'))
    started = time.time()
    try:
        source = args.source
        if source.startswith(('http://', 'https://')):
            media = str(work / 'media.mp4')
            size = fetch(source, media)
            print('DOWNLOAD bytes={0} seconds={1:.1f}'.format(size, time.time() - started), file=sys.stderr)
            source = media
        audio = str(work / 'audio.mp3')
        size = to_audio(ffmpeg, source, audio)
        print('AUDIO bytes={0} seconds={1:.1f}'.format(size, time.time() - started), file=sys.stderr)
        pieces, duration = chunk_audio(ffmpeg, audio, work, args.chunk_seconds)
        print('DURATION {0:.1f}s CHUNKS {1}'.format(duration, len(pieces)), file=sys.stderr)
        texts, seconds = [], 0
        for index, (path, start) in enumerate(pieces):
            text, usage = transcribe(key, path, args.language)
            texts.append(text)
            seconds += usage.get('seconds') or 0
            print('CHUNK {0}/{1} at {2:.0f}s chars={3} billed_seconds={4}'.format(
                index + 1, len(pieces), start, len(text), seconds), file=sys.stderr)
        out.write_text('\n'.join(texts).strip() + '\n', encoding='utf-8')
        print('WROTE {0} chars={1} seconds={2:.1f} audio_seconds={3:.0f}'.format(
            out, sum(len(text) for text in texts), time.time() - started, seconds))
    finally:
        if args.keep_audio:
            print('AUDIO KEPT ' + str(work), file=sys.stderr)
        else:
            shutil.rmtree(work, ignore_errors=True)
    return 0


if __name__ == '__main__':
    sys.exit(main())
