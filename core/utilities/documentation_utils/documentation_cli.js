#!/usr/bin/env node
/**
 * @author Angi Ichiva
 * @version 2.0.0
 *
 * CLI entrypoint for documentation utilities.
 */

import { parseCliArguments, printHelp } from './src/cli/cli-parser.js';
import { checkDocumentationReferences } from './src/services/reference-check-service.js';
import { generateDocumentationWiki } from './src/services/wiki-generation-service.js';
import { serveDocumentationWiki } from './src/services/static-server-service.js';

/**
 * Execute the documentation utilities CLI.
 *
 * @param {string[]} rawArgs - Process arguments after the script path.
 * @returns {Promise<number>} Exit code.
 */
export async function main(rawArgs) {
    const command = parseCliArguments(rawArgs);

    if (command.mode === 'help') {
        printHelp();
        return 0;
    }

    if (command.mode === 'check') {
        return checkDocumentationReferences(command);
    }

    if (command.mode === 'generate') {
        return generateDocumentationWiki(command);
    }

    if (command.mode === 'serve') {
        const serverInfo = await serveDocumentationWiki(command);
        console.log(`Serving documentation wiki: ${serverInfo.url}`);
        console.log('Press Ctrl+C to stop.');
        await new Promise(() => {});
    }

    return 1;
}

main(process.argv.slice(2)).then(exitCode => {
    if (Number.isInteger(exitCode)) {
        process.exitCode = exitCode;
    }
}).catch(error => {
    console.error(`Error: ${error.message}`);
    process.exitCode = 1;
});
