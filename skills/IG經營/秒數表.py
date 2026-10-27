"""腳本秒數表（中文版）：拍之前先算每句講多久，抓出會讓人滑走的地方。

中文化自 Jake Schincariol 的 instagram-agent-skill（beats.py，MIT 授權）。原版用英文字數算，中文會變成 0 秒。
這裡用中文字數算：總監實測講話速度約每秒 4.8 個字（萌主或其他人可以用 --rate 改）。

會抓出四個問題：
1. 開頭超過 3 秒。
2. 某一句超過 4 秒：拆成兩句，或那段畫面要有變化（換角度、跳字），不然觀眾會走。
3. 連續三句都沒有具體的東西（數字、名字、例子）。
4. 結尾沒有呼應開頭：最後一句重複開頭的一個詞，觀眾比較會重看，等於免費多一次觀看。

用法：
  python 秒數表.py 腳本.txt --target 30       # 一行一句，目標 30 秒
  python 秒數表.py 腳本.txt --target 60 --rate 4.5
"""

import argparse
import re

CN_NUM = "零一二兩三四五六七八九十百千萬億半"
CONCRETE_RE = re.compile(rf"\d|[{CN_NUM}]+\s*(萬|千|百|塊|元|天|週|年|個月|小時|分鐘|秒|倍|次|支|件|個|位|成)|[A-Za-z]{{2,}}|例如|比如|像是")
PUNCT_RE = re.compile(r"[\s，。、！？!?,.：:；;「」『』\"'（）()…—\-]")


def clean(t: str) -> str:
    return PUNCT_RE.sub("", t)


def main():
    ap = argparse.ArgumentParser(description="腳本秒數表（中文）")
    ap.add_argument("file")
    ap.add_argument("--target", type=float, default=30.0, help="目標秒數")
    ap.add_argument("--rate", type=float, default=4.8, help="每秒講幾個字（總監約 4.8）")
    a = ap.parse_args()
    lines = [l.strip() for l in open(a.file, encoding="utf-8") if l.strip()]
    if not lines:
        print("腳本是空的")
        return
    total_chars = sum(len(clean(l)) for l in lines)
    print(f"秒數表 · {total_chars} 個字 · 約 {total_chars / a.rate:.1f} 秒（每秒 {a.rate} 字）· 目標 {a.target:.0f} 秒")
    print("=" * 66)
    t, notes, dry = 0.0, [], 0
    for i, line in enumerate(lines):
        secs = len(clean(line)) / a.rate + 0.25  # 句子之間換氣約 0.25 秒
        tag = "開頭" if i == 0 else "結尾" if i == len(lines) - 1 else ""
        print(f"  {int(t // 60)}:{t % 60:04.1f}  {secs:4.1f}秒  {tag:<2}  {line}")
        if i == 0 and secs > 3.2:
            notes.append(f"開頭要 {secs:.1f} 秒，超過 3 秒。把重點往前移，或砍短到 15 個字內。")
        if secs > 4.0:
            notes.append(f"第 {i + 1} 句講 {secs:.1f} 秒，太長。拆成兩句，或那段畫面要有變化（換角度、跳出字），停著不動的畫面最容易讓人滑走。")
        dry = 0 if CONCRETE_RE.search(line) else dry + 1
        if dry == 3:
            notes.append(f"第 {i - 1}～{i + 1} 句都沒有具體的東西。在其中一句放進數字、名字或例子。")
        t += secs
    print("-" * 66)
    hook, last = clean(lines[0]), clean(lines[-1])
    shared = {hook[j:j + 2] for j in range(len(hook) - 1)} & {last[j:j + 2] for j in range(len(last) - 1)}
    if len(lines) > 1:
        if shared:
            notes.append(f"結尾呼應了開頭（「{sorted(shared)[0]}」），觀眾比較會重看，很好。")
        else:
            notes.append("結尾沒有呼應開頭。最後一句重複開頭的一個詞，是最省力的重看理由。")
    diff = t - a.target
    if diff < -3:
        notes.append(f"比目標短 {-diff:.0f} 秒。可以補約 {(-diff) * a.rate:.0f} 個字，或就拍短一點，短通常比較好。")
    elif diff > 3:
        notes.append(f"比目標長 {diff:.0f} 秒。要刪約 {diff * a.rate:.0f} 個字，先刪沒有具體內容的句子。")
    for n in notes:
        print(f"  - {n}")


if __name__ == "__main__":
    main()
