#!/usr/bin/env python3
"""Mock Anthropic API server for CC injection-format testing.

Features (CLI-selectable):
  --port N              listen port (default 4545)
  --first-delay SECS    delay the first main (non-selector) response (default 4; 0 = no delay → miss-first-train)
  --select A,B          memory filenames the selector "selects" (default: all files found at runtime? no — must be explicit)
  --main-mode mode      main conversation behavior:
                          tool_then_text : first main returns tool_use(Read), after tool_result returns final text
                          text           : always return plain text
  --tool-name NAME      tool to use in tool_then_text mode (default Read)
  --scenario NAME       named scenario presets (overrides above):
                          catch    : first-delay 4s + tool_then_text  (recall makes first request)
                          miss     : first-delay 0  + tool_then_text  (recall arrives mid-turn)
                          notool   : first-delay 4  + text            (no tool loop at all)
  --capture DIR         capture dir (default /tmp/cc-mem-capture)
  --static-dir DIR      serve /static/* from DIR (unused by CC, reserved)

Every request body is dumped to <capture>/<seq>_<kind>[_aftertool].json.
kind = selector | extract | main.
"""
import argparse, json, os, sys, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Lock

ap = argparse.ArgumentParser()
ap.add_argument('--port', type=int, default=4545)
ap.add_argument('--first-delay', type=float, default=4.0)
ap.add_argument('--select', default='')
ap.add_argument('--main-mode', default='tool_then_text', choices=['tool_then_text', 'text'])
ap.add_argument('--tool-name', default='Read')
ap.add_argument('--scenario', choices=['catch', 'miss', 'notool'])
ap.add_argument('--capture', default='/tmp/cc-mem-capture')
args = ap.parse_args()

if args.scenario == 'catch':
    args.first_delay, args.main_mode = 4.0, 'tool_then_text'
elif args.scenario == 'miss':
    args.first_delay, args.main_mode = 0.0, 'tool_then_text'
elif args.scenario == 'notool':
    args.first_delay, args.main_mode = 4.0, 'text'

SELECTED = [s.strip() for s in args.select.split(',') if s.strip()]
CAPTURE_DIR = args.capture
os.makedirs(CAPTURE_DIR, exist_ok=True)
lock = Lock()
counter = [0]

def classify(body):
    sys_str = json.dumps(body.get('system', ''), ensure_ascii=False)
    if 'You are selecting memories' in sys_str:
        return 'selector'
    if 'memory extraction subagent' in sys_str:
        return 'extract'
    return 'main'

class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_POST(self):
        n = int(self.headers.get('content-length', 0))
        raw = self.rfile.read(n)
        try:
            body = json.loads(raw)
        except Exception:
            body = {}
        kind = classify(body)
        msgs = body.get('messages', [])
        seen_tool_result = any(
            isinstance(m.get('content'), list) and
            any(b.get('type') == 'tool_result' for b in m['content'])
            for m in msgs if isinstance(m.get('content'), list))
        with lock:
            counter[0] += 1
            i = counter[0]
            tag = f'{i:02d}_{kind}' + ('_aftertool' if kind == 'main' and seen_tool_result else '')
            with open(os.path.join(CAPTURE_DIR, tag + '.json'), 'w') as f:
                json.dump(body, f, indent=1, ensure_ascii=False)

        # ── build response content ──
        if kind == 'selector':
            sel = SELECTED or []
            text = json.dumps({'selected_memories': sel}, ensure_ascii=False)
            content = [{'type': 'text', 'text': text}]
            stop = 'end_turn'
        elif kind == 'extract':
            content = [{'type': 'text', 'text': 'Nothing to save.'}]
            stop = 'end_turn'
        elif not seen_tool_result:
            if counter[0] == 1 or True:
                pass
            # first main call in this process (approximation: no tool_result seen yet)
            if args.first_delay > 0:
                time.sleep(args.first_delay)
            if args.main_mode == 'tool_then_text':
                content = [{'type': 'tool_use', 'id': 'toolu_mock1', 'name': args.tool_name,
                            'input': {'file_path': '/tmp/cc-mem-proj/notes.txt'}}]
                stop = 'tool_use'
            else:
                content = [{'type': 'text', 'text': '好的，已知悉。'}]
                stop = 'end_turn'
        else:
            content = [{'type': 'text', 'text': '好的，规格已确认。'}]
            stop = 'end_turn'

        msg = {'id': f'msg_mock_{i}', 'type': 'message', 'role': 'assistant',
               'model': body.get('model', 'claude-mock'), 'content': content,
               'stop_reason': stop, 'stop_sequence': None,
               'usage': {'input_tokens': 10, 'output_tokens': 5}}

        if body.get('stream'):
            self.send_response(200)
            self.send_header('content-type', 'text/event-stream')
            self.end_headers()
            events = [('message_start', {'type': 'message_start', 'message': msg})]
            if content[0]['type'] == 'text':
                events += [('content_block_start', {'type': 'content_block_start', 'index': 0, 'content_block': {'type': 'text', 'text': ''}}),
                           ('content_block_delta', {'type': 'content_block_delta', 'index': 0, 'delta': {'type': 'text_delta', 'text': content[0]['text']}}),
                           ('content_block_stop', {'type': 'content_block_stop', 'index': 0})]
            else:
                blk = content[0]
                events += [('content_block_start', {'type': 'content_block_start', 'index': 0, 'content_block': {'type': 'tool_use', 'id': blk['id'], 'name': blk['name']}}),
                           ('content_block_delta', {'type': 'content_block_delta', 'index': 0, 'delta': {'type': 'input_json_delta', 'partial_json': json.dumps(blk['input'])}}),
                           ('content_block_stop', {'type': 'content_block_stop', 'index': 0})]
            events += [('message_delta', {'type': 'message_delta', 'delta': {'stop_reason': stop}, 'usage': {'output_tokens': 5}}),
                       ('message_stop', {'type': 'message_stop'})]
            for name, data in events:
                self.wfile.write(f'event: {name}\ndata: {json.dumps(data)}\n\n'.encode())
                self.wfile.flush()
        else:
            data = json.dumps(msg).encode()
            self.send_response(200)
            self.send_header('content-type', 'application/json')
            self.send_header('content-length', str(len(data)))
            self.end_headers()
            self.wfile.write(data)

if __name__ == '__main__':
    print(f'mock on :{args.port} scenario={args.scenario} delay={args.first_delay} mode={args.main_mode} select={SELECTED}', flush=True)
    ThreadingHTTPServer(('127.0.0.1', args.port), H).serve_forever()
