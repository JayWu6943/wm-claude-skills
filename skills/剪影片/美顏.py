"""影片美顏：磨皮、美白、大眼、去黑眼圈、亮眼，每一項 0～100 可調（給拉霸用）。

2026-10-28 在總監的 Mac（薇萌剪片工具）實測後修了這幾件事，效果的算法其他都照原版：
- 手機直拍的影片有「旋轉標記」，原版把畫面當成橫的讀，整個畫面會變成一條條雜訊。現在照旋轉後的實際大小讀。
- 效果數值可以隨時換（拉霸即時預覽時不用每次重新載入找臉的模型）。
- 整支輸出時會回報進度（第幾格、每秒幾格），工具畫面才能顯示「還要多久」。
- 可以用 Mac 的硬體編碼器輸出中間檔（--fast，快很多，畫質用高位元率顧住）。
- 美白拉高時臉白、胸口不白看得出一條線 → 處理範圍往下延伸到胸口、越往下越淡。
- 額頭靠髮際線那一條沒處理、美白後偏黃 → 臉框上半部往上擴，碰到頭髮的會被擋掉。
- 蓋在臉頰的頭髮數值高時被磨糊 → 比皮膚暗很多的地方不處理。
- 整個畫面（連背景）變暗一點 → 顏色換算照原片規格並開精確進位，讀進來再寫出去完全不變色。

只處理臉和脖子的皮膚（用臉部 478 個定位點畫出範圍），背景、頭髮、衣服不會跟著變糊或變白。
- 磨皮：保留輪廓的柔化，再留一點原本的膚質，不會變塑膠臉。
- 美白：皮膚提亮，同時減少泛紅和偏黃。
- 大眼：以眼睛為中心輕微放大（像放大鏡），邊緣平順銜接。
- 去黑眼圈：只提亮下眼瞼下方。
- 亮眼：瞳孔周圍加一點對比和亮度。
定位點會在前後畫面之間做平滑，大眼才不會抖。

需要：mediapipe==0.10.14（新版拿掉了這裡用的臉部定位）和 opencv-python。
它跟新版 numpy 的其他套件常常互相打架，建議放在自己的 Python 環境（例如薇萌剪片工具的「.venv-美顏」）。

用法：
  整支影片：python 美顏.py 輸入.mp4 輸出.mp4 --smooth 40 --whiten 30 --eyes 20 --dark-circles 40 --bright-eyes 20
  只看一格：python 美顏.py 輸入.mp4 預覽.png --preview 3.0 --smooth 40 ...
總監建議的起點：磨皮 35、美白 25、大眼 15、去黑眼圈 35、亮眼 20。拍形象照的人，修太多觀眾看得出來。
"""

import argparse
import json
import subprocess
import sys
import time

import cv2
import mediapipe as mp
import numpy as np

FACE_OVAL = [10, 338, 297, 332, 284, 251, 389, 356, 454, 323, 361, 288, 397, 365, 379, 378, 400, 377,
             152, 148, 176, 149, 150, 136, 172, 58, 132, 93, 234, 127, 162, 21, 54, 103, 67, 109]
JAW = [172, 136, 150, 149, 176, 148, 152, 377, 400, 378, 379, 365, 397]
EYE_R = [33, 7, 163, 144, 145, 153, 154, 155, 133, 173, 157, 158, 159, 160, 161, 246]
EYE_L = [263, 249, 390, 373, 374, 380, 381, 382, 362, 398, 384, 385, 386, 387, 388, 466]
LOWER_R = [33, 7, 163, 144, 145, 153, 154, 155, 133]
LOWER_L = [362, 382, 381, 380, 374, 373, 390, 249, 263]
BROW_R = [46, 53, 52, 65, 55, 70, 63, 105, 66, 107]
BROW_L = [276, 283, 282, 295, 285, 300, 293, 334, 296, 336]
LIPS = [61, 146, 91, 181, 84, 17, 314, 405, 321, 375, 291, 409, 270, 269, 267, 0, 37, 39, 40, 185]
IRIS_R, IRIS_L = 468, 473
DETECT_W = 540  # 找臉時先縮小，比較快
DEFAULTS = {"smooth": 35, "whiten": 25, "eyes": 15, "dark": 35, "bright": 20}


