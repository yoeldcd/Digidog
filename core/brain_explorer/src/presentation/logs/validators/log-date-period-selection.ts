/**
 * Inclusive date range represented by one temporal Logs tree node.
 */
export interface LogDatePeriodSelection {
    /**
     * First date in `DD-MM-YYYY` format.
     * @type {string}
     */
    from: string;
    /**
     * Final date in `DD-MM-YYYY` format.
     * @type {string}
     */
    to: string;
    /**
     * Human-readable period label for the content header.
     * @type {string}
     */
    label: string;
}

const MONTH_LABELS = ["", "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"] as const;

/**
 * Convert a year, month, or day tree path into the CLI date-range contract.
 *
 * @param {string} path Synthetic path emitted by the temporal tree.
 * @returns {LogDatePeriodSelection | null} Inclusive period boundaries, or null for non-period nodes.
 */
export function logDatePeriodSelection(path: string): LogDatePeriodSelection | null {
    const match = String(path).match(/^logs-date:(\d{4})(?:-(\d{2}))?(?:-(\d{2}))?$/);
    if (!match) return null;
    const year = Number(match[1]);
    const month = match[2] ? Number(match[2]) : null;
    const day = match[3] ? Number(match[3]) : null;
    if (!Number.isInteger(year) || year < 1 || (month !== null && (month < 1 || month > 12))) return null;
    if (day !== null) {
        const lastDay = new Date(year, month ?? 0, 0).getDate();
        if (day < 1 || day > lastDay || month === null) return null;
        const date = formatDate(day, month, year);
        return { from: date, to: date, label: `${String(day).padStart(2, "0")} ${MONTH_LABELS[month]} ${year}` };
    }
    if (month !== null) {
        return { from: formatDate(1, month, year), to: formatDate(new Date(year, month, 0).getDate(), month, year), label: `${MONTH_LABELS[month]} ${year}` };
    }
    return { from: formatDate(1, 1, year), to: formatDate(31, 12, year), label: String(year) };
}

/**
 * Format one calendar date for the Brain CLI.
 * @param {number} day One-based day of month.
 * @param {number} month One-based month.
 * @param {number} year Four-digit year.
 * @returns {string} Date formatted as `DD-MM-YYYY`.
 */
function formatDate(day: number, month: number, year: number): string {
    return `${String(day).padStart(2, "0")}-${String(month).padStart(2, "0")}-${year}`;
}
