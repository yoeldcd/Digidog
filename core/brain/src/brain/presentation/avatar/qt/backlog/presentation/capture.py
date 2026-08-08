"""Desktop capture adapter isolated behind the task-manager capture port."""
from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QCoreApplication, QThread
from PySide6.QtGui import QGuiApplication, QPixmap, QScreen
from PySide6.QtWidgets import QApplication, QWidget


class QtScreenCapture:
    """Capture the desktop through an injected or primary Qt screen."""

    def __init__(
        self,
        screen_provider: Callable[[], QScreen | None] | None = None,
        settle_windows: Callable[[], None] | None = None,
        post_restore_settle: Callable[[], None] | None = None,
        restore_delay_ms: int = 350,
        sleep_ms: Callable[[int], None] | None = None,
    ) -> None:
        """Configure injectable screen, compositor, and restoration collaborators.

        Args:
            screen_provider: Callable returning the screen to capture.
            settle_windows: Callable that waits until hidden overlays disappear.
            post_restore_settle: Callable that lets restored windows settle.
            restore_delay_ms: Additional compositor delay after restoration.
            sleep_ms: Sleep function injected for deterministic tests.
        """
        self._screen_provider = screen_provider or QGuiApplication.primaryScreen
        self._settle_windows = settle_windows or self._default_settle_windows
        self._post_restore_settle = post_restore_settle or self._default_post_restore_settle
        self._restore_delay_ms = max(0, int(restore_delay_ms))
        self._sleep_ms = sleep_ms or QThread.msleep

    def capture(self) -> QPixmap:
        """Capture a clean desktop frame and restore Qt windows transactionally.

        The post-restore settle runs only after every hidden window is visible
        again. Its compositor delay prevents translucent avatar/backlog surfaces
        from leaving a stale trace in the next frame while keeping the capture
        itself free of this process's windows.

        Returns:
            QPixmap: Captured desktop image, or a null pixmap when no screen exists.
        """
        visible_windows = self._visible_top_levels()
        active_window = QApplication.activeWindow()
        capture_error: BaseException | None = None
        for window in visible_windows:
            window.hide()
        try:
            self._settle_windows()
            screen = self._screen_provider()
            return QPixmap() if screen is None else screen.grabWindow(0)
        except BaseException as error:
            capture_error = error
            raise
        finally:
            for window in visible_windows:
                window.show()
            if active_window in visible_windows:
                active_window.raise_()
                active_window.activateWindow()
            try:
                self._post_restore_settle()
            except BaseException:
                # Preserve the original capture/settle failure while still
                # surfacing a restoration failure on an otherwise successful
                # capture.
                if capture_error is None:
                    raise

    def _default_post_restore_settle(self) -> None:
        """Allow the compositor to retire hidden translucent surfaces.

        Returns:
            None.
        """
        QCoreApplication.processEvents()
        if self._restore_delay_ms:
            self._sleep_ms(self._restore_delay_ms)
        QCoreApplication.processEvents()

    @staticmethod
    def _visible_top_levels() -> tuple[QWidget, ...]:
        """Return visible top-level widgets that must be hidden for capture.

        Returns:
            tuple[QWidget, ...]: Visible windows belonging to the Qt application.
        """
        app = QApplication.instance()
        if app is None:
            return ()
        return tuple(window for window in app.topLevelWidgets() if window.isVisible())

    @staticmethod
    def _default_settle_windows() -> None:
        """Wait for hidden native surfaces to leave the compositor frame.

        Returns:
            None.
        """
        QCoreApplication.processEvents()
        # Let the Windows compositor fully retire hidden translucent surfaces.
        QThread.msleep(300)
        QCoreApplication.processEvents()
