class GalaxyMap {
                    constructor() {
                        this.map = null;
                        this.websocket = null;
                        this.locations = new Map();
                        this.corridors = new Map();
                        this.players = new Map();
                        this.npcs = new Map();  // ADD THIS LINE
                        this.npcsInTransit = new Map();
                        this.selectedLocation = null;
                        this.routePolylines = [];
                        this.highlightedLocations = [];
                        this.currentRoute = null;
                        this.labels = new Map();
                        this.routeMode = false;
                        this.showLabels = false;
                        this.showRoutes = false;
                        this.showNPCs = true;  // ADD THIS LINE
                        this.headerExpanded = true;
                        this.reconnectAttempts = 0;
                        this.maxReconnectAttempts = 10;
                        this.reconnectDelay = 1000;
                        this.labelGrid = new Map();
                        this.selectedCorridor = null;
                        this.corridorPolylines = new Map(); // Track corridor polylines
                        this.showRoutes = false; // Change default to false (hidden)
                        this.playersInTransit = new Map(); // Track players in transit
                        this.pendingLabelTimeouts = [];
                        this.initializeColorScheme();
                        console.log('🎨 Color scheme initialized');
                        this.init();
                    }
                    
                    initializeColorScheme(theme = null) {
                        let selectedTheme;
                        
                        if (theme) {
                            selectedTheme = theme;
                        } else {
                            // Fallback to random if no theme provided
                            const themes = ['blue', 'amber', 'green', 'red', 'purple'];
                            selectedTheme = themes[Math.floor(Math.random() * themes.length)];
                        }
                        
                        document.body.className = `theme-${selectedTheme}`;
                        
                        console.log(`🎨 CRT Terminal initialized with ${selectedTheme.toUpperCase()} color scheme`);
                    }
                    
                    init() {
                        console.log('🗺️ Setting up map...');
                        this.setupMap();
                        console.log('🎛️ Setting up event listeners...');
                        this.setupEventListeners();
                        this.setupSearchFunctionality();
                        console.log('🔌 Connecting WebSocket...');
                        this.connectWebSocket();
                        console.log('👁️ Hiding loading overlay...');
                        this.hideLoadingOverlay();
                        console.log('✅ Map initialization complete');
                    }
                    
                    setupMap() {
                        this.map = L.map('map', {
                            crs: L.CRS.Simple,
                            minZoom: -3,
                            maxZoom: 6,
                            zoomControl: false,
                            attributionControl: false,
                            maxBounds: [[-5000, -5000], [5000, 5000]],
                            maxBoundsViscosity: 1.0
                        });
                        
                        L.control.zoom({
                            position: 'bottomright'
                        }).addTo(this.map);
                        
                        this.map.setView([0, 0], 1);
                        
                        this.map.on('click', () => {
                            this.hideLocationPanel();
                        });
                        
                        // Update labels when zoom changes
                        this.map.on('zoomend', () => {
                            if (this.showLabels) {
                                this.updateLabelsForZoom();
                            }
                        });
                        
                        this.map.on('moveend', () => {
                            if (this.showLabels) {
                                this.updateLabelsForZoom();
                            }
                        });
                    }

                    setupEventListeners() {
                        // Header toggle
                        const headerToggle = document.getElementById('header-toggle');
                        const header = document.getElementById('header');
                        const map = document.getElementById('map');
                        const locationPanel = document.getElementById('location-panel');
                        
                        headerToggle?.addEventListener('click', () => {
                            this.headerExpanded = !this.headerExpanded;
                            
                            if (this.headerExpanded) {
                                header.classList.remove('header-collapsed');
                                header.classList.add('header-expanded');
                                map.classList.remove('header-collapsed');
                                locationPanel?.classList.remove('header-collapsed');
                                headerToggle.classList.remove('collapsed');
                            } else {
                                header.classList.remove('header-expanded');
                                header.classList.add('header-collapsed');
                                map.classList.add('header-collapsed');
                                locationPanel?.classList.add('header-collapsed');
                                headerToggle.classList.add('collapsed');
                            }
                        });
                        
                        // Mobile toggle
                        const mobileToggle = document.getElementById('mobile-toggle');
                        const controlsSection = document.getElementById('controls-section');
                        
                        mobileToggle?.addEventListener('click', () => {
                            controlsSection.classList.toggle('active');
                        });
                        
                        // Search functionality
                        const searchInput = document.getElementById('location-search');
                        const searchBtn = document.getElementById('search-btn');
                        const clearSearchBtn = document.getElementById('clear-search-btn');
                        
                        const performSearch = () => {
                            const query = searchInput.value.trim();
                            if (query) {
                                this.searchLocations(query);
                            }
                        };
                        
                        const clearSearch = () => {
                            searchInput.value = '';
                            this.clearHighlights();
                            this.clearSearch();
                        };
                        
                        searchBtn?.addEventListener('click', performSearch);
                        clearSearchBtn?.addEventListener('click', clearSearch);
                        
                        searchInput?.addEventListener('keypress', (e) => {
                            if (e.key === 'Enter') {
                                performSearch();
                            }
                        });
                        
                        searchInput?.addEventListener('input', (e) => {
                            if (!e.target.value.trim()) {
                                this.clearHighlights();
                            }
                        });
                        
                        // Route plotting
                        const plotRouteBtn = document.getElementById('plot-route-btn');
                        const clearRouteBtn = document.getElementById('clear-route-btn');
                        
                        plotRouteBtn?.addEventListener('click', () => {
                            const fromId = document.getElementById('route-from').value;
                            const toId = document.getElementById('route-to').value;
                            if (fromId && toId && fromId !== toId) {
                                this.plotRoute(parseInt(fromId), parseInt(toId));
                            }
                        });
                        
                        clearRouteBtn?.addEventListener('click', () => {
                            this.clearRoute();
                            document.getElementById('route-from').value = '';
                            document.getElementById('route-to').value = '';
                        });
                        
                        // View controls
                        const fitBoundsBtn = document.getElementById('fit-bounds-btn');
                        const toggleLabelsBtn = document.getElementById('toggle-labels-btn');
                        const toggleRoutesBtn = document.getElementById('toggle-routes-btn');
                        const toggleNPCsBtn = document.getElementById('toggle-npcs-btn');

                        fitBoundsBtn?.addEventListener('click', () => {
                            this.fitMapToBounds();
                        });

                        toggleLabelsBtn?.addEventListener('click', () => {
                            this.toggleLabels();
                        });

                        // Route toggle - single event listener only
                        toggleRoutesBtn?.addEventListener('click', () => {
                            this.toggleRoutes();
                        });

                        // Set initial button state
                        if (toggleRoutesBtn) {
                            toggleRoutesBtn.textContent = 'SHOW ROUTES';
                            toggleRoutesBtn.classList.remove('toggle-active');
                        }

                        if (toggleNPCsBtn) {
                            toggleNPCsBtn.addEventListener('click', () => {
                                this.toggleNPCs();
                            });
                        }

                        // Panel close
                        const closePanel = document.getElementById('close-panel');
                        closePanel?.addEventListener('click', () => {
                            this.hideLocationPanel();
                        });
                        
                        // Close panel when clicking outside
                        document.addEventListener('click', (e) => {
                            const panel = document.getElementById('location-panel');
                            const mapContainer = this.map?.getContainer();
                            
                            if (panel && !panel.contains(e.target) && 
                                mapContainer && !mapContainer.contains(e.target)) {
                                this.hideLocationPanel();
                            }
                        });
                        
                        // Keyboard shortcuts
                        document.addEventListener('keydown', (e) => {
                            if (e.target.tagName.toLowerCase() === 'input' || e.target.tagName.toLowerCase() === 'select') return;
                            
                            switch(e.key) {
                                case 'Escape':
                                    this.hideLocationPanel();
                                    this.clearHighlights();
                                    this.clearRoute();
                                    break;
                                case 'f':
                                case 'F':
                                    this.fitMapToBounds();
                                    break;
                                case 'l':
                                case 'L':
                                    this.toggleLabels();
                                    break;
                                case 'r':
                                case 'R':
                                    this.toggleRoutes();
                                    break;
                                case 'h':
                                case 'H':
                                    headerToggle?.click();
                                    break;
                            }
                        });
                    }
                    setupSearchFunctionality() {
                        const searchInput = document.getElementById('universal-search');
                        const searchBtn = document.getElementById('search-btn');
                        const resultsContainer = document.getElementById('search-results');

                        if (!searchInput || !searchBtn || !resultsContainer) return;

                        const performSearch = () => {
                            const query = searchInput.value.trim();
                            if (!query) {
                                resultsContainer.innerHTML = '<p>Please enter a search term.</p>';
                                return;
                            }

                            this.performUniversalSearch(query);
                        };

                        searchBtn.addEventListener('click', performSearch);
                        searchInput.addEventListener('keypress', (e) => {
                            if (e.key === 'Enter') {
                                performSearch();
                            }
                        });
                    }

