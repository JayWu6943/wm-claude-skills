"""去 AI 味（繁體中文版）：找出文案裡像 AI 寫的地方，能自動修的修掉，再給一個「像人寫的」分數。

概念來自 Jake Schincariol 的 instagram-agent-skill（humanize.py / detect.py，MIT 授權）；
原版只認得英文的 AI 口吻，這裡改成繁體中文清單（中文AI口吻.json，可以自己加）。

會做的事：
- 刪掉看不見的隱形字元（有些 AI 工具會偷藏，用來辨識是 AI 寫的）。
- 把常見的 AI 用語換成口語（例如「賦能」→「幫助」），或直接刪掉（例如「綜上所述」）。長的詞先換。
- 標出 AI 句型（不僅…更…、無論是…還是…、首先其次最後、破折號、表情符號清單…），這些要人改寫，不自動改。
- 給一個 0～100 的分數：越高越像人寫的，70 分以上再發。

用法：python 去AI味.py 文案.txt [--fix 修好.txt]
"""

import argparse
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))


def main():
    ap = argparse.ArgumentParser(description="去 AI 味（繁體中文）")
    ap.add_argument("file")
    ap.add_argument("--fix", help="把自動修好的版本存到這裡")
    a = ap.parse_args()
    lex = json.load(open(os.path.join(HERE, "中文AI口吻.json"), encoding="utf-8"))
    text = open(a.file, encoding="utf-8").read()
    fixed = text
    hidden = sum(fixed.count(c) for c in lex["隱形字元"])
    for c in lex["隱形字元"]:
        fixed = fixed.replace(c, "")
    words = []
    for w, rep in sorted(lex["詞語"].items(), key=lambda kv: -len(kv[0])):  # 長的先換，「量身打造」才不會先被「打造」換掉
        n = fixed.count(w)
        if n:
            words.append((w, rep, n))
            fixed = fixed.replace(w, rep)
    fixed = re.sub(r"，\s*，", "，", re.sub(r"^\s*，", "", fixed, flags=re.M))
    patterns = []
    for p in lex["句型"]:
        hits = re.findall(p["pattern"], fixed, flags=re.M)
        if hits:
            patterns.append((p["說明"], len(hits)))

    chars = max(len(re.sub(r"\s", "", text)), 1)
    penalty = hidden * 10 + sum(n for _, _, n in words) * 4 + sum(n for _, n in patterns) * 7
    score = max(0, min(100, 100 - penalty * 100 / max(chars / 3, 30)))
    print(f"像人寫的分數：{score:.0f} / 100" + ("（可以發）" if score >= 70 else "（建議再改）"))
    if hidden:
        print(f"- 刪掉 {hidden} 個隱形字元")
    for w, rep, n in words:
        print(f"- 「{w}」×{n} → " + (f"「{rep}」" if rep else "刪掉"))
    for desc, n in patterns:
        print(f"- 要改寫（{n} 處）：{desc}")
    if not (hidden or words or patterns):
        print("- 沒有找到明顯的 AI 口吻")
    if a.fix:
        open(a.fix, "w", encoding="utf-8").write(fixed)
        print(f"自動修好的版本存到：{a.fix}（句型的部分還是要人改）")


if __name__ == "__main__":
    main()
