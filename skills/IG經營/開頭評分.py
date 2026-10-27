"""短影音開頭評分（中文版）：用五個面向替開頭打分數，一次比較好幾個開頭。

中文化自 Jake Schincariol 的 instagram-agent-skill（hookscore.py，MIT 授權）。原版只看得懂英文，
中文會被當成「一個字」而全部低分，所以這裡用中文的字數、數字、語氣詞重寫。

五個面向（各 0～100，越高越好）：
- 長度：講得完的時間。總監講話約每秒 4.8 個字，開頭要在 3 秒內講完，所以 8～15 個字最好。
- 具體：有沒有數字、金額、年資、人名品牌這類「查得到」的東西。
- 張力：有沒有否定、轉折、代價、意外（不、別、居然、其實、虧、錯、沒人…）。
- 開門見山：重點有沒有在前 6 個字出現；用「大家好」「今天」開頭會扣分。
- 對象：是不是對著「你」講。

它能抓出：打招呼、鋪陳、沒有具體內容、太長的開頭。
它不能預測哪個開頭會紅，那要看你的表情、剪輯和平台推送；最後還是看後台的觀看留存曲線。

用法：
  python 開頭評分.py 開頭.txt          # 一行一個開頭，排名
  python 開頭評分.py --hook "我拍照拍了十四年，最近研究最多的居然不是相機"
  python 開頭評分.py 開頭.txt --json
"""

import argparse
import json
import os
import re
import statistics
import sys

CHARS_PER_SEC = 4.8
HERE = os.path.dirname(os.path.abspath(__file__))

CN_NUM = "零一二兩三四五六七八九十百千萬億半"
NUMBER_RE = re.compile(
    rf"\d[\d,\.]*\s*(%|萬|千|百|塊|元|天|週|周|年|個月|小時|分鐘|秒|倍|次|支|件|個|位|成)?"
    rf"|[{CN_NUM}]+\s*(萬|千|百|塊|元|天|週|周|年|個月|小時|分鐘|秒|倍|次|支|件|個|位|成)"
)
LATIN_NAME_RE = re.compile(r"[A-Za-z]{2,}")
HASHTAG_RE = re.compile(r"#\S+")
EMOJI_RE = re.compile(r"[\U0001F300-\U0001FAFF☀-➿]")

STAKES = [
    "不", "沒", "別", "錯", "虧", "賠", "輸", "失敗", "後悔", "代價", "學費", "損失", "浪費", "危險", "小心", "警告",
    "居然", "竟然", "其實", "但", "卻", "才", "只", "根本", "千萬", "絕對", "真相", "秘密", "沒人", "從來",
    "省", "免費", "取代", "淘汰", "被騙", "踩雷", "雷", "坑", "最", "第一次", "終於", "差", "爛", "貴",
]
WEAK_OPENERS = ["大家好", "哈囉", "嗨", "hello", "hi", "今天", "這支影片", "這集", "我想", "我要來", "我們來", "那個", "嗯", "所以", "就是"]
DEALBREAKERS = [
    (re.compile(r"^\s*(大家好|哈囉|嗨|hello|hi|嘿)", re.I), "用打招呼開頭。沒有人是來滑動態被打招呼的。"),
    (re.compile(r"(今天(要|想)?(跟大家|來)?(分享|聊|講)|這支影片(要|會)|我要來(教|分享))"), "影片前言。刪掉，直接從重點開始。"),
    (re.compile(r"^\s*(先別滑|不要滑|停一下)"), "叫人不要滑。要人注意，代表還沒贏得注意。"),
    (HASHTAG_RE, "開頭裡有標籤。標籤放在貼文最下面就好。"),
    (EMOJI_RE, "開頭裡有表情符號。畫面上的大字只放得下字，放不下表情。"),
]
YOU_RE = re.compile(r"(你|妳|你們|您)")
ME_RE = re.compile(r"(我|我們)")
IMPERATIVE_RE = re.compile(r"^(別|不要|先|試試|記得|快|馬上|直接|拿去|看)")


def clean(text: str) -> str:
    return re.sub(r"[\s，。、！？!?,.：:；;「」『』\"'（）()…—\-]", "", text)


def clamp(n: float) -> float:
    return max(0.0, min(100.0, n))


def check_length(text):
    n = len(clean(text))
    secs = n / CHARS_PER_SEC
    if 8 <= n <= 15:
        score = 100.0
    elif n < 8:
        score = clamp(100 - (8 - n) * 12)
    else:
        score = clamp(100 - (n - 15) * 6)
    return score, f"{n} 個字，約 {secs:.1f} 秒講完（最好 8～15 字、3 秒內）"


