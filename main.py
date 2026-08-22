import os
import time

import pandas as pd
import streamlit as st
from groq import Groq
from streamlit_webrtc import WebRtcMode, webrtc_streamer

from services.auth.login_wall import render_login_wall
from services.state.session_defaults import initial_session_defaults
from services.config.workout_config import EXERCISE_OPTIONS
from services.ui.style_loader import (
    load_css,
    inject_local_font,
    inject_webrtc_styles,
)
from services.persistence.exercise_repository import (
    init_db,
    get_users_exercises,
)
from services.vision.exercise_video_processor import VideoProcessorClass
from services.tracking.metrics import sync_metrics_update
from services.coaching.llm import LLMCoach
from services.coaching.tts import TextToSpeech
from services.coaching.voice_pipeline import (
    VoicePipeline,
    autoplay_audio,
)


# =========================================================
# HELPERS
# =========================================================

def safe_state_value(key, default=None):
    return st.session_state.get(key, default)


# =========================================================
# VOICE PIPELINE
# =========================================================

def initialize_voice_pipeline():
    if "voice_pipeline" in st.session_state:
        return

    try:
        api_key = os.environ.get("GROQ_API_KEY", "")

        if not api_key:
            try:
                api_key = st.secrets.get("GROQ_API_KEY", "")
            except Exception:
                pass

        if not api_key:
            print("GROQ_API_KEY not found.")
            st.session_state.voice_pipeline = None
            return

        groq_client = Groq(api_key=api_key)

        llm_coach = LLMCoach(groq_client)

        tts = TextToSpeech()

        st.session_state.voice_pipeline = VoicePipeline(
            llm_coach,
            tts,
        )

    except Exception as e:
        print(f"Voice pipeline initialization error: {e}")
        st.session_state.voice_pipeline = None


# =========================================================
# RESET WORKOUT
# =========================================================

def reset_workout_state():
    st.session_state.reps = 0
    st.session_state.current_set_reps = 0
    st.session_state.sets_completed = 0

    st.session_state.last_saved_sets_completed = 0
    st.session_state.last_notified_sets_completed = 0
    st.session_state.last_notified_workout_complete = False

    st.session_state.set_cycle_started_at = time.time()


# =========================================================
# START WORKOUT
# =========================================================

def start_workout(plan_exercise, plan_sets, plan_reps):

    st.session_state.exercise_type = plan_exercise
    st.session_state.target_sets = int(plan_sets)
    st.session_state.reps_per_set = int(plan_reps)

    reset_workout_state()

    st.session_state.workout_started = True

    voice_pipeline = safe_state_value(
        "voice_pipeline",
        None,
    )

    if voice_pipeline:

        try:
            result = voice_pipeline.process_event(
                event="workout_started",
                exercise=plan_exercise,
                metrics={},
            )

            if result:

                audio, feedback = result

                st.session_state.audio_to_play = audio
                st.session_state.coach_feedback = feedback

        except Exception as e:
            print(f"Workout start voice error: {e}")


# =========================================================
# END WORKOUT
# =========================================================

def end_workout():

    exercise = safe_state_value(
        "exercise_type",
        "Workout",
    )

    voice_pipeline = safe_state_value(
        "voice_pipeline",
        None,
    )

    if voice_pipeline:

        try:
            result = voice_pipeline.process_event(
                event="workout_completed",
                exercise=exercise,
                metrics={},
            )

            if result:

                audio, feedback = result

                st.session_state.audio_to_play = audio
                st.session_state.coach_feedback = feedback

        except Exception as e:
            print(f"Workout completion voice error: {e}")

    st.session_state.workout_started = False


# =========================================================
# SIDEBAR
# =========================================================

