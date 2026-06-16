import os
from maix import camera, display, image, nn, gpio

# ==========================================
# 1. HARDWARE & CONFIGURATION SETUP
# ==========================================
HIGH_RES_W, HIGH_RES_H = 1920, 1080  # Độ phân giải chụp và hiển thị

cam = camera.Camera(HIGH_RES_W, HIGH_RES_H, image.Format.FMT_RGB888)
disp = display.Display()
#motion_sensor = gpio.GPIO("PA17", gpio.Mode.IN, gpio.Pull.PULL_DOWN)
motion_sensor = 1
# ==========================================
# 2. NPU MODEL LOADING (MaixPy v4 Wrapper)
# ==========================================
# nn.FaceRecognizer gộp chung 2 model lại. Tham số dual_buff=True giúp pipeline chạy đa luồng để tăng FPS.
recognizer = nn.FaceRecognizer(
    detect_model="/root/models/retinaface.mud",
    feature_model="/root/models/face_feature.mud",
    dual_buff=True
)

# Hệ thống tự động quản lý Database. File .bin lưu trữ cả vector và label (tên).
DB_PATH = "/root/faces.bin"
if os.path.exists(DB_PATH):
    recognizer.load_faces(DB_PATH)
    print("Đã nạp cơ sở dữ liệu khuôn mặt.")

# ==========================================
# 3. CORE PROCESSING PIPELINE
# ==========================================
print("Hệ thống sẵn sàng. Đang chờ tín hiệu chuyển động...")

while True:
    # 1. Liên tục chụp ảnh độ phân giải cao
    img_high_res = cam.read()
    
    # 2. Kích hoạt khi có chuyển động
    # Reminder: Use motion_sensor.value() if use real sensor
    if motion_sensor == 1:
        img_high_res.draw_string(20, 20, "Motion Detected! Scanning...", scale=2, color=image.COLOR_RED)
        
        # Hàm recognize tự động scale ảnh cho NPU và trả về tọa độ chính xác cho ảnh gốc
        # 0.5: Ngưỡng phát hiện | 0.45: Ngưỡng IOU | 0.85: Ngưỡng tin cậy nhận diện (Cosine)
        faces = recognizer.recognize(img_high_res, 0.5, 0.45, 0.85)
        
        for obj in faces:
            # class_id == 0 luôn mặc định là "unknown" (người lạ)
            if obj.class_id == 0:
                color = image.COLOR_RED
            else:
                color = image.COLOR_GREEN
                
            img_high_res.draw_rect(obj.x, obj.y, obj.w, obj.h, color=color, thickness=3)
            
            # Trích xuất tên từ danh sách nhãn mặc định của recognizer
            label = recognizer.labels[obj.class_id]
            msg = f"{label} ({obj.score:.2f})"
            img_high_res.draw_string(obj.x, obj.y - 30, msg, scale=2, color=color)
            
    # Hiển thị ra màn hình
    disp.show(img_high_res)