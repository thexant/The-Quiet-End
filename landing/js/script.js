/* ========================================
   LANDING PAGE JAVASCRIPT
   ========================================
   
   This file handles the interactive features of the landing page,
   including theme randomization and effects.
*/

class LandingPageController {
    constructor() {
        this.themes = ['blue', 'amber', 'green', 'red', 'purple'];
        this.currentTheme = null;
        this.themeInterval = null;
        
        this.init();
    }
    
    init() {
        console.log('🎨 Landing Page Controller initialized');
        
        // Wait for DOM and config to be loaded
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', () => {
                this.setupPage();
            });
        } else {
            this.setupPage();
        }
    }
    
    setupPage() {
        console.log('🔧 Setting up landing page...');
        
        // Initialize theme
        this.initializeTheme();
        
        // Setup button interactions
        this.setupButtonEffects();
        
        // Setup responsive features
        this.setupResponsiveFeatures();
        
        // Setup accessibility features
        this.setupAccessibility();
        
        console.log('✅ Landing page setup complete');
    }
    
    initializeTheme() {
        // Check if THEME_MODE is available from config
        const themeMode = typeof THEME_MODE !== 'undefined' ? THEME_MODE : 'random';
        
        console.log('🎨 Initializing theme system, mode:', themeMode);
        
        if (themeMode === 'random') {
            this.setRandomTheme();
            
            // Set up theme cycling if interval is configured
            const cycleInterval = typeof THEME_CYCLE_INTERVAL !== 'undefined' ? THEME_CYCLE_INTERVAL : 30000;
            if (cycleInterval > 0) {
                this.themeInterval = setInterval(() => {
                    this.setRandomTheme();
                }, cycleInterval);
                console.log(`🔄 Theme cycling enabled every ${cycleInterval/1000} seconds`);
            }
        } else if (this.themes.includes(themeMode)) {
            this.setTheme(themeMode);
        } else {
            console.warn('⚠️ Invalid theme mode, defaulting to random');
            this.setRandomTheme();
        }
    }
    
    setRandomTheme() {
        const randomTheme = this.themes[Math.floor(Math.random() * this.themes.length)];
        this.setTheme(randomTheme);
    }
    
    setTheme(themeName) {
        if (!this.themes.includes(themeName)) {
            console.warn(`⚠️ Unknown theme: ${themeName}`);
            return;
        }
        
        // Remove existing theme classes
        this.themes.forEach(theme => {
            document.body.classList.remove(`theme-${theme}`);
        });
        
        // Apply new theme
        document.body.classList.add(`theme-${themeName}`);
        this.currentTheme = themeName;
        
        console.log(`🎨 Theme changed to: ${themeName.toUpperCase()}`);
        
        // Trigger theme change animation
        this.animateThemeChange();
    }
    
    animateThemeChange() {
        // Add a subtle flash effect when theme changes
        const flash = document.createElement('div');
        flash.style.cssText = `
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: var(--primary-color);
            opacity: 0.05;
            pointer-events: none;
            z-index: 9999;
            animation: theme-flash 0.5s ease-out;
        `;
        
        // Add flash animation keyframes if not already present
        if (!document.querySelector('#theme-flash-style')) {
            const style = document.createElement('style');
            style.id = 'theme-flash-style';
            style.textContent = `
                @keyframes theme-flash {
                    0% { opacity: 0.1; }
                    50% { opacity: 0.05; }
                    100% { opacity: 0; }
                }
            `;
            document.head.appendChild(style);
        }
        
        document.body.appendChild(flash);
        
        // Remove flash element after animation
        setTimeout(() => {
            if (flash.parentNode) {
                flash.parentNode.removeChild(flash);
            }
        }, 500);
    }
    
    setupButtonEffects() {
        const actionButtons = document.querySelectorAll('.action-button');
        
        actionButtons.forEach(button => {
            // Add click effect
            button.addEventListener('click', (e) => {
                this.createClickEffect(e);
            });
            
            // Add hover sound effect (if audio is enabled)
            button.addEventListener('mouseenter', () => {
                this.playHoverSound();
            });
            
            // Validate links
            const href = button.getAttribute('href');
            if (!href || href === '#') {
                button.classList.add('disabled-link');
                button.addEventListener('click', (e) => {
                    e.preventDefault();
                    this.showLinkWarning(button);
                });
            }
        });
    }
    
    createClickEffect(event) {
        const button = event.currentTarget;
        const rect = button.getBoundingClientRect();
        const x = event.clientX - rect.left;
        const y = event.clientY - rect.top;
        
        const ripple = document.createElement('div');
        ripple.style.cssText = `
            position: absolute;
            border-radius: 50%;
            background: var(--primary-color);
            width: 20px;
            height: 20px;
            opacity: 0.5;
            pointer-events: none;
            transform: translate(-50%, -50%);
            left: ${x}px;
            top: ${y}px;
            animation: ripple-effect 0.6s ease-out;
            z-index: 100;
        `;
        
        // Add ripple animation if not already present
        if (!document.querySelector('#ripple-style')) {
            const style = document.createElement('style');
            style.id = 'ripple-style';
            style.textContent = `
                @keyframes ripple-effect {
                    to {
                        transform: translate(-50%, -50%) scale(4);
                        opacity: 0;
                    }
                }
            `;
            document.head.appendChild(style);
        }
        
        button.style.position = 'relative';
        button.appendChild(ripple);
        
        setTimeout(() => {
            if (ripple.parentNode) {
                ripple.parentNode.removeChild(ripple);
            }
        }, 600);
    }
    
    playHoverSound() {
        // Placeholder for hover sound effect
        // Could be implemented with Web Audio API if desired
    }
    
    showLinkWarning(button) {
        const buttonTitle = button.querySelector('.button-title').textContent;
        
        // Create warning notification
        const warning = document.createElement('div');
        warning.style.cssText = `
            position: fixed;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            background: var(--gradient-panel);
            border: 2px solid var(--error-color);
            border-radius: 8px;
            padding: 1.5rem;
            z-index: 10000;
            max-width: 400px;
            text-align: center;
            box-shadow: 0 0 40px var(--error-color);
            font-family: 'Share Tech Mono', monospace;
            color: var(--text-primary);
        `;
        
        warning.innerHTML = `
            <h3 style="color: var(--error-color); margin: 0 0 1rem 0; font-family: 'Tektur', monospace;">
                ⚠️ LINK NOT CONFIGURED
            </h3>
            <p style="margin: 0 0 1rem 0; font-size: 0.9rem; line-height: 1.4;">
                The ${buttonTitle} link has not been configured yet.<br>
                Please edit the <strong>js/config.js</strong> file to set up this link.
            </p>
            <button onclick="this.parentElement.remove()" style="
                background: var(--error-color);
                color: white;
                border: none;
                padding: 0.5rem 1rem;
                border-radius: 4px;
                cursor: pointer;
                font-family: 'Share Tech Mono', monospace;
                text-transform: uppercase;
                font-weight: bold;
            ">
                CLOSE
            </button>
        `;
        
        document.body.appendChild(warning);
        
        // Auto-remove after 5 seconds
        setTimeout(() => {
            if (warning.parentNode) {
                warning.parentNode.removeChild(warning);
            }
        }, 5000);
    }
    
    setupResponsiveFeatures() {
        // Handle window resize for responsive adjustments
        let resizeTimeout;
        window.addEventListener('resize', () => {
            clearTimeout(resizeTimeout);
            resizeTimeout = setTimeout(() => {
                this.handleResize();
            }, 250);
        });
        
        // Initial setup
        this.handleResize();
    }
    
    handleResize() {
        const isMobile = window.innerWidth <= 768;
        
        // Adjust animations for mobile
        if (isMobile) {
            document.body.classList.add('mobile-mode');
        } else {
            document.body.classList.remove('mobile-mode');
        }
        
        // Adjust feature grid layout for very small screens
        const featuresGrid = document.querySelector('.features-grid');
        if (featuresGrid && window.innerWidth <= 480) {
            featuresGrid.style.gridTemplateColumns = '1fr';
        } else if (featuresGrid && window.innerWidth <= 768) {
            featuresGrid.style.gridTemplateColumns = 'repeat(2, 1fr)';
        }
    }
    
    setupAccessibility() {
        // Add keyboard navigation support
        const actionButtons = document.querySelectorAll('.action-button');
        
        actionButtons.forEach(button => {
            button.addEventListener('keydown', (e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    this.createClickEffect(e);
                    // Small delay before following link
                    setTimeout(() => {
                        if (button.href && button.href !== '#') {
                            window.open(button.href, '_blank');
                        }
                    }, 100);
                }
            });
        });
        
        // Add focus indicators
        const style = document.createElement('style');
        style.textContent = `
            .action-button:focus {
                outline: 2px solid var(--primary-color);
                outline-offset: 2px;
                box-shadow: 0 0 25px var(--glow-primary) !important;
            }
            
            .action-button:focus:not(:focus-visible) {
                outline: none;
            }
        `;
        document.head.appendChild(style);
    }
    
    // Public method to manually change theme (for developer console access)
    changeTheme(themeName) {
        if (this.themeInterval) {
            clearInterval(this.themeInterval);
            this.themeInterval = null;
            console.log('🔄 Theme cycling stopped');
        }
        this.setTheme(themeName);
    }
    
    // Public method to resume random theme cycling
    resumeRandomThemes() {
        if (this.themeInterval) {
            clearInterval(this.themeInterval);
        }
        
        const cycleInterval = typeof THEME_CYCLE_INTERVAL !== 'undefined' ? THEME_CYCLE_INTERVAL : 30000;
        this.themeInterval = setInterval(() => {
            this.setRandomTheme();
        }, cycleInterval);
        console.log('🔄 Theme cycling resumed');
    }
    
    // Cleanup method
    destroy() {
        if (this.themeInterval) {
            clearInterval(this.themeInterval);
        }
        console.log('🧹 Landing Page Controller destroyed');
    }
}

// Initialize the landing page controller
let landingPageController;

// Wait for config to be loaded, then initialize
document.addEventListener('DOMContentLoaded', () => {
    // Small delay to ensure config.js has loaded
    setTimeout(() => {
        landingPageController = new LandingPageController();
        
        // Make controller available globally for debugging
        window.landingPageController = landingPageController;
        
        console.log('🚀 Landing page fully initialized');
        console.log('💡 Developer tip: Use landingPageController.changeTheme("blue") in console to change themes manually');
        
    }, 100);
});

// Handle page visibility changes to pause/resume theme cycling
document.addEventListener('visibilitychange', () => {
    if (landingPageController) {
        if (document.hidden) {
            // Page is hidden, could pause theme cycling for performance
            console.log('📱 Page hidden, theme cycling continues');
        } else {
            // Page is visible again
            console.log('👁️ Page visible, theme cycling active');
        }
    }
});

// Handle beforeunload for cleanup
window.addEventListener('beforeunload', () => {
    if (landingPageController) {
        landingPageController.destroy();
    }
});