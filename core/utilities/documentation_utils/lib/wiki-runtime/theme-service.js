/**
 * @author Angi Ichiva
 * @version 2.0.0
 *
 * Handles reader theme switching.
 */

/**
 * Initialize persisted dark/light theme behavior.
 *
 * @returns {void}
 */
export function initializeTheme() {
    const themeToggle = document.getElementById('theme-toggle');
    const sunIcon = document.getElementById('theme-sun');
    const moonIcon = document.getElementById('theme-moon');
    const prismTheme = document.getElementById('prism-theme');
    let currentTheme = localStorage.getItem('wiki-theme') || 'dark';

    document.documentElement.setAttribute('data-theme', currentTheme);
    updateThemeUI({ currentTheme, sunIcon, moonIcon, prismTheme });

    themeToggle?.addEventListener('click', () => {
        currentTheme = currentTheme === 'dark' ? 'light' : 'dark';
        document.documentElement.setAttribute('data-theme', currentTheme);
        localStorage.setItem('wiki-theme', currentTheme);
        updateThemeUI({ currentTheme, sunIcon, moonIcon, prismTheme });
    });
}

/**
 * Update icon and Prism theme state.
 *
 * @param {object} params - UI parameters.
 * @param {string} params.currentTheme - Active theme.
 * @param {HTMLElement|null} params.sunIcon - Sun icon.
 * @param {HTMLElement|null} params.moonIcon - Moon icon.
 * @param {HTMLLinkElement|null} params.prismTheme - Prism theme link.
 * @returns {void}
 */
function updateThemeUI({ currentTheme, sunIcon, moonIcon, prismTheme }) {
    const currentHref = prismTheme?.getAttribute('href') || '';

    if (currentTheme === 'dark') {
        if (sunIcon) sunIcon.style.display = 'block';
        if (moonIcon) moonIcon.style.display = 'none';
        prismTheme?.setAttribute('href', currentHref.replace('prism.min.css', 'prism-tomorrow.min.css'));
        return;
    }

    if (sunIcon) sunIcon.style.display = 'none';
    if (moonIcon) moonIcon.style.display = 'block';
    prismTheme?.setAttribute('href', currentHref.replace('prism-tomorrow.min.css', 'prism.min.css'));
}
