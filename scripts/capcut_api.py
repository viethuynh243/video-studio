"""Thin client for VectCutAPI (CapCut draft automation, Flask on localhost:9001).

  python capcut_api.py status                         # is the server up? list desktop drafts
  python capcut_api.py build --spec draft.json        # create a NEW draft from a spec and save it to CapCut desktop
  python capcut_api.py types transition|font|intro_animation|outro_animation|audio_effect|text_intro|mask

draft.json:
{
  "name": "DU_AN_30s_v1",            # must not exist yet (never overwrite a draft)
  "width": 1920, "height": 1080,
  "video": [{"file": "D:/du_an/hinh.mp4", "start": 0, "end": 36.5, "target_start": 0, "volume": 0}],
  "audio": [{"file": "voice.wav", "target_start": 0, "volume": 1.0, "track": "voice"},
            {"file": "music.wav", "target_start": 0, "volume": 0.6, "track": "music"}],
  "text":  [{"text": "TÊN DỰ ÁN", "start": 0.7, "end": 5.5, "font_size": 8, "font_color": "#FFFFFF", "transform_y": 0.7}],
  "srt": "subs.srt"                            # optional subtitle file
}
Server not running?  cd ~/tools/VectCutAPI && python capcut_server.py   (run in background)
"""
import argparse, json, os, sys, urllib.request

BASE = os.environ.get('VECTCUT_URL', 'http://127.0.0.1:9001')
DRAFT_DIR = os.environ.get('CAPCUT_DRAFT_DIR',
                           os.path.expanduser('~/AppData/Local/CapCut/User Data/Projects/com.lveditor.draft'))


def call(ep, data=None, method='POST'):
    req = urllib.request.Request(BASE + ep, data=json.dumps(data or {}).encode() if method == 'POST' else None,
                                 headers={'Content-Type': 'application/json'}, method=method)
    with urllib.request.urlopen(req, timeout=600) as r:
        res = json.loads(r.read().decode('utf8'))
    if isinstance(res, dict) and res.get('success') is False:
        raise RuntimeError(f'{ep}: {res.get("error")}')
    return res


def absf(p, root):
    return p if os.path.isabs(p) else os.path.abspath(os.path.join(root, p))


def build(spec_path):
    spec = json.load(open(spec_path, encoding='utf8')); root = os.path.dirname(os.path.abspath(spec_path))
    names = [p['name'] for p in call('/list_projects')['output']['projects']]
    if spec['name'] in names or os.path.exists(os.path.join(DRAFT_DIR, spec['name'])): raise SystemExit(f'draft "{spec["name"]}" already exists - pick a new name')
    W, H = spec.get('width', 1920), spec.get('height', 1080)
    did = call('/create_draft', {'width': W, 'height': H})['output']['draft_id']
    for v in spec.get('video', []):
        call('/add_video', {'draft_id': did, 'video_url': absf(v['file'], root), 'start': v.get('start', 0), 'end': v.get('end', 0),
                            'target_start': v.get('target_start', 0), 'volume': v.get('volume', 1.0), 'speed': v.get('speed', 1.0),
                            'track_name': v.get('track', 'video_main'), 'width': W, 'height': H,
                            **({'transition': v['transition'], 'transition_duration': v.get('transition_duration', 0.5)} if v.get('transition') else {})})
    for x in spec.get('audio', []):
        call('/add_audio', {'draft_id': did, 'audio_url': absf(x['file'], root), 'start': x.get('start', 0), 'end': x.get('end'),
                            'target_start': x.get('target_start', 0), 'volume': x.get('volume', 1.0),
                            'track_name': x.get('track', 'audio_main'), 'width': W, 'height': H})
    for t in spec.get('text', []):
        call('/add_text', {'draft_id': did, 'width': W, 'height': H, 'track_name': t.get('track', 'text_main'),
                           **{k: v for k, v in t.items() if k != 'track'}})
    if spec.get('srt'):
        p = absf(spec['srt'], root)
        call('/add_subtitle', {'draft_id': did, 'srt': open(p, encoding='utf8').read() if os.path.exists(p) else spec['srt'],
                               'font_size': spec.get('srt_font_size', 5.0), 'border_width': 0.08, 'border_color': '#000000',
                               'width': W, 'height': H})
    r = call('/save_draft', {'draft_id': did, 'draft_folder': DRAFT_DIR, 'project_name': spec['name']})
    print('saved draft', spec['name'], '->', json.dumps(r.get('output'), ensure_ascii=False)[:300])


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('cmd', choices=['status', 'build', 'types']); ap.add_argument('arg', nargs='?'); ap.add_argument('--spec')
    a = ap.parse_args()
    if a.cmd == 'status':
        r = call('/list_projects')['output']
        print(f'server OK at {BASE}; {r["count"]} drafts in {DRAFT_DIR}')
        for p in r['projects']: print('  ', p['name'], p['modified_time'])
    elif a.cmd == 'build':
        build(a.spec)
    else:
        r = call(f'/get_{a.arg}_types', method='GET')
        print(json.dumps(r.get('output', r), ensure_ascii=False, indent=1)[:4000])


if __name__ == '__main__':
    main()