def probe(path: str) -> tuple[int, int, str]:
    """回傳「轉正之後」的寬、高和幀數。手機直拍的檔案寬高是橫的、另外記一個旋轉角度，ffmpeg 讀出來會自動轉正。"""
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height,r_frame_rate:stream_side_data=rotation:stream_tags=rotate",
         "-of", "json", path],
        capture_output=True, text=True, check=True,
    ).stdout
    s = json.loads(out)["streams"][0]
    w, h = int(s["width"]), int(s["height"])
    rot = 0
    for sd in s.get("side_data_list", []) or []:
        if "rotation" in sd:
            rot = int(round(float(sd["rotation"])))
    if not rot and (s.get("tags") or {}).get("rotate"):
        rot = int(s["tags"]["rotate"])
    if rot % 180:
        w, h = h, w
    return w, h, s["r_frame_rate"]

SWS = "flags=accurate_rnd+full_chroma_int"


def color_space(src: str) -> str:
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=color_space", "-of", "csv=p=0", src],
                         capture_output=True, text=True).stdout.strip().split(",")[0]
    return "bt709" if out == "bt709" else "bt601"


def color_args(src: str) -> tuple[list[str], list[str]]:
    """讀進來／寫出去的顏色換算。2026-10-28 實測：ffmpeg 預設的換算每來回一次亮度掉 1.6～2.1（整個畫面連背景都變暗），
    雲端版就有這個問題；照原片的規格（手機是 bt709）並開「精確進位」，來回一次完全不變（差 0.0）。"""
    m = color_space(src)
    read = ["-vf", f"scale=in_color_matrix={m}:in_range=tv:{SWS}"]
    write = ["-vf", f"scale=out_color_matrix={m}:out_range=tv:{SWS}"]
    if m == "bt709":
        write += ["-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709", "-color_range", "tv"]
    return read, write


