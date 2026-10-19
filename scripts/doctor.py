"""Report this skill's local capabilities without changing the environment."""
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys

import question_reader


def version(command):
    executable = shutil.which(command)
    if not executable:
        return {'available': False}
    try:
        result = subprocess.run([executable, '--version'], capture_output=True, text=True,
                                encoding='utf-8', errors='replace', timeout=15)
        return {'available': result.returncode == 0, 'path': executable,
                'version': (result.stdout or result.stderr).strip()[:200]}
    except (OSError, subprocess.SubprocessError) as error:
        return {'available': False, 'path': executable, 'error': str(error)}


def main():
    root = Path(__file__).resolve().parent.parent
    modules = {name: importlib.util.find_spec(name) is not None
               for name in ('zstandard', 'PIL', 'fontTools', 'rapidocr_onnxruntime', 'onnxruntime')}
    ocr_modules = ('PIL', 'fontTools', 'rapidocr_onnxruntime', 'onnxruntime')
    resources = {name: (root / name).is_file() for name in (
        'SKILL.md', 'README.md', 'NOTICE', 'references/dsh-runtime.md',
        'references/chaoxing.md', 'references/course-flow.md', 'references/quickstart.md',
        'scripts/dsh_probe.py', 'scripts/option_coverage.py', 'scripts/ocr_guard.py',
        'scripts/toc_status.py', 'scripts/session_cost.py', 'scripts/check_evidence.py',
        'scripts/question_reader.py', 'scripts/quiz_ocr.py', 'scripts/subtitle_evidence.py')}
    result = {
        'skill': 'course-study-dsh', 'version': '1.0.3',
        'python': {'path': sys.executable, 'version': sys.version.split()[0]},
        'node': version('node'),
        'reader': question_reader.doctor(),
        'dependencies': {
            'core': {'zstandard': modules['zstandard']},
            'ocr': {name: modules[name] for name in ocr_modules},
            'ocr_ready': all(modules[name] for name in ocr_modules),
            'ocr_install': 'pip install -r requirements-ocr.txt',
            'core_install': 'pip install -r requirements.txt',
            'browser_ready': 'unknown',
        },
        'resources': resources,
        'verdict': 'resources-ready' if all(resources.values()) else 'missing-resources',
        'browser': {'checked': False, 'reason': 'Use the current harness supported tools; no live session was opened.'},
        'notes': ['Optional OCR/font dependencies do not block DOM or screenshot workflows.',
                  'Harness browser channel is not probed here; use scripts/dsh_probe.py with --tools.',
                  'This reports installed files/commands/imports, not live course compatibility.'],
        'network_used': False, 'environment_changed': False,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if all(resources.values()) else 2


if __name__ == '__main__':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    raise SystemExit(main())
