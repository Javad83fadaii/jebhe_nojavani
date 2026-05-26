// main.js - جشنواره دانش

// Mock Data
const mockData = {
    userPoints: 1250,
    leaderboard: [
        { name: 'علی محمدی', points: 3450, rank: 1 },
        { name: 'زهرا حسینی', points: 2980, rank: 2 },
        { name: 'محمد رضایی', points: 2760, rank: 3 },
        { name: 'فاطمه کریمی', points: 2540, rank: 4 },
        { name: 'امیر احمدی', points: 2320, rank: 5 }
    ],
    profile: {
        name: 'علی رضایی',
        avatar: '👨‍🎓',
        points: 1250,
        purchases: [
            { name: 'کتاب الکترونیکی', points: 450, date: '۱۴۰۵/۰۱/۱۰' },
            { name: 'دوره آموزشی', points: 800, date: '۱۴۰۴/۱۲/۲۰' }
        ],
        badges: ['طلایی', 'نقره‌ای', 'برنزی', 'فعال', 'متعهد'],
        history: [
            { action: 'شرکت در مسابقه', points: '+۵۰', date: '۱۴۰۵/01/16' },
            { action: 'خرید از فروشگاه', points: '-۴۵۰', date: '۱۴۰۵/01/10' },
            { action: 'برنده شدن در مسابقه', points: '+۲۰۰', date: '۱۴۰۵/01/08' },
            { action: 'شرکت در مسابقه', points: '+۳۰', date: '۱۴۰۵/01/05' }
        ]
    }
};

// Initialize localStorage
function initializeStorage() {
    if (!localStorage.getItem('userPoints')) {
        localStorage.setItem('userPoints', mockData.userPoints.toString());
    }
    
    if (!localStorage.getItem('purchases')) {
        localStorage.setItem('purchases', JSON.stringify([]));
    }
}

// Get user points
function getUserPoints() {
    return parseInt(localStorage.getItem('userPoints')) || 0;
}

// Update points display
function updatePointsDisplay() {
    const pointsElements = document.querySelectorAll('.user-points');
    const points = getUserPoints();
    
    pointsElements.forEach(el => {
        el.textContent = points.toLocaleString('fa-IR');
    });
}

// Mobile Menu Toggle
function initMobileMenu() {
    const menuToggle = document.querySelector('.menu-toggle');
    const navLinks = document.querySelector('.nav-links');
    
    if (menuToggle && navLinks) {
        menuToggle.addEventListener('click', () => {
            navLinks.classList.toggle('active');
            
            // Animate hamburger
            const spans = menuToggle.querySelectorAll('span');
            spans.forEach(span => span.classList.toggle('active'));
        });
    }
}

// Countdown Timer
function initCountdownTimers() {
    const timers = document.querySelectorAll('[data-deadline]');
    
    function updateTimers() {
        timers.forEach(timer => {
            const deadline = new Date(timer.dataset.deadline);
            const now = new Date();
            const diff = deadline - now;
            
            if (diff <= 0) {
                timer.textContent = 'تمام شده';
                return;
            }
            
            const days = Math.floor(diff / (1000 * 60 * 60 * 24));
            const hours = Math.floor((diff % (1000 * 60 * 60 * 24)) / (1000 * 60 * 60));
            const minutes = Math.floor((diff % (1000 * 60 * 60)) / (1000 * 60));
            
            timer.textContent = `${days} روز ${hours} ساعت ${minutes} دقیقه`;
        });
    }
    
    updateTimers();
    setInterval(updateTimers, 60000); // Update every minute
}



// Shop functionality
function initShop() {
    const buyButtons = document.querySelectorAll('.buy-button');
    
    buyButtons.forEach(button => {
        button.addEventListener('click', (e) => {
            e.preventDefault();
            
            const points = parseInt(button.dataset.points);
            const itemId = button.dataset.id;
            const currentPoints = getUserPoints();
            
            if (currentPoints >= points) {
                // Deduct points
                const newPoints = currentPoints - points;
                localStorage.setItem('userPoints', newPoints.toString());
                
                // Add to purchases
                const purchases = JSON.parse(localStorage.getItem('purchases')) || [];
                purchases.push({
                    id: itemId,
                    name: button.dataset.name,
                    points: points,
                    date: new Date().toLocaleDateString('fa-IR')
                });
                localStorage.setItem('purchases', JSON.stringify(purchases));
                
                // Update display
                updatePointsDisplay();
                
                // Show success message
                showNotification('خرید با موفقیت انجام شد!', 'success');
                
                // Disable button if not enough points
                if (newPoints < points) {
                    button.disabled = true;
                    button.classList.add('disabled');
                }
            } else {
                showNotification('امتیاز کافی نیست!', 'error');
            }
        });
    });
}

