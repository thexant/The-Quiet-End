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
            # Check if corridor is gated or ungated
            corridor_name = location_data['corridor_name']
            
            if "Ungated" in corridor_name:
                # Ungated corridors block radio transmission
                await interaction.response.send_message(
                    "📡 **Radio transmission failed**\n\nYour radio signal cannot escape the ungated corridor. The electromagnetic interference from unshielded space-time distortions blocks all communications.",
                    ephemeral=True
                )
                return
            else:
                # Gated corridors relay from both gates
                await self._handle_gated_corridor_radio(interaction, location_data, char_name, callsign, message)
                return

        # If we get here, they're at a normal location (including ships docked at locations)
        current_location = location_data['location_id']
        
        # Get sender's location and coordinates (use ship's physical location if applicable)
        sender_location = self.db.execute_query(
            "SELECT name, x_coord, y_coord, system_name FROM locations WHERE location_id = ?",
            (current_location,),
            fetch='one'
        )
        
        if not sender_location:
            await interaction.response.send_message("Unable to determine your location for radio transmission.", ephemeral=True)
            return
        
        sender_loc_name, sender_x, sender_y, sender_system = sender_location
        
        # Find all players who can receive this transmission
        recipients = await self._calculate_radio_propagation(
            sender_x, sender_y, sender_system, message, interaction.guild.id
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
    async def _handle_gated_corridor_radio(self, interaction: discord.Interaction, location_data: dict, 
                                         char_name: str, callsign: str, message: str):
        """Handle radio transmission from within a gated corridor"""
        
        corridor_name = location_data['corridor_name']
        origin_name = location_data['origin_name']
        dest_name = location_data['dest_name']
        origin_id = location_data['origin_id']
        dest_id = location_data['dest_id']
        
        # Get gate coordinates for both ends
        origin_coords = self.db.execute_query(
            "SELECT x_coord, y_coord, system_name FROM locations WHERE location_id = ?",
            (origin_id,), fetch='one'
        )
        dest_coords = self.db.execute_query(
            "SELECT x_coord, y_coord, system_name FROM locations WHERE location_id = ?",
            (dest_id,), fetch='one'
        )
        
        if not origin_coords or not dest_coords:
            await interaction.response.send_message("Unable to establish relay connection.", ephemeral=True)
            return
        
        origin_x, origin_y, origin_system = origin_coords
        dest_x, dest_y, dest_system = dest_coords
        
        # Calculate propagation from both gates
        recipients_from_origin = await self._calculate_radio_propagation(
            origin_x, origin_y, origin_system, message, interaction.guild.id
        )
        recipients_from_dest = await self._calculate_radio_propagation(
            dest_x, dest_y, dest_system, message, interaction.guild.id
        )
        
        # Combine and deduplicate recipients
        all_recipients = {}
        for recipient in recipients_from_origin:
            all_recipients[recipient['user_id']] = recipient
            if 'relay_path' not in recipient:
                recipient['relay_path'] = []
            recipient['relay_path'].append(f"Gate: {origin_name}")
        
        for recipient in recipients_from_dest:
            user_id = recipient['user_id']
            if user_id in all_recipients:
                # User can receive from both gates - use the stronger signal
                existing = all_recipients[user_id]
                if recipient['signal_strength'] > existing['signal_strength']:
                    recipient['relay_path'] = [f"Gate: {dest_name}"]
                    all_recipients[user_id] = recipient
                else:
                    # Keep existing but note dual relay
                    existing['relay_path'].append(f"Gate: {dest_name}")
            else:
                if 'relay_path' not in recipient:
                    recipient['relay_path'] = []
                recipient['relay_path'].append(f"Gate: {dest_name}")
                all_recipients[user_id] = recipient
        
        recipients = list(all_recipients.values())
        
        if not recipients:
            await interaction.response.send_message(
                f"📡 **Signal relayed through corridor gates**\n\nTransmission relayed from **{origin_name}** and **{dest_name}** gates, but no players are in range to receive it.",
                ephemeral=True
            )
            return
        
        # Group recipients by their current location and send to location channels
        await self._broadcast_to_location_channels(
            interaction.guild, char_name, callsign, f"Corridor Relay ({corridor_name})", 
            f"Gated Transit", message, recipients
        )
        
        # Special confirmation message for gated corridor transmission
        gate_info = f"{origin_name}"
        if origin_name != dest_name:
            gate_info += f" and {dest_name}"
        
        await interaction.response.send_message(
            f"📡 **Transmission relayed through corridor gates**\n\nYour message has been broadcast from the **{gate_info}** gate(s). Signal reached {len(recipients)} recipient(s) across {len(set(r['location'] for r in recipients))} location(s).",
            ephemeral=True
        )
    @radio_group.command(name="repeater", description="Deploy a portable radio repeater at your location")
    async def deploy_repeater(self, interaction: discord.Interaction):
        # Check if user has a repeater in inventory
        repeater_item = self.db.execute_query(
            "SELECT item_id, quantity FROM inventory WHERE owner_id = ? AND item_name = 'Portable Radio Repeater'",
            (interaction.user.id,),
            fetch='one'
        )
        
        if not repeater_item or repeater_item[1] <= 0:
            await interaction.response.send_message("You don't have a Portable Radio Repeater to deploy!", ephemeral=True)
            return
        
        # Get character location
        char_location = self.db.execute_query(
            "SELECT current_location FROM characters WHERE user_id = ?",
            (interaction.user.id,),
            fetch='one'
        )
        
        if not char_location or not char_location[0]:
            await interaction.response.send_message("You cannot deploy a repeater while stranded in space!", ephemeral=True)
            return
        
        location_id = char_location[0]
        
        # Check if there's already a repeater at this location
        existing_repeater = self.db.execute_query(
            "SELECT repeater_id FROM repeaters WHERE location_id = ? AND is_active = 1",
            (location_id,),
            fetch='one'
        )
        
        if existing_repeater:
            await interaction.response.send_message("There is already an active repeater at this location!", ephemeral=True)
            return
        
        # Deploy the repeater
        self.db.execute_query(
            '''INSERT INTO repeaters (location_id, owner_id, repeater_type, receive_range, transmit_range, is_active)
               VALUES (?, ?, 'portable', 10, 8, 1)''',
            (location_id, interaction.user.id)
        )
        
        # Remove repeater from inventory
        if repeater_item[1] == 1:
            self.db.execute_query(
                "DELETE FROM inventory WHERE item_id = ?",
                (repeater_item[0],)
            )
        else:
            self.db.execute_query(
                "UPDATE inventory SET quantity = quantity - 1 WHERE item_id = ?",
                (repeater_item[0],)
            )
        
        location_name = self.db.execute_query(
            "SELECT name FROM locations WHERE location_id = ?",
            (location_id,),
            fetch='one'
        )[0]
        
        embed = discord.Embed(
            title="📡 Repeater Deployed",
            description=f"Successfully deployed portable radio repeater at **{location_name}**",
            color=0x00ff00
        )
        embed.add_field(name="Receive Range", value="10 systems", inline=True)
        embed.add_field(name="Transmit Range", value="8 systems", inline=True)
        embed.add_field(name="Status", value="🟢 Active", inline=True)
        embed.add_field(
            name="📶 Effect",
            value="This repeater will extend radio coverage for all players in the area!",
            inline=False
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @radio_group.command(name="repeaters", description="View active repeaters in the galaxy")
    async def list_repeaters(self, interaction: discord.Interaction):
        repeaters = self.db.execute_query(
            '''SELECT r.repeater_id, r.repeater_type, r.receive_range, r.transmit_range,
                      l.name as location_name, l.system_name, c.name as owner_name
               FROM repeaters r
               JOIN locations l ON r.location_id = l.location_id
               LEFT JOIN characters c ON r.owner_id = c.user_id
               WHERE r.is_active = 1
               ORDER BY r.repeater_type DESC, l.name''',
            fetch='all'
        )
        
        if not repeaters:
            await interaction.response.send_message("No active repeaters found in the galaxy.", ephemeral=True)
            return
        
        embed = discord.Embed(
            title="📡 Active Radio Repeaters",
            description="Current radio infrastructure across the galaxy",
            color=0x4169E1
        )
        
        # Group by type
        built_in = []
        portable = []
        
        for repeater in repeaters:
            rep_id, rep_type, recv_range, trans_range, loc_name, system, owner = repeater
            
            if rep_type == 'built_in':
                built_in.append(f"📡 **{loc_name}** ({system}) - R{recv_range}/T{trans_range}")
            else:
                owner_text = f" (Owned by {owner})" if owner else ""
                portable.append(f"📻 **{loc_name}** ({system}) - R{recv_range}/T{trans_range}{owner_text}")
        
        if built_in:
            embed.add_field(
                name="🏢 Built-in Infrastructure",
                value="\n".join(built_in[:10]),
                inline=False
            )
        
        if portable:
            embed.add_field(
                name="📻 Portable Repeaters",
                value="\n".join(portable[:10]),
                inline=False
            )
        
        embed.add_field(
            name="📶 Coverage Legend",
            value="R = Receive Range | T = Transmit Range (in systems)",
            inline=False
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    async def _calculate_radio_propagation(self, sender_x: float, sender_y: float, 
                                         sender_system: str, message: str, guild_id: int) -> List[Dict]:
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
            
            if system_distance <= 10:  # Within max range
                # Apply message degradation based on distance
                degraded_message = self._degrade_message(message, system_distance)
                
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
        
        # Now check for repeaters and extended coverage
        recipients = await self._extend_via_repeaters(sender_x, sender_y, message, recipients)
        
        return recipients
    
    async def _extend_via_repeaters(self, sender_x: float, sender_y: float, 
                                  original_message: str, direct_recipients: List[Dict]) -> List[Dict]:
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
        signal_sources = [{'x': sender_x, 'y': sender_y, 'message': original_message, 'distance': 0, 'name': 'Origin'}]
        
        # Find repeaters that can receive the original signal
        for repeater in repeaters:
            rep_id, recv_range, trans_range, rep_x, rep_y, rep_name, rep_system = repeater
            
            # Check if repeater is in range of original signal
            distance_to_repeater = math.sqrt((rep_x - sender_x) ** 2 + (rep_y - sender_y) ** 2)
            system_distance = int(distance_to_repeater / 10)
            
            if system_distance <= recv_range:
                # Repeater receives signal - add it as a new source
                degraded_at_repeater = self._degrade_message(original_message, system_distance)
                signal_sources.append({
                    'x': rep_x, 
                    'y': rep_y, 
                    'message': degraded_at_repeater,
                    'distance': system_distance,
                    'range': trans_range,
                    'name': f"Repeater @ {rep_name}"
                })
        
        # Now recalculate coverage with all signal sources
        enhanced_recipients = {}
        
        # Get all potential recipients again
        all_players = self.db.execute_query(
            '''SELECT c.user_id, c.name, c.callsign, l.location_id, l.name as loc_name,
                      l.x_coord, l.y_coord, l.system_name
               FROM characters c
               JOIN locations l ON c.current_location = l.location_id
               WHERE c.current_location IS NOT NULL''',
            fetch='all'
        )
        
        for player in all_players:
            user_id, char_name, callsign, loc_id, loc_name, x, y, system = player
            
            # Skip sender
            if x == sender_x and y == sender_y:
                continue
            
            best_signal = None
            
            # Check signal from all sources
            for source in signal_sources:
                distance = math.sqrt((x - source['x']) ** 2 + (y - source['y']) ** 2)
                system_distance = int(distance / 10)
                
                # Check range (origin has 10, repeaters have their own range)
                max_range = source.get('range', 10)
                
                if system_distance <= max_range:
                    # Calculate final message degradation
                    total_degradation = source['distance'] + system_distance
                    final_message = self._degrade_message(original_message, total_degradation)
                    signal_strength = max(0, 100 - (total_degradation * 10))
                    
                    # Keep the strongest signal
                    if not best_signal or signal_strength > best_signal['signal_strength']:
                        relay_path = [source['name']] if source['name'] != 'Origin' else []
                        
                        best_signal = {
                            'user_id': user_id,
                            'char_name': char_name,
                            'callsign': callsign,
                            'location_id': loc_id,
                            'location': loc_name,
                            'system': system,
                            'distance': system_distance,
                            'message': final_message,
                            'signal_strength': signal_strength,
                            'relay_path': relay_path,
                            'source': source['name']
                        }
            
            if best_signal:
                enhanced_recipients[user_id] = best_signal
        
        return list(enhanced_recipients.values())
    
    def _degrade_message(self, message: str, system_distance: int) -> str:
        """Apply signal degradation to message based on distance"""
        
        if system_distance <= 5:
            return message  # Clear transmission
        
        # Calculate degradation percentage
        degradation_start = system_distance - 5  # Start degrading after 5 systems
        degradation_percent = min(80, degradation_start * 15)  # 15% per system beyond 5, max 80%
        
        if degradation_percent <= 0:
            return message
        
        # Apply character-level corruption
        corruption_chars = ['_', '-', '~', '#', '*', ' ']
        result = list(message)
        
        for i, char in enumerate(result):
            if char.isalnum():  # Only corrupt letters and numbers
                if random.random() * 100 < degradation_percent:
                    result[i] = random.choice(corruption_chars)
        
        return ''.join(result)
    
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
    
    async def _send_location_radio_message(self, guild: discord.Guild, location_id: int,
                                         sender_name: str, sender_callsign: str,
                                         sender_location: str, sender_system: str, 
                                         original_message: str, recipients: List[Dict]):
        """Send a radio message to a specific location channel"""
        
        # Get or create the location channel
        from utils.channel_manager import ChannelManager
        channel_manager = ChannelManager(self.bot)
        
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
        if not clear_receivers and degraded_receivers:
            # Only degraded reception - hide location
            location_display = "[UNKNOWN LOCATION]"
            system_display = ""
        else:
            # Clear reception available - show location
            system_display = f", {sender_system}"

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