                    performUniversalSearch(query) {
                        const resultsContainer = document.getElementById('search-results');
                        if (!resultsContainer) return;

                        const queryLower = query.toLowerCase();
                        const results = {
                            locations: [],
                            npcs: [],
                            logs: [],
                            news: []
                        };

                        // Search locations
                        if (this.data && this.data.locations) {
                            this.data.locations.forEach(location => {
                                if (location.name.toLowerCase().includes(queryLower) ||
                                    location.description.toLowerCase().includes(queryLower) ||
                                    location.type.toLowerCase().includes(queryLower)) {
                                    results.locations.push(location);
                                }
                            });
                        }

                        this.displaySearchResults(results, query);
                    }

                    displaySearchResults(results, query) {
                        const resultsContainer = document.getElementById('search-results');
                        const totalResults = results.locations.length;

                        if (totalResults === 0) {
                            resultsContainer.innerHTML = `
                                <div class="no-results">
                                    <p>No results found for "${query}"</p>
                                    <p>Try searching for location names or types.</p>
                                </div>
                            `;
                            return;
                        }

                        let html = `<div class="search-results-summary">
                                        <h3>Search Results for "${query}" (${totalResults} found)</h3>
                                    </div>`;

                        // Display locations
                        if (results.locations.length > 0) {
                            html += `<div class="search-section">
                                        <h4>📍 Locations (${results.locations.length})</h4>`;
                            results.locations.forEach(location => {
                                html += `<div class="search-result location-result">
                                            <h5>${location.name}</h5>
                                            <p>Type: ${location.location_type}</p>
                                            <p>${location.description || 'No description available.'}</p>
                                         </div>`;
                            });
                            html += '</div>';
                        }

                        resultsContainer.innerHTML = html;
                    }

                    connectWebSocket() {
                        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
                        const wsUrl = `${protocol}//${window.location.host}/ws`;
                        
                        if (this.websocket) {
                            this.websocket.close();
                        }
                        
                        this.websocket = new WebSocket(wsUrl);
                        
                        this.websocket.onopen = () => {
                            this.updateConnectionStatus('CONNECTED', 'var(--success-color)');
                            this.reconnectAttempts = 0;
                            console.log('🔗 WebSocket connected to navigation systems');
                        };
                        
                        this.websocket.onmessage = (event) => {
                            try {
                                const data = JSON.parse(event.data);
                                this.handleWebSocketMessage(data);
                            } catch (error) {
                                console.error('Failed to parse WebSocket message:', error);
                            }
                        };
                        
                        this.websocket.onclose = () => {
                            this.updateConnectionStatus('DISCONNECTED', 'var(--error-color)');
                            console.log('🔌 WebSocket disconnected');
                            this.scheduleReconnect();
                        };

                        this.websocket.onerror = (error) => {
                            console.error('❌ WebSocket error:', error);
                            this.updateConnectionStatus('ERROR', 'var(--warning-color)');
                        };
                    }
                    
                    scheduleReconnect() {
                        if (this.reconnectAttempts < this.maxReconnectAttempts) {
                            this.reconnectAttempts++;
                            const delay = Math.min(this.reconnectDelay * Math.pow(2, this.reconnectAttempts - 1), 30000);
                            
                            this.updateConnectionStatus(`RECONNECTING... (${this.reconnectAttempts})`, 'var(--warning-color)');
                            
                            setTimeout(() => {
                                this.connectWebSocket();
                            }, delay);
                        } else {
                            this.updateConnectionStatus('CONNECTION FAILED', 'var(--error-color)');
                        }
                    }
                    
                    handleWebSocketMessage(data) {
                        switch(data.type) {
                            case 'galaxy_data':
                                this.updateGalaxyData(data.data);
                                if (data.data.selected_theme) {
                                    this.initializeColorScheme(data.data.selected_theme);
                                }
                                break;
                            case 'player_update':
                                this.updatePlayers(data.data);
                                break;
                            case 'npc_update':
                                this.updateNPCs(data.data);
                                break;
                            case 'transit_update':  // Add this new case
                                this.updatePlayersInTransit(data.data);
                                break;
                            case 'location_update':
                                this.updateLocation(data.data);
                                break;
                            case 'npc_transit_update':
                                this.updateNPCsInTransit(data.data);
                                break;
                            default:
                                console.warn('Unknown WebSocket message type:', data.type);
                        }
                    }
                    
                    updateGalaxyData(data) {
                        try {
                            this.locations.clear();
                            this.corridors.clear();
                            this.labelGrid.clear();
                            this.map.eachLayer((layer) => {
                                if (layer !== this.map._layers[Object.keys(this.map._layers)[0]]) {
                                    this.map.removeLayer(layer);
                                }
                            });
                            this.updatePlayersInTransit(data.players_in_transit || []);
                            this.updateNPCsInTransit(data.npcs_in_transit || []);
                            
                            data.locations.forEach(location => {
                                this.addLocation(location);
                            });
                            
                            data.corridors.forEach(corridor => {
                                this.addCorridor(corridor);
                            });
                            
                            this.applyRouteVisibility();
                            this.updatePlayers(data.players || []);
                            this.updateNPCs(data.dynamic_npcs || []);  // ADD THIS LINE
                            this.populateRouteSelects();
                            this.fitMapToBounds();
                            
                        } catch (error) {
                            console.error('Error updating galaxy data:', error);
                        }
                    }
                    
