"""照剪輯表把要留的段落接起來，保留原片的幀數（例如 60 幀），段落之間可以加很短的淡入淡出。

OpenMontage 的剪接工具（VideoCompose）固定輸出 30 幀；老闆要 60 幀時改用這支。
- 每段各自剪成剛好整數格畫面，聲音先用無壓縮格式保存、長度和畫面一樣，接起來才不會越來越不同步。
- `--xfade 秒數`：段落之間畫面交疊淡化、聲音交叉淡化（建議 0.1～0.15 秒），接點比較不會「跳」。
  不加就是直接接（硬切），每段頭尾聲音淡入淡出 15 毫秒避免「啪」聲。
- 一次最多處理 8 段再合併，長片、段落很多也不會把記憶體吃光。
- 會另外存一份「時間表」（輸出檔名 + .timeline.json）：每一段在成片裡從第幾秒開始、到第幾秒，
  字幕和特效的時間直接照這份算，不用猜。

用法：python 剪接.py 原片.mp4 保留段落.json 輸出.mp4 [--xfade 0.12]
保留段落.json：[[開始秒, 結束秒], [開始秒, 結束秒], ...]，照播放順序排。
"""

import json
import os
import subprocess
import sys
import tempfile
from fractions import Fraction

FADE = 0.015
GROUP = 8


def probe(path: str, entry: str) -> str:
    return subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", entry, "-of", "csv=p=0", path],
        capture_output=True, text=True, check=True,
    ).stdout.strip()


def cut_part(src: str, a: float, b: float, fps: Fraction, out: str, fade: bool) -> float:
    frames = max(int(round((b - a) * fps)), 1)
    d = float(frames / fps)
    af = f"atrim=0:{d:.6f},apad=whole_dur={d:.6f}"
    if fade:
        af += f",afade=t=in:d={FADE},afade=t=out:st={max(d - FADE, 0):.6f}:d={FADE}"
    subprocess.run(
        [
            "ffmpeg", "-v", "error", "-y", "-ss", f"{a:.3f}", "-i", src,
            "-map", "0:v:0", "-map", "0:a:0", "-r", str(fps), "-frames:v", str(frames),
            "-af", af, "-c:v", "libx264", "-preset", "medium", "-crf", "14", "-pix_fmt", "yuv420p",
            "-c:a", "pcm_s16le", "-ar", "48000", out,
        ],
        check=True,
    )
    return d


def join(parts: list[tuple[str, float]], out: str, fps: Fraction, xfade: float) -> float:
    """把幾段接成一段，回傳總長。xfade > 0 時段落交疊淡化。"""
    if xfade <= 0:
        listing = out + ".txt"
        with open(listing, "w", encoding="utf-8") as f:
            f.writelines(f"file '{p}'\n" for p, _ in parts)
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", listing, "-c", "copy", out], check=True)
        return sum(d for _, d in parts)
    inputs, chain, total = [], [], parts[0][1]
    for p, _ in parts:
        inputs += ["-i", p]
    v, a = "[0:v]", "[0:a]"
    for i, (_, d) in enumerate(parts[1:], start=1):
        off = total - xfade
        chain.append(f"{v}[{i}:v]xfade=transition=fade:duration={xfade}:offset={off:.6f}[v{i}]")
        chain.append(f"{a}[{i}:a]acrossfade=d={xfade}:c1=tri:c2=tri[a{i}]")
        v, a = f"[v{i}]", f"[a{i}]"
        total = off + d
    subprocess.run(
        [
            "ffmpeg", "-v", "error", "-y", *inputs, "-filter_complex", ";".join(chain),
            "-map", v, "-map", a, "-r", str(fps),
            "-c:v", "libx264", "-preset", "medium", "-crf", "14", "-pix_fmt", "yuv420p",
            "-c:a", "pcm_s16le", "-ar", "48000", out,
        ],
        check=True,
    )
    return total


def main(src: str, keep_path: str, dst: str, xfade: float = 0.0) -> None:
    with open(keep_path, encoding="utf-8") as f:
        keep = [(float(a), float(b)) for a, b in json.load(f)]
    fps = Fraction(probe(src, "stream=r_frame_rate"))
    with tempfile.TemporaryDirectory(dir=os.path.dirname(os.path.abspath(dst))) as tmp:
        parts = []
        for i, (a, b) in enumerate(keep):
            p = os.path.join(tmp, f"{i:04d}.mov")
            parts.append((p, cut_part(src, a, b, fps, p, fade=xfade <= 0)))

        # 每一段在成片裡的開始時間（交疊淡化時，後一段會往前疊 xfade 秒）
        timeline, t = [], 0.0
        for i, (_, d) in enumerate(parts):
            timeline.append({"index": i, "start": round(t, 3), "end": round(t + d, 3)})
            t += d - (xfade if xfade > 0 else 0)

        # 分組接，再把組接起來；組和組之間一樣交疊淡化
        groups = []
        for g in range(0, len(parts), GROUP):
            gp = os.path.join(tmp, f"g{g:04d}.mov")
            groups.append((gp, join(parts[g : g + GROUP], gp, fps, xfade)))
        whole = os.path.join(tmp, "whole.mov")
        join(groups, whole, fps, xfade) if len(groups) > 1 else os.replace(groups[0][0], whole)

        subprocess.run(
            ["ffmpeg", "-v", "error", "-y", "-i", whole, "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", dst],
            check=True,
        )
    with open(dst + ".timeline.json", "w", encoding="utf-8") as f:
        json.dump(timeline, f, ensure_ascii=False, indent=1)
    print(dst, f"{timeline[-1]['end']:.2f} 秒，{len(keep)} 段，交疊 {xfade} 秒")


if __name__ == "__main__":
    args = sys.argv[1:]
    x = 0.0
    if "--xfade" in args:
        k = args.index("--xfade")
        x = float(args[k + 1])
        args = args[:k] + args[k + 2 :]
    main(args[0], args[1], args[2], x)
