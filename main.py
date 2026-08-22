import streamlit as st
import os
import time
import pandas as pd

from services.auth.login_wall import render_login_wall
from services.state.session_defaults import initial_session_defaults
from services.config.workout_config import EXERCISE_OPTIONS
from services.ui.style_loader import load_css, inject_local_font, inject_webrtc_styles
from services.persistence.exercise_repository import init_db, get_users_exercises

from streamlit_webrtc import webrtc_streamer, WebRtcMode
from services.vision.exercise_video_processor import VideoProcessorClass
from services.tracking.metrics import sync_metrics_update

from groq import Groq
from services.coaching.llm import LLMCoach
from services.coaching.tts import TextToSpeech
from services.coaching.voice_pipeline import VoicePipeline, autoplay_audio


def render_metric_card(label, value):
    st.markdown(
        f"""
        <div class="metric-card">
            <div class="metric-label">{label}</div>
            <div class="metric-value">{value}</div>
        </div>
        """,
        unsafe_allow_html=True
    )


def main():

    st.set_page_config(
        page_icon="🏋️‍♀️",
        page_title="AI Real-time GYM Coach",
        initial_sidebar_state="expanded",
        layout="wide"
    )

    # --------------------------------------------------
    # LOAD EXISTING PROJECT CSS
    # --------------------------------------------------

    load_css(os.path.join(os.getcwd(), "static", "style.css"))

    inject_local_font(
        os.path.join(os.getcwd(), "static", "AdobeClean.otf"),
        "AdobeClean"
    )

    # --------------------------------------------------
    # ADDITIONAL UI STYLING
    # --------------------------------------------------

    st.markdown(
        """
        <style>

        /* MAIN APP */

        .stApp {
            background:
                radial-gradient(circle at top right,
                rgba(116, 76, 54, 0.12),
                transparent 35%),
                #10111b;
        }

        /* SIDEBAR */

        section[data-testid="stSidebar"] {
            background:
                linear-gradient(
                    180deg,
                    #181925 0%,
                    #12131d 100%
                );
            border-right: 1px solid #303141;
        }

        /* SECTION LABELS */

        .section-label {
            color: #cda47e;
            font-size: 0.72rem;
            font-weight: 700;
            letter-spacing: 0.22em;
            margin-bottom: 0.7rem;
        }

        /* HERO */

        .hero-title {
            font-size: 2.5rem;
            font-weight: 700;
            color: #f1dfc8;
            margin-bottom: 0.3rem;
        }

        .hero-subtitle {
            color: #aaa4a4;
            font-size: 1.05rem;
            margin-bottom: 1.8rem;
        }

        /* CARDS */

        .coach-card {
            background:
                linear-gradient(
                    145deg,
                    rgba(43, 42, 55, 0.95),
                    rgba(27, 28, 38, 0.95)
                );

            border: 1px solid #454050;

            border-radius: 22px;

            padding: 28px;

            margin-bottom: 20px;

            box-shadow:
                0 15px 40px rgba(0, 0, 0, 0.18);
        }

        .coach-title {
            color: #f1dfc8;
            font-size: 1.45rem;
            font-weight: 700;
            margin-bottom: 0.7rem;
        }

        .coach-text {
            color: #aaa4a4;
            font-size: 0.95rem;
            line-height: 1.7;
        }

        /* STATUS */

        .status-row {
            padding: 12px 0;
            border-bottom: 1px solid rgba(255,255,255,0.06);
            color: #ddd;
        }

        .status-row:last-child {
            border-bottom: none;
        }

        /* METRIC CARDS */

        .metric-card {
            background: #20212c;
            border: 1px solid #333546;
            border-radius: 12px;
            padding: 15px 16px;
            margin-bottom: 12px;
        }

        .metric-label {
            color: #9b9bab;
            font-size: 0.78rem;
            margin-bottom: 5px;
        }

        .metric-value {
            color: #f1dfc8;
            font-size: 1.25rem;
            font-weight: 700;
        }

        /* SIDEBAR HEADER */

        .sidebar-brand {
            font-size: 1.7rem;
            font-weight: 700;
            color: #f1dfc8;
            margin-bottom: 0.3rem;
        }

        .sidebar-user {
            color: #aaa4a4;
            font-size: 0.9rem;
            margin-bottom: 1rem;
        }

        /* WORKOUT CARD */

        .active-workout {
            background: #20212c;
            border: 1px solid #494250;
            border-radius: 16px;
            padding: 18px;
            margin-top: 12px;
        }

        .active-workout-title {
            color: #cda47e;
            font-size: 0.72rem;
            font-weight: 700;
            letter-spacing: 0.18em;
            margin-bottom: 10px;
        }

        .active-workout-name {
            color: #f1dfc8;
            font-size: 1.2rem;
            font-weight: 700;
        }

        .active-workout-plan {
            color: #aaa4a4;
            margin-top: 5px;
        }

        </style>
        """,
        unsafe_allow_html=True
    )

    # --------------------------------------------------
    # DATABASE
    # --------------------------------------------------

    init_db()

    # --------------------------------------------------
    # LOGIN
    # --------------------------------------------------

    if not render_login_wall():
        return

    # --------------------------------------------------
    # SESSION DEFAULTS
    # --------------------------------------------------

    initial_session_defaults()

    # --------------------------------------------------
    # VOICE PIPELINE
    # --------------------------------------------------

    if "voice_pipeline" not in st.session_state:

        try:

            api_key = os.environ.get("GROQ_API_KEY", "")

            if (
                not api_key
                and hasattr(st, "secrets")
                and "GROQ_API_KEY" in st.secrets
            ):
                api_key = st.secrets["GROQ_API_KEY"]

            groq_client = Groq(api_key=api_key)

            llm_coach = LLMCoach(groq_client)

            tts = TextToSpeech()

            st.session_state.voice_pipeline = VoicePipeline(
                llm_coach,
                tts
            )

        except Exception:

            st.session_state.voice_pipeline = None

    workout_started = st.session_state.get(
        "workout_started",
        False
    )

    # ==================================================
    # SIDEBAR
    # ==================================================

    with st.sidebar:

        st.markdown(
            """
            <div class="sidebar-brand">
                🏋️ Apna AI Coach
            </div>
            """,
            unsafe_allow_html=True
        )

        if st.session_state.username:

            st.markdown(
                f"""
                <div class="sidebar-user">
                    👤 Training as {st.session_state.username}
                </div>
                """,
                unsafe_allow_html=True
            )

        st.divider()

        # ----------------------------------------------
        # BEFORE WORKOUT
        # ----------------------------------------------

        if not workout_started:

            st.markdown(
                '<div class="section-label">WORKOUT SETUP</div>',
                unsafe_allow_html=True
            )

            plan_exercise = st.selectbox(
                "Exercise",
                options=EXERCISE_OPTIONS,
                key="plan_exercise"
            )

            col1, col2 = st.columns(2)

            with col1:

                plan_sets = st.number_input(
                    "Sets",
                    min_value=0,
                    max_value=50,
                    key="plan_sets",
                    step=1
                )

            with col2:

                plan_reps = st.number_input(
                    "Reps",
                    min_value=0,
                    max_value=50,
                    key="plan_reps",
                    step=1
                )

            st.markdown("")

            start_session_button = st.button(
                "START TRAINING →",
                width="stretch",
                key="start_session_button"
            )

            if start_session_button:

                st.session_state.exercise_type = plan_exercise

                st.session_state.target_sets = int(plan_sets)

                st.session_state.reps_per_set = int(plan_reps)

                st.session_state.reps = 0

                st.session_state.workout_started = True

                st.session_state.set_cycle_started_at = time.time()

                st.session_state.last_saved_sets_completed = 0

                st.session_state.last_notified_sets_completed = 0

                st.session_state.last_notified_workout_complete = False

                if st.session_state.voice_pipeline:

                    result = (
                        st.session_state.voice_pipeline.process_event(
                            event="workout_started",
                            exercise=plan_exercise,
                            metrics={}
                        )
                    )

                    if result:

                        (
                            st.session_state.audio_to_play,
                            st.session_state.coach_feedback
                        ) = result

                st.rerun()

        # ----------------------------------------------
        # ACTIVE WORKOUT
        # ----------------------------------------------

        else:

            exercise = st.session_state.get("exercise_type")

            sets = st.session_state.get("target_sets")

            reps = st.session_state.get("reps_per_set")

            st.markdown(
                '<div class="section-label">ACTIVE SESSION</div>',
                unsafe_allow_html=True
            )

            st.markdown(
                f"""
                <div class="active-workout">

                    <div class="active-workout-title">
                        CURRENT EXERCISE
                    </div>

                    <div class="active-workout-name">
                        {exercise}
                    </div>

                    <div class="active-workout-plan">
                        {sets} sets × {reps} reps
                    </div>

                </div>
                """,
                unsafe_allow_html=True
            )

            st.markdown("")

            end_session_button = st.button(
                "END WORKOUT",
                key="end_session_button",
                width="stretch"
            )

            if end_session_button:

                st.session_state.workout_started = False

                if st.session_state.voice_pipeline:

                    result = (
                        st.session_state.voice_pipeline.process_event(
                            event="workout_completed",
                            exercise=exercise,
                            metrics={}
                        )
                    )

                    if result:

                        (
                            st.session_state.audio_to_play,
                            st.session_state.coach_feedback
                        ) = result

                st.rerun()

        # ----------------------------------------------
        # PROGRESS
        # ----------------------------------------------

        if workout_started:

            st.divider()

            st.markdown(
                '<div class="section-label">LIVE PROGRESS</div>',
                unsafe_allow_html=True
            )

            total_reps = st.session_state.get("reps", 0)

            current_set_reps = st.session_state.get(
                "current_set_reps",
                0
            )

            reps_per_set = st.session_state.get(
                "reps_per_set",
                0
            )

            sets_completed = st.session_state.get(
                "sets_completed",
                0
            )

            target_sets = st.session_state.get(
                "target_sets",
                0
            )

            render_metric_card(
                "TOTAL REPS",
                total_reps
            )

            render_metric_card(
                "CURRENT SET",
                f"{current_set_reps} / {reps_per_set}"
            )

            render_metric_card(
                "SETS COMPLETED",
                f"{sets_completed} / {target_sets}"
            )

            # ------------------------------------------
            # EXERCISE METRICS
            # ------------------------------------------

            exercise = st.session_state.get("exercise_type")

            st.divider()

            st.markdown(
                '<div class="section-label">FORM METRICS</div>',
                unsafe_allow_html=True
            )

            if exercise == "Squats":

                render_metric_card(
                    "KNEE ANGLE",
                    f"{st.session_state.get('knee_angle', 0)}°"
                )

                render_metric_card(
                    "BACK ANGLE",
                    f"{st.session_state.get('back_angle', 0)}°"
                )

                render_metric_card(
                    "DEPTH STATUS",
                    st.session_state.get(
                        "depth_status",
                        "Waiting"
                    )
                )

            elif exercise == "Push-ups":

                render_metric_card(
                    "ELBOW ANGLE",
                    f"{st.session_state.get('elbow_angle', 0)}°"
                )

                render_metric_card(
                    "BODY ALIGNMENT",
                    st.session_state.get(
                        "body_alignment",
                        "Waiting"
                    )
                )

                render_metric_card(
                    "HIP POSITION",
                    st.session_state.get(
                        "hip_status",
                        "Waiting"
                    )
                )

            elif exercise == "Biceps Curls (Dumbbell)":

                render_metric_card(
                    "ELBOW ANGLE",
                    f"{st.session_state.get('elbow_angle', 0)}°"
                )

                render_metric_card(
                    "SHOULDER STABILITY",
                    st.session_state.get(
                        "shoulder_status",
                        "Waiting"
                    )
                )

                render_metric_card(
                    "SWING DETECTION",
                    st.session_state.get(
                        "swing_status",
                        "Waiting"
                    )
                )

            elif exercise == "Shoulder Press":

                render_metric_card(
                    "ELBOW ANGLE",
                    f"{st.session_state.get('elbow_angle', 0)}°"
                )

                render_metric_card(
                    "ARM EXTENSION",
                    st.session_state.get(
                        "extension_status",
                        "Waiting"
                    )
                )

                render_metric_card(
                    "BACK ARCH",
                    st.session_state.get(
                        "back_arch_status",
                        "Waiting"
                    )
                )

            elif exercise == "Lunges":

                render_metric_card(
                    "FRONT KNEE ANGLE",
                    f"{st.session_state.get('front_knee_angle', 0)}°"
                )

                render_metric_card(
                    "TORSO ANGLE",
                    f"{st.session_state.get('torso_angle', 0)}°"
                )

                render_metric_card(
                    "BALANCE STATUS",
                    st.session_state.get(
                        "balance_status",
                        "Waiting"
                    )
                )

    # ==================================================
    # MAIN PAGE
    # ==================================================

    st.markdown(
        """
        <div class="hero-title">
            AI Real-time GYM Coach
        </div>

        <div class="hero-subtitle">
            Train smarter. Track every repetition. Improve your form.
        </div>
        """,
        unsafe_allow_html=True
    )

    # ==================================================
    # AUDIO
    # ==================================================

    if st.session_state.get("audio_to_play"):

        autoplay_audio(
            st.session_state.audio_to_play
        )

    if st.session_state.get("coach_feedback"):

        st.success(
            f"🤖 Coach: {st.session_state.coach_feedback}"
        )

    # ==================================================
    # PRE-WORKOUT SCREEN
    # ==================================================

    if not workout_started:

        col1, col2 = st.columns([1.2, 1])

        with col1:

            st.markdown(
                """
                <div class="coach-card">

                    <div class="section-label">
                        YOUR TRAINING SYSTEM
                    </div>

                    <div class="coach-title">
                        Ready for real-time feedback
                    </div>

                    <div class="coach-text">
                        Select an exercise, configure your sets and repetitions,
                        then start your training session. Your AI coach will
                        monitor movement, track repetitions and provide
                        feedback during your workout.
                    </div>

                </div>
                """,
                unsafe_allow_html=True
            )

        with col2:

            st.markdown(
                """
                <div class="coach-card">

                    <div class="section-label">
                        SYSTEM STATUS
                    </div>

                    <div class="status-row">
                        🟢 Pose Detection Ready
                    </div>

                    <div class="status-row">
                        🧠 AI Coaching Ready
                    </div>

                    <div class="status-row">
                        🔊 Voice Feedback Ready
                    </div>

                </div>
                """,
                unsafe_allow_html=True
            )

    # ==================================================
    # ACTIVE WORKOUT
    # ==================================================

    else:

        st.markdown(
            '<div class="section-label">LIVE CAMERA ANALYSIS</div>',
            unsafe_allow_html=True
        )

        context = webrtc_streamer(

            key="exercise-analysis",

            mode=WebRtcMode.SENDRECV,

            video_processor_factory=VideoProcessorClass,

            rtc_configuration={
                "iceServers": [
                    {
                        "urls":
                        ["stun:stun.l.google.com:19302"]
                    }
                ]
            },

            media_stream_constraints={
                "video": True,
                "audio": False
            },

            async_processing=True
        )

        # IMPORTANT:
        # This keeps your existing backend metrics logic.

        sync_metrics_update(context)

        inject_webrtc_styles()

    # ==================================================
    # WORKOUT HISTORY
    # ==================================================

    st.markdown("<br>", unsafe_allow_html=True)

    st.markdown(
        '<div class="section-label">PERFORMANCE ARCHIVE</div>',
        unsafe_allow_html=True
    )

    st.subheader("Workout History")

    user_id = st.session_state.get("user_id", 0)

    if isinstance(user_id, int):

        history_rows = get_users_exercises(user_id)

        arr = [
            {
                "Exercise": row["exercise_name"],
                "Reps": row["reps"],
                "Sets": row["sets"],
                "Time (sec)": row["time"],
                "Date": row["created_at"]
            }
            for row in history_rows
        ]

        df = pd.DataFrame(arr)

        if not df.empty:

            df["Date"] = pd.to_datetime(
                df["Date"]
            ).dt.date

            agg_df = (
                df.groupby(
                    ["Exercise", "Date"]
                )
                .agg(
                    {
                        "Reps": "sum",
                        "Sets": "sum",
                        "Time (sec)": "sum"
                    }
                )
                .reset_index()
            )

            agg_df.index += 1

            st.dataframe(
                agg_df,
                width="stretch",
                hide_index=False
            )

        else:

            st.info("No workout history found yet.")


if __name__ == "__main__":
    main()
