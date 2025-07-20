import discord
from discord.ext import commands, tasks
from discord import app_commands
import asyncio
from datetime import datetime, timedelta
from typing import Optional

class BeaconView(discord.ui.View):
    def __init__(self, bot, user_id: int, beacon_type: str, location_id: int, item_id: int):
        super().__init__(timeout=300)
        self.bot = bot
        self.user_id = user_id
        self.beacon_type = beacon_type
        self.location_id = location_id
        self.item_id = item_id
        self.message_content = None

    @discord.ui.button(label="Set Beacon Message", style=discord.ButtonStyle.primary, emoji="📝")
    async def set_message(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This is not your beacon!", ephemeral=True)
            return

        if self.beacon_type == "emergency_beacon":
            modal = EmergencyBeaconModal(self)
        else:  # news_beacon
            modal = NewsBeaconModal(self)
        
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary, emoji="❌")
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This is not your beacon!", ephemeral=True)
            return

        await interaction.response.send_message("Beacon deployment cancelled.", ephemeral=True)

class EmergencyBeaconModal(discord.ui.Modal):
    def __init__(self, beacon_view):
        super().__init__(title="Emergency Beacon Configuration")
        self.beacon_view = beacon_view

    message = discord.ui.TextInput(
        label="Emergency Message",
        placeholder="Enter your distress message (max 500 characters)...",
        style=discord.TextStyle.paragraph,
        max_length=500,
        required=True
    )

    async def on_submit(self, interaction: discord.Interaction):
        # Defer the response first
        await interaction.response.defer(ephemeral=True)
        
        beacon_cog = self.beacon_view.bot.get_cog('BeaconSystemCog')
        if beacon_cog:
            success = await beacon_cog.deploy_emergency_beacon(
                self.beacon_view.user_id,
                self.beacon_view.location_id,
                self.message.value,
                self.beacon_view.item_id
            )
            
            if success:
                embed = discord.Embed(
                    title="🆘 Emergency Beacon Deployed",
                    description="Your emergency beacon has been activated and is transmitting your distress signal.",
                    color=0xff0000
                )
                embed.add_field(name="Message", value=f'"{self.message.value}"', inline=False)
                embed.add_field(name="Transmissions", value="3 times over 40 minutes", inline=True)
                embed.add_field(name="Range", value="Galactic radio network", inline=True)
                embed.set_footer(text="The beacon will continue transmitting even if you leave the area")
                
                await interaction.followup.send(embed=embed, ephemeral=True)
            else:
                await interaction.followup.send("Failed to deploy beacon!", ephemeral=True)

class NewsBeaconModal(discord.ui.Modal):
    def __init__(self, beacon_view):
        super().__init__(title="News Data-Stream Injection")
        self.beacon_view = beacon_view

    headline = discord.ui.TextInput(
        label="News Headline",
        placeholder="Enter headline for your data injection...",
        max_length=100,
        required=True
    )

    content = discord.ui.TextInput(
        label="News Content", 
        placeholder="Enter the news content you want to inject into the official stream...",
        style=discord.TextStyle.paragraph,
        max_length=1000,
        required=True
    )

    async def on_submit(self, interaction: discord.Interaction):
        # Defer the response first
        await interaction.response.defer(ephemeral=True)
        
        beacon_cog = self.beacon_view.bot.get_cog('BeaconSystemCog')
        if beacon_cog:
            success = await beacon_cog.deploy_news_beacon(
                self.beacon_view.user_id,
                self.beacon_view.location_id,
                self.headline.value,
                self.content.value,
                self.beacon_view.item_id
            )
            
            if success:
                embed = discord.Embed(
                    title="📰 News Data-Stream Injection Initiated",
                    description="Your data has been packaged for injection into the official news stream.",
                    color=0x00bfff
                )
                embed.add_field(name="Headline", value=self.headline.value, inline=False)
                embed.add_field(name="Content Preview", value=self.content.value[:200] + "..." if len(self.content.value) > 200 else self.content.value, inline=False)
                embed.add_field(name="Injection Status", value="⏳ Processing through news relays", inline=True)
                embed.set_footer(text="Your injection will appear in galactic news with appropriate transmission delay")
                
                await interaction.followup.send(embed=embed, ephemeral=True)
            else:
                await interaction.followup.send("Failed to inject data into news stream!", ephemeral=True)

class BeaconSystemCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = bot.db
        self.beacon_transmission_loop.start()

    def cog_unload(self):
        self.beacon_transmission_loop.cancel()

    @tasks.loop(minutes=1)  # Check every minute for beacons to transmit
    async def beacon_transmission_loop(self):
        """Handle beacon transmissions"""
        try:
            # Get beacons ready to transmit
            ready_beacons = self.db.execute_query(
                """SELECT beacon_id, beacon_type, user_id, location_id, message_content, 
                          transmissions_sent, max_transmissions
                   FROM active_beacons 
                   WHERE is_active = 1 
                   AND next_transmission <= datetime('now')
                   AND transmissions_sent < max_transmissions""",
                fetch='all'
            )
            
            for beacon_data in ready_beacons:
                beacon_id, beacon_type, user_id, location_id, message, sent, max_trans = beacon_data
                
                if beacon_type == "emergency_beacon":
                    await self._transmit_emergency_beacon(beacon_id, user_id, location_id, message)
                
                # Update beacon transmission count and next transmission time
                new_sent = sent + 1
                if new_sent >= max_trans:
                    # Beacon finished - deactivate
                    self.db.execute_query(
                        "UPDATE active_beacons SET is_active = 0 WHERE beacon_id = ?",
                        (beacon_id,)
                    )
                else:
                    # Schedule next transmission
                    next_time = datetime.utcnow() + timedelta(minutes=30)
                    self.db.execute_query(
                        """UPDATE active_beacons 
                           SET transmissions_sent = ?, next_transmission = ?
                           WHERE beacon_id = ?""",
                        (new_sent, next_time.isoformat(), beacon_id)
                    )
                
        except Exception as e:
            print(f"❌ Error in beacon transmission loop: {e}")

    @beacon_transmission_loop.before_loop
    async def before_beacon_transmission_loop(self):
        await self.bot.wait_until_ready()

    async def deploy_emergency_beacon(self, user_id: int, location_id: int, message: str, item_id: int) -> bool:
        """Deploy an emergency beacon"""
        try:
            # Remove item from inventory
            existing_item = self.db.execute_query(
                "SELECT quantity FROM inventory WHERE item_id = ?",
                (item_id,), fetch='one'
            )
            
            if not existing_item or existing_item[0] <= 0:
                return False
            
            if existing_item[0] == 1:
                self.db.execute_query("DELETE FROM inventory WHERE item_id = ?", (item_id,))
            else:
                self.db.execute_query(
                    "UPDATE inventory SET quantity = quantity - 1 WHERE item_id = ?", 
                    (item_id,)
                )
            
            # Create beacon record
            first_transmission = datetime.utcnow() + timedelta(seconds=30)  # First transmission in 30 seconds
            
            self.db.execute_query(
                """INSERT INTO active_beacons 
                   (beacon_type, user_id, location_id, message_content, next_transmission)
                   VALUES (?, ?, ?, ?, ?)""",
                ("emergency_beacon", user_id, location_id, message, first_transmission.isoformat())
            )
            
            return True
            
        except Exception as e:
            print(f"❌ Error deploying emergency beacon: {e}")
            return False

    async def deploy_news_beacon(self, user_id: int, location_id: int, headline: str, content: str, item_id: int) -> bool:
        """Deploy a news beacon"""
        try:
            # Remove item from inventory
            existing_item = self.db.execute_query(
                "SELECT quantity FROM inventory WHERE item_id = ?",
                (item_id,), fetch='one'
            )
            
            if not existing_item or existing_item[0] <= 0:
                return False
            
            if existing_item[0] == 1:
                self.db.execute_query("DELETE FROM inventory WHERE item_id = ?", (item_id,))
            else:
                self.db.execute_query(
                    "UPDATE inventory SET quantity = quantity - 1 WHERE item_id = ?", 
                    (item_id,)
                )
            
            # Get character info
            char_info = self.db.execute_query(
                "SELECT name, callsign FROM characters WHERE user_id = ?",
                (user_id,), fetch='one'
            )
            
            if not char_info:
                return False
            
            char_name, callsign = char_info
            
            # Get location info
            location_info = self.db.execute_query(
                "SELECT name, system_name FROM locations WHERE location_id = ?",
                (location_id,), fetch='one'
            )
            
            if not location_info:
                return False
            
            loc_name, system_name = location_info
            
            # Create news injection
            news_title = f"⚡ DATA-STREAM INJECTION: {headline}"
            news_content = f"**[UNAUTHORIZED DATA INJECTION DETECTED]**\n\n"
            news_content += f"**Source Analysis:** Signal intercepted from {loc_name} ({system_name} System)\n"
            news_content += f"**Injection Vector:** {char_name} [{callsign}]\n"
            news_content += f"**Security Classification:** Unverified Citizen Data\n\n"
            news_content += f"**Injected Content:**\n{content}\n\n"
            news_content += f"*Note: This content bypassed official news verification protocols. Galactic News Network assumes no responsibility for accuracy of injected data streams.*"
            
            # Queue through news system
            news_cog = self.bot.get_cog('GalacticNewsCog')
            if news_cog:
                # Get all guilds with news channels
                guilds_with_news = self.db.execute_query(
                    "SELECT guild_id FROM server_config WHERE galactic_updates_channel_id IS NOT NULL",
                    fetch='all'
                )
                
                for guild_tuple in guilds_with_news:
                    guild_id = guild_tuple[0]
                    await news_cog.queue_news(
                        guild_id, 'fluff_news', news_title, news_content, location_id
                    )
            
            return True
            
        except Exception as e:
            print(f"❌ Error deploying news beacon: {e}")
            return False

    async def _transmit_emergency_beacon(self, beacon_id: int, user_id: int, location_id: int, message: str):
        """Transmit emergency beacon signal"""
        try:
            # Get beacon location info
            location_info = self.db.execute_query(
                "SELECT name, x_coord, y_coord, system_name FROM locations WHERE location_id = ?",
                (location_id,), fetch='one'
            )
            
            if not location_info:
                return
            
            loc_name, x_coord, y_coord, system_name = location_info
            
            # Get character info
            char_info = self.db.execute_query(
                "SELECT name, callsign FROM characters WHERE user_id = ?",
                (user_id,), fetch='one'
            )
            
            if not char_info:
                return
            
            char_name, callsign = char_info
            
            # Get beacon transmission count
            transmission_info = self.db.execute_query(
                "SELECT transmissions_sent FROM active_beacons WHERE beacon_id = ?",
                (beacon_id,), fetch='one'
            )
            
            transmission_num = transmission_info[0] + 1 if transmission_info else 1
            
            # Use radio system for propagation
            radio_cog = self.bot.get_cog('RadioCog')
            if radio_cog:
                recipients = await radio_cog._calculate_radio_propagation(
                    x_coord, y_coord, system_name, message, 0  # Use 0 as guild_id for system message
                )
                
                if recipients:
                    # Group recipients by guild
                    guild_recipients = {}
                    for recipient in recipients:
                        member = self.bot.get_user(recipient['user_id'])
                        if member and member.mutual_guilds:
                            guild = member.mutual_guilds[0]
                            if guild.id not in guild_recipients:
                                guild_recipients[guild.id] = {'guild': guild, 'recipients': []}
                            guild_recipients[guild.id]['recipients'].append(recipient)
                    
                    # Send beacon messages to each guild
                    for guild_data in guild_recipients.values():
                        guild = guild_data['guild']
                        guild_recipients_list = guild_data['recipients']
                        
                        await self._send_beacon_transmission(
                            guild, char_name, callsign, loc_name, system_name, 
                            message, guild_recipients_list, transmission_num
                        )
            
            print(f"🆘 Emergency beacon transmission #{transmission_num} from {loc_name}")
            
        except Exception as e:
            print(f"❌ Error transmitting emergency beacon: {e}")

    async def _send_beacon_transmission(self, guild: discord.Guild, char_name: str, callsign: str,
                                      location_name: str, system_name: str, message: str,
                                      recipients: list, transmission_num: int):
        """Send beacon transmission to location channels"""
        
        # Group recipients by location
        location_groups = {}
        for recipient in recipients:
            location_id = recipient['location_id']
            if location_id not in location_groups:
                location_groups[location_id] = []
            location_groups[location_id].append(recipient)
        
        # Send to each location
        for location_id, location_recipients in location_groups.items():
            await self._send_location_beacon_message(
                guild, location_id, char_name, callsign, location_name, 
                system_name, message, location_recipients, transmission_num
            )

    async def _send_location_beacon_message(self, guild: discord.Guild, location_id: int,
                                          char_name: str, callsign: str, beacon_location: str,
                                          beacon_system: str, message: str, recipients: list, transmission_num: int):
        """Send beacon message to specific location channel"""
        
        # Get channel
        from utils.channel_manager import ChannelManager
        channel_manager = ChannelManager(self.bot)
        
        representative_member = None
        for recipient in recipients:
            member = guild.get_member(recipient['user_id'])
            if member:
                representative_member = member
                break
        
        if not representative_member:
            return
        
        channel = await channel_manager.get_or_create_location_channel(
            guild, location_id, representative_member, name, description, wealth
        )
        
        if not channel:
            return
        
        # Create special beacon embed
        embed = discord.Embed(
            title="🆘 EMERGENCY BEACON TRANSMISSION",
            color=0xff0000
        )
        
        embed.add_field(
            name="📡 Automated Distress Signal",
            value=f"**Transmission #{transmission_num}/3**\nBeacon deployed by: {char_name} [{callsign}]\n📍 Broadcasting from: {beacon_location}, {beacon_system}",
            inline=False
        )
        
        # Group recipients by signal quality
        clear_receivers = [r for r in recipients if r['signal_strength'] >= 70]
        degraded_receivers = [r for r in recipients if r['signal_strength'] < 70]
        
        signal_strength = clear_receivers[0]['signal_strength'] if clear_receivers else (degraded_receivers[0]['signal_strength'] if degraded_receivers else 0)
        signal_indicator = "🟢" if signal_strength >= 70 else ("📶" if signal_strength >= 30 else "📵")

        embed.add_field(
            name=f"📡 Emergency Signal {signal_indicator}",
            value=f"Beacon transmission received at this location\nSignal strength: {signal_strength}%",
            inline=False
        )
        
        # Show message (use clear version if available, otherwise degraded)
        display_message = message if clear_receivers else (degraded_receivers[0]['message'] if degraded_receivers else message)
        
        embed.add_field(
            name="🆘 Distress Message",
            value=f'"{display_message}"',
            inline=False
        )
        
        embed.add_field(
            name="⚠️ Beacon Status",
            value=f"**Transmission {transmission_num} of 3**\nNext transmission: {20 if transmission_num < 3 else 0} minutes\nSource: Automated emergency beacon",
            inline=False
        )
        
        embed.set_footer(text="Emergency Beacon Network • Automated Distress System")
        embed.timestamp = discord.utils.utcnow()
        
        try:
            await channel.send(embed=embed)
        except Exception as e:
            print(f"❌ Failed to send beacon message to {channel.name}: {e}")

async def setup(bot):
    await bot.add_cog(BeaconSystemCog(bot))