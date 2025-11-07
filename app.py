import streamlit as st
import pandas as pd
import seaborn as sns
import sweetviz as sv
from sklearn.datasets import load_iris, load_diabetes
from authlib.integrations.requests_client import OAuth2Session
from PIL import Image, ImageDraw, ImageFont
import time

# -------------------------------------------------
# STREAMLIT BASE
# -------------------------------------------------
st.set_page_config(page_title="Data SaaS", page_icon="📊", layout="wide")

# -------------------------------------------------
# GOOGLE OAUTH CONFIG
# -------------------------------------------------
GOOGLE_CLIENT_ID     = st.secrets["GOOGLE_CLIENT_ID"]
GOOGLE_CLIENT_SECRET = st.secrets["GOOGLE_CLIENT_SECRET"]

if st.secrets.get("ENV") == "production":
    REDIRECT_URI = "https://appweb-yveka9tg6yzdp5iikkyrfh.streamlit.app/"
else:
    REDIRECT_URI = "http://localhost:8501/"

AUTHORIZE_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL     = "https://oauth2.googleapis.com/token"
USERINFO_URL  = "https://openidconnect.googleapis.com/v1/userinfo"

oauth = OAuth2Session(
    client_id     = GOOGLE_CLIENT_ID,
    client_secret = GOOGLE_CLIENT_SECRET,
    scope         = "openid email profile",
    redirect_uri  = REDIRECT_URI,
)


# -------------------------------------------------
# DATA PROFILER PAGE
# -------------------------------------------------
def run_profiler_page():
    st.title("📊 Data Profiler")

    compare_mode = st.checkbox("Compare two datasets (Sweetviz compare)", value=False)

    def pick_dataset(label: str):
        sample = st.selectbox(
            f"{label} – sample dataset",
            ["None", "Titanic", "Iris", "Diabetes"],
            index=0,
            key=label
        )

        f = st.file_uploader(f"{label} – upload CSV", type=["csv"], key=f"{label}_upload")

        if sample == "Titanic":
            d = sns.load_dataset("titanic")
        elif sample == "Iris":
            d = load_iris(as_frame=True).frame
        elif sample == "Diabetes":
            d = load_diabetes(as_frame=True).frame
        else:
            d = None

        if f:
            d = pd.read_csv(f)

        return d

    df_main = pick_dataset("Dataset A")
    df_compare = pick_dataset("Dataset B") if compare_mode else None

    if df_main is not None and (not compare_mode or df_compare is not None):

        if st.button("Generate Sweetviz Report"):
            if compare_mode:
                report = sv.compare([df_main, "A"], [df_compare, "B"])
            else:
                report = sv.analyze(df_main)

            report.show_html("sweetviz_report.html", open_browser=False)

            with open("sweetviz_report.html", encoding="utf-8") as f:
                html = f.read()

            st.components.v1.html(html, height=900, scrolling=True)
    else:
        st.write("Pick (or upload) dataset(s)")


# -------------------------------------------------
# AUTH CALLBACK
# -------------------------------------------------
# query_params returns dict not function
qp = st.query_params

if "code" in qp and "oauth_token" not in st.session_state:
    token = oauth.fetch_token(TOKEN_URL, code=qp["code"])
    st.session_state["oauth_token"] = token
    st.query_params.clear()  # remove code param
    st.rerun()

# not logged in
if "oauth_token" not in st.session_state:
    st.title("Sign in")

    auth_url, _ = oauth.create_authorization_url(
        AUTHORIZE_URL,
        access_type="offline",
        prompt="consent"
    )

    st.link_button("Sign in with Google", auth_url)
    st.stop()

# -------------------------------------------------
# LOGGED IN SECTION
# -------------------------------------------------
with st.spinner("Authenticating user..."):
    time.sleep(0.4)

token = st.session_state["oauth_token"]
userinfo = oauth.get(USERINFO_URL, token=token).json()

email  = userinfo.get("email")
name   = userinfo.get("name", email.split("@")[0])
avatar = userinfo.get("picture")

# fallback avatar
if not avatar:
    img = Image.new("RGB", (120, 120), (48, 48, 48))
    draw = ImageDraw.Draw(img)
    letter = name[0].upper()
    font = ImageFont.load_default()
    w, h = draw.textsize(letter, font=font)
    draw.text(((120-w)/2, (120-h)/2), letter, fill=(255,255,255), font=font)
    avatar = img

# sidebar UI
with st.sidebar:
    st.image(avatar, width=80)
    st.markdown(f"**{name}**")
    st.caption(email)
    st.markdown("---")

    page = st.selectbox("Menu", ["Home", "Data Profiler"])

    if st.button("Logout"):
        st.session_state.clear()
        st.rerun()

st.title("✅ Logged in")

# router
if page == "Home":
    st.write("Welcome to your dashboard.")
    st.write("Pick an option from the menu on the left.")

elif page == "Data Profiler":
    run_profiler_page()
