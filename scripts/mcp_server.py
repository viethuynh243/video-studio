"""Video Studio MCP server: the skill's engine exposed as tools Claude can call directly.

Register once (user scope):
  claude mcp add --scope user video-studio -e PYTHONIOENCODING=utf-8 -- python <repo>/scripts/mcp_server.py

Quick tools return results immediately (probe, QC, voice suggestions, shot search, dictionary preview, contact sheet).
Long tools (make, revoice, subs, fps conversion, reframe, stabilise, critic, voice samples) start a background JOB and
return its id; poll with job_status / job_list. Jobs survive a server restart (state + log in ~/.cache/video_studio/jobs).
Outputs are never overwritten (the engine refuses existing files).
"""
import json, os, subprocess, sys, time, uuid

# Children (ffmpeg, ffprobe, python) must NEVER inherit stdin: it is the MCP JSON-RPC channel. ffmpeg reads stdin for
# its interactive keys and would swallow protocol bytes -> the server hangs. Default every Popen to stdin=DEVNULL.
_Popen_init = subprocess.Popen.__init__


def _popen_no_stdin(self, *a, **kw):
    if kw.get('stdin') is None and not kw.get('input'): kw['stdin'] = subprocess.DEVNULL
    _Popen_init(self, *a, **kw)


subprocess.Popen.__init__ = _popen_no_stdin
from mcp.server.fastmcp import FastMCP
if os.environ.get('VS_MCP_DEBUG'):
    import faulthandler; faulthandler.dump_traceback_later(int(os.environ['VS_MCP_DEBUG']), repeat=True, file=sys.stderr)

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
JOBS = os.path.expanduser('~/.cache/video_studio/jobs'); os.makedirs(JOBS, exist_ok=True)
ENV = dict(os.environ, PYTHONIOENCODING='utf-8', PYTHONUTF8='1')
# Heavy native modules must be imported at start-up on the main thread: importing numpy's C extension lazily inside a
# tool call (worker thread, after the event loop started) was seen to dead-lock on Windows.
import numpy, cv2  # noqa: E402,F401
import fps_convert, probe_qc, voices, accuracy, shot_select, tts_vi  # noqa: E402,F401
mcp = FastMCP('video-studio')


# ------------------------------------------------------------------ jobs
def _start(kind, args, outputs):
    jid = time.strftime('%m%d-%H%M%S-') + uuid.uuid4().hex[:4]
    log = os.path.join(JOBS, f'{jid}.log')
    p = subprocess.Popen([sys.executable] + args, stdout=open(log, 'w', encoding='utf8'), stderr=subprocess.STDOUT, env=ENV,
                         cwd=os.path.dirname(os.path.abspath(outputs[0])) if outputs else HERE,
                         creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    json.dump({'id': jid, 'kind': kind, 'pid': p.pid, 'args': args, 'outputs': outputs, 'start': time.time(), 'log': log},
              open(os.path.join(JOBS, f'{jid}.json'), 'w', encoding='utf8'), ensure_ascii=False)
    return {'job_id': jid, 'kind': kind, 'outputs': outputs, 'hint': 'poll with job_status(job_id)'}


def _alive(pid):
    try:
        import ctypes
        h = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid)
        if not h: return False
        code = ctypes.c_ulong(); ctypes.windll.kernel32.GetExitCodeProcess(h, ctypes.byref(code)); ctypes.windll.kernel32.CloseHandle(h)
        return code.value == 259
    except Exception:
        try: os.kill(pid, 0); return True
        except OSError: return False


@mcp.tool()
def job_status(job_id: str, tail: int = 25) -> dict:
    """Status of a background job: running/done/failed, last log lines, outputs that exist, and the QC report if any."""
    j = json.load(open(os.path.join(JOBS, f'{job_id}.json'), encoding='utf8'))
    log = open(j['log'], encoding='utf8', errors='replace').read().splitlines()
    running = _alive(j['pid'])
    failed = any(('Traceback' in l or 'Error' in l) for l in log[-40:]) and not running
    rep = None
    for o in j['outputs']:
        q = os.path.join(os.path.splitext(o)[0] + '_work', 'BAO_CAO_QC.md')
        if os.path.exists(q): rep = open(q, encoding='utf8').read()[:4000]
    return {'job_id': job_id, 'kind': j['kind'], 'state': 'running' if running else ('failed' if failed else 'done'),
            'elapsed_s': round(time.time() - j['start']), 'outputs': {o: os.path.exists(o) for o in j['outputs']},
            'log_tail': log[-tail:], 'qc_report': rep}


@mcp.tool()
def job_list(limit: int = 15) -> list:
    """Recent jobs (newest first) with their state."""
    ids = sorted([f[:-5] for f in os.listdir(JOBS) if f.endswith('.json')], reverse=True)[:limit]
    out = []
    for i in ids:
        j = json.load(open(os.path.join(JOBS, f'{i}.json'), encoding='utf8'))
        out.append({'job_id': i, 'kind': j['kind'], 'running': _alive(j['pid']), 'outputs': j['outputs']})
    return out