// Quiz submission
function initQuiz() {
    const submitButton = document.querySelector('#submit-quiz');
    
    if (submitButton) {
        submitButton.addEventListener('click', () => {
            // Calculate score (mock)
            const score = Math.floor(Math.random() * 100) + 1;
            const pointsEarned = Math.floor(score / 10) * 10;
            
            // Show animation
            const animation = document.createElement('div');
            animation.className = 'score-animation';
            animation.textContent = `${pointsEarned} امتیاز`;
            document.body.appendChild(animation);
            
            // Update points
            const currentPoints = getUserPoints();
            localStorage.setItem('userPoints', (currentPoints + pointsEarned).toString());
            updatePointsDisplay();
            
            // Remove animation after 2 seconds
            setTimeout(() => {
                animation.remove();
            }, 2000);
            
            // Show success message
            showNotification(`تبریک! شما ${pointsEarned} امتیاز کسب کردید.`, 'success');
        });
    }
}

// Show notification
function showNotification(message, type = 'info') {
    const notification = document.createElement('div');
    notification.className = `notification notification-${type}`;
    notification.textContent = message;
    notification.style.cssText = `
        position: fixed;
        top: 20px;
        left: 50%;
        transform: translateX(-50%);
        background: ${type === 'success' ? '#4CAF50' : '#f44336'};
        color: white;
        padding: 1rem 2rem;
        border-radius: 50px;
        z-index: 3000;
        animation: slideDown 0.3s ease;
    `;
    
    document.body.appendChild(notification);
    
    setTimeout(() => {
        notification.remove();
    }, 3000);
}

// Initialize active nav link
function initActiveNav() {
    const currentPage = document.body.dataset.page;
    const navLinks = document.querySelectorAll('.nav-links a[data-nav]');
    
    navLinks.forEach(link => {
        if (link.dataset.nav === currentPage) {
            link.classList.add('active');
        }
    });
}

// Load leaderboard
function loadLeaderboard() {
    const leaderboardContainer = document.querySelector('.leaderboard-list');
    
    if (leaderboardContainer) {
        leaderboardContainer.innerHTML = mockData.leaderboard.map(user => `
            <div class="leaderboard-item glass-card">
                <div class="leaderboard-rank">${user.rank}</div>
                <span>${user.name}</span>
                <span class="text-gold">${user.points.toLocaleString('fa-IR')} امتیاز</span>
            </div>
        `).join('');
    }
}


// Load shop items
function loadShop() {
    const container = document.querySelector('.shop-grid');
    const currentPoints = getUserPoints();
    
    if (container) {
        container.innerHTML = mockData.shopItems.map(item => {
            const canAfford = currentPoints >= item.points;
            
            return `
                <div class="competition-card" data-category="${item.category}">
                    <div class="card-image">
                        <span class="card-badge">${item.points} امتیاز</span>
                    </div>
                    <div class="card-content">
                        <span class="card-category">${item.category}</span>
                        <h3 class="card-title">${item.name}</h3>
                        <button class="btn buy-button ${canAfford ? 'btn-primary' : 'btn-secondary'}" 
                                data-id="${item.id}"
                                data-points="${item.points}"
                                data-name="${item.name}"
                                ${!canAfford ? 'disabled' : ''}>
                            خرید با امتیاز
                        </button>
                    </div>
                </div>
            `;
        }).join('');
        
        initShop();
    }
}

