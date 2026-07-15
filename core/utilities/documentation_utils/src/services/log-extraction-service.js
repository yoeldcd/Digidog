/**
 * @author Angi Ichiva
 * @version 2.0.0
 *
 * Extracts workspace logs for the generated logs.html virtual page.
 */

import fs from 'fs';
import path from 'path';
import { execFileSync } from 'child_process';

import { domainsMatch, getLogSuperdomain } from '../utils/text-utils.js';

/**
 * Build the markdown source for the generated logs page.
 *
 * @param {object} params - Log build parameters.
 * @param {string|null} params.agentDir - Agent workspace directory.
 * @param {string} params.projectName - Resolved project name.
 * @param {string|null} params.logDomain - Explicit log domain.
 * @param {string|null} [params.logDate] - Optional exact log date filter.
 * @param {string|null} [params.logTime] - Optional exact log time filter.
 * @param {string|null} [params.logFrom] - Optional inclusive lower date/timestamp bound.
 * @param {string|null} [params.logTo] - Optional inclusive upper date/timestamp bound.
 * @returns {string} Logs markdown.
 */
export function buildLogsMarkdown({ agentDir, projectName, logDomain, logDate = null, logTime = null, logFrom = null, logTo = null }) {
    const activeLogDomain = logDomain || projectName;
    const exactMatch = Boolean(logDomain);

    if (!agentDir) {
        return `# Agent Tech Logs for ${activeLogDomain}\n\nNo agent workspace was found.\n`;
    }

    const brainLogs = exportLogsFromBrain({ agentDir, activeLogDomain, logDate, logTime, logFrom, logTo });
    if (brainLogs) {
        return brainLogs;
    }

    const logsDir = path.join(agentDir, 'logs');
    const logFiles = collectLogFiles(logsDir);
    let combinedLogs = `# Agent Tech Logs for ${activeLogDomain}\n\n`;
    let hasLogs = false;

    logFiles.sort().reverse().forEach(logFile => {
        const logContent = fs.readFileSync(logFile, 'utf8');
        const domainLogs = extractDomainLogs(logContent, activeLogDomain, { exactMatch });

        if (!domainLogs) return;

        hasLogs = true;
        combinedLogs += `\n## ${logDateLabel(logFile)}\n\n${domainLogs}\n`;
    });

    if (!hasLogs) {
        combinedLogs += 'No matching log entries were found.\n';
    }

    return combinedLogs;
}

/**
 * Export logs through the workspace brain CLI when available.
 *
 * @param {object} params - Export parameters.
 * @param {string} params.agentDir - Agent workspace directory.
 * @param {string} params.activeLogDomain - Domain prefix to export.
 * @param {string|null} params.logDate - Optional exact log date filter.
 * @param {string|null} params.logTime - Optional exact log time filter.
 * @param {string|null} params.logFrom - Optional inclusive lower date/timestamp bound.
 * @param {string|null} params.logTo - Optional inclusive upper date/timestamp bound.
 * @returns {string|null} Exported Markdown or null when unavailable.
 */
function exportLogsFromBrain({ agentDir, activeLogDomain, logDate, logTime, logFrom, logTo }) {
    const brainScript = path.join(agentDir, 'scripts', 'brain.py');
    if (!fs.existsSync(brainScript)) return null;

    const workspaceRoot = path.dirname(agentDir);
    const commandArgs = [brainScript, ...buildBrainExportCommandArgs({
        activeLogDomain,
        logDate,
        logTime,
        logFrom,
        logTo
    })];
    const launchers = process.platform === 'win32' ? ['py', 'python'] : ['python3', 'python'];

    for (const launcher of launchers) {
        try {
            const output = execFileSync(launcher, commandArgs, {
                cwd: workspaceRoot,
                encoding: 'utf8',
                stdio: ['ignore', 'pipe', 'ignore'],
                timeout: 30000
            });
            if (output.trim()) return output;
        } catch {
            // Fall back to the next launcher, then to file extraction.
        }
    }

    return null;
}

/**
 * Build the silent Brain argument vector used by wiki generation.
 *
 * `--no-speak` is a parser-owned runtime flag and must precede the command.
 *
 * @param {object} params - Export parameters.
 * @param {string} params.activeLogDomain - Domain prefix to export.
 * @param {string|null} params.logDate - Optional exact log date filter.
 * @param {string|null} params.logTime - Optional exact log time filter.
 * @param {string|null} params.logFrom - Optional inclusive lower bound.
 * @param {string|null} params.logTo - Optional inclusive upper bound.
 * @returns {string[]} Brain CLI arguments excluding the Python script path.
 */