class Beauty:
    def __init__(self, smooth=0, whiten=0, eyes=0, dark=0, bright=0, still=False):
        self.set(smooth, whiten, eyes, dark, bright)
        self.still = still
        self.mesh = mp.solutions.face_mesh.FaceMesh(static_image_mode=still, max_num_faces=1, refine_landmarks=True,
                                                    min_detection_confidence=0.5, min_tracking_confidence=0.5)
        self.prev = None
        self.last_pts = None

    def set(self, smooth, whiten, eyes, dark, bright):
        self.s, self.w, self.e, self.d, self.b = [max(0.0, min(float(v), 100.0)) / 100 for v in (smooth, whiten, eyes, dark, bright)]

    def landmarks(self, frame: np.ndarray):
        h, w = frame.shape[:2]
        small = cv2.resize(frame, (DETECT_W, int(h * DETECT_W / w)))
        res = self.mesh.process(cv2.cvtColor(small, cv2.COLOR_BGR2RGB))
        if not res.multi_face_landmarks:
            self.prev = None
            return None
        pts = np.array([(p.x * w, p.y * h) for p in res.multi_face_landmarks[0].landmark], np.float32)
        # 前後畫面平滑：動得少就多跟上一格，避免抖；動得多（轉頭）就直接跟上
        if self.prev is not None and not self.still:
            move = np.linalg.norm(pts - self.prev, axis=1).mean()
            a = 0.35 if move < 6 else 0.8
            pts = self.prev + (pts - self.prev) * a
        self.prev = pts
        return pts

    @staticmethod
    def poly(mask: np.ndarray, pts: np.ndarray, value=1.0):
        cv2.fillPoly(mask, [np.round(pts).astype(np.int32)], value)

    def eye_bulge(self, img: np.ndarray, center: np.ndarray, radius: float, amount: float) -> np.ndarray:
        h, w = img.shape[:2]
        r = int(radius) + 2
        x0, y0 = max(int(center[0]) - r, 0), max(int(center[1]) - r, 0)
        x1, y1 = min(int(center[0]) + r, w), min(int(center[1]) + r, h)
        if x1 <= x0 or y1 <= y0:
            return img
        yy, xx = np.mgrid[y0:y1, x0:x1].astype(np.float32)
        dx, dy = xx - center[0], yy - center[1]
        d2 = (dx * dx + dy * dy) / (radius * radius)
        k = np.where(d2 < 1, 1 - amount * (1 - d2) ** 2, 1).astype(np.float32)
        mx, my = center[0] + dx * k, center[1] + dy * k
        img[y0:y1, x0:x1] = cv2.remap(img, mx, my, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
        return img

    def apply(self, frame: np.ndarray) -> np.ndarray:
        if max(self.s, self.w, self.e, self.d, self.b) == 0:
            return frame
        pts = self.landmarks(frame)
        self.last_pts = pts
        if pts is None:
            return frame
        out = frame.copy()
        h, w = out.shape[:2]
        eye_w_r = np.linalg.norm(pts[33] - pts[133])
        eye_w_l = np.linalg.norm(pts[362] - pts[263])

        # 大眼：先改形狀，其他效果再疊上去
        if self.e > 0:
            for c, ew in ((pts[IRIS_R], eye_w_r), (pts[IRIS_L], eye_w_l)):
                out = self.eye_bulge(out, c, ew * 0.95, self.e * 0.22)

        # 要處理的範圍：臉部外框，加上脖子和胸口（下巴往下延伸，且顏色要像皮膚）
        # 2026-10-28 改：原版脖子只到下巴下 0.6 張臉、而且是硬邊，美白拉高時臉白、胸口不白，看得出一條線。
        # 現在往下延伸到 1.1 張臉、往下越來越淡（下巴下 0.35 張臉以內是全強度），左右也放寬一點。
        xs, ys = pts[:, 0], pts[:, 1]
        face_h = ys.max() - ys.min()
        x0, x1 = int(max(xs.min() - 0.3 * face_h, 0)), int(min(xs.max() + 0.3 * face_h, w))
        y0, y1 = int(max(ys.min() - 0.2 * face_h, 0)), int(min(ys.max() + 1.15 * face_h, h))
        roi = out[y0:y1, x0:x1]
        off = np.array([x0, y0], np.float32)
        P = pts - off
        rh, rw = roi.shape[:2]

        ycc = cv2.cvtColor(roi, cv2.COLOR_BGR2YCrCb)
        face = np.zeros((rh, rw), np.float32)
        # 臉部外框的上緣在額頭中間，上面那一條額頭（髮際線前）原版不會處理，美白一拉高就看得出一條偏黃的帶子。
        # 上半部往上推 0.2 張臉；推到頭髮的部分會被下面「暗很多的不處理」擋掉。
        oval = P[FACE_OVAL].copy()
        cy, top = float(oval[:, 1].mean()), float(oval[:, 1].min())
        up = oval[:, 1] < cy
        oval[up, 1] -= 0.2 * face_h * (cy - oval[up, 1]) / max(cy - top, 1.0)
        self.poly(face, oval)
        # 臉框裡的頭髮（蓋在臉頰、額頭上的）比皮膚暗很多：照這張臉皮膚的中位亮度，暗很多的地方不處理，頭髮才不會被磨糊、變白
        Y = ycc[..., 0].astype(np.float32)
        y_med = float(np.median(Y[face > 0])) if (face > 0).any() else 128.0
        light = np.clip((Y - 0.5 * y_med) / max(0.25 * y_med, 1.0), 0, 1)
        light = cv2.GaussianBlur(light, (5, 5), 0)
        skin = face * light
        jaw = P[JAW]
        cx = float(jaw[:, 0].mean())
        bottom = jaw.copy()
        bottom[:, 0] = cx + (bottom[:, 0] - cx) * 1.35
        bottom[:, 1] += 1.1 * face_h
        neck_mask = np.zeros_like(skin)
        self.poly(neck_mask, np.vstack([jaw, bottom[::-1]]))
        chin_y = float(P[152][1])
        yy = np.arange(rh, dtype=np.float32)[:, None]
        neck_mask *= np.clip(1 - (yy - (chin_y + 0.35 * face_h)) / (0.75 * face_h), 0, 1)
        skin_color = ((ycc[..., 1] > 133) & (ycc[..., 1] < 178) & (ycc[..., 2] > 77) & (ycc[..., 2] < 135)).astype(np.float32)
        skin = np.maximum(skin, neck_mask * skin_color * light)
        for part in (EYE_R, EYE_L, LIPS):
            self.poly(skin, P[part], 0.0)
        for brow in (BROW_R, BROW_L):
            self.poly(skin, cv2.convexHull(P[brow]).reshape(-1, 2), 0.0)
        feather = max(int(face_h * 0.04) | 1, 3)
        skin = cv2.GaussianBlur(skin, (feather * 2 + 1, feather * 2 + 1), 0)[..., None]

        work = roi.astype(np.float32)
        if self.s > 0:  # 磨皮：保留輪廓的柔化，留 25% 原本的膚質
            bil = cv2.bilateralFilter(roi, 0, 25 + 45 * self.s, max(face_h * 0.012, 3)).astype(np.float32)
            work = work + (bil - work) * (0.85 * self.s) * skin
        lab = cv2.cvtColor(np.clip(work, 0, 255).astype(np.uint8), cv2.COLOR_BGR2LAB).astype(np.float32)
        if self.w > 0:  # 美白：提亮，減少泛紅、偏黃
            m = skin[..., 0]
            lab[..., 0] += (255 - lab[..., 0]) * 0.22 * self.w * m
            lab[..., 1] = 128 + (lab[..., 1] - 128) * (1 - 0.3 * self.w * m)
            lab[..., 2] = 128 + (lab[..., 2] - 128) * (1 - 0.2 * self.w * m)
        if self.d > 0:  # 去黑眼圈：下眼瞼下方提亮
            under = np.zeros((rh, rw), np.float32)
            for lid, ew in ((P[LOWER_R], eye_w_r), (P[LOWER_L], eye_w_l)):
                band = np.vstack([lid, (lid + np.array([0, 0.38 * ew]))[::-1]])
                self.poly(under, band)
            k = max(int(min(eye_w_r, eye_w_l) * 0.25) | 1, 3)
            under = cv2.GaussianBlur(under, (k * 2 + 1, k * 2 + 1), 0)
            lab[..., 0] += 14 * self.d * under
            lab[..., 2] = 128 + (lab[..., 2] - 128) * (1 - 0.3 * self.d * under)
        if self.b > 0:  # 亮眼：眼睛裡面加一點對比和亮度
            eye = np.zeros((rh, rw), np.float32)
            for part in (EYE_R, EYE_L):
                self.poly(eye, P[part])
            eye = cv2.GaussianBlur(eye, (5, 5), 0)
            L = lab[..., 0]
            mean = (L * eye).sum() / max(eye.sum(), 1)
            lab[..., 0] = L + ((mean + (L - mean) * (1 + 0.35 * self.b) + 6 * self.b) - L) * eye
        lab = np.clip(lab, 0, 255).astype(np.uint8)
        out[y0:y1, x0:x1] = cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)
        return out


