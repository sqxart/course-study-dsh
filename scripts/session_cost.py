"""Summarise a DeepSeek Harness session log: tokens, tool calls, per-turn cost.

Usage after a run:

    python scripts/session_cost.py "%USERPROFILE%/.dsh/sessions/<dir>/<id>/session.v4.jsonl.zstd"

The file is zstd-compressed JSONL. Token counts come from the `usage` object on
each assistant message, which already distinguishes fresh input from cache reads:
cache reads dominate a long session, so report them separately instead of
summing them into "tokens used".
"""

import argparse
import json
import statistics
import sys
from pathlib import Path


def load_events(path):
    try:
        import zstandard
    except ImportError:
        raise SystemExit('zstandard is required to read .zstd session logs')
    import io
    data = Path(path).read_bytes()
    reader = zstandard.ZstdDecompressor().stream_reader(io.BytesIO(data))
    text = reader.read().decode('utf-8', 'replace')
    events = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return events


def summarize(events):
    steps = []
    calls = {}
    payload = {}
    times = []
    per_turn = {}
    for event in events:
        kind = event.get('type')
        data = event.get('data') or {}
        if 'time' in event:
            times.append(event['time'])
        if kind == 'assistant/message' and isinstance(data.get('usage'), dict):
            usage = data['usage']
            steps.append(usage)
            turn = data.get('turn')
            bucket = per_turn.setdefault(turn, {'tokens': 0, 'steps': 0, 'calls': 0})
            bucket['tokens'] += usage.get('totalTokens', 0)
            bucket['steps'] += 1
        elif kind == 'tool/call':
            calls[data.get('callId')] = data.get('name')
            turn = data.get('turn')
            if turn in per_turn:
                per_turn[turn]['calls'] += 1
        elif kind == 'tool/result':
            name = calls.get(data.get('callId'), '?')
            content = (data.get('message') or {}).get('content') or []
            size = sum(len(part.get('text', '')) for part in content if isinstance(part, dict))
            payload[name] = payload.get(name, 0) + size

    totals = [step.get('totalTokens', 0) for step in steps]
    return {
        'steps': len(steps),
        'tool_calls': len(calls),
        'tokens': {
            'total': sum(totals),
            'input': sum(step.get('inputTokens', 0) for step in steps),
            'cache_read': sum(step.get('cacheReadTokens', 0) for step in steps),
            'output': sum(step.get('outputTokens', 0) for step in steps),
        },
        'per_step_median': int(statistics.median(totals)) if totals else None,
        'per_step_max': max(totals) if totals else None,
        'wall_hours': round((max(times) - min(times)) / 3600000, 2) if times else None,
        'turns': {str(turn): value for turn, value in sorted(per_turn.items(), key=lambda kv: (kv[0] is None, kv[0]))},
        'tool_payload_kb': {name: round(size / 1024, 1) for name, size in sorted(payload.items(), key=lambda kv: -kv[1])},
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('session', help='session.v4.jsonl.zstd')
    parser.add_argument('--json', action='store_true', help='Raw JSON instead of the text report')
    args = parser.parse_args(argv)

    try:
        events = load_events(args.session)
    except OSError as failure:
        print(json.dumps({'status': 'error', 'error': str(failure)}, ensure_ascii=False))
        return 2
    report = summarize(events)
    report['status'] = 'ok'
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0

    tokens = report['tokens']
    print('steps={0} tool_calls={1} wall={2}h'.format(report['steps'], report['tool_calls'], report['wall_hours']))
    print('tokens total={0:,} input={1:,} cache_read={2:,} output={3:,}'.format(
        tokens['total'], tokens['input'], tokens['cache_read'], tokens['output']))
    print('per-step median={0:,} max={1:,}'.format(report['per_step_median'] or 0, report['per_step_max'] or 0))
    print('\nturn   steps  calls      tokens')
    for turn, value in report['turns'].items():
        print('{0:<6} {1:>5} {2:>6} {3:>11,}'.format(turn, value['steps'], value['calls'], value['tokens']))
    print('\ntool payload (KB): ' + ', '.join(
        '{0}={1}'.format(name, size) for name, size in list(report['tool_payload_kb'].items())[:8]))
    return 0


if __name__ == '__main__':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    raise SystemExit(main())
