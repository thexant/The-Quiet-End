import discord
from discord import app_commands
from discord.ext import commands
import math
from datetime import datetime
from typing import Optional
import psycopg2
from utils.datetime_utils import safe_datetime_parse

class ContactsCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = bot.db
        
    @app_commands.command(name="contacts", description="Scan the galactic network for online operatives")
    async def contacts(self, interaction: discord.Interaction):
        """Display all online characters with their locations and travel status"""
        
        # Defer the response as this might take a moment
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)
        
        try:
            # Get all online characters
            online_chars = self.db.execute_query("""
                SELECT 
                    c.user_id,
                    c.name,
                    COALESCE(c.callsign, '[NO CALLSIGN]') as callsign,
                    c.current_location,
                    c.current_ship_id,
                    COALESCE(c.location_status, 'docked') as location_status,
                    COALESCE(l.name, 'Unknown Sector') as location_name,
                    CASE 
                        WHEN l.faction IS NULL THEN 'neutral' 
                        ELSE l.faction 
                    END as faction,
                    ts.corridor_id,
                    ts.origin_location,
                    ts.destination_location,
                    ts.start_time,
                    CASE 
                        WHEN ts.end_time IS NOT NULL THEN ts.end_time
                        ELSE ts.start_time + INTERVAL '1 second' * cor.travel_time
                    END as end_time,
                    cor.name as corridor_name,
                    orig.name as origin_name,
                    dest.name as dest_name
                FROM characters c
                LEFT JOIN locations l ON c.current_location = l.location_id
                LEFT JOIN travel_sessions ts ON c.user_id = ts.user_id AND ts.status = 'traveling'
                LEFT JOIN corridors cor ON ts.corridor_id = cor.corridor_id
                LEFT JOIN locations orig ON ts.origin_location = orig.location_id
                LEFT JOIN locations dest ON ts.destination_location = dest.location_id
                WHERE c.is_logged_in = TRUE
                ORDER BY c.name
            """, fetch='all')
        except psycopg2.Error as e:
            if "column" in str(e) and "does not exist" in str(e):
                # Fallback query for older databases
                online_chars = self.db.execute_query("""
                    SELECT 
                        c.user_id,
                        c.name,
                        COALESCE(c.callsign, '[NO CALLSIGN]') as callsign,
                        c.current_location,
                        c.current_ship_id,
                        'docked' as location_status,
                        COALESCE(l.name, 'Unknown Sector') as location_name,
                        'neutral' as faction,
                        ts.corridor_id,
                        ts.origin_location,
                        ts.destination_location,
                        ts.start_time,
                        CASE 
                            WHEN ts.end_time IS NOT NULL THEN ts.end_time
                            ELSE ts.start_time + INTERVAL '1 second' * cor.travel_time
                        END as end_time,
                        cor.name as corridor_name,
                        orig.name as origin_name,
                        dest.name as dest_name
                    FROM characters c
                    LEFT JOIN locations l ON c.current_location = l.location_id
                    LEFT JOIN travel_sessions ts ON c.user_id = ts.user_id AND ts.status = 'traveling'
                    LEFT JOIN corridors cor ON ts.corridor_id = cor.corridor_id
                    LEFT JOIN locations orig ON ts.origin_location = orig.location_id
                    LEFT JOIN locations dest ON ts.destination_location = dest.location_id
                    WHERE c.is_logged_in = TRUE
                    ORDER BY c.name
                """, fetch='all')
            else:
                raise e
        
        if not online_chars:
            embed = discord.Embed(
                title="🛰️ GALACTIC NETWORK SCAN",
                description="*No active signals detected in the network.*",
                color=0x00ff00,
                timestamp=datetime.utcnow()
            )
            embed.set_footer(text="GalNet Systems • Signal Strength: 0%")
            await interaction.followup.send(embed=embed, ephemeral=True)
            return
        
        # Create pages (10 contacts per page)
        contacts_per_page = 10
        total_pages = math.ceil(len(online_chars) / contacts_per_page)
        
        # Create the view with pagination buttons
        view = ContactsView(self.db, online_chars, contacts_per_page, interaction.user.id)
        
        # Send the first page
        try:
            embed = view.create_embed(0)
            await interaction.followup.send(embed=embed, view=view, ephemeral=True)
        except Exception as e:
            print(f"Error in contacts command: {e}")
            await interaction.followup.send(
                "⚠️ Error displaying contacts. Please try again later.",
                ephemeral=True
            )