def render_sidebar():

    workout_started = safe_state_value(
        "workout_started",
        False,
    )

    with st.sidebar:

        st.title("🏋️‍♀️ Apna AI Coach")

        username = safe_state_value(
            "username",
            "",
        )

        if username:
            st.caption(
                f"👤 Training as {username}"
            )

        st.divider()

        st.subheader("Workout Setup")

        # -------------------------------------------------
        # BEFORE WORKOUT
        # -------------------------------------------------

        if not workout_started:

            plan_exercise = st.selectbox(
                "Exercise",
                options=EXERCISE_OPTIONS,
                key="plan_exercise",
            )

            col1, col2 = st.columns(2)

            with col1:

                plan_sets = st.number_input(
                    "Sets",
                    min_value=1,
                    max_value=50,
                    step=1,
                    key="plan_sets",
                )

            with col2:

                plan_reps = st.number_input(
                    "Reps",
                    min_value=1,
                    max_value=50,
                    step=1,
                    key="plan_reps",
                )

            st.markdown("")

            start_session_button = st.button(
                "START TRAINING →",
                key="start_session_button",
                use_container_width=True,
            )

            if start_session_button:

                start_workout(
                    plan_exercise,
                    plan_sets,
                    plan_reps,
                )

                st.rerun()

        # -------------------------------------------------
        # DURING WORKOUT
        # -------------------------------------------------

        else:

            exercise = safe_state_value(
                "exercise_type",
                "Workout",
            )

            sets = safe_state_value(
                "target_sets",
                0,
            )

            reps_per_set = safe_state_value(
                "reps_per_set",
                0,
            )

            st.info(
                f"**{exercise}**\n\n"
                f"{sets} Sets × {reps_per_set} Reps"
            )

            end_session_button = st.button(
                "END TRAINING",
                key="end_session_button",
                use_container_width=True,
            )

            if end_session_button:

                end_workout()

                st.rerun()

            render_progress()

            render_exercise_metrics()


# =========================================================
# PROGRESS
# =========================================================

def render_progress():

    st.divider()

    st.subheader("Progress")

    total_reps = safe_state_value(
        "reps",
        0,
    )

    current_set_reps = safe_state_value(
        "current_set_reps",
        0,
    )

    reps_per_set = safe_state_value(
        "reps_per_set",
        0,
    )

    sets_completed = safe_state_value(
        "sets_completed",
        0,
    )

    target_sets = safe_state_value(
        "target_sets",
        0,
    )

    st.metric(
        "Total Reps",
        total_reps,
    )

    st.metric(
        "Current Set Reps",
        f"{current_set_reps} / {reps_per_set}",
    )

    st.metric(
        "Sets Completed",
        f"{sets_completed} / {target_sets}",
    )


# =========================================================
# EXERCISE METRICS
# =========================================================

def render_exercise_metrics():

    exercise = safe_state_value(
        "exercise_type",
        "",
    )

    st.divider()

    # -----------------------------------------------------
    # SQUATS
    # -----------------------------------------------------

    if exercise == "Squats":

        st.subheader("Squat Metrics")

        st.metric(
            "Knee Angle",
            f"{safe_state_value('knee_angle', 0)}°",
        )

        st.metric(
            "Back Angle",
            f"{safe_state_value('back_angle', 0)}°",
        )

        st.metric(
            "Depth Status",
            safe_state_value(
                "depth_status",
                "Waiting",
            ),
        )

    # -----------------------------------------------------
    # PUSH UPS
    # -----------------------------------------------------

    elif exercise == "Push-ups":

        st.subheader("Push-up Metrics")

        st.metric(
            "Elbow Angle",
            f"{safe_state_value('elbow_angle', 0)}°",
        )

        st.metric(
            "Body Alignment",
            safe_state_value(
                "body_alignment",
                "Waiting",
            ),
        )

        st.metric(
            "Hip Position",
            safe_state_value(
                "hip_status",
                "Waiting",
            ),
        )

    # -----------------------------------------------------
    # BICEPS CURL
    # -----------------------------------------------------

    elif exercise == "Biceps Curls (Dumbbell)":

        st.subheader("Curl Metrics")

        st.metric(
            "Elbow Angle",
            f"{safe_state_value('elbow_angle', 0)}°",
        )

        st.metric(
            "Shoulder Stability",
            safe_state_value(
                "shoulder_status",
                "Waiting",
            ),
        )

        st.metric(
            "Swing Detection",
            safe_state_value(
                "swing_status",
                "Waiting",
            ),
        )

    # -----------------------------------------------------
    # SHOULDER PRESS
    # -----------------------------------------------------

    elif exercise == "Shoulder Press":

        st.subheader("Shoulder Press Metrics")

        st.metric(
            "Elbow Angle",
            f"{safe_state_value('elbow_angle', 0)}°",
        )

        st.metric(
            "Arm Extension",
            safe_state_value(
                "extension_status",
                "Waiting",
            ),
        )

        st.metric(
            "Back Arch",
            safe_state_value(
                "back_arch_status",
                "Waiting",
            ),
        )

    # -----------------------------------------------------
    # LUNGES
    # -----------------------------------------------------

    elif exercise == "Lunges":

        st.subheader("Lunge Metrics")

        st.metric(
            "Front Knee Angle",
            f"{safe_state_value('front_knee_angle', 0)}°",
        )

        st.metric(
            "Torso Angle",
            f"{safe_state_value('torso_angle', 0)}°",
        )

        st.metric(
            "Balance Status",
            safe_state_value(
                "balance_status",
                "Waiting",
            ),
        )


