# cogs/radio.py - REWORKED VERSION
import discord
from discord.ext import commands
from discord import app_commands
import random
import math
import string
from typing import List, Tuple, Dict, Optional
from utils.location_utils import get_character_location_status

class RadioCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = bot.db
    
    radio_group = app_commands.Group(name="radio", description="Radio communication system")
    
    @radio_group.command(name="send", description="Send a radio message across the galaxy")
    @app_commands.describe(message="Message to broadcast via radio")
    async def radio_send(self, interaction: discord.Interaction, message: str):
        # Check if user has a character
        char_data = self.db.execute_query(
            "SELECT current_location, name, callsign FROM characters WHERE user_id = ?",
            (interaction.user.id,),
            fetch='one'
        )
        
        if not char_data:
            await interaction.response.send_message("You need a character to use the radio! Use `/character create` first.", ephemeral=True)
            return
        
        current_location, char_name, callsign = char_data
        
        # Handle existing characters without callsigns
        if not callsign:
            callsign = generate_callsign()
            # Ensure uniqueness
            while self.db.execute_query("SELECT user_id FROM characters WHERE callsign = ?", (callsign,), fetch='one'):
                callsign = generate_callsign()
            
            # Update character with new callsign
            self.db.execute_query(
                "UPDATE characters SET callsign = ? WHERE user_id = ?",
                (callsign, interaction.user.id)
            )
            
            await interaction.followup.send(
                f"📡 Radio callsign **{callsign}** has been assigned to your character!", 
                ephemeral=True
            )

        # Get location status (this now handles ship physical locations)
        location_status, location_data = get_character_location_status(self.db, interaction.user.id)

        if not location_data:
            await interaction.response.send_message("You are stranded in deep space and cannot access radio communications.", ephemeral=True)
            return

        # Handle corridor radio behavior
        if location_data['type'] == 'transit':
            await self._handle_transit_radio(interaction, location_data, char_name, callsign, message)
            return

        # If we get here, they're at a normal location (including ships docked at locations)
        current_location_id = location_data['location_id'] # Use a different variable name to avoid confusion with the initial 'current_location' from char_data
        
        # Get sender's location and coordinates (use ship's physical location if applicable)
        sender_location_info = self.db.execute_query(
            "SELECT name, x_coord, y_coord, system_name FROM locations WHERE location_id = ?",
            (current_location_id,),
            fetch='one'
        )
        
        if not sender_location_info:
            await interaction.response.send_message("Unable to determine your location for radio transmission.", ephemeral=True)
            return
        
        sender_loc_name, sender_x, sender_y, sender_system = sender_location_info
        
        # Find all players who can receive this transmission
        recipients = await self._calculate_radio_propagation(
            sender_x, sender_y, sender_system, message, interaction.guild.id, sender_corridor_type="normal"
        )
        
        if not recipients:
            await interaction.response.send_message(
                f"📡 Radio transmission sent!",
                ephemeral=True
            )
            return
        
        # Determine sender location display based on where they are
        if 'ship_context' in location_data:
            # Character is in ship interior, show ship context
            ship_info = location_data['ship_context']
            sender_location_display = f"Aboard {ship_info['ship_name']} at {location_data['name']}"
            sender_system_display = sender_system
        else:
            # Character is directly at location
            sender_location_display = location_data['name']
            sender_system_display = sender_system

        await self._broadcast_to_location_channels(
            interaction.guild, char_name, callsign, sender_location_display, 
            sender_system_display, message, recipients
        )
        
        # Try to award passive XP for radio communication (add this before the final response)
        char_cog = self.bot.get_cog('CharacterCog')
        if char_cog:
            xp_awarded = await char_cog.try_award_passive_xp(interaction.user.id, "radio")
            if xp_awarded:
                # Modify the final response to include XP notification
                final_message = f"📡 Radio transmission sent!\n✨ *You feel more experienced with radio operations.* (+5 XP)"
            else:
                final_message = f"📡 Radio transmission sent!"
        else:
            final_message = f"📡 Radio transmission sent!"

        await interaction.response.send_message(final_message, ephemeral=True)
    
    # Replace the _handle_gated_corridor_radio method with this new _handle_transit_radio method.
    # It now correctly handles both gated and ungated transit based on corridor type.
    async def _handle_transit_radio(self, interaction: discord.Interaction, location_data: dict, 
                                         char_name: str, callsign: str, message: str):
        """Handle radio transmission from within any corridor (gated or ungated)"""
        
        corridor_name = location_data['corridor_name']
        origin_name = location_data['origin_name']
        dest_name = location_data['dest_name']
        origin_id = location_data['origin_id']
        dest_id = location_data['dest_id']
        
        # Determine if it's an ungated corridor (assume 'Ungated' in name for simplicity)
        is_ungated = "Ungated" in corridor_name
        corridor_display_type = "Ungated Transit" if is_ungated else "Gated Transit"
        corridor_propagation_type = "ungated" if is_ungated else "gated"

        # Get location info and coordinates for both ends of the corridor
        origin_loc_info = self.db.execute_query(
            "SELECT x_coord, y_coord, system_name FROM locations WHERE location_id = ?",
            (origin_id,), fetch='one'
        )
        dest_loc_info = self.db.execute_query(
            "SELECT x_coord, y_coord, system_name FROM locations WHERE location_id = ?",
            (dest_id,), fetch='one'
        )
        
        if not origin_loc_info or not dest_loc_info:
            await interaction.response.send_message("Unable to establish relay connection from corridor ends.", ephemeral=True)
            return
        
        origin_x, origin_y, origin_system = origin_loc_info
        dest_x, dest_y, dest_system = dest_loc_info
        
        # Calculate propagation from both ends of the corridor, applying specific corridor degradation
        if is_ungated:
            # Apply heavy degradation to outgoing message from ungated corridor
            pre_degraded_message = self._degrade_message(message, 12, "ungated")  # Simulate 12 systems of ungated interference
        else:
            pre_degraded_message = message

        recipients_from_origin = await self._calculate_radio_propagation(
            origin_x, origin_y, origin_system, pre_degraded_message, interaction.guild.id, sender_corridor_type=corridor_propagation_type
        )
        recipients_from_dest = await self._calculate_radio_propagation(
            dest_x, dest_y, dest_system, pre_degraded_message, interaction.guild.id, sender_corridor_type=corridor_propagation_type
        )
        
        # Combine and deduplicate recipients, prioritizing stronger signals
        all_recipients = {}
        
        # Process recipients from origin side
        for recipient in recipients_from_origin:
            user_id_rec = recipient['user_id']
            if 'relay_path' not in recipient:
                recipient['relay_path'] = []
            recipient['relay_path'].append(f"Relay via: {origin_name} (Origin Gate)")
            all_recipients[user_id_rec] = recipient
        
        # Process recipients from destination side, taking the stronger signal
        for recipient in recipients_from_dest:
            user_id_rec = recipient['user_id']
            if user_id_rec in all_recipients:
                existing = all_recipients[user_id_rec]
                if recipient['signal_strength'] > existing['signal_strength']:
                    recipient['relay_path'] = [f"Relay via: {dest_name} (Destination Gate)"]
                    all_recipients[user_id_rec] = recipient
                else:
                    # If existing is stronger, just add the relay path
                    existing['relay_path'].append(f"Relay via: {dest_name} (Destination Gate)")
            else:
                if 'relay_path' not in recipient:
                    recipient['relay_path'] = []
                recipient['relay_path'].append(f"Relay via: {dest_name} (Destination Gate)")
                all_recipients[user_id_rec] = recipient
        
        recipients = list(all_recipients.values())
        
        if not recipients:
            await interaction.response.send_message(
                f"📡 **Transmission relayed through corridor {corridor_display_type}**\n\nYour message has been broadcast from the **{origin_name}** and **{dest_name}** corridor ends.",
                ephemeral=True
            )
            return
        
        # Broadcast to relevant location channels
        await self._broadcast_to_location_channels(
            interaction.guild, char_name, callsign, f"Corridor Relay ({corridor_name})", 
            f"Corridor {corridor_display_type}", message, recipients
        )
        
        # Confirmation message for the sender
        await interaction.response.send_message(
            f"📡 **Transmission relayed through corridor {corridor_display_type}**\n\nYour message has been broadcast from the **{origin_name}** and **{dest_name}** corridor ends.",
            ephemeral=True
        )

    # Modify _calculate_radio_propagation to accept the new corridor_type.
    async def _calculate_radio_propagation(self, sender_x: float, sender_y: float, 
                                         sender_system: str, message: str, guild_id: int, 
                                         sender_corridor_type: str = "normal") -> List[Dict]:
        """Calculate radio signal propagation and recipients"""
        
        # Get all players and their locations
        all_players = self.db.execute_query(
            '''SELECT c.user_id, c.name, c.callsign, l.location_id, l.name as loc_name,
                      l.x_coord, l.y_coord, l.system_name
               FROM characters c
               JOIN locations l ON c.current_location = l.location_id
               WHERE c.current_location IS NOT NULL AND c.is_logged_in = 1''',
            fetch='all'
        )
        
        recipients = []
        
        # Process players at locations
        if all_players:
            for player in all_players:
                user_id, char_name, callsign, loc_id, loc_name, x, y, system = player
                
                # Skip sender
                if x == sender_x and y == sender_y:
                    continue
                
                # Calculate distance
                distance = math.sqrt((x - sender_x) ** 2 + (y - sender_y) ** 2)
                system_distance = int(distance / 10)  # Convert to "systems" (rough approximation)
                
                if system_distance <= 3:  # Within max range (10 systems default for direct)
                    # Apply message degradation based on distance AND sender's corridor type
                    degraded_message = self._degrade_message(message, system_distance, sender_corridor_type)
                    
                    recipients.append({
                        'user_id': user_id,
                        'char_name': char_name,
                        'callsign': callsign,
                        'location_id': loc_id,
                        'location': loc_name,
                        'system': system,
                        'distance': system_distance,
                        'message': degraded_message,
                        'signal_strength': max(0, 100 - (system_distance * 20)),
                        'relay_path': []
                    })
        
        # NEW: Get all players currently in transit
        transit_players = self.db.execute_query(
            '''SELECT ts.user_id, c.name, c.callsign, ts.corridor_id,
                      cor.name as corridor_name, 
                      ol.location_id as origin_id, ol.name as origin_name, 
                      ol.x_coord as origin_x, ol.y_coord as origin_y, ol.system_name as origin_system,
                      dl.location_id as dest_id, dl.name as dest_name,
                      dl.x_coord as dest_x, dl.y_coord as dest_y, dl.system_name as dest_system
               FROM travel_sessions ts
               JOIN characters c ON ts.user_id = c.user_id
               JOIN corridors cor ON ts.corridor_id = cor.corridor_id
               JOIN locations ol ON ts.origin_location = ol.location_id
               JOIN locations dl ON ts.destination_location = dl.location_id
               WHERE ts.status = 'traveling' AND c.is_logged_in = 1''',
            fetch='all'
        )
        
        # Process players in transit
        for transit_player in transit_players:
            (user_id, char_name, callsign, corridor_id, corridor_name,
             origin_id, origin_name, origin_x, origin_y, origin_system,
             dest_id, dest_name, dest_x, dest_y, dest_system) = transit_player
            
            # Determine corridor type for additional degradation
            is_ungated = "Ungated" in corridor_name
            receiver_corridor_type = "ungated" if is_ungated else "gated"
            
            # Check if signal can reach either end of the corridor
            signal_received = False
            best_signal_strength = 0
            best_relay_path = []
            best_message = message
            best_distance = float('inf')
            
            # Check origin end
            origin_distance = math.sqrt((origin_x - sender_x) ** 2 + (origin_y - sender_y) ** 2)
            origin_system_distance = int(origin_distance / 10)
            
            if origin_system_distance <= 3:  # Within range
                # Calculate degradation: sender's corridor type + receiver's corridor type + distance
                total_degradation_distance = origin_system_distance
                
                # Apply sender's corridor degradation
                degraded_message = self._degrade_message(message, total_degradation_distance, sender_corridor_type)
                
                # Apply receiver's corridor degradation (additional degradation for ungated corridors)
                if receiver_corridor_type == "ungated":
                    # Apply additional degradation equivalent to 10 extra systems for ungated corridors
                    degraded_message = self._degrade_message(degraded_message, 10, "ungated")
                
                signal_strength = max(0, 100 - (total_degradation_distance * 10))
                if receiver_corridor_type == "ungated":
                    signal_strength = max(0, signal_strength - 50)  # Additional penalty for ungated
                
                if signal_strength > best_signal_strength:
                    signal_received = True
                    best_signal_strength = signal_strength
                    best_relay_path = [f"Relay via: {origin_name} (Corridor Entry)"]
                    best_message = degraded_message
                    best_distance = total_degradation_distance
            
            # Check destination end
            dest_distance = math.sqrt((dest_x - sender_x) ** 2 + (dest_y - sender_y) ** 2)
            dest_system_distance = int(dest_distance / 10)
            
            if dest_system_distance <= 3:  # Within range
                # Calculate degradation: sender's corridor type + receiver's corridor type + distance
                total_degradation_distance = dest_system_distance
                
                # Apply sender's corridor degradation
                degraded_message = self._degrade_message(message, total_degradation_distance, sender_corridor_type)
                
                # Apply receiver's corridor degradation
                if receiver_corridor_type == "ungated":
                    degraded_message = self._degrade_message(degraded_message, 10, "ungated")
                
                signal_strength = max(0, 100 - (total_degradation_distance * 10))
                if receiver_corridor_type == "ungated":
                    signal_strength = max(0, signal_strength - 50)
                
                if signal_strength > best_signal_strength:
                    signal_received = True
                    best_signal_strength = signal_strength
                    best_relay_path = [f"Relay via: {dest_name} (Corridor Exit)"]
                    best_message = degraded_message
                    best_distance = total_degradation_distance
            
            # If signal can be received from either end, add to recipients
            if signal_received:
                recipients.append({
                    'user_id': user_id,
                    'char_name': char_name,
                    'callsign': callsign,
                    'location_id': f"transit_{corridor_id}",  # Special ID for transit
                    'location': f"In Transit ({corridor_name})",
                    'system': f"Corridor Transit",
                    'distance': best_distance,
                    'message': best_message,
                    'signal_strength': best_signal_strength,
                    'relay_path': best_relay_path,
                    'in_transit': True,  # Flag to identify transit recipients
                    'corridor_type': receiver_corridor_type
                })
        
        # Now check for repeaters and extended coverage
        recipients = await self._extend_via_repeaters(sender_x, sender_y, message, recipients, sender_corridor_type)

        return recipients
    async def _extend_via_repeaters(self, sender_x: float, sender_y: float,
                                  original_message: str, direct_recipients: List[Dict],
                                  sender_corridor_type: str = "normal") -> List[Dict]: # Added sender_corridor_type
        """Extend radio coverage via repeaters"""
        
        # Get all players to calculate repeater coverage against
        all_players = self.db.execute_query(
            '''SELECT c.user_id, c.name, c.callsign, l.location_id, l.name as loc_name,
                      l.x_coord, l.y_coord, l.system_name
               FROM characters c
               JOIN locations l ON c.current_location = l.location_id
               WHERE c.current_location IS NOT NULL AND c.is_logged_in = 1''',
            fetch='all'
        )

        # Get all active repeaters
        repeaters = self.db.execute_query(
            '''SELECT r.repeater_id, r.receive_range, r.transmit_range,
                      l.x_coord, l.y_coord, l.name as loc_name, l.system_name
               FROM repeaters r
               JOIN locations l ON r.location_id = l.location_id
               WHERE r.is_active = 1''',
            fetch='all'
        )

        if not repeaters:
            return direct_recipients

        # We need a clear set of unique recipients with their best signal
        enhanced_recipients = {rec['user_id']: rec for rec in direct_recipients} # Start with direct recipients

        # Create a queue of signal sources that need to propagate
        # Each source is (x, y, message_at_source, distance_from_original_sender, transmission_range, source_name)
        # The message_at_source already has degradation up to this point.
        propagation_queue = []

        # Add original sender location as the initial propagation source
        propagation_queue.append({
            'x': sender_x,
            'y': sender_y,
            'message': original_message, # This is the original, undegraded message
            'total_degradation_distance': 0, # Total "distance" of degradation applied so far
            'range': 3, # Default range for direct transmission
            'name': 'Origin',
            'sender_corridor_type': sender_corridor_type # Propagate sender's original corridor type
        })

        processed_sources = set() # To prevent infinite loops if repeaters form a loop

        while propagation_queue:
            current_source = propagation_queue.pop(0)
            source_key = (current_source['x'], current_source['y'], current_source['name'])

            if source_key in processed_sources:
                continue
            processed_sources.add(source_key)

            # Check for other repeaters that can pick up this signal
            for repeater in repeaters:
                rep_id, recv_range, trans_range, rep_x, rep_y, rep_name, rep_system = repeater

                # Distance from current source to this repeater
                distance_to_repeater = math.sqrt((rep_x - current_source['x']) ** 2 + (rep_y - current_source['y']) ** 2)
                system_distance_to_repeater = int(distance_to_repeater / 10)

                if system_distance_to_repeater <= recv_range: # If repeater can receive
                    # Calculate total degradation distance through this path
                    new_total_degradation_distance = current_source['total_degradation_distance'] + system_distance_to_repeater

                    # Create new propagation source for this repeater
                    new_source_message = self._degrade_message(
                        original_message, new_total_degradation_distance, current_source['sender_corridor_type'] # Degrade based on total distance and original sender's corridor type
                    )

                    new_source = {
                        'x': rep_x,
                        'y': rep_y,
                        'message': new_source_message,
                        'total_degradation_distance': new_total_degradation_distance,
                        'range': trans_range, # Repeater transmits with its own range
                        'name': f"Repeater @ {rep_name}",
                        'sender_corridor_type': current_source['sender_corridor_type'] # Maintain original sender's corridor type for degradation calc
                    }
                    propagation_queue.append(new_source)

            # Check all players for reception from this source
            for player in all_players:
                user_id_rec, char_name, callsign, loc_id, loc_name, x, y, system = player

                # Skip original sender (already handled, or not target)
                if x == sender_x and y == sender_y and current_source['name'] == 'Origin':
                    continue

                # Distance from this current source to the player
                distance_to_player = math.sqrt((x - current_source['x']) ** 2 + (y - current_source['y']) ** 2)
                system_distance_to_player = int(distance_to_player / 10)

                if system_distance_to_player <= current_source['range']: # If player is in range of this source
                    # Total degradation path: original_sender -> ... -> current_source -> player
                    final_total_degradation_distance = current_source['total_degradation_distance'] + system_distance_to_player

                    final_message = self._degrade_message(
                        original_message, final_total_degradation_distance, current_source['sender_corridor_type'] # Degrade based on total path and original sender's corridor type
                    )
                    signal_strength = max(0, 100 - (final_total_degradation_distance * 10)) # Adjust multiplier as needed

                    # Construct relay path for display
                    relay_path_display = [current_source['name']] if current_source['name'] != 'Origin' else []

                    # Update if this is a better (stronger) signal for this player
                    if user_id_rec not in enhanced_recipients or signal_strength > enhanced_recipients[user_id_rec]['signal_strength']:
                        enhanced_recipients[user_id_rec] = {
                            'user_id': user_id_rec,
                            'char_name': char_name,
                            'callsign': callsign,
                            'location_id': loc_id,
                            'location': loc_name,
                            'system': system,
                            'distance': final_total_degradation_distance, # This is the total distance affecting degradation
                            'message': final_message,
                            'signal_strength': signal_strength,
                            'relay_path': relay_path_display,
                            'source': current_source['name'] # Debugging what source provided the signal
                        }

        return list(enhanced_recipients.values())
    
    # Modify _degrade_message to accept sender_corridor_type.
    # Find the existing _degrade_message method and modify its signature and content.
    def _degrade_message(self, message: str, system_distance: int, sender_corridor_type: str = "normal") -> str:
        """Apply signal degradation to message based on distance and corridor type"""
        
        # REPLACE THE ENTIRE METHOD WITH THIS:
        
        # More aggressive degradation for galactic distances
        degradation_start_threshold = 2  # Start degrading after just 2 systems
        
        # Apply additional fixed degradation for ungated corridors
        additional_ungated_degradation = 0
        if sender_corridor_type == "ungated":
            additional_ungated_degradation = 15  # Increased from 10 to 15 for heavier ungated penalty

        # Calculate total effective system distance for degradation
        total_effective_distance = system_distance + additional_ungated_degradation

        if total_effective_distance <= degradation_start_threshold:
            return message  # Clear transmission only within 2 systems

        # More aggressive degradation percentage for galactic realism
        degradation_factor_distance = total_effective_distance - degradation_start_threshold
        degradation_percent = min(95, degradation_factor_distance * 25)  # 25% per system beyond threshold, max 95%
        
        if degradation_percent <= 0:
            return message
        
        # Enhanced corruption characters for more realistic interference
        corruption_chars = ['_', '-', '~', '#', '*', ' ', '%', '$', '@', '?', '!', '&', '^']
        result = list(message)
        
        # Add "scattering" effect - random bursts of interference
        scatter_chance = min(0.3, degradation_percent / 200)  # Up to 30% chance of scatter effects
        
        for i, char in enumerate(result):
            if char.isalnum() or char in [' ', '.', ',', '!', '?']:
                if random.random() < (degradation_percent / 100):
                    # Apply scattering - sometimes replace with multiple interference chars
                    if random.random() < scatter_chance:
                        # Scatter effect: replace single char with 2-3 interference chars
                        result[i] = ''.join(random.choices(corruption_chars, k=random.randint(2, 3)))
                    else:
                        # Normal single-character corruption
                        result[i] = random.choice(corruption_chars)
        
        return ''.join(result)

    async def _broadcast_to_location_channels(self, guild: discord.Guild, 
                                            sender_name: str, sender_callsign: str, 
                                            sender_location: str, sender_system: str,
                                            original_message: str, recipients: List[Dict]):
        """Send radio messages to location channels where recipients are present"""
        
        # Group recipients by location (including transit channels)
        location_groups = {}
        transit_groups = {}
        
        for recipient in recipients:
            if recipient.get('in_transit', False):
                # Handle transit recipients - group by corridor
                corridor_id = recipient['location_id'].replace('transit_', '')
                if corridor_id not in transit_groups:
                    transit_groups[corridor_id] = []
                transit_groups[corridor_id].append(recipient)
            else:
                # Handle regular location recipients
                location_id = recipient['location_id']
                if location_id not in location_groups:
                    location_groups[location_id] = []
                location_groups[location_id].append(recipient)
        
        # Send messages to each location channel
        for location_id, location_recipients in location_groups.items():
            await self._send_location_radio_message(
                guild, location_id, sender_name, sender_callsign, 
                sender_location, sender_system, original_message, location_recipients
            )
        
        # Send messages to transit channels
        for corridor_id, transit_recipients in transit_groups.items():
            await self._send_transit_radio_message(
                guild, corridor_id, sender_name, sender_callsign,
                sender_location, sender_system, original_message, transit_recipients
            )
    async def _send_transit_radio_message(self, guild: discord.Guild, corridor_id: str,
                                         sender_name: str, sender_callsign: str,
                                         sender_location: str, sender_system: str, 
                                         original_message: str, recipients: List[Dict]):
        """Send a radio message to a transit channel"""
        
        # Find the transit channel for any of the recipients
        transit_channel = None
        for recipient in recipients:
            # Get the user's current travel session to find their transit channel
            travel_session = self.db.execute_query(
                "SELECT temp_channel_id FROM travel_sessions WHERE user_id = ? AND status = 'traveling'",
                (recipient['user_id'],),
                fetch='one'
            )
            
            if travel_session and travel_session[0]:
                transit_channel = guild.get_channel(travel_session[0])
                if transit_channel:
                    break
        
        if not transit_channel:
            return  # No valid transit channel found
        
        # Get corridor name for display
        corridor_name = recipients[0]['location'].replace('In Transit (', '').replace(')', '') if recipients else "Unknown Corridor"
        
        first_recipient = recipients[0] if recipients else None
        signal_strength = first_recipient['signal_strength'] if first_recipient else 0
        corridor_type = first_recipient.get('corridor_type', 'gated') if first_recipient else 'gated'

        # Create simplified radio message embed for transit
        embed = discord.Embed(
            title="📻 Incoming Radio Transmission",
            color=0x800080  # Purple for transit
        )

        # Style based on corridor type and signal quality
        if corridor_type == "ungated":
            embed.color = 0xff4444  # Red for dangerous ungated corridors
            embed.title = "📻⚠️ Degraded Radio Transmission"

        # Add transmission header with signal quality
        signal_indicator = "🟢" if signal_strength >= 70 else ("📶" if signal_strength >= 30 else "📵")
        embed.add_field(
            name=f"📡 Signal Origin {signal_indicator}", 
            value=f"[{sender_callsign}]\n📍 Broadcasting from {sender_location}, {sender_system}",
            inline=False
        )

        # Show appropriate message version
        if signal_strength >= 70:
            embed.add_field(
                name="📝 Transmission Content",
                value=f'"{original_message}"',
                inline=False
            )
        else:
            # Show degraded message
            degraded_message = first_recipient['message'] if first_recipient else original_message
            embed.add_field(
                name="📊 Received (Signal Degraded)",
                value=f'"{degraded_message}"',
                inline=False
            )

        # Add corridor-specific warnings
        if corridor_type == "ungated":
            embed.add_field(
                name="⚠️ Corridor Interference",
                value="Signal severely degraded due to ungated corridor instability",
                inline=False
            )
        
        # Add atmospheric footer
        embed.set_footer(
            text=f"• Received in {corridor_name} • Signal relayed through corridor endpoints"
        )
        embed.timestamp = discord.utils.utcnow()
        
        try:
            await transit_channel.send(embed=embed)
        except Exception as e:
            print(f"❌ Failed to send radio message to transit channel {transit_channel.name}: {e}")
    # Keep the _send_location_radio_message method as is.
    async def _send_location_radio_message(self, guild: discord.Guild, location_id: int,
                                         sender_name: str, sender_callsign: str,
                                         sender_location: str, sender_system: str, 
                                         original_message: str, recipients: List[Dict]):
        """Send a radio message to a specific location channel"""
        
        # Get or create the location channel
        from utils.channel_manager import ChannelManager
        channel_manager = self.bot.get_cog('ChannelManager') or ChannelManager(self.bot)
        
        # We need at least one recipient to be at this location to get/create the channel
        if not recipients:
            return
        
        # Get a member from the recipients to create the channel if needed
        representative_member = None
        for recipient in recipients:
            member = guild.get_member(recipient['user_id'])
            if member:
                representative_member = member
                break
        
        if not representative_member:
            return  # No valid members found
        
        channel = await channel_manager.get_or_create_location_channel(
            guild, location_id, representative_member, name, description, wealth
        )
        
        if not channel:
            return  # Failed to get/create channel
        
        # Get location name
        location_info = self.db.execute_query(
            "SELECT name FROM locations WHERE location_id = ?",
            (location_id,),
            fetch='one'
        )
        location_name = location_info[0] if location_info else "Unknown Location"
        
        # Determine signal quality from first recipient (all at same location have same quality)
        first_recipient = recipients[0] if recipients else None
        signal_strength = first_recipient['signal_strength'] if first_recipient else 0
        is_clear_signal = signal_strength >= 70

        # Create simplified radio message embed
        embed = discord.Embed(
            title="📻 Incoming Radio Transmission",
            color=0x00aaff if is_clear_signal else 0xff8800  # Blue for clear, orange for degraded
        )

        # Determine location display based on signal quality
        location_display = sender_location
        system_display = f", {sender_system}"

        # Hide location details for heavily degraded signals
        if signal_strength < 30 or ("Corridor Relay" in sender_location):
            location_display = "[UNKNOWN LOCATION]"
            system_display = ""

        # Add transmission header with signal quality indicator
        signal_indicator = "🟢" if is_clear_signal else ("📶" if signal_strength >= 30 else "📵")
        embed.add_field(
            name=f"📡 Signal Origin {signal_indicator}", 
            value=f"[{sender_callsign}]\n📍 Broadcasting from {location_display}{system_display}",
            inline=False
        )

        # Show the appropriate message version
        if is_clear_signal:
            embed.add_field(
                name="📝 Transmission Content",
                value=f'"{original_message}"',
                inline=False
            )
        else:
            # Show degraded message
            degraded_message = first_recipient['message'] if first_recipient else original_message
            embed.add_field(
                name="📊 Received (Signal Degraded)",
                value=f'"{degraded_message}"',
                inline=False
            )

        # Add relay information if applicable
        if first_recipient and first_recipient.get('relay_path'):
            embed.add_field(
                name="📡 Signal Path",
                value=" → ".join(first_recipient['relay_path']),
                inline=False
            )
        
        # Add atmospheric footer
        embed.set_footer(
            text=f"📻 Signal strength varies by distance and interference"
        )
        embed.timestamp = discord.utils.utcnow()
        
        try:
            await channel.send(embed=embed)
        except Exception as e:
            print(f"❌ Failed to send radio message to {channel.name}: {e}")

def generate_callsign() -> str:
    """Generate a random callsign in format ABCD-1234"""
    letters = ''.join(random.choices(string.ascii_uppercase, k=4))
    numbers = ''.join(random.choices(string.digits, k=4))
    return f"{letters}-{numbers}"

async def setup(bot):
    await bot.add_cog(RadioCog(bot))