                    addLocation(location) {
                        const marker = this.createLocationMarker(location);
                        marker.addTo(this.map);
                        
                        this.locations.set(location.location_id, {
                            ...location,
                            marker: marker
                        });
                        
                        marker.on('click', (e) => {
                            L.DomEvent.stopPropagation(e);
                            this.selectLocation(location);
                        });
                    }
                    
                    createLocationMarker(location) {
                        const colors = {
                            'Colony': 'var(--success-color)',
                            'Space Station': 'var(--primary-color)',
                            'Outpost': 'var(--warning-color)',
                            'Transit Gate': '#ffdd00'
                        };
                        
                        // Override color based on alignment
                        let color = colors[location.location_type] || '#ffffff';
                        
                        if (location.alignment === 'loyalist') {
                            color = '#4169E1'; // Royal Blue for Loyalists
                        } else if (location.alignment === 'outlaw') {
                            color = '#DC143C'; // Crimson for Outlaws
                        }
                        
                        const zoom = this.map.getZoom();
                        
                        // Apply consistent zoom scaling to ALL locations
                        let finalSize;
                        if (zoom < -1) {
                            finalSize = 12; // All tiny when zoomed way out
                        } else if (zoom < 0) {
                            finalSize = 13; // All small when zoomed out
                        } else if (zoom < 1) {
                            finalSize = 14; // All medium when mid-zoom
                        } else {
                            finalSize = 15; // All normal when zoomed in
                        }
                        
                        const marker = this.createShapedMarker(location, color, finalSize);
                        
                        // Add alignment class to marker element for additional styling
                        if (location.alignment !== 'neutral') {
                            marker.on('add', () => {
                                const element = marker.getElement();
                                if (element) {
                                    element.classList.add(`location-${location.alignment}`);
                                }
                            });
                        }
                        
                        return marker;
                    }    
                    getZoomAdjustedBaseSize(locationType) {
                        const zoom = this.map.getZoom();
                        
                        // Force complete uniformity at low zoom levels
                        if (zoom < -0.5) {
                            return 14; // Everyone gets exactly the same size when zoomed way out
                        }
                        
                        const baseSizes = {
                            'colony': 15,
                            'space_station': 15, 
                            'outpost': 15,
                            'gate': 15
                        };
                        
                        const baseSize = baseSizes[locationType.toLowerCase()] || 14;
                        
                        if (zoom < 1.5) {
                            // Still zoomed out: very minimal differences (max 1px variance)
                            const uniformSize = 15;
                            const variance = (baseSize - uniformSize) * 0.2; // Only 20% of type difference
                            return uniformSize + variance;
                        } else {
                            // Zoomed in enough: allow full differences
                            return baseSize;
                        }
                    }
                    addCorridor(corridor) {
                        // Improved corridor type detection
                        let corridorType = 'ungated'; // default
                        let color = 'var(--warning-color)'; // orange for ungated
                        
                        // Detect corridor type based on name patterns
                        if (corridor.name.toLowerCase().includes('approach')) {
                            corridorType = 'approach';
                            color = '#8c75ff'; // light green for local space
                        } else if (corridor.name.toLowerCase().includes('ungated')) {
                            corridorType = 'ungated';
                            color = 'var(--warning-color)'; // orange for ungated
                        } else {
                            // Check if route connects to gates by looking at endpoint types
                            const originIsGate = this.locations.get(corridor.origin_location)?.location_type === 'gate';
                            const destIsGate = this.locations.get(corridor.destination_location)?.location_type === 'gate';
                            
                            if (originIsGate || destIsGate) {
                                corridorType = 'gated';
                                color = 'var(--success-color)'; // green for gated
                            }
                        }
                        
                        // Create invisible thick line for better click targets
                        const clickTarget = L.polyline([
                            [corridor.origin_y, corridor.origin_x],
                            [corridor.dest_y, corridor.dest_x]
                        ], {
                            color: 'transparent',
                            weight: 12,
                            opacity: 0,
                            interactive: true
                        });

                        // Create visible line with proper styling
                        const polyline = L.polyline([
                            [corridor.origin_y, corridor.origin_x],
                            [corridor.dest_y, corridor.dest_x]
                        ], {
                            color: color,
                            weight: corridorType === 'gated' ? 2 : corridorType === 'approach' ? 1.5 : 3,
                            opacity: 0.7,
                            dashArray: corridorType === 'ungated' ? '8, 5' : corridorType === 'approach' ? '4, 2' : null,
                            className: `corridor ${corridorType}`,
                            corridorId: corridor.corridor_id,
                            interactive: false
                        });

                        // Add both to map
                        clickTarget.addTo(this.map);
                        polyline.addTo(this.map);

                        // Make click target interactive
                        clickTarget.on('click', (e) => {
                            L.DomEvent.stopPropagation(e);
                            this.selectCorridor(corridor, polyline);
                        });
                        
                        // Add mouseover effects to click target
                        clickTarget.on('mouseover', () => {
                            if (!polyline.getElement()?.classList.contains('corridor-selected')) {
                                polyline.setStyle({opacity: 1, weight: polyline.options.weight + 1});
                            }
                        });

                        clickTarget.on('mouseout', () => {
                            if (!polyline.getElement()?.classList.contains('corridor-selected')) {
                                polyline.setStyle({opacity: 0.7, weight: polyline.options.weight - 1});
                            }
                        });
                        
                        // Store both polylines for later reference
                        this.corridorPolylines.set(corridor.corridor_id, polyline);

                        this.corridors.set(corridor.corridor_id, {
                            ...corridor,
                            polyline: polyline,
                            clickTarget: clickTarget,
                            isGated: corridorType === 'gated',
                            corridorType: corridorType
                        });
                    }

                    // Add corridor selection functionality
                    selectCorridor(corridor, polyline) {
                        // Clear previous selection
                        if (this.selectedCorridor) {
                            this.selectedCorridor.polyline.getElement()?.classList.remove('corridor-selected');
                        }
                        
                        // Select new corridor
                        this.selectedCorridor = {corridor, polyline};
                        polyline.getElement()?.classList.add('corridor-selected');
                        
                        // Show corridor information panel
                        this.showCorridorInfo(corridor);
                    }

