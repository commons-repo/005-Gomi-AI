import streamlit as st


st.markdown(
    """
    <style>
    .home-title {
        text-align: center;
        font-size: 2.6rem;
        font-weight: 750;
        margin-top: 8vh;
        margin-bottom: 2.2rem;
    }
    [data-testid="stPageLink"] a {
        min-height: 4.5rem;
        justify-content: center;
        border-radius: 0.8rem;
    }
    [data-testid="stPageLink"] p {
        font-size: 1.45rem;
        font-weight: 650;
    }
    </style>
    <div class="home-title">♻️ Kitami Gomi AI Prototype</div>
    """,
    unsafe_allow_html=True,
)

version_1, version_2, version_3, version_4 = st.columns(4, gap="medium")

with version_1:
    st.page_link(
        "main_v1.py",
        label="Version 1.0",
        icon="1️⃣",
        use_container_width=True,
    )

with version_2:
    st.page_link(
        "main_v2.py",
        label="Version 2.0",
        icon="2️⃣",
        use_container_width=True,
    )

with version_3:
    st.page_link(
        "main_v3.py",
        label="Version 3.0",
        icon="3️⃣",
        use_container_width=True,
    )

with version_4:
    st.page_link(
        "main_v4.py",
        label="Version 4.0",
        icon="4️⃣",
        use_container_width=True,
    )

st.markdown("<div style='height: 4vh;'></div>", unsafe_allow_html=True)
st.divider()

with st.expander("Important notice", expanded=False):
    st.warning(
        "This application is an unofficial personal research and demonstration "
        "prototype. AI-based image recognition and responses may contain mistakes. "
        "Results are not official waste-sorting determinations by Kitami City."
    )

    st.markdown(
        """
This prototype is independently developed by **Angkush Kumar Ghosh, a resident of Kitami City**, as a personal research and demonstration project.  

At present, this prototype is **not affiliated with, endorsed by, authorized by, operated by, or developed in cooperation with Kitami City, Kitami City Office, or any other public organization**.  

Users should verify the displayed information against official Kitami City resources and use the prototype based on their own judgment and responsibility.  

**Please verify the information using the official Kitami City sources below:**

- [Kitami Autonomous Region waste sorting, calendar and dictionary](https://www.city.kitami.lg.jp/administration/life/detail.php?content=9346)
- [Waste guides, sorting dictionary and English guide](https://www.city.kitami.lg.jp/administration/life/detail.php?content=5755)
- https://www.city.kitami.lg.jp/administration/life/category/?category=453

        """
    )
