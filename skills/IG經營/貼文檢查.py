"""IG 貼文文字檢查（中文版）：先讓你看到「動態上沒點開時」別人看得到的那一段。

中文化自 Jake Schincariol 的 instagram-agent-skill（caption.py，MIT 授權）。
IG 動態上貼文文字只顯示開頭一小段，後面要點「更多」才看得到；大部分失敗的貼文就失敗在這一段。
中文字比英文寬，手機上大約只看得到前 2 行、50～60 個中文字（每支手機不同，可用 --window 調）。

檢查：
- 動態上看得到的那一段（框起來給你看）
- 總長度（上限 2200 字）
- 第一行有沒有在看得到的範圍內講完
- 看得到的那段有沒有具體的東西（數字、名字）
- 標籤數量：最多 5 個
- 只有一個行動呼籲（留言關鍵字、私訊、點連結 選一個）
- 想被搜尋到的關鍵字有沒有出現（--keywords）

用法：python 貼文檢查.py 貼文.txt --keywords "形象照,企業形象照"
"""

import argparse
import re
import textwrap

CN_NUM = "零一二兩三四五六七八九十百千萬億半"
CONCRETE_RE = re.compile(rf"\d|[{CN_NUM}]+\s*(萬|千|百|塊|元|天|週|年|個月|小時|分鐘|秒|倍|次|支|件|個|位|成)|[A-Za-z]{{2,}}")
TAG_RE = re.compile(r"#[^\s#]+")
CTA_RE = re.compile(r"(留言|私訊|點(擊)?連結|連結在|預約|加\s*LINE|追蹤|收藏|分享給)")


def main():
    ap = argparse.ArgumentParser(description="IG 貼文文字檢查（中文）")
    ap.add_argument("file")
    ap.add_argument("--keywords", default="", help="想被搜尋到的詞，用逗號分開")
    ap.add_argument("--window", type=int, default=55, help="動態上大約看得到幾個字")
    a = ap.parse_args()
    text = open(a.file, encoding="utf-8").read().strip()
    visible = text[: a.window]
    first_line = text.split("\n", 1)[0]

    print("  動態上看得到的部分（之後要點「更多」）")
    print("  ┌" + "─" * 24)
    for row in textwrap.wrap(visible.replace("\n", " ⏎ "), 20):
        print(f"  │ {row}")
    print("  └" + "─" * 18 + " …更多")
    print()

    def line(ok, name, msg):
        print(f"  {'通過' if ok else '注意'}  {name:<8}{msg}")

    line(len(text) <= 2200, "長度", f"{len(text)} / 2200 字")
    line(len(first_line) <= a.window, "第一行", f"{len(first_line)} 字" + ("，在看得到的範圍內講完" if len(first_line) <= a.window else "，會在講到一半時被切掉"))
    line(bool(CONCRETE_RE.search(visible)), "具體", "看得到的那段有數字或名字" if CONCRETE_RE.search(visible) else "看得到的那段沒有任何具體的東西")
    tags = TAG_RE.findall(text)
    line(len(tags) <= 5, "標籤", f"{len(tags)} 個" + (f"：{' '.join(tags)}" if tags else "") + ("" if len(tags) <= 5 else "，最多 5 個"))
    ctas = sorted(set(m.group(0) for m in CTA_RE.finditer(text)))
    line(len(ctas) == 1, "行動呼籲", f"{len(ctas)} 個" + (f"：{'、'.join(ctas)}" if ctas else "，結尾請只給一個明確的動作") + ("，太多會分散，留一個就好" if len(ctas) > 1 else ""))
    kws = [k.strip() for k in a.keywords.split(",") if k.strip()]
    if kws:
        miss = [k for k in kws if k not in text]
        line(not miss, "搜尋詞", f"{len(kws) - len(miss)}/{len(kws)} 有出現" + (f"，缺：{'、'.join(miss)}" if miss else ""))


if __name__ == "__main__":
    main()
