from core.base_exercise import BaseExercise


class ShoulderPressDetector(BaseExercise):
    UP_THRESHOLD = 150
    DOWN_THRESHOLD = 105
    MIN_VISIBILITY = 0.5

    LEFT_SHOULDER = 11
    LEFT_ELBOW = 13
    LEFT_WRIST = 15

    RIGHT_SHOULDER = 12
    RIGHT_ELBOW = 14
    RIGHT_WRIST = 16

    LEFT_HIP = 23
    LEFT_KNEE = 25

    RIGHT_HIP = 24
    RIGHT_KNEE = 26

    def __init__(self):
        super().__init__()
        self.reset()

    def reset(self):
        self.reps = 0
        self.stage = "down"

    def process(self, landmarks):

        left_visibility = (
            landmarks[self.LEFT_SHOULDER].visibility +
            landmarks[self.LEFT_ELBOW].visibility +
            landmarks[self.LEFT_WRIST].visibility
        ) / 3

        right_visibility = (
            landmarks[self.RIGHT_SHOULDER].visibility +
            landmarks[self.RIGHT_ELBOW].visibility +
            landmarks[self.RIGHT_WRIST].visibility
        ) / 3

        if left_visibility >= right_visibility:
            shoulder_idx = self.LEFT_SHOULDER
            elbow_idx = self.LEFT_ELBOW
            wrist_idx = self.LEFT_WRIST
            hip_idx = self.LEFT_HIP
            knee_idx = self.LEFT_KNEE
            visibility = left_visibility
        else:
            shoulder_idx = self.RIGHT_SHOULDER
            elbow_idx = self.RIGHT_ELBOW
            wrist_idx = self.RIGHT_WRIST
            hip_idx = self.RIGHT_HIP
            knee_idx = self.RIGHT_KNEE
            visibility = right_visibility

        if visibility < self.MIN_VISIBILITY:
            return {
                "reps": self.reps,
                "elbow_angle": 0,
                "extension_status": "LANDMARKS NOT CLEAR",
                "back_arch_status": "N/A"
            }

        shoulder = self.get_point(landmarks, shoulder_idx)
        elbow = self.get_point(landmarks, elbow_idx)
        wrist = self.get_point(landmarks, wrist_idx)

        elbow_angle = self.calculate_angle(
            shoulder,
            elbow,
            wrist
        )

        # ---------- REP COUNTING ----------
        # Bottom position
        if elbow_angle <= self.DOWN_THRESHOLD:
            self.stage = "down"

        # Full press / top position
        elif elbow_angle >= self.UP_THRESHOLD:

            if self.stage == "down":
                self.reps += 1
                self.stage = "up"

        # ---------- EXTENSION STATUS ----------
        if elbow_angle >= self.UP_THRESHOLD:
            extension_status = "FULL EXTENSION"

        elif elbow_angle >= 130:
            extension_status = "PRESSING"

        elif elbow_angle >= self.DOWN_THRESHOLD:
            extension_status = "HALF PRESS"

        else:
            extension_status = "START POSITION"

        # ---------- BACK POSTURE ----------
        shoulder_point = self.get_point(landmarks, shoulder_idx)
        hip_point = self.get_point(landmarks, hip_idx)
        knee_point = self.get_point(landmarks, knee_idx)

        back_angle = self.calculate_angle(
            shoulder_point,
            hip_point,
            knee_point
        )

        if back_angle >= 165:
            back_arch_status = "Neutral"

        elif back_angle >= 145:
            back_arch_status = "Slight Arch"

        else:
            back_arch_status = "Excessive Arch"

        return {
            "reps": self.reps,
            "elbow_angle": int(elbow_angle),
            "extension_status": extension_status,
            "back_arch_status": back_arch_status
        }
