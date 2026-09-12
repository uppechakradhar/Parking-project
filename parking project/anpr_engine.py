"""
anpr_engine.py
OpenCV-based license plate localization + OCR recognition.

Pipeline:
  1. Grayscale conversion
  2. Bilateral filter (noise reduction while keeping edges sharp)
  3. Canny edge detection
  4. Contour detection, filtered by rectangular aspect ratio (plates are wide rectangles)
  5. Crop candidate region(s) and run OCR (EasyOCR if available, else pytesseract,
     else a morphological contour-count heuristic as a last resort)
  6. Normalize the recognized string with regex to look like a real plate

Supports: single images, video files (samples frames), and live camera/RTSP streams
(frame-by-frame, same detect_and_recognize() call per frame).
"""
import re
import os
import cv2
import numpy as np

# ---- OCR backends (graceful fallback) -------------------------------------------------
_EASYOCR_READER = None
_EASYOCR_AVAILABLE = False
try:
    import easyocr  # heavy, optional
    _EASYOCR_AVAILABLE = True
except ImportError:
    _EASYOCR_AVAILABLE = False

_TESSERACT_AVAILABLE = False
try:
    import pytesseract
    _TESSERACT_AVAILABLE = True
except ImportError:
    _TESSERACT_AVAILABLE = False


def _get_easyocr_reader():
    global _EASYOCR_READER
    if _EASYOCR_READER is None and _EASYOCR_AVAILABLE:
        _EASYOCR_READER = easyocr.Reader(["en"], gpu=False)
    return _EASYOCR_READER


# Common plate formats. Generic alphanumeric fallback included.
PLATE_PATTERNS = [
    r"[A-Z]{2}[0-9]{2}[A-Z]{1,2}[0-9]{4}",   # e.g. KA01AB1234 (Indian format)
    r"[A-Z]{3}[0-9]{3,4}",                    # generic e.g. ABC1234
    r"[A-Z0-9]{5,10}",                        # generic alphanumeric fallback
]


def normalize_plate_text(raw_text: str) -> str:
    """Strip whitespace/special chars, uppercase, and try to match a known plate pattern."""
    if not raw_text:
        return ""
    cleaned = re.sub(r"[^A-Za-z0-9]", "", raw_text).upper()
    for pattern in PLATE_PATTERNS:
        match = re.search(pattern, cleaned)
        if match:
            return match.group(0)
    return cleaned


