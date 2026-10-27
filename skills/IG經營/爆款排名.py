"""爆款排名：把蒐集到的短影音，用「比這個帳號平常高幾倍」排名，標出用了哪個開頭公式，寫成參考清單。

中文化自 Jake Schincariol 的 instagram-agent-skill（swipe.py，MIT 授權）。
重點只有一個：觀看數本身不是證據。兩百萬粉絲的帳號拿到四十萬觀看，只是普通的一天；
四千粉絲的帳號拿到四十萬觀看，是真的做對了什麼，而且學得來。
所以排名看「倍數」= 觀看數 ÷ 這個帳號最近影片的中位數（沒有中位數才用粉絲數）。
3 倍以上才算訊號；1.5 倍以下就是那個帳號的日常，學不到東西。

輸入：一個用 Tab 分隔的表格，第一行是欄位名稱，邊滑邊填：
  帳號	粉絲數	中位數	觀看數	開頭
  @someone	48000	11000	412000	沒有人會告訴你，你的前三十支影片本來就會失敗
「開頭」填影片第一句話或第一行畫面字，用原文。

用法：python 爆款排名.py 蒐集.tsv [--out 參考清單.md]
"""

import argparse
import csv
import importlib.util
import os
import statistics

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("hookscore", os.path.join(HERE, "開頭評分.py"))
hookscore = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hookscore)


def num(v):
    try:
        return float(str(v).replace(",", "").strip())
    except ValueError:
        return 0.0


def main():
    ap = argparse.ArgumentParser(description="爆款排名（倍數法）")
    ap.add_argument("file")
    ap.add_argument("--out")
    a = ap.parse_args()
    rows = list(csv.DictReader(open(a.file, encoding="utf-8"), delimiter="\t"))
    used_median = any(num(r.get("中位數", 0)) for r in rows)
    out = []
    for r in rows:
        base = num(r.get("中位數", 0)) or num(r.get("粉絲數", 0))
        views = num(r.get("觀看數", 0))
        mult = views / base if base else 0
        hs = hookscore.run(r.get("開頭", "")) if r.get("開頭") else None
        out.append({**r, "倍數": round(mult, 1), "開頭分數": hs["分數"] if hs else None, "公式": hs["公式"] if hs else None})
    out.sort(key=lambda x: -x["倍數"])
    lines = [f"# 爆款參考清單（依「{'帳號中位數' if used_median else '粉絲數'}」算倍數排名）", ""]
    if not used_median:
        lines.append("注意：沒有填中位數，改用粉絲數當基準，倍數會失真，盡量補上中位數。\n")
    for x in out:
        level = "訊號" if x["倍數"] >= 3 else "日常" if x["倍數"] < 1.5 else "普通"
        lines.append(f"- **{x['倍數']} 倍**（{level}）{x.get('帳號', '')}：{x.get('開頭', '')}"
                     + (f"　［{x['公式']}，開頭 {x['開頭分數']} 分］" if x["公式"] else f"　［開頭 {x['開頭分數']} 分］" if x["開頭分數"] is not None else ""))
    sig = [x for x in out if x["倍數"] >= 3]
    if sig:
        lens = [len(hookscore.clean(x.get("開頭", ""))) for x in sig if x.get("開頭")]
        forms = [x["公式"] for x in sig if x["公式"]]
        lines += ["", "## 3 倍以上的共同點"]
        if lens:
            lines.append(f"- 開頭字數中位數：{statistics.median(lens):.0f} 字")
        if forms:
            top = max(set(forms), key=forms.count)
            lines.append(f"- 最常用的開頭公式：{top}（{forms.count(top)} 次）")
    text = "\n".join(lines)
    print(text)
    if a.out:
        open(a.out, "w", encoding="utf-8").write(text + "\n")


if __name__ == "__main__":
    main()