# ------------------------------------------------------------------ quick tools
@mcp.tool()
def video_probe(path: str) -> dict:
    """Stream facts of a video: size, fps, VFR, duration, and the REAL content frame rate (detects 24p padded to 30p)."""
    import fps_convert
    return fps_convert.probe(path)


@mcp.tool()
def video_qc(path: str, judder: bool = True) -> dict:
    """Technical QC: stray frames, flashes, black stretches, frozen/duplicate frames, per-shot judder & cadence, LUFS/true peak,
    letterbox. Returns the summary, findings and the 5 worst-judder shots."""
    from probe_qc import qc
    r = qc(path, judder)
    worst = sorted([s for s in r['shots'] if s.get('judder') is not None], key=lambda s: -s['judder'])[:5]
    return {'info': r['info'], 'summary': r['summary'], 'findings': r['findings'], 'worst_judder_shots': worst, 'shots': len(r['shots'])}


@mcp.tool()
def contact_sheet(film: str, out_jpg: str) -> str:
    """Contact sheet (3 frames per shot) for eye review. Read the image afterwards."""
    r = subprocess.run([sys.executable, os.path.join(HERE, 'contact_sheet.py'), film, out_jpg], capture_output=True, text=True, env=ENV)
    return r.stdout + r.stderr[-500:]


@mcp.tool()
def voices_suggest(muc_dich: str = 'doanh_nghiep', gioi_tinh: str = '', vung: str = '', am_sac: str = '', top: int = 4) -> list:
    """Suggest Vietnamese voices for a PURPOSE (doanh_nghiep, thoi_su, tai_lieu, quang_cao, mang_xa_hoi, huong_dan, sang_trong,
    tre_em, su_kien), optional gender (nam/nu), region (bac/trung/nam), timbre (tram/vua/sang). Ranked by measured accuracy,
    pitch and pace. Offer several to the user; never force one."""
    import voices
    return [{'voice': n, 'score': s, 'why': w} for n, s, w in voices.suggest(muc_dich, gioi_tinh or None, vung or None, top, am_sac or None)]


@mcp.tool()
def voices_catalogue() -> list:
    """All voices with measured profile (accuracy, F0, syllables/s, gender, region, style) if `voices.py profile` was run."""
    import voices
    p = voices.load_profiles()
    return list(p.values()) if p else voices.catalogue()


@mcp.tool()
def pronunciation_preview(text: str, extra_dict_json: str = '') -> str:
    """Show how the pronunciation dictionary + text normaliser will rewrite a line before TTS."""
    import accuracy, tts_vi
    d = accuracy.load_dict(json.loads(extra_dict_json) if extra_dict_json else None)
    return tts_vi.normalize(accuracy.apply_dict(text, d))


@mcp.tool()
def shot_search(library_json: str, query_english: str, top: int = 8, avoid_graphics: bool = True) -> list:
    """Search a footage library (built with shot_select.py scan --clip) by an ENGLISH description. Returns file, in/out,
    match, quality score and 'graphic' (likelihood of slide/infographic/burned-in text)."""
    import shot_select
    lib = json.load(open(library_json, encoding='utf8'))
    if any(s.get('clip') and 'graphic' not in s for s in lib): lib = shot_select.graphic_scores(lib)
    res = shot_select.search(lib, query_english, top * 3)
    if avoid_graphics: res = [s for s in res if s.get('graphic', 0) < 0.5] or res
    return [{k: s.get(k) for k in ('file', 'start', 'end', 'dur', 'match', 'score', 'graphic', 'judder', 'shake_px', 'faces')} for s in res[:top]]


# ------------------------------------------------------------------ long tools (jobs)
def _py(script): return os.path.join(HERE, script)


@mcp.tool()
def make_video(project_json: str, out_mp4: str, no_subs: bool = False, capcut_draft: str = '') -> dict:
    """Build a finished film from a project/storyboard JSON (see templates/project_make.json): voices (auto by purpose),
    accuracy guard, scenes (video/photo/colour/HTML motion/auto-picked), transitions, music, LUFS, subtitles, QC report."""
    a = [_py('autovideo.py'), 'make', project_json, '--out', out_mp4] + (['--no-subs'] if no_subs else []) + (['--capcut', capcut_draft] if capcut_draft else [])
    return _start('make', a, [out_mp4])


@mcp.tool()
def revoice_video(video: str, script: str, out_mp4: str, voice: str = 'auto', muc_dich: str = 'doanh_nghiep', gioi_tinh: str = '',
                  vung: str = '', burn_subs: bool = False, phat_am_json: str = '') -> dict:
    """Replace the narration of an existing video: separate music, auto-align sentences on the old voice, new voice
    (name | edge:<ShortName> | clone:<sample.wav> | auto by purpose), accuracy guard, original music kept, QC."""
    a = [_py('autovideo.py'), 'revoice', video, '--script', script, '--out', out_mp4, '--voice', voice, '--muc-dich', muc_dich]
    if gioi_tinh: a += ['--gioi-tinh', gioi_tinh]
    if vung: a += ['--vung', vung]
    if burn_subs: a.append('--subs')
    if phat_am_json: a += ['--phat-am', phat_am_json]
    return _start('revoice', a, [out_mp4])


