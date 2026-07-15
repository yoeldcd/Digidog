/**
 * @author Angi Ichiva
 * @version 2.0.0
 *
 * Parses public CLI commands for documentation utilities.
 */

import path from 'path';

import { getLogSuperdomain } from '../utils/text-utils.js';

const VALID_COMMANDS = new Set(['generate', 'check', 'serve', 'help', '--help', '-h']);

/**
 * Print CLI usage details.
 *
 * @returns {void}
 */
export function printHelp() {
    console.log(`
Documentation Utils

Usage:
  node documentation_cli.js generate <Path_documentation> [--log-domain <domain>]
  node documentation_cli.js check <Path_documentation> [--log-domain <domain>]
  node documentation_cli.js serve <Path_documentation> [--host 127.0.0.1] [--port 4173]
`);
}

/**
 * Parse command-line arguments into a normalized command DTO.
 *
 * @param {string[]} rawArgs - Process arguments after the script path.
 * @returns {import('../models/wiki-models.js').CliCommandDTO} Parsed command.
 */
export function parseCliArguments(rawArgs) {
    const mode = rawArgs[0] || 'help';

    if (!VALID_COMMANDS.has(mode)) {
        throw new Error(`Unknown command: ${mode}`);
    }

    if (mode === 'help' || mode === '--help' || mode === '-h') {
        return { mode: 'help' };
    }

    const argsAfterMode = rawArgs.slice(1);
    const positionalArgs = [];
    const options = {
        logDomain: null,
        host: '127.0.0.1',
        port: 4173
    };

    for (let index = 0; index < argsAfterMode.length; index += 1) {
        const arg = argsAfterMode[index];

        if (arg === '--log-domain') {
            options.logDomain = readOptionValue(argsAfterMode, index, '--log-domain');
            index += 1;
            continue;
        }

        if (arg.startsWith('--log-domain=')) {
            options.logDomain = arg.slice('--log-domain='.length);
            continue;
        }

        if (arg === '--host') {
            options.host = readOptionValue(argsAfterMode, index, '--host');
            index += 1;
            continue;
        }

        if (arg.startsWith('--host=')) {
            options.host = arg.slice('--host='.length);
            continue;
        }

        if (arg === '--port') {
            options.port = Number.parseInt(readOptionValue(argsAfterMode, index, '--port'), 10);
            index += 1;
            continue;
        }

        if (arg.startsWith('--port=')) {
            options.port = Number.parseInt(arg.slice('--port='.length), 10);
            continue;
        }

        if (arg.startsWith('--')) {
            throw new Error(`Unknown option for ${mode}: ${arg}`);
        }

        positionalArgs.push(arg);
    }

    validateModeArguments({ mode, positionalArgs, options });

    return {
        mode,
        documentationPath: path.resolve(positionalArgs[0]),
        logDomain: options.logDomain ? getLogSuperdomain(options.logDomain) : null,
        host: options.host,
        port: options.port
    };
}

/**
 * Read an option value from the argument list.
 *
 * @param {string[]} args - Argument array.
 * @param {number} index - Current option index.
 * @param {string} optionName - Option name for diagnostics.
 * @returns {string} Option value.
 */
function readOptionValue(args, index, optionName) {
    const value = args[index + 1];

    if (!value || value.startsWith('--')) {
        throw new Error(`${optionName} requires a value.`);
    }

    return value;
}

/**
 * Validate command-specific positional and option contracts.
 *
 * @param {object} params - Validation parameters.
 * @param {string} params.mode - Command mode.
 * @param {string[]} params.positionalArgs - Positional arguments.
 * @param {object} params.options - Parsed option values.
 * @returns {void}
 */
function validateModeArguments({ mode, positionalArgs, options }) {
    if (positionalArgs.length !== 1) {
        throw new Error(`${mode} requires exactly one <Path_documentation> argument.`);
    }

    if ((mode === 'generate' || mode === 'check') && !validateOptionalDomain(options.logDomain)) {
        throw new Error('--log-domain requires a non-empty domain value.');
    }

    if (mode === 'serve' && !Number.isInteger(options.port)) {
        throw new Error('--port requires an integer value.');
    }

    if (mode === 'serve' && (options.port < 0 || options.port > 65535)) {
        throw new Error('--port must be between 0 and 65535.');
    }
}

/**
 * Validate optional log-domain values.
 *
 * @param {string|null} value - Candidate domain.
 * @returns {boolean} True when absent or valid.
 */
function validateOptionalDomain(value) {
    return value === null || String(value).trim().length > 0;
}
