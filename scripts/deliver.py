"""Delivery presets + music beats.

  python deliver.py list
  python deliver.py export MASTER.mp4 PRESET OUT.mp4 [--reframe]       # e.g. youtube_1080, tiktok, master_prores
  python deliver.py beats MUSIC.wav [--json beats.json]                  # tempo, beats, downbeats (for cutting on the beat)

--reframe: for vertical/square presets use camera.py reframe (tracks the subject) instead of a centre crop.
Importable: PRESETS, export(...), beats(path) -> (tempo, beat_times, downbeat_times), snap(t, beats, tol).
"""
import argparse, json, os, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))

PRESETS = {
    # name: (W, H, fps or None=keep, video args, audio LUFS, TP, note)
    'youtube_1080': (1920, 1080, None, ['-c:v', 'libx264', '-crf', '16', '-preset', 'slow', '-profile:v', 'high'], -14, -1.0, 'YouTube 1080p'),
    'youtube_4k':   (3840, 2160, None, ['-c:v', 'libx264', '-crf', '17', '-preset', 'slow', '-profile:v', 'high'], -14, -1.0, 'YouTube 2160p'),
    'facebook':     (1920, 1080, 30, ['-c:v', 'libx264', '-crf', '18', '-preset', 'slow', '-maxrate', '12M', '-bufsize', '24M'], -14, -1.0, 'Facebook ngang'),
    'tiktok':       (1080, 1920, 30, ['-c:v', 'libx264', '-crf', '18', '-preset', 'slow', '-maxrate', '15M', '-bufsize', '30M'], -14, -1.0, 'TikTok/Reels/Shorts 9:16'),
    'reels':        (1080, 1920, 30, ['-c:v', 'libx264', '-crf', '18', '-preset', 'slow'], -14, -1.0, 'Instagram Reels 9:16'),
    'square':       (1080, 1080, 30, ['-c:v', 'libx264', '-crf', '18', '-preset', 'slow'], -14, -1.0, '1:1'),
    'feed_4x5':     (1080, 1350, 30, ['-c:v', 'libx264', '-crf', '18', '-preset', 'slow'], -14, -1.0, '4:5 feed'),
    'trinh_chieu':  (1920, 1080, None, ['-c:v', 'libx264', '-crf', '14', '-preset', 'slow'], -16, -1.5, 'Hội trường / sự kiện'),
    'phat_song':    (1920, 1080, 25, ['-c:v', 'libx264', '-crf', '14', '-preset', 'slow', '-x264-params', 'nal-hrd=cbr', '-b:v', '20M', '-minrate', '20M', '-maxrate', '20M', '-bufsize', '20M'], -23, -1.0, 'Phát sóng EBU R128'),
    'master_prores':(None, None, None, ['-c:v', 'prores_ks', '-profile:v', '3', '-pix_fmt', 'yuv422p10le'], -16, -1.0, 'Master ProRes 422 HQ (.mov)'),
    'hevc_nvenc':   (None, None, None, ['-c:v', 'hevc_nvenc', '-preset', 'p7', '-cq', '19', '-tag:v', 'hvc1'], -14, -1.0, 'HEVC GPU nhỏ gọn'),
    'preview':      (1280, 720, None, ['-c:v', 'libx264', '-crf', '24', '-preset', 'fast'], -14, -1.0, 'Bản xem nhanh < 30 MB/phút'),
}


def export(src, preset, out, reframe=False):
    if os.path.exists(out): raise SystemExit(f'{out} đã tồn tại')
    W, H, fps, vargs, lufs, tp, _ = PRESETS[preset]
    vin = src
    if W and reframe and (W / H) < 1.5:
        sys.path.insert(0, HERE); import camera
        vin = os.path.splitext(out)[0] + '_reframe_tmp.mp4'
        camera.reframe(src, vin, f'{W}:{H}', f'{W}x{H}')
    vf = []
    if W and vin == src: vf += [f'scale={W}:{H}:force_original_aspect_ratio=increase:flags=lanczos', f'crop={W}:{H}', 'setsar=1']
    if fps: vf.append(f'fps={fps}')
    pix = [] if '-pix_fmt' in vargs else ['-pix_fmt', 'yuv420p']
    gop = ['-g', str(int(2 * (fps or 25)))] if 'prores' not in preset else []
    cmd = ['ffmpeg', '-v', 'error', '-y', '-i', vin] + (['-i', src, '-map', '0:v', '-map', '1:a?'] if vin != src else []) + \
          (['-vf', ','.join(vf)] if vf else []) + vargs + pix + gop + \
          ['-af', f'loudnorm=I={lufs}:TP={tp}:LRA=11', '-c:a', 'pcm_s24le' if 'prores' in preset else 'aac', '-b:a', '320k', '-ar', '48000']
    if out.lower().endswith('.mp4'): cmd += ['-movflags', '+faststart']
    subprocess.run(cmd + [out], check=True)
    if vin != src: os.remove(vin)
    print(f'{preset} -> {out}')


def beats(path):
    import librosa, numpy as np
    y, sr = librosa.load(path, sr=22050, mono=True)
    tempo, bf = librosa.beat.beat_track(y=y, sr=sr, trim=False)
    bt = librosa.frames_to_time(bf, sr=sr)
    onset = librosa.onset.onset_strength(y=y, sr=sr)
    strength = onset[np.clip(bf, 0, len(onset) - 1)] if len(bf) else np.array([])
    # downbeats: phase of 4 with the strongest average onset
    ph = max(range(4), key=lambda p: strength[p::4].mean() if len(strength[p::4]) else 0) if len(bt) >= 8 else 0
    return float(np.atleast_1d(tempo)[0]), [round(float(t), 3) for t in bt], [round(float(t), 3) for t in bt[ph::4]]


def snap(t, grid, tol=0.35):
    if not grid: return t
    c = min(grid, key=lambda g: abs(g - t)); return c if abs(c - t) <= tol else t


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest='cmd', required=True)
    sp.add_parser('list')
    e = sp.add_parser('export'); e.add_argument('src'); e.add_argument('preset'); e.add_argument('out'); e.add_argument('--reframe', action='store_true')
    b = sp.add_parser('beats'); b.add_argument('music'); b.add_argument('--json')
    a = ap.parse_args()
    if a.cmd == 'list':
        for k, v in PRESETS.items(): print(f'{k:14s} {v[0] or "giữ"}x{v[1] or "giữ"} fps {v[2] or "giữ"}  {v[4]} LUFS  {v[6]}')
    elif a.cmd == 'export': export(a.src, a.preset, a.out, a.reframe)
    else:
        t, bt, db = beats(a.music)
        print(f'tempo {t:.1f} BPM, {len(bt)} beats, {len(db)} downbeats; first downbeats {db[:6]}')
        if a.json: json.dump({'tempo': t, 'beats': bt, 'downbeats': db}, open(a.json, 'w'))


if __name__ == '__main__':
    main()
