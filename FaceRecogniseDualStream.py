"""
Dual-stream face recognition for MaixCAM.

Stream 1 (AI):  camera at recognizer.input_width/height — fast NPU inference
Stream 2 (LCD): add_channel() at high resolution — sharp preview on screen

Why RetinaFace only?
  nn.FaceRecognizer bundles detection + alignment + feature extraction.
  The detect_model must be one of MaixPy's supported face detectors that
  output landmarks for alignment:
    - retinaface.mud          + face_feature.mud           (this script)
    - yolov8n_face.mud        + insghtface_webface_r50.mud
    - face_detector.mud       + face_feature.mud
  You cannot plug in a random nn.YOLOv8 or nn.FaceDetector separately —
  FaceRecognizer.recognize() owns the full pipeline.

  If yolov8n_face fails on your firmware, stay on retinaface.mud.

Memory tip:
  Lower DISPLAY_W/H or set CAM_BUFF_NUM=2 if OOM.
  Disable MaixVision image preview when using 1280x720+.
"""

import math
import os

from maix import app, camera, display, image, nn

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
DETECT_MODEL = "/root/models/retinaface.mud"
FEATURE_MODEL = "/root/models/face_feature.mud"
DB_PATH = "/root/faces.bin"

# High-res display channel (adjust to your panel / memory budget)
# 1280x720 is a good balance; try 1920x1080 if you have headroom
DISPLAY_W, DISPLAY_H = 1280, 720
CAM_BUFF_NUM = 2  # lower = less RAM, higher = smoother capture

DETECT_TH = 0.5
IOU_TH = 0.45
RECOGNIZE_TH = 0.85

# Stub — replace with real LD2410 / GPIO gate later
MOTION_ACTIVE = True


def scale_box(obj, sx, sy):
    """Map detection box from AI frame coords to display frame coords."""
    return (
        int(obj.x * sx),
        int(obj.y * sy),
        int(obj.w * sx),
        int(obj.h * sy),
    )


def scale_points(points, sx, sy):
    """Map landmark keypoints to display frame coords."""
    if not points:
        return []
    scaled = []
    for p in points:
        scaled.append((int(p[0] * sx), int(p[1] * sy)))
    return scaled


def draw_face_overlay(img_disp, obj, label, sx, sy):
    x, y, w, h = scale_box(obj, sx, sy)
    if obj.class_id == 0:
        color = image.COLOR_RED
    else:
        color = image.COLOR_GREEN

    img_disp.draw_rect(x, y, w, h, color=color, thickness=2)

    pts = scale_points(obj.points, sx, sy)
    if pts:
        radius = math.ceil(w / 10)
        radius = radius if radius < 5 else 4
        img_disp.draw_keypoints(pts, color, size=radius)

    msg = f"{label} ({obj.score:.2f})"
    ty = max(y - 24, 0)
    img_disp.draw_string(x, ty, msg, scale=1.5, color=color)


def main():
    # dual_buff=True pipelines CPU prep with NPU inference (higher FPS, 1-frame lag)
    recognizer = nn.FaceRecognizer(
        detect_model=DETECT_MODEL,
        feature_model=FEATURE_MODEL,
        dual_buff=True,
    )

    if os.path.exists(DB_PATH):
        recognizer.load_faces(DB_PATH)
        print("Loaded face database:", DB_PATH)

    ai_w = recognizer.input_width()
    ai_h = recognizer.input_height()
    ai_fmt = recognizer.input_format()
    print(f"AI stream: {ai_w}x{ai_h}  Display stream: {DISPLAY_W}x{DISPLAY_H}")

    # Primary channel = AI resolution (matches RetinaFace .mud input)
    cam_ai = camera.Camera(ai_w, ai_h, ai_fmt, buff_num=CAM_BUFF_NUM)
    # Secondary channel = high-res for LCD (same sensor, independent scaler)
    cam_disp = cam_ai.add_channel(DISPLAY_W, DISPLAY_H, image.Format.FMT_RGB888, buff_num=CAM_BUFF_NUM)

    disp = display.Display()

    sx = DISPLAY_W / ai_w
    sy = DISPLAY_H / ai_h

    print("Dual-stream ready. AI on ch0, display on ch1.")

    while not app.need_exit():
        img_ai = cam_ai.read()
        img_disp = cam_disp.read()

        if MOTION_ACTIVE:
            faces = recognizer.recognize(img_ai, DETECT_TH, IOU_TH, RECOGNIZE_TH)

            for obj in faces:
                label = recognizer.labels[obj.class_id]
                draw_face_overlay(img_disp, obj, label, sx, sy)
        else:
            img_disp.draw_string(10, 10, "Waiting for presence...", scale=1.5, color=image.COLOR_WHITE)

        disp.show(img_disp)


if __name__ == "__main__":
    main()