                    // Add corridor information panel
                    showCorridorInfo(corridor) {
                        // Get players and NPCs in this corridor
                        const playersInCorridor = this.playersInTransit.get(corridor.corridor_id) || [];
                        const npcsInCorridor = this.npcsInTransit.get(corridor.corridor_id) || [];
                        
                        const panelContent = `
                            <div class="corridor-info-panel">
                                <h3>${corridor.name}</h3>
                                <div class="corridor-details">
                                    <p><strong>Type:</strong> ${corridor.name.includes('Ungated') ? 'Ungated (Dangerous)' : 'Gated (Safe)'}</p>
                                    <p><strong>Travel Time:</strong> ${Math.floor(corridor.travel_time / 60)} minutes ${corridor.travel_time % 60} seconds</p>
                                    <p><strong>Fuel Cost:</strong> ${corridor.fuel_cost} units</p>
                                    <p><strong>Danger Level:</strong> ${corridor.danger_level}/5</p>
                                </div>
                                ${playersInCorridor.length > 0 ? `
                                    <div class="transit-players">
                                        <h4>Players in Transit:</h4>
                                        ${playersInCorridor.map(player => `
                                            <div class="transit-player">
                                                ${player.name} (${player.origin} → ${player.destination})
                                            </div>
                                        `).join('')}
                                    </div>
                                ` : ''}
                                ${npcsInCorridor.length > 0 ? `
                                    <div class="transit-players">
                                        <h4>NPCs in Transit:</h4>
                                        ${npcsInCorridor.map(npc => `
                                            <div class="transit-player" style="color: var(--warning-color);">
                                                ${npc.name} (${npc.callsign}) - ${npc.ship_name}<br>
                                                ${npc.origin} → ${npc.destination}
                                            </div>
                                        `).join('')}
                                    </div>
                                ` : ''}
                                ${playersInCorridor.length === 0 && npcsInCorridor.length === 0 ? '<p>No players or NPCs currently in transit</p>' : ''}
                                <button onclick="galaxyMap.clearCorridorSelection()">Close</button>
                            </div>
                        `;
                        
                        // Create or update info panel
                        let infoPanel = document.getElementById('corridor-info-panel');
                        if (!infoPanel) {
                            infoPanel = document.createElement('div');
                            infoPanel.id = 'corridor-info-panel';
                            infoPanel.className = 'corridor-info-overlay';
                            document.body.appendChild(infoPanel);
                        }
                        
                        infoPanel.innerHTML = panelContent;
                        infoPanel.style.display = 'block';
                    }
                    // Clear corridor selection
                    clearCorridorSelection() {
                        if (this.selectedCorridor) {
                            this.selectedCorridor.polyline.getElement()?.classList.remove('corridor-selected');
                            this.selectedCorridor = null;
                        }
                        
                        const infoPanel = document.getElementById('corridor-info-panel');
                        if (infoPanel) {
                            infoPanel.style.display = 'none';
                        }
                    }
                    updatePlayersInTransit(transitData) {
                        this.playersInTransit.clear();
                        
                        transitData.forEach(player => {
                            if (!this.playersInTransit.has(player.corridor_id)) {
                                this.playersInTransit.set(player.corridor_id, []);
                            }
                            this.playersInTransit.get(player.corridor_id).push(player);
                        });
                        
                        // Update corridor highlighting
                        this.updateCorridorHighlighting();
                    }

                    // Highlight corridors with players in transit
                    updateCorridorHighlighting() {
                        this.corridorPolylines.forEach((polyline, corridorId) => {
                            const hasPlayers = this.playersInTransit.has(corridorId);
                            const hasNPCs = this.npcsInTransit.has(corridorId);
                            const element = polyline.getElement();
                            
                            if (element) {
                                // Remove all transit classes
                                element.classList.remove('corridor-active', 'corridor-player-transit', 'corridor-npc-transit');
                                
                                if (hasPlayers && hasNPCs) {
                                    // Both players and NPCs - use player color (blue) as priority
                                    element.classList.add('corridor-player-transit');
                                } else if (hasPlayers) {
                                    // Only players - blue pulse
                                    element.classList.add('corridor-player-transit');
                                } else if (hasNPCs) {
                                    // Only NPCs - yellow pulse
                                    element.classList.add('corridor-npc-transit');
                                }
                            }
                        });
                    }
                    toggleRoutes() {
                        this.showRoutes = !this.showRoutes;
                        const btn = document.getElementById('toggle-routes-btn');
                        
                        this.applyRouteVisibility();
                        
                        if (btn) {
                            if (this.showRoutes) {
                                btn.textContent = 'HIDE ROUTES';
                                btn.classList.add('toggle-active');
                            } else {
                                btn.textContent = 'SHOW ROUTES';
                                btn.classList.remove('toggle-active');
                                // Clear corridor selection when hiding routes
                                this.clearCorridorSelection();
                            }
                        }
                    }
                    toggleNPCs() {
                        this.showNPCs = !this.showNPCs;
                        const btn = document.getElementById('toggle-npcs-btn');
                        
                        this.applyNPCVisibility();
                        
                        if (btn) {
                            if (this.showNPCs) {
                                btn.textContent = 'NPCS';
                                btn.classList.add('toggle-active');
                            } else {
                                btn.textContent = 'NPCS';
                                btn.classList.remove('toggle-active');
                            }
                        }
                    }
                    
                    applyNPCVisibility() {
                        this.locations.forEach(location => {
                            if (location.npcIndicator) {
                                if (this.showNPCs) {
                                    location.npcIndicator.getElement()?.classList.remove('routes-hidden');
                                } else {
                                    location.npcIndicator.getElement()?.classList.add('routes-hidden');
                                }
                            }
                        });
                    }
                    applyRouteVisibility() {
                        this.corridors.forEach(corridor => {
                            // Apply visibility to the visible polyline
                            if (corridor.polyline) {
                                if (this.showRoutes) {
                                    corridor.polyline.getElement()?.classList.remove('routes-hidden');
                                } else {
                                    corridor.polyline.getElement()?.classList.add('routes-hidden');
                                }
                            }
                            
                            // Apply interactivity to the click target
                            if (corridor.clickTarget) {
                                if (this.showRoutes) {
                                    corridor.clickTarget.setStyle({interactive: true});
                                    corridor.clickTarget.getElement()?.classList.remove('routes-hidden');
                                } else {
                                    corridor.clickTarget.setStyle({interactive: false});
                                    corridor.clickTarget.getElement()?.classList.add('routes-hidden');
                                }
                            }
                        });
                        
                        this.routePolylines.forEach(routeLine => {
                            if (this.showRoutes) {
                                routeLine.getElement()?.classList.remove('routes-hidden');
                            } else {
                                routeLine.getElement()?.classList.add('routes-hidden');
                            }
                        });
                    }
                    updateNPCs(npcs) {
                        this.npcs.clear();
                        
                        npcs.forEach(npc => {
                            if (!this.npcs.has(npc.location_id)) {
                                this.npcs.set(npc.location_id, []);
                            }
                            this.npcs.get(npc.location_id).push(npc);
                        });
                        
                        this.locations.forEach((location, locationId) => {
                            this.updateLocationWithNPCs(location, this.npcs.get(locationId) || []);
                        });
                        
                        if (this.selectedLocation) {
                            this.updateLocationPanel(this.selectedLocation);
                        }
                    }
                    
