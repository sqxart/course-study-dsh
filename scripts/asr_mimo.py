"""Transcribe a course video (or a local audio file) with an OpenAI-compatible ASR endpoint.

The default provider is MiMo, which exposes ASR through a chat completion:
`POST https://api.xiaomimimo.com/v1/chat/completions` with `model=mimo-v2.5-asr`
and one `input_audio` part carrying base64 mp3/wav. Auth is the `api-key` header.

The endpoint is not MiMo-specific: any service that accepts the same `input_audio`
chat payload works — point `--endpoint` / `--model` at it, and use `--auth-style bearer`
when it wants `Authorization: Bearer <key>` instead of the `api-key` header.

The course player serves a signed direct MP4 (`s2.cldisk.com/.../sd.mp4?at_=...`), so the
pipeline is: download → ffmpeg to 16 kHz mono mp3 → chunk → base64 per chunk → transcript.

    python scripts/asr_mimo.py --source "<signed mp4 url>" --out runs/<task>/asr/2.1.txt
    python scripts/asr_mimo.py --source "<mp4>" --out out.txt `
        --endpoint https://api.groq.com/openai/v1/chat/completions `
        --model whisper-large-v3-turbo --auth-style bearer --provider-key-env GROQ_API_KEY

The API key is read from `--api-key`, then `$MIMO_API_KEY` / `$ASR_API_KEY` / the provider
env named by `--provider-key-env`, then `--key-file` (default `local/mimo.key`); it is never
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
PRIVATE_CONFIG = Path(__file__).resolve().parents[1] / 'local' / 'private.toml'
KEY_ENV_VARS = ('MIMO_API_KEY', 'ASR_API_KEY')


def asr_enabled():
    """`[asr] enabled` in local/private.toml; missing file or key means the public default (off)."""
    try:
        import tomllib
    except ImportError:                     # Python < 3.11
        return None, 'tomllib unavailable'
    if not PRIVATE_CONFIG.is_file():
        return None, 'no local/private.toml'
    try:
        payload = tomllib.loads(PRIVATE_CONFIG.read_text(encoding='utf-8'))
    except Exception as error:              # noqa: BLE001 - a broken config must be visible
        return None, 'unreadable local/private.toml: {0}'.format(error)
    value = (payload.get('asr') or {}).get('enabled')
    return bool(value) if value is not None else None, None


def find_tool(name):
    path = shutil.which(name) or shutil.which(name + '.exe')
    if not path:
        raise SystemExit(name + ' not found on PATH')
    return path


def read_key(args):
    if args.api_key:
        return args.api_key.strip()
    candidates = list(KEY_ENV_VARS)
    provider_env = getattr(args, 'provider_key_env', None)
    if provider_env:
        candidates.insert(0, provider_env)
    for name in candidates:
        value = os.environ.get(name)
        if value:
            return value.strip()
    path = Path(args.key_file)
    if path.is_file():
        return path.read_text(encoding='utf-8').strip()
    raise SystemExit('no API key: set {0}, or write {1}'.format(' or '.join(candidates), path))


def private_asr(section):
    """`[asr]` table from local/private.toml, so a default can live in config instead of flags."""
    try:
        import tomllib
    except ImportError:
        return {}
    if not PRIVATE_CONFIG.is_file():
        return {}
    try:
        payload = tomllib.loads(PRIVATE_CONFIG.read_text(encoding='utf-8'))
    except Exception:                       # noqa: BLE001 - a broken config is reported elsewhere
        return {}
    return payload.get(section) or {}


def fetch(url, target, timeout=600, referer='https://mooc1.chaoxing.com/', attempts=8):
    """Download with resume: the media CDN drops the connection every few MB.

    It also answers 403 without a platform Referer (no cookie is needed). Each retry asks
    for the missing byte range, so a 30 MB lecture costs several short responses, not a
    restart from zero.
    """
    headers = {'User-Agent': 'Mozilla/5.0', 'Referer': referer, 'Accept': '*/*'}
    for attempt in range(attempts):
        have = os.path.getsize(target) if os.path.exists(target) else 0
        request_headers = dict(headers)
        if have:
            request_headers['Range'] = 'bytes={0}-'.format(have)
        request = urllib.request.Request(url, headers=request_headers)
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                total = response.headers.get('Content-Range')
                expected = None
                if total and '/' in total:
                    expected = int(total.rsplit('/', 1)[1])
                elif response.headers.get('Content-Length'):
                    expected = have + int(response.headers['Content-Length'])
                mode = 'ab' if have and response.status == 206 else 'wb'
                if mode == 'wb' and have:
                    have = 0
                with open(target, mode) as handle:
                    shutil.copyfileobj(response, handle)
        except Exception:
            if attempt == attempts - 1:
                raise
            time.sleep(1.5)
            continue
        size = os.path.getsize(target)
        if expected is None or size >= expected:
            return size
        time.sleep(0.8)
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


def transcribe(key, audio_path, language='zh', timeout=300, endpoint=None, model=None,
               auth_style='api-key'):
    payload = {
        'model': model or MODEL,
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
    headers = {'Content-Type': 'application/json'}
    if auth_style == 'bearer':
        headers['Authorization'] = 'Bearer ' + key
    else:
        headers['api-key'] = key
    request = urllib.request.Request(endpoint or ENDPOINT, data=body, method='POST', headers=headers)
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
    parser.add_argument('--api-key', help='API key (else env MIMO_API_KEY/ASR_API_KEY or key file)')
    parser.add_argument('--key-file', default=str(DEFAULT_KEY_FILE))
    parser.add_argument('--provider-key-env', help='Extra env var to read the key from, e.g. GROQ_API_KEY')
    parser.add_argument('--endpoint', help='OpenAI-compatible chat-completions URL (default: MiMo)')
    parser.add_argument('--model', help='ASR model name (default: mimo-v2.5-asr)')
    parser.add_argument('--auth-style', default='api-key', choices=('api-key', 'bearer'),
                        help='api-key header (MiMo) or Authorization: Bearer (most other providers)')
    parser.add_argument('--keep-audio', action='store_true', help='Keep the intermediate mp3 chunks')
    parser.add_argument('--force', action='store_true',
                        help='Run even when local/private.toml has [asr] enabled = false')
    args = parser.parse_args(argv)

    config = private_asr('asr')
    args.endpoint = args.endpoint or config.get('endpoint')
    args.model = args.model or config.get('model')
    args.auth_style = args.auth_style if args.auth_style != 'api-key' else (config.get('auth_style') or 'api-key')
    if args.key_file == str(DEFAULT_KEY_FILE) and config.get('key_file'):
        args.key_file = config['key_file']

    enabled, why = asr_enabled()
    if enabled is False and not args.force:
        raise SystemExit('ASR is switched off: set [asr] enabled = true in local/private.toml '
                         '(or pass --force). {0}'.format(why or ''))
    if enabled is None and not args.force:
        print('note: [asr] enabled not found in local/private.toml ({0}); continuing'.format(why or 'default'),
              file=sys.stderr)

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
            text, usage = transcribe(key, path, args.language, endpoint=args.endpoint,
                                     model=args.model, auth_style=args.auth_style)
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
