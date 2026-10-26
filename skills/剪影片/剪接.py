"""照剪輯表把要留的段落接起來，保留原片的幀數（例如 60 幀）。

OpenMontage 的剪接工具（VideoCompose）固定輸出 30 幀；老闆要 60 幀時改用這支。
每段各自重新編碼（剪點精準到每一格畫面，頭尾聲音淡入淡出 15 毫秒，避免接點有「啪」的雜音），
再直接接起來。一段一段做，長片、段落很多也不會把記憶體吃光。

用法：python 剪接.py 原片.mp4 保留段落.json 輸出.mp4
保留段落.json：[[開始秒, 結束秒], [開始秒, 結束秒], ...]，照播放順序排。
"""

import json
import os
import subprocess
import sys
import tempfile

FADE = 0.015


def fps_of(src: str) -> str:
    return subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=r_frame_rate", "-of", "csv=p=0", src],
        capture_output=True, text=True, check=True,
    ).stdout.strip()


def main(src: str, keep_path: str, dst: str) -> None:
    with open(keep_path, encoding="utf-8") as f:
        keep = [(float(a), float(b)) for a, b in json.load(f)]
    fps = fps_of(src)
    with tempfile.TemporaryDirectory(dir=os.path.dirname(os.path.abspath(dst))) as tmp:
        parts = []
        for i, (a, b) in enumerate(keep):
            d = b - a
            part = os.path.join(tmp, f"{i:04d}.mp4")
            subprocess.run(
                [
                    "ffmpeg", "-v", "error", "-y", "-ss", f"{a:.3f}", "-i", src, "-t", f"{d:.3f}",
                    "-map", "0:v:0", "-map", "0:a:0", "-r", fps,
                    "-af", f"afade=t=in:d={FADE},afade=t=out:st={max(d - FADE, 0):.3f}:d={FADE}",
                    "-c:v", "libx264", "-preset", "medium", "-crf", "16", "-pix_fmt", "yuv420p",
                    "-c:a", "aac", "-b:a", "192k", "-ar", "48000", part,
                ],
                check=True,
            )
            parts.append(part)
        listing = os.path.join(tmp, "list.txt")
        with open(listing, "w", encoding="utf-8") as f:
            f.writelines(f"file '{p}'\n" for p in parts)
        subprocess.run(
            ["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", listing, "-c", "copy", "-movflags", "+faststart", dst],
            check=True,
        )
    print(dst, f"{sum(b - a for a, b in keep):.2f} 秒")


if __name__ == "__main__":
    main(*sys.argv[1:4])
