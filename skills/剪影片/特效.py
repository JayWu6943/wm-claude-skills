"""最後一道：鏡頭放大特效＋字幕＋特效音，一次輸出成片。

特效稿（JSON）格式：
{
  "fps": 60,
  "zooms": [
    {"start": 0.0, "end": 2.5, "scale": 1.12, "type": "push"},  # 整段慢慢推近（開頭、情緒句）
    {"start": 8.2, "end": 10.4, "scale": 1.15, "type": "jump"}   # 較快推近後停住（重點句，常搭配 whoosh）
  ],
  "sfx": [
    {"at": 0.0, "name": "impact-bass-1", "volume": 0.35},
    {"at": 8.2, "name": "whoosh-short", "volume": 0.3}
  ]
}
特效音用 OpenMontage 內建的 21 個音效（Pixabay 授權，商用免費、不用標示來源），名字就是檔名：
whoosh、whoosh-short、whoosh-cinematic、pop、click、click-soft、ping、chime、notification、sparkle、
riser、impact-bass-1、impact-bass-2、typing、key-press、glitch-1～3、error。

用法：python 特效.py 剪好的片.mp4 字幕.ass 特效稿.json 成片.mp4 [OpenMontage 資料夾]
"""

import json
import os
import subprocess
import sys

FACE_Y = 0.38  # 放大時的中心偏上，臉通常在畫面上半部
ATTACK = 0.4  # jump：放大花多久到位（秒）
RELEASE = 0.45  # 放大結束後，花多久慢慢退回原樣（秒）
SUPERSAMPLE = 2  # 先把畫面放大幾倍再算位置；放大過程不會一格一格抖


def ease(u: str) -> str:
    """平滑曲線：開始慢、中間快、結束慢（u 會先限制在 0～1）。"""
    c = f"clip({u},0,1)"
    return f"({c}*{c}*(3-2*{c}))"


def zoom_expr(zooms: list[dict]) -> str:
    """每個放大都是：慢慢進 → 停住 → 慢慢退，不會一下子跳上去或彈回來（總監說原本「卡卡的」）。"""
    parts = []
    for z in zooms:
        a, b, s = float(z["start"]), float(z["end"]), float(z.get("scale", 1.12))
        rise = max(b - a, 0.01) if z.get("type") == "push" else ATTACK
        env = f"{ease(f'(it-{a})/{rise}')}*(1-{ease(f'(it-{b})/{RELEASE}')})"
        parts.append(f"{s - 1}*{env}")
    return "1+" + "+".join(parts) if parts else "1"


def main(src: str, ass: str, fx_path: str, dst: str, om: str = "/home/user/OpenMontage") -> None:
    with open(fx_path, encoding="utf-8") as f:
        fx = json.load(f)
    fps = int(fx.get("fps", 60))
    w, h = (
        subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height", "-of", "csv=p=0:s=x", src],
            capture_output=True, text=True, check=True,
        ).stdout.strip().split("x")
    )
    sfx_dir = os.path.join(om, ".agents/skills/hyperframes-media/assets/sfx")
    fonts = os.path.expanduser("~/.fonts")

    inputs = ["-i", src]
    video = (
        f"[0:v]scale={int(w) * SUPERSAMPLE}:{int(h) * SUPERSAMPLE}:flags=lanczos,"
        f"zoompan=z='{zoom_expr(fx.get('zooms', []))}':d=1"
        f":x='iw/2-(iw/zoom/2)':y='(ih-ih/zoom)*{FACE_Y}':s={w}x{h}:fps={fps},"
        f"subtitles='{ass}':fontsdir='{fonts}'[v]"
    )
    audio_parts, mix = [], ["[0:a]"]
    for i, s in enumerate(fx.get("sfx", []), start=1):
        inputs += ["-i", os.path.join(sfx_dir, f"{s['name']}.mp3")]
        ms = int(float(s["at"]) * 1000)
        audio_parts.append(f"[{i}:a]adelay={ms}|{ms},volume={s.get('volume', 0.3)}[s{i}]")
        mix.append(f"[s{i}]")
    audio_parts.append(
        f"{''.join(mix)}amix=inputs={len(mix)}:normalize=0:duration=first,loudnorm=I=-14:TP=-1.5[a]"
    )
    subprocess.run(
        [
            "ffmpeg", "-v", "error", "-y", *inputs,
            "-filter_complex", ";".join([video, *audio_parts]),
            "-map", "[v]", "-map", "[a]", "-r", str(fps),
            "-c:v", "libx264", "-preset", "medium", "-crf", "17", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-movflags", "+faststart", dst,
        ],
        check=True,
    )
    print(dst)


if __name__ == "__main__":
    main(*sys.argv[1:6])
