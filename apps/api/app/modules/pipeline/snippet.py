"""The quote a report shows for a search result.

Search engines return page text with menus and sharing buttons in it. This
picks real sentences out of that text, by fixed rules: no model writes a
quote, so a report can't show words the source didn't publish.
"""

import re
import unicodedata

MAX_SNIPPET_CHARS = 320
# Tavily marks the gaps between the passages it extracted with this.
_GAP = re.compile(r"\[\.\.\.\]|\n+")
# Only before a capital, so "Nov. 5" and "art. 3" don't end a sentence.
_SENTENCE_END = re.compile(r"(?<=[.!?…])\s+(?=[¿¡«\"“]?[A-ZÁÉÍÓÚÑ])")
_WORD = re.compile(r"\w+")
_MIN_SENTENCE_CHARS = 40
_MIN_WORD_CHARS = 4
_LEADING = " :;,.-–—"
_NOISE = (
    "add ap news",
    "banner whatsapp",
    "bookmark guardar",
    "comentar (0)",
    "compartir",
    "copia y pega",
    "copiar enlace",
    "crear cuenta",
    "descárgala",
    "dale play",
    "escucha este artículo",
    "facebook",
    "iniciar sesión",
    "inicia sesión",
    "le puede interesar",
    "lea también",
    "newsletter",
    "publicidad",
    "read more",
    "suscríbete",
    "tracking technologies",
    "twitter",
)


def _visible(text: str) -> str:
    """Without zero-width marks and the like, which pages use for line breaks."""
    return "".join(c for c in text if unicodedata.category(c) != "Cf")


def _words(text: str) -> set[str]:
    plain = unicodedata.normalize("NFKD", text.lower())
    plain = "".join(c for c in plain if not unicodedata.combining(c))
    return {w for w in _WORD.findall(plain) if len(w) >= _MIN_WORD_CHARS}


def _passages(content: str) -> list[list[str]]:
    """Each stretch of continuous text, split into its usable sentences."""
    passages = []
    for passage in _GAP.split(content):
        cleaned = _visible(passage).replace("#", " ")
        sentences = [" ".join(s.split()).lstrip(_LEADING) for s in _SENTENCE_END.split(cleaned)]
        passages.append(
            [
                s
                for s in sentences
                if len(s) >= _MIN_SENTENCE_CHARS and not any(noise in s.lower() for noise in _NOISE)
            ]
        )
    return passages


def _cut(text: str) -> str:
    if len(text) <= MAX_SNIPPET_CHARS:
        return text
    return text[:MAX_SNIPPET_CHARS].rsplit(" ", 1)[0].rstrip(" ,;:") + "…"


def best_snippet(content: str, claim: str) -> str:
    """The sentences that talk most about `claim`, with the ones right after
    them while they fit. Earlier text wins a tie, so with nothing in common,
    as with a page in another language, the quote is where the page starts."""
    claim_words = _words(claim)
    best: tuple[int, int] | None = None
    best_score = -1
    passages = _passages(content)
    for p, sentences in enumerate(passages):
        for s, sentence in enumerate(sentences):
            score = len(claim_words & _words(sentence))
            if score > best_score:
                best, best_score = (p, s), score

    if best is None:
        return _cut(" ".join(_visible(content).split()))

    sentences = passages[best[0]]
    snippet = sentences[best[1]]
    for following in sentences[best[1] + 1 :]:
        if len(snippet) + 1 + len(following) > MAX_SNIPPET_CHARS:
            break
        snippet = f"{snippet} {following}"
    return _cut(snippet)
