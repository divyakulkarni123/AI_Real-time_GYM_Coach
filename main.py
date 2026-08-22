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


# =========================================================
# UI STYLING
# =========================================================

def inject_dashboard_styles():
    st.markdown("""
    <style>

    /* Main background */
    .stApp {
        background:
            radial-gradient(
                circle at 15% 10%,
                rgba(184, 120, 76, 0.10),
                transparent 28%
            ),
            radial-gradient(
                circle at 85% 85%,
                rgba(120, 70, 90, 0.10),
                transparent 30%
            ),
            #0f1018;
    }

    /* Hide default Streamlit header */
    header[data-testid="stHeader"] {
        background: transparent;
    }

    /* Main content spacing */
    .block-container {
        padding-top: 2.2rem;
        padding-bottom: 3rem;
        max-width: 1450px;
    }

    /* Section titles */
    .dashboard-title {
        font-size: 2.5rem;
        font-weight: 700;
        letter-spacing: -1px;
        margin-bottom: 0;
        color: #f2e8df;
    }

    .dashboard-subtitle {
        color: #aaa1a1;
        font-size: 1rem;
        margin-top: 0.35rem;
        margin-bottom: 2rem;
    }

    /* Small label */
    .section-label {
        color: #c89568;
        font-size: 0.75rem;
        font-weight: 700;
        letter-spacing: 2px;
        text-transform: uppercase;
        margin-bottom: 0.6rem;
    }

    /* Dashboard cards */
    .dashboard-card {
        background: linear-gradient(
            145deg,
            rgba(32, 33, 45, 0.96),
            rgba(21, 22, 31, 0.96)
        );
        border: 1px solid rgba(222, 193, 163, 0.14);
        border-radius: 18px;
        padding: 20px;
        margin-bottom: 16px;
        box-shadow:
            0 10px 35px rgba(0, 0, 0, 0.22);
    }

    /* Workout plan card */
    .workout-card {
        background: linear-gradient(
            145deg,
            rgba(42, 36, 40, 0.96),
            rgba(25, 26, 36, 0.98)
        );
        border: 1px solid rgba(206, 150, 103, 0.22);
        border-radius: 18px;
        padding: 22px;
        margin-bottom: 18px;
    }

    /* Camera section */
    .camera-panel {
        background: rgba(20, 21, 30, 0.92);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 22px;
        padding: 18px;
        margin-bottom: 20px;
    }

    /* AI coach panel */
    .coach-panel {
        background: linear-gradient(
            135deg,
            rgba(78, 52, 70, 0.45),
            rgba(32, 30, 42, 0.75)
        );
        border: 1px solid rgba(210, 164, 129, 0.18);
        border-radius: 18px;
        padding: 18px 20px;
        margin-top: 18px;
    }

    .coach-title {
        color: #d9a878;
        font-size: 0.75rem;
        font-weight: 700;
        letter-spacing: 1.8px;
        margin-bottom: 8px;
    }

    /* Metric labels */
    [data-testid="stMetric"] {
        background: rgba(29, 30, 41, 0.78);
        border: 1px solid rgba(255, 255, 255, 0.07);
        border-radius: 15px;
        padding: 14px;
    }

    [data-testid="stMetricLabel"] {
        color: #aaa4a4;
    }

    [data-testid="stMetricValue"] {
        color: #f1d8bd;
    }

    /* Sidebar */
    [data-testid="stSidebar"] {
        background: linear-gradient(
            180deg,
            #161722,
            #10111a
        );
        border-right: 1px solid rgba(255,255,255,0.05);
    }

    /* Sidebar title */
    .sidebar-brand {
        font-size: 1.55rem;
        font-weight: 700;
        color: #f0e2d5;
        margin-bottom: 0.25rem;
    }

    .sidebar-user {
        color: #9d9696;
        font-size: 0.9rem;
        margin-bottom: 1rem;
    }

    /* Buttons */
    .stButton > button {
        border-radius: 10px;
        border: 1px solid rgba(225, 177, 131, 0.28);
        background: linear-gradient(
            135deg,
            #c99160,
            #a86557
        );
        color: white;
        font-weight: 600;
        min-height: 44px;
    }

    .stButton > button:hover {
        border-color: rgba(255, 220, 185, 0.65);
        transform: translateY(-1px);
    }

    /* Selectbox / inputs */
    [data-baseweb="select"] > div,
    [data-baseweb="input"] > div {
        background-color: rgba(35, 36, 47, 0.95);
        border-color: rgba(255,255,255,0.10);
    }

    /* History table */
    [data-testid="stTable"] {
        background: rgba(23, 24, 34, 0.7);
        border-radius: 14px;
        overflow: hidden;
    }

    </style>
    """, unsafe_allow_html=True)


