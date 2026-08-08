# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Qt avatar movie loading, scaling, and animation projection."""
from __future__ import annotations

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QMovie, QPixmap

from brain.presentation.avatar.window.config import avatar_asset


def fit_avatar_frame(frame: QPixmap, available: QSize) -> QPixmap:
    """Scale an avatar GIF canvas without per-frame alpha cropping.

    Args:
        frame (QPixmap): Current GIF canvas.
        available (QSize): Available target viewport.

    Returns:
        QPixmap: Aspect-preserving scaled frame.
    """
    if frame.isNull():
        return frame
    # GIF frames share one logical canvas. Cropping each alpha mask independently
    # makes the character pulse as the occupied pixels change between frames.
    return frame.scaled(available, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)


class QtAvatarRendererMixin:
    """Mixin managing avatar animation assets, frame scaling, and state transitions."""

    def _animation_for_state(
        self,
        state: str,
        emotion: str,
        speaking_active: bool | None = None,
    ) -> tuple[str, str]:
        """Select speaking visuals only while shared playback state is audible.

        Args:
            state (str): Current avatar state identifier.
            emotion (str): Emotion animation identifier.
            speaking_active (bool | None): Whether speech playback is currently active.

        Returns:
            tuple[str, str]: Primary animation name and fallback state.
        """
        audible = state == "speaking" if speaking_active is None else speaking_active
        if audible:
            return emotion or "speaking", "speaking"
        if state == "working":
            return "working", "awaiting"
        if state in {"awaiting", "thinking", "preparing", "speaking", "muted", "muted_replay"}:
            return self.awaiting_quota_animation or "awaiting", "awaiting"
        return state, "speaking"

    def _set_state(
        self,
        state: str,
        force: bool = False,
        emotion: str = "",
        processing: bool | None = None,
        processing_emotion: str = "",
        speaking_active: bool | None = None,
    ) -> None:
        """Apply avatar animation and processing chrome as one atomic state.

        Args:
            state (str): Requested avatar state name.
            force (bool): Whether to force asset reloading even if unchanged.
            emotion (str): Emotion animation identifier.
            processing (bool | None): Whether background processing is active.
            processing_emotion (str): Emotion active during background processing.
            speaking_active (bool | None): Whether speech audio is currently playing.

        Returns:
            None.
        """
        changed = state != self.state or emotion != self.emotion
        self.state, self.emotion = state, emotion

        if state in {"preparing", "speaking"}:
            self.show()

        self._apply_topmost()
        animation, fallback = self._animation_for_state(state, emotion, speaking_active)
        path = avatar_asset(animation, fallback_state=fallback)

        if (changed or force) and path.is_file() and str(path) != self.current_asset:
            if self.movie:
                self.movie.stop()
            self.movie = QMovie(str(path))
            self.movie.setCacheMode(QMovie.CacheMode.CacheNone)
            self.movie.frameChanged.connect(self._render_movie_frame)
            self.movie.start()
            self.current_asset = str(path)

        self.controls.set_state(
            self.active_presentation_owned,
            self.controls.mute_mode,
        )
        processing_active = bool(processing)
        self.controls.set_processing(processing_active, processing_emotion)

    def _render_movie_frame(self, *_args) -> None:
        """Render current GIF frame scaled into the avatar label bounds.

        Args:
            *_args: Ignored Qt frameChanged signal arguments.

        Returns:
            None.
        """
        if self.movie:
            available = QSize(max(1, self.width()), max(1, self.height() - 36))
            self.avatar.setPixmap(fit_avatar_frame(self.movie.currentPixmap(), available))

