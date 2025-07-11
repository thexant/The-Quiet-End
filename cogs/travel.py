# cogs/travel.py - IMPROVED VERSION
import discord
from discord.ext import commands
from discord import app_commands, ui
import asyncio
from datetime import datetime, timedelta, timezone
import random
from utils.channel_manager import ChannelManager
from cogs.corridor_events import CorridorEventsCog

class DockingFeeView(discord.ui.View):
    def __init__(self, bot, user_id, location_id, fee, origin_location_id):
        super().__init__(timeout=300) # 5 minute timeout
        self.bot = bot
        self.user_id = user_id
        self.location_id = location_id
        self.fee = fee
        self.origin_location_id = origin_location_id
        self.decision = asyncio.Future()

    @discord.ui.button(label="Pay Fee", style=discord.ButtonStyle.success)
    async def pay_fee(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This is not your docking decision.", ephemeral=True)
            return

        # Check if user can afford it
        money = self.bot.db.execute_query(
            "SELECT money FROM characters WHERE user_id = ?", (self.user_id,), fetch='one'
        )[0]

        if money < self.fee:
            await interaction.response.send_message(f"You cannot afford the {self.fee:,} credit docking fee.", ephemeral=True)
            self.decision.set_result('leave')
            self.stop()
            return

        # Deduct fee
        self.bot.db.execute_query(
            "UPDATE characters SET money = money - ? WHERE user_id = ?", (self.fee, self.user_id)
        )
        await interaction.response.send_message(f"You paid the {self.fee:,} credit docking fee.", ephemeral=True)
        self.decision.set_result('pay')
        self.stop()

    @discord.ui.button(label="Leave", style=discord.ButtonStyle.danger)
    async def leave(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This is not your docking decision.", ephemeral=True)
            return
        
        await interaction.response.send_message("You decide to leave the area.", ephemeral=True)
        self.decision.set_result('leave')
        self.stop()

    async def wait_for_decision(self):
        return await self.decision
class TravelCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = bot.db
        self.channel_mgr = ChannelManager(bot) 
        self.active_status_messages = {}  # Track active status messages for auto-refresh
        
    travel_group = app_commands.Group(name="travel", description="Travel and corridor navigation")
    
    async def _trigger_corridor_events(self, transit_channel, user_id, corridor_id, travel_time):
        """Trigger corridor events during travel based on danger level"""
        if not transit_channel:
            return
        
        # Get corridor danger level first
        danger_info = self.db.execute_query(
            "SELECT danger_level, name, is_active FROM corridors WHERE corridor_id = ?",
            (corridor_id,),
            fetch='one'
        )
        
        if not danger_info:
            return
        
        danger_level, corridor_name, is_active = danger_info
        
        # Check if corridor is still active
        if not is_active:
            # Corridor has collapsed during travel - this is handled by the travel completion logic
            return
        
        # Calculate number of potential events based on travel time and danger
        base_events = max(1, travel_time // 300)  # One potential event per 5 minutes
        max_events = min(3, base_events)  # Cap at 3 events max
        
        # Schedule events at random intervals
        for i in range(max_events):
            # Random chance based on danger level
            event_chance = danger_level * 0.15  # 15% per danger level
            
            if random.random() < event_chance:
                # Random time during travel (but not too early or late)
                min_delay = max(30, travel_time * 0.1)  # At least 30 seconds, or 10% of travel time
                max_delay = min(travel_time - 60, travel_time * 0.9)  # At most 90% of travel time
                
                if max_delay > min_delay:
                    event_delay = random.uniform(min_delay, max_delay)
                    
                    # Schedule the event
                    asyncio.create_task(self._delayed_corridor_event(
                        transit_channel, [user_id], danger_level, event_delay
                    ))
    async def _delayed_corridor_event(self, transit_channel, travelers, danger_level, delay):
        """Trigger a corridor event after a delay"""
        await asyncio.sleep(delay)
        
        # Check if the channel still exists and travel is still active
        try:
            # Verify the channel exists
            await transit_channel.fetch_message(transit_channel.last_message_id or 1)
        except:
            return  # Channel gone or travel completed
        
        # Trigger the event
        events_cog = self.bot.get_cog('CorridorEventsCog')
        if events_cog:
            await events_cog.trigger_corridor_event(transit_channel, travelers, danger_level)

    @travel_group.command(
        name="go",
        description="Depart along a chosen corridor"
    )
    async def travel_go(self, interaction: discord.Interaction):
        # fetch both current location and docking status
        row = self.db.execute_query(
            "SELECT current_location, location_status FROM characters WHERE user_id = ?",
            (interaction.user.id,),
            fetch='one'
        )
        if not row:
            return await interaction.response.send_message("🚫 Character not found.", ephemeral=True)
        
        origin_id, status = row
        # block if docked
        if status == "docked":
            return await interaction.response.send_message(
                "❌ You must undock before travelling! Use `/character undock`.",
                ephemeral=True
            )
        # NEW: Check for active jobs before allowing travel
        proceed = await self._check_active_jobs(interaction.user.id, interaction)
        if not proceed:
            return  # User needs to confirm job cancellation first    
        # Check if user is in a group
        group_check = self.db.execute_query(
            "SELECT group_id FROM characters WHERE user_id = ? AND group_id IS NOT NULL",
            (interaction.user.id,),
            fetch='one'
        )
        if group_check:
            await interaction.response.send_message(
                "❌ You're in a group! Group travel must be initiated by the leader using `/group travel_vote`.",
                ephemeral=True
            )
            return
        # Check if user is logged in
        login_status = self.db.execute_query(
            "SELECT is_logged_in FROM characters WHERE user_id = ?",
            (interaction.user.id,),
            fetch='one'
        )

        if not login_status or not login_status[0]:
            return await interaction.response.send_message(
                "❌ You must be logged in to travel! Use `/character login` first.",
                ephemeral=True
            )
        # Check if character has an active ship    
        active_ship = self.db.execute_query(
            "SELECT active_ship_id FROM characters WHERE user_id = ?",
            (interaction.user.id,),
            fetch='one'
        )

        if not active_ship or not active_ship[0]:
            await interaction.response.send_message(
                "❌ You need an active ship to travel! Visit a shipyard to purchase or activate a ship.",
                ephemeral=True
            )
            return    
        # 🔥 FIXED: use origin_location, join on locations, and fetch='all'
        corridors = self.db.execute_query(
            '''
            SELECT c.corridor_id,
                   c.name,
                   l.name AS dest_name,
                   c.travel_time,
                   c.fuel_cost,
                   l.location_type
              FROM corridors c
              JOIN locations l ON c.destination_location = l.location_id
             WHERE c.origin_location = ? AND c.is_active = 1
            ''',
            (origin_id,),
            fetch='all'
        )
        if not corridors:
            return await interaction.response.send_message("No corridors depart from here.", ephemeral=True)

        # Get current location name for clearer route display
        current_location_name = self.db.execute_query(
            "SELECT name FROM locations WHERE location_id = ?",
            (origin_id,),
            fetch='one'
        )[0]

        # Build the dropdown
        options = []
        for cid, cname, dest_name, ttime, cost, dest_type in corridors:
            label = f"{current_location_name} → {dest_name}"
            hours   = ttime // 3600
            minutes = (ttime % 3600) // 60
            if hours:
                time_text = f"{hours}h {minutes}m"
            else:
                time_text = f"{minutes}m"

            # Determine travel type
            if "Approach" in cname:
                travel_type = "🌌 LOCAL"
            elif dest_type == "gate":
                travel_type = "🔵 GATED"
            elif "Ungated" in cname:
                travel_type = "⭕ UNGATED"
            else:
                travel_type = "🔵 GATED"

            desc = f"via {cname} · {time_text} · {cost}⚡ fuel · {travel_type}"
            options.append(discord.SelectOption(
                label=label,
                description=desc[:100],
                value=str(cid)
            ))

        select = ui.Select(placeholder="Choose your corridor", options=options, min_values=1, max_values=1)
        
        async def on_select(inter: discord.Interaction):
            if inter.user.id != interaction.user.id:
                return await inter.response.send_message("This isn't your travel menu!", ephemeral=True)

            # grab the choice they just made
            choice = int(select.values[0])
            cid, cname, dest_name, travel_time, cost, _ = next(
                c for c in corridors if c[0] == choice
            )
            # Get ship efficiency and modify travel time
            ship_efficiency = self.db.execute_query(
                "SELECT fuel_efficiency FROM ships WHERE owner_id = ?",
                (inter.user.id,), fetch='one'
            )[0]

            # Apply ship efficiency to travel time
            # fuel_efficiency ranges 3-10, where 10 = fastest
            # Create multiplier: efficiency 3 = 1.4x time, efficiency 10 = 0.8x time
            efficiency_modifier = 1.6 - (ship_efficiency * 0.08)  # 1.36 to 0.8 range
            actual_travel_time = max(int(travel_time * efficiency_modifier), 60)  # Minimum 1 minute

            # Update the variables for the rest of the function
            travel_time = actual_travel_time
            # Check fuel
            char_fuel = self.db.execute_query(
                "SELECT s.current_fuel FROM characters c JOIN ships s ON c.ship_id = s.ship_id WHERE c.user_id = ?",
                (inter.user.id,), fetch='one'
            )
            
            if not char_fuel or char_fuel[0] < cost:
                await inter.response.send_message(
                    f"Insufficient fuel! Need {cost}, have {char_fuel[0] if char_fuel else 0}.", 
                    ephemeral=True
                )
                return

            # Deduct fuel
            self.db.execute_query(
                "UPDATE ships SET current_fuel = current_fuel - ? WHERE owner_id = ?",
                (cost, inter.user.id)
            )

            # Create transit channel
            transit_chan = await self.channel_mgr.create_transit_channel(
                inter.guild,
                inter.user,
                cname,
                dest_name
            )

            # Record the session (storing transit_chan.id safely)
            start = datetime.utcnow()
            end = start + timedelta(seconds=travel_time)  # travel_time is already in seconds from DB
            self.db.execute_query(
                """
                INSERT INTO travel_sessions
                  (user_id, corridor_id, origin_location, destination_location,
                   start_time, end_time, temp_channel_id, status)
                VALUES (?, ?, ?, 
                        (SELECT destination_location FROM corridors WHERE corridor_id = ?),
                        ?, ?, ?, 'traveling')
                """,
                (
                    inter.user.id,
                    cid,
                    origin_id,
                    cid,
                    start.isoformat(),
                    end.isoformat(),
                    transit_chan.id if transit_chan else None
                )
            )

            # Confirm departure back to the user
            mins, secs = divmod(travel_time, 60)  # Use travel_time variable
            hours = mins // 60
            mins = mins % 60
            
            if hours > 0:
                time_display = f"{hours}h {mins}m {secs}s"
            else:
                time_display = f"{mins}m {secs}s"
            
            await inter.response.edit_message(
                content=f"🚀 Departure confirmed. ETA: {time_display}",
                view=None
            )

            # Remove user from origin location immediately
            old_location = self.db.execute_query(
                "SELECT current_location FROM characters WHERE user_id = ?",
                (inter.user.id,), fetch='one'
            )
            old_location_id = old_location[0] if old_location else None
            
            # Set character location to None (in transit)
            self.db.execute_query(
                "UPDATE characters SET current_location = NULL WHERE user_id = ?",
                (inter.user.id,)
            )
            
            # Remove access from old location
            if old_location_id:
                await self.channel_mgr.update_channel_on_player_movement(
                    inter.guild, inter.user.id, old_location_id, None
                )

            # Start auto-refreshing progress tracking if transit channel exists
            if transit_chan:
                asyncio.create_task(self._start_travel_progress_tracking(
                    transit_chan, inter.user.id, cid, travel_time, start, end, dest_name  # Pass 'end' not 'end_time'
                ))

            # Start corridor events system
            if transit_chan:
                asyncio.create_task(self._trigger_corridor_events(
                    transit_chan, inter.user.id, cid, travel_time
                ))

            # Schedule the actual travel completion
            asyncio.create_task(self._complete_travel_after_delay(
                inter.user.id, cid, travel_time, dest_name, transit_chan, inter.guild
            ))

        select.callback = on_select
        view = ui.View(timeout=60)
        view.add_item(select)
        await interaction.response.send_message("Select your route to depart:", view=view, ephemeral=True)
    async def _check_active_jobs(self, user_id: int, interaction: discord.Interaction) -> bool:
        """Check if user has active stationary jobs and warn them. Returns True if should proceed."""
        active_jobs = self.db.execute_query(
            '''SELECT j.job_id, j.title, j.reward_money 
               FROM jobs j 
               JOIN job_tracking jt ON j.job_id = jt.job_id
               WHERE j.taken_by = ? AND j.job_status = 'active' AND jt.start_location = (
                   SELECT current_location FROM characters WHERE user_id = ?
               )''',
            (user_id, user_id),
            fetch='all'
        )
        
        if not active_jobs:
            return True  # No active jobs, proceed
        
        # Create warning embed
        embed = discord.Embed(
            title="⚠️ Active Job Warning",
            description=f"You have {len(active_jobs)} active job(s) at this location.",
            color=0xff9900
        )
        
        job_list = []
        total_reward = 0
        for job_id, title, reward in active_jobs:
            job_list.append(f"• **{title}** - {reward:,} credits")
            total_reward += reward
        
        embed.add_field(
            name="Active Jobs",
            value="\n".join(job_list),
            inline=False
        )
        
        embed.add_field(
            name="⚠️ WARNING",
            value=f"Leaving this location will **cancel all active jobs** and you will **lose {total_reward:,} credits** in potential rewards!",
            inline=False
        )
        
        embed.add_field(
            name="Options",
            value="• Click **Cancel** to stay and complete your jobs\n• Click **Proceed Anyway** to leave and cancel all jobs",
            inline=False
        )
        
        view = JobCancellationConfirmView(self.bot, user_id, active_jobs)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        return False  # Don't proceed yet, wait for user confirmation

    async def _start_travel_progress_tracking(self, transit_channel, user_or_group_id, corridor_id, travel_time, start_time, end_time, dest_name, is_group=False):
        """Start auto-refreshing progress tracking in transit channel for solo or group travel"""
        try:
            # Send initial progress embed
            embed = self._create_progress_embed(0, travel_time, start_time, end_time, dest_name)
            progress_message = await transit_channel.send(embed=embed)

            # Track this message for auto-updates
            if is_group:
                session_key = f"group_{user_or_group_id}_{corridor_id}"
                session_data = {
                    'message': progress_message,
                    'channel': transit_channel,
                    'start_time': start_time,
                    'end_time': end_time,
                    'travel_time': travel_time,
                    'dest_name': dest_name,
                    'group_id': user_or_group_id,
                    'corridor_id': corridor_id
                }
            else:
                session_key = f"{user_or_group_id}_{corridor_id}"
                session_data = {
                    'message': progress_message,
                    'channel': transit_channel,
                    'start_time': start_time,
                    'end_time': end_time,
                    'travel_time': travel_time,
                    'dest_name': dest_name,
                    'user_id': user_or_group_id,
                    'corridor_id': corridor_id
                }

            self.active_status_messages[session_key] = session_data

            # Start auto-refresh loop
            asyncio.create_task(self._auto_refresh_progress(session_key))

        except Exception as e:
            print(f"❌ Failed to start progress tracking: {e}")

    async def _auto_refresh_progress(self, session_key):
        """Auto-refresh progress embed every 30 seconds"""
        try:
            while session_key in self.active_status_messages:
                await asyncio.sleep(30)  # Update every 30 seconds
                
                if session_key not in self.active_status_messages:
                    break
                
                session_data = self.active_status_messages[session_key]
                
                # Check if travel is still active for solo or group
                if 'group_id' in session_data:
                    active_session = self.db.execute_query(
                        "SELECT status FROM travel_sessions WHERE group_id = ? AND corridor_id = ? AND status = 'traveling' LIMIT 1",
                        (session_data['group_id'], session_data['corridor_id']),
                        fetch='one'
                    )
                else:
                    active_session = self.db.execute_query(
                        "SELECT status FROM travel_sessions WHERE user_id = ? AND corridor_id = ? AND status = 'traveling'",
                        (session_data['user_id'], session_data['corridor_id']),
                        fetch='one'
                    )
                
                if not active_session:
                    # Travel completed or cancelled, stop refreshing
                    if session_key in self.active_status_messages:
                        del self.active_status_messages[session_key]
                    break
                
                # Calculate current progress
                now = datetime.utcnow()
                elapsed = (now - session_data['start_time']).total_seconds()
                progress_percent = min(100, (elapsed / session_data['travel_time']) * 100) if session_data['travel_time'] > 0 else 100
                
                # Update embed
                embed = self._create_progress_embed(
                    progress_percent, 
                    session_data['travel_time'],
                    session_data['start_time'],
                    session_data['end_time'],
                    session_data['dest_name']
                )
                
                try:
                    await session_data['message'].edit(embed=embed)
                except:
                    # Message deleted or channel gone, stop refreshing
                    if session_key in self.active_status_messages:
                        del self.active_status_messages[session_key]
                    break
                    
        except Exception as e:
            print(f"❌ Error in auto-refresh: {e}")
            if session_key in self.active_status_messages:
                del self.active_status_messages[session_key]

    async def _auto_refresh_progress(self, session_key):
        """Auto-refresh progress embed every 30 seconds"""
        try:
            while session_key in self.active_status_messages:
                await asyncio.sleep(30)  # Update every 30 seconds
                
                if session_key not in self.active_status_messages:
                    break
                
                session_data = self.active_status_messages[session_key]
                
                # Check if travel is still active
                active_session = self.db.execute_query(
                    "SELECT status FROM travel_sessions WHERE user_id = ? AND corridor_id = ? AND status = 'traveling'",
                    (session_data['user_id'], session_data['corridor_id']),
                    fetch='one'
                )
                
                if not active_session:
                    # Travel completed or cancelled, stop refreshing
                    del self.active_status_messages[session_key]
                    break
                
                # Calculate current progress
                now = datetime.utcnow()
                elapsed = (now - session_data['start_time']).total_seconds()
                progress_percent = min(100, (elapsed / session_data['travel_time']) * 100)
                
                # Update embed
                embed = self._create_progress_embed(
                    progress_percent, 
                    session_data['travel_time'],
                    session_data['start_time'],
                    session_data['end_time'],
                    session_data['dest_name']
                )
                
                try:
                    await session_data['message'].edit(embed=embed)
                except:
                    # Message deleted or channel gone, stop refreshing
                    del self.active_status_messages[session_key]
                    break
                    
        except Exception as e:
            print(f"❌ Error in auto-refresh: {e}")
            if session_key in self.active_status_messages:
                del self.active_status_messages[session_key]

    def _create_progress_embed(self, progress_percent, travel_time, start_time, end_time, dest_name):
        """Create a progress embed with progress bar and ETA"""
        embed = discord.Embed(
            title="🚀 Journey in Progress",
            description=f"Traveling to **{dest_name}**",
            color=0xff6600
        )
        
        # Progress bar
        filled_blocks = int(progress_percent // 10)
        empty_blocks = 10 - filled_blocks
        progress_bar = "🟩" * filled_blocks + "⬜" * empty_blocks
        
        embed.add_field(
            name="📊 Progress",
            value=f"`{progress_bar}` {progress_percent:.1f}%",
            inline=False
        )
        
        # Time information
        now = datetime.utcnow()
        elapsed = (now - start_time).total_seconds()
        remaining = max(0, (end_time - now).total_seconds())
        
        # Format times
        def format_time(seconds):
            seconds = int(seconds)
            hours = seconds // 3600
            minutes = (seconds % 3600) // 60
            secs = seconds % 60
            
            if hours > 0:
                return f"{hours}h {minutes}m {secs}s"
            elif minutes > 0:
                return f"{minutes}m {secs}s"
            else:
                return f"{secs}s"
        
        embed.add_field(
            name="⏱️ Time Elapsed",
            value=format_time(elapsed),
            inline=True
        )
        
        embed.add_field(
            name="⏳ Time Remaining",
            value=format_time(remaining) if remaining > 0 else "Arriving soon...",
            inline=True
        )
        
        # FIXED: ETA timestamp calculation
        if remaining > 0:
            # Use the actual end_time as UTC so timestamp() isn’t offset by the server’s local TZ
            utc_ts = int(end_time.replace(tzinfo=timezone.utc).timestamp())
            embed.add_field(
                name="🎯 Estimated Arrival",
                value=f"<t:{utc_ts}:R>",
                inline=True
            )
        else:
            embed.add_field(
                name="🎯 Status",
                value="**Arriving Now**",
                inline=True
            )
        
        embed.add_field(
            name="⚠️ Transit Safety",
            value="Monitor this channel for corridor events and hazards",
            inline=False
        )
        
        # Add timestamp
        embed.timestamp = now
        embed.set_footer(text="Auto-updating every 30 seconds")
        
        return embed
# In cogs/travel.py, replace the _complete_travel_after_delay method

    async def _complete_travel_after_delay(self, user_id, corridor_id, travel_time, dest_name, transit_chan, guild):
        """Waits for travel time and then hands off to the arrival handler."""
        await asyncio.sleep(travel_time)

        try:
            # Get destination and origin info from the completed travel session
            session_info = self.db.execute_query(
                "SELECT destination_location, origin_location FROM travel_sessions WHERE user_id=? AND corridor_id=? AND status='traveling' ORDER BY session_id DESC LIMIT 1",
                (user_id, corridor_id), fetch='one'
            )
            if not session_info:
                print(f"No active travel session found for user {user_id} on completion.")
                return

            dest_location_id, origin_location_id = session_info

            # Mark session as arrived before handling access
            self.db.execute_query(
                "UPDATE travel_sessions SET status='arrived' WHERE user_id=? AND corridor_id=? AND status='traveling'",
                (user_id, corridor_id)
            )

            # Handle the arrival access check
            await self._handle_arrival_access(user_id, dest_location_id, origin_location_id, guild, transit_chan)

        except Exception as e:
            print(f"❌ Error during initial travel completion: {e}")


    async def _handle_arrival_access(self, user_id: int, dest_location_id: int, origin_location_id: int, guild: discord.Guild, transit_chan: discord.TextChannel):
        """Handles docking access checks, fees, and combat for faction-controlled areas."""
        try:
            # Get destination and character info
            location_info = self.db.execute_query("SELECT name, faction FROM locations WHERE location_id = ?", (dest_location_id,), fetch='one')
            if not location_info: return
            dest_name, faction = location_info

            rep_cog = self.bot.get_cog('ReputationCog')
            if not rep_cog:
                print("ReputationCog not found, cannot check access.")
                # Fallback to default behavior if rep system is offline
                await self._grant_final_access(user_id, dest_location_id, guild, transit_chan)
                return

            rep_entry = self.db.execute_query("SELECT reputation FROM character_reputation WHERE user_id = ? AND location_id = ?", (user_id, dest_location_id), fetch='one')
            reputation = rep_entry[0] if rep_entry else 0
            rep_tier = rep_cog.get_reputation_tier(reputation)

            access_granted = False
            message = ""
            view = None

            # Faction Logic
            if faction == 'government':
                if rep_tier in ['Heroic', 'Good']:
                    access_granted = True
                    message = f"Welcome to the secure government area of {dest_name}, your reputation precedes you."
                elif rep_tier == 'Neutral':
                    fee = (50 - reputation) * 10
                    message = f"{dest_name} is a secure government area. Due to your neutral reputation, a docking fee of **{fee:,} credits** is required."
                    view = DockingFeeView(self.bot, user_id, dest_location_id, fee, origin_location_id)
                else: # Bad or Evil
                    message = f"🚨 **HOSTILE DETECTED!** 🚨\nYour criminal reputation is known here. {dest_name} security forces engage on sight! You are forced to retreat."
                    await self._force_retreat(user_id, origin_location_id, guild, transit_chan, message)
                    return

            elif faction == 'bandit':
                if rep_tier in ['Evil', 'Bad']:
                    access_granted = True
                    message = f"Welcome to {dest_name}, friend. We don't ask questions here."
                elif rep_tier == 'Neutral':
                    fee = (50 + reputation) * 10
                    message = f"{dest_name} is a haven for those outside the law. To prove you're not a spy, a 'contribution' of **{fee:,} credits** is required to dock."
                    view = DockingFeeView(self.bot, user_id, dest_location_id, fee, origin_location_id)
                else: # Good or Heroic
                    message = f"⚔️ **LAWMAN DETECTED!** ⚔️\nYour kind isn't welcome at {dest_name}. The locals open fire, forcing you to retreat!"
                    await self._force_retreat(user_id, origin_location_id, guild, transit_chan, message)
                    return

            else: # Neutral faction
                access_granted = True
                message = f"You have arrived at {dest_name}."

            # Process access
            if access_granted:
                await self._grant_final_access(user_id, dest_location_id, guild, transit_chan, message)
            elif view:
                # Send message and wait for fee payment
                if transit_chan: await transit_chan.send(message, view=view)
                decision = await view.wait_for_decision()
                if decision == 'pay':
                    await self._grant_final_access(user_id, dest_location_id, guild, transit_chan, f"Docking fees paid. You are cleared to land at {dest_name}.")
                else: # Leave
                    await self._force_retreat(user_id, origin_location_id, guild, transit_chan, f"You refused to pay the fee and have returned to your previous location.")

        except Exception as e:
            print(f"❌ Error in arrival access handling: {e}")
            # Fallback to granting access on error to avoid trapping players
            await self._grant_final_access(user_id, dest_location_id, guild, transit_chan, "An error occurred during docking, but you have been granted access.")


    async def _grant_final_access(self, user_id: int, dest_location_id: int, guild: discord.Guild, transit_chan: discord.TextChannel, arrival_message: str = ""):
        """Finalizes arrival, updates DB and channels, and cleans up."""
        self.db.execute_query(
            "UPDATE characters SET current_location=? WHERE user_id=?",
            (dest_location_id, user_id)
        )
        
        # Update ship docking location
        ship_id_result = self.db.execute_query("SELECT active_ship_id FROM characters WHERE user_id=?", (user_id,), fetch='one')
        if ship_id_result and ship_id_result[0]:
            self.db.execute_query("UPDATE ships SET docked_at_location=? WHERE ship_id=?", (dest_location_id, ship_id_result[0]))

        # Give channel access
        await self.channel_mgr.update_channel_on_player_movement(guild, user_id, None, dest_location_id)

        # Send arrival message
        if transit_chan:
            await transit_chan.send(arrival_message)
            await self.channel_mgr.cleanup_transit_channel(transit_chan.id, delay_seconds=30)
        
        # Cleanup progress tracking
        # This part assumes you have a way to derive the corridor_id for the session_key.
        # Since it's complex, we'll just attempt a generic cleanup.
        for key in list(self.active_status_messages.keys()):
            if key.startswith(f"{user_id}_"):
                del self.active_status_messages[key]
                break


    async def _force_retreat(self, user_id: int, origin_location_id: int, guild: discord.Guild, transit_chan: discord.TextChannel, reason: str):
        """Forces a player to retreat back to their origin location."""
        if transit_chan: await transit_chan.send(reason)
        
        # Move character back to origin
        self.db.execute_query(
            "UPDATE characters SET current_location = ? WHERE user_id = ?",
            (origin_location_id, user_id)
        )

        # Give channel access back to origin
        await self.channel_mgr.give_user_location_access(guild.get_member(user_id), origin_location_id)

        # Cleanup transit channel
        if transit_chan:
            await self.channel_mgr.cleanup_transit_channel(transit_chan.id, delay_seconds=15)

    @travel_group.command(name="routes", description="View available travel routes from current location")
    async def view_routes(self, interaction: discord.Interaction):
        char_location = self.db.execute_query(
            "SELECT current_location FROM characters WHERE user_id = ?",
            (interaction.user.id,),
            fetch='one'
        )
        
        if not char_location:
            await interaction.response.send_message("Character not found!", ephemeral=True)
            return
            
        if not char_location[0]:
            await interaction.response.send_message("You are currently in transit. Use `/travel status` to check your journey progress.", ephemeral=True)
            return
        
        current_location_id = char_location[0]
        
        # Get current location name
        current_location_name = self.db.execute_query(
            "SELECT name FROM locations WHERE location_id = ?",
            (current_location_id,),
            fetch='one'
        )[0]
        
        routes = self.db.execute_query(
            '''SELECT c.name, l.name, l.location_type, c.travel_time, c.danger_level, c.corridor_id
               FROM corridors c
               JOIN locations l ON c.destination_location = l.location_id
               WHERE c.origin_location = ? AND c.is_active = 1
               ORDER BY c.travel_time''',
            (current_location_id,),
            fetch='all'
        )
        
        embed = discord.Embed(
                title="🗺️ Available Travel Routes",
                description=f"Routes departing from **{current_location_name}**",
                color=0x4169E1
            )
            
        if routes:
            route_lines = []
            
            # Get ship efficiency for time estimates
            ship_efficiency = self.db.execute_query(
                "SELECT fuel_efficiency FROM ships WHERE owner_id = ?",
                (interaction.user.id,), fetch='one'
            )
            ship_eff = ship_efficiency[0] if ship_efficiency else 5
            efficiency_modifier = 1.6 - (ship_eff * 0.08)
            
            for corridor_name, dest_name, dest_type, travel_time, danger, corridor_id in routes:
                # Apply ship efficiency to displayed time
                actual_time = max(int(travel_time * efficiency_modifier), 60)
                
                # Determine route type and emoji
                if "Approach" in corridor_name:
                    route_emoji = "🌌"  # Local space
                elif "Ungated" in corridor_name:
                    route_emoji = "⭕"  # Dangerous ungated
                else:
                    route_emoji = "🔵"  # Safe gated
                
                dest_emoji = {
                    'colony': '🏭',
                    'space_station': '🛰️',
                    'outpost': '🛤️',
                    'gate': '🚪'
                }.get(dest_type, '📍')
                
                # Format time with ship efficiency
                mins = actual_time // 60
                secs = actual_time % 60
                if mins >= 60:
                    hours = mins // 60
                    mins = mins % 60
                    time_text = f"{hours}h{mins}m"
                else:
                    time_text = f"{mins}m{secs}s" if secs > 0 else f"{mins}m"
                
                danger_text = "⚠️" * danger if danger > 0 else ""
                
                # Show both base time and ship-modified time
                base_mins = travel_time // 60
                if base_mins != mins:
                    time_text += f" (base: {base_mins}m)"
                
                route_lines.append(f"{route_emoji} **{current_location_name}** → {dest_emoji} **{dest_name}**\n   `{time_text}` travel time {danger_text}")
            
            embed.add_field(
                name="🚀 Available Departures",
                value="\n".join(route_lines),
                inline=False
            )
            
            if ship_efficiency:
                embed.add_field(
                    name="🔧 Ship Performance",
                    value=f"Your ship efficiency: {ship_eff}/10\nBetter efficiency = faster travel",
                    inline=False
                )
        else:
            embed.add_field(
                name="🚀 Available Departures",
                value="*No active routes from this location*",
                inline=False
            )
            
        embed.add_field(
            name="💡 How to Travel",
            value="Use `/travel go` to select a route and begin your journey.",
            inline=False
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @travel_group.command(name="status", description="Show your current travel progress")
    async def travel_status(self, interaction: discord.Interaction):
        record = self.db.execute_query(
            """
            SELECT
              ts.start_time,
              ts.end_time,
              ts.temp_channel_id,
              c.name        AS corridor_name,
              dest.name     AS dest_name,
              orig.name     AS origin_name
            FROM travel_sessions ts
            JOIN corridors c  ON ts.corridor_id       = c.corridor_id
            JOIN locations dest ON ts.destination_location = dest.location_id
            JOIN locations orig ON ts.origin_location      = orig.location_id
            WHERE ts.user_id = ? AND ts.status = 'traveling'
            """,
            (interaction.user.id,),
            fetch='one'
        )

        if not record:
            return await interaction.response.send_message(
                "You are not currently traveling.", ephemeral=True
            )

        try:
            start_str, end_str, temp_chan_id, corridor_name, dest_name, origin_name = record
            start_dt = datetime.fromisoformat(start_str)
            end_dt   = datetime.fromisoformat(end_str)
            now      = datetime.utcnow()  # Use UTC to match database times
            remaining = end_dt - now

            if remaining.total_seconds() <= 0:
                return await interaction.response.send_message(
                    "Your journey should be completing soon.", ephemeral=True
                )

            # Calculate travel time and progress
            total_journey_secs = (end_dt - start_dt).total_seconds()
            elapsed = (now - start_dt).total_seconds()
            progress = max(0, min(100, (elapsed / total_journey_secs) * 100)) if total_journey_secs > 0 else 0

            # Create the same style embed as the auto-refreshing one
            embed = self._create_progress_embed(progress, total_journey_secs, start_dt, end_dt, dest_name)
            
            # Add route information
            embed.insert_field_at(0, name="🗺️ Route", value=f"**{origin_name}** → **{dest_name}**\nvia *{corridor_name}*", inline=False)

            if temp_chan_id:
                temp_chan = self.bot.get_channel(temp_chan_id)
                if temp_chan:
                    embed.add_field(name="Transit Channel", value=temp_chan.mention, inline=True)

            # ADD THIS SHIP EFFICIENCY CODE HERE:
            # Get ship efficiency for accurate time calculation
            ship_efficiency = self.db.execute_query(
                "SELECT fuel_efficiency FROM ships WHERE owner_id = ?",
                (interaction.user.id,), fetch='one'
            )

            if ship_efficiency:
                ship_eff_value = ship_efficiency[0]
                embed.add_field(
                    name="🚀 Ship Efficiency", 
                    value=f"Level {ship_eff_value}/10 (affects travel speed)", 
                    inline=True
                )
        except Exception as e:
            print(f"[TravelStatus] error calculating progress: {e}")
            embed = discord.Embed(
                title="Travel Status Error",
                description="Unable to calculate travel progress. Contact an administrator.",
                color=0xff0000
            )

        await interaction.response.send_message(embed=embed, ephemeral=True)

    
    @travel_group.command(name="emergency_exit", description="Attempt an emergency exit from a corridor (EXTREMELY DANGEROUS)")
    async def emergency_exit(self, interaction: discord.Interaction):
        session = self.db.execute_query(
            '''SELECT ts.*, c.danger_level, c.name as corridor_name
               FROM travel_sessions ts
               JOIN corridors c ON ts.corridor_id = c.corridor_id
               WHERE ts.user_id = ? AND ts.status = 'traveling' ''',
            (interaction.user.id,),
            fetch='one'
        )

        if not session:
            await interaction.response.send_message("You are not currently traveling.", ephemeral=True)
            return

        corridor_name = session[11]
        if "Approach" in corridor_name:
            await interaction.response.send_message("You cannot perform an emergency exit in local space.", ephemeral=True)
            return

        embed = discord.Embed(
            title="⚠️ EMERGENCY CORRIDOR EXIT",
            description="**EXTREME WARNING**: This action has a high probability of resulting in **instant death**.\n\nSurviving the exit will cause catastrophic damage to your ship and severe injury. You will be end up in a random location.",
            color=0xff0000
        )

        danger_level = session[10]
        survival_chance = max(10, 50 - (danger_level * 10))  # High risk of death

        embed.add_field(
            name="Estimated Survival Chance",
            value=f"**{survival_chance}%** (Danger Level: {danger_level})",
            inline=False
        )
        embed.add_field(
            name="Recommendation",
            value="**DO NOT ATTEMPT** unless certain death is imminent. It is always safer to complete the journey.",
            inline=False
        )

        view = EmergencyExitView(self.bot, interaction.user.id, session[0])
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
    
    @travel_group.command(name="fuel_estimate", description="Calculate fuel needed for various routes")
    async def fuel_estimate(self, interaction: discord.Interaction):
        char_location = self.db.execute_query(
            "SELECT current_location FROM characters WHERE user_id = ?",
            (interaction.user.id,),
            fetch='one'
        )
        
        if not char_location:
            await interaction.response.send_message("Character not found!", ephemeral=True)
            return
        
        if not char_location[0]:
            await interaction.response.send_message("You are currently in transit and cannot calculate fuel estimates.", ephemeral=True)
            return
        
        # Get ship efficiency
        ship_info = self.db.execute_query(
            '''SELECT s.current_fuel, s.fuel_capacity, s.fuel_efficiency, c.name as owner_name
               FROM characters c
               JOIN ships s ON c.ship_id = s.ship_id
               WHERE c.user_id = ?''',
            (interaction.user.id,),
            fetch='one'
        )
        
        if not ship_info:
            await interaction.response.send_message("Ship information not found!", ephemeral=True)
            return
        
        current_fuel, fuel_capacity, efficiency, owner_name = ship_info
        
        # Get nearby routes
        routes = self.db.execute_query(
            '''SELECT l.name, c.fuel_cost, c.travel_time, c.danger_level
               FROM corridors c
               JOIN locations l ON c.destination_location = l.location_id
               WHERE c.origin_location = ? AND c.is_active = 1
               ORDER BY c.fuel_cost''',
            (char_location[0],),
            fetch='all'
        )
        
        embed = discord.Embed(
            title="⛽ Fuel Consumption Estimates",
            description=f"Fuel calculations for {owner_name}",
            color=0x8B4513
        )
        
        # Ship status
        fuel_percent = (current_fuel / fuel_capacity) * 100 if fuel_capacity > 0 else 0
        fuel_emoji = "🟢" if fuel_percent > 70 else "🟡" if fuel_percent > 30 else "🔴"
        
        embed.add_field(
            name="Current Fuel",
            value=f"{fuel_emoji} {current_fuel}/{fuel_capacity} ({fuel_percent:.0f}%)",
            inline=True
        )
        embed.add_field(name="Engine Efficiency", value=f"{efficiency}/10", inline=True)
        embed.add_field(name="", value="", inline=True)  # Spacer
        
        if routes:
            # Calculate actual fuel consumption based on ship efficiency
            route_text = []
            for dest_name, base_fuel_cost, travel_time, danger in routes[:8]:
                # Better efficiency reduces fuel consumption
                actual_cost = max(1, int(base_fuel_cost * (11 - efficiency) / 10))
                
                status = "✅" if current_fuel >= actual_cost else "❌"
                danger_text = "⚠️" * danger
                time_text = f"{travel_time//60}m"
                
                route_text.append(f"{status} **{dest_name}** - {actual_cost} fuel ({time_text}) {danger_text}")
            
            embed.add_field(
                name="Route Fuel Requirements",
                value="\n".join(route_text),
                inline=False
            )
            
            # Calculate maximum range
            if routes:
                cheapest_route = min(routes, key=lambda x: x[1])
                cheapest_cost = max(1, int(cheapest_route[1] * (11 - efficiency) / 10))
                max_jumps = current_fuel // cheapest_cost if cheapest_cost > 0 else 0
                
                embed.add_field(
                    name="Maximum Range",
                    value=f"~{max_jumps} jumps on current fuel",
                    inline=True
                )
        else:
            embed.add_field(name="No Routes Available", value="No active corridors from current location.", inline=False)
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    @travel_group.command(name="plotroute", description="Calculate the best route to a destination")
    @app_commands.describe(destination="Name of the destination location")
    async def plot_route(self, interaction: discord.Interaction, destination: str):
        # Check if user is logged in
        login_status = self.db.execute_query(
            "SELECT is_logged_in FROM characters WHERE user_id = ?",
            (interaction.user.id,),
            fetch='one'
        )

        if not login_status or not login_status[0]:
            await interaction.response.send_message(
                "❌ You must be logged in to plot routes! Use `/character login` first.",
                ephemeral=True
            )
            return

        # Get current location
        char_location = self.db.execute_query(
            "SELECT current_location FROM characters WHERE user_id = ?",
            (interaction.user.id,),
            fetch='one'
        )
        
        if not char_location or not char_location[0]:
            await interaction.response.send_message(
                "❌ You must be at a location to plot routes. Complete your current travel first.",
                ephemeral=True
            )
            return
        
        current_location_id = char_location[0]
        
        await interaction.response.defer(ephemeral=True)
        
        try:
            # Find destination location(s) with fuzzy matching
            destination_matches = self.db.execute_query(
                "SELECT location_id, name, location_type FROM locations WHERE name LIKE ? ORDER BY name",
                (f"%{destination}%",),
                fetch='all'
            )
            
            if not destination_matches:
                await interaction.followup.send(
                    f"❌ No location found matching '{destination}'. Try a different search term.",
                    ephemeral=True
                )
                return
            
            # If multiple matches, show options or pick exact match
            if len(destination_matches) > 1:
                exact_match = None
                for match in destination_matches:
                    if match[1].lower() == destination.lower():
                        exact_match = match
                        break
                
                if exact_match:
                    destination_matches = [exact_match]
                else:
                    # Show multiple options
                    if len(destination_matches) > 10:
                        destination_matches = destination_matches[:10]
                    
                    options_text = []
                    for loc_id, name, loc_type in destination_matches:
                        type_emoji = {
                            'colony': '🏭',
                            'space_station': '🛰️', 
                            'outpost': '🛤️',
                            'gate': '🚪'
                        }.get(loc_type, '📍')
                        options_text.append(f"{type_emoji} **{name}** ({loc_type})")
                    
                    embed = discord.Embed(
                        title="🔍 Multiple Locations Found",
                        description=f"Found {len(destination_matches)} locations matching '{destination}':",
                        color=0xffaa00
                    )
                    embed.add_field(
                        name="Matches",
                        value="\n".join(options_text),
                        inline=False
                    )
                    embed.add_field(
                        name="💡 Tip",
                        value="Try a more specific search term, or use the exact location name.",
                        inline=False
                    )
                    
                    await interaction.followup.send(embed=embed, ephemeral=True)
                    return
            
            destination_id, dest_name, dest_type = destination_matches[0]
            
            # Check if already at destination
            if destination_id == current_location_id:
                current_name = self.db.execute_query(
                    "SELECT name FROM locations WHERE location_id = ?",
                    (current_location_id,),
                    fetch='one'
                )[0]
                
                await interaction.followup.send(
                    f"❌ You are already at **{current_name}**!",
                    ephemeral=True
                )
                return
            
            # Calculate route
            route = await self._calculate_shortest_route(current_location_id, destination_id)
            
            if not route:
                # No route found
                current_name = self.db.execute_query(
                    "SELECT name FROM locations WHERE location_id = ?",
                    (current_location_id,),
                    fetch='one'
                )[0]
                
                embed = discord.Embed(
                    title="🚫 No Route Available",
                    description=f"No available route from **{current_name}** to **{dest_name}**.",
                    color=0xff4444
                )
                embed.add_field(
                    name="⏳ Try Again Later",
                    value="Corridor networks change over time. Wait for corridor shifts and try again.",
                    inline=False
                )
                embed.add_field(
                    name="💡 Alternative Options",
                    value="• Check `/travel routes` for current available routes\n• Travel to intermediate locations first\n• Wait for automatic corridor shifts",
                    inline=False
                )
                
                await interaction.followup.send(embed=embed, ephemeral=True)
                return
            
            # Format and send route
            await self._send_route_embeds(interaction, route, dest_name)
            
        except Exception as e:
            print(f"❌ Error in plot_route: {e}")
            await interaction.followup.send(
                "❌ An error occurred while calculating the route. Please try again.",
                ephemeral=True
            )

    async def _calculate_shortest_route(self, start_id: int, end_id: int) -> list:
        """Calculate shortest route using BFS pathfinding"""
        
        # Get all active corridors
        corridors = self.db.execute_query(
            "SELECT origin_location, destination_location, corridor_id, name, travel_time FROM corridors WHERE is_active = 1",
            fetch='all'
        )
        
        # Build adjacency graph
        graph = {}
        corridor_info = {}
        
        for origin, dest, corridor_id, corridor_name, travel_time in corridors:
            if origin not in graph:
                graph[origin] = []
            graph[origin].append(dest)
            corridor_info[(origin, dest)] = {
                'corridor_id': corridor_id,
                'name': corridor_name,
                'travel_time': travel_time
            }
        
        # BFS to find shortest path
        from collections import deque
        
        queue = deque([(start_id, [start_id])])
        visited = {start_id}
        
        while queue:
            current_location, path = queue.popleft()
            
            if current_location == end_id:
                # Found destination, build detailed route
                detailed_route = []
                for i in range(len(path) - 1):
                    origin = path[i]
                    dest = path[i + 1]
                    
                    # Get location info
                    origin_info = self.db.execute_query(
                        "SELECT name, location_type FROM locations WHERE location_id = ?",
                        (origin,),
                        fetch='one'
                    )
                    dest_info = self.db.execute_query(
                        "SELECT name, location_type FROM locations WHERE location_id = ?",
                        (dest,),
                        fetch='one'
                    )
                    
                    corridor = corridor_info.get((origin, dest))
                    
                    if origin_info and dest_info and corridor:
                        detailed_route.append({
                            'origin_id': origin,
                            'origin_name': origin_info[0],
                            'origin_type': origin_info[1],
                            'dest_id': dest,
                            'dest_name': dest_info[0],
                            'dest_type': dest_info[1],
                            'corridor_name': corridor['name'],
                            'travel_time': corridor['travel_time']
                        })
                
                return detailed_route
            
            # Explore neighbors
            if current_location in graph:
                for neighbor in graph[current_location]:
                    if neighbor not in visited:
                        visited.add(neighbor)
                        queue.append((neighbor, path + [neighbor]))
        
        return []  # No route found

    async def _send_route_embeds(self, interaction: discord.Interaction, route: list, dest_name: str):
        """Send route information, splitting into multiple embeds if needed"""
        
        if not route:
            return
        
        # Calculate totals
        total_time = sum(step['travel_time'] for step in route)
        total_jumps = len(route)
        
        # Format time
        hours = total_time // 3600
        minutes = (total_time % 3600) // 60
        seconds = total_time % 60
        
        if hours > 0:
            total_time_str = f"{hours}h {minutes}m {seconds}s"
        elif minutes > 0:
            total_time_str = f"{minutes}m {seconds}s"
        else:
            total_time_str = f"{seconds}s"
        
        # Create main embed
        embed = discord.Embed(
            title="🗺️ Route to " + dest_name,
            description=f"**{total_jumps} jump{'s' if total_jumps != 1 else ''}** • **{total_time_str}** total travel time",
            color=0x4169E1
        )
        
        # Build route steps
        route_steps = []
        step_emojis = {
            'colony': '🏭',
            'space_station': '🛰️',
            'outpost': '🛤️', 
            'gate': '🚪'
        }
        
        # Add starting location
        start_emoji = step_emojis.get(route[0]['origin_type'], '📍')
        route_steps.append(f"{start_emoji} **{route[0]['origin_name']}** *(current)*")
        
        # Add route steps
        for i, step in enumerate(route):
            # Format travel time
            step_time = step['travel_time']
            step_mins = step_time // 60
            step_secs = step_time % 60
            time_str = f"{step_mins}m {step_secs}s" if step_mins > 0 else f"{step_secs}s"
            
            # Add corridor
            corridor_type = "🔵" if "Ungated" not in step['corridor_name'] else "⭕"
            route_steps.append(f"    ↓ *{step['corridor_name']}* ({time_str}) {corridor_type}")
            
            # Add destination
            dest_emoji = step_emojis.get(step['dest_type'], '📍')
            dest_status = " *(destination)*" if i == len(route) - 1 else ""
            route_steps.append(f"{dest_emoji} **{step['dest_name']}**{dest_status}")
        
        # Split into multiple embeds if too long
        max_chars = 1000  # Conservative limit for embed field
        current_content = []
        embed_count = 1
        
        for step in route_steps:
            test_content = current_content + [step]
            if len('\n'.join(test_content)) > max_chars and current_content:
                # Send current embed
                embed.add_field(
                    name=f"🛤️ Route Steps {f'(Part {embed_count})' if len(route_steps) > 10 else ''}",
                    value='\n'.join(current_content),
                    inline=False
                )
                
                if embed_count == 1:
                    # Add additional info to first embed
                    embed.add_field(
                        name="📊 Route Summary",
                        value=f"**Jumps:** {total_jumps}\n**Total Time:** {total_time_str}\n**Corridor Types:** Mixed",
                        inline=True
                    )
                    
                embed.add_field(
                    name="🗺️ Route Legend",
                    value="🌌 = Local Space (Safe, Short)\n🔵 = Gated Corridor (Safe, Medium)\n⭕ = Ungated Corridor (Dangerous, Direct)",
                    inline=True
                )

                embed.add_field(
                    name="ℹ️ Travel Types",
                    value="**Local Space:** Short movements within system\n**Gated:** Protected inter-system routes\n**Ungated:** Direct but hazardous passages",
                    inline=True
                )
                    
                await interaction.followup.send(embed=embed, ephemeral=True)
                embed_count += 1
                
                # Create new embed for continuation
                embed = discord.Embed(
                    title=f"🗺️ Route to {dest_name} (Part {embed_count})",
                    color=0x4169E1
                )
                current_content = [step]
            else:
                current_content.append(step)
        
        # Send final embed
        if current_content:
            embed.add_field(
                name=f"🛤️ Route Steps {f'(Part {embed_count})' if embed_count > 1 else ''}",
                value='\n'.join(current_content),
                inline=False
            )
            
            if embed_count == 1:
                # Add summary info if this is the only embed
                embed.add_field(
                    name="📊 Route Summary", 
                    value=f"**Jumps:** {total_jumps}\n**Total Time:** {total_time_str}",
                    inline=True
                )
                
                embed.add_field(
                    name="🔵 Legend",
                    value="🔵 = Gated (Safe)\n⭕ = Ungated (Dangerous)",
                    inline=True
                )
            
            embed.add_field(
                name="💡 Next Steps",
                value="Use `/travel go` to begin your journey along this route.",
                inline=False
            )
            
            await interaction.followup.send(embed=embed, ephemeral=True)
class EmergencyExitView(discord.ui.View):
    def __init__(self, bot, user_id: int, session_id: int):
        super().__init__(timeout=60)
        self.bot = bot
        self.user_id = user_id
        self.session_id = session_id
    
    @discord.ui.button(label="CONFIRM EMERGENCY EXIT", style=discord.ButtonStyle.danger, emoji="💀")
    async def confirm_exit(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This is not your panel!", ephemeral=True)
            return
        
        # Get session info
        session = self.bot.db.execute_query(
            '''SELECT ts.*, c.danger_level, ol.name as origin_name, dl.name as dest_name
               FROM travel_sessions ts
               JOIN corridors c ON ts.corridor_id = c.corridor_id
               JOIN locations ol ON ts.origin_location = ol.location_id
               JOIN locations dl ON ts.destination_location = dl.location_id
               WHERE ts.session_id = ?''',
            (self.session_id,),
            fetch='one'
        )
        
        if not session or session[9] != 'traveling':
            await interaction.response.send_message("Travel session no longer active!", ephemeral=True)
            return
        
        danger_level = session[10]
        survival_chance = max(10, 50 - (danger_level * 10))
        
        # Roll for survival
        roll = random.randint(1, 100)
        survived = roll <= survival_chance
        
        if survived:
            # Survived the exit, now take massive damage
            hp_loss = random.randint(40, 80)
            hull_loss = random.randint(50, 90)
            
            # Apply damage and check for death from damage
            char_cog = self.bot.get_cog('CharacterCog')
            died_from_damage = False
            if char_cog:
                died_from_damage = await char_cog.update_character_hp(
                    self.user_id, -hp_loss, interaction.guild, "Emergency exit trauma"
                )

            if died_from_damage:
                # Death is handled by update_character_hp, just end here
                await interaction.response.edit_message(content="You survived the initial corridor exit, but the trauma was too much. Your vision fades to black...", view=None)
                return

            # Survived the damage, apply hull damage and relocate
            self.bot.db.execute_query(
                "UPDATE ships SET hull_integrity = MAX(1, hull_integrity - ?) WHERE owner_id = ?",
                (hull_loss, self.user_id)
            )

            # Relocate to a random, non-gate location
            random_location = self.bot.db.execute_query(
                "SELECT location_id, name FROM locations WHERE location_type != 'gate' ORDER BY RANDOM() LIMIT 1",
                fetch='one'
            )
            
            if random_location:
                new_location_id, new_location_name = random_location
                self.bot.db.execute_query(
                    "UPDATE characters SET current_location = ? WHERE user_id = ?",
                    (new_location_id, self.user_id)
                )
                
                # Update channel access
                from utils.channel_manager import ChannelManager
                channel_manager = ChannelManager(self.bot)
                await channel_manager.give_user_location_access(interaction.user, new_location_id)

                outcome_desc = f"You are violently thrown out of the corridor, your ship screaming in protest. You black out, only to awaken in an unknown system near **{new_location_name}**."
                location_text = f"Stranded near {new_location_name}"
            else:
                # Fallback: stranded in deep space
                self.bot.db.execute_query(
                    "UPDATE characters SET current_location = NULL WHERE user_id = ?",
                    (self.user_id,)
                )
                outcome_desc = "You are violently thrown out of the corridor into the blackness of deep space. Your ship is a wreck, and you are lost."
                location_text = "Lost in Deep Space"

            embed = discord.Embed(
                title="🚨 EMERGENCY EXIT SURVIVAL",
                description=outcome_desc,
                color=0xff9900
            )
            embed.add_field(name="Survival Roll", value=f"{roll}/{survival_chance} - SUCCESS", inline=True)
            embed.add_field(name="Health Lost", value=f"{hp_loss} HP", inline=True)
            embed.add_field(name="Hull Damage", value=f"{hull_loss} integrity", inline=True)
            embed.add_field(name="New Location", value=location_text, inline=False)
            embed.add_field(name="⚠️ Critical Actions", value="Seek immediate medical attention and ship repairs.", inline=False)
        else:
            # Did not survive the exit
            char_cog = self.bot.get_cog('CharacterCog')
            if char_cog:
                await char_cog.update_character_hp(self.user_id, -999, interaction.guild, "Failed emergency exit")
            
            embed = discord.Embed(
                title="💀 EMERGENCY EXIT FAILED",
                description="Your attempt to exit the corridor failed catastrophically. The ship was torn apart by the unstable energies of the corridor.",
                color=0x8b0000
            )
            embed.add_field(name="Survival Roll", value=f"{roll}/{survival_chance} - FAILED", inline=True)
            embed.add_field(name="Status", value="Lost to the void", inline=False)

        # Update travel session and clean up
        self.db.execute_query(
            "UPDATE travel_sessions SET status = 'emergency_exit' WHERE session_id = ?",
            (self.session_id,)
        )
        
        if session[6]:  # temp_channel_id
            temp_channel = self.bot.get_channel(session[6])
            if temp_channel:
                try:
                    await temp_channel.delete(reason="Emergency exit from corridor")
                except:
                    pass
        
        await interaction.response.edit_message(embed=embed, view=None)
    
    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary, emoji="❌")
    async def cancel_exit(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This is not your panel!", ephemeral=True)
            return
        
        await interaction.response.edit_message(content="Emergency exit cancelled. Your journey continues.", view=None)
    
    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary, emoji="❌")
    async def cancel_exit(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This is not your panel!", ephemeral=True)
            return
        
        await interaction.response.send_message("Emergency exit cancelled. Continue monitoring corridor conditions.", ephemeral=True)
class JobCancellationConfirmView(discord.ui.View):
    def __init__(self, bot, user_id: int, active_jobs: list):
        super().__init__(timeout=60)
        self.bot = bot
        self.user_id = user_id
        self.active_jobs = active_jobs
    
    @discord.ui.button(label="Proceed Anyway", style=discord.ButtonStyle.danger, emoji="⚠️")
    async def proceed_anyway(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This is not your panel!", ephemeral=True)
            return
        
        # Cancel all active jobs
        for job_id, title, reward in self.active_jobs:
            self.bot.db.execute_query(
                "UPDATE jobs SET is_taken = 0, taken_by = NULL, taken_at = NULL, job_status = 'available' WHERE job_id = ?",
                (job_id,)
            )
            
            # Remove from job tracking
            self.bot.db.execute_query(
                "DELETE FROM job_tracking WHERE job_id = ? AND user_id = ?",
                (job_id, self.user_id)
            )
        
        embed = discord.Embed(
            title="❌ Jobs Cancelled",
            description=f"Cancelled {len(self.active_jobs)} job(s). You may now travel.",
            color=0xff4444
        )
        
        # Now proceed with normal travel - re-trigger the travel command
        travel_cog = self.bot.get_cog('TravelCog')
        if travel_cog:
            # Recreate the travel interface
            await self._show_travel_interface(interaction)
        else:
            await interaction.response.send_message("Travel system unavailable.", ephemeral=True)
    
    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary, emoji="❌")
    async def cancel_travel(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This is not your panel!", ephemeral=True)
            return
        
        await interaction.response.send_message("Travel cancelled. Complete your jobs first.", ephemeral=True)
    
    async def _show_travel_interface(self, interaction: discord.Interaction):
        """Show the normal travel interface after jobs are cancelled"""
        row = self.bot.db.execute_query(
            "SELECT current_location, location_status FROM characters WHERE user_id = ?",
            (self.user_id,),
            fetch='one'
        )
        if not row:
            await interaction.response.send_message("🚫 Character not found.", ephemeral=True)
            return
        
        origin_id, status = row
        
        corridors = self.bot.db.execute_query(
            '''
            SELECT c.corridor_id,
                   c.name,
                   l.name AS dest_name,
                   c.travel_time,
                   c.fuel_cost,
                   l.location_type
              FROM corridors c
              JOIN locations l ON c.destination_location = l.location_id
             WHERE c.origin_location = ? AND c.is_active = 1
            ''',
            (origin_id,),
            fetch='all'
        )
        
        if not corridors:
            await interaction.response.send_message("No corridors depart from here.", ephemeral=True)
            return

        # Get current location name for clearer route display
        current_location_name = self.bot.db.execute_query(
            "SELECT name FROM locations WHERE location_id = ?",
            (origin_id,),
            fetch='one'
        )[0]

        # Build the dropdown - reuse existing logic from travel_go
        from discord import ui
        options = []
        for cid, cname, dest_name, ttime, cost, dest_type in corridors:
            label = f"{current_location_name} → {dest_name}"
            hours   = ttime // 3600
            minutes = (ttime % 3600) // 60
            if hours:
                time_text = f"{hours}h {minutes}m"
            else:
                time_text = f"{minutes}m"

            # Determine travel type
            if "Approach" in cname:
                travel_type = "🌌 LOCAL"
            elif dest_type == "gate":
                travel_type = "🔵 GATED"
            elif "Ungated" in cname:
                travel_type = "⭕ UNGATED"
            else:
                travel_type = "🔵 GATED"

            desc = f"via {cname} · {time_text} · {cost}⚡ fuel · {travel_type}"
            options.append(discord.SelectOption(
                label=label,
                description=desc[:100],
                value=str(cid)
            ))

        select = ui.Select(placeholder="Choose your corridor", options=options, min_values=1, max_values=1)
        
        # This needs the same callback logic as the original travel_go - simplified version
        async def on_select(inter: discord.Interaction):
            if inter.user.id != interaction.user.id:
                return await inter.response.send_message("This isn't your travel menu!", ephemeral=True)

            # Get the choice they just made
            choice = int(select.values[0])
            corridor_data = None
            for c in corridors:
                if c[0] == choice:
                    corridor_data = c
                    break
            
            if not corridor_data:
                await inter.response.send_message("Corridor not found!", ephemeral=True)
                return
            
            cid, cname, dest_name, travel_time, cost, _ = corridor_data
            
            # Get ship efficiency and modify travel time
            ship_efficiency = self.bot.db.execute_query(
                "SELECT fuel_efficiency FROM ships WHERE owner_id = ?",
                (inter.user.id,), fetch='one'
            )
            
            if ship_efficiency:
                ship_eff = ship_efficiency[0]
                efficiency_modifier = 1.6 - (ship_eff * 0.08)
                actual_travel_time = max(int(travel_time * efficiency_modifier), 60)
                travel_time = actual_travel_time
            
            # Check fuel
            char_fuel = self.bot.db.execute_query(
                "SELECT s.current_fuel FROM characters c JOIN ships s ON c.active_ship_id = s.ship_id WHERE c.user_id = ?",
                (inter.user.id,), fetch='one'
            )
            
            if not char_fuel or char_fuel[0] < cost:
                await inter.response.send_message(
                    f"Insufficient fuel! Need {cost}, have {char_fuel[0] if char_fuel else 0}.", 
                    ephemeral=True
                )
                return

            # Deduct fuel
            self.bot.db.execute_query(
                "UPDATE ships SET current_fuel = current_fuel - ? WHERE owner_id = ?",
                (cost, inter.user.id)
            )

            # Create transit channel
            travel_cog = self.bot.get_cog('TravelCog')
            if not travel_cog:
                await inter.response.send_message("Travel system unavailable.", ephemeral=True)
                return
                
            transit_chan = await travel_cog.channel_mgr.create_transit_channel(
                inter.guild, inter.user, cname, dest_name
            )

            # Record the session
            start = datetime.utcnow()
            end = start + timedelta(seconds=travel_time)
            self.bot.db.execute_query(
                """
                INSERT INTO travel_sessions
                  (user_id, corridor_id, origin_location, destination_location,
                   start_time, end_time, temp_channel_id, status)
                VALUES (?, ?, ?, 
                        (SELECT destination_location FROM corridors WHERE corridor_id = ?),
                        ?, ?, ?, 'traveling')
                """,
                (inter.user.id, cid, origin_id, cid, start.isoformat(), end.isoformat(), transit_chan.id if transit_chan else None)
            )

            # Confirm departure
            mins, secs = divmod(travel_time, 60)
            hours = mins // 60
            mins = mins % 60
            
            if hours > 0:
                time_display = f"{hours}h {mins}m {secs}s"
            else:
                time_display = f"{mins}m {secs}s"
            
            await inter.response.edit_message(
                content=f"🚀 Departure confirmed after job cancellation. ETA: {time_display}",
                view=None
            )

            # Remove user from origin location immediately
            old_location = self.bot.db.execute_query(
                "SELECT current_location FROM characters WHERE user_id = ?",
                (inter.user.id,), fetch='one'
            )
            old_location_id = old_location[0] if old_location else None
            
            # Set character location to None (in transit)
            self.bot.db.execute_query(
                "UPDATE characters SET current_location = NULL WHERE user_id = ?",
                (inter.user.id,)
            )
            
            # Remove access from old location
            if old_location_id:
                await travel_cog.channel_mgr.update_channel_on_player_movement(
                    inter.guild, inter.user.id, old_location_id, None
                )

            # Start travel completion
            import asyncio
            asyncio.create_task(travel_cog._complete_travel_after_delay(
                inter.user.id, cid, travel_time, dest_name, transit_chan, inter.guild
            ))
        
        select.callback = on_select
        view = ui.View(timeout=60)
        view.add_item(select)
        await interaction.response.send_message("Jobs cancelled. Select your route to depart:", view=view, ephemeral=True)
        
async def setup(bot):
    await bot.add_cog(TravelCog(bot))