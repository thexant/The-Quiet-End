# utils/location_utils.py
from typing import Optional, Tuple
import sqlite3

def get_character_location_status(db, user_id: int) -> Tuple[str, Optional[dict]]:
    """
    Get character location status including ship and transit information.
    Returns (status_text, location_data)
    """
    # Check current character state
    char_data = db.execute_query(
        "SELECT current_location, name, current_ship_id, location_status FROM characters WHERE user_id = ?",
        (user_id,),
        fetch='one'
    )
    
    if not char_data:
        return "Character not found", None
    
    current_location_id, char_name, current_ship_id, location_status = char_data

    # Priority 1: Check if inside a ship
    if current_ship_id:
        ship_data = db.execute_query(
            "SELECT s.name, s.docked_at_location, l.name as loc_name "
            "FROM ships s "
            "LEFT JOIN locations l ON s.docked_at_location = l.location_id "
            "WHERE s.ship_id = ?",
            (current_ship_id,),
            fetch='one'
        )
        if ship_data:
            ship_name, ship_location_id, ship_location_name = ship_data
            if ship_location_id and ship_location_name:
                # Get location status for where ship is docked
                dock_location_info = db.execute_query(
                    "SELECT location_type, is_derelict, gate_status FROM locations WHERE location_id = ?",
                    (ship_location_id,),
                    fetch='one'
                )
                
                dock_status_indicator = ""
                if dock_location_info:
                    dock_location_type, dock_is_derelict, dock_gate_status = dock_location_info
                    if dock_is_derelict:
                        dock_status_indicator = " 💀[DERELICT]"
                    elif dock_location_type == 'gate' and dock_gate_status == 'unused':
                        dock_status_indicator = " ⚫[UNUSED GATE]"
                    elif dock_location_type == 'gate' and dock_gate_status == 'relocated':
                        dock_status_indicator = " 🔄[RELOCATED GATE]"
                
                # Ship is docked somewhere - return physical location for radio/map purposes
                status_text = f"Aboard '{ship_name}' (docked at {ship_location_name}{dock_status_indicator})"
                return status_text, {
                    'type': 'location',  # Treat as location for radio purposes
                    'location_id': ship_location_id,
                    'name': ship_location_name,
                    'ship_context': {
                        'ship_id': current_ship_id,
                        'ship_name': ship_name,
                        'in_ship_interior': True
                    }
                }
            else:
                # Ship is in deep space
                status_text = f"Aboard '{ship_name}' (in deep space)"
                return status_text, {'type': 'ship', 'ship_id': current_ship_id, 'name': ship_name}
        else:
            # Data inconsistency, evict player from non-existent ship
            db.execute_query("UPDATE characters SET current_ship_id = NULL, current_location = NULL WHERE user_id = ?", (user_id,))

    # Priority 2: Check if at a physical location
    if current_location_id:
        location_info = db.execute_query(
            "SELECT name, location_type, is_derelict, gate_status FROM locations WHERE location_id = ?",
            (current_location_id,),
            fetch='one'
        )
        
        if location_info:
            location_name, location_type, is_derelict, gate_status = location_info
            
            # Add status indicators
            status_indicator = ""
            if is_derelict:
                status_indicator = " 💀[DERELICT]"
            elif location_type == 'gate' and gate_status == 'unused':
                status_indicator = " ⚫[UNUSED GATE]"
            elif location_type == 'gate' and gate_status == 'relocated':
                status_indicator = " 🔄[RELOCATED GATE]"
            
            status_text = f"At {location_name}{status_indicator} ({location_status})"
            return status_text, {
                'type': 'location', 
                'location_id': current_location_id, 
                'name': location_name,
                'is_derelict': is_derelict,
                'gate_status': gate_status,
                'location_type': location_type
            }
        else:
            status_text = f"At Unknown Location ({location_status})"
            return status_text, {'type': 'location', 'location_id': current_location_id, 'name': "Unknown Location"}
    
    # Priority 3: Check if in transit
    transit_data = db.execute_query(
        """SELECT ts.corridor_id, c.name as corridor_name,
                  ol.name as origin_name, dl.name as dest_name,
                  ts.origin_location, ts.destination_location, c.corridor_type
           FROM travel_sessions ts
           JOIN corridors c ON ts.corridor_id = c.corridor_id
           JOIN locations ol ON ts.origin_location = ol.location_id
           JOIN locations dl ON ts.destination_location = dl.location_id
           WHERE ts.user_id = ? AND ts.status = 'traveling'""",
        (user_id,),
        fetch='one'
    )
    
    if transit_data:
        corridor_id, corridor_name, origin_name, dest_name, origin_id, dest_id, corridor_type = transit_data
        status_text = f"In transit: {origin_name} → {dest_name} (via {corridor_name})"
        return status_text, {
            'type': 'transit',
            'corridor_id': corridor_id,
            'corridor_name': corridor_name,
            'origin_name': origin_name,
            'dest_name': dest_name,
            'origin_id': origin_id,
            'dest_id': dest_id,
            'corridor_type': corridor_type
        }
    
    # If nothing else, they are lost
    return "Lost in deep space", None