// Load profile data
function loadProfile() {
    const profile = mockData.profile;
    const storedPurchases = JSON.parse(localStorage.getItem('purchases')) || [];
    const purchases = [...profile.purchases, ...storedPurchases];
    
    // Update profile header
    const avatarEl = document.querySelector('.profile-avatar');
    const nameEl = document.querySelector('.profile-name');
    
    if (avatarEl) avatarEl.textContent = profile.avatar;
    if (nameEl) nameEl.textContent = profile.name;
    
    // Load timeline
    const timelineContainer = document.querySelector('.timeline');
    if (timelineContainer) {
        timelineContainer.innerHTML = profile.history.map(item => `
            <div class="timeline-item">
                <span class="timeline-date">${item.date}</span>
                <span>${item.action}</span>
                <span class="text-gold">${item.points}</span>
            </div>
        `).join('');
    }
    

    // Load purchases
    const purchasesContainer = document.querySelector('.purchases-list');
    if (purchasesContainer) {
        purchasesContainer.innerHTML = purchases.map(purchase => `
            <div class="leaderboard-item glass-card">
                <span>${purchase.name}</span>
                <span class="text-gold">${purchase.points} امتیاز</span>
            </div>
        `).join('');
    }
    
    // Load badges
    const badgesContainer = document.querySelector('.badges-grid');
    if (badgesContainer) {
        badgesContainer.innerHTML = profile.badges.map(badge => `
            <div class="badge-item">
                <div class="badge-icon">🏆</div>
                <span>${badge}</span>
            </div>
        `).join('');
    }
}



// Smooth scroll
function initSmoothScroll() {
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function (e) {
            e.preventDefault();
            const target = document.querySelector(this.getAttribute('href'));
            if (target) {
                target.scrollIntoView({
                    behavior: 'smooth',
                    block: 'start'
                });
            }
        });
    });
}

// Global reveal animations
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
        '.timeline-item',
        '.badge-item',
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
        '.question-item',
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
        '.timeline',
        '.badges-grid',
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

// Initialize everything when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    // initializeStorage(); // Disabled - we use Django backend now
    // updatePointsDisplay(); // Disabled - points are rendered by Django template
    initMobileMenu();
    initActiveNav();
    initSmoothScroll();
    initGlobalRevealAnimations();
    // loadLeaderboard(); // Disabled - leaderboard is rendered by Django template
    loadShop();
    // loadProfile(); // Disabled - profile is rendered by Django template
    initQuiz();
    
    // Add Font Awesome if not present
    if (!document.querySelector('link[href*="font-awesome"]')) {
        const fontAwesome = document.createElement('link');
        fontAwesome.rel = 'stylesheet';
        fontAwesome.href = 'https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css';
        document.head.appendChild(fontAwesome);
    }
});

// Add CSS animations for notifications
const style = document.createElement('style');
style.textContent = `
    @keyframes slideDown {
        from {
            top: -100px;
            opacity: 0;
        }
        to {
            top: 20px;
            opacity: 1;
        }
    }
    
    .notification {
        box-shadow: 0 4px 15px rgba(0,0,0,0.2);
    }
    
    .btn:disabled {
        opacity: 0.5;
        cursor: not-allowed;
        transform: none !important;
    }
    
    .btn:disabled:hover {
        transform: none;
    }
`;
document.head.appendChild(style);
// ============================================
// توابع مدیریت کاربر و احراز هویت
// ============================================

// دریافت کاربر جاری
function getCurrentUser() {
    const session = sessionStorage.getItem('userSession') || localStorage.getItem('userSession');
    if (session) {
        return JSON.parse(session);
    }
    return null;
}

// بررسی لاگین بودن کاربر
function isAuthenticated() {
    return getCurrentUser() !== null;
}

// خروج از حساب
function logout() {
    localStorage.removeItem('userSession');
    sessionStorage.removeItem('userSession');
    localStorage.removeItem('userPoints');
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    localStorage.removeItem('user_type');
    window.location.href = '/logout/';
}

// به‌روزرسانی پروفایل کاربر
function updateUserProfile(userData) {
    const currentUser = getCurrentUser();
    if (!currentUser) return;
    
    // به‌روزرسانی در localStorage
    const users = JSON.parse(localStorage.getItem('users') || '[]');
    const userIndex = users.findIndex(u => u.id === currentUser.userId);
    
    if (userIndex !== -1) {
        users[userIndex] = { ...users[userIndex], ...userData };
        localStorage.setItem('users', JSON.stringify(users));
        
        // به‌روزرسانی سشن
        const updatedSession = {
            userId: users[userIndex].id,
            username: users[userIndex].username,
            email: users[userIndex].email,
            fullName: `${users[userIndex].firstName} ${users[userIndex].lastName}`,
            avatar: users[userIndex].avatar
        };
        
        sessionStorage.setItem('userSession', JSON.stringify(updatedSession));
        localStorage.setItem('userSession', JSON.stringify(updatedSession));
    }
}