class ContactsView(discord.ui.View):
    def __init__(self, db, contacts, per_page, user_id):
        super().__init__(timeout=300)  # 5 minute timeout
        self.db = db
        self.contacts = contacts
        self.per_page = per_page
        self.current_page = 0
        self.total_pages = math.ceil(len(contacts) / per_page)
        self.user_id = user_id
        
        # Update button states
        self.update_buttons()
    
    def create_embed(self, page: int) -> discord.Embed:
        """Create the embed for a specific page"""
        start_idx = page * self.per_page
        end_idx = min(start_idx + self.per_page, len(self.contacts))
        page_contacts = self.contacts[start_idx:end_idx]
        
        # Create the embed with galactic theme
        embed = discord.Embed(
            title="🛰️ GALACTIC NETWORK SCAN",
            description=f"*Detecting {len(self.contacts)} active signals across the galaxy...*\n\n",
            color=0x00ff00,
            timestamp=datetime.utcnow()
        )
        
        # Add contacts to this page
        for char in page_contacts:
            user_id, name, callsign, location_id, ship_id, status, loc_name, faction, \
            corridor_id, origin_id, dest_id, start_time, end_time, corridor_name, \
            origin_name, dest_name = char
            
            # Format the callsign
            if callsign and callsign != '[NO CALLSIGN]':
                callsign_display = f"[{callsign}]"
            else:
                callsign_display = "[NO CALLSIGN]"
            
            # Determine the character's status and location
            if corridor_id:  # Character is traveling
                # Calculate progress
                if start_time and end_time:
                    try:
                        # Handle both timestamp formats
                        if 'T' in start_time:
                            start = safe_datetime_parse(start_time.replace('Z', '+00:00'))
                            end = safe_datetime_parse(end_time.replace('Z', '+00:00'))
                        else:
                            start = datetime.strptime(start_time, '%Y-%m-%d %H:%M:%S')
                            end = datetime.strptime(end_time, '%Y-%m-%d %H:%M:%S')
                        
                        now = datetime.utcnow()
                        
                        # Make start timezone-aware if needed
                        if start.tzinfo is None:
                            start = start.replace(tzinfo=None)
                        if end.tzinfo is None:
                            end = end.replace(tzinfo=None)
                        
                        total_duration = (end - start).total_seconds()
                        elapsed = (now - start).total_seconds()
                        progress = min(100, max(0, (elapsed / total_duration) * 100))
                        
                        # Create progress bar
                        bar_length = 10
                        filled = int(progress / 100 * bar_length)
                        progress_bar = "█" * filled + "░" * (bar_length - filled)
                        
                        location_info = (
                            f"🚀 **IN TRANSIT**: {corridor_name or 'Hyperspace Corridor'}\n"
                            f"   ├─ Origin: {origin_name or 'Unknown'}\n"
                            f"   ├─ Destination: {dest_name or 'Unknown'}\n"
                            f"   └─ Progress: [{progress_bar}] {progress:.0f}%"
                        )
                    except Exception as e:
                        location_info = f"🚀 **IN TRANSIT**: {corridor_name or 'Hyperspace Corridor'}"
                else:
                    location_info = f"🚀 **IN TRANSIT**: {corridor_name or 'Hyperspace Corridor'}"
                    
            elif ship_id and not location_id:  # Character is in their ship interior
                try:
                    ship_info = self.db.execute_query(
                        "SELECT name, ship_type FROM ships WHERE ship_id = %s",
                        (ship_id,), fetch='one'
                    )
                    if ship_info:
                        ship_name, ship_type = ship_info
                        location_info = f"🚀 **SHIP INTERIOR**: {ship_name} ({ship_type})"
                    else:
                        location_info = "🚀 **SHIP INTERIOR**: Unknown Vessel"
                except:
                    location_info = "🚀 **SHIP INTERIOR**: Unknown Vessel"
                    
            elif location_id:  # Character is at a location
                status_icon = "🛬" if status == "docked" else "🚀"
                faction_tag = ""
                if faction and faction not in ['neutral', 'Independent']:
                    faction_tag = f" [{faction.upper()}]"
                location_info = f"{status_icon} **{loc_name}**{faction_tag}"
                
            else:  # Character location unknown
                location_info = "❓ **SIGNAL LOST** - Location Unknown"
            
            # Add field for this character
            embed.add_field(
                name=f"**{name}** {callsign_display}",
                value=location_info,
                inline=False
            )
        
        # Add footer with page info and theme elements
        signal_strength = max(20, 100 - (page * 5))  # Signal degrades with distance/pages
        embed.set_footer(
            text=f"GalNet Systems • Page {page + 1}/{self.total_pages} • Signal Strength: {signal_strength}%"
        )
        
        return embed
    
    def update_buttons(self):
        """Update button states based on current page"""
        # First page button
        self.first_page.disabled = self.current_page == 0
        self.prev_page.disabled = self.current_page == 0
        
        # Last page button
        self.next_page.disabled = self.current_page >= self.total_pages - 1
        self.last_page.disabled = self.current_page >= self.total_pages - 1
        
        # Update page counter
        self.page_counter.label = f"{self.current_page + 1}/{self.total_pages}"
    
    @discord.ui.button(label="◀◀", style=discord.ButtonStyle.primary, disabled=True)
    async def first_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Go to first page"""
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This panel is not for you!", ephemeral=True)
            return
            
        self.current_page = 0
        self.update_buttons()
        embed = self.create_embed(self.current_page)
        await interaction.response.edit_message(embed=embed, view=self)
    
    @discord.ui.button(label="◀", style=discord.ButtonStyle.primary, disabled=True)
    async def prev_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Go to previous page"""
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This panel is not for you!", ephemeral=True)
            return
            
        self.current_page -= 1
        self.update_buttons()
        embed = self.create_embed(self.current_page)
        await interaction.response.edit_message(embed=embed, view=self)
    
    @discord.ui.button(label="1/1", style=discord.ButtonStyle.secondary, disabled=True)
    async def page_counter(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Page counter - does nothing when clicked"""
        pass
    
    @discord.ui.button(label="▶", style=discord.ButtonStyle.primary)
    async def next_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Go to next page"""
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This panel is not for you!", ephemeral=True)
            return
            
        self.current_page += 1
        self.update_buttons()
        embed = self.create_embed(self.current_page)
        await interaction.response.edit_message(embed=embed, view=self)
    
    @discord.ui.button(label="▶▶", style=discord.ButtonStyle.primary)
    async def last_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Go to last page"""
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This panel is not for you!", ephemeral=True)
            return
            
        self.current_page = self.total_pages - 1
        self.update_buttons()
        embed = self.create_embed(self.current_page)
        await interaction.response.edit_message(embed=embed, view=self)
    
    @discord.ui.button(label="🔄 Refresh", style=discord.ButtonStyle.success)
    async def refresh(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Refresh the contact list"""
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This panel is not for you!", ephemeral=True)
            return
        
        try:
            # Re-fetch online characters
            self.contacts = self.db.execute_query("""
                SELECT 
                    c.user_id,
                    c.name,
                    COALESCE(c.callsign, '[NO CALLSIGN]') as callsign,
                    c.current_location,
                    c.current_ship_id,
                    COALESCE(c.location_status, 'docked') as location_status,
                    COALESCE(l.name, 'Unknown Sector') as location_name,
                    CASE 
                        WHEN l.faction IS NULL THEN 'neutral' 
                        ELSE l.faction 
                    END as faction,
                    ts.corridor_id,
                    ts.origin_location,
                    ts.destination_location,
                    ts.start_time,
                    CASE 
                        WHEN ts.end_time IS NOT NULL THEN ts.end_time
                        ELSE ts.start_time + INTERVAL '1 second' * cor.travel_time
                    END as end_time,
                    cor.name as corridor_name,
                    orig.name as origin_name,
                    dest.name as dest_name
                FROM characters c
                LEFT JOIN locations l ON c.current_location = l.location_id
                LEFT JOIN travel_sessions ts ON c.user_id = ts.user_id AND ts.status = 'traveling'
                LEFT JOIN corridors cor ON ts.corridor_id = cor.corridor_id
                LEFT JOIN locations orig ON ts.origin_location = orig.location_id
                LEFT JOIN locations dest ON ts.destination_location = dest.location_id
                WHERE c.is_logged_in = TRUE
                ORDER BY c.name
            """, fetch='all')
        except psycopg2.Error as e:
            if "column" in str(e) and "does not exist" in str(e):
                # Fallback query for older databases
                self.contacts = self.db.execute_query("""
                    SELECT 
                        c.user_id,
                        c.name,
                        COALESCE(c.callsign, '[NO CALLSIGN]') as callsign,
                        c.current_location,
                        c.current_ship_id,
                        'docked' as location_status,
                        COALESCE(l.name, 'Unknown Sector') as location_name,
                        'neutral' as faction,
                        ts.corridor_id,
                        ts.origin_location,
                        ts.destination_location,
                        ts.start_time,
                        CASE 
                            WHEN ts.end_time IS NOT NULL THEN ts.end_time
                            ELSE ts.start_time + INTERVAL '1 second' * cor.travel_time
                        END as end_time,
                        cor.name as corridor_name,
                        orig.name as origin_name,
                        dest.name as dest_name
                    FROM characters c
                    LEFT JOIN locations l ON c.current_location = l.location_id
                    LEFT JOIN travel_sessions ts ON c.user_id = ts.user_id AND ts.status = 'traveling'
                    LEFT JOIN corridors cor ON ts.corridor_id = cor.corridor_id
                    LEFT JOIN locations orig ON ts.origin_location = orig.location_id
                    LEFT JOIN locations dest ON ts.destination_location = dest.location_id
                    WHERE c.is_logged_in = TRUE
                    ORDER BY c.name
                """, fetch='all')
            else:
                raise e
        
        # Recalculate pages
        self.total_pages = math.ceil(len(self.contacts) / self.per_page)
        if self.current_page >= self.total_pages:
            self.current_page = max(0, self.total_pages - 1)
        
        self.update_buttons()
        embed = self.create_embed(self.current_page)
        await interaction.response.edit_message(embed=embed, view=self)


async def setup(bot):
    await bot.add_cog(ContactsCog(bot))