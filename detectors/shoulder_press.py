from core.base_exercise import BaseExercise


class ShoulderPressDetector(BaseExercise):

    # More forgiving thresholds
    UP_THRESHOLD = 150
    DOWN_THRESHOLD = 110
    MIN_VISIBILITY = 0.5

    LEFT_SHOULDER = 11
    LEFT_ELBOW = 13
    LEFT_WRIST = 15

    RIGHT_SHOULDER = 12
    RIGHT_ELBOW = 14
    RIGHT_WRIST = 16

    LEFT_HIP = 23
    RIGHT_HIP = 24

    LEFT_KNEE = 25
    RIGHT_KNEE = 26


    def __init__(self):
        super().__init__()


    def reset(self):
        self.reps = 0
        self.stage = None


    def process(self, landmarks):

        # Select the more visible arm
        left_visibility = (
            landmarks[self.LEFT_SHOULDER].visibility
            + landmarks[self.LEFT_ELBOW].visibility
            + landmarks[self.LEFT_WRIST].visibility
        )

        right_visibility = (
            landmarks[self.RIGHT_SHOULDER].visibility
            + landmarks[self.RIGHT_ELBOW].visibility
            + landmarks[self.RIGHT_WRIST].visibility
        )


        if left_visibility >= right_visibility:

            shoulder_idx = self.LEFT_SHOULDER
            elbow_idx = self.LEFT_ELBOW
            wrist_idx = self.LEFT_WRIST
            hip_idx = self.LEFT_HIP
            knee_idx = self.LEFT_KNEE

        else:

            shoulder_idx = self.RIGHT_SHOULDER
            elbow_idx = self.RIGHT_ELBOW
            wrist_idx = self.RIGHT_WRIST
            hip_idx = self.RIGHT_HIP
            knee_idx = self.RIGHT_KNEE


        # Calculate elbow angle
        elbow_angle = self.calculate_angle(
            self.get_point(landmarks, shoulder_idx),
            self.get_point(landmarks, elbow_idx),
            self.get_point(landmarks, wrist_idx)
        )


        # Check visibility
        visible = (
            landmarks[shoulder_idx].visibility > self.MIN_VISIBILITY
            and landmarks[elbow_idx].visibility > self.MIN_VISIBILITY
            and landmarks[wrist_idx].visibility > self.MIN_VISIBILITY
        )


        if visible:

            # START / BOTTOM POSITION
            if elbow_angle <= self.DOWN_THRESHOLD:

                self.stage = "down"


            # PRESS UP → COUNT REP
            elif (
                elbow_angle >= self.UP_THRESHOLD
                and self.stage == "down"
            ):

                self.stage = "up"
                self.reps += 1


        # Extension status
        if elbow_angle >= self.UP_THRESHOLD:
            extension_status = "FULL EXTENSION"

        elif elbow_angle >= 130:
            extension_status = "NEARLY EXTENDED"

        elif elbow_angle >= self.DOWN_THRESHOLD:
            extension_status = "PRESSING"

        else:
            extension_status = "START POSITION"


        # Back angle
        back_angle = self.calculate_angle(
            self.get_point(landmarks, shoulder_idx),
            self.get_point(landmarks, hip_idx),
            self.get_point(landmarks, knee_idx)
        )


        if back_angle >= 160:
            back_arch_status = "Neutral"

        elif back_angle >= 140:
            back_arch_status = "Slight Arch"

        else:
            back_arch_status = "Excessive Arch"


        return {
            "reps": self.reps,
            "elbow_angle": int(elbow_angle),
            "extension_status": extension_status,
            "back_arch_status": back_arch_status,
        }
