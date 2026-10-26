"""剪之前檢查：剪輯表裡每一段，有沒有混到另一個人的聲音。

兩個人接話很緊時，引導的人常在出鏡的人還沒講完就開始講下一句，聲音會疊在段落頭尾。
這支用更細的聲紋（每 0.05 秒取 0.5 秒）把每一段掃一遍，列出「聽起來像另一個人」的位置，
看到就把那一段的頭或尾修短（或拆成兩段）再掃一次，直到沒有為止。

剪輯表（JSON）：[[開始秒, 結束秒, "S" 或 "Q", "字幕文字"], ...]
  S = 出鏡的人講的（不該有引導的人的聲音）；Q = 藏鏡人提問（不該有出鏡的人的聲音）

用法：python 檢查漏剪.py 原片.mp4 剪輯表.json [--guide high|low] [--om OpenMontage 資料夾]
只列出有問題的段落；「像別人」那欄是（段內第幾秒, 像引導的人, 像出鏡的人）。兩個分數差不到 0.03 的多半是誤判，可以不管。
"""

import importlib.util
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("who", os.path.join(HERE, "誰在講.py"))
who = importlib.util.module_from_spec(spec)
spec.loader.exec_module(who)

SR = who.SR
W, H = 0.5, 0.05


def main(media: str, table_path: str, guide: str = "high", om: str = "/home/user/OpenMontage") -> None:
    import sherpa_onnx

    model = os.path.join(om, "models/eres2net_zh.onnx")
    with open(table_path, encoding="utf-8") as f:
        table = json.load(f)
    audio = who.load_audio(media)
    times, speech, f0 = who.frames(audio)
    starts, embs = who.voiceprints(audio, speech, model)
    lab, centers = who.two_people(embs)
    pitch = []
    for k in (0, 1):
        m = np.zeros(len(times), bool)
        for s in starts[lab == k]:
            m[int(s / 0.01) : int((s + who.WIN) / 0.01)] = True
        pitch.append(np.median(f0[m & (f0 > 0)]))
    g = int(np.argmax(pitch)) if guide == "high" else int(np.argmin(pitch))
    s_ = 1 - g

    ex = sherpa_onnx.SpeakerEmbeddingExtractor(sherpa_onnx.SpeakerEmbeddingExtractorConfig(model=model, num_threads=os.cpu_count() or 2))

    def emb(a: float) -> np.ndarray:
        st = ex.create_stream()
        st.accept_waveform(SR, audio[int(a * SR) : int((a + W) * SR)])
        st.input_finished()
        e = np.array(ex.compute(st))
        return e / np.linalg.norm(e)

    problems = 0
    for i, (a, b, role, text) in enumerate(table):
        flags, t = [], a
        while t + W <= b + 1e-6:
            m = (times >= t) & (times < t + W)
            if speech[m].mean() > 0.3:
                e = emb(t)
                sg, ss = float(e @ centers[g]), float(e @ centers[s_])
                wrong = sg - ss if role == "S" else ss - sg
                if wrong > 0.03:
                    flags.append((round(t - a, 2), round(sg, 2), round(ss, 2)))
            t += H
        if flags:
            problems += 1
            print(f"第 {i} 段 {role}「{text}」（{a}～{b}）像別人：{flags[:6]}")
    print("全部乾淨" if not problems else f"有 {problems} 段要修")


if __name__ == "__main__":
    args = sys.argv[1:]
    opts = {}
    for key in ("--guide", "--om"):
        if key in args:
            k = args.index(key)
            opts[key[2:]] = args[k + 1]
            args = args[:k] + args[k + 2 :]
    main(args[0], args[1], **opts)
