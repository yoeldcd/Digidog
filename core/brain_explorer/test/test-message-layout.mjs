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
const appShellSource = await readFile(new URL("../src/presentation/shell/layouts/app-shell.ts", import.meta.url), "utf8");

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
    /expanded[\s\S]*data-message-control="collapse"[\s\S]*data-action="collapse-message"[\s\S]*icon\("chevronDown"\)/,
    "Expanded messages must expose a dedicated leading chevron to collapse details."
);
assert.match(
    viewSource,
    /voice-message-leading-action[\s\S]*data-message-control="audio"/,
    "Collapsed messages must retain their dedicated audio control."
);
assert.match(
    viewSource,
    /dataset\.messageControl !== desiredChild\.dataset\.messageControl[\s\S]*replaceWith/,
    "Closing a message must replace its chevron node with the retained audio control."
);
assert.match(
    viewSource,
    /data-action="expand-message"/,
    "Collapsed message summaries must remain the explicit expansion control."
);
assert.match(
    viewSource,
    /action\?\.dataset\.action === "expand-message" \|\| action\?\.dataset\.action === "collapse-message"/,
    "Only explicit expand or collapse controls may toggle a message card."
);
assert.doesNotMatch(
    viewSource,
    /closest<HTMLElement>\("\.voice-message-item"\)[\s\S]{0,90}#toggleExpandedMessage/,
    "Clicks in message content must not toggle the card."
);
assert.match(
    viewSource,
    /getVoiceStatus[\s\S]*activeSpeakId[\s\S]*serviceState/,
    "Play and Pause state must come from daemon status polling."
);
assert.match(viewSource, /response\.data\?\.playbackActive === true/, "Message playback state must use the daemon's explicit audible contract.");
assert.match(appShellSource, /#playLatestVoice\(\)[\s\S]*replayVoiceMessage\(\)/, "The shell replay action must use the shared daemon queue.");
assert.doesNotMatch(appShellSource, /new Audio\(\`\/api\/voice\/latest/, "The shell must not bypass daemon playback state with private HTML audio.");
assert.doesNotMatch(viewSource, /setTimeout\([^\n]+750\)/, "Idle voice status must not poll every 750 ms.");
assert.match(viewSource, /VOICE_STATUS_ACTIVE_INTERVAL_MS\s*=\s*1_500/, "Active playback may use a responsive status interval.");
assert.match(viewSource, /VOICE_STATUS_IDLE_INTERVAL_MS\s*=\s*10_000/, "Idle playback must back off status polling.");
assert.match(viewSource, /VOICE_STATUS_HIDDEN_INTERVAL_MS\s*=\s*60_000/, "Hidden layouts must nearly suspend status polling.");
assert.match(viewSource, /statusPollInFlight/, "Voice status synchronization must reject overlapping requests.");
assert.match(viewSource, /visibilitychange/, "Voice status must resynchronize when the document becomes visible.");
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
assert.match(styles, /voice-message-collapse-action > \.svg-icon \{ transform: rotate\(180deg\); \}/, "The collapse chevron must point upward.");
assert.match(styles, /voice-message-preview[\s\S]*font-size:\s*17px/, "Preview text must use the enlarged content size.");
assert.match(styles, /voice-message-markdown[^{]*\{[^}]*font-size:\s*17px/, "Expanded content must use the enlarged size.");
assert.match(styles, /voice-speak-status[\s\S]*font-size:\s*13px/, "Classification labels must use the enlarged size.");
assert.match(styles, /voice-message-time[\s\S]*font-size:\s*14px/, "Message times must use the enlarged size.");
assert.match(
    viewSource,
    /container\.scrollTop [+-]=/,
    "Expanded messages must remain focused inside the message viewport."
);
assert.match(viewSource, /this\.#expandedIds\.clear\(\)/, "Only one message may remain expanded.");
assert.match(
    viewSource,
    /Date\.parse\(left\.created_at\)[\s\S]*Date\.parse\(right\.created_at\)[\s\S]*right\.id\.localeCompare\(left\.id\)/,
    "Messages must be ordered by absolute timestamp newest-first with a stable tie-breaker."
);
assert.match(viewSource, /const latestMessage = this\.#history\[0\]/, "Initial focus must target the first, newest chronological message.");
assert.match(viewSource, /article === container\.firstElementChild[\s\S]*container\.scrollTop = 0/, "The newest expanded message must remain aligned to the top.");
assert.match(
    viewSource,
    /focusLatestId[\s\S]*requestAnimationFrame\(\(\) => this\.#focusMessage\(focusLatestId, true\)\)/,
    "The newest message must receive expansion and viewport focus after reconciliation."
);
assert.match(
    viewSource,
    /#refreshMessageList\(\)[\s\S]*existingItems[\s\S]*#patchElement/,
    "Background refreshes must reconcile keyed cards instead of replacing the list."
);
assert.doesNotMatch(viewSource, /container\.innerHTML\s*=\s*this\.#renderMessages/, "Polling must not replace the message-list composition.");
assert.doesNotMatch(viewSource, /if \(!silent\)\s*\{[\s\S]{0,100}this\.#render\(\)/, "Manual refresh must not replace the complete Messages composition.");
assert.match(viewSource, /dataset\.eventsBound[\s\S]*#handleMessageListClick/, "Message interactions must use one stable delegated listener.");
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
assert.match(viewSource, /rename-session[\s\S]*autoname-session/, "Sessions must expose Rename and Autoname actions.");
assert.match(viewSource, /message-session-name-dialog[\s\S]*session-name-input/, "Session naming must use a custom prompt dialog.");
assert.match(viewSource, /Generating a concise proposal/, "Autoname must expose a visible waiting state.");
assert.match(viewSource, /slice\(0, 17\)[\s\S]*\.\.\./, "Session labels must be visibly limited to twenty characters.");
assert.match(viewSource, /title:\s*session\.chatId \? session\.label/, "Abbreviated sessions must retain their complete hover title.");
assert.match(styles, /message-session-name-dialog[^{]*\{[^}]*50dvw/, "The naming dialog must use the requested responsive 50dvw basis.");
assert.match(styles, /message-session-name-dialog::backdrop/, "The naming dialog must integrate with the Explorer modal treatment.");
assert.doesNotMatch(styles, /voice-message-item\.is-expanded\s*\{[^}]*surface-selected/s, "Expanded messages must not impersonate the playing state.");
assert.match(viewSource, /name && name === this\.#playingName \? "is-playing"/, "Messages without audio names must never impersonate playback.");

console.log("message layout contract passed");