# =========================================================
# WELCOME SCREEN
# =========================================================

def render_welcome_screen():

    st.title("AI Real-time GYM Coach")

    st.markdown(
        "### Train smarter. Track every repetition. Improve your form."
    )

    st.info(
        "Configure your exercise, sets and repetitions "
        "from the sidebar to begin your training session."
    )

    st.divider()

    col1, col2 = st.columns(
        [1.2, 1],
        gap="large",
    )

    with col1:

        with st.container(border=True):

            st.markdown(
                "##### YOUR TRAINING SYSTEM"
            )

            st.subheader(
                "Ready for real-time feedback"
            )

            st.write(
                "Your AI coach analyzes your movement, "
                "tracks repetitions and monitors your "
                "exercise form while you train."
            )

    with col2:

        with st.container(border=True):

            st.markdown(
                "##### SYSTEM STATUS"
            )

            st.success(
                "🟢 Pose Detection Ready"
            )

            st.success(
                "🧠 AI Coaching Ready"
            )

            st.success(
                "🔊 Voice Feedback Ready"
            )


# =========================================================
# LIVE WORKOUT + WEBCAM
# =========================================================

def render_live_workout():

    st.title("AI Real-time GYM Coach")

    st.markdown(
        "### Live pose detection and AI-powered coaching"
    )

    exercise = safe_state_value(
        "exercise_type",
        "Workout",
    )

    st.info(
        f"🏋️ Currently training: **{exercise}**"
    )

    # -----------------------------------------------------
    # PLAY AI VOICE
    # -----------------------------------------------------

    audio = safe_state_value(
        "audio_to_play",
        None,
    )

    if audio:

        try:

            autoplay_audio(audio)

            # Prevent the same audio from repeatedly playing
            st.session_state.audio_to_play = None

        except Exception as e:

            print(
                f"Audio playback error: {e}"
            )

    # -----------------------------------------------------
    # SHOW AI FEEDBACK
    # -----------------------------------------------------

    feedback = safe_state_value(
        "coach_feedback",
        "",
    )

    if feedback:

        st.success(
            f"🤖 **Coach:** {feedback}"
        )

    # -----------------------------------------------------
    # WEBCAM STYLING
    # -----------------------------------------------------

    inject_webrtc_styles()

    st.subheader("📹 Live Camera")

    # -----------------------------------------------------
    # WEBCAM
    # -----------------------------------------------------

    context = webrtc_streamer(

        key="exercise-analysis",

        mode=WebRtcMode.SENDRECV,

        video_processor_factory=VideoProcessorClass,

        rtc_configuration={
            "iceServers": [
                {
                    "urls": [
                        "stun:stun.l.google.com:19302"
                    ]
                }
            ]
        },

        media_stream_constraints={
            "video": {
                "width": {
                    "ideal": 640
                },
                "height": {
                    "ideal": 480
                },
                "frameRate": {
                    "ideal": 24,
                    "max": 24
                }
            },
            "audio": False,
        },

        async_processing=True,
    )

    # -----------------------------------------------------
    # SYNC REP COUNT + METRICS
    # -----------------------------------------------------

    if context is not None:

        try:

            sync_metrics_update(context)

        except Exception as e:

            print(
                f"Metrics update error: {e}"
            )

    # IMPORTANT:
    # Do not add time.sleep() + st.rerun() here.
    # It can interrupt the WebRTC webcam connection.