def _encoder(fast: bool) -> list[str]:
    if fast:
        encs = subprocess.run(["ffmpeg", "-hide_banner", "-encoders"], capture_output=True, text=True).stdout
        if "h264_videotoolbox" in encs:
            return ["-c:v", "h264_videotoolbox", "-b:v", "28M", "-allow_sw", "1"]
    return ["-c:v", "libx264", "-preset", "medium", "-crf", "16"]


def run_video(src: str, dst: str, beauty: Beauty, fast: bool = False, report: bool = False) -> None:
    w, h, fps = probe(src)
    total = 0
    if report:
        try:
            total = int(subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-count_packets", "-show_entries", "stream=nb_read_packets",
                                        "-of", "csv=p=0", src], capture_output=True, text=True, check=True).stdout.strip().split(",")[0])
        except Exception:  # noqa: BLE001
            total = 0
    rd, wr = color_args(src)
    reader = subprocess.Popen(["ffmpeg", "-v", "error", "-i", src, *rd, "-f", "rawvideo", "-pix_fmt", "bgr24", "-"], stdout=subprocess.PIPE)
    writer = subprocess.Popen(
        ["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{w}x{h}", "-r", fps, "-i", "-",
         "-i", src, "-map", "0:v", "-map", "1:a?", *wr, *_encoder(fast),
         "-pix_fmt", "yuv420p", "-c:a", "copy", "-shortest", dst],
        stdin=subprocess.PIPE,
    )
    size = w * h * 3
    n = 0
    t0 = time.time()
    while True:
        buf = reader.stdout.read(size)
        if len(buf) < size:
            break
        frame = np.frombuffer(buf, np.uint8).reshape(h, w, 3).copy()
        writer.stdin.write(beauty.apply(frame).tobytes())
        n += 1
        if report and n % 15 == 0:
            el = time.time() - t0
            print(json.dumps({"frames": n, "total": total, "fps": round(n / max(el, 1e-6), 2)}), flush=True)
    writer.stdin.close()
    writer.wait()
    reader.wait()
    if writer.returncode != 0:
        raise SystemExit(f"美顏輸出失敗（ffmpeg {writer.returncode}）")
    if report:
        print(json.dumps({"frames": n, "total": total or n, "done": True, "seconds": round(time.time() - t0, 1)}), flush=True)
    else:
        print(dst, f"{n} 格")


