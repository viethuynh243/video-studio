"""Place voice lines at their script times, process the voice, duck the music, normalise loudness, mux onto video.

  python voice_mix.py --script script.json --voice-dir DIR --voice-prefix ThienMinh --music music.wav \
                      --video VIDEO.mp4 --out OUT.mp4 [--lufs -16] [--duck-ratio 5] [--max-speedup 1.08] [--slow 1.0]

script.json : [[start, end, "text"], ...] (seconds on the video timeline; "end" = end of the slot for that line)
voice files : DIR/<prefix>_<i>.wav (e.g. from tts_vi.py). Silence is trimmed; a line longer than its slot is sped up
              (atempo) up to --max-speedup, beyond that a warning is printed (rewrite the line instead).
--slow 0.95 : slow every line slightly (rubberband, formant preserved) for a calmer delivery when slots allow.
Writes OUT.mp4 (video stream copied) plus OUT_voice.wav (voice stem) and OUT_mix.wav next to it.
Importable: mix_voice(lines, voice_files, video, out, music=None, ...) -> list of (start, end) actually used per line.
"""
import argparse, json, os, subprocess
import numpy as np
import soundfile as sf

SR = 48000
CHAIN = ('highpass=f=75,equalizer=f=180:t=q:w=1.2:g=1.5,equalizer=f=3200:t=q:w=1.0:g=1.5,deesser=i=0.35,'
         'acompressor=threshold=-20dB:ratio=2.5:attack=8:release=120:makeup=2,loudnorm=I=-17:TP=-2:LRA=6')
TRIM = 'silenceremove=start_periods=1:start_threshold=-50dB,areverse,silenceremove=start_periods=1:start_threshold=-50dB,areverse'


def dur(p):
    return float(subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', p],
                                capture_output=True, text=True).stdout)


def ff(args):
    r = subprocess.run(['ffmpeg', '-v', 'error', '-y'] + args, capture_output=True, text=True, encoding='utf8', errors='replace')
    if r.returncode: raise RuntimeError(r.stderr[-800:])


def prepare_line(src, tmp, i, slot, slow=1.0, max_speedup=1.08):
    """Trim, optional slow-down, fit into slot (speed-up), voice chain. Returns (wav_path, speed_factor)."""
    t0 = os.path.join(tmp, f't{i}.wav')
    try:
        ff(['-i', src, '-af', TRIM + (f',rubberband=tempo={slow}:formant=preserved' if slow != 1.0 else ''), '-ar', str(SR), '-ac', '1', t0])
    except RuntimeError:
        ff(['-i', src, '-af', TRIM + (f',atempo={slow}' if slow != 1.0 else ''), '-ar', str(SR), '-ac', '1', t0])
    d, k = dur(t0), 1.0
    if slot and d > slot:
        k = d / slot
        if k > max_speedup: print(f'WARNING line {i}: {d:.2f}s in a {slot:.2f}s slot needs x{k:.2f} - shorten the text')
        k = min(k, max_speedup)
    t1 = os.path.join(tmp, f'v{i}.wav')
    ff(['-i', t0, '-af', (f'atempo={k:.4f},' if k > 1 else '') + CHAIN + f',aresample={SR}', '-ac', '1', t1])
    return t1, k


def mix_voice(lines, voice_files, video, out, music=None, lufs=-16.0, duck_ratio=5.0, max_speedup=1.08, slow=1.0,
              lead=0.05, music_gain=1.0, music_fade_out=2.0, total=None):
    """lines: [(start, end, text)], voice_files: [wav or None]. Writes out (mp4), <out>_voice.wav, <out>_mix.wav."""
    T = total or dur(video)
    base = os.path.splitext(out)[0]; tmp = base + '_tmp'; os.makedirs(tmp, exist_ok=True)
    voice = np.zeros(int(T * SR) + SR, np.float32)
    used = []
    for i, ((st, en, _), src) in enumerate(zip(lines, voice_files)):
        if not src: used.append(None); continue
        p, k = prepare_line(src, tmp, i, en - st - lead - 0.1, slow, max_speedup)
        x, _ = sf.read(p, dtype='float32')
        fd = int(0.02 * SR); x[:fd] *= np.linspace(0, 1, fd); x[-fd:] *= np.linspace(1, 0, fd)
        j = int((st + lead) * SR); voice[j:j + len(x)] += x[:max(0, len(voice) - j)]
        used.append((st + lead, st + lead + len(x) / SR))
        print(f'line {i}: {st + lead:.2f}-{st + lead + len(x) / SR:.2f}s (slot ends {en:.2f}){" sped x%.3f" % k if k > 1 else ""}')
    vstem = base + '_voice.wav'; sf.write(vstem, voice[:int(T * SR)], SR)
    mix = base + '_mix.wav'
    if music:
        fo = max(0.0, T - music_fade_out)
        ff(['-stream_loop', '-1', '-i', music, '-i', vstem, '-filter_complex',
            f'[0]atrim=0:{T:.3f},asetpts=N/SR/TB,aresample={SR},volume={music_gain},afade=t=out:st={fo:.3f}:d={music_fade_out}[m];'
            f'[1]aresample={SR},asplit[v1][v2];'
            f'[m][v1]sidechaincompress=threshold=0.02:ratio={duck_ratio}:attack=60:release=700:makeup=1[d];'
            f'[d][v2]amix=inputs=2:normalize=0:duration=first,loudnorm=I={lufs}:TP=-1.5:LRA=9[o]',
            '-map', '[o]', '-ac', '2', '-ar', str(SR), '-t', f'{T:.3f}', mix])
    else:
        ff(['-i', vstem, '-af', f'loudnorm=I={lufs}:TP=-1.5', '-ac', '2', '-ar', str(SR), mix])
    ff(['-i', video, '-i', mix, '-map', '0:v', '-map', '1:a', '-c:v', 'copy', '-c:a', 'aac', '-b:a', '256k',
        '-movflags', '+faststart', '-t', f'{T:.3f}', out])
    return used


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--script', required=True); ap.add_argument('--voice-dir', required=True)
    ap.add_argument('--voice-prefix', required=True); ap.add_argument('--music'); ap.add_argument('--video', required=True)
    ap.add_argument('--out', required=True); ap.add_argument('--lufs', type=float, default=-16)
    ap.add_argument('--duck-ratio', type=float, default=5); ap.add_argument('--max-speedup', type=float, default=1.08)
    ap.add_argument('--slow', type=float, default=1.0); ap.add_argument('--lead', type=float, default=0.05)
    ap.add_argument('--music-gain', type=float, default=1.0)
    a = ap.parse_args()
    if os.path.exists(a.out): raise SystemExit(f'{a.out} exists - choose a new name (never overwrite deliverables)')
    S = json.load(open(a.script, encoding='utf8'))
    S = [(x['start'], x['end'], x['text']) if isinstance(x, dict) else tuple(x) for x in S]
    files = [os.path.join(a.voice_dir, f'{a.voice_prefix}_{i}.wav') for i in range(len(S))]
    mix_voice(S, files, a.video, a.out, a.music, a.lufs, a.duck_ratio, a.max_speedup, a.slow, a.lead, a.music_gain)
    print('done', a.out)


if __name__ == '__main__':
    main()
