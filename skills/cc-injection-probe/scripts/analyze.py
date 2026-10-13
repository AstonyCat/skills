#!/usr/bin/env python3
"""analyze.py — summarize captured CC API requests: where injections landed.
usage: analyze.py [capture_dir]   (default /tmp/cc-mem-capture)
Prints per request: message shape tree + injected-content locations
(recall / total_tokens / MEMORY.md index / attribution / system sections)."""
import json, glob, os, sys

CAP = sys.argv[1] if len(sys.argv) > 1 else '/tmp/cc-mem-capture'

def blocks(c):
    if isinstance(c, str):
        yield 'str', c
    elif isinstance(c, list):
        for b in c:
            if isinstance(b, dict):
                yield b.get('type'), b.get('text', '')

def tag_text(t):
    tags = []
    if t.lstrip().startswith('<system-reminder'): tags.append('SR-wrap')
    if 'Retrieved for possible relevance' in t: tags.append('RECALL-lead')
    if 'Memory: /' in t or 'Memory: ' in t[:200]: tags.append('MEMORY-file')
    if '<total_tokens>' in t: tags.append('TOTAL-TOKENS')
    if 'auto-memory' in t and 'MEMORY.md' in t: tags.append('MEMORY.md-index')
    if 'Attribution for git' in t: tags.append('ATTRIBUTION')
    if t.startswith('# Environment'): tags.append('ENV')
    if 'You are selecting memories' in t: tags.append('SELECTOR-SYS')
    return tags

for fn in sorted(glob.glob(os.path.join(CAP, '*.json'))):
    name = os.path.basename(fn)
    if name == 'mock.log': continue
    d = json.load(open(fn))
    msgs = d.get('messages', [])
    print(f"== {name}  model={d.get('model')} msgs={len(msgs)}")
    # top-level system
    sysm = d.get('system')
    if isinstance(sysm, list):
        for k, b in enumerate(sysm):
            t = b.get('text', '')
            print(f"   system[{k}] {len(t):>6}b cc={'Y' if b.get('cache_control') else '-'} {' '.join(tag_text(t)) or t[:40]!r}")
    for i, m in enumerate(msgs):
        for bt, t in blocks(m.get('content')):
            tags = tag_text(t)
            head = t[:56].replace('\n', '|')
            print(f"   [{i}] {m['role']:<9} {bt:<10} {len(t):>6}b {' '.join(tags) if tags else ''} :: {head!r}")
    print()
