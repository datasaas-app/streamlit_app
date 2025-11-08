# app.py
import streamlit as st
import requests
import uuid
import pandas as pd
import seaborn as sns
import sweetviz as sv
from sklearn.datasets import load_iris, load_diabetes

st.set_page_config(page_title="Analytics App", layout="wide")

# -----------------------
# CONFIG / SECRETS
# -----------------------
# secrets.toml should contain:
# [google]
# client_id = "xxx.apps.googleusercontent.com"
# client_secret = "yyy"
#
# [app]
# LOCAL_URL = "http://localhost:8501"   # exact URI you registered in Google Cloud

CLIENT_ID = st.secrets["google"]["client_id"]
CLIENT_SECRET = st.secrets["google"]["client_secret"]
LOCAL_URL = st.secrets["app"].get("LOCAL_URL", "http://localhost:8501")

REDIRECT_URI = LOCAL_URL  # ensure this exactly matches what's in Google Cloud Console

AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"
SCOPE = "openid email profile"

# -----------------------
# Helpers: OAuth requests
# -----------------------
def build_login_link(state: str):
    # Note: redirect_uri must match exactly what's registered.
    params = {
        "client_id": CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "scope": SCOPE,
        "state": state,
        "access_type": "offline",
        "prompt": "consent",
    }
    from urllib.parse import urlencode
    return f"{AUTH_URL}?{urlencode(params)}"

def exchange_code_for_token(code: str):
    data = {
        "code": code,
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "redirect_uri": REDIRECT_URI,
        "grant_type": "authorization_code",
    }
    resp = requests.post(TOKEN_URL, data=data, timeout=15)
    resp.raise_for_status()
    return resp.json()

def fetch_userinfo(access_token: str):
    headers = {"Authorization": f"Bearer {access_token}"}
    resp = requests.get(USERINFO_URL, headers=headers, timeout=15)
    resp.raise_for_status()
    return resp.json()

# -----------------------
# Session state defaults
# -----------------------
if "oauth_token" not in st.session_state:
    st.session_state["oauth_token"] = None
if "user" not in st.session_state:
    st.session_state["user"] = None
if "oauth_state" not in st.session_state:
    st.session_state["oauth_state"] = None

# -----------------------
# OAuth callback handling
# -----------------------
qp = st.query_params
if "code" in qp and st.session_state["oauth_token"] is None:
    # get code value (list or str)
    code = qp["code"][0] if isinstance(qp["code"], list) else qp["code"]
    try:
        token_json = exchange_code_for_token(code)
        access_token = token_json.get("access_token")
        if access_token:
            st.session_state["oauth_token"] = token_json
            # fetch userinfo
            user = fetch_userinfo(access_token)
            st.session_state["user"] = user
        else:
            st.error("No access token received from Google.")
    except Exception as e:
        st.error(f"Error exchanging code for token: {e}")
    # clear query params so we don't process code repeatedly
    st.query_params = {}

# -----------------------
# Not logged in -> show login link
# -----------------------
if st.session_state["oauth_token"] is None:
    # create and store state to compare later (optional CSRF protection)
    state = str(uuid.uuid4())
    st.session_state["oauth_state"] = state
    login_link = build_login_link(state)
    st.title("Login required")
    st.markdown("Click below to sign in with your Google account:")
    st.markdown(f"[**Sign in with Google**]({login_link})")
    st.stop()

# -----------------------
# Logged-in: Sidebar UI
# -----------------------
user = st.session_state.get("user", {})
# Simple global CSS to make images round
st.markdown(
    """
    <style>
    img {
      border-radius: 50%;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

with st.sidebar:
    if user.get("picture"):
        st.image(user.get("picture"), width=80)
    st.write(f"**{user.get('email', 'Unknown')}**")
    st.write("---")
    if st.button("Log out"):
        # clear session and reload
        st.session_state["oauth_token"] = None
        st.session_state["user"] = None
        st.experimental_rerun()

# -----------------------
# Sidebar navigation
# -----------------------
page = st.sidebar.radio("Navigation", ["Home", "Data Profiler"])

# -----------------------
# HOME PAGE (style B)
# -----------------------
if page == "Home":
    st.title("🏠 Home")
    st.write(f"Welcome, **{user.get('email', '')}**!")
    st.write(
        """
        This is your production-ready local app running on an Ubuntu VM (or local machine).
        
        Instructions:
        - Use the **Data Profiler** page to upload or choose sample datasets.
        - The Google account avatar appears in the sidebar.
        - To run in a public environment later, change `REDIRECT_URI` to your public URL
          and add that URL to the OAuth Authorized Redirect URIs in Google Cloud Console.
        """
    )

# -----------------------
# DATA PROFILER PAGE
# -----------------------
elif page == "Data Profiler":
    st.title("📊 Data Profiler")
    st.write("This page is visible only after login.")

    compare_mode = st.checkbox("Compare two datasets (Sweetviz compare)", value=False)

    def pick_dataset(label):
        sample = st.selectbox(
            f"{label} – sample dataset",
            ["None", "Titanic", "Iris", "Diabetes"],
            index=0,
            key=f"{label}_sample",
        )
        uploaded_file = st.file_uploader(f"{label} – upload CSV", type=["csv"], key=f"{label}_upload")
        df = None
        if sample == "Titanic":
            try:
                df = sns.load_dataset("titanic")
            except Exception:
                df = None
        elif sample == "Iris":
            df = load_iris(as_frame=True).frame
        elif sample == "Diabetes":
            df = load_diabetes(as_frame=True).frame

        if uploaded_file is not None:
            try:
                df = pd.read_csv(uploaded_file)
            except Exception as e:
                st.error(f"Failed to read CSV: {e}")
                df = None
        return df

    df_main = pick_dataset("Dataset A")
    df_compare = pick_dataset("Dataset B") if compare_mode else None

    if df_main is not None and (not compare_mode or df_compare is not None):
        st.subheader("Data Preview – Dataset A")
        st.dataframe(df_main, height=350)

        if compare_mode:
            st.subheader("Data Preview – Dataset B")
            st.dataframe(df_compare, height=350)

        if st.button("Generate Sweetviz Report"):
            try:
                if compare_mode:
                    report = sv.compare([df_main, "A"], [df_compare, "B"])
                else:
                    report = sv.analyze(df_main)
                report_file = "sweetviz_report.html"
                report.show_html(report_file, open_browser=False)
                with open(report_file, "r", encoding="utf-8") as f:
                    html = f.read()
                st.components.v1.html(html, height=900, scrolling=True)
            except Exception as e:
                st.error(f"Failed to generate Sweetviz report: {e}")
    else:
        st.info("Pick (or upload) dataset(s) to start profiling.")
