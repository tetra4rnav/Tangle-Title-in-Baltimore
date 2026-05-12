import streamlit as st

from shared_style import apply_theme, render_page_toc, section_h2, support_badge


st.set_page_config(
    page_title="Tangled Titles Synthesis Platform",
    layout="wide",
)

apply_theme()

support_badge()

INSTRUCTION_TOC = (
    ("how-to-use-this-platform", "How to use this platform"),
    ("synthesis-logic", "Synthesis Logic"),
)

render_page_toc("instruction", INSTRUCTION_TOC)

st.title("Tangled Titles Synthesis Platform")

st.markdown(
    """
    <p class="section-note">
    This interactive site synthesizes qualitative interviews, power mapping, and
    quantitative spatial analysis to explain how tangled titles shape housing
    stability and Black wealth preservation in Baltimore.
    </p>
    """,
    unsafe_allow_html=True,
)

section_h2("how-to-use-this-platform", "How to use this platform")
st.markdown(
    """
    <div class="takeaway">
    Begin with the Introduction to understand the resident pathway, then move
    through the Resident Journey, Quant Map, Interview, and Power Map to build
    the final presentation narrative.
    </div>
    """,
    unsafe_allow_html=True,
)

st.write("")

col1, col2, col3 = st.columns(3)

with col1:
    st.markdown(
        """
        <div class="soft-card">
            <h3>Start with Introduction</h3>
            <p>Understand the resident pathway and the core system question before
            moving into the evidence pages.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

with col2:
    st.markdown(
        """
        <div class="soft-card">
            <h3>Read the Resident Journey</h3>
            <p>Connect the qualitative, quantitative, and systems evidence into a
            presentation-ready synthesis.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

with col3:
    st.markdown(
        """
        <div class="soft-card">
            <h3>Explore the Evidence</h3>
            <p>Move through Quant Map, Interview, and Power Map to inspect
            spatial patterns, themes, and system actors.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

st.write("")

section_h2("synthesis-logic", "Synthesis Logic")
st.markdown(
    """
    This site is organized as a synthesis product. Each page connects a different
    source of evidence to the same explanatory question: where does the tangled
    title problem become a barrier, and where can intervention enter the system?
    """
)
