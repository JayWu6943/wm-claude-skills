"""分辨影片裡每一句是「引導的人」還是「出鏡的人」講的。

拍法：引導的人（通常在鏡頭後面）先講一句，出鏡的人照著再講一次。成片只留出鏡的人講的。

判斷依據（不用網路、不用錢）：
1. 跟讀配對：後面幾秒內出現幾乎一樣的一句話，前面那句是引導，後面那句是出鏡的人。
   出鏡的人同一句講了好幾次，每一次都算出鏡的人，剪輯時挑講得最好的那次。
2. 聲音特徵：每句算音高和音量，分成兩群聲音。
   跟讀那句多數落在哪一群，那一群就是出鏡的人。沒配到對的句子（例如「好，再來一次」）就靠這個分。
3. 兩個判斷不一致、兩個人聲音太像，或句子太短，標成「不確定」，列進剪輯表給老闆確認。

用法：python 誰在講.py 逐字稿.json 原片.mp4 輸出.json
逐字稿.json 是 OpenMontage 聽打工具（Transcriber）的輸出，要有每個字的時間（words）。
"""

import difflib
import json
import re
import subprocess
import sys

import numpy as np

SR = 16000
GAP = 0.35  # 字和字之間停超過這麼久，就當成下一句
SIMILAR = 0.6  # 兩句文字相似度到這個程度，算跟讀
FOLLOW_WITHIN = 15.0  # 跟讀要在前一句結束後幾秒內出現

try:
    import opencc

    _cc = opencc.OpenCC("s2twp")
    to_trad = _cc.convert
except Exception:  # 沒裝 OpenCC 也能跑，只是顯示的字是簡體
    to_trad = lambda s: s  # noqa: E731


def load_audio(path: str) -> np.ndarray:
    raw = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", path, "-ac", "1", "-ar", str(SR), "-f", "s16le", "-"],
        check=True,
        capture_output=True,
    ).stdout
    return np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0


def utterances(transcript: dict) -> list[dict]:
    words = []
    for seg in transcript["segments"]:
        words.extend(seg.get("words") or [{"word": seg["text"], "start": seg["start"], "end": seg["end"]}])
    out: list[dict] = []
    for w in words:
        if out and w["start"] - out[-1]["end"] < GAP:
            out[-1]["text"] += w["word"]
            out[-1]["end"] = w["end"]
        else:
            out.append({"start": w["start"], "end": w["end"], "text": w["word"]})
    for u in out:
        u["text"] = to_trad(u["text"].strip())
    return [u for u in out if clean(u["text"])]


def clean(text: str) -> str:
    return re.sub(r"[\s\W_]+", "", text)


def pitch_and_level(audio: np.ndarray, start: float, end: float) -> tuple[float | None, float]:
    seg = audio[int(start * SR) : int(end * SR)]
    if len(seg) < SR * 0.2:
        return None, -99.0
    level = 20 * np.log10(np.sqrt(np.mean(seg**2)) + 1e-9)
    frame, hop = int(0.04 * SR), int(0.01 * SR)
    lo, hi = SR // 400, SR // 70  # 70～400 Hz 的人聲範圍
    pitches = []
    gate = np.sqrt(np.mean(seg**2)) * 0.5
    for i in range(0, len(seg) - frame, hop):
        f = seg[i : i + frame]
        if np.sqrt(np.mean(f**2)) < gate:
            continue
        f = f - f.mean()
        ac = np.correlate(f, f, "full")[frame - 1 :]
        if ac[0] <= 0:
            continue
        lag = lo + int(np.argmax(ac[lo:hi]))
        if ac[lag] / ac[0] > 0.45:
            pitches.append(SR / lag)
    return (float(np.median(pitches)) if len(pitches) >= 5 else None), float(level)


def two_groups(values: np.ndarray) -> tuple[np.ndarray, float]:
    """一維（音高取對數）分兩群，回傳每點屬於哪群，以及兩群音高差多少（比例）。"""
    a, b = np.percentile(values, 25), np.percentile(values, 75)
    for _ in range(50):
        lab = (np.abs(values - b) < np.abs(values - a)).astype(int)
        if lab.min() == lab.max():
            break
        a, b = values[lab == 0].mean(), values[lab == 1].mean()
    gap = float(np.exp(abs(b - a)) - 1)
    return lab, float(gap)


def main(transcript_path: str, media_path: str, out_path: str) -> None:
    with open(transcript_path, encoding="utf-8") as f:
        transcript = json.load(f)
    utts = utterances(transcript)
    audio = load_audio(media_path)
    for u in utts:
        u["pitch"], u["level"] = pitch_and_level(audio, u["start"], u["end"])
        u["by_pair"] = None

    # 1. 跟讀配對
    for i, a in enumerate(utts):
        ta = clean(a["text"])
        if len(ta) < 3:
            continue
        for b in utts[i + 1 : i + 5]:
            if b["start"] - a["end"] > FOLLOW_WITHIN:
                break
            if difflib.SequenceMatcher(None, ta, clean(b["text"])).ratio() >= SIMILAR:
                if a["by_pair"] is None:
                    a["by_pair"] = "引導"
                b["by_pair"] = "出鏡"

    # 2. 聲音分群（用音高；音高抓不到的句子不參與）
    voiced = [u for u in utts if u["pitch"]]
    voice_ok = False
    if len(voiced) >= 4:
        lab, gap = two_groups(np.log([u["pitch"] for u in voiced]))
        subject_votes = [lab[k] for k, u in enumerate(voiced) if u["by_pair"] == "出鏡"]
        guide_votes = [lab[k] for k, u in enumerate(voiced) if u["by_pair"] == "引導"]
        if subject_votes and gap >= 0.08:
            subj_group = int(round(np.mean(subject_votes)))
            # 跟讀那邊和引導那邊要落在不同群，聲音分群才可信
            if not guide_votes or int(round(np.mean(guide_votes))) != subj_group:
                voice_ok = True
                for k, u in enumerate(voiced):
                    u["by_voice"] = "出鏡" if lab[k] == subj_group else "引導"

    # 3. 綜合判斷
    for u in utts:
        p, v = u["by_pair"], u.get("by_voice")
        if p and (v is None or v == p):
            u["who"], u["sure"] = p, "高" if v else "中"
        elif p and v and v != p:
            u["who"], u["sure"] = p, "不確定"
        elif v and len(clean(u["text"])) >= 2:
            u["who"], u["sure"] = v, "中"
        else:
            u["who"], u["sure"] = "不確定", "不確定"

    result = {
        "voice_separable": voice_ok,
        "utterances": [
            {k: (round(v, 2) if isinstance(v, float) else v) for k, v in u.items() if k in ("start", "end", "text", "who", "sure", "pitch", "level")}
            for u in utts
        ],
    }
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=1)

    print(f"聲音分得開：{'是' if voice_ok else '否（只靠跟讀配對判斷）'}")
    for u in utts:
        print(f"{u['start']:7.2f}～{u['end']:7.2f}  {u['who']:<3} 把握{u['sure']:<3} {u['text']}")


if __name__ == "__main__":
    main(*sys.argv[1:4])