// دریافت اطلاعات کامل کاربر از روی سشن
function getUserFullInfo() {
    const currentUser = getCurrentUser();
    if (!currentUser) return null;
    
    const users = JSON.parse(localStorage.getItem('users') || '[]');
    return users.find(u => u.id === currentUser.userId);
}

// به‌روزرسانی امتیاز کاربر در دیتابیس محلی
function updateUserPoints(newPoints) {
    const currentUser = getCurrentUser();
    if (!currentUser) return;
    
    const users = JSON.parse(localStorage.getItem('users') || '[]');
    const userIndex = users.findIndex(u => u.id === currentUser.userId);
    
    if (userIndex !== -1) {
        users[userIndex].points = newPoints;
        localStorage.setItem('users', JSON.stringify(users));
    }
    
    localStorage.setItem('userPoints', newPoints.toString());
}

// اورراید کردن تابع getUserPoints قبلی
const originalGetUserPoints = window.getUserPoints;
window.getUserPoints = function() {
    const currentUser = getCurrentUser();
    if (!currentUser) return 0;
    
    const users = JSON.parse(localStorage.getItem('users') || '[]');
    const user = users.find(u => u.id === currentUser.userId);
    return user ? user.points : parseInt(localStorage.getItem('userPoints')) || 0;
};

// اورراید کردن تابع updatePointsDisplay
const originalUpdatePointsDisplay = window.updatePointsDisplay;
window.updatePointsDisplay = function() {
    const pointsElements = document.querySelectorAll('.user-points');
    const points = getUserPoints();
    
    pointsElements.forEach(el => {
        if (el) el.textContent = points.toLocaleString('fa-IR');
    });
};

// محافظت از صفحاتی که نیاز به لاگین دارند
function requireAuth(redirectUrl = '/login/') {
    if (!isAuthenticated()) {
        window.location.href = redirectUrl + '?next=' + encodeURIComponent(window.location.pathname);
        return false;
    }
    return true;
}

// بارگذاری داده‌های پروفایل کاربر واقعی (جایگزین mockData.profile)
function loadRealUserProfile() {
    const user = getUserFullInfo();
    if (!user) return;
    
    // به‌روزرسانی هدر پروفایل
    const avatarEl = document.querySelector('.profile-avatar');
    const nameEl = document.querySelector('.profile-name');
    const userPointsEl = document.querySelector('.user-points');
    
    if (avatarEl) avatarEl.textContent = user.avatar || '👤';
    if (nameEl) nameEl.textContent = `${user.firstName} ${user.lastName}`;
    if (userPointsEl) userPointsEl.textContent = user.points?.toLocaleString('fa-IR') || '0';
    
    // تاریخچه امتیازات (از localStorage مخصوص هر کاربر)
    const userHistoryKey = `user_history_${user.id}`;
    let history = JSON.parse(localStorage.getItem(userHistoryKey)) || [];
    
    // اگر تاریخچه خالی بود، نمونه داده اضافه کن
    if (history.length === 0) {
        history = [
            { action: 'شرکت در مسابقه', points: '+۵۰', date: new Date().toLocaleDateString('fa-IR') },
            { action: 'امتیاز خوش‌آمدگویی', points: '+۱۰۰', date: new Date().toLocaleDateString('fa-IR') }
        ];
        localStorage.setItem(userHistoryKey, JSON.stringify(history));
    }
    
    // بارگذاری تایم‌لاین
    const timelineContainer = document.querySelector('.timeline');
    if (timelineContainer) {
        timelineContainer.innerHTML = history.map(item => `
            <div class="timeline-item">
                <span class="timeline-date">${item.date}</span>
                <span>${item.action}</span>
                <span class="text-gold">${item.points}</span>
            </div>
        `).join('');
    }
    
    // مسابقات تکمیل شده
    const userCompletedKey = `user_completed_${user.id}`;
    let completed = JSON.parse(localStorage.getItem(userCompletedKey)) || [];
    const completedContainer = document.querySelector('.completed-list');
    if (completedContainer) {
        if (completed.length === 0) {
            completedContainer.innerHTML = '<div class="glass-card" style="text-align: center; padding: 2rem;">هنوز در مسابقه‌ای شرکت نکرده‌اید</div>';
        } else {
            completedContainer.innerHTML = completed.map(comp => `
                <div class="leaderboard-item glass-card">
                    <span>${comp.name}</span>
                    <span class="text-gold">+${comp.points} امتیاز</span>
                </div>
            `).join('');
        }
    }
    
    // خریدها
    const userPurchasesKey = `user_purchases_${user.id}`;
    let purchases = JSON.parse(localStorage.getItem(userPurchasesKey)) || [];
    const purchasesContainer = document.querySelector('.purchases-list');
    if (purchasesContainer) {
        if (purchases.length === 0) {
            purchasesContainer.innerHTML = '<div class="glass-card" style="text-align: center; padding: 2rem;">هنوز خریدی انجام نداده‌اید</div>';
        } else {
            purchasesContainer.innerHTML = purchases.map(purchase => `
                <div class="leaderboard-item glass-card">
                    <span>${purchase.name}</span>
                    <span class="text-gold">${purchase.points} امتیاز</span>
                </div>
            `).join('');
        }
    }
    
    // نشان‌ها
    const badgesContainer = document.querySelector('.badges-grid');
    if (badgesContainer) {
        const badges = user.badges || ['تازه‌وارد'];
        badgesContainer.innerHTML = badges.map(badge => `
            <div class="badge-item">
                <div class="badge-icon">🏆</div>
                <span>${badge}</span>
            </div>
        `).join('');
    }
}

