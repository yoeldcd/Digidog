/**
 * @author Yoel David <yoeldcd@gmail.com>
 * @see https://x.com/SAY6267
 */

import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";

const viewSource = await readFile(
    new URL("../src/presentation/messages/layouts/messages-view.ts", import.meta.url),
    "utf8"
);
const styles = await readFile(new URL("../src/styles/views.css", import.meta.url), "utf8");

assert.match(
    viewSource,
    /class="structure-layout messages-structure"/,
    "Messages must use the shared full-height master-detail layout."
);
assert.match(
    viewSource,
    /<brain-structure-tree data-role="message-session-tree"><\/brain-structure-tree>/,
    "Messages must render sessions with the shared StructureTree web component."
);
assert.match(
    viewSource,
    /tree\.model\s*=\s*\{/,
    "Messages must configure the shared tree through its public model contract."
);
assert.doesNotMatch(
    viewSource,
    /message-session-browser|message-tree-level/,
    "Messages must not restore a private card or duplicate tree implementation."
);
assert.doesNotMatch(
    styles,
    /\.message-session-browser|\.message-tree-level/,
    "Messages must inherit the shared sidepanel styles."
);
assert.match(
    viewSource,
    /voice-speak-status[\s\S]*voice-message-time/,
    "Every message summary must order classification before time."
);
assert.match(
    styles,
    /grid-template-columns:\s*minmax\(0, 1fr\) minmax\(132px, 180px\) 64px/,
    "Message summaries must share fixed classification and time columns."
);
assert.match(
    viewSource,
    /voice-message-leading-action[\s\S]*data-action="play-message"/,
    "The leading message-list control must replay retained audio."
);
assert.match(
    viewSource,
    /expanded[\s\S]*voice-message-leading-placeholder[\s\S]*renderLeadingAudioAction/,
    "Expanded messages must keep the metadata grid while hiding the duplicate leading playback action."
);
assert.match(
    viewSource,
    /getVoiceStatus[\s\S]*activeSpeakId[\s\S]*serviceState/,
    "Play and Pause state must come from daemon status polling."
);
assert.match(
    viewSource,
    /voice-message-leading-action[\s\S]*data-action="generate-message-audio"/,
    "The leading message-list control must generate missing audio."
);
assert.doesNotMatch(
    viewSource,
    /icon\(expanded \? "chevronDown" : "chevronRight"\)/,
    "Message rows must not retain the decorative expansion chevron."
);
assert.match(
    styles,
    /voice-message-summary[\s\S]*width:\s*100%/,
    "Expanded summaries must retain the full metadata grid width."
);
assert.match(styles, /voice-message-preview[\s\S]*font-size:\s*17px/, "Preview text must use the enlarged content size.");
assert.match(styles, /voice-message-markdown[^{]*\{[^}]*font-size:\s*17px/, "Expanded content must use the enlarged size.");
assert.match(styles, /voice-speak-status[\s\S]*font-size:\s*13px/, "Classification labels must use the enlarged size.");
assert.match(styles, /voice-message-time[\s\S]*font-size:\s*14px/, "Message times must use the enlarged size.");
assert.match(
    viewSource,
    /container\.scrollTop [+-]=/,
    "Expanded messages must remain focused inside the message viewport."
);
assert.match(
    viewSource,
    /data-action="generate-message-audio"/,
    "Historical messages without retained audio must expose audio generation."
);
assert.match(
    viewSource,
    /generatedAudioSpeakIds[\s\S]*waitForGeneratedAudio/,
    "Generated historical audio must become a retained download control."
);

console.log("message layout contract passed");