                    updateLocationWithNPCs(location, npcsHere) {
                        const marker = location.marker;
                        if (!marker) return;

                        if (location.npcIndicator) {
                            this.map.removeLayer(location.npcIndicator);
                            delete location.npcIndicator;
                        }

                        if (npcsHere.length > 0) {
                            const indicator = L.circleMarker([location.y_coord, location.x_coord], {
                                radius: 16,
                                fillColor: 'transparent',
                                color: 'var(--warning-color)',
                                weight: 3,
                                opacity: 1,
                                fillOpacity: 0,
                                className: 'npc-presence-indicator',
                                interactive: false,
                                pane: 'shadowPane'
                            });

                            indicator.addTo(this.map);
                            location.npcIndicator = indicator;
                            
                            marker.bringToFront();
                        }
                    }
                    updatePlayers(players) {
                        const playerCount = document.getElementById('player-count');
                        if (playerCount) {
                            // Use total count from server data, or calculate if not provided
                            const totalCount = this.galaxyData?.total_player_count || 
                                              (players.length + (this.playersInTransit.size > 0 ? 
                                               Array.from(this.playersInTransit.values()).flat().length : 0));
                            playerCount.textContent = `${totalCount} CONTACTS`;
                        }
                        
                        this.players.clear();
                        
                        players.forEach(player => {
                            if (!this.players.has(player.location_id)) {
                                this.players.set(player.location_id, []);
                            }
                            this.players.get(player.location_id).push(player);
                        });
                        
                        this.locations.forEach((location, locationId) => {
                            this.updateLocationWithPlayers(location, this.players.get(locationId) || []);
                        });
                        
                        if (this.selectedLocation) {
                            this.updateLocationPanel(this.selectedLocation);
                        }
                    }
                    
                    updateLocationWithPlayers(location, playersHere) {
                        const marker = location.marker;
                        if (!marker) return;

                        if (location.playerIndicator) {
                            this.map.removeLayer(location.playerIndicator);
                            delete location.playerIndicator;
                        }

                        if (playersHere.length > 0) {
                            const indicator = L.circleMarker([location.y_coord, location.x_coord], {
                                radius: 18,
                                fillColor: 'transparent',
                                color: 'var(--success-color)',
                                weight: 3,
                                opacity: 1,
                                fillOpacity: 0,
                                className: 'player-presence-indicator',
                                interactive: false,
                                pane: 'shadowPane' // Put it in a lower layer
                            });

                            indicator.addTo(this.map);
                            location.playerIndicator = indicator;
                            
                            // Ensure the main marker stays clickable by bringing it to front
                            marker.bringToFront();
                        }
                    }
                    updateNPCsInTransit(transitData) {
                        this.npcsInTransit.clear();
                        
                        transitData.forEach(npc => {
                            if (!this.npcsInTransit.has(npc.corridor_id)) {
                                this.npcsInTransit.set(npc.corridor_id, []);
                            }
                            this.npcsInTransit.get(npc.corridor_id).push(npc);
                        });
                        
                        // Update corridor highlighting
                        this.updateCorridorHighlighting();
                    }
                    selectLocation(location) {
                        this.selectedLocation = location;
                        this.updateLocationPanel(location);
                        this.showLocationPanel();
                        
                        this.clearHighlights();
                        this.highlightLocation(location, 'var(--primary-color)');
                    }
                    
                    async updateLocationPanel(location) {
                        const titleElement = document.getElementById('location-title');
                        const detailsElement = document.getElementById('location-details');
                        
                        if (!titleElement || !detailsElement) return;
                        
                        titleElement.textContent = location.name.toUpperCase();
                        
                        const playersHere = this.players.get(location.location_id) || [];
                        const npcsHere = this.npcs.get(location.location_id) || [];
                        const staticNPCs = location.static_npcs || [];
                        const subLocations = await this.getSubLocations(location.location_id);
                        
                        const wealthDisplay = this.getWealthDisplay(location.wealth_level);
                        const typeIcon = this.getLocationTypeIcon(location.location_type);
                        
                        // Create alignment panel if not neutral
                        let alignmentPanel = '';
                        if (location.alignment === 'loyalist') {
                            alignmentPanel = `
                                <div class="alignment-panel alignment-loyalist">
                                    🛡️ LOYALISTS
                                </div>
                            `;
                        } else if (location.alignment === 'outlaw') {
                            alignmentPanel = `
                                <div class="alignment-panel alignment-outlaw">
                                    ⚔️ OUTLAWS
                                </div>
                            `;
                        }
                        
                        const detailsHtml = `
                            ${alignmentPanel}
                            <div class="location-detail">
                                <strong>${typeIcon} TYPE:</strong> ${location.location_type.toUpperCase()}
                            </div>
                            <div class="location-detail">
                                <strong>💰 WEALTH:</strong> ${wealthDisplay}
                            </div>
                            <div class="location-detail">
                                <strong>👥 POPULATION:</strong> ${location.population?.toLocaleString() || 'UNKNOWN'}
                            </div>
                            <div class="location-detail">
                                <strong>📍 COORDINATES:</strong> (${location.x_coord}, ${location.y_coord})
                            </div>
                            <div class="location-detail">
                                <strong>📄 DESCRIPTION:</strong>
                                <div style="margin-top: 0.5rem; font-style: italic; color: var(--text-secondary); text-transform: none;">
                                    ${location.description || 'No description available.'}
                                </div>
                            </div>
                            ${subLocations.length > 0 ? `
                                <div class="sub-locations">
                                    <strong>🏢 AVAILABLE AREAS:</strong>
                                    ${subLocations.map(sub => `
                                        <div class="sub-location-item">
                                            ${sub.icon || '📍'} ${sub.name.toUpperCase()} - ${sub.description}
                                        </div>
                                    `).join('')}
                                </div>
                            ` : ''}
                            ${playersHere.length > 0 ? `
                                <div class="players-list">
                                    <strong>👥 CONTACTS PRESENT (${playersHere.length}):</strong>
                                    ${playersHere.map(player => `
                                        <div class="player-item">
                                            <span class="status-indicator status-online"></span>
                                            ${player.name.toUpperCase()}
                                        </div>
                                    `).join('')}
                                </div>
                            ` : ''}
                            ${npcsHere.length > 0 ? `
                                <div class="players-list">
                                    <strong>🤖 NPCS PRESENT (${npcsHere.length}):</strong>
                                    ${npcsHere.map(npc => `
                                        <div class="player-item">
                                            <span class="status-indicator" style="background: var(--warning-color); box-shadow: 0 0 8px var(--warning-color);"></span>
                                            ${npc.name.toUpperCase()} (${npc.callsign}) - ${npc.ship_name}
                                        </div>
                                    `).join('')}
                                </div>
                            ` : ''}
                            ${staticNPCs.length > 0 ? `
                                <div class="players-list">
                                    <strong>👤 NOTABLE INHABITANTS (${staticNPCs.length}):</strong>
                                    ${staticNPCs.map(npc => `
                                        <div class="player-item">
                                            <span class="status-indicator" style="background: var(--accent-color); box-shadow: 0 0 8px var(--accent-color);"></span>
                                            ${npc.name.toUpperCase()} (${npc.age}) - ${npc.occupation.toUpperCase()}
                                            <div style="font-size: 0.7rem; color: var(--text-muted); margin-left: 1rem; font-style: italic;">
                                                ${npc.personality}
                                            </div>
                                        </div>
                                    `).join('')}
                                </div>
                            ` : ''}
                            ${playersHere.length === 0 && npcsHere.length === 0 && staticNPCs.length === 0 ? '<div class="location-detail"><em>No contacts, NPCs, or notable inhabitants currently present</em></div>' : ''}
                        `;
                        
                        detailsElement.innerHTML = detailsHtml;
                    }
                    
                    
                    getWealthDisplay(wealthLevel) {
                        if (wealthLevel >= 9) return '👑 OPULENT';
                        if (wealthLevel >= 7) return '💎 WEALTHY';
                        if (wealthLevel >= 5) return '💰 PROSPEROUS';
                        if (wealthLevel >= 3) return '⚖️ AVERAGE';
                        if (wealthLevel >= 2) return '📉 POOR';
                        if (wealthLevel >= 1) return '🗑️ IMPOVERISHED';
                        return '❓ UNKNOWN';
                    }
                    
