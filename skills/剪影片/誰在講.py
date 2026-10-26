"""分辨影片裡哪些時間是「引導的人」在講、哪些是「出鏡的人」在講。

拍法：引導的人（通常在鏡頭後面）先講一句，出鏡的人照著再講一次，兩個人常常接得很緊、中間沒停頓，
聽打出來的逐字稿也常把兩個人的話黏在一起，所以這裡不看逐字稿，直接聽聲音分人。

做法（全部在這台電腦上跑，不用網路、不用錢）：
1. 聲紋：每 0.2 秒取一段 0.8 秒的聲音，用聲紋模型（3D-Speaker 中文模型）算出「這段像誰」，分成兩個人。
2. 哪一個是引導的人：
   - 總監有說的直接指定：女生（聲音高的）是引導加 `--guide high`，男生（聲音低的）是引導加 `--guide low`。
   - 沒指定就看跟讀：把兩個人各自的話分開聽打，誰的話常常重複另一個人剛講過的，誰就是出鏡的人。
3. 把兩個人各自講話的時間段分開聽打（各自接成一條聲音再聽打，比混在一起準很多），時間換回原片的時間。

輸出（JSON）：
- speakers.出鏡 / speakers.引導：各自講話的時間段 [{start, end, text, words}]，時間是原片的秒數；
  words 是每個字的時間，要從一段中間切（例如只留後半句）時用。
- keep：出鏡的人講話的時間段（前後各留一點空間），可以直接當 剪接.py 的「保留段落」初稿。
  同一句講了好幾次的，要在剪輯表挑一次留下，其他從 keep 拿掉。

準備（第一次）：
  .venv/bin/python -m pip install sherpa-onnx
  模型放到 OpenMontage 的 models/eres2net_zh.onnx：
  https://huggingface.co/csukuangfj/speaker-embedding-models/resolve/main/3dspeaker_speech_eres2net_base_sv_zh-cn_3dspeaker_16k.onnx

用法：python 誰在講.py 原片.mp4 輸出.json [--guide high|low] [--om OpenMontage 資料夾]
"""

import difflib
import json
import os
import re
import subprocess
import sys

import numpy as np

SR = 16000
WIN, HOP = 0.8, 0.2  # 聲紋取樣：每 0.2 秒取 0.8 秒
JOIN = 0.35  # 同一個人停不到這麼久，算同一段
PAD_BEFORE, PAD_AFTER = 0.08, 0.12  # 剪的時候頭尾多留一點，避免切到字

try:
    import opencc

    to_trad = opencc.OpenCC("s2twp").convert
except Exception:  # 沒裝 OpenCC 也能跑，只是字是簡體
    to_trad = lambda s: s  # noqa: E731


def load_audio(path: str) -> np.ndarray:
    raw = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", path, "-ac", "1", "-ar", str(SR), "-f", "s16le", "-"],
        check=True,
        capture_output=True,
    ).stdout
    return np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0


