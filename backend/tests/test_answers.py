import pytest

from app.services.answers import clean_guess, edit_distance, is_correct, normalize, variants
from app.services.scoring import score_for


@pytest.mark.parametrize(
    ("guess", "title"),
    [
        ("bohemian rhapsody", "Bohemian Rhapsody"),
        ("BOHEMIAN RHAPSODY", "Bohemian Rhapsody"),
        ("  Bohemian    Rhapsody  ", "Bohemian Rhapsody"),
        ("Bohemian Rhapsody!!!", "Bohemian Rhapsody"),
        ("epitafio", "Epitáfio"),
        ("ÉPITÁFIO", "Epitáfio"),
        ("nao existe amor em sp", "Não Existe Amor em SP"),
        ("Satisfaction", "(I Can't Get No) Satisfaction"),
        ("i cant get no satisfaction", "(I Can't Get No) Satisfaction"),
        ("Anarchy in the UK", "Anarchy in the U.K."),
        ("mr brightside", "Mr. Brightside"),
        ("baby one more time", "...Baby One More Time"),
        ("Scientist", "The Scientist"),
        ("dont stop believin", "Don't Stop Believin'"),
        ("Rock & Roll All Nite", "Rock and Roll All Nite"),
        ("Bohemian Rhapsody - Remastered 2011", "Bohemian Rhapsody"),
        ("bohemian rapsody", "Bohemian Rhapsody"),  # erro de digitação tolerado
        ("Smells Like Teen Sprit", "Smells Like Teen Spirit"),
    ],
)
def test_accepts_equivalent_titles(guess: str, title: str) -> None:
    assert is_correct(guess, title, [])


@pytest.mark.parametrize(
    ("guess", "title"),
    [
        ("Stairway to Heaven", "Bohemian Rhapsody"),
        ("Queen", "Bohemian Rhapsody"),  # artista não é a resposta
        ("Bohemian", "Bohemian Rhapsody"),
        ("", "Bohemian Rhapsody"),
        ("!!!", "Bohemian Rhapsody"),
        ("Hey", "Hey Jude"),
    ],
)
def test_rejects_wrong_titles(guess: str, title: str) -> None:
    assert not is_correct(guess, title, [])


def test_aliases_are_accepted() -> None:
    assert is_correct("Sweet Child of Mine", "Sweet Child O' Mine", ["Sweet Child of Mine"])
    assert is_correct("parabens pra voce", "Parabéns a Você", ["Parabéns pra Você"])


def test_typo_tolerance_does_not_accept_another_catalog_song() -> None:
    # "Hurt" está a uma letra de "Hurts", mas é outra música do catálogo.
    assert not is_correct("Hurt", "Hurts", [], other_titles=["Hurt", "Hurts"])
    assert is_correct("Hurts", "Hurts", [], other_titles=["Hurt", "Hurts"])


def test_short_titles_need_exact_match() -> None:
    assert not is_correct("Jumo", "Jump", [])
    assert is_correct("jump", "Jump", [])


def test_normalize_and_variants() -> None:
    assert normalize("  Ação   Já! ") == "acao ja"
    assert variants("Primeiros Erros (Chove)") == {"primeiros erros chove", "primeiros erros"}
    assert normalize("Get Lucky feat. Pharrell") == "get lucky"


def test_edit_distance() -> None:
    assert edit_distance("abc", "abc") == 0
    assert edit_distance("abc", "acb") == 1  # transposição
    assert edit_distance("kitten", "sitting") == 3
    assert edit_distance("a", "abcdefgh", limit=2) == 3


def test_clean_guess_strips_control_chars_and_limits_size() -> None:
    assert clean_guess("Hey\x00 Jude\n") == "Hey Jude"
    assert len(clean_guess("a" * 500)) == 120


@pytest.mark.parametrize(("attempt", "points"), [(1, 100), (2, 80), (3, 60), (4, 40),
                                                 (5, 20), (6, 10)])
def test_score_table(attempt: int, points: int) -> None:
    assert score_for(attempt, True, [100, 80, 60, 40, 20, 10]) == points


def test_loss_scores_zero_and_invalid_attempt_raises() -> None:
    assert score_for(6, False, [100, 80, 60, 40, 20, 10]) == 0
    with pytest.raises(ValueError):
        score_for(7, True, [100, 80, 60, 40, 20, 10])