def check_specific(text):
    nums = [m.group(0) for m in NUMBER_RE.finditer(text)]
    names = LATIN_NAME_RE.findall(text)
    hits = len(nums) + len(names)
    score = 15.0 if hits == 0 else clamp(45 + hits * 30)
    found = "、".join((nums + names)[:3])
    return score, (f"{hits} 個具體的東西：{found}" if hits else "沒有數字、沒有名字，沒有可以查證的東西")


def check_stakes(text):
    hits = sorted({w for w in STAKES if w in text})
    score = {0: 20.0, 1: 70.0}.get(len(hits), 100.0)
    return score, (f"{len(hits)} 個張力詞：{'、'.join(hits[:4])}" if hits else "沒有任何代價、轉折或意外")


def check_frontload(text):
    t = clean(text)
    if not t:
        return 0.0, "空白"
    penalty, weak = 0, None
    for w in WEAK_OPENERS:
        if t.lower().startswith(w.lower()):
            penalty, weak = 30, w
            break
    pos = None
    for i in range(len(t)):
        seg = t[i:]
        if NUMBER_RE.match(seg) or LATIN_NAME_RE.match(seg) or any(seg.startswith(w) for w in STAKES):
            pos = i
            break
    if pos is None:
        base, where = 30.0, "整句沒有重點詞"
    elif pos < 6:
        base, where = 100.0, f"重點在第 {pos + 1} 個字"
    elif pos < 12:
        base, where = 70.0, f"重點在第 {pos + 1} 個字，可以再往前"
    else:
        base, where = 40.0, f"重點在第 {pos + 1} 個字，太後面"
    return clamp(base - penalty), where + (f"；開頭是弱詞「{weak}」" if weak else "")


def check_address(text):
    if YOU_RE.search(text):
        return 100.0, "對著觀眾講（有「你」）"
    if IMPERATIVE_RE.search(clean(text)):
        return 90.0, "命令句開頭"
    if ME_RE.search(text):
        return 70.0, "用「我」講，沒有點到觀眾"
    return 35.0, "第三人稱，沒有對著任何人"


CHECKS = [("長度", check_length), ("具體", check_specific), ("張力", check_stakes), ("開門見山", check_frontload), ("對象", check_address)]
WEIGHTS = {"長度": 0.2, "具體": 0.25, "張力": 0.2, "開門見山": 0.2, "對象": 0.15}


def formula_of(text):
    try:
        d = json.load(open(os.path.join(HERE, "開頭公式.json"), encoding="utf-8"))
    except Exception:
        return None
    by_id = {f["id"]: f for f in d["公式"]}
    for i in d.get("辨識順序", by_id):
        f = by_id.get(i)
        if f and re.search(f["match"], text):
            return f"#{f['id']} {f['名稱']}"
    return None


def run(text: str) -> dict:
    parts = {name: fn(text) for name, fn in CHECKS}
    total = sum(parts[n][0] * WEIGHTS[n] for n in parts)
    breakers = [msg for rx, msg in DEALBREAKERS if rx.search(text)]
    if breakers:
        total = min(total, 55.0)
    weakest = min(parts, key=lambda n: parts[n][0])
    label = "強" if total >= 75 else "可以" if total >= 50 else "弱"
    return {"開頭": text, "分數": round(total, 1), "評語": label, "最弱": weakest,
            "細項": {n: {"分數": round(s, 1), "說明": d} for n, (s, d) in parts.items()},
            "致命傷": breakers, "公式": formula_of(text)}


def main():
    ap = argparse.ArgumentParser(description="短影音開頭評分（中文）")
    ap.add_argument("file", nargs="?", help="一行一個開頭；- 代表從輸入讀")
    ap.add_argument("--hook")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    if a.hook:
        hooks = [a.hook]
    elif a.file:
        src = sys.stdin if a.file == "-" else open(a.file, encoding="utf-8")
        hooks = [l.strip() for l in src if l.strip()]
    else:
        ap.error("給一個檔案或 --hook")
    results = sorted((run(h) for h in hooks), key=lambda r: -r["分數"])
    if a.json:
        print(json.dumps(results, ensure_ascii=False, indent=1))
        return
    print("開頭排名")
    print("=" * 60)
    for i, r in enumerate(results):
        mark = "→" if i == 0 else " "
        print(f"{mark} {r['分數']:5.1f} {r['評語']:<2} {r['開頭']}")
        print(f"         最弱：{r['最弱']}（{r['細項'][r['最弱']]['說明']}）" + (f"　公式：{r['公式']}" if r["公式"] else ""))
        for b in r["致命傷"]:
            print(f"         致命傷：{b}")
    top = results[0]["分數"]
    print()
    print("拍分數最高的那個。" if top >= 50 else "最高的也不到 50 分，這些都還不是好開頭，再想一輪。")
    if len(results) > 2:
        print(f"（這批平均 {statistics.mean(r['分數'] for r in results):.1f} 分）")


if __name__ == "__main__":
    main()