                    getLocationTypeIcon(locationType) {
                        const icons = {
                            'Colony': '🏘️',
                            'Space Station': '🛰️',
                            'Outpost': '🏭',
                            'Transit Gate': '🌌'
                        };
                        return icons[locationType] || '📍';
                    }
                    
                    async getSubLocations(locationId) {
                        try {
                            const response = await fetch(`/api/location/${locationId}/sub-locations`);
                            if (response.ok) {
                                return await response.json();
                            }
                        } catch (error) {
                            console.error('Failed to fetch sub-locations:', error);
                        }
                        return [];
                    }
                    
                    showLocationPanel() {
                        const panel = document.getElementById('location-panel');
                        if (panel) {
                            panel.classList.remove('hidden');
                        }
                    }
                    
                    hideLocationPanel() {
                        const panel = document.getElementById('location-panel');
                        if (panel) {
                            panel.classList.add('hidden');
                        }
                        this.selectedLocation = null;
                        this.clearHighlights();
                    }
                    
                    searchLocations(query) {
                        this.clearHighlights();
                        
                        if (!query.trim()) return;
                        
                        const results = [];
                        const queryLower = query.toLowerCase();
                        
                        this.locations.forEach((location) => {
                            if (location.name.toLowerCase().includes(queryLower) ||
                                location.location_type.toLowerCase().includes(queryLower)) {
                                results.push(location);
                            }
                        });
                        
                        if (results.length > 0) {
                            results.forEach(location => {
                                this.highlightLocation(location, 'var(--primary-color)');
                            });
                            
                            if (results.length === 1) {
                                this.map.setView([results[0].y_coord, results[0].x_coord], 4);
                                this.selectLocation(results[0]);
                            } else {
                                this.fitBoundsToLocations(results);
                            }
                        }
                    }
                    
                    clearSearch() {
                        const searchInput = document.getElementById('location-search');
                        if (searchInput) {
                            searchInput.value = '';
                        }
                        this.clearHighlights();
                    }
                    
                    highlightLocation(location, color = '#ffff00') {
                        if (!location.marker) return;
                        
                        const originalOptions = location.marker.options;
                        location.marker.setStyle({
                            ...originalOptions,
                            color: color,
                            weight: 4,
                            opacity: 1,
                            className: `${originalOptions.className} location-highlight`
                        });
                        
                        this.highlightedLocations.push(location);
                    }
                    
                    clearHighlights() {
                        this.highlightedLocations.forEach(location => {
                            if (location.marker) {
                                const originalOptions = location.marker.options;
                                location.marker.setStyle({
                                    ...originalOptions,
                                    color: '#ffffff',
                                    weight: 2,
                                    opacity: 1,
                                    className: originalOptions.className.replace(' location-highlight', '')
                                });
                            }
                        });
                        this.highlightedLocations = [];
                    }
                    
                    async plotRoute(fromId, toId) {
                        try {
                            const response = await fetch(`/api/route/${fromId}/${toId}`);
                            if (!response.ok) throw new Error('Route calculation failed');
                            
                            const routeData = await response.json();
                            
                            if (routeData.error) {
                                alert('NO ROUTE FOUND BETWEEN SELECTED LOCATIONS');
                                return;
                            }
                            
                            this.displayRoute(routeData);
                            
                        } catch (error) {
                            console.error('Error plotting route:', error);
                            alert('FAILED TO CALCULATE ROUTE');
                        }
                    }
                    
                    displayRoute(routeData) {
                        this.clearRoute();
                        
                        if (!routeData.path || routeData.path.length < 2) return;
                        
                        const routeCoords = routeData.path.map(location => [location.y_coord, location.x_coord]);
                        const routeLine = L.polyline(routeCoords, {
                            color: '#ffff00',
                            weight: 5,
                            opacity: 0.9,
                            className: 'route-highlight'
                        });
                        
                        routeLine.addTo(this.map);
                        this.routePolylines.push(routeLine);
                        
                        if (!this.showRoutes) {
                            routeLine.getElement()?.classList.add('routes-hidden');
                        }
                        
                        routeData.path.forEach(location => {
                            const loc = this.locations.get(location.location_id);
                            if (loc) {
                                this.highlightLocation(loc, '#ffff00');
                            }
                        });
                        
                        this.map.fitBounds(routeLine.getBounds(), { padding: [20, 20] });
                        this.currentRoute = routeData;
                        
                        const clearBtn = document.getElementById('clear-route-btn');
                        if (clearBtn) clearBtn.disabled = false;
                    }
                    
                    clearRoute() {
                        this.routePolylines.forEach(polyline => {
                            this.map.removeLayer(polyline);
                        });
                        this.routePolylines = [];
                        
                        this.clearHighlights();
                        this.currentRoute = null;
                        
                        const clearBtn = document.getElementById('clear-route-btn');
                        if (clearBtn) clearBtn.disabled = true;
                    }
                    