# =========================================================
# MAIN APPLICATION
# =========================================================

def main():

    # -----------------------------------------------------
    # PAGE CONFIG
    # -----------------------------------------------------

    st.set_page_config(
        page_icon="🏋️‍♀️",
        page_title="AI Real-time GYM Coach",
        initial_sidebar_state="expanded",
        layout="wide"
    )

    # -----------------------------------------------------
    # EXISTING STYLING
    # -----------------------------------------------------

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

    inject_dashboard_styles()

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
    # SAME BACKEND LOGIC
    # -----------------------------------------------------

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

            st.session_state.voice_pipeline = (
                VoicePipeline(
                    llm_coach,
                    tts
                )
            )

        except Exception:

            st.session_state.voice_pipeline = None


    # -----------------------------------------------------
    # WORKOUT STATE
    # -----------------------------------------------------

    workout_started = st.session_state.get(
        "workout_started",
        False
    )


    # =====================================================
    # SIDEBAR
    # =====================================================

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


        # -------------------------------------------------
        # BEFORE WORKOUT
        # -------------------------------------------------

        if not workout_started:

            st.markdown(
                '<div class="section-label">Workout Setup</div>',
                unsafe_allow_html=True
            )

            plan_exercise = st.selectbox(
                "Exercise",
                options=EXERCISE_OPTIONS,
                key="plan_exercise"
            )

            col_set, col_rep = st.columns(2)

            with col_set:

                plan_sets = st.number_input(
                    "Sets",
                    min_value=0,
                    max_value=50,
                    key="plan_sets",
                    step=1
                )

            with col_rep:

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

                # SAME BACKEND LOGIC

                st.session_state.exercise_type = (
                    plan_exercise
                )

                st.session_state.target_sets = int(
                    plan_sets
                )

                st.session_state.reps_per_set = int(
                    plan_reps
                )

                st.session_state.reps = 0

                st.session_state.workout_started = True

                st.session_state.set_cycle_started_at = (
                    time.time()
                )

                st.session_state.last_saved_sets_completed = 0

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

                st.session_state.last_notified_sets_completed = 0

                st.session_state.last_notified_workout_complete = False

                st.rerun()


        # -------------------------------------------------
        # ACTIVE WORKOUT
        # -------------------------------------------------

        else:

            exercise = st.session_state.get(
                "exercise_type"
            )

            sets = st.session_state.get(
                "target_sets"
            )

            reps = st.session_state.get(
                "reps_per_set"
            )

            st.markdown(
                '<div class="section-label">Active Session</div>',
                unsafe_allow_html=True
            )

            st.markdown(
                f"""
                <div class="workout-card">
                    <div style="
                        font-size:0.75rem;
                        color:#c89568;
                        letter-spacing:1.5px;
                        font-weight:700;
                        margin-bottom:8px;
                    ">
                        CURRENT EXERCISE
                    </div>

                    <div style="
                        font-size:1.35rem;
                        font-weight:700;
                        color:#f1e5da;
                        margin-bottom:6px;
                    ">
                        {exercise}
                    </div>

                    <div style="
                        color:#aaa4a4;
                        font-size:0.9rem;
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

                # SAME BACKEND LOGIC

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


        # -------------------------------------------------
        # LIVE PROGRESS
        # -------------------------------------------------

        if workout_started:

            st.divider()

            st.markdown(
                '<div class="section-label">Live Progress</div>',
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

            st.metric(
                "Total Reps",
                f"{total_reps}"
            )

            st.metric(
                "Current Set",
                f"{current_set_reps} / {reps_per_set}"
            )

            st.metric(
                "Sets Completed",
                f"{sets_completed} / {target_sets}"
            )


        # -------------------------------------------------
        # EXERCISE METRICS
        # SAME BACKEND DATA
        # -------------------------------------------------

        if workout_started:

            st.divider()

            exercise = st.session_state.get(
                "exercise_type"
            )

            st.markdown(
                '<div class="section-label">Movement Analysis</div>',
                unsafe_allow_html=True
            )


            if exercise == "Squats":

                st.metric(
                    "Knee Angle",
                    f"{st.session_state.get('knee_angle', 0)}°"
                )

                st.metric(
                    "Back Angle",
                    f"{st.session_state.get('back_angle', 0)}°"
                )

                st.metric(
                    "Depth Status",
                    st.session_state.get(
                        "depth_status",
                        "Waiting..."
                    )
                )


            elif exercise == "Push-ups":

                st.metric(
                    "Elbow Angle",
                    f"{st.session_state.get('elbow_angle', 0)}°"
                )

                st.metric(
                    "Body Alignment",
                    st.session_state.get(
                        "body_alignment",
                        "Waiting..."
                    )
                )

                st.metric(
                    "Hip Position",
                    st.session_state.get(
                        "hip_status",
                        "Waiting..."
                    )
                )


            elif exercise == "Biceps Curls (Dumbbell)":

                st.metric(
                    "Elbow Angle",
                    f"{st.session_state.get('elbow_angle', 0)}°"
                )

                st.metric(
                    "Shoulder Stability",
                    st.session_state.get(
                        "shoulder_status",
                        "Waiting..."
                    )
                )

                st.metric(
                    "Swing Detection",
                    st.session_state.get(
                        "swing_status",
                        "Waiting..."
                    )
                )


            elif exercise == "Shoulder Press":

                st.metric(
                    "Elbow Angle",
                    f"{st.session_state.get('elbow_angle', 0)}°"
                )

                st.metric(
                    "Arm Extension",
                    st.session_state.get(
                        "extension_status",
                        "Waiting..."
                    )
                )

                st.metric(
                    "Back Arch",
                    st.session_state.get(
                        "back_arch_status",
                        "Waiting..."
                    )
                )


            elif exercise == "Lunges":

                st.metric(
                    "Front Knee Angle",
                    f"{st.session_state.get('front_knee_angle', 0)}°"
                )

                st.metric(
                    "Torso Angle",
                    f"{st.session_state.get('torso_angle', 0)}°"
                )

                st.metric(
                    "Balance Status",
                    st.session_state.get(
                        "balance_status",
                        "Waiting..."
                    )
                )


    # =====================================================
    # MAIN DASHBOARD
    # =====================================================


    # -----------------------------------------------------
    # HEADER
    # -----------------------------------------------------

    if workout_started:

        st.markdown(
            """
            <div class="section-label">
                Live Training Session
            </div>

            <div class="dashboard-title">
                Movement Command Center
            </div>

            <div class="dashboard-subtitle">
                Real-time pose tracking and intelligent coaching
            </div>
            """,
            unsafe_allow_html=True
        )

    else:

        st.markdown(
            """
            <div class="section-label">
                Ready When You Are
            </div>

            <div class="dashboard-title">
                Build Your Next Session
            </div>

            <div class="dashboard-subtitle">
                Configure your workout and let AI monitor every repetition.
            </div>
            """,
            unsafe_allow_html=True
        )


    # -----------------------------------------------------
    # AUDIO
    # -----------------------------------------------------

    if st.session_state.get("audio_to_play"):

        autoplay_audio(
            st.session_state.audio_to_play
        )


    # =====================================================
    # BEFORE WORKOUT
    # =====================================================

    if not workout_started:

        col1, col2 = st.columns(
            [1.2, 1]
        )

        with col1:

            st.markdown(
                """
                <div class="dashboard-card">

                    <div class="section-label">
                        Your Training System
                    </div>

                    <h2 style="
                        color:#f1e5da;
                        margin-top:8px;
                    ">
                        Ready for real-time feedback
                    </h2>

                    <p style="
                        color:#aaa4a4;
                        line-height:1.7;
                    ">
                        Your AI coach will analyze your body movement,
                        track repetitions and monitor exercise form while
                        you train.
                    </p>

                </div>
                """,
                unsafe_allow_html=True
            )

        with col2:

            st.markdown(
                """
                <div class="dashboard-card">

                    <div class="section-label">
                        System Status
                    </div>

                    <p style="color:#ddd;">
                        🟢 Pose Detection Ready
                    </p>

                    <p style="color:#ddd;">
                        🧠 AI Coaching Ready
                    </p>

                    <p style="color:#ddd;">
                        🔊 Voice Feedback Ready
                    </p>

                </div>
                """,
                unsafe_allow_html=True
            )


    # =====================================================
    # ACTIVE WORKOUT
    # =====================================================

    else:

        # -------------------------------------------------
        # CAMERA
        # -------------------------------------------------

        st.markdown(
            '<div class="section-label">Live Camera Feed</div>',
            unsafe_allow_html=True
        )

        st.markdown(
            '<div class="camera-panel">',
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
                        "stun:stun.l.google.com:19302"
                    }
                ]
            },

            media_stream_constraints={
                "video": True,
                "audio": False
            },

            async_processing=True
        )

        st.markdown(
            '</div>',
            unsafe_allow_html=True
        )


        # -------------------------------------------------
        # SAME METRIC SYNC BACKEND
        # -------------------------------------------------

        sync_metrics_update(
            context
        )


        # -------------------------------------------------
        # AI COACH FEEDBACK
        # -------------------------------------------------

        st.markdown(
            """
            <div class="coach-panel">

                <div class="coach-title">
                    🤖 AI COACH
                </div>

            """,
            unsafe_allow_html=True
        )

        if st.session_state.get("coach_feedback"):

            st.success(
                st.session_state.coach_feedback
            )

        else:

            st.markdown(
                """
                <div style="
                    color:#aaa4a4;
                    line-height:1.6;
                ">
                    Monitoring your movement. Your coach will provide
                    feedback when it detects an important event.
                </div>
                """,
                unsafe_allow_html=True
            )

        st.markdown(
            '</div>',
            unsafe_allow_html=True
        )


        # -------------------------------------------------
        # AUTO REFRESH
        # SAME LOGIC
        # -------------------------------------------------

        if context.state.playing:

            time.sleep(0.25)

            st.rerun()


        inject_webrtc_styles()


    # =====================================================
    # WORKOUT HISTORY
    # =====================================================

    st.markdown("<br>", unsafe_allow_html=True)

    st.markdown(
        '<div class="section-label">Performance Archive</div>',
        unsafe_allow_html=True
    )

    st.markdown(
        """
        <h2 style="
            color:#f1e5da;
            margin-top:5px;
            margin-bottom:20px;
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


        df = pd.DataFrame(
            arr
        )


        if not df.empty:

            df["Date"] = (
                pd.to_datetime(
                    df["Date"]
                )
                .dt.date
            )


            agg_df = (

                df.groupby(
                    ["Exercise", "Date"]
                )

                .agg({
                    "Reps": "sum",
                    "Sets": "sum",
                    "Time (sec)": "sum"
                })

                .reset_index()
            )


            agg_df.index += 1


            st.table(
                agg_df,
                border="horizontal"
            )


        else:

            st.info(
                "No workout history found yet. "
                "Your completed sessions will appear here."
            )


# =========================================================
# RUN APP
# =========================================================

if __name__ == "__main__":
    main()
