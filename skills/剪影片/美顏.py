"""影片美顏：磨皮、美白、大眼、去黑眼圈、亮眼，每一項 0～100 可調（給拉霸用）。

只處理臉和脖子的皮膚（用臉部 478 個定位點畫出範圍），背景、頭髮、衣服不會跟著變糊或變白。
- 磨皮：保留輪廓的柔化，再留一點原本的膚質，不會變塑膠臉。
- 美白：皮膚提亮，同時減少泛紅和偏黃。
- 大眼：以眼睛為中心輕微放大（像放大鏡），邊緣平順銜接。
- 去黑眼圈：只提亮下眼瞼下方。
- 亮眼：瞳孔周圍加一點對比和亮度。
定位點會在前後畫面之間做平滑，大眼才不會抖。

需要：OpenMontage 的 Python 環境裡有 mediapipe==0.10.14（新版拿掉了這裡用的臉部定位）和 opencv-python。

用法：
  整支影片：python 美顏.py 輸入.mp4 輸出.mp4 --smooth 40 --whiten 30 --eyes 20 --dark-circles 40 --bright-eyes 20
  只看一格（拉霸即時預覽用）：python 美顏.py 輸入.mp4 預覽.png --preview 3.0 --smooth 40 ...
總監建議的起點：磨皮 35、美白 25、大眼 15、去黑眼圈 35、亮眼 20。拍形象照的人，修太多觀眾看得出來。
"""

import argparse
import json
import subprocess
import sys

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


def probe(path: str) -> tuple[int, int, str]:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height,r_frame_rate", "-of", "json", path],
        capture_output=True, text=True, check=True,
    ).stdout
    s = json.loads(out)["streams"][0]
    return int(s["width"]), int(s["height"]), s["r_frame_rate"]


class Beauty:
    def __init__(self, smooth, whiten, eyes, dark, bright, still=False):
        self.s, self.w, self.e, self.d, self.b = [max(0.0, min(v, 100.0)) / 100 for v in (smooth, whiten, eyes, dark, bright)]
        self.mesh = mp.solutions.face_mesh.FaceMesh(static_image_mode=still, max_num_faces=1, refine_landmarks=True,
                                                    min_detection_confidence=0.5, min_tracking_confidence=0.5)
        self.prev = None

    def landmarks(self, frame: np.ndarray):
        h, w = frame.shape[:2]
        small = cv2.resize(frame, (DETECT_W, int(h * DETECT_W / w)))
        res = self.mesh.process(cv2.cvtColor(small, cv2.COLOR_BGR2RGB))
        if not res.multi_face_landmarks:
            self.prev = None
            return None
        pts = np.array([(p.x * w, p.y * h) for p in res.multi_face_landmarks[0].landmark], np.float32)
        # 前後畫面平滑：動得少就多跟上一格，避免抖；動得多（轉頭）就直接跟上
        if self.prev is not None:
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

        # 要處理的範圍：臉部外框，加上脖子（下巴往下延伸，且顏色要像皮膚）
        xs, ys = pts[:, 0], pts[:, 1]
        face_h = ys.max() - ys.min()
        x0, x1 = int(max(xs.min() - 0.15 * face_h, 0)), int(min(xs.max() + 0.15 * face_h, w))
        y0, y1 = int(max(ys.min() - 0.1 * face_h, 0)), int(min(ys.max() + 0.7 * face_h, h))
        roi = out[y0:y1, x0:x1]
        off = np.array([x0, y0], np.float32)
        P = pts - off
        rh, rw = roi.shape[:2]

        skin = np.zeros((rh, rw), np.float32)
        self.poly(skin, P[FACE_OVAL])
        jaw = P[JAW]
        neck = np.vstack([jaw, (jaw + np.array([0, 0.6 * face_h]))[::-1]])
        neck_mask = np.zeros_like(skin)
        self.poly(neck_mask, neck)
        ycc = cv2.cvtColor(roi, cv2.COLOR_BGR2YCrCb)
        skin_color = ((ycc[..., 1] > 133) & (ycc[..., 1] < 178) & (ycc[..., 2] > 77) & (ycc[..., 2] < 135)).astype(np.float32)
        skin = np.maximum(skin, neck_mask * skin_color)
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


def run_video(src: str, dst: str, beauty: Beauty) -> None:
    w, h, fps = probe(src)
    reader = subprocess.Popen(["ffmpeg", "-v", "error", "-i", src, "-f", "rawvideo", "-pix_fmt", "bgr24", "-"], stdout=subprocess.PIPE)
    writer = subprocess.Popen(
        ["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{w}x{h}", "-r", fps, "-i", "-",
         "-i", src, "-map", "0:v", "-map", "1:a?", "-c:v", "libx264", "-preset", "medium", "-crf", "16",
         "-pix_fmt", "yuv420p", "-c:a", "copy", "-shortest", dst],
        stdin=subprocess.PIPE,
    )
    size = w * h * 3
    n = 0
    while True:
        buf = reader.stdout.read(size)
        if len(buf) < size:
            break
        frame = np.frombuffer(buf, np.uint8).reshape(h, w, 3).copy()
        writer.stdin.write(beauty.apply(frame).tobytes())
        n += 1
    writer.stdin.close()
    writer.wait()
    reader.wait()
    print(dst, f"{n} 格")


def run_preview(src: str, dst: str, t: float, beauty: Beauty) -> None:
    w, h, _ = probe(src)
    raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", str(t), "-i", src, "-frames:v", "1", "-f", "rawvideo", "-pix_fmt", "bgr24", "-"],
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
    a = ap.parse_args()
    b = Beauty(a.smooth, a.whiten, a.eyes, a.dark_circles, a.bright_eyes, still=a.preview is not None)
    if a.preview is not None:
        run_preview(a.src, a.dst, a.preview, b)
    else:
        run_video(a.src, a.dst, b)
    sys.exit(0)