                    populateRouteSelects() {
                        const fromSelect = document.getElementById('route-from');
                        const toSelect = document.getElementById('route-to');
                        
                        if (!fromSelect || !toSelect) return;
                        
                        [fromSelect, toSelect].forEach(select => {
                            while (select.children.length > 1) {
                                select.removeChild(select.lastChild);
                            }
                        });
                        
                        const sortedLocations = Array.from(this.locations.values())
                            .sort((a, b) => a.name.localeCompare(b.name));
                        
                        sortedLocations.forEach(location => {
                            [fromSelect, toSelect].forEach(select => {
                                const option = document.createElement('option');
                                option.value = location.location_id;
                                option.textContent = `${location.name.toUpperCase()} (${location.location_type.toUpperCase()})`;
                                select.appendChild(option);
                            });
                        });
                        
                        fromSelect.disabled = false;
                        toSelect.disabled = false;
                        
                        [fromSelect, toSelect].forEach(select => {
                            select.addEventListener('change', () => {
                                const plotBtn = document.getElementById('plot-route-btn');
                                if (plotBtn) {
                                    plotBtn.disabled = !(fromSelect.value && toSelect.value && fromSelect.value !== toSelect.value);
                                }
                            });
                        });
                    }
                    
                    fitMapToBounds() {
                        if (this.locations.size === 0) return;
                        
                        const bounds = L.latLngBounds();
                        this.locations.forEach(location => {
                            bounds.extend([location.y_coord, location.x_coord]);
                        });
                        
                        this.map.fitBounds(bounds, { padding: [20, 20] });
                    }
                    
                    fitBoundsToLocations(locations) {
                        if (locations.length === 0) return;
                        
                        const bounds = L.latLngBounds();
                        locations.forEach(location => {
                            bounds.extend([location.y_coord, location.x_coord]);
                        });
                        
                        this.map.fitBounds(bounds, { padding: [40, 40] });
                    }
                    
                toggleLabels() {
                    this.showLabels = !this.showLabels;
                    const btn = document.getElementById('toggle-labels-btn');
                    
                    if (this.showLabels) {
                        this.addLocationLabels();
                        if (btn) {
                            btn.textContent = 'HIDE LABELS';
                            btn.classList.add('toggle-active');
                        }
                    } else {
                        this.removeLocationLabels();
                        if (btn) {
                            btn.textContent = 'SHOW LABELS';
                            btn.classList.remove('toggle-active');
                        }
                    }
                }
                
                addLocationLabels() {
                    this.removeLocationLabels();
                    
                    const zoom = this.map.getZoom();
                    const bounds = this.map.getBounds();
                    
                    // Get all visible locations
                    let visibleLocations = [];
                    this.locations.forEach(location => {
                        const point = L.latLng(location.y_coord, location.x_coord);
                        if (bounds.contains(point)) {
                            visibleLocations.push(location);
                        }
                    });

                    // Simple, predictable logic: if few locations visible, show all labels
                    // If many locations visible, show only the most important ones
                    let locationsToLabel;
                    
                    if (visibleLocations.length <= 8) {
                        // When zoomed in close or few locations visible, show ALL labels
                        locationsToLabel = visibleLocations;
                    } else if (zoom >= 2) {
                        // High zoom with many locations - show top 75%
                        visibleLocations.sort((a, b) => this.getLocationImportance(b) - this.getLocationImportance(a));
                        locationsToLabel = visibleLocations.slice(0, Math.floor(visibleLocations.length * 0.75));
                    } else if (zoom >= 0) {
                        // Medium zoom - show top 50%
                        visibleLocations.sort((a, b) => this.getLocationImportance(b) - this.getLocationImportance(a));
                        locationsToLabel = visibleLocations.slice(0, Math.floor(visibleLocations.length * 0.5));
                    } else if (zoom >= -2) {
                        // Low zoom - show top 25%
                        visibleLocations.sort((a, b) => this.getLocationImportance(b) - this.getLocationImportance(a));
                        locationsToLabel = visibleLocations.slice(0, Math.max(1, Math.floor(visibleLocations.length * 0.25)));
                    } else {
                        // Very low zoom - show only top 10 most important
                        visibleLocations.sort((a, b) => this.getLocationImportance(b) - this.getLocationImportance(a));
                        locationsToLabel = visibleLocations.slice(0, Math.min(10, visibleLocations.length));
                    }

                    // Initialize timeout tracking
                    if (!this.pendingLabelTimeouts) {
                        this.pendingLabelTimeouts = [];
                    }

                    // Add labels immediately instead of with delays to prevent conflicts
                    locationsToLabel.forEach((location) => {
                        this.addSimpleLabel(location);
                    });
                }

                
                // Replace the existing addSimpleLabel function
                addSimpleLabel(location) {
                    const zoom = this.map.getZoom();
                    const labelSize = this.getSimpleLabelSize(zoom);
                    
                    // Simple offset pattern - cycle through positions to avoid overlap
                    const offsetPatterns = [
                        [0, -35],      // Above
                        [30, -20],     // Top-right
                        [30, 20],      // Bottom-right
                        [0, 35],       // Below
                        [-30, 20],     // Bottom-left
                        [-30, -20],    // Top-left
                        [40, 0],       // Right
                        [-40, 0]       // Left
                    ];
                    
                    // Use location ID to get consistent positioning
                    const patternIndex = location.location_id % offsetPatterns.length;
                    const [offsetX, offsetY] = offsetPatterns[patternIndex];
                    
                    // Scale offset with zoom
                    const zoomScale = Math.max(0.7, Math.min(1.5, 1.0 + (zoom * 0.1)));
                    const finalOffsetX = offsetX * zoomScale;
                    const finalOffsetY = offsetY * zoomScale;
                    
                    // Calculate label position
                    const basePoint = this.map.latLngToContainerPoint([location.y_coord, location.x_coord]);
                    const labelPoint = L.point(basePoint.x + finalOffsetX, basePoint.y + finalOffsetY);
                    const labelPosition = this.map.containerPointToLatLng(labelPoint);
                    
                    // Check if position is within map bounds
                    if (!this.map.getBounds().contains(labelPosition)) {
                        // Try opposite offset if out of bounds
                        const fallbackPoint = L.point(basePoint.x - finalOffsetX, basePoint.y - finalOffsetY);
                        const fallbackPosition = this.map.containerPointToLatLng(fallbackPoint);
                        if (this.map.getBounds().contains(fallbackPosition)) {
                            this.createLabelMarker(location, fallbackPosition, labelSize, zoom);
                        }
                        return;
                    }
                    
                    this.createLabelMarker(location, labelPosition, labelSize, zoom);
                }