# =========================================================
# WORKOUT HISTORY
# =========================================================

def render_workout_history():

    st.divider()

    st.markdown(
        "##### PERFORMANCE ARCHIVE"
    )

    st.subheader(
        "Workout History"
    )

    user_id = safe_state_value(
        "user_id",
        0,
    )

    if not isinstance(user_id, int):

        st.info(
            "No workout history available."
        )

        return

    try:

        history_rows = get_users_exercises(
            user_id
        )

    except Exception as e:

        st.error(
            f"Could not load workout history: {e}"
        )

        return

    if not history_rows:

        st.info(
            "No workout history found."
        )

        return

    rows = []

    for row in history_rows:

        rows.append(
            {
                "Exercise": row["exercise_name"],
                "Reps": row["reps"],
                "Sets": row["sets"],
                "Time (sec)": row["time"],
                "Date": row["created_at"],
            }
        )

    df = pd.DataFrame(rows)

    if df.empty:

        st.info(
            "No workout history found."
        )

        return

    df["Date"] = pd.to_datetime(
        df["Date"],
        errors="coerce",
    ).dt.date

    agg_df = (
        df.groupby(
            ["Exercise", "Date"],
            dropna=False,
        )
        .agg(
            {
                "Reps": "sum",
                "Sets": "sum",
                "Time (sec)": "sum",
            }
        )
        .reset_index()
    )

    agg_df.index += 1

    st.dataframe(
        agg_df,
        use_container_width=True,
    )


# =========================================================
# MAIN
# =========================================================

def main():

    st.set_page_config(
        page_icon="🏋️‍♀️",
        page_title="AI Real-time GYM Coach",
        initial_sidebar_state="expanded",
        layout="wide",
    )

    # -----------------------------------------------------
    # LOAD CSS
    # -----------------------------------------------------

    load_css(
        os.path.join(
            os.getcwd(),
            "static",
            "static.css",
        )
    )

    # -----------------------------------------------------
    # LOAD FONT
    # -----------------------------------------------------

    inject_local_font(
        os.path.join(
            os.getcwd(),
            "static",
            "AdobeClean.otf",
        ),
        "AdobeClean",
    )

    # -----------------------------------------------------
    # DATABASE
    # -----------------------------------------------------

    init_db()

    # -----------------------------------------------------
    # LOGIN
    # -----------------------------------------------------

    if not render_login_wall():

        return

    # -----------------------------------------------------
    # SESSION DEFAULTS
    # -----------------------------------------------------

    initial_session_defaults()

    # -----------------------------------------------------
    # VOICE PIPELINE
    # -----------------------------------------------------

    initialize_voice_pipeline()

    # -----------------------------------------------------
    # SIDEBAR
    # -----------------------------------------------------

    render_sidebar()

    # -----------------------------------------------------
    # MAIN SCREEN
    # -----------------------------------------------------

    if st.session_state.get(
        "workout_started",
        False,
    ):

        render_live_workout()

    else:

        render_welcome_screen()

    # -----------------------------------------------------
    # HISTORY
    # -----------------------------------------------------

    render_workout_history()


# =========================================================
# RUN APP
# =========================================================

if __name__ == "__main__":

    main()
