# utils/architecture_validator.py
"""
Architecture validation utility for maintaining proper galaxy routing rules.
Ensures compliance with ROUTE-LOCATION-RULES.md during corridor shifts and changes.
"""

class ArchitectureValidator:
    def __init__(self, db):
        self.db = db
    
    async def validate_and_fix_architecture(self, silent: bool = True) -> dict:
        """
        Validate and fix all architecture violations.
        Returns a summary of fixes applied.
        """
        fixes = {
            'cross_system_removed': 0,
            'major_to_gate_fixed': 0,
            'major_to_major_removed': 0,
            'missing_local_created': 0,
            'unused_gate_fixed': 0,
            'moving_gate_fixed': 0,
            'active_gate_fixed': 0,
            'gated_violations_removed': 0,
            'duplicates_removed': 0
        }
        
        # CRITICAL FIX: Clean up ALL duplicate routes first (not just local space)
        duplicates_removed = await self._remove_duplicate_routes(fixes, silent)
        if duplicates_removed > 0 and not silent:
            print(f"🧹 Removed {duplicates_removed} duplicate routes between location pairs")
        
        # PERFORMANCE SAFEGUARD: Check if route counts are still excessive after cleanup
        current_local_routes = self.db.execute_query(
            "SELECT COUNT(*) FROM corridors WHERE corridor_type = 'local_space'",
            fetch='one'
        )[0]
        
        total_routes = self.db.execute_query("SELECT COUNT(*) FROM corridors", fetch='one')[0]
        
        if current_local_routes > 200 or total_routes > 1000:  # Safety limits
            if not silent:
                print(f"⚠️ WARNING: Route counts still excessive after cleanup (Local: {current_local_routes}, Total: {total_routes}). Skipping route creation to prevent database overload.")
            # Still run other validations but skip route creation
            await self._fix_cross_system_violations(fixes, silent)
            await self._remove_major_to_major_gated(fixes, silent)
            await self._remove_gated_major_to_gate(fixes, silent)
            await self._fix_gate_connectivity_by_status(fixes, silent)
            return fixes
        
        # Step 1: Remove cross-system architectural violations
        await self._fix_cross_system_violations(fixes, silent)
        
        # Step 2: Remove direct major-to-major gated connections (keep ungated only)
        await self._remove_major_to_major_gated(fixes, silent)
        
        # Step 3: Remove direct gated connections from major locations to gates
        await self._remove_gated_major_to_gate(fixes, silent)
        
        # Step 4: Ensure all major locations have local space connections to gates in their system
        await self._ensure_local_space_connections(fixes, silent)
        
        # Step 5: Fix gate-specific connectivity based on status
        await self._fix_gate_connectivity_by_status(fixes, silent)
        
        return fixes
    
    async def _remove_duplicate_routes(self, fixes: dict, silent: bool = True) -> int:
        """Remove duplicate routes between the same location pairs with same corridor type"""
        # Find location pairs with multiple routes of THE SAME TYPE (true duplicates)
        duplicates = self.db.execute_query(
            """SELECT origin_location, destination_location, corridor_type, COUNT(*) as count,
                      STRING_AGG(corridor_id || ':' || name, ',') as corridor_info
               FROM corridors 
               GROUP BY origin_location, destination_location, corridor_type
               HAVING COUNT(*) > 1""",
            fetch='all'
        )
        
        routes_removed = 0
        for origin_id, dest_id, corridor_type, count, corridor_info_str in duplicates:
            # Parse corridor info (format: "id:name,id:name,...")
            corridor_data = []
            for info in corridor_info_str.split(','):
                parts = info.split(':', 1)  # Split on first colon only
                if len(parts) == 2:
                    corridor_id = int(parts[0])
                    corridor_name = parts[1]
                    corridor_data.append((corridor_id, corridor_name))
            
            if len(corridor_data) <= 1:
                continue  # Skip if somehow no duplicates
            
            # Keep the first route, delete the rest
            routes_to_delete = corridor_data[1:]  # Keep corridor_data[0], delete the rest
            
            for corridor_id, corridor_name in routes_to_delete:
                self.db.execute_query(
                    "DELETE FROM corridors WHERE corridor_id = %s",
                    (corridor_id,)
                )
                routes_removed += 1
            
            if not silent:
                route_names = [name for _, name in routes_to_delete]
                print(f"🧹 Cleaned up {len(routes_to_delete)} duplicate {corridor_type} routes between locations {origin_id} → {dest_id}")
                print(f"    Removed: {', '.join(route_names[:3])}{'...' if len(route_names) > 3 else ''}")
        
        fixes['duplicates_removed'] = routes_removed
        return routes_removed
    
    async def _fix_cross_system_violations(self, fixes: dict, silent: bool = True):
        """Remove any connections that violate system-based architecture"""
        cross_system_violations = self.db.execute_query(
            """SELECT c.corridor_id, c.name, lo.name as origin_name, ld.name as dest_name,
                      lo.location_type as origin_type, ld.location_type as dest_type
               FROM corridors c
               JOIN locations lo ON c.origin_location = lo.location_id  
               JOIN locations ld ON c.destination_location = ld.location_id
               WHERE (
                   (lo.location_type IN ('colony', 'space_station', 'outpost') AND ld.location_type = 'gate') OR
                   (lo.location_type = 'gate' AND ld.location_type IN ('colony', 'space_station', 'outpost'))
               )
               AND lo.system_name != ld.system_name
               AND c.corridor_type != 'ungated'""",
            fetch='all'
        )
        
        for corridor_id, name, origin_name, dest_name, origin_type, dest_type in cross_system_violations:
            self.db.execute_query("DELETE FROM corridors WHERE corridor_id = %s", (corridor_id,))
            fixes['cross_system_removed'] += 1
            if not silent:
                connection_type = f"{origin_type} ↔ {dest_type}"
                print(f"🗑️ Removed cross-system violation: {name} - {connection_type} ({origin_name} → {dest_name})")

    async def _remove_major_to_major_gated(self, fixes: dict, silent: bool = True):
        """Remove direct gated connections between major locations (keep ungated only)"""
        major_to_major_gated = self.db.execute_query(
            """SELECT c.corridor_id, c.name, lo.name as origin_name, ld.name as dest_name
               FROM corridors c
               JOIN locations lo ON c.origin_location = lo.location_id  
               JOIN locations ld ON c.destination_location = ld.location_id
               WHERE lo.location_type IN ('colony', 'space_station', 'outpost')
               AND ld.location_type IN ('colony', 'space_station', 'outpost')
               AND c.corridor_type != 'ungated'""",
            fetch='all'
        )
        
        for corridor_id, name, origin_name, dest_name in major_to_major_gated:
            self.db.execute_query("DELETE FROM corridors WHERE corridor_id = %s", (corridor_id,))
            fixes['major_to_major_removed'] += 1
            if not silent:
                print(f"🗑️ Removed major-to-major gated: {name} ({origin_name} → {dest_name})")

    async def _remove_gated_major_to_gate(self, fixes: dict, silent: bool = True):
        """Remove any direct gated connections from major locations to gates"""
        gated_major_to_gate = self.db.execute_query(
            """SELECT c.corridor_id, c.name, lo.name as origin_name, ld.name as dest_name,
                      lo.location_type as origin_type, ld.location_type as dest_type
               FROM corridors c
               JOIN locations lo ON c.origin_location = lo.location_id  
               JOIN locations ld ON c.destination_location = ld.location_id
               WHERE (
                   (lo.location_type IN ('colony', 'space_station', 'outpost') AND ld.location_type = 'gate') OR
                   (lo.location_type = 'gate' AND ld.location_type IN ('colony', 'space_station', 'outpost'))
               )
               AND c.corridor_type != 'local_space' 
               AND c.corridor_type != 'ungated'""",
            fetch='all'
        )
        
        for corridor_id, name, origin_name, dest_name, origin_type, dest_type in gated_major_to_gate:
            self.db.execute_query("DELETE FROM corridors WHERE corridor_id = %s", (corridor_id,))
            fixes['gated_violations_removed'] += 1
            if not silent:
                connection_type = f"{origin_type} ↔ {dest_type}"
                print(f"🗑️ Removed gated major-gate connection: {name} - {connection_type} ({origin_name} → {dest_name})")

    async def _ensure_local_space_connections(self, fixes: dict, silent: bool = True):
        """Ensure all major locations have proper local space connections to gates in their system"""
        # Get all systems and their major locations and gates
        systems_data = self.db.execute_query(
            """SELECT DISTINCT l.system_name,
                      STRING_AGG(CASE WHEN l.location_type IN ('colony', 'space_station', 'outpost') 
                                        THEN l.location_id || ':' || l.name END, ',') as majors,
                      STRING_AGG(CASE WHEN l.location_type = 'gate' 
                                        THEN l.location_id || ':' || l.name || ':' || l.gate_status END, ',') as gates
               FROM locations l
               WHERE l.system_name IS NOT NULL 
               AND l.location_type IN ('colony', 'space_station', 'outpost', 'gate')
               GROUP BY l.system_name
               HAVING STRING_AGG(CASE WHEN l.location_type IN ('colony', 'space_station', 'outpost') 
                                        THEN l.location_id || ':' || l.name END, ',') IS NOT NULL 
                  AND STRING_AGG(CASE WHEN l.location_type = 'gate' 
                                        THEN l.location_id || ':' || l.name || ':' || l.gate_status END, ',') IS NOT NULL""",
            fetch='all'
        )
        
        for system_name, majors_str, gates_str in systems_data:
            if not majors_str or not gates_str:
                continue
                
            # Parse major locations
            majors = []
            for major_data in majors_str.split(','):
                if ':' in major_data:
                    major_id, major_name = major_data.split(':', 1)
                    majors.append((int(major_id), major_name))
            
            # Parse gates
            gates = []
            for gate_data in gates_str.split(','):
                if gate_data.count(':') >= 2:
                    parts = gate_data.split(':')
                    gate_id, gate_name, gate_status = int(parts[0]), parts[1], parts[2]
                    gates.append((gate_id, gate_name, gate_status))
            
            # Ensure connections between majors and gates in the same system
            for major_id, major_name in majors:
                for gate_id, gate_name, gate_status in gates:
                    await self._ensure_local_connection_exists(
                        major_id, major_name, gate_id, gate_name, fixes, silent
                    )

    async def _ensure_local_connection_exists(self, major_id: int, major_name: str, 
                                           gate_id: int, gate_name: str, fixes: dict, silent: bool = True):
        """Ensure a local space connection exists between major location and gate"""
        # Check if connection already exists
        existing_connection = self.db.execute_query(
            """SELECT corridor_id FROM corridors 
               WHERE ((origin_location = %s AND destination_location = %s) OR 
                      (origin_location = %s AND destination_location = %s))
               AND corridor_type = 'local_space'
               AND is_active = true""",
            (major_id, gate_id, gate_id, major_id),
            fetch='one'
        )
        
        if not existing_connection:
            # Double-check: Ensure we're not creating duplicate connections by checking more thoroughly
            double_check = self.db.execute_query(
                """SELECT COUNT(*) FROM corridors 
                   WHERE ((origin_location = %s AND destination_location = %s) OR 
                          (origin_location = %s AND destination_location = %s))
                   AND is_active = true""",
                (major_id, gate_id, gate_id, major_id),
                fetch='one'
            )[0]
            
            if double_check > 0:
                if not silent:
                    print(f"⚠️ Skipping local space creation for {major_name} ↔ {gate_name}: {double_check} existing routes found")
                return
            
            # Create bidirectional local space connection
            route_name = f"Local Space: {major_name} ↔ {gate_name}"
            
            # Create outbound route (major → gate)
            self.db.execute_query(
                """INSERT INTO corridors 
                   (name, origin_location, destination_location, is_active, 
                    travel_time, fuel_cost, danger_level, is_bidirectional, last_shift)
                   VALUES (%s, %s, %s, 1, 60, 5, 1, 1, NOW())""",
                (route_name, major_id, gate_id)
            )
            
            # Create return route (gate → major)
            self.db.execute_query(
                """INSERT INTO corridors 
                   (name, origin_location, destination_location, is_active, 
                    travel_time, fuel_cost, danger_level, is_bidirectional, last_shift)
                   VALUES (%s, %s, %s, 1, 60, 5, 1, 1, NOW())""",
                (route_name, gate_id, major_id)
            )
            
            fixes['missing_local_created'] += 2  # Count both directions
            if not silent:
                print(f"✅ Created local space connection: {route_name} (bidirectional)")

    async def _fix_gate_connectivity_by_status(self, fixes: dict, silent: bool = True):
        """Fix gate connectivity based on their status (active/unused/moving)"""
        # Get all gates with their current connections
        gates_data = self.db.execute_query(
            """SELECT l.location_id, l.name, l.gate_status,
                      COUNT(CASE WHEN c.corridor_type = 'gated' THEN 1 END) as gated_connections,
                      COUNT(CASE WHEN c.corridor_type = 'local_space' THEN 1 END) as local_connections
               FROM locations l
               LEFT JOIN corridors c ON (c.origin_location = l.location_id OR c.destination_location = l.location_id)
               WHERE l.location_type = 'gate'
               GROUP BY l.location_id, l.name, l.gate_status""",
            fetch='all'
        )
        
        for gate_id, gate_name, gate_status, gated_connections, local_connections in gates_data:
            if gate_status == 'unused':
                # Unused gates should have ONLY local connections
                if gated_connections > 0:
                    await self._remove_gate_gated_connections(gate_id, gate_name, silent)
                    fixes['unused_gate_fixed'] += gated_connections
                    if not silent:
                        print(f"🔧 Fixed unused gate {gate_name}: removed {gated_connections} gated connections")
                        
            elif gate_status == 'moving':
                # Moving gates should have local connections but no gated connections
                if gated_connections > 0:
                    await self._remove_gate_gated_connections(gate_id, gate_name, silent)
                    fixes['moving_gate_fixed'] += gated_connections
                    if not silent:
                        print(f"🔧 Fixed moving gate {gate_name}: removed {gated_connections} gated connections")
                        
            elif gate_status == 'active':
                # Active gates should have both local connections AND gated connections to other active gates
                fixed_count = await self._ensure_active_gate_connections(gate_id, gate_name, gated_connections, silent)
                fixes['active_gate_fixed'] += fixed_count

    async def _remove_gate_gated_connections(self, gate_id: int, gate_name: str, silent: bool = True):
        """Remove all gated connections from a gate (keep only local space)"""
        gated_corridors = self.db.execute_query(
            """SELECT corridor_id FROM corridors 
               WHERE (origin_location = %s OR destination_location = %s)
               AND corridor_type = 'gated'""",
            (gate_id, gate_id),
            fetch='all'
        )
        
        for corridor_tuple in gated_corridors:
            corridor_id = corridor_tuple[0]
            self.db.execute_query("DELETE FROM corridors WHERE corridor_id = %s", (corridor_id,))
            if not silent:
                print(f"🗑️ Removed gated connection from gate {gate_name}")

    async def _ensure_active_gate_connections(self, gate_id: int, gate_name: str, current_gated_connections: int, silent: bool = True) -> int:
        """Ensure an active gate has proper gated connections to other active gates"""
        fixes_made = 0
        
        # Active gates should have at least 1-3 gated connections to other active gates
        if current_gated_connections < 1:
            # Find nearby active gates to connect to
            gate_info = self.db.execute_query(
                "SELECT x_coordinate, y_coordinate FROM locations WHERE location_id = %s",
                (gate_id,), fetch='one'
            )
            
            if not gate_info:
                return fixes_made
                
            gate_x, gate_y = gate_info
            
            # Find nearby active gates (not including this one)
            nearby_gates = self.db.execute_query(
                """SELECT location_id, name, x_coordinate, y_coordinate 
                   FROM locations 
                   WHERE location_type = 'gate' 
                   AND gate_status = 'active' 
                   AND location_id != %s
                   ORDER BY ((x_coordinate - %s) * (x_coordinate - %s) + (y_coordinate - %s) * (y_coordinate - %s))
                   LIMIT 3""",
                (gate_id, gate_x, gate_x, gate_y, gate_y),
                fetch='all'
            )
            
            # Create gated connections to the nearest active gates
            for target_id, target_name, target_x, target_y in nearby_gates:
                # Check if bidirectional corridors already exist
                forward_exists = self.db.execute_query(
                    """SELECT corridor_id FROM corridors 
                       WHERE origin_location = %s AND destination_location = %s
                       AND corridor_type != 'local_space'""",
                    (gate_id, target_id), fetch='one'
                )
                
                backward_exists = self.db.execute_query(
                    """SELECT corridor_id FROM corridors 
                       WHERE origin_location = %s AND destination_location = %s
                       AND corridor_type != 'local_space'""",
                    (target_id, gate_id), fetch='one'
                )
                
                # Calculate distance and travel time
                distance = ((target_x - gate_x) ** 2 + (target_y - gate_y) ** 2) ** 0.5
                travel_time = max(300, int(distance * 2))  # At least 5 minutes, scale with distance
                fuel_cost = max(50, int(distance * 0.5))  # Scale fuel with distance
                
                # Create forward corridor if missing
                if not forward_exists:
                    self.db.execute_query(
                        """INSERT INTO corridors (name, origin_location, destination_location, travel_time, fuel_cost, danger_level, is_active, is_generated, is_bidirectional)
                           VALUES (%s, %s, %s, %s, %s, 2, 1, 1, 1)""",
                        (f"{gate_name} - {target_name} Corridor", gate_id, target_id, travel_time, fuel_cost)
                    )
                    fixes_made += 1
                    if not silent:
                        print(f"🔧 Fixed active gate {gate_name}: created gated connection to {target_name}")
                
                # Create backward corridor if missing
                if not backward_exists:
                    self.db.execute_query(
                        """INSERT INTO corridors (name, origin_location, destination_location, travel_time, fuel_cost, danger_level, is_active, is_generated, is_bidirectional)
                           VALUES (%s, %s, %s, %s, %s, 2, 1, 1, 1)""",
                        (f"{target_name} - {gate_name} Corridor", target_id, gate_id, travel_time, fuel_cost)
                    )
                    fixes_made += 1
                    if not silent:
                        print(f"🔧 Fixed active gate {gate_name}: created return gated connection from {target_name}")
                
                # Stop after creating connections to avoid over-connecting
                if fixes_made >= 2:  # Forward + backward to one gate is enough
                    break
        
        return fixes_made

    def get_architecture_violations_summary(self) -> dict:
        """Get a summary of current architecture violations without fixing them"""
        violations = {
            'cross_system_connections': 0,
            'major_to_major_gated': 0,
            'major_to_gate_gated': 0,
            'gate_status_violations': 0,
            'missing_local_connections': 0
        }
        
        # Count cross-system violations
        cross_system = self.db.execute_query(
            """SELECT COUNT(*) FROM corridors c
               JOIN locations lo ON c.origin_location = lo.location_id  
               JOIN locations ld ON c.destination_location = ld.location_id
               WHERE (
                   (lo.location_type IN ('colony', 'space_station', 'outpost') AND ld.location_type = 'gate') OR
                   (lo.location_type = 'gate' AND ld.location_type IN ('colony', 'space_station', 'outpost'))
               )
               AND lo.system_name != ld.system_name
               AND c.corridor_type != 'ungated'""",
            fetch='one'
        )[0]
        violations['cross_system_connections'] = cross_system
        
        # Count major-to-major gated connections
        major_to_major = self.db.execute_query(
            """SELECT COUNT(*) FROM corridors c
               JOIN locations lo ON c.origin_location = lo.location_id  
               JOIN locations ld ON c.destination_location = ld.location_id
               WHERE lo.location_type IN ('colony', 'space_station', 'outpost')
               AND ld.location_type IN ('colony', 'space_station', 'outpost')
               AND c.corridor_type != 'ungated'""",
            fetch='one'
        )[0]
        violations['major_to_major_gated'] = major_to_major
        
        # Count gated major-to-gate connections
        major_to_gate = self.db.execute_query(
            """SELECT COUNT(*) FROM corridors c
               JOIN locations lo ON c.origin_location = lo.location_id  
               JOIN locations ld ON c.destination_location = ld.location_id
               WHERE (
                   (lo.location_type IN ('colony', 'space_station', 'outpost') AND ld.location_type = 'gate') OR
                   (lo.location_type = 'gate' AND ld.location_type IN ('colony', 'space_station', 'outpost'))
               )
               AND c.corridor_type != 'local_space' 
               AND c.corridor_type != 'ungated'""",
            fetch='one'
        )[0]
        violations['major_to_gate_gated'] = major_to_gate
        
        return violations