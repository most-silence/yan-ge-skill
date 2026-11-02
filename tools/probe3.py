import time, traceback
from faster_whisper import WhisperModel
src = r"E:\AIProjetct\Nothing\眼哥\sources\00-原始音频\video_关于均线系统的看法_1080p_top_0_2.mp3"
print("load...", flush=True)
m = WhisperModel("small", device="cpu", compute_type="int8", cpu_threads=8)
print("loaded", flush=True)
try:
    segs, info = m.transcribe(src, language="zh", beam_size=1, vad_filter=False)
    print("duration", info.duration, flush=True)
    n = 0
    for s in segs:
        n += 1
        if n <= 8:
            print(f"[{s.start:7.2f} -> {s.end:7.2f}] {s.text}", flush=True)
        if n >= 20: break
    print("OK segments", n, flush=True)
except Exception as e:
    print("EXC:", type(e).__name__, e, flush=True)
    traceback.print_exc()
