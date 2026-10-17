"""Separate a mixed soundtrack into voice and music with Demucs (htdemucs_ft), via the Python API
(the demucs CLI failed on this machine with a missing 'sphn' module).

  python demucs_split.py INPUT(.mp4/.wav) OUTDIR [--model htdemucs_ft] [--device cuda|cpu]

Writes OUTDIR/voice.wav (vocals) and OUTDIR/music.wav (drums+bass+other), 44.1 kHz stereo float.
"""
import argparse, os, subprocess, tempfile


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('inp'); ap.add_argument('outdir'); ap.add_argument('--model', default='htdemucs_ft')
    ap.add_argument('--device', default=None)
    a = ap.parse_args()
    import torch, soundfile as sf
    from demucs.pretrained import get_model
    from demucs.apply import apply_model
    dev = a.device or ('cuda' if torch.cuda.is_available() else 'cpu')
    os.makedirs(a.outdir, exist_ok=True)
    wav = os.path.join(tempfile.mkdtemp(), 'in.wav')
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', a.inp, '-vn', '-ac', '2', '-ar', '44100', wav], check=True)
    x, sr = sf.read(wav, dtype='float32', always_2d=True)
    t = torch.from_numpy(x.T)
    ref = t.mean(0); t = (t - ref.mean()) / (ref.std() + 1e-8)
    m = get_model(a.model); m.eval()
    with torch.no_grad():
        src = apply_model(m, t[None], device=dev, shifts=1, split=True, overlap=0.25, progress=True)[0]
    src = src * (ref.std() + 1e-8) + ref.mean()
    names = m.sources
    voc = src[names.index('vocals')]
    mus = sum(src[i] for i, n in enumerate(names) if n != 'vocals')
    sf.write(os.path.join(a.outdir, 'voice.wav'), voc.T.cpu().numpy(), sr)
    sf.write(os.path.join(a.outdir, 'music.wav'), mus.T.cpu().numpy(), sr)
    print('wrote', a.outdir, 'voice.wav music.wav on', dev)


if __name__ == '__main__':
    main()
