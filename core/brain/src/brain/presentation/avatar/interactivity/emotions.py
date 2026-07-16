# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Extensible avatar emotion names and their conversational emoji."""

EMOTION_EMOJIS = {
    "happy": "😊", "sad": "😢", "angry": "😠", "excited": "🤩", "exited": "👋",
    "hot": "🥵", "wondered": "🤔", "curious": "🧐", "thinking": "💭", "love": "😍",
    "loved": "🥰", "shy": "☺️", "playful": "😜", "calm": "😌", "proud": "😼",
    "surprised": "😲", "confused": "😕", "sleepy": "😴", "tired": "🥱", "focused": "🎯",
    "determined": "💪", "hopeful": "🌤️", "grateful": "🙏", "joyful": "😄", "cheerful": "😁",
    "giggly": "🤭", "mischievous": "😈", "nervous": "😬", "afraid": "😨", "scared": "😱",
    "brave": "🦸", "confident": "😎", "relaxed": "🧘", "peaceful": "🕊️", "serious": "😐",
    "skeptical": "🤨", "annoyed": "🙄", "frustrated": "😤", "embarrassed": "😳", "blushing": "😊",
    "lonely": "🥺", "nostalgic": "🕰️", "inspired": "💡", "creative": "🎨", "celebrating": "🎉",
    "dancing": "💃", "singing": "🎶", "listening": "👂", "speaking": "🗣️", "awaiting": "⏳",
    "greeting": "🙋", "waving": "👋", "winking": "😉", "teasing": "😏", "caring": "🤗",
    "gentle": "🌸", "tender": "🫶", "protective": "🛡️", "supportive": "🤝", "encouraging": "📣",
    "amazed": "😮", "astonished": "🤯", "dreamy": "💫", "bored": "🥱", "impatient": "⌛",
    "alert": "🚨", "energetic": "⚡", "soft": "🪶", "silly": "🤪", "sassy": "💅",
    "dramatic": "🎭", "adoring": "🤩", "melancholic": "🌧️", "optimistic": "🌈", "pessimistic": "🌫️",
    "relieved": "😮‍💨", "content": "🙂", "delighted": "😃", "eager": "🐾", "interested": "👀",
    "observant": "🔎", "puzzled": "🧩", "doubtful": "🫤", "shocked": "😧", "flustered": "🫣",
    "jealous": "😒", "apologetic": "🙇", "forgiving": "💞", "trusting": "🤍", "suspicious": "🕵️",
    "devoted": "🩷", "friendly": "🐶", "helpful": "🧰", "working": "🛠️", "coding": "💻",
    "debugging": "🐛", "learning": "📚", "remembering": "🧠", "reflecting": "🪞", "radiant": "✨",
}

assert len(EMOTION_EMOJIS) == 100


def emotion_emoji(emotion: str) -> str:
    """Return a representative emoji, defaulting unknown states to happy."""
    return EMOTION_EMOJIS.get((emotion or "happy").lower(), EMOTION_EMOJIS["happy"])
