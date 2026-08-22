import streamlit as st
import os
import time
import pandas as pd

from services.auth.login_wall import render_login_wall
from services.state.session_defaults import initial_session_defaults
from services.config.workout_config import EXERCISE_OPTIONS
from services.ui.style_loader import load_css, inject_local_font, inject_webrtc_styles
from services.persistence.exercise_repository import init_db, get_users_exercises
from services.tracking.metrics import sync_metrics_update

from streamlit_webrtc import webrtc_streamer, WebRtcMode
from services.vision.exercise_video_processor import VideoProcessorClass

from groq import Groq
from services.coaching.llm import LLMCoach
from services.coaching.tts import TextToSpeech
from services.coaching.voice_pipeline import VoicePipeline, autoplay_audio


def inject_main_styles():
    st.markdown(
        """
        <style>

        /* ===============================
           MAIN BACKGROUND
        ================================= */

        .stApp {
            background:
                radial-gradient(
                    circle at 15% 20%,
                    rgba(190, 130, 90, 0.10),
                    transparent 28%
                ),
                radial-gradient(
                    circle at 85% 10%,
                    rgba(160, 90, 120, 0.08),
                    transparent 25%
                ),
                linear-gradient(
                    135deg,
                    #0b0b12 0%,
                    #101019 45%,
                    #17131b 100%
                );
            color: #e9e4df;
        }


        /* ===============================
           SIDEBAR
        ================================= */

        section[data-testid="stSidebar"] {
            background:
                linear-gradient(
                    180deg,
                    #11111a 0%,
                    #15131d 100%
                );
            border-right: 1px solid rgba(210, 170, 130, 0.12);
        }

        section[data-testid="stSidebar"] * {
            color: #e8e1dc;
        }


        /* ===============================
           HEADINGS
        ================================= */

        h1 {
            font-weight: 500 !important;
            letter-spacing: -1px !important;
        }

        h2, h3 {
            color: #eaded2 !important;
        }


        /* ===============================
           HERO SECTION
        ================================= */

        .gym-hero {
            padding: 26px 30px;
            margin-bottom: 28px;

            border-radius: 24px;

            background:
                linear-gradient(
                    135deg,
                    rgba(40, 36, 46, 0.92),
                    rgba(25, 24, 34, 0.92)
                );

            border: 1px solid rgba(220, 170, 130, 0.18);

            box-shadow:
                0 15px 45px rgba(0, 0, 0, 0.25);
        }

        .gym-title {
            font-size: 2.2rem;
            font-weight: 500;

            background:
                linear-gradient(
                    90deg,
                    #f0d5a9,
                    #d59a82
                );

            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;

            margin-bottom: 8px;
        }

        .gym-subtitle {
            color: #b8b0ad;
            font-size: 1rem;
            letter-spacing: 0.5px;
        }


        /* ===============================
           METRIC CARDS
        ================================= */

        div[data-testid="stMetric"] {
            background:
                linear-gradient(
                    145deg,
                    rgba(35, 35, 47, 0.95),
                    rgba(25, 24, 34, 0.95)
                );

            border:
                1px solid rgba(220, 170, 130, 0.12);

            padding: 18px;

            border-radius: 16px;

            box-shadow:
                0 8px 25px rgba(0, 0, 0, 0.18);
        }

        div[data-testid="stMetricLabel"] {
            color: #aaa2a0 !important;
        }

        div[data-testid="stMetricValue"] {
            color: #f0d4a7 !important;
            font-weight: 500 !important;
        }


        /* ===============================
           INFO BOX
        ================================= */

        div[data-testid="stAlert"] {
            border-radius: 14px;
        }


        /* ===============================
           BUTTONS
        ================================= */

        .stButton > button {
            border-radius: 12px;

            border:
                1px solid rgba(230, 180, 135, 0.30);

            background:
                linear-gradient(
                    135deg,
                    #d6a268,
                    #c98779
                );

            color: #17131a;

            font-weight: 600;

            transition: all 0.2s ease;
        }

        .stButton > button:hover {
            transform: translateY(-1px);

            border:
                1px solid rgba(255, 220, 180, 0.55);

            box-shadow:
                0 8px 20px rgba(200, 130, 90, 0.20);
        }


        /* ===============================
           INPUTS
        ================================= */

        input,
        textarea {
            background: #1c1c27 !important;
            color: #f1e8df !important;
            border-radius: 10px !important;
        }


        /* ===============================
           SELECT BOX
        ================================= */

        div[data-baseweb="select"] > div {
            background: #1c1c27 !important;
            border-color:
                rgba(220, 170, 130, 0.20) !important;
            color: #f1e8df !important;
        }


        /* ===============================
           CAMERA AREA
        ================================= */

        .camera-section {
            margin-top: 20px;
            padding: 18px;

            border-radius: 20px;

            background:
                linear-gradient(
                    145deg,
                    rgba(25, 25, 35, 0.90),
                    rgba(16, 16, 24, 0.90)
                );

            border:
                1px solid rgba(220, 170, 130, 0.12);
        }


        /* ===============================
           TABLE
        ================================= */

        .stTable {
            border-radius: 14px;
            overflow: hidden;
        }


        /* ===============================
           DIVIDER
        ================================= */

        hr {
            border-color:
                rgba(220, 170, 130, 0.12) !important;
        }


        /* ===============================
           FOOTER
        ================================= */

        .footer-text {
            text-align: center;
            color: #77717a;
            font-size: 0.8rem;
            letter-spacing: 2px;
            margin-top: 30px;
        }

        </style>
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

    # Load existing CSS
    load_css(os.path.join(os.getcwd(), "static", "style.css"))
    inject_local_font(
        os.path.join(os.getcwd(), "static", "AdobeClean.otf"),
        "AdobeClean"
    )

    # Premium complementary styling
    inject_main_styles()

    init_db()

    # ===============================
    # LOGIN
    # ===============================

    if not render_login_wall():
        return

    initial_session_defaults()


    # ===============================
    # AI COACH INITIALIZATION
    # ===============================

    if "voice_pipeline" not in st.session_state:

        try:

            api_key = os.environ.get("GROQ_API_KEY", "")

            if (
                not api_key
                and hasattr(st, "secrets")
                and "GROQ_API_KEY" in st.secrets
            ):
                api_key = st.secrets["GROQ_API_KEY"]

            if api_key:

                groq_client = Groq(api_key=api_key)

                llm_coach = LLMCoach(groq_client)

                tts = TextToSpeech()

                st.session_state.voice_pipeline = VoicePipeline(
                    llm_coach,
                    tts
                )

            else:
                st.session_state.voice_pipeline = None

        except Exception:
            st.session_state.voice_pipeline = None


    workout_started = st.session_state.get(
        "workout_started",
        False
    )


    # ===============================
    # SIDEBAR
    # ===============================

    with st.sidebar:

        st.markdown("## 🏋️ Apna AI Coach")

        if st.session_state.get("username"):
            st.caption(
                f"👤 Logged in as **{st.session_state.username}**"
            )

        st.divider()

        st.subheader("Workout Plan")


        # ===============================
        # BEFORE WORKOUT
        # ===============================

        if not workout_started:

            plan_exercise = st.selectbox(
                "Exercise",
                options=EXERCISE_OPTIONS,
                key="plan_exercise"
            )

            plan_sets = st.number_input(
                "Sets",
                min_value=1,
                max_value=50,
                value=3,
                step=1,
                key="plan_sets"
            )

            plan_reps = st.number_input(
                "Reps per Set",
                min_value=1,
                max_value=50,
                value=10,
                step=1,
                key="plan_reps"
            )

            st.markdown("<br>", unsafe_allow_html=True)

            if st.button(
                "START WORKOUT →",
                width="stretch",
                key="start_session_button"
            ):

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

                if st.session_state.get("voice_pipeline"):

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


        # ===============================
        # ACTIVE WORKOUT
        # ===============================

        else:

            exercise = st.session_state.get("exercise_type")

            sets = st.session_state.get("target_sets")

            reps_per_set = st.session_state.get("reps_per_set")

            st.markdown(
                f"""
                <div style="
                    padding:16px;
                    border-radius:14px;
                    background:rgba(210,160,110,0.08);
                    border:1px solid rgba(210,160,110,0.15);
                ">
                    <div style="
                        color:#f0d4a7;
                        font-size:1.05rem;
                        font-weight:600;
                    ">
                        {exercise}
                    </div>

                    <div style="
                        color:#aaa2a0;
                        margin-top:5px;
                    ">
                        {sets} Sets · {reps_per_set} Reps
                    </div>
                </div>
                """,
                unsafe_allow_html=True
            )

            st.markdown("<br>", unsafe_allow_html=True)

            if st.button(
                "END WORKOUT",
                key="end_session_button",
                width="stretch"
            ):

                st.session_state.workout_started = False

                if st.session_state.get("voice_pipeline"):

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


        # ===============================
        # LIVE PROGRESS
        # ===============================

        if workout_started:

            st.divider()

            st.subheader("Live Progress")

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

            st.metric(
                "Total Reps",
                total_reps
            )

            st.metric(
                "Current Set",
                f"{current_set_reps} / {reps_per_set}"
            )

            st.metric(
                "Sets Completed",
                f"{sets_completed} / {target_sets}"
            )


            # ===============================
            # EXERCISE METRICS
            # ===============================

            st.divider()

            exercise = st.session_state.get("exercise_type")


            if exercise == "Squats":

                st.subheader("Squat Metrics")

                st.metric(
                    "Knee Angle",
                    f"{st.session_state.get('knee_angle', 0)}°"
                )

                st.metric(
                    "Back Angle",
                    f"{st.session_state.get('back_angle', 0)}°"
                )

                st.metric(
                    "Depth",
                    st.session_state.get(
                        "depth_status",
                        "Waiting..."
                    )
                )


            elif exercise == "Push-ups":

                st.subheader("Push-up Metrics")

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

                st.subheader("Curl Metrics")

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

                st.subheader("Shoulder Press Metrics")

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

                st.subheader("Lunge Metrics")

                st.metric(
                    "Front Knee Angle",
                    f"{st.session_state.get('front_knee_angle', 0)}°"
                )

                st.metric(
                    "Torso Angle",
                    f"{st.session_state.get('torso_angle', 0)}°"
                )

                st.metric(
                    "Balance",
                    st.session_state.get(
                        "balance_status",
                        "Waiting..."
                    )
                )


    # ===============================
    # MAIN PAGE
    # ===============================

    st.markdown(
        """
        <div class="gym-hero">

            <div class="gym-title">
                AI Real-time GYM Coach
            </div>

            <div class="gym-subtitle">
                Train smarter. Move better. Get real-time AI-powered guidance.
            </div>

        </div>
        """,
        unsafe_allow_html=True
    )


    # ===============================
    # AUDIO
    # ===============================

    if st.session_state.get("audio_to_play"):
        autoplay_audio(
            st.session_state.audio_to_play
        )


    if st.session_state.get("coach_feedback"):

        st.success(
            f"🤖 **AI Coach:** "
            f"{st.session_state.coach_feedback}"
        )


    # ===============================
    # BEFORE WORKOUT SCREEN
    # ===============================

    if not workout_started:

        col1, col2, col3 = st.columns(3)

        with col1:
            st.markdown(
                """
                <div class="gym-hero">
                    <h3>🎯 Real-time Tracking</h3>
                    <p>
                        Live pose detection tracks
                        your movement and repetitions.
                    </p>
                </div>
                """,
                unsafe_allow_html=True
            )

        with col2:
            st.markdown(
                """
                <div class="gym-hero">
                    <h3>🧠 Smart Form Analysis</h3>
                    <p>
                        Detect movement patterns
                        and identify form issues.
                    </p>
                </div>
                """,
                unsafe_allow_html=True
            )

        with col3:
            st.markdown(
                """
                <div class="gym-hero">
                    <h3>🔊 AI Coaching</h3>
                    <p>
                        Receive proactive
                        real-time workout guidance.
                    </p>
                </div>
                """,
                unsafe_allow_html=True
            )


        st.markdown(
            """
            <div class="footer-text">
                POWERED BY COMPUTER VISION · AI COACHING · REAL-TIME ANALYTICS
            </div>
            """,
            unsafe_allow_html=True
        )


    # ===============================
    # ACTIVE WORKOUT CAMERA
    # ===============================

    else:

        st.markdown(
            '<div class="camera-section">',
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

        st.markdown(
            '</div>',
            unsafe_allow_html=True
        )


        # IMPORTANT:
        # Sync live metrics AFTER camera initialization
        sync_metrics_update(context)


        # Controlled refresh
        if context and context.state.playing:

            time.sleep(0.20)

            st.rerun()


        inject_webrtc_styles()


    # ===============================
    # WORKOUT HISTORY
    # ===============================

    st.markdown("<br>", unsafe_allow_html=True)

    st.divider()

    st.markdown("### Workout History")

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

            df["Date"] = (
                pd.to_datetime(df["Date"]).dt.date
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

            st.info(
                "No workout history yet. "
                "Your completed workouts will appear here."
            )


if __name__ == "__main__":
    main()
