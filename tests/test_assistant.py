from pathlib import Path
from types import SimpleNamespace

import pytest

from src.llm import answer, build_messages
from src.rag import build_index, tokenize

DOCS = sorted((Path(__file__).parent.parent / "documents").glob("*.md"))


@pytest.fixture(scope="module")
def index():
    return build_index(DOCS)


def test_tokenize_ignore_accents_et_mots_vides():
    assert tokenize("Les congés payés") == ["conge", "paye"]


@pytest.mark.parametrize("question, fichier_attendu", [
    ("Combien est remboursé un repas sur un chantier ?", "notes-de-frais.md"),
    ("Comment poser mes congés ?", "conges-et-absences.md"),
    ("Le casque est-il obligatoire ?", "securite-chantier.md"),
    ("J'ai perdu mon ordinateur portable", "informatique-et-onboarding.md"),
    ("Que faire en cas d'arrêt maladie ?", "conges-et-absences.md"),
])
def test_recherche_trouve_le_bon_document(index, question, fichier_attendu):
    resultats = index.search(question)
    assert resultats, "aucun passage trouvé"
    assert resultats[0][0].source == fichier_attendu


def test_question_hors_sujet_ne_renvoie_rien(index):
    assert index.search("Quelle est la recette du couscous ?") == []


def test_sans_passage_pas_d_appel_a_claude():
    class ClientInterdit:
        @property
        def messages(self):
            raise AssertionError("Claude ne doit pas être appelé")
    assert "aucun document" in answer("Question ?", [], client=ClientInterdit())


def test_appel_claude_avec_sources(index):
    appels = {}

    class FauxClient:
        class messages:
            @staticmethod
            def create(**kwargs):
                appels.update(kwargs)
                return SimpleNamespace(content=[SimpleNamespace(type="text", text="20,70 € [notes-de-frais.md]")])

    passages = [c for c, _ in index.search("remboursement repas chantier")]
    reponse = answer("Combien pour un repas ?", passages, client=FauxClient())
    assert reponse == "20,70 € [notes-de-frais.md]"
    contenu = appels["messages"][-1]["content"]
    assert "<sources>" in contenu and "notes-de-frais.md" in contenu
    assert "N'invente jamais" in appels["system"]


def test_historique_limite_a_trois_echanges():
    historique = [{"role": "user" if i % 2 == 0 else "assistant", "content": str(i)} for i in range(10)]
    messages = build_messages("Q", [], historique)
    assert len(messages) == 7