export function buildBrainExportCommandArgs({ activeLogDomain, logDate, logTime, logFrom, logTo }) {
    const commandArgs = ['--no-speak', 'export-logs', '--domain', activeLogDomain];
    appendOptionalFilter(commandArgs, '--date', logDate);
    appendOptionalFilter(commandArgs, '--time', logTime);
    appendOptionalFilter(commandArgs, '--from', logFrom);
    appendOptionalFilter(commandArgs, '--to', logTo);
    return commandArgs;
}

/**
 * Append an optional CLI filter argument.
 *
 * @param {string[]} commandArgs - Mutable argument list.
 * @param {string} flag - CLI flag.
 * @param {string|null} value - Optional flag value.
 * @returns {void}
 */
function appendOptionalFilter(commandArgs, flag, value) {
    if (!value) return;
    commandArgs.push(flag, value);
}

/**
 * Collect log files recursively.
 *
 * @param {string} dir - Logs directory.
 * @returns {string[]} Absolute log file paths.
 */
function collectLogFiles(dir) {
    if (!fs.existsSync(dir)) return [];

    const results = [];
    const entries = fs.readdirSync(dir, { withFileTypes: true });

    entries.forEach(entry => {
        const fullPath = path.join(dir, entry.name);

        if (entry.isDirectory()) {
            results.push(...collectLogFiles(fullPath));
            return;
        }

        if (entry.isFile() && (fullPath.endsWith('.log') || fullPath.endsWith('.log.md'))) {
            results.push(fullPath);
        }
    });

    return results;
}

/**
 * Return a human-readable log date label for fallback file extraction.
 *
 * @param {string} logFile - Absolute log file path.
 * @returns {string} Date label.
 */
function logDateLabel(logFile) {
    return path.basename(logFile).replace(/\.log\.md$|\.log$/u, '');
}

/**
 * Extract matching domain logs from one log file.
 *
 * @param {string} logContent - Raw log file content.
 * @param {string} domain - Target superdomain.
 * @param {object} options - Extraction options.
 * @param {boolean} options.exactMatch - Use exact superdomain matching.
 * @returns {string|null} Extracted markdown.
 */
function extractDomainLogs(logContent, domain, options) {
    const lines = logContent.split('\n');
    let currentEntryHeader = null;
    let currentEntryLines = [];
    let isTargetDomain = false;
    const extractedLogs = [];

    lines.forEach(line => {
        if (line.startsWith('## ')) {
            flushCurrentEntry({ extractedLogs, currentEntryHeader, currentEntryLines, isTargetDomain });
            currentEntryHeader = line;
            currentEntryLines = [];
            isTargetDomain = false;
            return;
        }

        if (line.startsWith('### (')) {
            const match = line.match(/^###\s*\(([^)]+)\)/);
            const entryDomain = match ? getLogSuperdomain(match[1]) : '';
            isTargetDomain = logDomainsMatch(entryDomain, domain, options.exactMatch);
        }

        if (currentEntryHeader) {
            currentEntryLines.push(line);
        }
    });

    flushCurrentEntry({ extractedLogs, currentEntryHeader, currentEntryLines, isTargetDomain });
    return extractedLogs.length > 0 ? extractedLogs.join('\n') : null;
}

/**
 * Append the current parsed log entry when it matches.
 *
 * @param {object} params - Flush parameters.
 * @param {string[]} params.extractedLogs - Output lines.
 * @param {string|null} params.currentEntryHeader - Current entry header.
 * @param {string[]} params.currentEntryLines - Current entry body.
 * @param {boolean} params.isTargetDomain - Match state.
 * @returns {void}
 */
function flushCurrentEntry({ extractedLogs, currentEntryHeader, currentEntryLines, isTargetDomain }) {
    if (isTargetDomain && currentEntryHeader && currentEntryLines.length > 0) {
        extractedLogs.push(currentEntryHeader);
        extractedLogs.push(currentEntryLines.join('\n'));
    }
}

/**
 * Match one log domain against the selected target.
 *
 * @param {string} entryDomain - Log entry superdomain.
 * @param {string} targetDomain - Selected domain.
 * @param {boolean} exactMatch - Use exact matching.
 * @returns {boolean} True when matched.
 */
function logDomainsMatch(entryDomain, targetDomain, exactMatch) {
    if (exactMatch) {
        return getLogSuperdomain(entryDomain).toLowerCase() === getLogSuperdomain(targetDomain).toLowerCase();
    }

    return domainsMatch(targetDomain, entryDomain);
}
