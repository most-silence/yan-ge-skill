# tools/ · 转写工具链

> 已跑通。本文件记录可复现的配置，避免重踩坑。

- **状态**：🟢 可用
- **实测速度**：**6.7–8.2 倍实时**（Ryzen 7 7840H，int8，8 线程）
- **流量**：0（模型已本地化，全程 `HF_HUB_OFFLINE=1`）

---

## 环境

| 项 | 值 |
|---|---|
| venv | `tools/.venv`（Python 3.11） |
| faster-whisper | 1.2.1 |
| **ctranslate2** | **4.5.0**（⚠️ 4.8.3 会崩，必须降级） |
| setuptools | **<81**（4.5.0 依赖 pkg_resources） |
| PyAV | 18.1.0（免系统 ffmpeg） |
| **onnxruntime** | **1.19.2**（⚠️ 1.31.0 在本机 import 即崩 0xC0000005） |
| PyMuPDF | 1.26.7（PDF 渲染，免 poppler） |
| RapidOCR | 3.x（onnxruntime 后端，免系统 tesseract） |
| pypdf | 6.4.2（纯 Python 文本 PDF 提取） |
| 模型 | `small`，463.7 MB，已在 `~/.cache/huggingface/hub` |

---

## 崩溃排查结论（重要）

**本机（Zen4 / Ryzen 7 7840H）有两个包会崩 0xC0000005，都是版本问题，不是代码问题：**

### 1. ctranslate2 4.8.3

加载任何模型都崩。已排除：模型文件损坏、PATH 里的 Anaconda DLL、`KMP_DUPLICATE_LIB_OK`、`CT2_FORCE_CPU_ISA`、`float32`/`int8` 精度。

**解法**：降级到 `ctranslate2==4.5.0` + `setuptools<81`。

**另一个坑**：`transcribe()` 参数组合也会触发同样的崩溃。

| 参数 | 结果 |
|---|---|
| `beam_size=5` + `vad_filter=True` + `temperature=[0,0.2,0.4]` | ❌ 崩溃 |
| `beam_size=1` + `vad_filter=False`（不传 temperature） | ✅ 正常 |

### 2. onnxruntime 1.31.0

`import onnxruntime` 直接崩。这是 PyMuPDF 和 RapidOCR 双双失败的**共同根因**——表面上看是 PDF 库的问题，实际是 ORT 的。

试过无效的：`OMP_NUM_THREADS`、`ORT_DISABLE_ALL_OPTIMIZATIONS`、`ORT_SEQUENTIAL_EXECUTION`。

**解法**：`pip install "onnxruntime==1.19.2"`。

> ⚠️ **这两个版本锁不能动**：`ctranslate2==4.5.0`、`onnxruntime==1.19.2`、`setuptools<81`。
> 升级任何一个都会让整条工具链崩掉。新建 venv 时先装这三个。

---

## 脚本

| 脚本 | 用途 |
|---|---|
| `extract_audio.py` | 视频 → 16kHz 单声道 mp3（PyAV，无 ffmpeg 依赖） |
| `transcribe_srt.py` | mp3 → SRT + 带时间戳 txt（内置术语纠错表） |
| `extract_frames.py` | 视频 → 关键帧 PNG + `_manifest.csv`（指代词密度触发） |
| `extract_pdf.py` | 文本 PDF → txt（pypdf；`--probe` 判定文本型/扫描型） |
| `ocr_pdf.py` | 扫描 PDF → txt（PyMuPDF 渲染 + RapidOCR，可断点续跑） |
| `probe_books.py` | 书籍结构探查（章节、行数、字符量） |

### PDF 处理决策树

```
拿到 PDF
   ↓
extract_pdf.py --probe        # 看每页字符数
   ↓
字符/页 > 300 ? ──是──→ extract_pdf.py   （文本型，秒级）
   │
   否
   ↓
ocr_pdf.py --dpi 200          （扫描型，约 3.5–4.5 秒/页）
```

**实测**：
| 书 | 页数 | 类型 | 耗时 | 产出 |
|---|---:|---|---:|---|
| 《笑傲牛熊》 | 315 | 文本型 | 秒级 | 421 KB / 164k 字 |
| 《股票魔法师》 | 54 | 文本型 | 秒级 | 73 KB / 27k 字 |
| 《手把手教你读财报》 | 146 | 扫描型 | 628 s | 425 KB / 162k 字 |
| 《股市操练大全4》 | 446 | 扫描型 | 约 26 min | 进行中 |

### 标准命令

```powershell
$env:PYTHONIOENCODING='utf-8'
$env:HF_HUB_OFFLINE='1'          # 强制离线，防止偷跑流量
$py='E:\AIProjetct\Nothing\眼哥\tools\.venv\Scripts\python.exe'

# 1. 抽音频
& $py tools\extract_audio.py `
    --input 'sources\02-抖音视频\*.mp4' `
    --outdir 'sources\00-原始音频'

# 2. 转写
& $py tools\transcribe_srt.py `
    --input 'sources\00-原始音频\*.mp3' `
    --outdir 'sources\02-抖音视频' `
    --model small
```

---

## 已知缺陷

| 问题 | 影响 | 处理 |
|---|---|---|
| 专有名词误识别 | 「眼哥」→「演歌/衍哥」 | 已加 `FIXES` 纠错表 + `initial_prompt` |
| 断句碎 | 单句 1–3 秒，语义不完整 | 蒸馏时按段落重组，不改原文 |
| 无标点 | 全靠语感断句 | 保持原样，不润色 |
| 无说话人分离 | 单人节目影响小 | 可接受 |

> **纠错表要持续补**：每发现一个新的高频错词就加进 `transcribe_srt.py` 的 `FIXES`，然后重跑（已存在的文件会跳过，需要先删）。
