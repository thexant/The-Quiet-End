/* ========================================
   LANDING PAGE CONFIGURATION
   ========================================
   
   This file contains all the customizable content for your landing page.
   Edit the values below to change links and information without touching HTML/CSS.
   
   IMPORTANT: After making changes, save this file and refresh your webpage.
*/

// ========================================
// DISCORD INVITE LINK
// ========================================
// Replace the URL below with your Discord server invite link
const DISCORD_INVITE_URL = "https://discord.gg/JsJcnTKyQn";

// ========================================
// WIKI AND MAP LINKS
// ========================================
// Replace these URLs with your actual wiki and map URLs
const WIKI_URL = "https://thequietend.servegame.com/wiki";
const MAP_URL = "https://thequietend.servegame.com/map";

// ========================================
// GAME INFORMATION CONTENT
// ========================================
// Edit the text below to describe your game. You can use basic HTML tags like <br> for line breaks.
const GAME_INFO_HTML = `
	<p><strong>Welcome to The Quiet End</strong> - an immersive Discord-based space game set in a slowly dying galaxy where human civilization teeters on the edge of collapse</p>
    
    <p>Navigate the dangerous and shifting corridors of space as an independent pilot in a universe where every transmission might be your last. Experience a living, breathing galaxy where your choices matter and death is permanent in this unique blend of roleplay, exploration, and survival:</p>
    
    <ul>
        <li><strong>Dynamic Galaxy Simulation:</strong> Travel between procedurally connected colonies, space stations, outposts, and gates, each with unique economies, NPCs, and opportunities that evolve in real-time</li>
        <li><strong>Permadeath & Consequence:</strong> Character death is permanent and meaningful - your actions ripple through the galaxy as galactic news reports chronicle the rise and fall of pilots across human space</li>
        <li><strong>Real-Time Economy:</strong> Engage in a living marketplace where job opportunities, trade routes, and shop inventories fluctuate based on player actions and galactic events</li>
        <li><strong>Interactive Communications:</strong> Use an advanced radio system to communicate across the void, coordinate with other pilots, and intercept emergency transmissions from NPCs fighting for survival</li>
        <li><strong>The Approaching End:</strong> Experience the unique "endgame apocalypse" where administrators can trigger galactic collapse - locations are systematically destroyed as reality itself unravels, forcing players into desperate survival scenarios</li>
    </ul>
    
    <p>The galaxy is <strong>persistent and dynamic</strong> - a procedurally generated network of star systems connected by treacherous travel corridors, populated by AI-driven NPCs who live, work, and die according to their own schedules. Galactic news broadcasts chronicle everything from successful harvests to pilot obituaries, creating an authentic sense of a civilization slowly succumbing to entropy.</p>
    
    <p><em>In the depths of space, every decision echoes in the silence. Will you be another casualty of the void, or will your name be remembered when the last beacon goes dark?</em></p>
`;

// ========================================
// THEME CONFIGURATION
// ========================================
// Set to 'random' for random theme each visit, or specify: 'blue', 'amber', 'green', 'red', 'purple'
const THEME_MODE = "random";

// ========================================
// ADVANCED SETTINGS
// ========================================
// These settings control technical aspects of the page

// How often to cycle the theme in 'random' mode (milliseconds)
const THEME_CYCLE_INTERVAL = 30000; // 30 seconds

// Enable/disable CRT effects (scanlines, static) - set to false to disable
const ENABLE_CRT_EFFECTS = true;

// Page title (appears in browser tab)
const PAGE_TITLE = "The Quiet End - Discord Space Trading Game";

// ========================================
// DO NOT EDIT BELOW THIS LINE
// ========================================
// The code below applies your configuration - editing it may break the page

// Apply configuration when page loads
document.addEventListener('DOMContentLoaded', function() {
    // Set page title
    document.title = PAGE_TITLE;
    
    // Apply links
    const discordLink = document.getElementById('discord-link');
    const wikiLink = document.getElementById('wiki-link');
    const mapLink = document.getElementById('map-link');
    
    if (discordLink) discordLink.href = DISCORD_INVITE_URL;
    if (wikiLink) wikiLink.href = WIKI_URL;
    if (mapLink) mapLink.href = MAP_URL;
    
    // Apply game info content
    const gameInfoContent = document.getElementById('game-info-content');
    if (gameInfoContent) {
        gameInfoContent.innerHTML = GAME_INFO_HTML;
    }
    
    // Disable CRT effects if configured
    if (!ENABLE_CRT_EFFECTS) {
        const scanlines = document.querySelector('.scanlines');
        const staticOverlay = document.querySelector('.static-overlay');
        if (scanlines) scanlines.style.display = 'none';
        if (staticOverlay) staticOverlay.style.display = 'none';
    }
    
    console.log('Landing page configuration loaded successfully');
    console.log('Discord URL:', DISCORD_INVITE_URL);
    console.log('Wiki URL:', WIKI_URL);
    console.log('Map URL:', MAP_URL);
    console.log('Theme mode:', THEME_MODE);
});