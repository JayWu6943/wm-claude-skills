"""把校對好的字幕稿做成薇萌樣式的字幕檔（.ass），再用 ffmpeg 燒進影片。

OpenMontage 內建的逐字字幕是為英文設計的，中文會在字和字之間多出空格，所以中文字幕改用這支。

字幕稿（JSON）格式：
{
  "title": "形象照跟證件照差在哪",          # 片頭標題，前 3 秒出現在上方；不要就留空
  "endcard": ["歐巴老吳｜薇萌 WM Group", "想拍出你的專業形象，私訊我們", "wmgroup.com.tw"],
  "endcard_seconds": 3,                     # 片尾字卡長度；成片要先接好這段畫面（黑畫面或最後一格延長）
  "duration": 25.7,                         # 成片總長（含片尾）
  "cues": [
    {"start": 0.0, "end": 2.4, "text": "證件照 大頭貼 跟形象照", "keys": ["形象照"]},
    ...
  ],
  "cards": [                                # 特效字卡（選填）
    {"start": 5.0, "end": 6.2, "text": "形象照", "style": "big"},          # 畫面中間跳出的大字重點
    {"start": 9.0, "end": 12.0, "text": "你覺得形象照\\n該怎麼拍？", "style": "question"}  # 上方提問框（藏鏡人提問）
  ]
}
每一句 text 一行最多 12 個字（老闆指定更少就照老闆的）；超過就用 \\n 斷成兩行。keys 是要用品牌金色標出的重點字。
沒有片尾字卡就不要給 endcard。字幕每句出現時會有「彈出」的小動畫。

用法：python 字幕.py 字幕稿.json 輸出.ass [寬 高]
"""

import json
import sys

GOLD = "&H007CA7C9"  # 品牌金 #C9A77C（ASS 色碼是 藍綠紅 的順序）
WHITE = "&H00FFFFFF"
INK = "&H00161A1A"  # 品牌深色 #1a1916
INK_BOX = "&H33161A1A"  # 深色、稍微透明，片頭標題底色
FONT = "Noto Sans TC"


def ts(sec: float) -> str:
    sec = max(sec, 0)
    h = int(sec // 3600)
    m = int(sec % 3600 // 60)
    s = sec % 60
    return f"{h}:{m:02d}:{s:05.2f}"


def highlight(text: str, keys: list[str]) -> str:
    out = text.replace("\n", "\\N")
    for k in keys or []:
        out = out.replace(k, f"{{\\c{GOLD}&}}{k}{{\\c{WHITE}&}}")
    return out


def build(script: dict, width: int, height: int) -> str:
    sub_size = round(height * 0.038)  # 1920 高約 72
    title_size = round(height * 0.042)
    # 字幕底線放在畫面約 73% 高的位置，避開下方 20% 平台按鈕區
    sub_margin = round(height * 0.27)
    lines = [
        "[Script Info]",
        "ScriptType: v4.00+",
        f"PlayResX: {width}",
        f"PlayResY: {height}",
        "WrapStyle: 2",
        "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
        f"Style: Sub,{FONT},{sub_size},{WHITE},{WHITE},{INK},{INK},-1,0,0,0,100,100,2,0,1,6,0,2,60,60,{sub_margin},1",
        f"Style: Title,{FONT},{title_size},{WHITE},{WHITE},{INK_BOX},{INK_BOX},-1,0,0,0,100,100,4,0,3,22,0,8,80,80,{round(height * 0.12)},1",
        f"Style: End,{FONT},{sub_size},{WHITE},{WHITE},{INK},{INK},-1,0,0,0,100,100,4,0,1,0,0,5,60,60,0,1",
        f"Style: Big,{FONT},{round(height * 0.075)},{GOLD},{GOLD},{INK},{INK},-1,0,0,0,100,100,6,0,1,9,4,5,60,60,0,1",
        f"Style: Question,{FONT},{round(height * 0.036)},{INK},{INK},{WHITE},{WHITE},-1,0,0,0,100,100,2,0,3,26,0,8,90,90,{round(height * 0.14)},1",
        "",
        "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]

    end_len = float(script.get("endcard_seconds", 3)) if script.get("endcard") else 0
    duration = float(script.get("duration", 0)) or max(float(c["end"]) for c in script["cues"])
    end_start = duration - end_len if end_len else float("inf")

    if script.get("title"):
        lines.append(f"Dialogue: 1,{ts(0)},{ts(min(3, end_start))},Title,,0,0,0,,{{\\fad(150,200)}}{script['title']}")

    for c in script["cues"]:
        end = min(float(c["end"]), end_start)
        if end <= float(c["start"]):
            continue
        pop = "{\\fscx86\\fscy86\\t(0,110,\\fscx100\\fscy100)}"
        lines.append(f"Dialogue: 0,{ts(float(c['start']))},{ts(end)},Sub,,0,0,0,,{pop}{highlight(c['text'], c.get('keys'))}")

    for c in script.get("cards", []):
        text = c["text"].replace("\n", "\\N")
        if c.get("style") == "question":
            # 上方白底深字的提問框，淡入淡出
            lines.append(
                f"Dialogue: 4,{ts(float(c['start']))},{ts(float(c['end']))},Question,,0,0,0,,"
                f"{{\\fad(180,180)\\fscx90\\fscy90\\t(0,160,\\fscx100\\fscy100)}}{text}"
            )
        else:
            # 畫面中間跳出的大字：先放大超過一點再彈回來
            lines.append(
                f"Dialogue: 4,{ts(float(c['start']))},{ts(float(c['end']))},Big,,0,0,0,,"
                f"{{\\fad(0,150)\\fscx40\\fscy40\\t(0,140,\\fscx112\\fscy112)\\t(140,240,\\fscx100\\fscy100)}}{text}"
            )

    if end_len:
        # 片尾：整面品牌深色底，中間三行字，第一行（署名）用金色
        box = f"{{\\an7\\pos(0,0)\\p1\\bord0\\c{INK}&\\fad(250,0)}}m 0 0 l {width} 0 {width} {height} 0 {height}{{\\p0}}"
        lines.append(f"Dialogue: 2,{ts(end_start)},{ts(duration)},End,,0,0,0,,{box}")
        rows = script["endcard"]
        gap = round(sub_size * 1.9)
        top = height / 2 - gap * (len(rows) - 1) / 2
        for i, row in enumerate(rows):
            color = GOLD if i == 0 else WHITE
            size = round(sub_size * (1.05 if i == 0 else 0.8))
            lines.append(
                f"Dialogue: 3,{ts(end_start)},{ts(duration)},End,,0,0,0,,"
                f"{{\\an5\\pos({width // 2},{round(top + gap * i)})\\fs{size}\\c{color}&\\fad(400,0)}}{row}"
            )
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    src, dst = sys.argv[1], sys.argv[2]
    w, h = (int(sys.argv[3]), int(sys.argv[4])) if len(sys.argv) > 4 else (1080, 1920)
    with open(src, encoding="utf-8") as f:
        data = json.load(f)
    with open(dst, "w", encoding="utf-8") as f:
        f.write(build(data, w, h))
    print(dst)
