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
from services.coaching.voice_pipeline import VoicePipeline, autoplay_audio


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


def reset_workout_state():
    st.session_state.reps = 0
    st.session_state.current_set_reps = 0
    st.session_state.sets_completed = 0
    st.session_state.last_saved_sets_completed = 0
    st.session_state.last_notified_sets_completed = 0
    st.session_state.last_notified_workout_complete = False
    st.session_state.set_cycle_started_at = time.time()


def safe_state_value(key, default):
    return st.session_state.get(key, default)


def render_sidebar(workout_started):
    with st.sidebar:
        st.markdown("## 🏋🏻‍♀️ Apna AI Coach")

        username = safe_state_value("username", "")
        if username:
            st.caption(f"👤 Training as {username}")

        st.divider()

        st.markdown("### Workout Setup")

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

            if st.button(
                "START TRAINING →",
                key="start_session_button",
                use_container_width=True,
            ):
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
                            (
                                st.session_state.audio_to_play,
                                st.session_state.coach_feedback,
                            ) = result

                    except Exception as e:
                        print(f"Voice feedback error: {e}")

                st.rerun()

        else:
            exercise = safe_state_value("exercise_type", "Workout")
            sets = safe_state_value("target_sets", 0)
            reps = safe_state_value("reps_per_set", 0)

            st.info(
                f"**{exercise}**\n\n"
                f"{sets} Sets × {reps} Reps"
            )

            if st.button(
                "END TRAINING",
                key="end_session_button",
                use_container_width=True,
            ):
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
                            (
                                st.session_state.audio_to_play,
                                st.session_state.coach_feedback,
                            ) = result

                    except Exception as e:
                        print(f"Workout completion feedback error: {e}")

                st.session_state.workout_started = False
                st.rerun()

        if workout_started:
            render_progress()
            render_exercise_metrics()


def render_progress():
    total_reps = safe_state_value("reps", 0)
    current_set_reps = safe_state_value("current_set_reps", 0)
    reps_per_set = safe_state_value("reps_per_set", 0)
    sets_completed = safe_state_value("sets_completed", 0)
    target_sets = safe_state_value("target_sets", 0)

    st.divider()
    st.markdown("### Progress")

    st.metric("Total Reps", total_reps)

    st.metric(
        "Current Set",
        f"{current_set_reps} / {reps_per_set}",
    )

    st.metric(
        "Sets Completed",
        f"{sets_completed} / {target_sets}",
    )


def render_exercise_metrics():
    exercise = safe_state_value("exercise_type", "")

    st.divider()

    if exercise == "Squats":
        st.markdown("### Squat Metrics")

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
            safe_state_value("depth_status", "Waiting"),
        )

    elif exercise == "Push-ups":
        st.markdown("### Push-up Metrics")

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

    elif exercise == "Biceps Curls (Dumbbell)":
        st.markdown("### Curl Metrics")

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

    elif exercise == "Shoulder Press":
        st.markdown("### Shoulder Press Metrics")

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

    elif exercise == "Lunges":
        st.markdown("### Lunge Metrics")

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


def render_welcome_screen():
    st.markdown("# AI Real-time GYM Coach")
    st.markdown(
        "### Train smarter. Track every repetition. Improve your form."
    )

    st.info(
        "Configure your exercise, sets and repetitions from the sidebar "
        "to begin your training session."
    )

    st.divider()

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Your Training System")
        st.write("**Ready for real-time feedback**")
        st.caption(
            "Your AI coach will analyze movement, track repetitions "
            "and monitor your exercise form."
        )

    with col2:
        st.subheader("System Status")
        st.write("🟢 Pose Detection Ready")
        st.write("🧠 AI Coaching Ready")
        st.write("🔊 Voice Feedback Ready")


def render_workout_history():
    st.divider()
    st.markdown("### Performance Archive")
    st.markdown("## Workout History")

    user_id = safe_state_value("user_id", 0)

    if not isinstance(user_id, int):
        st.info("No workout history available.")
        return

    try:
        history_rows = get_users_exercises(user_id)
    except Exception as e:
        st.error(f"Could not load workout history: {e}")
        return

    if not history_rows:
        st.info("No workout history found yet.")
        return

    rows = [
        {
            "Exercise": row["exercise_name"],
            "Reps": row["reps"],
            "Sets": row["sets"],
            "Time (sec)": row["time"],
            "Date": row["created_at"],
        }
        for row in history_rows
    ]

    df = pd.DataFrame(rows)

    if df.empty:
        st.info("No workout history found yet.")
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
        hide_index=False,
    )


def render_live_workout():
    st.markdown("# AI Real-time GYM Coach")
    st.markdown(
        "### Live pose detection and AI-powered coaching"
    )

    if safe_state_value("audio_to_play", None):
        try:
            autoplay_audio(st.session_state.audio_to_play)
            st.session_state.audio_to_play = None
        except Exception as e:
            print(f"Audio playback error: {e}")

    feedback = safe_state_value("coach_feedback", "")
    if feedback:
        st.success(f"🤖 **Coach:** {feedback}")

    inject_webrtc_styles()

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
            "audio": False,
        },
        async_processing=True,
    )

    sync_metrics_update(context)

    if context.state.playing:
        time.sleep(0.15)
        st.rerun()


def main():
    st.set_page_config(
        page_icon="🏋🏻‍♀️",
        page_title="AI Real-time GYM Coach",
        initial_sidebar_state="expanded",
        layout="wide",
    )

    load_css(
        os.path.join(
            os.getcwd(),
            "static",
            "static.css",
        )
    )

    inject_local_font(
        os.path.join(
            os.getcwd(),
            "static",
            "AdobeClean.otf",
        ),
        "AdobeClean",
    )

    init_db()

    if not render_login_wall():
        return

    initial_session_defaults()
    initialize_voice_pipeline()

    workout_started = safe_state_value(
        "workout_started",
        False,
    )

    render_sidebar(workout_started)

    if workout_started:
        render_live_workout()
    else:
        render_welcome_screen()

    render_workout_history()


if __name__ == "__main__":
    main()