def frames(audio: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """每 10 毫秒一格：回傳（時間, 有沒有在講話, 音高 Hz；抓不到是 0）。"""
    size, hop = int(0.04 * SR), int(0.01 * SR)
    lo, hi = SR // 400, SR // 70
    n = max((len(audio) - size) // hop, 0)
    idx = np.arange(size)[None, :] + hop * np.arange(n)[:, None]
    f = audio[idx] * np.hanning(size)
    f -= f.mean(axis=1, keepdims=True)
    energy = np.sqrt(np.mean(f**2, axis=1))
    ac = np.fft.irfft(np.abs(np.fft.rfft(f, 2 * size)) ** 2)[:, :size]
    lag = lo + np.argmax(ac[:, lo:hi], axis=1)
    strength = ac[np.arange(n), lag] / np.maximum(ac[:, 0], 1e-12)
    speech = energy > np.percentile(energy, 35)
    f0 = np.where(speech & (strength > 0.45), SR / lag, 0.0)
    return np.arange(n) * 0.01 + 0.02, speech, f0


def voiceprints(audio: np.ndarray, speech: np.ndarray, model: str) -> tuple[np.ndarray, np.ndarray]:
    import sherpa_onnx

    ex = sherpa_onnx.SpeakerEmbeddingExtractor(
        sherpa_onnx.SpeakerEmbeddingExtractorConfig(model=model, num_threads=os.cpu_count() or 2)
    )
    starts, embs = [], []
    for s in np.arange(0, len(audio) / SR - WIN, HOP):
        i0, i1 = int(s / 0.01), int((s + WIN) / 0.01)
        if speech[i0:i1].mean() < 0.5:
            continue
        st = ex.create_stream()
        st.accept_waveform(SR, audio[int(s * SR) : int((s + WIN) * SR)])
        st.input_finished()
        e = np.array(ex.compute(st))
        starts.append(s)
        embs.append(e / np.linalg.norm(e))
    return np.array(starts), np.array(embs)


def two_people(embs: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """聲紋分兩個人（餘弦相似度分兩群），回傳每段屬於誰、兩個人的聲紋中心。"""
    c = embs[[0, int(np.argmin(embs @ embs[0]))]]
    for _ in range(30):
        lab = np.argmax(embs @ c.T, axis=1)
        c = np.array([embs[lab == k].mean(0) for k in (0, 1)])
        c /= np.linalg.norm(c, axis=1, keepdims=True)
    return lab, c


def spans(times: np.ndarray, speech: np.ndarray, who: np.ndarray, person: int) -> list[list[float]]:
    out: list[list[float]] = []
    for t, sp, w in zip(times, speech, who):
        if not sp or w < 0:
            continue
        if w == person:
            if out and out[-1][2] and t - out[-1][1] < JOIN:
                out[-1][1] = t
            else:
                out.append([t, t, True])
        elif out:
            out[-1][2] = False  # 另一個人開口了，這段結束
    return [[a, b] for a, b, _ in out if b - a >= 0.3]


def transcribe(media: str, segs: list[list[float]], model) -> list[dict]:
    """把一個人的時間段接成一條聲音聽打，每個字放回它原本那一段。沒聽到字的段落 text 是空的（多半是笑聲、雜音）。"""
    if not segs:
        return []
    audio = load_audio(media)
    pieces, table, pos = [], [], 0.0
    for a, b in segs:
        piece = audio[int(max(a - PAD_BEFORE, 0) * SR) : int((b + PAD_AFTER) * SR)]
        table.append((pos, max(a - PAD_BEFORE, 0)))
        pieces.append(piece)
        pieces.append(np.zeros(int(0.3 * SR), np.float32))  # 段和段之間墊 0.3 秒，讓聽打分得出句子
        pos += (len(piece) + int(0.3 * SR)) / SR
    joined = np.concatenate(pieces)

    def piece_of(t: float) -> int:
        return max(i for i, (p, _) in enumerate(table) if p <= t + 1e-6)

    result, _ = model.transcribe(joined, language="zh", word_timestamps=True, vad_filter=False)
    words: list[list[dict]] = [[] for _ in segs]
    for seg in result:
        for w in seg.words or []:
            k = piece_of((w.start + w.end) / 2)
            shift = table[k][1] - table[k][0]  # 接起來的聲音時間 → 原片時間
            words[k].append({"word": to_trad(w.word.strip()), "start": round(w.start + shift, 2), "end": round(w.end + shift, 2)})
    return [
        {"start": round(a, 2), "end": round(b, 2), "text": "".join(x["word"] for x in ws), "words": ws}
        for (a, b), ws in zip(segs, words)
    ]


def clean(text: str) -> str:
    return re.sub(r"[\s\W_]+", "", text)


def repeats(a: list[dict], b: list[dict]) -> int:
    """b 裡有幾句是在 15 秒內重複 a 剛講過的話（跟讀）。"""
    n = 0
    for y in b:
        for x in a:
            if 0 <= y["start"] - x["end"] < 15 and difflib.SequenceMatcher(None, clean(x["text"]), clean(y["text"])).ratio() >= 0.6:
                n += 1
                break
    return n


def main(media: str, out_path: str, guide: str | None = None, om: str = "/home/user/OpenMontage") -> None:
    from faster_whisper import WhisperModel

    audio = load_audio(media)
    times, speech, f0 = frames(audio)
    starts, embs = voiceprints(audio, speech, os.path.join(om, "models/eres2net_zh.onnx"))
    lab, centers = two_people(embs)
    similarity = float(centers[0] @ centers[1])

    # 每 10 毫秒那一格，看蓋到它的取樣多數像誰（越像的票越重）
    vote = np.zeros((len(times), 2))
    for s, l, e in zip(starts, lab, embs):
        i0, i1 = int(s / 0.01), int((s + WIN) / 0.01)
        vote[i0:i1, l] += max(float(e @ centers[l] - e @ centers[1 - l]), 0.01)
    who = np.where(vote.sum(1) > 0, np.argmax(vote, 1), -1)

    pitch = [float(np.median(f0[(who == k) & (f0 > 0)])) if ((who == k) & (f0 > 0)).any() else 0.0 for k in (0, 1)]
    segs = [spans(times, speech, who, k) for k in (0, 1)]
    model = WhisperModel("medium", device="cpu", compute_type="int8")
    said = [transcribe(media, segs[k], model) for k in (0, 1)]

    if guide in ("high", "low"):
        g = int(np.argmax(pitch)) if guide == "high" else int(np.argmin(pitch))
        how = "總監指定"
    else:
        r0, r1 = repeats(said[1], said[0]), repeats(said[0], said[1])  # r0：0 號跟讀 1 號的次數
        g = 1 if r0 >= r1 else 0
        how = f"看跟讀（{max(r0, r1)} 句對 {min(r0, r1)} 句）"
    s = 1 - g

    result = {
        "similarity": round(similarity, 2),
        "separable": similarity < 0.6,
        "guide_pitch_hz": round(pitch[g]),
        "subject_pitch_hz": round(pitch[s]),
        "speakers": {"出鏡": said[s], "引導": said[g]},
        "keep": [[round(max(a - PAD_BEFORE, 0), 2), round(b + PAD_AFTER, 2)] for a, b in segs[s]],
    }
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=1)

    print(f"兩個人聲音像不像：{similarity:.2f}（0.6 以下算分得開）")
    print(f"引導的人：音高約 {pitch[g]:.0f} Hz；出鏡的人：約 {pitch[s]:.0f} Hz（{how}）")
    rows = [(x["start"], x["end"], "出鏡", x["text"]) for x in said[s]] + [(x["start"], x["end"], "引導", x["text"]) for x in said[g]]
    for a, b, w, t in sorted(rows):
        print(f"{a:7.2f}～{b:7.2f}  {w}  {t}")


if __name__ == "__main__":
    args = sys.argv[1:]
    opts = {}
    for key in ("--guide", "--om"):
        if key in args:
            k = args.index(key)
            opts[key[2:]] = args[k + 1]
            args = args[:k] + args[k + 2 :]
    main(args[0], args[1], **opts)