// اورراید کردن تابع loadProfile
const originalLoadProfile = window.loadProfile;
window.loadProfile = function() {
    if (isAuthenticated()) {
        loadRealUserProfile();
    } else {
        if (originalLoadProfile) originalLoadProfile();
    }
};



// تابع خرید از فروشگاه
function purchaseItem(itemId, itemName, pointsCost) {
    const user = getCurrentUser();
    if (!user) return false;
    
    const currentPoints = getUserPoints();
    if (currentPoints < pointsCost) return false;
    
    // کاهش امتیاز
    const newPoints = currentPoints - pointsCost;
    updateUserPoints(newPoints);
    updatePointsDisplay();
    
    // ثبت در خریدها
    const userPurchasesKey = `user_purchases_${user.userId}`;
    let purchases = JSON.parse(localStorage.getItem(userPurchasesKey)) || [];
    purchases.push({
        id: itemId,
        name: itemName,
        points: pointsCost,
        date: new Date().toLocaleDateString('fa-IR')
    });
    localStorage.setItem(userPurchasesKey, JSON.stringify(purchases));
    
    // ثبت در تاریخچه
    const userHistoryKey = `user_history_${user.userId}`;
    let history = JSON.parse(localStorage.getItem(userHistoryKey)) || [];
    history.unshift({
        action: `خرید از فروشگاه: ${itemName}`,
        points: `-${pointsCost}`,
        date: new Date().toLocaleDateString('fa-IR')
    });
    localStorage.setItem(userHistoryKey, JSON.stringify(history));
    
    return true;
}

// به‌روزرسانی تابع initShop برای استفاده از purchaseItem واقعی
const originalInitShop = window.initShop;
window.initShop = function() {
    const buyButtons = document.querySelectorAll('.buy-button');
    
    buyButtons.forEach(button => {
        button.addEventListener('click', (e) => {
            e.preventDefault();
            
            if (!isAuthenticated()) {
                showNotification('لطفاً ابتدا وارد حساب خود شوید.', 'error');
                setTimeout(() => {
                    window.location.href = '/login/?next=/shop/';
                }, 1500);
                return;
            }
            
            const points = parseInt(button.dataset.points);
            const itemId = button.dataset.id;
            const itemName = button.dataset.name;
            
            if (purchaseItem(itemId, itemName, points)) {
                showNotification(`${itemName} با موفقیت خریداری شد!`, 'success');
                
                // غیرفعال کردن دکمه اگر امتیاز کافی نبود
                if (getUserPoints() < points) {
                    button.disabled = true;
                    button.classList.add('disabled');
                }
            } else {
                showNotification('امتیاز کافی نیست!', 'error');
            }
        });
    });
};
