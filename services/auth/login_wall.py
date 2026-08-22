import streamlit as st
from services.persistence.exercise_repository import get_or_create_user


def render_login_wall():
    if st.session_state.get("username"):
        return True

    # ================================
    # PAGE STYLING
    # ================================

    st.markdown("""
<style>

[data-testid="stSidebar"] {
    display: none;
}

[data-testid="stHeader"] {
    background: transparent;
}

.block-container {
    max-width: 1150px;
    padding-top: 2rem;
    padding-bottom: 3rem;
}


/* ================================
   BACKGROUND
================================ */

[data-testid="stAppViewContainer"] {
    background:
        radial-gradient(
            circle at 15% 20%,
            rgba(218, 139, 91, 0.13),
            transparent 30%
        ),
        radial-gradient(
            circle at 85% 15%,
            rgba(190, 95, 120, 0.12),
            transparent 32%
        ),
        radial-gradient(
            circle at 50% 100%,
            rgba(112, 76, 145, 0.10),
            transparent 42%
        ),
        linear-gradient(
            135deg,
            #0b0b10 0%,
            #111018 50%,
            #17111a 100%
        );
}


/* ================================
   HERO
================================ */

.login-hero {
    text-align: center;
    margin-top: 1rem;
    margin-bottom: 2.7rem;
}

.hero-icon {
    width: 76px;
    height: 76px;

    margin: 0 auto 1.2rem auto;

    display: flex;
    align-items: center;
    justify-content: center;

    font-size: 2.5rem;

    border-radius: 24px;

    background:
        linear-gradient(
            145deg,
            rgba(218, 163, 112, 0.24),
            rgba(133, 78, 108, 0.18)
        );

    border:
        1px solid rgba(232, 184, 130, 0.28);

    box-shadow:
        0 12px 45px rgba(0, 0, 0, 0.38),
        inset 0 1px 0 rgba(255, 255, 255, 0.08);
}

.hero-title {
    font-size: clamp(3rem, 6vw, 5.3rem);

    font-weight: 800;

    letter-spacing: -0.055em;

    line-height: 1.05;

    margin-bottom: 0.9rem;

    background:
        linear-gradient(
            90deg,
            #f3eee8 0%,
            #ddb77d 48%,
            #c77975 100%
        );

    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;

    background-clip: text;
}

.hero-tagline {
    color: #aaa3ad;

    font-size: 0.92rem;

    letter-spacing: 0.2em;

    text-transform: uppercase;

    font-weight: 600;
}


/* ================================
   LOGIN CARD
================================ */

.login-card {
    max-width: 760px;

    margin: 0 auto 1.2rem auto;

    padding: 2.1rem 2.2rem;

    border-radius: 26px;

    background:
        linear-gradient(
            145deg,
            rgba(31, 28, 37, 0.94),
            rgba(19, 18, 24, 0.97)
        );

    border:
        1px solid rgba(228, 202, 170, 0.17);

    box-shadow:
        0 25px 80px rgba(0, 0, 0, 0.42),
        inset 0 1px 0 rgba(255, 255, 255, 0.04);
}

.login-heading {
    text-align: center;

    font-size: 1.9rem;

    font-weight: 700;

    color: #f1ece6;

    margin-bottom: 0.55rem;
}

.login-subtext {
    text-align: center;

    color: #a39ba6;

    font-size: 0.95rem;

    line-height: 1.6;
}


/* ================================
   INPUT
================================ */

.stTextInput label {
    color: #d8d0c8 !important;

    font-size: 0.9rem !important;

    font-weight: 600 !important;
}

.stTextInput input {
    background:
        rgba(255, 255, 255, 0.055) !important;

    border:
        1px solid rgba(226, 194, 159, 0.17) !important;

    border-radius: 14px !important;

    color: #f3eee8 !important;

    padding: 0.85rem 1rem !important;

    transition:
        all 0.25s ease !important;
}

.stTextInput input:focus {
    border-color:
        rgba(214, 156, 104, 0.70) !important;

    box-shadow:
        0 0 0 3px
        rgba(214, 156, 104, 0.10) !important;
}


/* ================================
   BUTTON
================================ */

.stButton button {
    width: 100% !important;

    min-height: 52px !important;

    border-radius: 14px !important;

    border:
        1px solid
        rgba(240, 211, 175, 0.35) !important;

    background:
        linear-gradient(
            100deg,
            #d49a5c,
            #c77975
        ) !important;

    color: #171116 !important;

    font-weight: 800 !important;

    letter-spacing: 0.05em !important;

    box-shadow:
        0 10px 30px
        rgba(202, 120, 100, 0.18) !important;

    transition:
        transform 0.2s ease,
        box-shadow 0.2s ease !important;
}

.stButton button:hover {
    transform:
        translateY(-2px) !important;

    box-shadow:
        0 16px 40px
        rgba(202, 120, 100, 0.30) !important;
}


/* ================================
   PRIVACY
================================ */

.privacy-text {
    text-align: center;

    margin-top: 1.3rem;

    color: #85808a;

    font-size: 0.82rem;
}


/* ================================
   FEATURES
================================ */

.features-wrapper {
    max-width: 1000px;

    margin: 3.8rem auto 1.8rem auto;
}

.features-title {
    text-align: center;

    color: #eee8e1;

    font-size: 1.45rem;

    font-weight: 700;
}

.feature-card {
    min-height: 230px;

    padding: 1.7rem;

    border-radius: 22px;

    background:
        linear-gradient(
            145deg,
            rgba(255, 255, 255, 0.055),
            rgba(255, 255, 255, 0.015)
        );

    border:
        1px solid
        rgba(255, 255, 255, 0.08);

    box-shadow:
        0 12px 35px
        rgba(0, 0, 0, 0.18);

    transition:
        transform 0.25s ease,
        border 0.25s ease,
        box-shadow 0.25s ease;
}

.feature-card:hover {
    transform:
        translateY(-6px);

    border:
        1px solid
        rgba(218, 163, 112, 0.35);

    box-shadow:
        0 20px 50px
        rgba(0, 0, 0, 0.28);
}

.feature-icon {
    width: 50px;
    height: 50px;

    display: flex;

    align-items: center;
    justify-content: center;

    margin-bottom: 1.1rem;

    border-radius: 15px;

    font-size: 1.45rem;

    background:
        linear-gradient(
            145deg,
            rgba(218, 163, 112, 0.22),
            rgba(199, 121, 117, 0.13)
        );

    border:
        1px solid
        rgba(226, 194, 159, 0.15);
}

.feature-card h3 {
    color: #eee8e1;

    font-size: 1.1rem;

    margin-bottom: 0.7rem;
}

.feature-card p {
    color: #a39ba6;

    font-size: 0.9rem;

    line-height: 1.65;

    margin: 0;
}


/* ================================
   FOOTER
================================ */

.login-footer {
    text-align: center;

    margin-top: 3rem;

    color: #6e6872;

    font-size: 0.78rem;

    letter-spacing: 0.06em;
}

</style>
""", unsafe_allow_html=True)


    # ================================
    # HERO
    # ================================

    st.markdown("""
<div class="login-hero">
<div class="hero-icon">🏋🏻‍♀️</div>
<div class="hero-title">AI Real-time GYM Trainer</div>
<div class="hero-tagline">Train Smarter. Move Better.</div>
</div>
""", unsafe_allow_html=True)


    # ================================
    # LOGIN CARD
    # ================================

    st.markdown("""
<div class="login-card">
<div class="login-heading">Welcome! Ready to train?</div>
<div class="login-subtext">
Enter your unique name to begin your AI-powered workout session.
</div>
</div>
""", unsafe_allow_html=True)


    # ================================
    # LOGIN INPUT
    # ================================

    _, center_col, _ = st.columns([1, 2.2, 1])

    with center_col:

        username = st.text_input(
            "Name (unique)",
            placeholder="Enter your name e.g. Divya",
            key="login_username_input"
        )

        start_button = st.button(
            "START SESSION →",
            key="start_login_session"
        )

        st.markdown("""
<div class="privacy-text">
🔒 Your workout data is secure and private
</div>
""", unsafe_allow_html=True)


    # ================================
    # LOGIN ACTION
    # ================================

    if start_button:

        clean_username = username.strip()

        if not clean_username:
            st.warning("Please enter your name to continue.")

        else:

            try:

                user_id = get_or_create_user(clean_username)

                st.session_state.username = clean_username
                st.session_state.user_id = user_id

                st.rerun()

            except Exception as e:

                st.error(
                    f"Unable to start your session: {e}"
                )


    # ================================
    # FEATURES TITLE
    # ================================

    st.markdown("""
<div class="features-wrapper">
<div class="features-title">
Your AI-powered training experience
</div>
</div>
""", unsafe_allow_html=True)


    # ================================
    # FEATURE CARDS
    # ================================

    feature_col1, feature_col2, feature_col3 = st.columns(3)


    with feature_col1:

        st.markdown("""
<div class="feature-card">
<div class="feature-icon">🎯</div>
<h3>Real-time Pose Tracking</h3>
<p>
Live pose detection monitors your movement
and tracks every exercise repetition.
</p>
</div>
""", unsafe_allow_html=True)


    with feature_col2:

        st.markdown("""
<div class="feature-card">
<div class="feature-icon">🧠</div>
<h3>Smart Form Feedback</h3>
<p>
Detect movement mistakes and receive
instant AI-powered form guidance.
</p>
</div>
""", unsafe_allow_html=True)


    with feature_col3:

        st.markdown("""
<div class="feature-card">
<div class="feature-icon">🔊</div>
<h3>Proactive AI Coaching</h3>
<p>
Get real-time voice coaching while
performing your workout.
</p>
</div>
""", unsafe_allow_html=True)


    # ================================
    # FOOTER
    # ================================

    st.markdown("""
<div class="login-footer">
POWERED BY COMPUTER VISION · AI COACHING · REAL-TIME ANALYTICS
</div>
""", unsafe_allow_html=True)


    return False