def run_preview(src: str, dst: str, t: float, beauty: Beauty) -> None:
    w, h, _ = probe(src)
    rd, _ = color_args(src)
    raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", str(t), "-i", src, "-frames:v", "1", *rd, "-f", "rawvideo", "-pix_fmt", "bgr24", "-"],
                         capture_output=True, check=True).stdout
    frame = np.frombuffer(raw, np.uint8).reshape(h, w, 3).copy()
    cv2.imwrite(dst, beauty.apply(frame))
    print(dst)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="影片美顏（0～100）")
    ap.add_argument("src")
    ap.add_argument("dst")
    ap.add_argument("--smooth", type=float, default=0, help="磨皮")
    ap.add_argument("--whiten", type=float, default=0, help="美白")
    ap.add_argument("--eyes", type=float, default=0, help="大眼")
    ap.add_argument("--dark-circles", type=float, default=0, help="去黑眼圈")
    ap.add_argument("--bright-eyes", type=float, default=0, help="亮眼")
    ap.add_argument("--preview", type=float, help="只處理這一秒的一格，輸出圖片")
    ap.add_argument("--fast", action="store_true", help="用 Mac 硬體編碼器輸出（中間檔用）")
    ap.add_argument("--progress", action="store_true", help="每 15 格印一行進度（給工具畫面用）")
    a = ap.parse_args()
    b = Beauty(a.smooth, a.whiten, a.eyes, a.dark_circles, a.bright_eyes, still=a.preview is not None)
    if a.preview is not None:
        run_preview(a.src, a.dst, a.preview, b)
    else:
        run_video(a.src, a.dst, b, fast=a.fast, report=a.progress)
    sys.exit(0)