@mcp.tool()
def subtitle_video(video: str, script: str, out_mp4: str) -> dict:
    """Burn word-timed subtitles (and write .srt) aligned on the video's own speech."""
    return _start('subs', [_py('autovideo.py'), 'subs', video, '--script', script, '--out', out_mp4], [out_mp4])


@mcp.tool()
def convert_fps(src: str, out_mp4: str, fps: float, start: float = -1, dur: float = -1, slowmo: float = 1.0, shutter: float = 180,
                engine: str = 'rife') -> dict:
    """Any frame rate 24/25/30/50/60/120 both ways, slow motion, 180-degree motion blur; removes 24p-in-30p padding.
    Uses RIFE (GPU) for non-integer ratios so pans stay even."""
    a = [_py('fps_convert.py'), 'convert', src, out_mp4, '--fps', str(fps), '--slowmo', str(slowmo), '--shutter', str(shutter), '--engine', engine]
    if start >= 0: a += ['--start', str(start)]
    if dur > 0: a += ['--dur', str(dur)]
    return _start('fps', a, [out_mp4])


@mcp.tool()
def reframe_video(src: str, out_mp4: str, aspect: str = '9:16', size: str = '1080x1920', mode: str = 'auto') -> dict:
    """Smart reframe (16:9 -> 9:16 / 1:1 / 4:5): follows faces and the main subject like a camera operator (locked-off when
    still, smooth speed-limited pans otherwise). mode: auto | static | follow."""
    return _start('reframe', [_py('camera.py'), 'reframe', src, out_mp4, '--aspect', aspect, '--size', size, '--mode', mode], [out_mp4])


@mcp.tool()
def stabilize_video(src: str, out_mp4: str, strength: int = 30, tripod: bool = False) -> dict:
    """Two-pass vidstab stabilisation (tripod=True locks the frame)."""
    a = [_py('camera.py'), 'stabilize', src, out_mp4, '--strength', str(strength)] + (['--tripod'] if tripod else [])
    return _start('stabilize', a, [out_mp4])


@mcp.tool()
def motion_graphic(html: str, out_mp4: str, dur: float, params_json: str = '{}', fps: float = 25, size: str = '1920x1080') -> dict:
    """Render an HTML motion graphic (window.seek(t) contract, e.g. templates/motion/route_map.html) to MP4 with adaptive
    sub-frame motion blur. Run motion_stills first to look at it."""
    return _start('motion', [_py('motion_html.py'), 'render', html, out_mp4, '--dur', str(dur), '--fps', str(fps), '--size', size,
                             '--params', params_json], [out_mp4])


@mcp.tool()
def motion_stills(html: str, out_png: str, times: list[float], params_json: str = '{}', size: str = '1920x1080') -> str:
    """Stills of an HTML motion graphic at given times (look before rendering)."""
    r = subprocess.run([sys.executable, _py('motion_html.py'), 'stills', html, out_png, '--times'] + [str(t) for t in times] +
                       ['--size', size, '--params', params_json], capture_output=True, text=True, env=ENV)
    return r.stdout + r.stderr[-800:]


@mcp.tool()
def critic_kit(film: str, project_json: str = '', facts_md: str = '') -> dict:
    """Build the independent-review kit (contact/phone/strips + hard checks + rubric). Then give the folder to a FRESH
    read-only agent to score 1-10 per category (default verdict: revise) - judge != builder."""
    a = [_py('critic.py'), film] + (['--project', project_json] if project_json else []) + (['--facts', facts_md] if facts_md else [])
    return _start('critic', a, [os.path.join(os.path.splitext(film)[0] + '_critic', 'CRITIC.md')])


@mcp.tool()
def voice_samples(text_lines: list[str], voices: list[str], out_dir: str) -> dict:
    """Synthesise the user's own lines with several voices (with listen-back + automatic re-takes) for the user to choose."""
    os.makedirs(out_dir, exist_ok=True)
    jp = os.path.join(out_dir, 'mau_loi.json'); json.dump(text_lines, open(jp, 'w', encoding='utf8'), ensure_ascii=False)
    code = ("import sys,json; sys.path.insert(0,r'%s'); import accuracy; L=json.load(open(r'%s',encoding='utf8'))\n"
            "for v in %r:\n    fs, rows = accuracy.guarded_synth(L, v, r'%s')\n    print(v, [r['acc'] for r in rows], fs)" % (HERE, jp, voices, out_dir))
    return _start('voices', ['-c', code], [out_dir])


if __name__ == '__main__':
    mcp.run()
