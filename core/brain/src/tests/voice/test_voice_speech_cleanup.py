# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

'Voice speech projection and Markdown cleanup contracts.'

from unittest.mock import patch

from brain.infrastructure.voice.contracts.avatar_speak_request import AvatarSpeakRequest
from brain.infrastructure.voice.service.voice_service import VoiceService, clean_text_for_speech


def test_speech_cleanup_extracts_angi_dialogue_body_before_stripping_roleplay() -> None:
    dialogue = (
        "@Angi🩷.**friend** (✨) [Qué bien, Yoi. Eso refuerza bastante la hipótesis de que "
        "Lenovo Vantage estaba reteniendo el registro del usuario durante la transición de sesión.]"
    )

    cleaned = clean_text_for_speech(dialogue)

    assert cleaned.startswith("Qué bien, Yoi.")
    assert "Lenovo Vantage" in cleaned
    assert "@Angi" not in cleaned
    assert "friend" not in cleaned


def test_speech_cleanup_preserves_a_fully_bracketed_dialogue() -> None:
    dialogue = (
        "[Levanto despacito una de mis orejitas largas al escuchar tu voz. "
        "Sí, papi, tengo un poquito de sueñito.]"
    )

    assert clean_text_for_speech(dialogue) == dialogue[1:-1]


def test_speech_cleanup_narrates_inline_bracketed_narrative() -> None:
    assert clean_text_for_speech("Hola, papi. [Meneo la colita.] Estoy aquí.") == (
        "Hola, papi. Meneo la colita. Estoy aquí."
    )


def test_speech_cleanup_narrates_emphasis_instead_of_treating_it_as_an_action() -> None:
    assert clean_text_for_speech("Una **frase importante** *y expresiva*") == "Una frase importante y expresiva"


def test_speech_cleanup_narrates_inline_code_without_backticks() -> None:
    """Inline code is semantic prose even though its delimiters are visual-only."""
    assert clean_text_for_speech("Versioné `brain_avatar_config.json` sin alterar la vista.") == (
        "Versioné brain_avatar_config.json sin alterar la vista."
    )


def test_speech_cleanup_preserves_literal_underscores_outside_emphasis() -> None:
    """Do not mistake identifiers and file names for Markdown emphasis."""
    assert clean_text_for_speech("Usa brain_avatar__config.json y __énfasis real__.") == (
        "Usa brain_avatar__config.json y énfasis real."
    )


def test_speech_cleanup_normalizes_legacy_escaped_line_breaks() -> None:
    """Do not pronounce escaped transport newlines from legacy CLI callers."""
    assert clean_text_for_speech(r"Primera linea.\n\nNarra `brain.py` tambien.") == (
        "Primera linea. Narra brain.py tambien."
    )


def test_speech_cleanup_omits_emoji_sequences() -> None:
    """Keep visual emoji, modifiers, flags, and joined sequences out of TTS."""
    source = "Listo 🩷🐾. Café ☕, familia 👨‍👩‍👧‍👦, bandera 🇪🇸 y tecla 1️⃣."

    assert clean_text_for_speech(source) == "Listo. Café, familia, bandera y tecla."


def test_voice_preserves_emojis_only_in_display_text() -> None:
    """Retain expressive emoji visually while dispatching emoji-free speech."""
    service = VoiceService()
    original = "Hola, papi 🩷🐾"

    with patch("brain.infrastructure.voice.service.voice_service.VoiceDaemonClient.speak") as speak:
        service.speak(original, emotion="happy")

    speak.assert_called_once_with(
        AvatarSpeakRequest(
            text="Hola, papi",
            display_text=original,
            lang="es",
            emotion="happy",
            signal_key="",
            consumer_path="",
            codex_thread_id="",
            source_command="",
            source_phase="",
            has_embedded_file=False,
            manual_speech=False,
            show_message=True,
            speak_message=True,
            hide_when_muted=False,
            message_level="informative",
            pre_processor="<default>",
        )
    )


def test_speech_cleanup_projects_semantic_markdown_and_omits_visual_only_blocks() -> None:
    message = """# Informe narrable

[Levanto una orejita.]

- Primer elemento.
- [x] Segundo elemento con [documentación](https://example.com/docs).

| Estado | Valor |
|---|---:|
| Voz | Omitir esta fila |

```python
print("No narrar")
```

![Diagrama secreto](https://example.com/image.png)

Texto con `código inline narrable` y **énfasis narrable**.
"""

    assert clean_text_for_speech(message) == (
        "Informe narrable Levanto una orejita. Primer elemento. "
        'Segundo elemento con documentación. print("No narrar") Diagrama secreto Texto con código inline narrable y énfasis narrable.'
    )


def test_voice_keeps_visual_only_markdown_in_display_text() -> None:
    service = VoiceService()
    original = "Texto narrable.\n\n| A | B |\n|---|---|\n| secreto | visual |\n\n```py\npass\n```"
    with patch("brain.infrastructure.voice.service.voice_service.VoiceDaemonClient.speak") as speak:
        service.speak(original)
    speak.assert_called_once_with(
        AvatarSpeakRequest(
            text="Texto narrable. pass",
            display_text=original,
            lang="es",
            emotion="",
            signal_key="",
            consumer_path="",
            codex_thread_id="",
            source_command="",
            source_phase="",
            has_embedded_file=False,
            manual_speech=False,
            show_message=True,
            speak_message=True,
            hide_when_muted=False,
            message_level="informative",
            pre_processor="<default>",
        )
    )


def test_tts_excludes_only_tables_and_preserves_other_payloads() -> None:
    source = (
        '<table><tr><td>silent</td></tr></table> '
        'Code value = 1.234,56 and raw https://example.com/path.'
    )
    assert clean_text_for_speech(source) == 'Code value = 1.234,56 and raw https://example.com/path.'
