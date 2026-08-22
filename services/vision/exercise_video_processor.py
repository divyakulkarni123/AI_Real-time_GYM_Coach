import os
import time
import cv2
import av
import numpy as np
import mediapipe as mp
import threading

from streamlit_webrtc import VideoProcessorBase
from mediapipe.tasks import python
from mediapipe.tasks.python import vision

from detectors.squat import SquatDetector
from detectors.pushup import PushUpDetector
from detectors.biceps_curl import BicepsCurlDetector
from detectors.shoulder_press import ShoulderPressDetector
from detectors.lunges import LungesDetector

from services.config.workout_config import POSE_CONNECTIONS


class VideoProcessorClass(VideoProcessorBase):

    def __init__(self):
        self._lock = threading.Lock()

        self._latest_metrics = None
        self._exercise_type = "Squats"

        # Timestamp tracking for MediaPipe VIDEO mode
        self._start_time = time.time()
        self._last_timestamp_ms = 0

        # --------------------------------------------------
        # LOAD MEDIAPIPE MODEL
        # --------------------------------------------------
        model_path = os.path.join(
            os.getcwd(),
            "ml_models",
            "pose_landmarker_full.task"
        )

        if not os.path.exists(model_path):
            raise FileNotFoundError(
                f"Pose model not found: {model_path}"
            )

        base_options = python.BaseOptions(
            model_asset_path=model_path
        )

        options = vision.PoseLandmarkerOptions(
            base_options=base_options,
            running_mode=vision.RunningMode.VIDEO,
            min_pose_detection_confidence=0.7,
            min_pose_presence_confidence=0.7,
            min_tracking_confidence=0.7,
            output_segmentation_masks=False
        )

        self._landmarker = vision.PoseLandmarker.create_from_options(
            options
        )

        # --------------------------------------------------
        # EXERCISE DETECTORS
        # --------------------------------------------------
        self._detectors = {
            "Squats": SquatDetector(),
            "Push-ups": PushUpDetector(),
            "Biceps Curls (Dumbbell)": BicepsCurlDetector(),
            "Shoulder Press": ShoulderPressDetector(),
            "Lunges": LungesDetector(),
        }

    # ======================================================
    # METRICS
    # ======================================================

    def set_latest_metrics(self, metrics):
        if metrics is None:
            return

        with self._lock:
            self._latest_metrics = metrics.copy()

    def get_latest_metrics(self):
        with self._lock:
            if self._latest_metrics is None:
                return None

            return self._latest_metrics.copy()

    # ======================================================
    # EXERCISE SELECTION
    # ======================================================

    def set_exercise(self, exercise_type):
        with self._lock:
            if exercise_type in self._detectors:
                self._exercise_type = exercise_type

    def get_exercise(self):
        with self._lock:
            return self._exercise_type

    # ======================================================
    # DRAW SKELETON
    # ======================================================

    def _draw_skeleton(self, img, landmarks):
        height, width = img.shape[:2]

        for start_idx, end_idx in POSE_CONNECTIONS:

            if (
                start_idx >= len(landmarks)
                or end_idx >= len(landmarks)
            ):
                continue

            p1 = landmarks[start_idx]
            p2 = landmarks[end_idx]

            visibility_1 = getattr(p1, "visibility", 1.0)
            visibility_2 = getattr(p2, "visibility", 1.0)

            if visibility_1 > 0.5 and visibility_2 > 0.5:

                x1 = int(p1.x * width)
                y1 = int(p1.y * height)

                x2 = int(p2.x * width)
                y2 = int(p2.y * height)

                cv2.line(
                    img,
                    (x1, y1),
                    (x2, y2),
                    (0, 255, 0),
                    5
                )

        for landmark in landmarks:

            visibility = getattr(
                landmark,
                "visibility",
                1.0
            )

            if visibility > 0.5:

                x = int(landmark.x * width)
                y = int(landmark.y * height)

                cv2.circle(
                    img,
                    (x, y),
                    6,
                    (255, 0, 0),
                    -1
                )

    # ======================================================
    # NO POSE WARNING
    # ======================================================

    def _draw_no_pose_warnings(self, img):

        cv2.putText(
            img,
            "NO POSE DETECTED",
            (30, 50),
            cv2.FONT_HERSHEY_SIMPLEX,
            1,
            (0, 0, 255),
            2,
            cv2.LINE_AA
        )

        cv2.putText(
            img,
            "PLEASE FACE THE CAMERA",
            (30, 100),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            (0, 0, 255),
            2,
            cv2.LINE_AA
        )

    # ======================================================
    # EXERCISE OVERLAYS
    # ======================================================

    def _draw_overlays(self, img, metrics, exercise_type):

        if exercise_type == "Squats":
            self._draw_squats_overlays(img, metrics)

        elif exercise_type == "Push-ups":
            self._draw_pushup_overlays(img, metrics)

        elif exercise_type == "Biceps Curls (Dumbbell)":
            self._draw_curl_overlays(img, metrics)

        elif exercise_type == "Shoulder Press":
            self._draw_press_overlays(img, metrics)

        elif exercise_type == "Lunges":
            self._draw_lunge_overlays(img, metrics)

    def _draw_squats_overlays(self, img, metrics):

        height, _ = img.shape[:2]

        status = metrics.get(
            "depth_status",
            "N/A"
        )

        cv2.putText(
            img,
            f"DEPTH: {status}",
            (20, height - 20),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            (0, 255, 0),
            2
        )

    def _draw_pushup_overlays(self, img, metrics):

        height, _ = img.shape[:2]

        body = metrics.get(
            "body_alignment",
            "N/A"
        )

        hip = metrics.get(
            "hip_status",
            "N/A"
        )

        cv2.putText(
            img,
            f"BODY: {body} | HIP: {hip}",
            (20, height - 20),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (0, 255, 0),
            2
        )

    def _draw_curl_overlays(self, img, metrics):

        height, _ = img.shape[:2]

        swing = metrics.get(
            "swing_status",
            "N/A"
        )

        cv2.putText(
            img,
            f"SWING: {swing}",
            (20, height - 20),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            (0, 255, 0),
            2
        )

    def _draw_press_overlays(self, img, metrics):

        height, _ = img.shape[:2]

        extension = metrics.get(
            "extension_status",
            "N/A"
        )

        back = metrics.get(
            "back_arch_status",
            "N/A"
        )

        cv2.putText(
            img,
            f"EXT: {extension} | BACK: {back}",
            (20, height - 20),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (0, 255, 0),
            2
        )

    def _draw_lunge_overlays(self, img, metrics):

        height, _ = img.shape[:2]

        balance = metrics.get(
            "balance_status",
            "N/A"
        )

        cv2.putText(
            img,
            f"BALANCE: {balance}",
            (20, height - 20),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            (0, 255, 0),
            2
        )

    # ======================================================
    # RECEIVE WEBCAM FRAME
    # ======================================================

    def recv(self, frame):

        # Convert WebRTC frame to BGR image
        image = frame.to_ndarray(format="bgr24")

        # Mirror webcam
        image = cv2.flip(image, 1)

        # --------------------------------------------------
        # CORRECT COLOR CONVERSION
        # MediaPipe expects SRGB/RGB
        # --------------------------------------------------
        rgb_image = cv2.cvtColor(
            image,
            cv2.COLOR_BGR2RGB
        )

        mp_image = mp.Image(
            image_format=mp.ImageFormat.SRGB,
            data=rgb_image
        )

        # --------------------------------------------------
        # VIDEO TIMESTAMP
        # Must continuously increase
        # --------------------------------------------------
        timestamp_ms = int(
            (time.time() - self._start_time) * 1000
        )

        if timestamp_ms <= self._last_timestamp_ms:
            timestamp_ms = self._last_timestamp_ms + 1

        self._last_timestamp_ms = timestamp_ms

        # --------------------------------------------------
        # POSE DETECTION
        # --------------------------------------------------
        result = self._landmarker.detect_for_video(
            mp_image,
            timestamp_ms
        )

        # --------------------------------------------------
        # POSE FOUND
        # --------------------------------------------------
        if result.pose_landmarks:

            landmarks = result.pose_landmarks[0]

            # Draw skeleton
            self._draw_skeleton(
                image,
                landmarks
            )

            # Get CURRENT exercise
            exercise_type = self.get_exercise()

            # Get correct detector
            detector = self._detectors.get(
                exercise_type
            )

            if detector is not None:

                try:
                    metrics = detector.process(
                        landmarks
                    )

                    if metrics is None:
                        metrics = {}

                    # Important
                    metrics["pose_detected"] = True
                    metrics["exercise_type"] = exercise_type

                    # Draw exercise information
                    self._draw_overlays(
                        image,
                        metrics,
                        exercise_type
                    )

                    # Send metrics to Streamlit
                    self.set_latest_metrics(
                        metrics
                    )

                except Exception as error:

                    print(
                        f"Detector error for "
                        f"{exercise_type}: {error}"
                    )

                    self.set_latest_metrics({
                        "pose_detected": True,
                        "exercise_type": exercise_type,
                        "detector_error": str(error)
                    })

        # --------------------------------------------------
        # NO POSE
        # --------------------------------------------------
        else:

            self._draw_no_pose_warnings(
                image
            )

            with self._lock:

                if self._latest_metrics is None:

                    self._latest_metrics = {
                        "pose_detected": False
                    }

                else:

                    self._latest_metrics[
                        "pose_detected"
                    ] = False

        return av.VideoFrame.from_ndarray(
            image,
            format="bgr24"
        )
