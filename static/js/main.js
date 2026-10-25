// main.js - جبهه نوجوانی

function initActiveNav() {
    const currentPage = typeof window.resolveNavKey === 'function'
        ? window.resolveNavKey(window.location.pathname)
        : document.body.dataset.page;
    const navLinks = document.querySelectorAll('.nav-item[data-nav]');

    navLinks.forEach((link) => {
        const isActive = link.dataset.nav === currentPage;
        link.classList.toggle('active', isActive);
        if (isActive) {
            link.setAttribute('aria-current', 'page');
        } else {
            link.removeAttribute('aria-current');
        }
    });
}

function initSmoothScroll() {
    document.querySelectorAll('a[href^="#"]').forEach((anchor) => {
        anchor.addEventListener('click', function (event) {
            const targetSelector = this.getAttribute('href');
            if (!targetSelector || targetSelector === '#') {
                return;
            }

            const target = document.querySelector(targetSelector);
            if (!target) {
                return;
            }

            event.preventDefault();
            target.scrollIntoView({
                behavior: 'smooth',
                block: 'start'
            });
        });
    });
}

function initGlobalRevealAnimations() {
    const contentRoot = document.getElementById('site-content');
    if (!contentRoot) return;

    const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    const revealSelectors = [
        '.hero-content',
        '.feature-item',
        '.step',
        '.profile-header',
        '.leaderboard-item',
        '.learning-hero',
        '.hero-stat',
        '.stage-card',
        '.stage-hero',
        '.stage-meta-card',
        '.stage-status-card',
        '.stage-summary-card',
        '.stage-content-card',
        '.stage-actions-card',
        '.stage-note-card',
        '.stage-locked-card',
        '.challenge-hero',
        '.challenge-stat-card',
        '.challenge-card',
        '.challenge-empty-state',
        '.challenge-meta-chip',
        '.progress-hero',
        '.progress-stage-item',
        '.progress-stat',
        '.exam-hero',
        '.exam-question',
        '.glass-card',
        '.bazar-hero',
        '.bazar-card',
        '.bazar-empty-state',
        '.bazar-pagination',
        '.info-section',
        '.edit-section',
        '.stat-card'
    ];

    const blockedParents = [
        '.challenge-modal',
        '.challenge-modal-overlay',
        '.site-modal',
        '.site-modal-backdrop',
        '.profile-menu'
    ].join(', ');

    const groupSelectors = [
        '.features',
        '.steps',
        '.leaderboard-list',
        '.hero-stats',
        '.stage-grid',
        '.stage-meta-grid',
        '.challenge-grid',
        '.challenge-meta-row',
        '.bazar-summary-grid',
        '.bazar-products-grid',
        '.stats-grid',
        '.info-grid',
        '.form-grid',
        '.progress-stats',
        '.progress-stage-list',
        '.exam-questions'
    ].join(', ');

    const rawTargets = Array.from(contentRoot.querySelectorAll(revealSelectors.join(', '))).filter((element) => {
        if (!element || element.classList.contains('site-reveal')) return false;
        if (blockedParents && element.closest(blockedParents)) return false;
        return element.offsetParent !== null || element.getClientRects().length > 0;
    });

    const targetSet = new Set(rawTargets);
    const revealTargets = rawTargets.filter((element) => {
        let parent = element.parentElement;
        while (parent && parent !== contentRoot) {
            if (targetSet.has(parent) && !parent.matches(groupSelectors)) {
                return false;
            }
            parent = parent.parentElement;
        }
        return true;
    });

    const groupCounts = new Map();
    revealTargets.forEach((element) => {
        const groupParent = element.closest(groupSelectors) || element.parentElement || contentRoot;
        const index = groupCounts.get(groupParent) || 0;
        element.classList.add('site-reveal');
        element.style.setProperty('--reveal-delay', `${Math.min(index, 7) * 70}ms`);
        groupCounts.set(groupParent, index + 1);
    });

    const revealElement = (element) => {
        element.classList.add('site-reveal--visible');
    };

    if (!revealTargets.length || prefersReducedMotion || !('IntersectionObserver' in window)) {
        revealTargets.forEach(revealElement);
        document.body.classList.add('site-motion-ready');
        return;
    }

    const observer = new IntersectionObserver((entries, currentObserver) => {
        entries.forEach((entry) => {
            if (!entry.isIntersecting) return;
            revealElement(entry.target);
            currentObserver.unobserve(entry.target);
        });
    }, {
        threshold: 0.14,
        rootMargin: '0px 0px -10% 0px'
    });

    revealTargets.forEach((element) => observer.observe(element));
    document.body.classList.add('site-motion-ready');
}

document.addEventListener('DOMContentLoaded', () => {
    initActiveNav();
    initSmoothScroll();
    initGlobalRevealAnimations();
});
