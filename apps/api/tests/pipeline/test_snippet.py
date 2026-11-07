from app.modules.pipeline.snippet import MAX_SNIPPET_CHARS, best_snippet

CLAIM = "Ueno Bank cerró, generando una crisis en Paraguay."


def test_short_clean_text_stays_the_same() -> None:
    assert best_snippet("Fragmento real de la fuente.", CLAIM) == "Fragmento real de la fuente."


def test_picks_the_sentence_about_the_claim() -> None:
    content = (
        "El Papa inicia este viernes su gira por Uruguay, Argentina y Perú con un mensaje. "
        "El Banco Central cerró Ueno Bank y desató una crisis en Paraguay por su solvencia. "
        "Teherán podría reabrir el estrecho de Ormuz si Estados Unidos acepta sus condiciones."
    )

    assert best_snippet(content, CLAIM).startswith("El Banco Central cerró Ueno Bank")


def test_drops_page_furniture() -> None:
    content = (
        "Inicia sesión para leer todas las noticias Iniciar sesión Crear cuenta Mi cuenta "
        "Newsletters Suscriptores [...] Banner WhatsApp [...] "
        "Ueno Bank cerró sus sucursales y dejó a los clientes sin acceso a sus cuentas. [...] "
        "Compartir: Whatsapp Facebook Twitter Bluesky Linkedin Copiar enlace"
    )

    snippet = best_snippet(content, CLAIM)

    assert snippet.startswith("Ueno Bank cerró sus sucursales")
    assert "Whatsapp" not in snippet
    assert "Inicia sesión" not in snippet


def test_strips_markdown_marks() -> None:
    content = "## ¿Qué decidió el Banco? ### Ueno Bank cerró por una crisis grave de solvencia."

    assert "#" not in best_snippet(content, CLAIM)


def test_never_crosses_a_gap_in_the_source() -> None:
    content = (
        "Ueno Bank cerró sus puertas en Paraguay este martes por la mañana. [...] "
        "Peña renunció a la presidencia días después del escándalo financiero."
    )

    assert "Peña" not in best_snippet(content, CLAIM)


def test_adds_the_next_sentence_when_it_fits() -> None:
    first = "Ueno Bank cerró sus puertas en Paraguay este martes por la mañana."
    second = "Los clientes no pudieron retirar sus ahorros durante varios días."

    assert best_snippet(f"{first} {second}", CLAIM) == f"{first} {second}"


def test_long_text_is_cut_at_a_word() -> None:
    content = "Ueno Bank cerró en Paraguay " + "con una crisis muy grave " * 40

    snippet = best_snippet(content, CLAIM)

    assert len(snippet) <= MAX_SNIPPET_CHARS + 1
    assert snippet.endswith("…")
    assert content.startswith(snippet[:-1].rstrip())


def test_every_word_comes_from_the_source() -> None:
    content = (
        "Banner WhatsApp [...] Ueno Bank cerró. La crisis en Paraguay creció mucho esta semana."
    )

    snippet = best_snippet(content, CLAIM)

    assert snippet.rstrip("…") in content


def test_text_in_another_language_still_gives_a_snippet() -> None:
    content = "The central bank seized the lender on Tuesday and its branches locked their doors."

    assert best_snippet(content, CLAIM) == content


def test_only_noise_falls_back_to_the_start_of_the_text() -> None:
    assert best_snippet("Banner WhatsApp", CLAIM) == "Banner WhatsApp"


def test_empty_text_gives_an_empty_snippet() -> None:
    assert best_snippet("", CLAIM) == ""


def test_an_abbreviation_does_not_end_the_sentence() -> None:
    content = (
        "Ueno Bank cerró en Paraguay por la crisis, según el Congreso, Thursday, Nov. 5, 2026."
    )

    assert best_snippet(content, CLAIM) == content


def test_invisible_characters_are_removed() -> None:
    content = "Ueno Bank cerró y la crisis dejó a 3 ​millones de clientes sin ⁠acceso."

    assert (
        best_snippet(content, CLAIM)
        == "Ueno Bank cerró y la crisis dejó a 3 millones de clientes sin acceso."
    )


def test_leading_punctuation_is_removed() -> None:
    content = ": Según el informe, Ueno Bank cerró y generó una crisis en todo Paraguay."

    assert best_snippet(content, CLAIM).startswith("Según el informe")
