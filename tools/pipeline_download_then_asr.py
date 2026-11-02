"""pipeline_download_then_asr.py — 下载完成后自动启动 ASR 全量转写。

链式流水线（挂一个后台任务即可过夜）：
  1. 等 download_audio.py --loop 把 364 集全部下完（audio/ 文件数 >= urls.json 条数）
  2. 下载进程退出后，自动调用 transcribe.py 逐集转写（断点：已有 .txt 跳过）
  3. 全程写 pipeline.log，任何一步可见进度

用法：python pipeline_download_then_asr.py
"""
import json
import os
import subprocess
import sys
import time
from pathlib import Path

BASE = Path(r"E:\AIProjetct\Nothing\眼哥\sources\00-原始素材\earsonme")
TOOL = Path(r"E:\AIProjetct\Nothing\眼哥\tools")
PY = TOOL / ".venv" / "Scripts" / "python.exe"
OUTDIR = Path(r"E:\AIProjetct\Nothing\眼哥\sources\05-播客转写\audio_txt")
LOG = TOOL / "pipeline.log"

MODEL = "medium"          # 与此前 4.1x realtime 测试一致
BEAM = "1"


def log(msg):
    line = f"[{time.strftime('%m-%d %H:%M:%S')}] {msg}"
    print(line, flush=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def main():
    log("== 流水线启动：等待下载完成 ==")
    while True:
        urls = json.loads((BASE / "urls.json").read_text(encoding="utf-8"))
        have = {f for f in os.listdir(BASE / "audio") if f.endswith(".m4a")}
        log(f"下载进度 {len(have)}/{len(urls)}")
        if len(have) >= len(urls):
            break
        # 下载进程若已退出且没下完，重启它
        alive = False
        out = subprocess.run(
            ["tasklist", "/FI", "IMAGENAME eq python.exe", "/FO", "CSV", "/NH"],
            capture_output=True, text=True).stdout
        if "download_audio" in out or "python.exe" in out:
            # tasklist 不含命令行，需要再查一次命令行
            out2 = subprocess.run(
                ["powershell", "-NoProfile", "-Command",
                 "Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | "
                 "Select-Object -ExpandProperty CommandLine"],
                capture_output=True, text=True).stdout
            alive = "download_audio.py" in out2
        if not alive:
            log("下载进程不在了，重启 download_audio.py --loop")
            subprocess.Popen([str(PY), "-u", "-X", "utf8", "download_audio.py", "--loop"], cwd=str(TOOL))
        time.sleep(120)

    log("== 下载完成，启动 ASR 全量转写 ==")
    env = dict(os.environ, PYTHONIOENCODING="utf-8", HF_HUB_OFFLINE="1")
    r = subprocess.run(
        [str(PY), "-u", "-X", "utf8", "transcribe.py",
         "--input", str(BASE / "audio" / "*.m4a"),
         "--outdir", str(OUTDIR),
         "--model", MODEL, "--beam-size", BEAM],
        cwd=str(TOOL), env=env)
    log(f"== ASR 结束，exit={r.returncode} ==")


if __name__ == "__main__":
    main()
