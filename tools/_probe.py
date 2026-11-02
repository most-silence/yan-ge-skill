import sys, os
from faster_whisper import WhisperModel
ct = sys.argv[1]
m = WhisperModel("small", device="cpu", compute_type=ct, cpu_threads=8)
print("LOADED", ct)
