import streamlit as st
import os
import time
import pandas as pd

from services.auth.login_wall import render_login_wall
from services.state.session_defaults import initial_session_defaults
from services.config.workout_config import EXERCISE_OPTIONS
from services.ui.style_loader import (
    load_css,
    inject_local_font,
    inject_webrtc_styles
)
from services.persistence.exercise_repository import (
    init_db,
    get_users_exercises
)
from streamlit_webrtc import webrtc_streamer, WebRtcMode
from services.vision.exercise_video_processor import VideoProcessorClass
from services.tracking.metrics import sync_metrics_update

from groq import Groq
from services.coaching.llm import LLMCoach
from services.coaching.tts import TextToSpeech
from services.coaching.voice_pipeline import (
    VoicePipeline,
    autoplay_audio
)


def metric_card(label, value):
    st.markdown(
        f"""
        <div style="
            background: linear-gradient(145deg, #1d1f2a, #181923);
            border: 1px solid #353341;
            border-radius: 14px;
            padding: 16px 18px;
            margin-bottom: 10px;
        ">
            <div style="
                color: #9b9aaa;
                font-size: 0.78rem;
                text-transform: uppercase;
                letter-spacing: 1.5px;
                margin-bottom: 8px;
            ">
                {label}
            </div>

            <div style="
                color: #f0d7bb;
                font-size: 1.35rem;
                font-weight: 700;
            ">
                {value}
            </div>
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
    # LOAD EXISTING BACKEND STYLING
    # --------------------------------------------------

    load_css(
        os.path.join(
            os.getcwd(),
            "static",
            "style.css"
        )
    )

    inject_local_font(
        os.path.join(
            os.getcwd(),
            "static",
            "AdobeClean.otf"
        ),
        "AdobeClean"
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
            api_key = os.environ.get(
                "GROQ_API_KEY",
                ""
            )

            if (
                not api_key
                and hasattr(st, "secrets")
                and "GROQ_API_KEY" in st.secrets
            ):
                api_key = st.secrets["GROQ_API_KEY"]

            groq_client = Groq(
                api_key=api_key
            )

            llm_coach = LLMCoach(
                groq_client
            )

            tts = TextToSpeech()

            st.session_state.voice_pipeline = VoicePipeline(
                llm_coach,
                tts
            )

        except Exception:
            st.session_state.voice_pipeline = None

    # --------------------------------------------------
    # WORKOUT STATE
    # --------------------------------------------------

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
            <div style="padding: 10px 0 16px 0;">
                <div style="
                    font-size: 1.7rem;
                    font-weight: 700;
                    color: #f1d5b5;
                    margin-bottom: 6px;
                ">
                    🏋️ Apna AI Coach
                </div>

                <div style="
                    color: #a8a5b2;
                    font-size: 0.9rem;
                ">
                    Training as your personal AI coach
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )

        st.divider()

        # ==============================================
        # BEFORE WORKOUT
        # ==============================================

        if not workout_started:

            st.markdown(
                """
                <div style="
                    color: #cfa77f;
                    font-size: 0.75rem;
                    font-weight: 700;
                    letter-spacing: 3px;
                    margin-bottom: 10px;
                ">
                    WORKOUT SETUP
                </div>
                """,
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
                    min_value=1,
                    max_value=50,
                    key="plan_sets",
                    step=1
                )

            with col2:
                plan_reps = st.number_input(
                    "Reps",
                    min_value=1,
                    max_value=50,
                    key="plan_reps",
                    step=1
                )

            st.markdown("<br>", unsafe_allow_html=True)

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
                st.session_state.current_set_reps = 0
                st.session_state.sets_completed = 0

                st.session_state.workout_started = True

                st.session_state.set_cycle_started_at = time.time()

                st.session_state.last_saved_sets_completed = 0
                st.session_state.last_notified_sets_completed = 0
                st.session_state.last_notified_workout_complete = False

                if st.session_state.voice_pipeline:

                    result = (
                        st.session_state
                        .voice_pipeline
                        .process_event(
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

        # ==============================================
        # ACTIVE WORKOUT
        # ==============================================

        else:

            exercise = st.session_state.get(
                "exercise_type",
                ""
            )

            sets = st.session_state.get(
                "target_sets",
                0
            )

            reps = st.session_state.get(
                "reps_per_set",
                0
            )

            st.markdown(
                """
                <div style="
                    color: #cfa77f;
                    font-size: 0.75rem;
                    font-weight: 700;
                    letter-spacing: 3px;
                    margin-bottom: 12px;
                ">
                    ACTIVE SESSION
                </div>
                """,
                unsafe_allow_html=True
            )

            # IMPORTANT:
            # Valid HTML in ONE clean string.
            # No broken quote nesting.

            st.markdown(
                f"""
                <div style="
                    background: linear-gradient(145deg, #2a252b, #1d1e28);
                    border: 1px solid #4a3c3c;
                    border-radius: 18px;
                    padding: 20px;
                    margin-bottom: 16px;
                ">
                    <div style="
                        color: #cfa77f;
                        font-size: 0.75rem;
                        font-weight: 700;
                        letter-spacing: 2px;
                        margin-bottom: 12px;
                    ">
                        CURRENT EXERCISE
                    </div>

                    <div style="
                        color: #f1e2d2;
                        font-size: 1.3rem;
                        font-weight: 700;
                        margin-bottom: 8px;
                    ">
                        {exercise}
                    </div>

                    <div style="
                        color: #aaa4a4;
                        font-size: 0.9rem;
                    ">
                        {sets} sets × {reps} reps
                    </div>
                </div>
                """,
                unsafe_allow_html=True
            )

            end_session_button = st.button(
                "END WORKOUT",
                key="end_session_button",
                width="stretch"
            )

            if end_session_button:

                st.session_state.workout_started = False

                if st.session_state.voice_pipeline:

                    result = (
                        st.session_state
                        .voice_pipeline
                        .process_event(
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

        # ==============================================
        # LIVE METRICS
        # ==============================================

        if workout_started:

            st.divider()

            st.markdown(
                """
                <div style="
                    color: #cfa77f;
                    font-size: 0.75rem;
                    font-weight: 700;
                    letter-spacing: 3px;
                    margin-bottom: 12px;
                ">
                    LIVE PERFORMANCE
                </div>
                """,
                unsafe_allow_html=True
            )

            total_reps = st.session_state.get(
                "reps",
                0
            )

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

            metric_card(
                "Total Reps",
                total_reps
            )

            metric_card(
                "Current Set",
                f"{current_set_reps} / {reps_per_set}"
            )

            metric_card(
                "Sets Completed",
                f"{sets_completed} / {target_sets}"
            )

            st.divider()

            # ==========================================
            # EXERCISE-SPECIFIC METRICS
            # ==========================================

            if exercise == "Squats":

                st.markdown("### Squat Metrics")

                metric_card(
                    "Knee Angle",
                    f"{st.session_state.get('knee_angle', 0)}°"
                )

                metric_card(
                    "Back Angle",
                    f"{st.session_state.get('back_angle', 0)}°"
                )

                metric_card(
                    "Depth Status",
                    st.session_state.get(
                        "depth_status",
                        "Waiting..."
                    )
                )

            elif exercise == "Push-ups":

                st.markdown("### Push-up Metrics")

                metric_card(
                    "Elbow Angle",
                    f"{st.session_state.get('elbow_angle', 0)}°"
                )

                metric_card(
                    "Body Alignment",
                    st.session_state.get(
                        "body_alignment",
                        "Waiting..."
                    )
                )

                metric_card(
                    "Hip Position",
                    st.session_state.get(
                        "hip_status",
                        "Waiting..."
                    )
                )

            elif exercise == "Biceps Curls (Dumbbell)":

                st.markdown("### Curl Metrics")

                metric_card(
                    "Elbow Angle",
                    f"{st.session_state.get('elbow_angle', 0)}°"
                )

                metric_card(
                    "Shoulder Stability",
                    st.session_state.get(
                        "shoulder_status",
                        "Waiting..."
                    )
                )

                metric_card(
                    "Swing Detection",
                    st.session_state.get(
                        "swing_status",
                        "Waiting..."
                    )
                )

            elif exercise == "Shoulder Press":

                st.markdown("### Shoulder Press Metrics")

                metric_card(
                    "Elbow Angle",
                    f"{st.session_state.get('elbow_angle', 0)}°"
                )

                metric_card(
                    "Arm Extension",
                    st.session_state.get(
                        "extension_status",
                        "Waiting..."
                    )
                )

                metric_card(
                    "Back Arch",
                    st.session_state.get(
                        "back_arch_status",
                        "Waiting..."
                    )
                )

            elif exercise == "Lunges":

                st.markdown("### Lunge Metrics")

                metric_card(
                    "Front Knee Angle",
                    f"{st.session_state.get('front_knee_angle', 0)}°"
                )

                metric_card(
                    "Torso Angle",
                    f"{st.session_state.get('torso_angle', 0)}°"
                )

                metric_card(
                    "Balance Status",
                    st.session_state.get(
                        "balance_status",
                        "Waiting..."
                    )
                )

    # ==================================================
    # MAIN PAGE
    # ==================================================

    st.markdown(
        """
        <div style="
            padding-top: 20px;
            padding-bottom: 25px;
        ">
            <div style="
                color: #cfa77f;
                font-size: 0.75rem;
                font-weight: 700;
                letter-spacing: 4px;
                margin-bottom: 14px;
            ">
                AI-POWERED FITNESS SYSTEM
            </div>

            <h1 style="
                color: #f1e2d2;
                font-size: 3rem;
                margin-bottom: 8px;
            ">
                Train smarter.
            </h1>

            <p style="
                color: #aaa4a4;
                font-size: 1.1rem;
            ">
                Configure your workout and let AI monitor every repetition.
            </p>
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

    # ==================================================
    # COACH FEEDBACK
    # ==================================================

    if st.session_state.get("coach_feedback"):

        st.markdown(
            f"""
            <div style="
                background: linear-gradient(145deg, #25232d, #1d1e27);
                border-left: 4px solid #cfa77f;
                border-radius: 10px;
                padding: 18px;
                margin-bottom: 20px;
                color: #e7dfd8;
            ">
                <div style="
                    color: #cfa77f;
                    font-size: 0.8rem;
                    font-weight: 700;
                    letter-spacing: 2px;
                    margin-bottom: 8px;
                ">
                    🤖 AI COACH
                </div>

                {st.session_state.coach_feedback}
            </div>
            """,
            unsafe_allow_html=True
        )

    # ==================================================
    # BEFORE WORKOUT
    # ==================================================

    if not workout_started:

        col1, col2 = st.columns([1.4, 1])

        with col1:

            st.markdown(
                """
                <div style="
                    background: linear-gradient(145deg, #211f29, #181923);
                    border: 1px solid #393542;
                    border-radius: 20px;
                    padding: 35px;
                    min-height: 260px;
                ">
                    <div style="
                        color: #cfa77f;
                        font-size: 0.75rem;
                        font-weight: 700;
                        letter-spacing: 3px;
                        margin-bottom: 18px;
                    ">
                        YOUR TRAINING SYSTEM
                    </div>

                    <h2 style="
                        color: #f1e2d2;
                        margin-top: 0;
                    ">
                        Ready for real-time feedback
                    </h2>

                    <p style="
                        color: #aaa4a4;
                        line-height: 1.8;
                    ">
                        Select an exercise, configure your sets and repetitions,
                        then start your session. Your AI coach will monitor your
                        movement, track repetitions and provide feedback while you train.
                    </p>
                </div>
                """,
                unsafe_allow_html=True
            )

        with col2:

            st.markdown(
                """
                <div style="
                    background: linear-gradient(145deg, #211f29, #181923);
                    border: 1px solid #393542;
                    border-radius: 20px;
                    padding: 30px;
                    min-height: 260px;
                ">
                    <div style="
                        color: #cfa77f;
                        font-size: 0.75rem;
                        font-weight: 700;
                        letter-spacing: 3px;
                        margin-bottom: 18px;
                    ">
                        SYSTEM STATUS
                    </div>

                    <p style="color: #d7d4d9;">
                        🟢 Pose Detection Ready
                    </p>

                    <p style="color: #d7d4d9;">
                        🧠 AI Coaching Ready
                    </p>

                    <p style="color: #d7d4d9;">
                        🔊 Voice Feedback Ready
                    </p>
                </div>
                """,
                unsafe_allow_html=True
            )

    # ==================================================
    # ACTIVE WORKOUT CAMERA
    # ==================================================

    else:

        st.markdown(
            """
            <div style="
                color: #cfa77f;
                font-size: 0.75rem;
                font-weight: 700;
                letter-spacing: 3px;
                margin-bottom: 12px;
            ">
                LIVE MOTION ANALYSIS
            </div>
            """,
            unsafe_allow_html=True
        )

        context = webrtc_streamer(
            key="exercise-analysis",
            mode=WebRtcMode.SENDRECV,
            video_processor_factory=VideoProcessorClass,
            rtc_configuration={
                "iceServers": [
                    {
                        "urls": "stun:stun.l.google.com:19302"
                    }
                ]
            },
            media_stream_constraints={
                "video": True,
                "audio": False
            },
            async_processing=True
        )

        # Keep your existing metric synchronization backend
        sync_metrics_update(context)

        # IMPORTANT:
        # Do not change this unless you intentionally redesign
        # your real-time refresh mechanism.
        if context and context.state.playing:
            time.sleep(0.25)
            st.rerun()

        inject_webrtc_styles()

    # ==================================================
    # WORKOUT HISTORY
    # ==================================================

    st.markdown("<br>", unsafe_allow_html=True)

    st.divider()

    st.markdown(
        """
        <div style="
            color: #cfa77f;
            font-size: 0.75rem;
            font-weight: 700;
            letter-spacing: 4px;
            margin-top: 20px;
            margin-bottom: 8px;
        ">
            PERFORMANCE ARCHIVE
        </div>
        """,
        unsafe_allow_html=True
    )

    st.markdown(
        """
        <h2 style="
            color: #f1e2d2;
            margin-top: 0;
        ">
            Workout History
        </h2>
        """,
        unsafe_allow_html=True
    )

    user_id = st.session_state.get(
        "user_id",
        0
    )

    if isinstance(user_id, int):

        history_rows = get_users_exercises(
            user_id
        )

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

            df["Date"] = (
                pd.to_datetime(
                    df["Date"]
                ).dt.date
            )

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

            st.markdown(
                """
                <div style="
                    background: #1b1c25;
                    border: 1px dashed #44414d;
                    border-radius: 14px;
                    padding: 30px;
                    text-align: center;
                    color: #9d9aa5;
                ">
                    No workout history yet. Complete a session to start building your archive.
                </div>
                """,
                unsafe_allow_html=True
            )


if __name__ == "__main__":
    main()
