"""Interface Streamlit de l'assistant documentaire.

Lancer : streamlit run app.py
"""
import tempfile
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

from src.llm import answer
from src.rag import build_index

load_dotenv()
DOCS_DIR = Path(__file__).parent / "documents"

st.set_page_config(page_title="Assistant documentaire IA", page_icon="📄")
st.title("Assistant documentaire IA")
st.caption("Posez une question : l'assistant répond à partir des documents internes et cite ses sources.")


@st.cache_resource(show_spinner="Indexation des documents…")
def load_index(paths: tuple[str, ...]):
    return build_index([Path(p) for p in paths])


with st.sidebar:
    st.header("Documents")
    uploads = st.file_uploader("Ajouter vos documents (PDF, Markdown, TXT)",
                               type=["pdf", "md", "txt"], accept_multiple_files=True)
    if uploads:
        tmp = Path(tempfile.mkdtemp())
        for f in uploads:
            (tmp / f.name).write_bytes(f.getvalue())
        paths = sorted(str(p) for p in tmp.iterdir())
        st.success(f"{len(paths)} document(s) chargé(s)")
    else:
        paths = sorted(str(p) for p in DOCS_DIR.glob("*") if p.suffix in {".md", ".txt", ".pdf"})
        st.info("Démo : documents de l'entreprise fictive BâtiNova.")
    for p in paths:
        st.write("•", Path(p).name)
    show_sources = st.toggle("Afficher les passages utilisés", value=True)

index = load_index(tuple(paths))

if "history" not in st.session_state:
    st.session_state.history = []

for msg in st.session_state.history:
    with st.chat_message(msg["role"]):
        st.markdown(msg["display"])

if question := st.chat_input("Ex. : Comment me faire rembourser un repas ?"):
    with st.chat_message("user"):
        st.markdown(question)
    passages = [c for c, _ in index.search(question)]
    api_history = [{"role": m["role"], "content": m["display"]} for m in st.session_state.history]
    with st.chat_message("assistant"):
        with st.spinner("Recherche dans les documents…"):
            reply = answer(question, passages, api_history)
        st.markdown(reply)
        if show_sources and passages:
            with st.expander(f"{len(passages)} passage(s) utilisé(s)"):
                for c in passages:
                    st.markdown(f"**{c.source} — {c.section}**\n\n> {c.text}")
    st.session_state.history += [
        {"role": "user", "display": question},
        {"role": "assistant", "display": reply},
    ]
