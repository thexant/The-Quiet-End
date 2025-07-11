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
        
        await interaction.response.send_message(
            f"📡 Radio transmission sent!",
            ephemeral=True
        )
    
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
        recipients_from_origin = await self._calculate_radio_propagation(
            origin_x, origin_y, origin_system, message, interaction.guild.id, sender_corridor_type=corridor_propagation_type
        )
        recipients_from_dest = await self._calculate_radio_propagation(
            dest_x, dest_y, dest_system, message, interaction.guild.id, sender_corridor_type=corridor_propagation_type
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
                f"📡 **Signal relayed through corridor {corridor_display_type}**\n\nTransmission attempted from **{origin_name}** and **{dest_name}** ends, but no players are in range to receive it.",
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
            f"📡 **Transmission relayed through corridor {corridor_display_type}**\n\nYour message has been broadcast from the **{origin_name}** and **{dest_name}** corridor ends. Signal reached {len(recipients)} recipient(s) across {len(set(r['location_id'] for r in recipients))} location(s).",
            ephemeral=True
        )

    # Modify _calculate_radio_propagation to accept the new corridor_type.
    # Find the existing _calculate_radio_propagation method and modify its signature and content.
    async def _calculate_radio_propagation(self, sender_x: float, sender_y: float, 
                                         sender_system: str, message: str, guild_id: int, 
                                         sender_corridor_type: str = "normal") -> List[Dict]: # Added sender_corridor_type
        """Calculate radio signal propagation and recipients"""
        
        # Get all players and their locations
        all_players = self.db.execute_query(
            '''SELECT c.user_id, c.name, c.callsign, l.location_id, l.name as loc_name,
                      l.x_coord, l.y_coord, l.system_name
               FROM characters c
               JOIN locations l ON c.current_location = l.location_id
               WHERE c.current_location IS NOT NULL''',
            fetch='all'
        )
        
        if not all_players:
            return []
        
        # Calculate direct transmission to all players
        recipients = []
        
        for player in all_players:
            user_id, char_name, callsign, loc_id, loc_name, x, y, system = player
            
            # Skip sender
            if x == sender_x and y == sender_y:
                continue
            
            # Calculate distance
            distance = math.sqrt((x - sender_x) ** 2 + (y - sender_y) ** 2)
            system_distance = int(distance / 10)  # Convert to "systems" (rough approximation)
            
            if system_distance <= 10:  # Within max range (10 systems default for direct)
                # Apply message degradation based on distance AND sender's corridor type
                degraded_message = self._degrade_message(message, system_distance, sender_corridor_type) # Passed sender_corridor_type
                
                recipients.append({
                    'user_id': user_id,
                    'char_name': char_name,
                    'callsign': callsign,
                    'location_id': loc_id,
                    'location': loc_name,
                    'system': system,
                    'distance': system_distance,
                    'message': degraded_message,
                    'signal_strength': max(0, 100 - (system_distance * 10)),
                    'relay_path': []
                })
        
        # Now check for repeaters and extended coverage (pass sender_corridor_type down)
        recipients = await self._extend_via_repeaters(sender_x, sender_y, message, recipients, sender_corridor_type) # Passed sender_corridor_type

        return recipients
    
    # Modify _extend_via_repeaters to accept corridor_type.
    # Find the existing _extend_via_repeaters method and modify its signature and content.
    async def _extend_via_repeaters(self, sender_x: float, sender_y: float, 
                                  original_message: str, direct_recipients: List[Dict],
                                  sender_corridor_type: str = "normal") -> List[Dict]: # Added sender_corridor_type
        """Extend radio coverage via repeaters"""
        
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
        
        # Track all signal sources (original + repeaters that receive signal)
        # Note: Original sender is now an implicit source from _calculate_radio_propagation's initial call
        # Repeaters become "sources" if they can receive a signal from the original sender or other repeaters.
        
        # For simplicity, let's treat the initial sender as a "source" and then repeaters that pick up that signal.
        # This is a bit of a BFS-like approach for signal spread.
        
        # We need a clear set of unique recipients with their best signal
        enhanced_recipients = {rec['user_id']: rec for rec in direct_recipients} # Start with direct recipients

        # Create a queue of signal sources that need to propagate
        # Each source is (x, y, message_at_source, distance_from_original_sender, transmission_range, source_name)
        # The message_at_source already has degradation up to this point.
        propagation_queue = []
        
        # Add original sender location as the initial propagation source
        # This assumes the original message comes out from the sender's current location effectively.
        propagation_queue.append({
            'x': sender_x, 
            'y': sender_y, 
            'message': original_message, # This is the original, undegraded message
            'total_degradation_distance': 0, # Total "distance" of degradation applied so far
            'range': 10, # Default range for direct transmission
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
    def _degrade_message(self, message: str, system_distance: int, sender_corridor_type: str = "normal") -> str: # Added sender_corridor_type
        """Apply signal degradation to message based on distance and corridor type"""
        
        # Base degradation starts after 5 systems
        degradation_start_threshold = 5
        
        # Apply additional fixed degradation for ungated corridors
        additional_ungated_degradation = 0
        if sender_corridor_type == "ungated":
            additional_ungated_degradation = 10 # Equivalent to an extra 10 systems distance in degradation

        # Calculate total effective system distance for degradation
        total_effective_distance = system_distance + additional_ungated_degradation

        if total_effective_distance <= degradation_start_threshold:
            return message  # Clear transmission or minimal degradation

        # Calculate degradation percentage
        degradation_factor_distance = total_effective_distance - degradation_start_threshold
        degradation_percent = min(80, degradation_factor_distance * 15) # 15% per system beyond threshold, max 80%
        
        if degradation_percent <= 0:
            return message
        
        # Apply character-level corruption
        corruption_chars = ['_', '-', '~', '#', '*', ' ', '%', '$', '@'] # Added more corruption chars
        result = list(message)
        
        for i, char in enumerate(result):
            if char.isalnum():  # Only corrupt letters and numbers
                if random.random() * 100 < degradation_percent:
                    result[i] = random.choice(corruption_chars)
        
        return ''.join(result)

    # Keep the _broadcast_to_location_channels method as is.
    async def _broadcast_to_location_channels(self, guild: discord.Guild, 
                                            sender_name: str, sender_callsign: str, 
                                            sender_location: str, sender_system: str,
                                            original_message: str, recipients: List[Dict]):
        """Send radio messages to location channels where recipients are present"""
        
        # Group recipients by location
        location_groups = {}
        for recipient in recipients:
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
            guild, location_id, representative_member
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
        
        # Group recipients by signal quality FIRST
        clear_receivers = []
        degraded_receivers = []
        
        for recipient in recipients:
            if recipient['signal_strength'] >= 70:
                clear_receivers.append(recipient)
            else:
                degraded_receivers.append(recipient)
        
        # Create immersive radio message embed
        embed = discord.Embed(
            title="📻 Incoming Radio Transmission",
            color=0x00aaff
        )
        
        # Determine if location should be shown based on signal quality
        location_display = sender_location
        system_display = f", {sender_system}"

        # If no clear receivers and only degraded, or if it's explicitly from transit where full location is ambiguous
        if (not clear_receivers and degraded_receivers) or ("Corridor Relay" in sender_location):
            location_display = "[UNKNOWN LOCATION]"
            system_display = ""


        # Add transmission header
        embed.add_field(
            name="📡 Signal Origin", 
            value=f"[{sender_callsign}]\n📍 Broadcasting from {location_display}{system_display}",
            inline=False
        )
        
        # Show who receives what quality
        if clear_receivers:
            clear_names = [f"**{r['char_name']}** [{r['callsign']}]" for r in clear_receivers]
            embed.add_field(
                name="🟢 Clear Reception",
                value="\n".join(clear_names[:5]) + (f"\n*...and {len(clear_names)-5} more*" if len(clear_names) > 5 else ""),
                inline=True
            )
            
            # Show clear message
            embed.add_field(
                name="📝 Transmission Content",
                value=f'"{original_message}"',
                inline=False
            )
        
        if degraded_receivers:
            degraded_names = []
            for r in degraded_receivers:
                signal_bars = "📶" if r['signal_strength'] >= 50 else "📵"
                relay_info = f" (via {', '.join(r['relay_path'])})" if r['relay_path'] else ""
                degraded_names.append(f"{signal_bars} **{r['char_name']}** [{r['callsign']}]{relay_info}")
            
            embed.add_field(
                name="📡 Weak Reception", 
                value="\n".join(degraded_names[:5]) + (f"\n*...and {len(degraded_names)-5} more*" if len(degraded_names) > 5 else ""),
                inline=True
            )
            
            # Show degraded message example
            if not clear_receivers:  # Only show if no clear message already shown
                worst_signal = min(degraded_receivers, key=lambda x: x['signal_strength'])
                embed.add_field(
                    name="📊 Received (Degraded)",
                    value=f'"{worst_signal["message"]}"',
                    inline=False
                )
        
        # Add atmospheric footer
        embed.set_footer(
            text=f"• Signal strength varies by distance and interference",
            icon_url="https://cdn.discordapp.com/emojis/📻.png"
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