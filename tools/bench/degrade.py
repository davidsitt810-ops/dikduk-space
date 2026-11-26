"""A take as a phone in a room would send it — exam_voice.py's DEGRADE, as a module for the other runners (the same
lines; exam_voice.py keeps its own copy for now): a small room's early echoes, pink noise under the singing, Opus.
  parts('phone') -> room, snr=20, kbps=24      parts('noisy') -> room, snr=10, kbps=24      or 'room,snr=15,kbps=64' ...
  degrade(wav bytes, seed, DG) -> wav bytes (16 kHz mono)"""
import subprocess

def parts(spec):
    DG = {}
    for part in {'phone': 'room,snr=20,kbps=24', 'noisy': 'room,snr=10,kbps=24'}.get(spec, spec).split(','):
        k, _, v = part.partition('='); DG[k] = float(v) if v else 1.0
    assert DG and set(DG) <= {'room', 'snr', 'kbps'}, f'phone, noisy, or parts of room,snr=<dB>,kbps=<n>: {spec}'
    return DG

def degrade(wav, seed, DG):
    import numpy as np
    pcm = subprocess.run(['ffmpeg', '-v', 'error', '-i', 'pipe:0', '-ac', '1', '-ar', '16000', '-f', 's16le', 'pipe:1'], input=wav, capture_output=True, timeout=120).stdout
    x = np.frombuffer(pcm, dtype=np.int16).astype(np.float32); sr = 16000
    if len(x) < sr // 10: return wav
    y = x.copy()
    if DG.get('room'):
        for ms, g in ((11, .35), (23, .22), (37, .14), (53, .08)):   # early reflections of a small room
            d = int(sr * ms / 1000); y[d:] += g * x[:-d]
    if 'snr' in DG:
        n = len(y); rng = np.random.default_rng(seed); f = np.fft.rfftfreq(n, 1 / sr)
        spec = rng.normal(size=len(f)) + 1j * rng.normal(size=len(f)); spec[0] = 0; spec[1:] /= np.sqrt(f[1:])   # pink: power 1/f
        noise = np.fft.irfft(spec, n).astype(np.float32)
        e = (y[: n // 320 * 320].reshape(-1, 320) ** 2).mean(1); act = e[e >= .2 * np.percentile(e, 95)]   # the singing's own level
        y = y + noise * np.sqrt(float(act.mean()) / max(1e-9, float((noise ** 2).mean())) / 10 ** (DG['snr'] / 10))
    y = y * min(1.0, 30000 / max(1.0, float(np.abs(y).max())))
    raw = np.clip(y, -32768, 32767).astype(np.int16).tobytes()
    if 'kbps' in DG:
        raw = subprocess.run(['ffmpeg', '-v', 'error', '-f', 's16le', '-ar', '16000', '-ac', '1', '-i', 'pipe:0', '-c:a', 'libopus', '-b:a', f'{int(DG["kbps"])}k', '-f', 'ogg', 'pipe:1'],
                             input=raw, capture_output=True, timeout=120).stdout
        return subprocess.run(['ffmpeg', '-v', 'error', '-i', 'pipe:0', '-ac', '1', '-ar', '16000', '-f', 'wav', 'pipe:1'], input=raw, capture_output=True, timeout=120).stdout
    return subprocess.run(['ffmpeg', '-v', 'error', '-f', 's16le', '-ar', '16000', '-ac', '1', '-i', 'pipe:0', '-f', 'wav', 'pipe:1'], input=raw, capture_output=True, timeout=120).stdout