def locate_plate_candidates(image: np.ndarray):
    """
    Preprocess and find rectangular contour candidates likely to be a license plate.
    Returns a list of (x, y, w, h) bounding boxes, sorted by contour area (largest first).
    """
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    filtered = cv2.bilateralFilter(gray, 11, 17, 17)
    edged = cv2.Canny(filtered, 30, 200)

    contours, _ = cv2.findContours(edged.copy(), cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
    contours = sorted(contours, key=cv2.contourArea, reverse=True)[:15]

    candidates = []
    img_h, img_w = gray.shape[:2]

    for c in contours:
        x, y, w, h = cv2.boundingRect(c)
        if w == 0 or h == 0:
            continue
        aspect_ratio = w / float(h)
        area_ratio = (w * h) / float(img_w * img_h)
        # License plates are wide rectangles, roughly 2:1 to 6:1 aspect ratio,
        # and shouldn't be the whole image or a tiny speck.
        if 1.8 <= aspect_ratio <= 6.0 and 0.005 <= area_ratio <= 0.35:
            candidates.append((x, y, w, h, cv2.contourArea(c)))

    candidates.sort(key=lambda t: t[4], reverse=True)
    return [(x, y, w, h) for x, y, w, h, _ in candidates]


def _ocr_crop(crop: np.ndarray):
    """Run OCR on a cropped plate region. Returns (text, confidence 0-100)."""
    if crop.size == 0:
        return "", 0.0

    # Upscale small crops for better OCR accuracy
    h, w = crop.shape[:2]
    if w < 300:
        scale = 300.0 / max(w, 1)
        crop = cv2.resize(crop, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_CUBIC)

    gray_crop = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY) if len(crop.shape) == 3 else crop
    _, thresh = cv2.threshold(gray_crop, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    if _EASYOCR_AVAILABLE:
        reader = _get_easyocr_reader()
        results = reader.readtext(crop)
        if results:
            # pick the result with highest confidence
            results.sort(key=lambda r: r[2], reverse=True)
            text = "".join([r[1] for r in results])
            conf = float(results[0][2]) * 100.0
            return text, round(conf, 1)
        return "", 0.0

    if _TESSERACT_AVAILABLE:
        config = "--psm 7 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
        text = pytesseract.image_to_string(thresh, config=config)
        # crude confidence proxy: presence of alnum chars
        alnum = re.sub(r"[^A-Za-z0-9]", "", text)
        conf = min(95.0, 40.0 + len(alnum) * 5.0) if alnum else 0.0
        return text, round(conf, 1)

    # Last-resort heuristic: no OCR engine installed. Count contour "blobs" in the
    # thresholded crop as a rough character-count signal, but no text can be read.
    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    char_like = [c for c in contours if 10 < cv2.boundingRect(c)[3] < thresh.shape[0]]
    conf = min(50.0, len(char_like) * 5.0)
    return "", round(conf, 1)


def detect_and_recognize(image: np.ndarray):
    """
    Main entry point: takes a BGR OpenCV frame, returns:
      {
        "success": bool,
        "plate_text": str,
        "confidence": float (0-100),
        "bbox": (x, y, w, h) or None,
        "annotated_frame": np.ndarray  (frame with bounding box + text drawn)
      }
    """
    annotated = image.copy()
    candidates = locate_plate_candidates(image)

    best_text, best_conf, best_box = "", 0.0, None

    for (x, y, w, h) in candidates[:5]:
        crop = image[y:y + h, x:x + w]
        text, conf = _ocr_crop(crop)
        normalized = normalize_plate_text(text)
        if normalized and conf > best_conf:
            best_text, best_conf, best_box = normalized, conf, (x, y, w, h)

    # If no OCR-confirmed candidate, still show the top geometric candidate box (unlabeled)
    if best_box is None and candidates:
        best_box = candidates[0]

    if best_box:
        x, y, w, h = best_box
        color = (0, 255, 0) if best_text else (0, 165, 255)
        cv2.rectangle(annotated, (x, y), (x + w, y + h), color, 2)
        label = f"{best_text} ({best_conf:.0f}%)" if best_text else "Plate region (unread)"
        cv2.putText(annotated, label, (x, max(0, y - 10)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)

    return {
        "success": bool(best_text),
        "plate_text": best_text,
        "confidence": best_conf,
        "bbox": best_box,
        "annotated_frame": annotated,
    }


def process_image_file(path: str):
    """Load an image from disk and run detection. Returns the result dict + saves annotated copy."""
    image = cv2.imread(path)
    if image is None:
        return {"success": False, "plate_text": "", "confidence": 0.0, "bbox": None, "error": "Could not read image"}
    result = detect_and_recognize(image)
    return result


def process_video_file(path: str, sample_every_n_frames: int = 10, max_frames_to_scan: int = 60):
    """
    Scan a video file frame-by-frame (sampling every N frames for speed), run detection
    on each sampled frame, and return the result with the highest OCR confidence found.
    """
    cap = cv2.VideoCapture(path)
    if not cap.isOpened():
        return {"success": False, "plate_text": "", "confidence": 0.0, "bbox": None, "error": "Could not open video"}

    best_result = {"success": False, "plate_text": "", "confidence": 0.0, "bbox": None, "annotated_frame": None}
    frame_idx = 0
    scanned = 0

    while scanned < max_frames_to_scan:
        ret, frame = cap.read()
        if not ret:
            break
        if frame_idx % sample_every_n_frames == 0:
            result = detect_and_recognize(frame)
            scanned += 1
            if result["confidence"] > best_result["confidence"]:
                best_result = result
        frame_idx += 1

    cap.release()
    return best_result


def save_annotated_frame(annotated_frame: np.ndarray, upload_dir: str, filename: str) -> str:
    """Save an annotated frame to the uploads directory and return the relative path."""
    os.makedirs(upload_dir, exist_ok=True)
    full_path = os.path.join(upload_dir, filename)
    cv2.imwrite(full_path, annotated_frame)
    return f"uploads/{filename}"


def generate_mjpeg_stream(source):
    """
    Generator that yields MJPEG-encoded frames with live ANPR bounding boxes drawn,
    for use with Flask's video_feed streaming endpoint.
    `source` can be an int (webcam index), an RTSP URL string, or a video file path.
    """
    cap = cv2.VideoCapture(source)
    if not cap.isOpened():
        return
    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                # loop video files instead of ending the stream
                cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                continue
            result = detect_and_recognize(frame)
            annotated = result["annotated_frame"]
            ok, buffer = cv2.imencode(".jpg", annotated)
            if not ok:
                continue
            frame_bytes = buffer.tobytes()
            yield (b"--frame\r\n"
                   b"Content-Type: image/jpeg\r\n\r\n" + frame_bytes + b"\r\n")
    finally:
        cap.release()