                // Add this new function to create properly sized label markers
                createLabelMarker(location, position, labelSize, zoom) {
                    const wealthClass = this.getWealthClass(location.wealth_level);
                    const zoomClass = this.getZoomClass(zoom);
                    const labelText = this.formatLabelText(location.name, zoom);
                    
                    // Calculate proper text dimensions
                    const textLength = labelText.length;
                    const charWidth = zoom >= 2 ? 8 : zoom >= 0 ? 7 : 6;
                    const calculatedWidth = Math.max(labelSize.width, textLength * charWidth + 20);
                    
                    const label = L.marker(position, {
                        icon: L.divIcon({
                            className: `location-label ${wealthClass} ${zoomClass}`,
                            html: `<div class="label-text">${labelText}</div>`,
                            iconSize: [calculatedWidth, labelSize.height],
                            iconAnchor: [calculatedWidth / 2, labelSize.height / 2]
                        }),
                        interactive: false
                    });

                    label.addTo(this.map);
                    location.label = label;
                }
                formatLabelText(name, zoom) {
                    // Truncate long names at low zoom levels
                    if (zoom < -1 && name.length > 12) {
                        return name.substring(0, 10).toUpperCase() + '...';
                    } else if (zoom < 1 && name.length > 15) {
                        return name.substring(0, 12).toUpperCase() + '...';
                    }
                    return name.toUpperCase();
                }

                getSimpleLabelSize(zoom) {
                    if (zoom >= 3) {
                        return { width: 120, height: 28 };
                    } else if (zoom >= 1) {
                        return { width: 100, height: 24 };
                    } else if (zoom >= -1) {
                        return { width: 80, height: 20 };
                    } else {
                        return { width: 70, height: 18 };
                    }
                }

                getLocationImportance(location) {
                    const typeWeights = {
                        'Space Station': 100,
                        'Colony': 80,
                        'Transit Gate': 60,
                        'Outpost': 40
                    };
                    
                    const baseScore = typeWeights[location.location_type] || 20;
                    const wealthBonus = (location.wealth_level || 1) * 10;
                    const populationBonus = Math.log10((location.population || 1) + 1) * 5;
                    
                    return baseScore + wealthBonus + populationBonus;
                }

                getWealthClass(wealthLevel) {
                    if (wealthLevel >= 7) return 'wealth-high';
                    if (wealthLevel >= 4) return 'wealth-medium';
                    return 'wealth-low';
                }

                getZoomClass(zoom) {
                    if (zoom >= 3) return 'zoom-large';
                    if (zoom >= 0) return 'zoom-medium';
                    return 'zoom-small';
                }

                updateLabelsForZoom() {
                    if (this.showLabels) {
                        clearTimeout(this.labelUpdateTimeout);
                        this.labelUpdateTimeout = setTimeout(() => {
                            this.addLocationLabels();
                        }, 200);
                    }
                }
                // Fix the removeLocationLabels function
                removeLocationLabels() {
                    this.locations.forEach(location => {
                        if (location.label) {
                            this.map.removeLayer(location.label);
                            location.label = null;
                        }
                    });
                }

                // Update the createLocationMarker function to use different shapes and sizes
                createLocationMarker(location) {
                    const colors = {
                        'Colony': 'var(--success-color)',
                        'Space Station': 'var(--primary-color)',
                        'Outpost': 'var(--warning-color)',
                        'Transit Gate': '#ffdd00'
                    };
                    
                    const color = colors[location.location_type] || '#ffffff';
                    const zoom = this.map.getZoom();
                    
                    // Apply consistent zoom scaling to ALL locations
                    let finalSize;
                    if (zoom < -1) {
                        finalSize = 12; // All tiny when zoomed way out
                    } else if (zoom < 0) {
                        finalSize = 13; // All small when zoomed out
                    } else if (zoom < 1) {
                        finalSize = 14; // All medium when mid-zoom
                    } else {
                        finalSize = 15; // All normal when zoomed in
                    }
                    
                    return this.createShapedMarker(location, color, finalSize);
                }
                calculatePopulationSize(population) {
                    // Disabled to ensure uniform scaling
                    return 0;
                }
                getBaseMarkerSize(locationType) {
                    // Uniform base size - differentiation comes from shape, not size
                    return 15;
                }
                createShapedMarker(location, color, size) {
                    const markerOptions = {
                        radius: size,
                        fillColor: '#ffffff',
                        color: '#ffffff',
                        weight: 2,
                        opacity: 1,
                        fillOpacity: 0.9,
                        className: `location-marker ${location.location_type.toLowerCase().replace(' ', '-')}`
                    };

                    let marker;
                    
                    // Use different shapes based on location type
                    switch(location.location_type.toLowerCase()) {
                        case 'colony':
                            marker = L.circleMarker([location.y_coord, location.x_coord], markerOptions);
                            break;
                            
                        case 'space_station':
                            const trianglePoints = this.getTrianglePoints(location.x_coord, location.y_coord, size);
                            marker = L.polygon(trianglePoints, {
                                ...markerOptions,
                                className: `${markerOptions.className} triangle-marker`
                            });
                            break;
                            
                        case 'outpost':
                            const squarePoints = this.getSquarePoints(location.x_coord, location.y_coord, size);
                            marker = L.polygon(squarePoints, {
                                ...markerOptions,
                                className: `${markerOptions.className} square-marker`
                            });
                            break;
                            
                        case 'gate':
                            const diamondPoints = this.getDiamondPoints(location.x_coord, location.y_coord, size);
                            marker = L.polygon(diamondPoints, {
                                ...markerOptions,
                                className: `${markerOptions.className} diamond-marker`
                            });
                            break;
                            
                        default:
                            marker = L.circleMarker([location.y_coord, location.x_coord], markerOptions);
                            break;
                    }
                    
                    marker.on('click', (e) => {
                        L.DomEvent.stopPropagation(e);
                        this.selectLocation(location);  // ✅ CORRECT - passing location object
                    });
                    
                    return marker;
                }
                            

                getTrianglePoints(x, y, size) {
                    const offset = size * 0.018; // Slightly larger for better visibility
                    return [
                        [y + offset, x],           // Top
                        [y - offset, x - offset],  // Bottom left
                        [y - offset, x + offset]   // Bottom right
                    ];
                }

                getSquarePoints(x, y, size) {
                    const offset = size * 0.015; // Slightly larger for better visibility
                    return [
                        [y + offset, x - offset],  // Top left
                        [y + offset, x + offset],  // Top right
                        [y - offset, x + offset],  // Bottom right
                        [y - offset, x - offset]   // Bottom left
                    ];
                }

                getDiamondPoints(x, y, size) {
                    const offset = size * 0.018; // Slightly larger for better visibility
                    return [
                        [y + offset, x],           // Top
                        [y, x + offset],           // Right
                        [y - offset, x],           // Bottom
                        [y, x - offset]            // Left
                    ];
                }
                    
                    updateConnectionStatus(text, color) {
                        const indicator = document.getElementById('connection-indicator');
                        const statusText = document.getElementById('connection-text');
                        
                        if (indicator && statusText) {
                            indicator.style.color = color;
                            statusText.textContent = text;
                        }
                    }
                    
                    hideLoadingOverlay() {
                        const overlay = document.getElementById('loading-overlay');
                        if (overlay) {
                            setTimeout(() => {
                                overlay.classList.add('hidden');
                            }, 1500);
                        }
                    }
                }

                let galaxyMap;

                // Initialize map when page loads
                document.addEventListener('DOMContentLoaded', () => {
                    galaxyMap = new GalaxyMap();
                });