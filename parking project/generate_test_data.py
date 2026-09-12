"""
generate_test_data.py
Creates synthetic vehicle images and short test video clips with clear license
plate text, so the ANPR system can be tested immediately without physical hardware.

Run: python generate_test_data.py
Output: static/uploads/sample_car1.jpg, sample_car2.jpg, sample_bike1.jpg,
        static/uploads/sample_video1.mp4, sample_video2.mp4
"""
import os
import cv2
import numpy as np

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(BASE_DIR, "static", "uploads")
os.makedirs(OUTPUT_DIR, exist_ok=True)

SAMPLE_PLATES = ["KA01AB1234", "DL08CZ5678", "MH12XY9988"]


def draw_vehicle_scene(plate_text: str, width=800, height=500, body_color=(90, 90, 90)):
    """Draws a very simple synthetic 'vehicle' rectangle with a license plate on it."""
    img = np.full((height, width, 3), (235, 235, 235), dtype=np.uint8)  # light background

    # Ground line
    cv2.line(img, (0, height - 80), (width, height - 80), (180, 180, 180), 4)

    # Vehicle body (rounded rectangle approximation)
    body_top_left = (width // 2 - 220, height // 2 - 90)
    body_bottom_right = (width // 2 + 220, height // 2 + 90)
    cv2.rectangle(img, body_top_left, body_bottom_right, body_color, -1)
    cv2.rectangle(img, body_top_left, body_bottom_right, (30, 30, 30), 3)

    # Windshield
    cv2.rectangle(img, (width // 2 - 150, height // 2 - 80), (width // 2 + 150, height // 2 - 10),
                  (160, 200, 220), -1)

    # Wheels
    cv2.circle(img, (width // 2 - 140, height // 2 + 90), 35, (20, 20, 20), -1)
    cv2.circle(img, (width // 2 + 140, height // 2 + 90), 35, (20, 20, 20), -1)

    # License plate (white rectangle with black border, centered lower on body)
    plate_w, plate_h = 220, 60
    px = width // 2 - plate_w // 2
    py = height // 2 + 15
    cv2.rectangle(img, (px, py), (px + plate_w, py + plate_h), (255, 255, 255), -1)
    cv2.rectangle(img, (px, py), (px + plate_w, py + plate_h), (0, 0, 0), 3)

    # Plate text
    font = cv2.FONT_HERSHEY_SIMPLEX
    font_scale = 1.1
    thickness = 3
    text_size = cv2.getTextSize(plate_text, font, font_scale, thickness)[0]
    text_x = px + (plate_w - text_size[0]) // 2
    text_y = py + (plate_h + text_size[1]) // 2
    cv2.putText(img, plate_text, (text_x, text_y), font, font_scale, (0, 0, 0), thickness)

    return img


def generate_sample_images():
    body_colors = [(90, 90, 90), (60, 60, 160), (30, 120, 60)]
    for i, plate in enumerate(SAMPLE_PLATES, start=1):
        img = draw_vehicle_scene(plate, body_color=body_colors[(i - 1) % len(body_colors)])
        out_path = os.path.join(OUTPUT_DIR, f"sample_car{i}.jpg")
        cv2.imwrite(out_path, img)
        print(f"Created {out_path}  (plate: {plate})")


def generate_sample_videos(num_videos=2, fps=15, duration_sec=3):
    for v in range(1, num_videos + 1):
        plate = SAMPLE_PLATES[(v - 1) % len(SAMPLE_PLATES)]
        out_path = os.path.join(OUTPUT_DIR, f"sample_video{v}.mp4")
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        width, height = 800, 500
        writer = cv2.VideoWriter(out_path, fourcc, fps, (width, height))

        total_frames = fps * duration_sec
        for f in range(total_frames):
            # Simulate the vehicle driving in from the left toward center
            progress = f / max(1, total_frames - 1)
            offset_x = int((1 - progress) * -250)
            frame = draw_vehicle_scene(plate, width, height)
            M = np.float32([[1, 0, offset_x], [0, 1, 0]])
            frame = cv2.warpAffine(frame, M, (width, height), borderValue=(235, 235, 235))
            writer.write(frame)

        writer.release()
        print(f"Created {out_path}  (plate: {plate}, {total_frames} frames @ {fps}fps)")


if __name__ == "__main__":
    print("Generating synthetic ANPR test media...")
    generate_sample_images()
    generate_sample_videos()
    print("\nDone. Use these files to test /entry and /exit via file upload:")
    print(f"  Images: {OUTPUT_DIR}/sample_car1.jpg, sample_car2.jpg, sample_car3.jpg")
    print(f"  Videos: {OUTPUT_DIR}/sample_video1.mp4, sample_video2.mp4")
