# Avatar presentation packages

The avatar presentation is split by ownership instead of toolkit prefixes:

- `window/` owns backend selection, configuration, the executable entrypoint,
  and native window priority.
- `qt/` owns the PySide6 window, painted controls, and Markdown bubble.
- `tk/` owns the Tk fallback window and its animated GIF renderer.
- `interactivity/` owns toolkit-neutral dialogue, emotion, and reaction rules.

Dependency direction is `window -> qt|tk -> interactivity`. Toolkit packages may
read shared window configuration, but neither toolkit imports the other.
