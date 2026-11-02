#!/usr/bin/env python3
"""Validate SRT syntax; warn on overlaps without assuming subtitles never overlap."""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TIME = re.compile(r'^(\d{2,}):(\d{2}):(\d{2}),(\d{3}) --> (\d{2,}):(\d{2}):(\d{2}),(\d{3})$')
INVISIBLE = re.compile(r'[\u200e\u200f\u202a-\u202e\u2066-\u2069\ufeff\s]')


def milliseconds(parts: tuple[str, ...]) -> int:
    hours, minutes, seconds, ms = map(int, parts)
    if minutes >= 60 or seconds >= 60:
        raise ValueError('minutes and seconds must be below 60')
    return ((hours * 60 + minutes) * 60 + seconds) * 1000 + ms


def validate(path: Path) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    try:
        content = path.read_text(encoding='utf-8-sig')
    except (UnicodeDecodeError, OSError) as exc:
        return [f'cannot read UTF-8: {exc}'], warnings
    blocks = re.split(r'\n[ \t]*\n', content.strip().replace('\r\n', '\n')) if content.strip() else []
    if not blocks:
        return ['no subtitle cues'], warnings
    previous_start = -1
    previous_end = -1
    expected = 1
    for block in blocks:
        lines = block.splitlines()
        label = lines[0] if lines else '?'
        if len(lines) < 3:
            errors.append(f'cue {label}: expected index, timestamp, and text')
            continue
        if not re.fullmatch(r'\d+', label):
            errors.append(f'cue {label}: invalid index')
        else:
            index = int(label)
            if index != expected:
                warnings.append(f'cue {label}: expected index {expected}')
            expected = index + 1
        match = TIME.fullmatch(lines[1].strip())
        if not match:
            errors.append(f'cue {label}: invalid timestamp: {lines[1]}')
            continue
        try:
            start = milliseconds(match.groups()[:4])
            end = milliseconds(match.groups()[4:])
        except ValueError as exc:
            errors.append(f'cue {label}: {exc}')
            continue
        if end <= start:
            errors.append(f'cue {label}: end must be later than start')
        if start < previous_start:
            errors.append(f'cue {label}: cues are not ordered by start time')
        if start < previous_end:
            warnings.append(f'cue {label}: overlaps preceding cue')
        if not INVISIBLE.sub('', '\n'.join(lines[2:])):
            errors.append(f'cue {label}: subtitle text is empty')
        previous_start = start
        previous_end = end
    return errors, warnings


def main() -> int:
    files = sorted((ROOT / 'videos').rglob('*.srt'))
    if not files:
        print('No SRT files found.', file=sys.stderr)
        return 1
    errors_total = 0
    warnings_total = 0
    for path in files:
        errors, warnings = validate(path)
        errors_total += len(errors)
        warnings_total += len(warnings)
        print(f'{path.relative_to(ROOT)}: {len(errors)} errors, {len(warnings)} warnings')
        for message in errors:
            print(f'  ERROR: {message}')
        for message in warnings[:10]:
            print(f'  WARNING: {message}')
        if len(warnings) > 10:
            print(f'  ... {len(warnings)-10} additional warnings')
    print(f'Checked {len(files)} files: {errors_total} errors, {warnings_total} warnings.')
    return 1 if errors_total else 0


if __name__ == '__main__':
    raise SystemExit(main())
