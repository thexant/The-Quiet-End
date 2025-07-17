# utils/channel_manager.py - IMPROVED VERSION
import discord
import asyncio
from datetime import datetime, timedelta
from typing import Optional, List, Tuple
import re
from utils.ship_activities import ShipActivityManager, ShipActivityView

class ChannelManager:
    """
    Manages on-demand creation and cleanup of location channels
    """
    
    def __init__(self, bot):
        self.bot = bot
        self.db = bot.db
        self.active_location_messages = {}
        # Default configuration (will be overridden by server config)
        self.max_location_channels = 50
        self.channel_timeout_hours = 48
        self.cleanup_batch_size = 5
        self.auto_cleanup_enabled = True
        
        # Category cache
        self._category_cache = {}
        
        # Track active location messages to clean them up
        self._active_location_messages = {}  # {user_id: {location_id: message_id}}
        
        # Start background cleanup task
        self._start_background_cleanup()
    
    def _start_background_cleanup(self):
        """Start the background cleanup task"""
        async def background_cleanup():
            while True:
                try:
                    await asyncio.sleep(60)  # Increased from 30 seconds to reduce conflicts
                    
                    # Get all guilds the bot is in
                    for guild in self.bot.guilds:
                        try:
                            # Use a timeout for cleanup operations
                            await asyncio.wait_for(
                                self._check_and_cleanup_empty_channels(guild),
                                timeout=30.0  # 30 second timeout
                            )
                        except asyncio.TimeoutError:
                            print(f"⚠️ Channel cleanup timed out for guild {guild.name}")
                            continue
                        except Exception as e:
                            print(f"❌ Error in channel cleanup for guild {guild.name}: {e}")
                            continue
                        
                        # Yield between guilds
                        await asyncio.sleep(1)
                            
                except Exception as e:
                    print(f"❌ Error in background cleanup: {e}")
                    await asyncio.sleep(120)  # Wait longer if there's an error
        
        # Start the background task
        self.bot.loop.create_task(background_cleanup())
    
    async def _load_server_config(self, guild: discord.Guild):
        """Load server-specific configuration"""
        config = self.db.execute_query(
            '''SELECT max_location_channels, channel_timeout_hours, auto_cleanup_enabled
               FROM server_config WHERE guild_id = ?''',
            (guild.id,),
            fetch='one'
        )
        
        if config:
            self.max_location_channels = config[0] or 50
            self.channel_timeout_hours = config[1] or 48
            self.auto_cleanup_enabled = config[2] if config[2] is not None else True
        
    async def get_or_create_location_channel(self, guild: discord.Guild, location_id: int, user: discord.Member = None) -> Optional[discord.TextChannel]:
        """
        Get existing channel for location or create one if needed
        Returns None if location doesn't exist
        """
        # Load server configuration
        await self._load_server_config(guild)
        
        # Get location info
        location_info = self.db.execute_query(
            '''SELECT location_id, channel_id, name, location_type, description, wealth_level
               FROM locations WHERE location_id = ?''',
            (location_id,),
            fetch='one'
        )
        
        if not location_info:
            return None
        
        loc_id, channel_id, name, loc_type, description, wealth = location_info
        
        # Check if channel already exists
        if channel_id:
            channel = guild.get_channel(channel_id)
            if channel:
                # Update last active time
                await self._update_channel_activity(location_id)
                return channel
            else:
                # Channel was deleted, clear the reference
                self.db.execute_query(
                    "UPDATE locations SET channel_id = NULL, channel_last_active = NULL WHERE location_id = ?",
                    (location_id,)
                )
        
        # Need to create new channel
        channel = await self._create_location_channel(guild, location_info, user)
        return channel
    
    async def get_or_create_home_channel(self, guild: discord.Guild, home_info: tuple, user: discord.Member = None) -> Optional[discord.TextChannel]:
        """
        Get existing channel for home or create one if needed
        """
        home_id, home_name, location_id, interior_desc, channel_id = home_info
        
        # Check if channel already exists
        if channel_id:
            channel = guild.get_channel(channel_id)
            if channel:
                return channel
            else:
                # Channel was deleted, clear the reference
                self.db.execute_query(
                    "UPDATE home_interiors SET channel_id = NULL WHERE home_id = ?",
                    (home_id,)
                )
        
        # Create new home channel
        channel = await self._create_home_channel(guild, home_info, user)
        return channel

    async def _create_home_channel(self, guild: discord.Guild, home_info: tuple, requesting_user: discord.Member = None) -> Optional[discord.TextChannel]:
        """
        Create a new Discord channel for a home interior
        """
        home_id, home_name, location_id, interior_desc, channel_id = home_info
        
        try:
            # Generate safe channel name
            channel_name = self._generate_home_channel_name(home_name)
            
            # Create channel topic
            topic = f"Home Interior: {home_name}"
            if interior_desc:
                topic += f" | {interior_desc[:100]}"
            
            # Set up permissions - start with no access for @everyone
            overwrites = {
                guild.default_role: discord.PermissionOverwrite(read_messages=False, send_messages=False)
            }
            
            # Give access to requesting user if provided
            if requesting_user:
                overwrites[requesting_user] = discord.PermissionOverwrite(read_messages=True, send_messages=True)
            
            # Find or create category for home channels
            category = await self._get_or_create_home_category(guild)
            
            # Create the channel
            channel = await guild.create_text_channel(
                channel_name,
                category=category,
                topic=topic,
                overwrites=overwrites,
                reason=f"Home interior channel for: {home_name}"
            )
            
            # Update database with channel info
            self.db.execute_query(
                "INSERT OR REPLACE INTO home_interiors (home_id, channel_id) VALUES (?, ?)",
                (home_id, channel.id)
            )
            
            # Send welcome message to channel
            await self._send_home_welcome(channel, home_info)
            
            print(f"🏠 Created home channel #{channel_name} for {home_name}")
            return channel
            
        except Exception as e:
            print(f"❌ Failed to create home channel for {home_name}: {e}")
            return None

    def _generate_home_channel_name(self, home_name: str) -> str:
        """Generate a Discord-safe channel name for homes"""
        import re
        safe_name = re.sub(r'[^\w\s-]', '', home_name.lower())
        safe_name = re.sub(r'\s+', '-', safe_name)
        safe_name = safe_name.strip('-')
        
        # Add home prefix
        home_prefix = "home"
        
        # Ensure name isn't too long
        max_name_length = 85 - len(home_prefix)
        if len(safe_name) > max_name_length:
            safe_name = safe_name[:max_name_length].rstrip('-')
        
        return f"{home_prefix}-{safe_name}"

    async def _get_or_create_home_category(self, guild: discord.Guild) -> Optional[discord.CategoryChannel]:
        """
        Get the residences category from the server config.
        """
        category_id = self.db.execute_query(
            "SELECT residences_category_id FROM server_config WHERE guild_id = ?",
            (guild.id,),
            fetch='one'
        )
        
        if category_id and category_id[0]:
            category = guild.get_channel(category_id[0])
            if isinstance(category, discord.CategoryChannel):
                return category
        
        # Fallback for safety
        for cat in guild.categories:
            if cat.name == '🏠 RESIDENCES':
                return cat
        
        return None

    async def _send_home_welcome(self, channel: discord.TextChannel, home_info: tuple):
        """Send a welcome message to a newly created home channel"""
        home_id, home_name, location_id, interior_desc, channel_id = home_info
        
        # Get owner info
        owner_id = self.db.execute_query(
            "SELECT owner_id FROM location_homes WHERE home_id = ?",
            (home_id,),
            fetch='one'
        )[0]
        
        owner_name = self.db.execute_query(
            "SELECT name FROM characters WHERE user_id = ?",
            (owner_id,),
            fetch='one'
        )[0]
        
        # Get home customizations
        customizations = self.db.execute_query(
            '''SELECT wall_color, floor_type, lighting_style, furniture_style, ambiance
               FROM home_customizations WHERE home_id = ?''',
            (home_id,),
            fetch='one'
        )
        
        # Set defaults if no customization exists
        if not customizations:
            customizations = ('Beige', 'Standard Tile', 'Standard', 'Basic', 'Cozy')
        
        wall_color, floor_type, lighting, furniture, ambiance = customizations
        
        # Generate dynamic interior description based on customizations
        custom_desc = self._generate_custom_interior_description(
            interior_desc, wall_color, floor_type, lighting, furniture, ambiance
        )
        
        embed = discord.Embed(
            title=f"🏠 Welcome to {home_name}",
            description=custom_desc,
            color=self._get_color_from_wall(wall_color)
        )
        
        # Add customization details field
        embed.add_field(
            name="🎨 Current Theme",
            value=(
                f"**Walls:** {wall_color}\n"
                f"**Flooring:** {floor_type}\n"
                f"**Lighting:** {lighting}\n"
                f"**Furniture:** {furniture}\n"
                f"**Ambiance:** {ambiance}"
            ),
            inline=True
        )
        
        # Get home activities - Import here to avoid circular imports
        try:
            from utils.home_activities import HomeActivityManager
            activity_manager = HomeActivityManager(self.bot)
            activities = activity_manager.get_home_activities(home_id)
            
            if activities:
                activity_list = []
                for activity in activities[:8]:
                    activity_list.append(f"{activity['icon']} {activity['name']}")
                
                embed.add_field(
                    name="🎮 Home Facilities",
                    value="\n".join(activity_list),
                    inline=True
                )
        except ImportError:
            # HomeActivityManager not available, skip activities
            activities = None
        
        embed.add_field(
            name="🎮 Available Actions",
            value=(
                "• Use the activity buttons below\n" if activities else ""
                "• `/home customize theme` - View/change theme\n"
                "• `/home interior leave` - Exit your home\n"
                "• `/home interior invite` - Invite someone"
            ),
            inline=False
        )
        
        try:
            await channel.send(embed=embed)
            
            # Send activity buttons if available
            if activities:
                try:
                    from utils.home_activities import HomeActivityView
                    activity_view = HomeActivityView(self.bot, home_id, home_name, owner_name)
                    activity_embed = discord.Embed(
                        title="🎯 Home Activities",
                        description="Choose an activity:",
                        color=0x00ff88
                    )
                    await channel.send(embed=activity_embed, view=activity_view)
                except ImportError:
                    pass
                    
        except Exception as e:
            print(f"❌ Failed to send home welcome message: {e}")
    
    
    def _generate_custom_interior_description(self, base_desc, wall_color, floor_type, lighting, furniture, ambiance):
        """Generate a dynamic description based on customizations"""
        if base_desc:
            desc = base_desc + "\n\n"
        else:
            desc = ""
        
        # Add atmospheric description based on customizations
        atmosphere_map = {
            ('Beige', 'Standard Tile', 'Standard', 'Basic', 'Cozy'): 
                "The warm beige walls and standard tile flooring create a simple, comfortable atmosphere.",
            ('Gray', 'Hardwood', 'Dim', 'Modern', 'Relaxing'): 
                "Soft gray walls complement the hardwood floors, while dim lighting creates a relaxing modern sanctuary.",
            ('Blue', 'Carpet', 'Bright', 'Luxury', 'Elegant'): 
                "Deep navy walls paired with plush carpeting and bright lighting showcase the elegant luxury furnishings.",
            ('Black', 'Marble', 'Neon', 'Industrial', 'Chaotic'): 
                "Dramatic black walls and gleaming marble floors are accentuated by neon lighting, creating an energetic industrial vibe.",
            ('Crimson', 'Stone', 'Candlelit', 'Federation', 'Calm'): 
                "Rich crimson walls and ancient stone floors are bathed in flickering candlelight, highlighting the Federation style furnishings.",
        }
        
        # Try to find exact match
        key = (wall_color, floor_type, lighting, furniture, ambiance)
        if key in atmosphere_map:
            desc += atmosphere_map[key]
        else:
            # Generate dynamic description
            desc += f"The {wall_color.lower()} walls are complemented by {floor_type.lower()} flooring. "
            desc += f"{lighting} lighting illuminates the {furniture.lower()} furniture, creating a {ambiance.lower()} atmosphere."
        
        return desc

    def _get_color_from_wall(self, wall_color):
        """Get Discord embed color based on wall color"""
        color_map = {
            'Beige': 0xF5DEB3,
            'Gray': 0x808080,
            'White': 0xFFFFFF,
            'Navy': 0x000080,
            'Green': 0x228B22,
            'Black': 0x000000,
            'Crimson': 0xDC143C,
            'Purple': 0x9370DB
        }
        return color_map.get(wall_color, 0x8B4513)  # Default brown
    
    async def give_user_home_access(self, user: discord.Member, home_id: int) -> bool:
        """Give a user access to a home's channel"""
        home_channel = self.db.execute_query(
            "SELECT channel_id FROM home_interiors WHERE home_id = ?",
            (home_id,),
            fetch='one'
        )
        
        if not home_channel or not home_channel[0]:
            return False
        
        channel = user.guild.get_channel(home_channel[0])
        if not channel:
            return False
        
        try:
            await channel.set_permissions(user, read_messages=True, send_messages=True)
            return True
        except Exception as e:
            print(f"❌ Failed to give {user.name} home access: {e}")
            return False

    async def remove_user_home_access(self, user: discord.Member, home_id: int) -> bool:
        """Remove a user's access to a home channel"""
        home_channel = self.db.execute_query(
            "SELECT channel_id FROM home_interiors WHERE home_id = ?",
            (home_id,),
            fetch='one'
        )
        
        if not home_channel or not home_channel[0]:
            return True
        
        channel = user.guild.get_channel(home_channel[0])
        if not channel:
            return True
        
        try:
            await channel.set_permissions(user, overwrite=None)
            return True
        except Exception as e:
            print(f"❌ Failed to remove {user.name} home access: {e}")
            return False

    async def cleanup_home_channel(self, channel_id: int):
        """Delete a home channel immediately"""
        channel = self.bot.get_channel(channel_id)
        if channel:
            try:
                await channel.delete(reason="Home interior cleanup")
                print(f"🏠 Cleaned up home channel #{channel.name}")
            except Exception as e:
                print(f"❌ Failed to delete home channel: {e}")
        
        # Clear from database
        self.db.execute_query(
            "UPDATE home_interiors SET channel_id = NULL WHERE channel_id = ?",
            (channel_id,)
        )
    async def get_location_statistics(self, guild: discord.Guild) -> dict:
        """
        Get comprehensive statistics about location channel usage
        """
        # Load server config
        await self._load_server_config(guild)
        
        # Get total locations
        total_locations = self.db.execute_query(
            "SELECT COUNT(*) FROM locations",
            fetch='one'
        )[0]
        
        # Get locations with active channels
        active_channels = self.db.execute_query(
            "SELECT COUNT(*) FROM locations WHERE channel_id IS NOT NULL",
            fetch='one'
        )[0]
        
        # Get recently active channels (last 24 hours)
        recently_active = self.db.execute_query(
            "SELECT COUNT(*) FROM locations WHERE channel_id IS NOT NULL AND channel_last_active > datetime('now', '-24 hours')",
            fetch='one'
        )[0]
        
        # Calculate capacity usage
        channel_capacity = self.max_location_channels
        capacity_usage = (active_channels / channel_capacity) * 100 if channel_capacity > 0 else 0
        
        return {
            'total_locations': total_locations,
            'active_channels': active_channels,
            'recently_active': recently_active,
            'channel_capacity': channel_capacity,
            'capacity_usage': capacity_usage
        }

    async def cleanup_channels_task(self, guild: discord.Guild):
        """
        Manual cleanup task for channels - wrapper for the internal cleanup method
        """
        await self._cleanup_old_channels(guild, force=False)
    async def _create_location_channel(self, guild: discord.Guild, location_info: Tuple, requesting_user: discord.Member = None) -> Optional[discord.TextChannel]:
        """
        Create a new Discord channel for a location
        """
        loc_id, channel_id, name, loc_type, description, wealth = location_info
        
        # Check if we need to clean up old channels first
        await self._cleanup_old_channels_if_needed(guild)
        
        try:
            # Generate safe channel name
            channel_name = self._generate_channel_name(name, loc_type)
            
            # Create channel topic
            wealth_stars = "⭐" * min(wealth // 2, 5)
            topic = f"{loc_type.replace('_', ' ').title()}: {name} {wealth_stars}"
            if description:
                topic += f" | {description[:100]}"
            
            # Set up permissions - start with no access for @everyone
            overwrites = {
                guild.default_role: discord.PermissionOverwrite(read_messages=False, send_messages=False)
            }
            
            # Give access to requesting user if provided
            if requesting_user:
                overwrites[requesting_user] = discord.PermissionOverwrite(read_messages=True, send_messages=True)
            
            # Find or create category for location channels
            category = await self._get_or_create_location_category(guild, loc_type)
            
            # Create the channel
            channel = await guild.create_text_channel(
                channel_name,
                category=category,
                topic=topic,
                overwrites=overwrites,
                reason=f"On-demand creation for location: {name}"
            )
            
            # Update database with channel info
            current_time = datetime.now()
            self.db.execute_query(
                '''UPDATE locations 
                   SET channel_id = ?, channel_last_active = ?
                   WHERE location_id = ?''',
                (channel.id, current_time, loc_id)
            )
            
            # Send welcome message to channel with available routes
            await self._send_location_welcome(channel, location_info)
            
            print(f"📍 Created location channel #{channel_name} for {name}")
            return channel
            
        except Exception as e:
            print(f"❌ Failed to create channel for {name}: {e}")
            return None
    
    def _generate_channel_name(self, location_name: str, location_type: str) -> str:
        """Generate a Discord-safe channel name with activity indicator"""
        # Remove special characters and convert to lowercase
        safe_name = re.sub(r'[^\w\s-]', '', location_name.lower())
        safe_name = re.sub(r'\s+', '-', safe_name)
        safe_name = safe_name.strip('-')
        
        # Add type prefix for clarity
        type_prefix = {
            'colony': 'col',
            'space_station': 'sta',
            'outpost': 'out',
            'gate': 'gate'
        }.get(location_type, 'loc')
        
        # Ensure name isn't too long (Discord limit is 100 chars)
        max_name_length = 85 - len(type_prefix)  # Leave room for indicators
        if len(safe_name) > max_name_length:
            safe_name = safe_name[:max_name_length].rstrip('-')
        
        return f"{type_prefix}-{safe_name}"
    
    async def _get_or_create_location_category(self, guild: discord.Guild, location_type: str) -> Optional[discord.CategoryChannel]:
        """
        Get configured category for location type from server config
        """
        # Map location types to config columns
        category_mapping = {
            'colony': 'colony_category_id',
            'space_station': 'station_category_id', 
            'outpost': 'outpost_category_id',
            'gate': 'gate_category_id'
        }
        
        config_column = category_mapping.get(location_type)
        if not config_column:
            return None
        
        # Get category ID from server config
        category_id = self.db.execute_query(
            f"SELECT {config_column} FROM server_config WHERE guild_id = ?",
            (guild.id,),
            fetch='one'
        )
        
        if not category_id or not category_id[0]:
            # Fallback to creating/finding by name if no config
            return await self._fallback_category_creation(guild, location_type)
        
        # Get the configured category
        category = guild.get_channel(category_id[0])
        if category and isinstance(category, discord.CategoryChannel):
            return category
        
        # Category was deleted, fallback to creation
        return await self._fallback_category_creation(guild, location_type)
    
    async def _fallback_category_creation(self, guild: discord.Guild, location_type: str) -> Optional[discord.CategoryChannel]:
        """
        Fallback category creation if server config is missing
        """
        category_names = {
            'colony': '🏭 COLONIES',
            'space_station': '🛰️ SPACE STATIONS',
            'outpost': '🛤️ OUTPOSTS',
            'gate': '🚪 GATES'
        }
        
        category_name = category_names.get(location_type, '📍 LOCATIONS')
        
        # Look for existing category
        for category in guild.categories:
            if category.name == category_name:
                return category
        
        # Create new category if it doesn't exist
        try:
            category = await guild.create_category(
                category_name,
                reason=f"Auto-created category for {location_type} locations"
            )
            return category
        except Exception as e:
            print(f"❌ Failed to create category {category_name}: {e}")
            return None
    
    async def _send_location_welcome(self, channel: discord.TextChannel, location_info: Tuple):
        """Send a welcome message to a newly created location channel with available routes"""
        loc_id, channel_id, name, loc_type, description, wealth = location_info
        
        # Get services info including alignment flags
        services_info = self.db.execute_query(
            '''SELECT has_jobs, has_shops, has_medical, has_repairs, has_fuel, has_upgrades, population,
                      has_federal_supplies, has_black_market, has_shipyard
               FROM locations WHERE location_id = ?''',
            (loc_id,),
            fetch='one'
        )
        
        if not services_info:
            return
        # Get available homes info
        homes_info = self.db.execute_query(
            '''SELECT COUNT(*), MIN(price), MAX(price), home_type
               FROM location_homes 
               WHERE location_id = ? AND is_available = 1
               GROUP BY home_type''',
            (loc_id,),
            fetch='all'
        )

        (has_jobs, has_shops, has_medical, has_repairs, has_fuel, has_upgrades, 
        population, has_federal_supplies, has_black_market, has_shipyard) = services_info
        # Get available homes info
        homes_info = self.db.execute_query(
            '''SELECT COUNT(*), MIN(price), MAX(price), home_type
               FROM location_homes 
               WHERE location_id = ? AND is_available = 1
               GROUP BY home_type''',
            (loc_id,),
            fetch='all'
        )


        # Determine location status and enhance description
        location_status = None
        status_emoji = ""
        enhanced_description = description
        embed_color = 0x4169E1  # Default blue
        
        if has_federal_supplies:
            location_status = "Loyal"
            status_emoji = "🏛️"
            embed_color = 0x0066cc  # Federal blue
            # Add federal flair to description
            if enhanced_description:
                enhanced_description += "\n\n🏛️ **Federal Territory:** This location operates under direct federal oversight with enhanced security protocols and premium government-grade supplies."
            else:
                enhanced_description = "🏛️ **Federal Territory:** This location operates under direct federal oversight with enhanced security protocols and premium government-grade supplies."
        elif has_black_market:
            location_status = "Bandit"
            status_emoji = "💀"
            embed_color = 0x8b0000  # Dark red
            # Add bandit flair to description
            if enhanced_description:
                enhanced_description += "\n\n💀 **Outlaw Haven:** This location operates outside federal jurisdiction. Discretion is advised, and contraband trade flourishes in the shadows."
            else:
                enhanced_description = "💀 **Outlaw Haven:** This location operates outside federal jurisdiction. Discretion is advised, and contraband trade flourishes in the shadows."
        
        # Create welcome embed with status-aware styling
        title_with_status = f"📍 Welcome to {name}"
        if location_status:
            title_with_status = f"{status_emoji} Welcome to {name}"
        
        embed = discord.Embed(
            title=title_with_status,
            description=enhanced_description,
            color=embed_color
        )
        
        # Location details
        type_emoji = {
            'colony': '🏭',
            'space_station': '🛰️',
            'outpost': '🛤️',
            'gate': '🚪'
        }.get(loc_type, '📍')
        
        embed.add_field(
            name="Location Type",
            value=f"{type_emoji} {loc_type.replace('_', ' ').title()}",
            inline=True
        )
        
        embed.add_field(
            name="Population",
            value=f"{population:,}",
            inline=True
        )
        
        # Add status field if location has special alignment
        if location_status:
            embed.add_field(
                name="Status",
                value=f"{status_emoji} **{location_status}**",
                inline=True
            )
        else:
            # Keep the wealth field in the same position for normal locations
            wealth_text = "⭐" * min(wealth // 2, 5) if wealth > 0 else "💸"
            embed.add_field(
                name="Wealth Level",
                value=f"{wealth_text} {wealth}/10",
                inline=True
            )
        
        # For aligned locations, show wealth in a separate row for better formatting
        if location_status:
            wealth_text = "⭐" * min(wealth // 2, 5) if wealth > 0 else "💸"
            embed.add_field(
                name="Wealth Level",
                value=f"{wealth_text} {wealth}/10",
                inline=True
            )
            # Add empty field for better formatting
            embed.add_field(name="", value="", inline=True)
            embed.add_field(name="", value="", inline=True)
        
        # Available services with status-aware enhancements
        services = []
        if has_jobs:   services.append("💼 Jobs")
        if has_shops:  services.append("🛒 Shopping")
        if has_medical:services.append("⚕️ Medical")
        if has_repairs:services.append("🔨 Repairs")
        if has_fuel:   services.append("⛽ Fuel")
        if has_upgrades:services.append("⬆️ Upgrades")
        if has_shipyard: services.append("🏗️ Shipyard") 
        
        # Add special services based on status
        if has_federal_supplies:
            services.append("🏛️ Federal Supplies")
        if has_black_market:
            services.append("💀 Black Market")

        if services:
            embed.add_field(
                name="Available Services",
                value=" • ".join(services),
                inline=False
            )
                # Add to the embed after the services section:
        if homes_info:
            homes_text = []
            for count, min_price, max_price, home_type in homes_info:
                if count == 1:
                    homes_text.append(f"• **{count} {home_type}** - {min_price:,} credits")
                else:
                    homes_text.append(f"• **{count} {home_type}s** - {min_price:,}-{max_price:,} credits")
            
            embed.add_field(
                name="🏠 Available Homes",
                value="\n".join(homes_text),
                inline=True
            )
        # STATIC NPCS
        npc_cog = self.bot.get_cog('NPCCog')
        if npc_cog:
            static_npcs = npc_cog.get_static_npcs_for_location(loc_id)
            if static_npcs:
                npc_list = [f"{name} - {age}" for name, age in static_npcs[:5]]  # Limit to 5 for space
                if len(static_npcs) > 5:
                    npc_list.append(f"...and {len(static_npcs) - 5} more")
                
                npc_field_name = "Notable NPCs"
                if location_status == "Loyal":
                    npc_field_name = "🏛️ Federal Personnel"
                elif location_status == "Bandit":
                    npc_field_name = "💀 Local Contacts"
                
                embed.add_field(
                    name=npc_field_name,
                    value="\n".join(npc_list),
                    inline=False
                )
        
        # LOGBOOK PRESENCE
        log_count = self.db.execute_query(
            "SELECT COUNT(*) FROM location_logs WHERE location_id = ?",
            (loc_id,),
            fetch='one'
        )[0]
        embed.add_field(
            name="📓 Logbook",
            value="Available" if log_count > 0 else "None",
            inline=True
        )

        # Get available routes and display them
        routes = self.db.execute_query(
            '''SELECT c.name, l.name as dest_name, l.location_type as dest_type, c.travel_time, c.danger_level
               FROM corridors c
               JOIN locations l ON c.destination_location = l.location_id
               WHERE c.origin_location = ? AND c.is_active = 1
               ORDER BY c.travel_time
               LIMIT 8''',
            (loc_id,),
            fetch='all'
        )
        
        if routes:
            route_lines = []
            for corridor_name, dest_name, dest_type, travel_time, danger in routes:
                # Determine route type and emoji
                if "Approach" in corridor_name:
                    route_emoji = "🌌"  # Local space
                elif "Ungated" in corridor_name:
                    route_emoji = "⭕️"  # Dangerous ungated
                else:
                    route_emoji = "🔵"  # Safe gated
                
                dest_emoji = {
                    'colony': '🏭',
                    'space_station': '🛰️',
                    'outpost': '🛤️',
                    'gate': '🚪'
                }.get(dest_type, '📍')
                
                # Format time
                mins = travel_time // 60
                secs = travel_time % 60
                if mins > 60:
                    hours = mins // 60
                    mins = mins % 60
                    time_text = f"{hours}h{mins}m"
                elif mins > 0:
                    time_text = f"{mins}m{secs}s" if secs > 0 else f"{mins}m"
                else:
                    time_text = f"{secs}s"
                
                danger_text = "⚠️" * danger if danger > 0 else ""
                # Clear departure → destination format
                route_lines.append(f"{route_emoji} **{name} → {dest_emoji} {dest_name}** · {time_text} {danger_text}")
            
            embed.add_field(
                name="🗺️ Available Routes",
                value="\n".join(route_lines),
                inline=False
            )
        else:
            embed.add_field(
                name="🗺️ Available Routes",
                value="*No active routes from this location*",
                inline=False
            )
        
        # Status-aware usage instructions
        getting_started_text = "• Use `/here` for interactive options\n• Use `/travel routes` to see detailed travel info\n• Use `/shop list` and `/job list` to see what's available\n• Use `/status` to see information about your character."
        
        if location_status == "Loyal":
            getting_started_text += "\n• Access premium federal supplies and secure services"
        elif location_status == "Bandit":
            getting_started_text += "\n• Explore black market opportunities (discretion advised)"
        
        embed.add_field(
            name="🎮 Getting Started",
            value=getting_started_text,
            inline=False
        )
        
        # Status-aware channel info
        channel_info_text = "This channel was created automatically when someone arrived. It will be cleaned up if unused for extended periods."
        
        if location_status:
            if location_status == "Loyal":
                channel_info_text += " Federal monitoring protocols are in effect."
            elif location_status == "Bandit":
                channel_info_text += " Communications may be monitored by local authorities."
        
        embed.add_field(
            name="ℹ️ Channel Info",
            value=channel_info_text,
            inline=False
        )
        
        try:
            await channel.send(embed=embed)
        except Exception as e:
            print(f"❌ Failed to send welcome message to {channel.name}: {e}")

    async def send_location_arrival(self, channel: discord.TextChannel, user: discord.Member, location_id: int):
        """Send arrival announcement when a player enters a location"""
        
        # Get character name and reputation
        char_data = self.db.execute_query(
            "SELECT name FROM characters WHERE user_id = ?",
            (user.id,),
            fetch='one'
        )
        
        if not char_data:
            return
        
        char_name = char_data[0]
        
        # Get location name
        location_name = self.db.execute_query(
            "SELECT name FROM locations WHERE location_id = ?",
            (location_id,),
            fetch='one'
        )[0]
        
        # Get reputation and determine emoji
        reputation_emoji = await self._get_reputation_emoji(user.id, location_id)
        
        embed = discord.Embed(
            title="🚀 Arrival",
            description=f"{reputation_emoji}{char_name} has arrived at {location_name}",
            color=0x00ff00
        )
        
        try:
            await channel.send(embed=embed)
        except Exception as e:
            print(f"❌ Failed to send arrival message to {channel.name}: {e}")

    async def send_location_departure(self, channel: discord.TextChannel, user: discord.Member, location_id: int):
        """Send departure announcement when a player leaves a location"""
        
        # Check if other players are present (excluding the departing player)
        other_players = self.db.execute_query(
            "SELECT COUNT(*) FROM characters WHERE current_location = ? AND user_id != ? AND is_logged_in = 1",
            (location_id, user.id),
            fetch='one'
        )[0]
        
        # Skip departure message if no other players present
        if other_players == 0:
            return
        
        # Get character name
        char_data = self.db.execute_query(
            "SELECT name FROM characters WHERE user_id = ?",
            (user.id,),
            fetch='one'
        )
        
        if not char_data:
            return
        
        char_name = char_data[0]
        
        # Get location name
        location_name = self.db.execute_query(
            "SELECT name FROM locations WHERE location_id = ?",
            (location_id,),
            fetch='one'
        )[0]
        
        # Get reputation and determine emoji
        reputation_emoji = await self._get_reputation_emoji(user.id, location_id)
        
        embed = discord.Embed(
            title="Departure 🚀",
            description=f"{reputation_emoji}{char_name} has left {location_name}",
            color=0xff6600
        )
        
        try:
            await channel.send(embed=embed)
        except Exception as e:
            print(f"❌ Failed to send departure message to {channel.name}: {e}")

    async def _get_reputation_emoji(self, user_id: int, location_id: int) -> str:
        """Get reputation emoji for a user at a specific location"""
        
        # Check for active bounties first - this takes priority
        bounty_cog = self.bot.get_cog('BountyCog')
        if bounty_cog and bounty_cog.has_active_bounty(user_id):
            return "🎯 "  # Bounty target emoji
        
        # Get user's reputation at this location
        reputation_data = self.db.execute_query(
            "SELECT reputation FROM character_reputation WHERE user_id = ? AND location_id = ?",
            (user_id, location_id),
            fetch='one'
        )
        
        if not reputation_data:
            return ""  # No reputation = neutral, no emoji
        
        reputation_score = reputation_data[0]
        
        # Determine emoji based on reputation tier
        if reputation_score >= 80:
            return "⭐ "  # Heroic
        elif reputation_score >= 50:
            return "😇 "  # Good
        elif reputation_score <= -80:
            return "💀 "  # Evil
        elif reputation_score <= -50:
            return "😈 "  # Bad
        else:
            return ""  # Neutral, no emoji

    def _track_active_location_message(self, user_id: int, location_id: int, message_id: int):
        """Track an active location message for later cleanup"""
        if user_id not in self._active_location_messages:
            self._active_location_messages[user_id] = {}
        self._active_location_messages[user_id][location_id] = message_id

    async def _remove_active_location_message(self, user_id: int, location_id: int, channel: discord.TextChannel):
        """Remove tracked active location message"""
        if user_id in self._active_location_messages:
            if location_id in self._active_location_messages[user_id]:
                message_id = self._active_location_messages[user_id][location_id]
                try:
                    message = await channel.fetch_message(message_id)
                    await message.delete()
                except:
                    pass  # Message already deleted or not found
                
                # Remove from tracking
                del self._active_location_messages[user_id][location_id]
                if not self._active_location_messages[user_id]:
                    del self._active_location_messages[user_id]
    
    async def _update_channel_activity(self, location_id: int):
        """
        Update the last active time for a location channel
        """
        current_time = datetime.now()
        self.db.execute_query(
            "UPDATE locations SET channel_last_active = ? WHERE location_id = ?",
            (current_time, location_id)
        )
    
    async def give_user_location_access(self, user: discord.Member, location_id: int) -> bool:
        """Give a user access to a location's channel, creating it if necessary"""
        try:
            channel = await self.get_or_create_location_channel(user.guild, location_id, user)
            if not channel:
                print(f"❌ Could not create or find channel for location {location_id}")
                return False
            
            # Set permissions
            await channel.set_permissions(user, read_messages=True, send_messages=True)
            await self._update_channel_activity(location_id)
            
            # Send personalized location status to the user
            await self.send_location_arrival(channel, user, location_id)
            
            # Check if user has a transport job to this location
            transport_job = self.db.execute_query(
                '''SELECT j.job_id, j.title, j.reward_money 
                   FROM jobs j
                   WHERE j.taken_by = ? 
                   AND j.is_taken = 1 
                   AND j.destination_location_id = ?
                   AND j.job_status != 'completed' ''',
                (user.id, location_id),
                fetch='one'
            )
            
            if transport_job:
                job_id, job_title, reward = transport_job
                
                # Send transport job arrival notification
                embed = discord.Embed(
                    title="📦 Transport Job - Destination Reached!",
                    description=f"You've arrived at the destination for **{job_title}**",
                    color=0x00ff00
                )
                embed.add_field(
                    name="✅ Ready to Complete",
                    value=f"Use `/job complete` to unload cargo and receive your reward of **{reward:,} credits**",
                    inline=False
                )
                
                try:
                    # Try ephemeral first by creating a webhook-style message
                    await channel.send(
                        content=f"{user.mention}",
                        embed=embed,
                        delete_after=60  # Auto-delete after 1 minute
                    )
                except Exception as e:
                    print(f"Failed to send transport job notification: {e}")
            
            print(f"✅ Successfully gave {user.name} access to location {location_id}")
            return True
            
        except Exception as e:
            print(f"❌ Error giving {user.name} access to location {location_id}: {e}")
            return False
            
    async def remove_user_location_access(self, user: discord.Member, location_id: int) -> bool:
        """
        Remove a user's access to a location channel and clean up their messages
        """
        location_info = self.db.execute_query(
            "SELECT channel_id FROM locations WHERE location_id = ?",
            (location_id,),
            fetch='one'
        )
        
        if not location_info or not location_info[0]:
            return True  # No channel exists, so access is already "removed"
        
        channel = user.guild.get_channel(location_info[0])
        if not channel:
            return True  # Channel doesn't exist
        
        try:
            await self.send_location_departure(channel, user, location_id)
            # Remove their active location message first
            await self._remove_active_location_message(user.id, location_id, channel)
            
            # Remove channel permissions
            await channel.set_permissions(user, overwrite=None)
            
            print(f"🚪 Removed {user.name} access from location channel")
            return True
        except Exception as e:
            print(f"❌ Failed to remove {user.name} access from {channel.name}: {e}")
            return False
    
    async def _check_and_cleanup_empty_channels(self, guild: discord.Guild):
        """Background task to check and cleanup empty channels - IMPROVED with timeout handling"""
        if not self.auto_cleanup_enabled:
            return
            
        # More aggressive cleanup - only 1 minute instead of 2
        cutoff_time = datetime.now() - timedelta(minutes=2)  # Increased from 1 minute
        
        try:
            # Use read-only query with timeout
            empty_channels = self.db.execute_read_query(
                '''SELECT l.location_id, l.channel_id, l.name,
                          COUNT(CASE WHEN c.is_logged_in = 1 THEN c.user_id END) as logged_in_count
                   FROM locations l
                   LEFT JOIN characters c ON l.location_id = c.current_location
                   WHERE l.channel_id IS NOT NULL 
                   AND (l.channel_last_active IS NULL OR l.channel_last_active < ?)
                   GROUP BY l.location_id, l.channel_id, l.name
                   HAVING logged_in_count = 0
                   LIMIT 3''',  # Reduced from 5 to avoid conflicts
                (cutoff_time,),
                fetch='all'
            )
            
            # Also check for empty ship channels with read-only query
            empty_ship_channels = self.db.execute_read_query(
                '''SELECT s.ship_id, s.channel_id, s.name,
                          COUNT(CASE WHEN c.is_logged_in = 1 THEN c.user_id END) as logged_in_count
                   FROM ships s
                   LEFT JOIN characters c ON s.ship_id = c.current_ship_id
                   WHERE s.channel_id IS NOT NULL
                   GROUP BY s.ship_id, s.channel_id, s.name
                   HAVING logged_in_count = 0
                   LIMIT 2''',  # Reduced limit
                fetch='all'
            )
            
        except Exception as e:
            print(f"⚠️ Database timeout in cleanup query: {e}")
            return  # Skip cleanup if database is busy
        
        cleaned_count = 0
        
        # Clean up location channels
        for location_id, channel_id, location_name, logged_in_count in empty_channels:
            channel = guild.get_channel(channel_id)
            if channel:
                try:
                    # Additional check: make sure no one is traveling TO this location
                    travelers_coming = self.db.execute_read_query(
                        "SELECT COUNT(*) FROM travel_sessions WHERE destination_location = ? AND status = 'traveling'",
                        (location_id,),
                        fetch='one'
                    )[0]
                    
                    if travelers_coming == 0:
                        await channel.delete(reason="Automated cleanup - no logged-in players")
                        print(f"🧹 Auto-cleaned channel #{channel.name} for {location_name} (no logged-in players)")
                        cleaned_count += 1
                        
                        # Update database after successful deletion
                        self.db.execute_query(
                            "UPDATE locations SET channel_id = NULL, channel_last_active = NULL WHERE location_id = ?",
                            (location_id,)
                        )
                    else:
                        # Someone is traveling here, update activity to keep channel
                        await self._update_channel_activity(location_id)
                        continue
                            
                except Exception as e:
                    print(f"❌ Failed to delete channel for {location_name}: {e}")
            
            # Yield between deletions
            await asyncio.sleep(0.5)
        
        # Clean up ship channels
        for ship_id, channel_id, ship_name, logged_in_count in empty_ship_channels:
            channel = guild.get_channel(channel_id)
            if channel:
                try:
                    await channel.delete(reason="Automated cleanup - no players aboard ship")
                    print(f"🧹 Auto-cleaned ship channel #{channel.name} for {ship_name} (no players aboard)")
                    cleaned_count += 1
                    
                    # Update database after successful deletion
                    self.db.execute_query(
                        "UPDATE ships SET channel_id = NULL WHERE ship_id = ?",
                        (ship_id,)
                    )
                except Exception as e:
                    print(f"❌ Failed to delete ship channel for {ship_name}: {e}")
            
            # Yield between deletions
            await asyncio.sleep(0.5)
        
        if cleaned_count > 0:
            print(f"🧹 Background cleanup: removed {cleaned_count} channels with no logged-in players")
            
    async def immediate_ship_cleanup(self, guild: discord.Guild, ship_id: int):
        """Check if a ship should be cleaned up immediately when someone leaves"""
        # Wait just a moment for database to update
        await asyncio.sleep(1)
        
        # Check if ship has any LOGGED-IN players
        logged_in_players = self.db.execute_query(
            "SELECT COUNT(*) FROM characters WHERE current_ship_id = ? AND is_logged_in = 1",
            (ship_id,),
            fetch='one'
        )[0]
        
        if logged_in_players == 0:
            # Get ship channel info
            ship_info = self.db.execute_query(
                "SELECT channel_id, name FROM ships WHERE ship_id = ?",
                (ship_id,),
                fetch='one'
            )
            
            if ship_info and ship_info[0]:
                channel = guild.get_channel(ship_info[0])
                if channel:
                    try:
                        await channel.delete(reason="No logged-in players aboard ship")
                        print(f"🧹 Immediately cleaned up ship channel for: {ship_info[1]} (no logged-in players)")
                        
                        self.db.execute_query(
                            "UPDATE ships SET channel_id = NULL WHERE ship_id = ?",
                            (ship_id,)
                        )
                    except Exception as e:
                        print(f"❌ Failed to cleanup empty ship channel: {e}")
    async def _cleanup_old_channels_if_needed(self, guild: discord.Guild):
        """
        Clean up old unused channels if we're approaching the limit - IMPROVED to count only logged-in players
        """
        # Count current location channels that have logged-in players or recent activity
        current_channels = self.db.execute_query(
            '''SELECT COUNT(DISTINCT l.location_id)
               FROM locations l
               LEFT JOIN characters c ON l.location_id = c.current_location AND c.is_logged_in = 1
               WHERE l.channel_id IS NOT NULL 
               AND (c.user_id IS NOT NULL OR l.channel_last_active > datetime('now', '-1 hour'))''',
            fetch='one'
        )[0]
        
        if current_channels >= self.max_location_channels:
            await self._cleanup_old_channels(guild, force=True)
    
    async def _cleanup_old_channels(self, guild: discord.Guild, force: bool = False):
        """Clean up old unused location channels with better logic"""
        # More aggressive cleanup timing
        if force:
            cutoff_time = datetime.now() - timedelta(minutes=30)  # 30 minutes if forced
        else:
            cutoff_time = datetime.now() - timedelta(hours=2)     # 2 hours normal cleanup
        
        # Only clean up channels with no current players
        old_channels = self.db.execute_query(
            '''SELECT l.location_id, l.channel_id, l.name,
                      COUNT(c.user_id) as player_count,
                      l.channel_last_active
               FROM locations l
               LEFT JOIN characters c ON l.location_id = c.current_location
               WHERE l.channel_id IS NOT NULL 
               AND (l.channel_last_active IS NULL OR l.channel_last_active < ?)
               GROUP BY l.location_id, l.channel_id, l.name, l.channel_last_active
               HAVING player_count = 0
               ORDER BY l.channel_last_active ASC
               LIMIT ?''',
            (cutoff_time, self.cleanup_batch_size),
            fetch='all'
        )
        
        cleaned_count = 0
        for location_id, channel_id, location_name, player_count, last_active in old_channels:
            channel = guild.get_channel(channel_id)
            if channel:
                try:
                    # Check for very recent messages (last 10 minutes)
                    recent_cutoff = datetime.now() - timedelta(minutes=10)
                    recent_activity = False
                    async for message in channel.history(limit=3, after=recent_cutoff):
                        recent_activity = True
                        break
                    
                    if not recent_activity:
                        await channel.delete(reason="Automated cleanup - location empty and unused")
                        print(f"🧹 Cleaned up empty channel #{channel.name} for {location_name}")
                        cleaned_count += 1
                    else:
                        # Update activity time since we found recent messages
                        await self._update_channel_activity(location_id)
                        continue
                        
                except Exception as e:
                    print(f"❌ Failed to delete channel for {location_name}: {e}")
            
            # Clear channel reference from database
            self.db.execute_query(
                "UPDATE locations SET channel_id = NULL, channel_last_active = NULL WHERE location_id = ?",
                (location_id,)
            )
        
        if cleaned_count > 0:
            print(f"🧹 Cleaned up {cleaned_count} unused location channels")

    async def update_channel_on_player_movement(self, guild: discord.Guild, user_id: int, old_location_id: int = None, new_location_id: int = None):
        """Update channels when a player moves between locations - IMPROVED for immediate cleanup"""
        
        member = guild.get_member(user_id)
        if not member:
            return
        
        # Remove access from old location
        if old_location_id:
            success = await self.remove_user_location_access(member, old_location_id)
            if success:
                # Immediate cleanup check for the old location (no delay)
                asyncio.create_task(self._immediate_cleanup_check(guild, old_location_id))
        
        # Give access to new location
        if new_location_id:
            await self.give_user_location_access(member, new_location_id)

    async def _immediate_cleanup_check(self, guild: discord.Guild, location_id: int):
        """Check if a location should be cleaned up immediately - IMPROVED to check login status"""
        # Wait just a moment for database to update
        await asyncio.sleep(2)
        
        # IMPROVED: Check if location has any LOGGED-IN players
        logged_in_count = self.db.execute_query(
            "SELECT COUNT(*) FROM characters WHERE current_location = ? AND is_logged_in = 1",
            (location_id,),
            fetch='one'
        )[0]
        
        # Also check if anyone is traveling TO this location
        travelers_coming = self.db.execute_query(
            "SELECT COUNT(*) FROM travel_sessions WHERE destination_location = ? AND status = 'traveling'",
            (location_id,),
            fetch='one'
        )[0]
        
        if logged_in_count == 0 and travelers_coming == 0:
            # Get channel info
            location_info = self.db.execute_query(
                "SELECT channel_id, name FROM locations WHERE location_id = ?",
                (location_id,),
                fetch='one'
            )
            
            if location_info and location_info[0]:
                channel = guild.get_channel(location_info[0])
                if channel:
                    try:
                        await channel.delete(reason="No logged-in players at location")
                        print(f"🧹 Immediately cleaned up channel for location: {location_info[1]} (no logged-in players)")
                        
                        self.db.execute_query(
                            "UPDATE locations SET channel_id = NULL, channel_last_active = NULL WHERE location_id = ?",
                            (location_id,)
                        )
                    except Exception as e:
                        print(f"❌ Failed to cleanup empty location channel: {e}")

    async def create_transit_channel(self, guild: discord.Guild, user_or_group, corridor_name: str, destination: str) -> Optional[discord.TextChannel]:
        """
        Create a temporary channel for corridor transit - IMPROVED with travel type detection
        """
        try:
            # Get transit category from config
            transit_category_id = self.db.execute_query(
                "SELECT transit_category_id FROM server_config WHERE guild_id = ?",
                (guild.id,),
                fetch='one'
            )
            
            category = None
            if transit_category_id and transit_category_id[0]:
                category = guild.get_channel(transit_category_id[0])
            
            # Fallback category creation
            if not category:
                for cat in guild.categories:
                    if cat.name == '🚀 IN TRANSIT':
                        category = cat
                        break
                
                if not category:
                    try:
                        category = await guild.create_category(
                            '🚀 IN TRANSIT',
                            reason="Transit category for corridor travel"
                        )
                    except Exception:
                        pass  # Continue without category
            
            # Set up permissions
            overwrites = {
                guild.default_role: discord.PermissionOverwrite(read_messages=False, send_messages=False)
            }
            
            # Add permissions for travelers
            if isinstance(user_or_group, list):
                # Group travel
                for member in user_or_group:
                    if isinstance(member, discord.Member):
                        overwrites[member] = discord.PermissionOverwrite(read_messages=True, send_messages=True)
                
                # Use leader's ID for channel name to be consistent
                channel_name = f"transit-group-{user_or_group[0].id}"
            else:
                # Solo travel
                overwrites[user_or_group] = discord.PermissionOverwrite(read_messages=True, send_messages=True)
                channel_name = f"transit-{user_or_group.id}"
            
            # Determine travel type based on corridor name for better topic
            if "Approach" in corridor_name:
                travel_type = "local space"
                topic = f"In local space traveling to {destination}"
            elif "Ungated" in corridor_name:
                travel_type = "dangerous ungated corridor"
                topic = f"In dangerous ungated corridor {corridor_name} to {destination}"
            else:
                travel_type = "gated corridor"
                topic = f"In gated corridor {corridor_name} to {destination}"
            
            # Create the transit channel
            channel = await guild.create_text_channel(
                channel_name,
                category=category,
                topic=topic,
                overwrites=overwrites,
                reason=f"Temporary transit channel through {corridor_name}"
            )
            
            # Send initial transit message with proper travel type
            await self._send_transit_welcome(channel, corridor_name, destination, travel_type)
            
            print(f"🚀 Created transit channel #{channel_name} for {corridor_name}")
            return channel
            
        except Exception as e:
            print(f"❌ Failed to create transit channel: {e}")
            return None
    
    async def _send_transit_welcome(self, channel: discord.TextChannel, corridor_name: str, destination: str, travel_type: str):
        """Send welcome message to transit channel - IMPROVED with travel type and ship info"""
        # Get travelers in this channel
        travelers = []
        member_ships = {}
        
        # Extract user IDs from channel permissions
        for target, overwrite in channel.overwrites.items():
            if isinstance(target, discord.Member) and overwrite.read_messages:
                travelers.append(target)
                
                # Get their ship info
                ship_info = self.db.execute_query(
                    '''SELECT s.ship_id, s.name, s.ship_type, s.interior_description
                       FROM characters c
                       JOIN ships s ON c.active_ship_id = s.ship_id
                       WHERE c.user_id = ?''',
                    (target.id,),
                    fetch='one'
                )
                
                if ship_info:
                    member_ships[target.id] = ship_info
        
        # Determine title and description based on travel type
        if travel_type == "local space":
            title = f"🌌 Local Space Transit to {destination}"
            description = f"Your ship is traveling through local space to **{destination}**"
            hazard_text = "• Monitor for local traffic\n• Watch for debris fields\n• Maintain safe distance from other vessels\n• Check navigation systems regularly"
        elif travel_type == "dangerous ungated corridor":
            title = f"⚠️ Ungated Corridor Transit - {corridor_name}"
            description = f"Your ship is traveling through the dangerous ungated corridor **{corridor_name}** to **{destination}**"
            hazard_text = "• **HIGH RADIATION EXPOSURE RISK**\n• Watch for corridor instability\n• Monitor structural integrity\n• Be prepared for emergency exits\n• **EXTREME DANGER - STAY ALERT**"
        else:
            title = f"🔒 Gated Corridor Transit - {corridor_name}"
            description = f"Your ship is traveling through the gated corridor **{corridor_name}** to **{destination}**"
            hazard_text = "• Monitor for standard corridor hazards\n• Watch for static fog alerts\n• Check gate synchronization\n• Maintain course through gate network"
        
        embed = discord.Embed(
            title=title,
            description=description,
            color=0x800080 if travel_type == "gated corridor" else 0xff6600 if travel_type == "local space" else 0xff0000
        )
        
        # If single traveler, show their ship info
        if len(travelers) == 1 and travelers[0].id in member_ships:
            ship_id, ship_name, ship_type, interior_desc = member_ships[travelers[0].id]
            
            embed.add_field(
                name="🚀 Your Ship",
                value=f"**{ship_name}** ({ship_type})",
                inline=False
            )
            
            if interior_desc:
                embed.add_field(
                    name="📐 Ship Interior",
                    value=interior_desc[:300] + "..." if len(interior_desc) > 300 else interior_desc,
                    inline=False
                )
        elif len(travelers) > 1:
            # Show all ships in group travel
            ship_list = []
            for traveler in travelers[:5]:  # Limit display
                if traveler.id in member_ships:
                    _, ship_name, ship_type, _ = member_ships[traveler.id]
                    char_name = self.db.execute_query(
                        "SELECT name FROM characters WHERE user_id = ?",
                        (traveler.id,),
                        fetch='one'
                    )[0]
                    ship_list.append(f"• **{char_name}** - {ship_name} ({ship_type})")
            
            if ship_list:
                embed.add_field(
                    name="🚀 Group Fleet",
                    value="\n".join(ship_list),
                    inline=False
                )
        
        embed.add_field(
            name="⚠️ Transit Hazards",
            value=hazard_text,
            inline=False
        )
        
        embed.add_field(
            name="🛠️ Available Actions",
            value="• Use ship activities below to pass the time\n• `/character ship` - Check ship status\n• `/character inventory` - Use items\n• `/travel status` - Check progress\n• `/travel emergency_exit` - Emergency exit (dangerous!)",
            inline=False
        )
        
        if travel_type != "local space":
            embed.add_field(
                name="👥 Group Travel",
                value="Group members can coordinate actions and share resources during transit.",
                inline=False
            )
        
        embed.add_field(
            name="ℹ️ Transit Info",
            value="This channel will be automatically deleted when your journey completes.",
            inline=False
        )
        
        try:
            await channel.send(embed=embed)
            
            # Send ship activity buttons for single traveler
            if len(travelers) == 1 and travelers[0].id in member_ships:
                ship_id, ship_name, _, _ = member_ships[travelers[0].id]
                char_name = self.db.execute_query(
                    "SELECT name FROM characters WHERE user_id = ?",
                    (travelers[0].id,),
                    fetch='one'
                )[0]
                
                activity_manager = ShipActivityManager(self.bot)
                activities = activity_manager.get_ship_activities(ship_id)
                
                if activities:
                    activity_view = ShipActivityView(self.bot, ship_id, ship_name, char_name, destination)
                    activity_embed = discord.Embed(
                        title="🎯 Ship Activities",
                        description="Pass the time during transit with your ship's facilities:",
                        color=0x00ff88
                    )
                    await channel.send(embed=activity_embed, view=activity_view)
                    
        except Exception as e:
            print(f"❌ Failed to send transit welcome: {e}")
    async def immediate_logout_cleanup(self, guild: discord.Guild, location_id: int, ship_id: int = None):
        """Immediately check and cleanup a location when someone logs out"""
        # Wait just a moment for database to update
        await asyncio.sleep(1)
        
        # Handle location cleanup if provided
        if location_id:
            # Check if location has any LOGGED-IN players
            logged_in_players = self.db.execute_query(
                "SELECT COUNT(*) FROM characters WHERE current_location = ? AND is_logged_in = 1",
                (location_id,),
                fetch='one'
            )[0]
            
            # Also check if anyone is traveling TO this location
            travelers_coming = self.db.execute_query(
                "SELECT COUNT(*) FROM travel_sessions WHERE destination_location = ? AND status = 'traveling'",
                (location_id,),
                fetch='one'
            )[0]
            
            if logged_in_players == 0 and travelers_coming == 0:
                # Get channel info
                location_info = self.db.execute_query(
                    "SELECT channel_id, name FROM locations WHERE location_id = ?",
                    (location_id,),
                    fetch='one'
                )
                
                if location_info and location_info[0]:
                    channel = guild.get_channel(location_info[0])
                    if channel:
                        try:
                            await channel.delete(reason="Last logged-in player left location")
                            print(f"🧹 Logout cleanup: removed channel for {location_info[1]} (no logged-in players)")
                            
                            self.db.execute_query(
                                "UPDATE locations SET channel_id = NULL, channel_last_active = NULL WHERE location_id = ?",
                                (location_id,)
                            )
                        except Exception as e:
                            print(f"❌ Failed to cleanup location channel during logout: {e}")
        
        # NEW: Handle ship cleanup if provided
        if ship_id:
            await self.immediate_ship_cleanup(guild, ship_id)

    async def restore_user_location_on_login(self, user: discord.Member, location_id: int) -> bool:
        """Restore or create location access when a user logs in"""
        # First, ensure the channel exists and user has access
        channel = await self.get_or_create_location_channel(user.guild, location_id, user)
        if not channel:
            print(f"❌ Failed to create/access channel for location {location_id}")
            return False
        
        try:
            # Ensure user has permissions
            await channel.set_permissions(user, read_messages=True, send_messages=True)
            await self._update_channel_activity(location_id)
            
            # Send personalized location status
            await self.send_location_arrival(channel, user, location_id)
            
            print(f"✅ Login restoration: gave {user.name} access to location {location_id}")
            return True
        except Exception as e:
            print(f"❌ Failed to restore {user.name} access during login: {e}")
            return False
    async def cleanup_transit_channel(self, channel_id: int, delay_seconds: int = 30):
        """
        Clean up a transit channel after a delay
        """
        await asyncio.sleep(delay_seconds)
        
        channel = self.bot.get_channel(channel_id)
        if channel:
            try:
                await channel.delete(reason="Transit completed")
                print(f"🗑️ Cleaned up transit channel #{channel.name}")
            except Exception as e:
                print(f"❌ Failed to delete transit channel: {e}")
    
    async def get_server_config(self, guild: discord.Guild) -> dict:
        """
        Get server configuration for this guild
        """
        config = self.db.execute_query(
            '''SELECT colony_category_id, station_category_id, outpost_category_id,
                      gate_category_id, transit_category_id, max_location_channels,
                      channel_timeout_hours, auto_cleanup_enabled, setup_completed
               FROM server_config WHERE guild_id = ?''',
            (guild.id,),
            fetch='one'
        )
        
        if not config:
            return {
                'setup_completed': False,
                'max_location_channels': 50,
                'channel_timeout_hours': 48,
                'auto_cleanup_enabled': True
            }
        
        return {
            'colony_category_id': config[0],
            'station_category_id': config[1],
            'outpost_category_id': config[2], 
            'gate_category_id': config[3],
            'transit_category_id': config[4],
            'max_location_channels': config[5] or 50,
            'channel_timeout_hours': config[6] or 48,
            'auto_cleanup_enabled': config[7] if config[7] is not None else True,
            'setup_completed': config[8] or False
        }
    async def get_or_create_ship_channel(self, guild: discord.Guild, ship_info: tuple, user: discord.Member = None) -> Optional[discord.TextChannel]:
        """
        Get existing channel for ship or create one if needed
        """
        ship_id, ship_name, ship_type, interior_desc, channel_id = ship_info
        
        # Check if channel already exists
        if channel_id:
            channel = guild.get_channel(channel_id)
            if channel:
                return channel
            else:
                # Channel was deleted, clear the reference
                self.db.execute_query(
                    "UPDATE ships SET channel_id = NULL WHERE ship_id = ?",
                    (ship_id,)
                )
        
        # Create new ship channel
        channel = await self._create_ship_channel(guild, ship_info, user)
        return channel

    async def _create_ship_channel(self, guild: discord.Guild, ship_info: tuple, requesting_user: discord.Member = None) -> Optional[discord.TextChannel]:
        """
        Create a new Discord channel for a ship interior
        """
        ship_id, ship_name, ship_type, interior_desc, channel_id = ship_info
        
        try:
            # Generate safe channel name
            channel_name = self._generate_ship_channel_name(ship_name, ship_type)
            
            # Create channel topic
            topic = f"Ship Interior: {ship_name} ({ship_type})"
            if interior_desc:
                topic += f" | {interior_desc[:100]}"
            
            # Set up permissions - start with no access for @everyone
            overwrites = {
                guild.default_role: discord.PermissionOverwrite(read_messages=False, send_messages=False)
            }
            
            # Give access to requesting user if provided
            if requesting_user:
                overwrites[requesting_user] = discord.PermissionOverwrite(read_messages=True, send_messages=True)
            
            # Find or create category for ship channels
            category = await self._get_or_create_ship_category(guild)
            
            # Create the channel
            channel = await guild.create_text_channel(
                channel_name,
                category=category,
                topic=topic,
                overwrites=overwrites,
                reason=f"Ship interior channel for: {ship_name}"
            )
            
            # Update database with channel info
            self.db.execute_query(
                "UPDATE ships SET channel_id = ? WHERE ship_id = ?",
                (channel.id, ship_id)
            )
            
            # Send welcome message to channel
            await self._send_ship_welcome(channel, ship_info)
            
            print(f"🚀 Created ship channel #{channel_name} for {ship_name}")
            return channel
            
        except Exception as e:
            print(f"❌ Failed to create ship channel for {ship_name}: {e}")
            return None

    def _generate_ship_channel_name(self, ship_name: str, ship_type: str) -> str:
        """Generate a Discord-safe channel name for ships"""
        # Remove special characters and convert to lowercase
        import re
        safe_name = re.sub(r'[^\w\s-]', '', ship_name.lower())
        safe_name = re.sub(r'\s+', '-', safe_name)
        safe_name = safe_name.strip('-')
        
        # Add ship prefix
        ship_prefix = "ship"
        
        # Ensure name isn't too long
        max_name_length = 85 - len(ship_prefix)
        if len(safe_name) > max_name_length:
            safe_name = safe_name[:max_name_length].rstrip('-')
        
        return f"{ship_prefix}-{safe_name}"

    async def _get_or_create_ship_category(self, guild: discord.Guild) -> Optional[discord.CategoryChannel]:
        """
        Get the ship interiors category from the server config.
        """
        category_id = self.db.execute_query(
            "SELECT ship_interiors_category_id FROM server_config WHERE guild_id = ?",
            (guild.id,),
            fetch='one'
        )
        
        if category_id and category_id[0]:
            category = guild.get_channel(category_id[0])
            if isinstance(category, discord.CategoryChannel):
                return category
        
        # Fallback for safety, though it shouldn't be needed after setup
        for cat in guild.categories:
            if cat.name == '🚀 SHIP INTERIORS':
                return cat
        
        return None

    async def _send_ship_welcome(self, channel: discord.TextChannel, ship_info: tuple):
        """Send a welcome message to a newly created ship channel"""
        ship_id, ship_name, ship_type, interior_desc, channel_id = ship_info
        
        # Get owner info
        owner_id = self.db.execute_query(
            "SELECT owner_id FROM ships WHERE ship_id = ?",
            (ship_id,),
            fetch='one'
        )[0]
        
        owner_name = self.db.execute_query(
            "SELECT name FROM characters WHERE user_id = ?",
            (owner_id,),
            fetch='one'
        )[0]
        
        embed = discord.Embed(
            title=f"🚀 Welcome Aboard {ship_name}",
            description=interior_desc or "You are now inside your ship.",
            color=0x2F4F4F
        )
        
        embed.add_field(
            name="Ship Class",
            value=ship_type,
            inline=True
        )
        
        # Get ship activities
        activity_manager = ShipActivityManager(self.bot)
        activities = activity_manager.get_ship_activities(ship_id)
        
        if activities:
            activity_list = []
            for activity in activities[:8]:  # Limit display
                activity_list.append(f"{activity['icon']} {activity['name']}")
            
            embed.add_field(
                name="🎮 Ship Facilities",
                value="\n".join(activity_list),
                inline=False
            )
        
        embed.add_field(
            name="🎮 Available Actions",
            value="• Use the activity buttons below to interact with your ship\n• `/ship interior leave` - Exit the ship\n• `/character inventory` - Check your items\n• `/character ship` - Check ship status",
            inline=False
        )
        
        embed.add_field(
            name="ℹ️ Ship Interior",
            value="This is your private ship space. Other players can only enter if you grant them access.",
            inline=False
        )
        
        try:
            await channel.send(embed=embed)
            
            # Send activity buttons
            if activities:
                activity_view = ShipActivityView(self.bot, ship_id, ship_name, owner_name)
                activity_embed = discord.Embed(
                    title="🎯 Ship Activities",
                    description="Choose an activity to interact with your ship:",
                    color=0x00ff88
                )
                await channel.send(embed=activity_embed, view=activity_view)
                
        except Exception as e:
            print(f"❌ Failed to send ship welcome message: {e}")

    async def give_user_ship_access(self, user: discord.Member, ship_id: int) -> bool:
        """Give a user access to a ship's channel"""
        ship_info = self.db.execute_query(
            "SELECT channel_id FROM ships WHERE ship_id = ?",
            (ship_id,),
            fetch='one'
        )
        
        if not ship_info or not ship_info[0]:
            return False
        
        channel = user.guild.get_channel(ship_info[0])
        if not channel:
            return False
        
        try:
            await channel.set_permissions(user, read_messages=True, send_messages=True)
            return True
        except Exception as e:
            print(f"❌ Failed to give {user.name} ship access: {e}")
            return False

    async def remove_user_ship_access(self, user: discord.Member, ship_id: int) -> bool:
        """Remove a user's access to a ship channel"""
        ship_info = self.db.execute_query(
            "SELECT channel_id FROM ships WHERE ship_id = ?",
            (ship_id,),
            fetch='one'
        )
        
        if not ship_info or not ship_info[0]:
            return True
        
        channel = user.guild.get_channel(ship_info[0])
        if not channel:
            return True
        
        try:
            await channel.set_permissions(user, overwrite=None)
            return True
        except Exception as e:
            print(f"❌ Failed to remove {user.name} ship access: {e}")
            return False
class CharacterDeleteConfirmView(discord.ui.View):
    def __init__(self, bot, user_id: int, char_name: str):
        super().__init__(timeout=60)
        self.bot = bot
        self.user_id = user_id
        self.char_name = char_name
    
    @discord.ui.button(label="PERMANENTLY DELETE CHARACTER", style=discord.ButtonStyle.danger, emoji="💀")
    async def confirm_delete(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This is not your deletion panel!", ephemeral=True)
            return
        
        # Get current location for channel cleanup
        char_data = self.bot.db.execute_query(
            "SELECT current_location, ship_id FROM characters WHERE user_id = ?",
            (self.user_id,),
            fetch='one'
        )
        
        if not char_data:
            await interaction.response.send_message("Character not found!", ephemeral=True)
            return
        
        current_location, ship_id = char_data
        
        # Delete character and associated data
        self.bot.db.execute_query("DELETE FROM characters WHERE user_id = ?", (self.user_id,))

        # Delete character identity (add this line)
        self.bot.db.execute_query("DELETE FROM character_identity WHERE user_id = ?", (self.user_id,))

        if ship_id:
            self.bot.db.execute_query("DELETE FROM ships WHERE ship_id = ?", (ship_id,))
        
        # Cancel any active travel
        self.bot.db.execute_query(
            "UPDATE travel_sessions SET status = 'manual_deletion' WHERE user_id = ? AND status = 'traveling'",
            (self.user_id,)
        )
        
        # Remove from any group
        self.bot.db.execute_query("UPDATE characters SET group_id = NULL WHERE user_id = ?", (self.user_id,))
        
        # Cancel any jobs
        self.bot.db.execute_query(
            "UPDATE jobs SET is_taken = 0, taken_by = NULL, taken_at = NULL WHERE taken_by = ?",
            (self.user_id,)
        )
        
        # Remove access from location channels using channel manager
        if current_location:
            channel_manager = ChannelManager(self.bot)
            await channel_manager.remove_user_location_access(interaction.user, current_location)
        
        embed = discord.Embed(
            title="💀 Character Deleted",
            description=f"**{self.char_name}** has been permanently deleted.",
            color=0x000000
        )
        
        embed.add_field(
            name="⚰️ Deletion Complete",
            value="All character data, inventory, and progress has been erased.",
            inline=False
        )
        
        embed.add_field(
            name="🔄 Starting Over",
            value="You can create a new character with `/character create` to begin a new journey.",
            inline=False
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
        await self.cleanup_character_homes(user_id)
        print(f"💀 Character deletion (manual): {self.char_name} (ID: {self.user_id})")
    
    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary, emoji="❌")
    async def cancel_delete(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This is not your deletion panel!", ephemeral=True)
            return
        
        await interaction.response.send_message("Character deletion cancelled. Your character is safe!", ephemeral=True)