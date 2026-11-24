import streamlit as st


st.set_page_config(
    page_title="Kitami Gomi AI Prototype",
    page_icon="♻️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

home_page = st.Page("home.py", title="Home", icon="🏠", default=True)
version_1_page = st.Page("main_v1.py", title="Version 1.0", icon="1️⃣")
version_2_page = st.Page("main_v2.py", title="Version 2.0", icon="2️⃣")
version_3_page = st.Page("main_v3.py", title="Version 3.0", icon="3️⃣")
version_4_page = st.Page("main_v4.py", title="Version 4.0", icon="4️⃣")

navigation = st.navigation(
    [home_page, version_1_page, version_2_page, version_3_page, version_4_page],
    position="hidden",
)
navigation.run()
