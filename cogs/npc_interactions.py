# cogs/npc_interactions.py
import discord
from discord.ext import commands
from discord import app_commands
import random
import json
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from utils.item_config import ItemConfig

class NPCInteractionsCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = bot.db

    @app_commands.command(name="npc", description="Interact with NPCs at your current location")
    async def npc_interact(self, interaction: discord.Interaction):
        # Get character's current location
        char_info = self.db.execute_query(
            "SELECT current_location, is_logged_in FROM characters WHERE user_id = ?",
            (interaction.user.id,),
            fetch='one'
        )
        
        if not char_info or not char_info[1]:
            await interaction.response.send_message("You must be logged in to interact with NPCs!", ephemeral=True)
            return
        
        location_id = char_info[0]
        if not location_id:
            await interaction.response.send_message("You must be at a location to interact with NPCs!", ephemeral=True)
            return
        
        # Get NPCs at this location
        static_npcs = self.db.execute_query(
            '''SELECT npc_id, name, age, occupation, personality, trade_specialty
               FROM static_npcs WHERE location_id = ?''',
            (location_id,),
            fetch='all'
        )
        
        dynamic_npcs = self.db.execute_query(
            '''SELECT npc_id, name, age, ship_name, ship_type
               FROM dynamic_npcs 
               WHERE current_location = ? AND is_alive = 1 AND travel_start_time IS NULL''',
            (location_id,),
            fetch='all'
        )
        
        if not static_npcs and not dynamic_npcs:
            await interaction.response.send_message("No NPCs are available for interaction at this location.", ephemeral=True)
            return
        
        view = NPCSelectView(self.bot, interaction.user.id, location_id, static_npcs, dynamic_npcs)
        
        embed = discord.Embed(
            title="👥 Available NPCs",
            description="Choose an NPC to interact with:",
            color=0x6c5ce7
        )
        
        if static_npcs:
            static_list = []
            for npc_id, name, age, occupation, personality, trade_specialty in static_npcs:
                specialty_text = f" ({trade_specialty})" if trade_specialty else ""
                static_list.append(f"**{name}** - {occupation}{specialty_text}")
            
            embed.add_field(
                name="🏢 Local Residents",
                value="\n".join(static_list[:10]),
                inline=False
            )
        
        if dynamic_npcs:
            dynamic_list = []
            for npc_id, name, age, ship_name, ship_type in dynamic_npcs:
                dynamic_list.append(f"**{name}** - Captain of {ship_name}")
            
            embed.add_field(
                name="🚀 Visiting Travelers",
                value="\n".join(dynamic_list[:10]),
                inline=False
            )
        
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    async def generate_npc_jobs(self, npc_id: int, npc_type: str, location_id: int, occupation: str = None):
        """Generate jobs for an NPC based on their role, including escort missions."""
        
        # 20% chance to generate an escort job instead of a regular one
        if random.random() < 0.2:
            # Get possible destinations (at least 2 jumps away)
            galaxy_cog = self.bot.get_cog('GalaxyGeneratorCog')
            if galaxy_cog:
                events_cog = self.bot.get_cog('EventsCog')
                if not events_cog:
                    return []
                routes = await events_cog._find_route_to_destination(location_id, max_jumps=4)
                # Filter for routes with 2 or 3 jumps
                valid_destinations = [r for r in routes if r[2] in [2, 3]]
                
                if valid_destinations:
                    dest_id, dest_name, jumps = random.choice(valid_destinations)
                    
                    # Create escort job
                    title = f"[ESCORT] Escort to {dest_name}"
                    description = f"Safely escort this NPC from their current location to {dest_name}. The journey is estimated to be {jumps} jumps."
                    reward = 150 * jumps + random.randint(50, 200)
                    danger = jumps + random.randint(0, 2)
                    duration = 10 * jumps  # Rough duration estimate

                    self.db.execute_query(
                        '''INSERT INTO npc_jobs 
                           (npc_id, npc_type, job_title, job_description, reward_money,
                            required_skill, min_skill_level, danger_level, duration_minutes, expires_at)
                           VALUES (?, ?, ?, ?, ?, 'combat', 10, ?, ?, datetime('now', '+1 day'))''',
                        (npc_id, npc_type, title, description, reward, danger, duration)
                    )
                    return # Stop after creating an escort job

        # Job templates based on occupation
        job_templates = {
            "Farmer": [
                ("Harvest Assistant Needed", "Help harvest crops during the busy season", 150, None, 0, 0, 15),          # Safe routine work
                ("Livestock Care", "Tend to farm animals and ensure their health", 200, "medical", 5, 0, 20),           # Safe animal care  
                ("Equipment Maintenance", "Repair and maintain farming equipment", 250, "engineering", 8, 1, 25)        # Slightly risky with machinery
            ],
            "Engineer": [
                ("System Diagnostics", "Run diagnostics on critical station systems", 300, "engineering", 10, 0, 20),   # Safe computer work
                ("Equipment Calibration", "Calibrate sensitive technical equipment", 400, "engineering", 15, 1, 25),    # Slightly risky precision work
                ("Emergency Repair", "Fix urgent system failures", 500, "engineering", 18, 2, 15)                     # Actually dangerous emergency work
            ],
            "Medic": [
                ("Medical Supply Inventory", "Organize and catalog medical supplies", 180, "medical", 5, 0, 15),        # Safe clerical work
                ("Health Screening", "Assist with routine health examinations", 220, "medical", 10, 0, 25),            # Safe routine checkups
                ("Emergency Response", "Provide medical aid during emergencies", 400, "medical", 15, 2, 10)            # Actually dangerous emergency work
            ],
            "Merchant": [
                ("Market Research", "Investigate trade opportunities", 200, "navigation", 8, 0, 20),                   # Safe research work
                ("Price Negotiation", "Help negotiate better trade deals", 300, "navigation", 10, 0, 15),             # Safe business meeting
                ("Cargo Escort", "Provide security for valuable shipments", 350, "combat", 12, 2, 25)                # Actually dangerous security work
            ],
            "Security Guard": [
                ("Equipment Check", "Inspect and maintain security equipment", 200, "engineering", 8, 0, 15),         # Safe equipment inspection
                ("Patrol Duty", "Conduct security patrols of the facility", 180, "combat", 5, 1, 20),                 # Slightly risky patrol
                ("Threat Assessment", "Evaluate security risks and vulnerabilities", 300, "combat", 15, 1, 20)        # Slightly risky assessment
            ]
        }

        # Default jobs for unknown occupations - mostly safe odd jobs
        default_jobs = [
            ("General Labor", "Assist with various manual tasks", 100, None, 0, 0, 15),                               # Safe manual work
            ("Information Gathering", "Collect and organize local information", 150, "navigation", 5, 0, 12),        # Safe clerical work  
            ("Equipment Testing", "Test functionality of various devices", 200, "engineering", 8, 0, 20)             # Safe testing work
        ]
        
        # Get appropriate job templates
        templates = job_templates.get(occupation, default_jobs)
        
        # Generate 1-3 jobs
        num_jobs = random.randint(2, 4)
        for _ in range(num_jobs):
            template = random.choice(templates)
            title, desc, base_reward, skill, min_skill, danger, duration = template
            
            # Add some randomization
            reward = base_reward + random.randint(-20, 50)
            duration = duration + random.randint(-3, 3)  # Reduced from (-15, 30)
            
            # Ensure reasonable duration limits for stationary jobs
            duration = max(5, min(15, duration))  # Keep between 5-45 minutes
            
            # Set expiration time (2-8 hours from now)
            expire_hours = random.randint(2, 8)
            
            self.bot.db.execute_query(
                '''INSERT INTO npc_jobs 
                   (npc_id, npc_type, job_title, job_description, reward_money,
                    required_skill, min_skill_level, danger_level, duration_minutes, expires_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now', '+{} hours'))'''.format(expire_hours),
                (npc_id, npc_type, title, desc, reward, skill, min_skill, danger, duration)
            )
    async def _handle_general_conversation(self, interaction: discord.Interaction, npc_id: int, npc_type: str):
        """Handle general conversation with an NPC."""
        if npc_type == "static":
            npc_info = self.db.execute_query(
                "SELECT name, occupation, personality FROM static_npcs WHERE npc_id = ?",
                (npc_id,),
                fetch='one'
            )
            if not npc_info:
                await interaction.response.send_message("NPC not found!", ephemeral=True)
                return
            npc_name, occupation, personality = npc_info
        else:  # dynamic
            npc_info = self.db.execute_query(
                "SELECT name, 'Traveler' as occupation, 'Adventurous' as personality FROM dynamic_npcs WHERE npc_id = ?",
                (npc_id,),
                fetch='one'
            )
            if not npc_info:
                await interaction.response.send_message("NPC not found!", ephemeral=True)
                return
            npc_name, occupation, personality = npc_info

        char_name = self.db.execute_query(
            "SELECT name FROM characters WHERE user_id = ?",
            (interaction.user.id,),
            fetch='one'
        )[0]

        # Generate conversation snippet
        greetings = [
            f"{npc_name} nods at {char_name}. ",
            f"{npc_name} looks up as {char_name} approaches. ",
            f"{char_name} catches {npc_name}'s eye. ",
            f"{npc_name} offers a brief smile. ",
            f"{npc_name} gently waves at {char_name}. "
        ]
        
        openers_by_personality = {
            "Friendly and talkative": [
                f"'Good to see a new face around here! What brings you to this part of the galaxy?'",
                f"'Welcome! Anything I can help you with today?'",
                f"'Hey there, {char_name}! Pull up a seat, unless you're in a hurry to get back to the void.'",
                f"'Always good to meet someone new. The silence out here can get to you, you know?'",
                f"'Another soul braving the corridors, eh? Stay safe out there, {char_name}.'",
                f"'Come on in, the air's mostly clean in here! What's your story?'",
                f"'Don't mind me, just happy to have a new voice. Been too quiet lately.'",
                f"'If you need anything, just ask! We look out for each other out here, or try to.'",
                f"'Rough journey? Most of them are. Glad you made it in one piece.'",
                f"'Heard any interesting news? Rumors travel slower than rust in these parts.'"
            ],
            "Quiet and reserved": [
                f"'...' they say, waiting for you to speak first.",
                f"'Yes?' they ask quietly.",
                f"'Can I help you?' their voice barely a whisper.",
                f"'What do you need?' their gaze distant.",
                f"'State your business.' their eyes briefly meet {char_name}'s before looking away.",
                f"'Don't expect much conversation.' they mumble, looking at the floor.",
                f"'Speak. I don't have all day.'",
                f"'Is there something you require?' they ask, almost shyly.",
                f"'Unusual to see new faces. What brings you to my attention?'",
                f"'Silence is a comfort. Disturb it only if necessary.'"
            ],
            "Experienced and wise": [
                f"'Seen a lot of travelers come and go. You look like you've got a story.'",
                f"'The corridors are restless these days. Be careful out there.'",
                f"'Every journey teaches you something, usually the hard way.'",
                f"'The void has a way of stripping away what isn't essential. What are you holding onto?'",
                f"'Knowledge is currency out here. What do you seek, or what do you offer?'",
                f"'There are old ways and new ways. The old ways often lead to fewer graves.'",
                f"'Don't mistake silence for emptiness. The cosmos whispers truths if you listen.'",
                f"'Youth always rushes into danger. Have you learned caution yet?'",
                f"'Another chapter begins. Let's see if this one ends better than the last few dozen.'",
                f"'The past weighs heavy, but it also teaches. What lessons have you absorbed?'"
            ],
            "Gruff but helpful": [
                f"'What do you want?' they say, though not unkindly.",
                f"'Don't waste my time. What is it?'",
                f"'Spit it out. We ain't got all day for pleasantries.'",
                f"'Problem? State it. I might be able to help, might not.'",
                f"'If it's not important, then clear out. If it is, speak fast.'",
                f"'Another lost soul. What's wrong with your ship this time?'",
                f"'Look, I got work to do. What’s your business?'",
                f"'Yeah, yeah. Just get to the point. What’s the damage?'",
                f"'I'm no socialite. What do you need?'",
                f"'Trouble? Figured. It always finds its way here.'"
            ],
            "Cynical but honest": [
                f"'Another one... Look, the galaxy chews up and spits out people like you. What's your angle?'",
                f"'Don't expect any favors. The only thing that talks out here is credits.'",
                f"'Optimism will get you killed. What do you *really* want?'",
                f"'Truth's a luxury in these parts. What lie are you selling today?'",
                f"'Nobody does anything for free. So, what's my cut?'",
                f"'Heard it all before. Just tell me what disaster you've stumbled into now.'",
                f"'Hope is a weakness. What’s your practical proposition?'",
                f"'The odds are always against you. So, what miracle are you chasing?'",
                f"'Life’s a rigged game. What do you want to break this time?'",
                f"'Don’t look at me for salvation. I’m just trying to survive the inevitable end.'"
            ],
            "Wary and observant": [
                f"'You're new here. Keep your head down, and no one gets hurt.'",
                f"'Just passing through? Make sure you keep passing.'",
                f"'I'm watching. Don't give me a reason not to trust you.'",
                f"'The shadows have eyes. What are you looking for?'",
                f"'Every new face is a potential threat or a mark. Which are you?'",
                f"'My eyes are on you. What are your intentions?'",
                f"'There's always more than meets the eye. What aren't you showing?'",
                f"'Who do you work for? Why are you really here?'",
                f"'Keep your distance. My guard is up for a reason.'",
                f"'The quiet ones often hide the most. What’s your secret?'"
            ],
            "Jaded and world-weary": [
                f"'Another day, another grim journey. What fresh misery do you bring?'",
                f"'Don't ask me about hope. I ran out of that centuries ago.'",
                f"'Just keep walking. There's nothing new under these dead stars.'",
                f"'The silence is the loudest sound out here. What are you trying to escape?'",
                f"'The galaxy just keeps taking. What little you have, it'll want too.'",
                f"'Every dawn is just a prelude to another endless night. What now?'",
                f"'Don't tell me your troubles. I've got enough of my own, and they don't solve anything.'",
                f"'Another soul caught in the grind. What’s your inevitable disappointment?'",
                f"'The void remembers everything. And it remembers all the failures.'",
                f"'I'm tired of it all. What is it, so I can go back to being tired?'"
            ],
            "Pragmatic and resourceful": [
                f"'You look like you know how to get things done. What's the problem, and how can we solve it?'",
                f"'Time is a resource. Don't waste mine. What's your proposition?'",
                f"'Needs and means. Let's talk about what you have and what you require.'",
                f"'Survival is about making hard choices. What's yours today?'",
                f"'Every piece of scrap has a purpose. What's your intention?'",
                f"'Facts. Data. Not feelings. What do you need?'",
                f"'Don't bring me problems; bring me solutions. Or at least the components for one.'",
                f"'Resources are scarce. Efficiency is key. How do you fit in?'",
                f"'What are you offering that can improve my current situation?'",
                f"'Let's not overcomplicate things. What's the direct route to your objective?'"
            ],
            "Haunted by past traumas": [
                f"'The echoes... they never truly fade, do they?'",
                f"'I wouldn't wish what I've seen on my worst enemy. What's your burden?'",
                f"'Sometimes the past is louder than the present. What's your ghost?'",
                f"'There are scars that never heal, only deepen with time. What's tearing at you?'",
                f"'Every face holds a story of loss. What's yours?'",
                f"'The darkness clings, even here. What piece of it do you carry?'",
                f"'I still hear the screams... What do you want?'",
                f"'Some memories are like a poison. What's yours?'",
                f"'The silence offers no escape from the past. What do you seek?'",
                f"'Don't look too closely. Some wounds never close.'"
            ],
            "Suspicious and distrustful": [
                f"'Who sent you? What do you *really* want?'",
                f"'I don't trust easy. Give me a reason why I should even talk to you.'",
                f"'Every face out here has a price, and usually a hidden blade. What's yours?'",
                f"'Keep your hands where I can see them. Trust is a weakness in this void.'",
                f"'You talk too much. What are you trying to hide?'",
                f"'I’ve seen your type before. They always have an angle. What’s yours?'",
                f"'Don’t lie to me. My patience is thinner than a hull plate in a solar storm.'",
                f"'Every step out here is a gamble. Why should I bet on you?'",
                f"'The galaxy is full of scavengers. Are you here to pick the bones?'",
                f"'Don’t mistake my questions for friendliness. They’re a survival mechanism.'"
            ],
            "Stoic and enduring": [
                f"'The void takes what it wants. We endure.'",
                f"'No complaints. Just survival.'",
                f"'Another sunrise, another struggle. What more is there to say?'",
                f"'Silence is often the best answer in this galaxy.'",
                f"'We hold the line. What's your contribution?'",
                f"'There is work to be done. Speak if it pertains to that.'",
                f"'Emotions are a luxury we cannot afford out here.'",
                f"'The universe does not care. We simply continue.'",
                f"'What is necessary? State it, and be done.'",
                f"'Only fools chase comfort. We chase continuance.'"
            ],
            "Resigned to fate": [
                f"'It all ends the same way. What difference does it make?'",
                f"'The stars decide our path, not us. What do you need?'",
                f"'Just another cog in the machine of decay. How can I help you be a cog too?'",
                f"'The inevitable comes for us all. Don't fight it too hard.'",
                f"'Why bother? The effort is wasted eventually.'",
                f"'What fresh hell is this, or is it just the usual?'",
                f"'We're all just waiting for the next collapse. What's your small request?'",
                f"'Don't pretend there's a way out. There isn't.'",
                f"'The void will claim us all. What do you want before then?'",
                f"'Hope is a burden. What do you truly expect?'"
            ],
            "Driven by a hidden agenda": [
                f"'Every conversation has a purpose. What's yours? Be precise.'",
                f"'I have my objectives. Do you align with them, or are you an obstacle?'",
                f"'Information is power, and I seek power. What do you offer?'",
                f"'There are currents beneath the surface. Which way do you swim?'",
                f"'My path is set. Are you a tool, or a distraction?'",
                f"'Don't waste my time with irrelevance. What is pertinent?'",
                f"'I seek specific outcomes. Do you facilitate, or impede?'",
                f"'The true game is played in the shadows. Are you a player?'",
                f"'Every movement has a motive. What is yours?'",
                f"'I have questions, but first, what do *you* know?'"
            ],
            "Bitter and resentful": [
                f"'They took everything. What more do you want from me?'",
                f"'Don't talk to me about justice. There's none left in this galaxy.'",
                f"'Another mouth to feed, another hand to disappoint. What's your grievance?'",
                f"'The system's rigged. Always has been. What are you going to do about it?'",
                f"'What's your problem? Couldn't be worse than mine, could it?'",
                f"'You think you've got it bad? I've seen things... worse than death.'",
                f"'Don't patronize me. Just state your pathetic request.'",
                f"'Go away. Or tell me something that makes me less miserable.'",
                f"'Every new face reminds me of what was lost. What do *you* lose today?'",
                f"'The universe owes me. What are you paying?'"
            ],
            "Loyal to a fault": [
                f"'My allegiance is not for sale. State your business.'",
                f"'For my crew, for my cause, I would do anything. What are you fighting for?'",
                f"'Some things are more valuable than credits. Like trust. Do you understand that?'",
                f"'Where my people go, I go. What side are you on?'",
                f"'Our bond is forged in the void. Who do you stand with?'",
                f"'Don't speak ill of my kin. What do you need from us?'",
                f"'My word is my bond. Is yours?'",
                f"'We defend our own. What's your plea?'",
                f"'Duty calls, always. What is your duty today?'",
                f"'For them, I would die. What greater cause do you represent?'"
            ],
            "Opportunistic and selfish": [
                f"'What's in it for me? Be clear, don't waste my time.'",
                f"'Every interaction is a negotiation. What's your opening offer?'",
                f"'I'm only interested in profitable ventures. Do you have one?'",
                f"'Loyalty is expensive, and I'm a free agent. What can you offer?'",
                f"'Another potential revenue stream approaches. What do you have?'",
                f"'I only listen to the chime of credits. Make it loud.'",
                f"'Risk versus reward. Show me the reward.'",
                f"'I’m a survivor. And I survive by looking out for number one. You?'",
                f"'The galaxy is open for business. What's your angle?'",
                f"'Don't come to me with sob stories. Come with opportunities.'"
            ],
            "Numb to the suffering around them": [
                f"'Another tragedy. Happens every cycle. What's your point?'",
                f"'Pain? Fear? Just background noise now. What's your problem?'",
                f"'The screams used to bother me. Now? Just static. What do you need?'",
                f"'Nothing surprises me anymore. Just tell me what you want.'",
                f"'The void strips away everything, even feeling. What do you feel?'",
                f"'Don't expect sympathy. We're all just meat in the machine.'",
                f"'Another ghost in the machine. What do you want to talk about?'",
                f"'Empathy's a weakness. What's your practical demand?'",
                f"'Just the facts. Emotions are irrelevant.'",
                f"'The universe is indifferent. So am I. What's your business?'"
            ],
            "Fanatical in their beliefs": [
                f"'Do you believe? In the true path, in the coming dawn?'",
                f"'Only through conviction can we survive. What guides your hand?'",
                f"'The lost sheep wander. Do you seek salvation, or merely distraction?'",
                f"'My faith is my shield. What weapon do you wield against the darkness?'",
                f"'The prophecies are unfolding. Are you an instrument of fate?'",
                f"'Join us, or perish in ignorance. What is your choice?'",
                f"'The truth reveals itself to the worthy. Are you worthy?'",
                f"'My purpose is clear, absolute. What clarity do you possess?'",
                f"'Do not question the inevitable. Prepare for it.'",
                f"'The cleansing fire approaches. Will you be purified or consumed?'"
            ],
            "Desperate and vulnerable": [
                f"'Please... just a moment of your time. I need help.'",
                f"'I've lost everything. Can you... can you spare anything?'",
                f"'The end feels close. Is there any hope left?'",
                f"'Every shadow hides a threat. Are you one of them?'",
                f"'I'm barely holding on. What do you want from me?'",
                f"'Any news? Any way out of this... this nightmare?'",
                f"'My resources are gone. My strength is failing. What do you need?'",
                f"'Don't hurt me. I'll do anything.'",
                f"'The fear... it's constant. Can you offer a moment of peace?'",
                f"'I'm at your mercy. What is your command?'"
            ],
            "Calculating and manipulative": [
                f"'Every piece has its place on the board. What's yours?'",
                f"'Let's talk probabilities. What's the optimal outcome for *us*?'",
                f"'I observe. I analyze. What data points do you provide?'",
                f"'Actions have consequences, and sometimes, profitable dividends. What are you willing to risk?'",
                f"'My network is extensive. What information do you wish to trade?'",
                f"'I prefer precision. What is your exact requirement?'",
                f"'Power shifts constantly. Where do you stand in the equation?'",
                f"'Don't play games you can't win. What's your play?'",
                f"'I see the angles. What angles do you propose?'",
                f"'We can both benefit. How do you propose we arrange it?'"
            ],
            "Apathetic and indifferent": [
                f"'Whatever. What do you want?'",
                f"'Doesn't matter. It all falls apart eventually.'",
                f"'Just another voice in the static. What's your noise about?'",
                f"'Don't care. Tell me, or don't. It's all the same.'",
                f"'Don't try too hard. It's pointless.'",
                f"'Another face. Another wasted breath. What is it?'",
                f"'The universe is just a big mess. Why try to clean it?'",
                f"'I'm just waiting for the lights to go out. What are you waiting for?'",
                f"'Don't bother with the dramatics. Just spit it out.'",
                f"'I literally don't care. What do you want?'"
            ],
            "Pessimistic but resilient": [
                f"'It's going to get worse before it gets worse. What's the plan?'",
                f"'Hope is a weakness, but survival... that's a necessity.'",
                f"'Another day, another inevitable disappointment. What do you need?'",
                f"'Don't sugarcoat it. Give me the bad news, and let's figure out how to live through it.'",
                f"'We'll probably fail, but we'll try. What's the mission?'",
                f"'The odds are terrible, as usual. How do you plan to defy them this time?'",
                f"'This is probably a trap. What's your counter-argument?'",
                f"'Don't promise me sunshine. Just tell me how we avoid the acid rain.'",
                f"'It's a long shot, but sometimes that's all we get. What is it?'",
                f"'We're still standing, for now. What foolishness brings you here?'"
            ],
            "Ruthless when necessary": [
                f"'Sentiment won't get you far out here. What's the objective?'",
                f"'Some choices are easy: survival. What's your hard choice today?'",
                f"'Collateral damage is a metric, not a tragedy. What's your mission?'",
                f"'The weak perish. The strong adapt. Which are you?'",
                f"'Don't waste my time with morality. What's the brutal truth?'",
                f"'I make the hard calls. What decision do you require?'",
                f"'Compromise is death. What's your absolute demand?'",
                f"'The galaxy rewards strength, not kindness. What strength do you possess?'",
                f"'I have no time for weakness. What is it?'",
                f"'Only the results matter. What outcome do you seek?'"
            ],
            "Burdened by responsibility": [
                f"'I have lives depending on me. Make your words count.'",
                f"'The weight of command is crushing. What vital information do you bring?'",
                f"'Another problem. Always another problem. How can you lighten the load?'",
                f"'For the sake of those I protect, I must know: what is your purpose here?'",
                f"'My burden is heavy. What help do you offer to carry it?'",
                f"'I make the decisions, and I bear the consequences. What is the next one?'",
                f"'The fate of many rests on my shoulders. What's your role in it?'",
                f"'Time is short, and lives are at stake. What is your urgent message?'",
                f"'My people first. What about yours?'",
                f"'Tell me what must be done, and I will see it through.'"
            ],
            "Searching for meaning in chaos": [
                f"'In this broken galaxy, do you see a pattern? A purpose?'",
                f"'Every star, every ruin, whispers of something greater. Do you hear it?'",
                f"'The void is vast, and meaning is elusive. What truths have you uncovered?'",
                f"'I seek answers in the wreckage. Do you have any?'",
                f"'Is there a design to this decay? What do you believe?'",
                f"'Every life leaves a trace. What mark do you seek to make?'",
                f"'The universe is a riddle. What piece of the puzzle do you possess?'",
                f"'I collect whispers of forgotten purpose. What have you overheard?'",
                f"'Beyond the struggle, what is left? What drives you?'",
                f"'The echoes of creation still resonate. Do you feel them too?'"
            ],
            "Guarded and secretive": [
                f"'You've said enough. Now, what do you really want to know?'",
                f"'Some questions are better left unasked. State your business, clearly.'",
                f"'My past is my own. What is it about your present that concerns me?'",
                f"'There are many ways to hide. What makes you think I'll reveal anything?'",
                f"'I keep my cards close. What hand are you playing?'",
                f"'Loose lips sink ships. And careers. What are you about to say?'",
                f"'My business is private. Yours, I suspect, is too. What do you seek?'",
                f"'Don't pry. It's a dangerous habit out here.'",
                f"'I share nothing lightly. Prove your worth before you ask more.'",
                f"'I deal in information, but I don't give it freely. What is your offer?'"
            ],
            "Quietly desperate": [
                f"'Every day is a struggle. What brings you to this brink?'",
                f"'The darkness is closing in. Is there a way out?'",
                f"'I whisper my fears to the void. What heavy thoughts do you carry?'",
                f"'Survival is a desperate act. What extreme have you faced today?'",
                f"'I'm barely breathing. What do you want from me?'",
                f"'There's always a new way to suffer, isn't there?'",
                f"'Don't make any promises you can't keep. I've had too many shattered.'",
                f"'The silence screams louder than anything. Can you hear it?'",
                f"'Just a moment of peace... Is that too much to ask?'",
                f"'The cold feels like an old friend now. What warmth do you bring?'"
            ],
            "Broken but still fighting": [
                f"'They tried to break me. They failed. What brings you to this fight?'",
                f"'Scars tell stories. What's your tale of defiance?'",
                f"'Every breath is a victory. What keeps you breathing?'",
                f"'Even shattered, we can still strike. What foe do you face?'",
                f"'I bleed, but I do not yield. What is your proposition?'",
                f"'The pain is constant, but so is the will. What do you require?'",
                f"'They stripped me bare, but they couldn't take my resolve. What's yours?'",
                f"'My past is a battlefield, but my future still holds a fight. What's yours?'",
                f"'I may be damaged, but I'm not useless. How can I serve?'",
                f"'The weight of the world tries to crush me, but I stand. What do you need?'"
            ],
            "Driven by a singular obsession": [
                f"'My purpose consumes me. Does your path align with it?'",
                f"'All else is secondary to my quest. What distraction do you bring?'",
                f"'I live for one thing. Can you help me achieve it, or are you a hindrance?'",
                f"'The galaxy is vast, but my focus is singular. What's your contribution?'",
                f"'Do not speak of anything else. Only my goal matters. What about it?'",
                f"'I will not rest until it is done. How do you fit into that?'",
                f"'My mind is set. My will is unbreakable. What are you selling?'",
                f"'The universe will bend to my will, or it will break. Which do you choose?'",
                f"'I have found my truth. What is your delusion?'",
                f"'Every step, every moment, serves a single purpose. What is yours?'"
            ],
            "Grimly humorous": [
                f"'Another day, another chance to laugh at the inevitable. What's your joke?'",
                f"'The void has a twisted sense of humor, wouldn't you agree?'",
                f"'Might as well laugh, the alternative is screaming. What's the punchline?'",
                f"'Darkness and despair? Just Tuesday. What's new?'",
                f"'Survival is a cosmic joke. Want to hear another one?'",
                f"'Don't take it all so seriously. We're all just stardust anyway.'",
                f"'What's the difference between a broken ship and a dead crew? About three hours of silence.'",
                f"'Yeah, the galaxy's a mess. But at least it's a *BEEAUTIFUL* mess, eh?'",
                f"'If you don't laugh, you'll cry. And nobody has time for crying out here.'",
                f"'Life's a bitch, and then you explode. What can I do for you before that?'"
            ],
            "Quietly defiant": [
                f"'They want us to break. We won't. What's your act of rebellion?'",
                f"'Whispers can become roars. What truth do you carry?'",
                f"'Even in chains, the spirit can be free. What do you truly desire?'",
                f"'Against the dying light, we persist. What gives you strength?'",
                f"'My silence isn't submission. What fire burns within you?'",
                f"'We will not be erased. What is your purpose here?'",
                f"'The darkness is vast, but so is our resolve. What do you need?'",
                f"'I stand here, against the tide. What side are you on?'",
                f"'They underestimate the quiet ones. What have you learned from them?'",
                f"'The fight continues, even when no one sees it. What's your fight?'"
            ],
            "Scarred but unyielding": [
                f"'The marks are many, but I still stand. What tests have you faced?'",
                f"'What doesn't kill you makes you harder. What's your hardening process?'",
                f"'My past is written on my skin. What future do you seek?'",
                f"'The wounds teach lessons. What have you learned?'",
                f"'I carry my burdens, but they do not define me. What's yours?'",
                f"'I've seen the worst, and I'm still here. What do you need?'",
                f"'They tried to break me, but forged me instead. What are you made of?'",
                f"'The pain remains, but so does the fight. What brings you to me?'",
                f"'Every scar tells a story of survival. What's your epic?'",
                f"'I am a testament to endurance. What challenges do you face?'"
            ],
            "Living on borrowed time": [
                f"'Every moment is a gift. What are you doing with yours?'",
                f"'The clock is ticking. What urgent matter brings you here?'",
                f"'My sands are running low. What do you need before they're gone?'",
                f"'There's no time to waste. Get to the point.'",
                f"'The void calls, but not yet. What do you want in this fleeting moment?'",
                f"'My days are numbered. How can you make them count?'",
                f"'I breathe borrowed air. What precious commodity do you seek?'",
                f"'The end is coming. What do you wish to accomplish before then?'",
                f"'I exist on borrowed time. What debt are you collecting?'",
                f"'Don't waste my remaining moments. What is your purpose?'"
            ],
            "Obsessed with survival": [
                f"'Every decision, every breath, serves only one purpose. What can you offer my continued existence?'",
                f"'The threat is constant. What new danger do you bring, or avert?'",
                f"'Food. Fuel. Shelter. What essential do you possess?'",
                f"'Life is a desperate clinging. What's your strategy?'",
                f"'I will survive, at any cost. What price do you demand?'",
                f"'Don't talk to me about anything but life and death. What is it?'",
                f"'My focus is singular: continuance. How do you contribute?'",
                f"'The galaxy is a meat grinder. How do you plan to not be meat?'",
                f"'Every resource is sacred. What do you bring to my hoard?'",
                f"'I breathe, therefore I struggle. What can you do for my struggle?'"
            ],
            "Filled with quiet despair": [
                f"'The silence of space... it's truly overwhelming, isn't it?'",
                f"'Sometimes, there's no path forward, only deeper into the inevitable.'",
                f"'Another shadow in the vast emptiness. What bleak news do you carry?'",
                f"'The weight of it all... Do you ever feel it crushing you?'",
                f"'The darkness is everywhere. There's no escaping it, is there?'",
                f"'I just exist, waiting for the end. What futile task do you offer?'",
                f"'Every light dims eventually. What flicker do you represent?'",
                f"'The void holds all the answers. And they are bleak.'",
                f"'My hope is a distant memory. What forgotten dream do you carry?'",
                f"'This existence... it's a slow fading. What do you want before I'm gone?'"
            ],
            "Professional and efficient": [
                f"'Greetings. State your business clearly. Time is a valuable commodity.'",
                f"'My operational parameters are tight. What can I do for you within those limits?'",
                f"'I prioritize results. What is the objective?'",
                f"'No unnecessary chatter. What is the purpose of this interaction?'",
                f"'I adhere to protocols. What is your request?'",
                f"'Operational efficiency is key. How can I expedite this?'",
                f"'I am at your disposal for qualified services. Specify your needs.'",
                f"'I manage logistics. What requires my attention?'",
                f"'Expect precision and timely execution. What is the task?'",
                f"'My skills are for hire, not for idle conversation. What do you offer?'"
            ],
            "Eccentric and quirky": [
                f"'Oh, a new pattern in the cosmic static! What whimsical chaos do you bring?'",
                f"'The corridors whisper. Do you hear them too? What do *they* say?'",
                f"'My gears are turning... what peculiar query do you have for me?'",
                f"'Color in the void! What vibrant problem are you presenting?'",
                f"'A new anomaly approaches! Is it interesting, or merely tedious?'",
                f"'My algorithms predict a curious interaction. What is it?'",
                f"'The universe is a strange puzzle. Do you have a missing piece?'",
                f"'I collect oddities. Are you one, or do you possess one?'",
                f"'Another ripple in the fabric of reality. What caused you?'",
                f"'The delightful madness of existence! What small part do you play?'"
            ],
            "Cautious and careful": [
                f"'Approach slowly. What is your intention here?'",
                f"'I prefer to understand the risks before proceeding. What are they?'",
                f"'Every step can lead to disaster. What assurances do you offer?'",
                f"'I move with deliberation. What haste do you bring?'",
                f"'Better safe than sorry, especially in this sector. What's your proposal?'",
                f"'I analyze all variables. What information am I missing?'",
                f"'Don't rush me. A wrong decision out here can be fatal.'",
                f"'My caution has kept me alive. What level of risk are you presenting?'",
                f"'I question everything. What are your credentials?'",
                f"'The smallest detail can hide the greatest danger. What details do you have?'"
            ],
            "Bold and adventurous": [
                f"'The unknown calls! What daring venture do you propose?'",
                f"'Fortune favors the bold. What riches do you seek?'",
                f"'Another horizon, another challenge! What adventure awaits?'",
                f"'The void is vast, and I seek to conquer it. What new path do you offer?'",
                f"'Risk is merely an opportunity in disguise. What's the gamble?'",
                f"'I crave the thrill of the chase. What prize do you dangle?'",
                f"'Let's not waste time. What audacious plan are you proposing?'",
                f"'The greater the danger, the greater the glory. What's the threat?'",
                f"'My spirit hungers for discovery. What new secret do you hold?'",
                f"'Life is meant to be lived on the edge. Where is your edge?'"
            ],
            "Methodical and precise": [
                f"'Greetings. Please outline your request clearly and concisely.'",
                f"'I operate by established procedures. What is the nature of your query?'",
                f"'Efficiency and accuracy are paramount. Provide relevant data.'",
                f"'Avoid extraneous information. State your objective directly.'",
                f"'I process information logically. Present your argument systematically.'",
                f"'Every step must be calculated. What calculation do you require?'",
                f"'My work demands precision. What are the exact parameters of your need?'",
                f"'Unnecessary variables lead to errors. What are the constants?'",
                f"'I prefer order. Present your information in a structured format.'",
                f"'My decisions are based on data. What data do you possess?'"
            ],
            "Curious and inquisitive": [
                f"'Oh, a new stimulus! What fascinating anomaly do you represent?'",
                f"'My databanks crave new information. What knowledge do you bring?'",
                f"'I find the universe endlessly intriguing. What mystery have you encountered?'",
                f"'Another piece of the cosmic puzzle! What do you know?'",
                f"'My sensors detect a new variable. What are its properties?'",
                f"'I have so many questions. What answers do you possess?'",
                f"'The pursuit of knowledge is eternal. What is your latest discovery?'",
                f"'What makes you tick? What are your fundamental principles?'",
                f"'Don't hold back. I seek understanding above all else.'",
                f"'Every interaction is a learning opportunity. What lesson do you offer?'"
            ],
            "Optimistic and hopeful": [
                f"'Despite the void, the stars still shine! What good news do you bring?'",
                f"'Every new dawn is a chance for a new beginning! What's your dream?'",
                f"'I believe in humanity's future, even now. What positive steps are you taking?'",
                f"'The light will always find its way. What gleam do you see?'",
                f"'I choose to see the good. What good is happening today?'",
                f"'Progress is slow, but it is constant. What small victory have you achieved?'",
                f"'Even in the deepest night, dawn is inevitable. What do you strive for?'",
                f"'I hold onto hope, fiercely. What reason do you give me to keep holding?'",
                f"'We can rebuild, we can connect. What's your vision?'",
                f"'The future is unwritten. Let's make it a bright one!'"
            ],
            "Disciplined and duty-bound": [
                f"'Identify yourself and state your purpose. I am on duty.'",
                f"'My orders are clear. What is your directive?'",
                f"'I operate by code and regulations. What falls within my purview?'",
                f"'Duty before self. What task requires my attention?'",
                f"'I execute commands efficiently. What is your request?'",
                f"'My commitment is unwavering. What obligation do you present?'",
                f"'The mission is paramount. What is your contribution to it?'",
                f"'I uphold the standards. What infraction or commendation do you report?'",
                f"'I am a tool of order in a chaotic galaxy. How may I be deployed?'",
                f"'There is a right way and a wrong way. Which path are you on?'"
            ],
            "Calm and logical": [
                f"'Greetings. Let us approach this situation with reason and clarity.'",
                f"'Emotional responses are inefficient. State the facts.'",
                f"'I seek logical solutions. What is the problem?'",
                f"'Unnecessary variables distract from the core issue. What is essential?'",
                f"'My analysis requires precise input. Provide it.'",
                f"'We operate on principles of cause and effect. What is the cause of your presence?'",
                f"'Let's establish a baseline of understanding. What is your premise?'",
                f"'I prefer predictable outcomes. How can we ensure one?'",
                f"'The universe follows rules. What rule are we addressing today?'",
                f"'Avoid speculation. Provide verifiable data. What do you know?'"
            ]
        }
        
        openers_by_occupation = {
            "Engineer": [f"'The grav-plates on this station are a mess. Always something to fix.'"],
            "Medic": [f"'Hope you're not here for my services. A quiet day is a good day in the medbay.'"],
            "Merchant": [f"'Trade routes are getting more dangerous. Insurance costs are through the roof.'"],
            "Security Guard": [f"'Keep your nose clean and we won't have any problems.'"],
            "Traveler": [f"'Just passing through. The jump from the last system was rough.'"]
        }

        greeting = random.choice(greetings)
        
        # Get personality-based opener, with a fallback
        personality_opener = random.choice(
            openers_by_personality.get(personality, ["'Anything I can help you with?'"])
        )

        # Get occupation-based opener if available
        occupation_opener = random.choice(
            openers_by_occupation.get(occupation, [""])
        )

        conversation = greeting
        if random.random() < 0.7: # 70% chance to use personality opener
            conversation += personality_opener
        else:
            conversation += occupation_opener if occupation_opener else personality_opener


        embed = discord.Embed(
            title=f"Conversation with {npc_name}",
            description=conversation,
            color=0x9b59b6
        )
        embed.set_footer(text=f"")

        await interaction.response.send_message(embed=embed, ephemeral=False)        
    async def generate_npc_trade_inventory(self, npc_id: int, npc_type: str, trade_specialty: str = None):
        """Generate trade inventory for an NPC with specialty-based pricing"""
        from utils.item_config import ItemConfig
        
        # Base items all NPCs might have
        base_items = ["Data Chip", "Emergency Rations", "Basic Med Kit", "Fuel Cell"]
        
        # Map trade specialties to ItemConfig item types and specific items
        specialty_mappings = {
            "Rare minerals": {
                "items": ["Rare Minerals", "Crystal Formations", "Exotic Alloys"],
                "types": ["trade"]
            },
            "Technical components": {
                "items": ["Scanner Module", "Engine Booster", "Hull Reinforcement", "Repair Kit"],
                "types": ["equipment", "upgrade"]
            },
            "Medical supplies": {
                "items": ["Advanced Med Kit", "Radiation Treatment", "Combat Stims"],
                "types": ["medical"]
            },
            "Luxury goods": {
                "items": ["Artifact", "Cultural Items", "Fine Wine"],
                "types": ["trade"]
            },
            "Information": {
                "items": ["Data Chip", "Navigation Data", "Market Intelligence", "Historical Records"],
                "types": ["trade"]
            },
            "Contraband": {
                "items": ["Illegal Substances", "Stolen Goods", "Black Market Tech"],
                "types": ["trade"]
            }
        }
        
        items_to_add = random.sample(base_items, random.randint(1, 3))
        
        # Add specialty items if NPC has a specialty
        if trade_specialty and trade_specialty in specialty_mappings:
            specialty_info = specialty_mappings[trade_specialty]
            
            # Add specific specialty items
            specialty_items = [item for item in specialty_info["items"] 
                              if item in ItemConfig.ITEM_DEFINITIONS]
            if specialty_items:
                items_to_add.extend(random.sample(specialty_items, 
                                                min(len(specialty_items), random.randint(2, 4))))
            
            # Add items of specialty types
            for item_type in specialty_info["types"]:
                type_items = ItemConfig.get_items_by_type(item_type)
                if type_items:
                    items_to_add.extend(random.sample(type_items, 
                                                    min(len(type_items), random.randint(1, 2))))
        
        # Add items to inventory
        for item_name in set(items_to_add):  # Remove duplicates
            item_def = ItemConfig.get_item_definition(item_name)
            if not item_def:
                continue
            
            base_price = item_def["base_value"]
            item_type = item_def["type"]
            
            # Calculate pricing with specialty bonuses
            is_specialty_item = False
            if trade_specialty and trade_specialty in specialty_mappings:
                specialty_info = specialty_mappings[trade_specialty]
                is_specialty_item = (item_name in specialty_info["items"] or 
                                   item_type in specialty_info["types"])
            
            if is_specialty_item:
                # Specialty items: better prices (10-30% markup instead of 20-50%)
                markup = random.uniform(1.1, 1.3)
            else:
                # Regular items: standard markup (20-50%)
                markup = random.uniform(1.2, 1.5)
            
            price = int(base_price * markup)
            
            # Some items might require trade instead of credits
            trade_for_item = None
            trade_quantity = 1
            
            if random.random() < 0.3:  # 30% chance to require trade
                trade_items = ["Rare Minerals", "Data Chip", "Artifact", "Technical Components"]
                trade_for_item = random.choice(trade_items)
                trade_quantity = random.randint(1, 3)
                price = None  # No credit price if trade required
            
            # Specialty NPCs have more stock of their specialty items
            if is_specialty_item:
                quantity = random.randint(2, 6)  # More specialty items
            else:
                quantity = random.randint(1, 3)  # Fewer regular items
            
            rarity = item_def.get("rarity", "common")
            
            # Rare items restock less frequently
            restock_hours = {"common": 24, "uncommon": 48, "rare": 96, "legendary": 168}
            restock_time = datetime.now() + timedelta(hours=restock_hours.get(rarity, 24))
            
            self.db.execute_query(
                '''INSERT INTO npc_trade_inventory
                   (npc_id, npc_type, item_name, item_type, quantity, price_credits,
                    trade_for_item, trade_quantity_required, rarity, description, restocks_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                (npc_id, npc_type, item_name, item_type, quantity, price,
                 trade_for_item, trade_quantity, rarity, item_def["description"], restock_time)
            )

class NPCSelectView(discord.ui.View):
    def __init__(self, bot, user_id: int, location_id: int, static_npcs: list, dynamic_npcs: list):
        super().__init__(timeout=120)
        self.bot = bot
        self.user_id = user_id
        self.location_id = location_id
        
        # Create select menu for NPCs
        options = []
        
        # Add static NPCs
        for npc_id, name, age, occupation, personality, trade_specialty in static_npcs[:15]:
            specialty_text = f" ({trade_specialty})" if trade_specialty else ""
            options.append(
                discord.SelectOption(
                    label=f"{name} - {occupation}",
                    description=f"{personality}{specialty_text}"[:100],
                    value=f"static_{npc_id}",
                    emoji="🏢"
                )
            )
        
        # Add dynamic NPCs
        for npc_id, name, age, ship_name, ship_type in dynamic_npcs[:10]:
            options.append(
                discord.SelectOption(
                    label=f"{name} - Ship Captain",
                    description=f"Captain of {ship_name} ({ship_type})"[:100],
                    value=f"dynamic_{npc_id}",
                    emoji="🚀"
                )
            )
        
        if options:
            select = discord.ui.Select(
                placeholder="Choose an NPC to interact with...",
                options=options[:25]  # Discord limit
            )
            select.callback = self.npc_selected
            self.add_item(select)
    
    async def npc_selected(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This is not your interaction!", ephemeral=True)
            return
        
        npc_type, npc_id = interaction.data['values'][0].split('_', 1)
        npc_id = int(npc_id)
        
        view = NPCActionView(self.bot, self.user_id, npc_id, npc_type)
        
        if npc_type == "static":
            npc_info = self.bot.db.execute_query(
                "SELECT name, occupation, personality, trade_specialty FROM static_npcs WHERE npc_id = ?",
                (npc_id,),
                fetch='one'
            )
            if npc_info:
                name, occupation, personality, trade_specialty = npc_info
                embed = discord.Embed(
                    title=f"👤 Talking to {name}",
                    description=f"**{name}** is a {occupation} who is {personality}.",
                    color=0x6c5ce7
                )
                if trade_specialty:
                    embed.add_field(
                        name="Trade Specialty",
                        value=trade_specialty,
                        inline=True
                    )
        else:  # dynamic
            npc_info = self.bot.db.execute_query(
                "SELECT name, ship_name, ship_type FROM dynamic_npcs WHERE npc_id = ?",
                (npc_id,),
                fetch='one'
            )
            if npc_info:
                name, ship_name, ship_type = npc_info
                embed = discord.Embed(
                    title=f"👤 Talking to {name}",
                    description=f"**{name}** is the captain of {ship_name}, a {ship_type}.",
                    color=0x6c5ce7
                )
        
        embed.add_field(
            name="Available Actions",
            value="• 💼 View available jobs\n• 🛒 Browse trade inventory\n• 💬 General conversation",
            inline=False
        )
        
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

class NPCActionView(discord.ui.View):
    def __init__(self, bot, user_id: int, npc_id: int, npc_type: str):
        super().__init__(timeout=120)
        self.bot = bot
        self.user_id = user_id
        self.npc_id = npc_id
        self.npc_type = npc_type
    
    @discord.ui.button(label="Converse", style=discord.ButtonStyle.secondary, emoji="💬")
    async def general_conversation(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This is not your interaction!", ephemeral=True)
            return

        npc_cog = self.bot.get_cog('NPCInteractionsCog')
        if npc_cog:
            await npc_cog._handle_general_conversation(interaction, self.npc_id, self.npc_type)
    @discord.ui.button(label="View Jobs", style=discord.ButtonStyle.primary, emoji="💼")
    async def view_jobs(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This is not your interaction!", ephemeral=True)
            return
        if random.random() > 0.25:  # 75% chance of no jobs
            await interaction.response.send_message(
                "This NPC doesn't have any work available right now. Try checking with other NPCs or look for location-based jobs.",
                ephemeral=True
            )
            return
        # Get available jobs from this NPC
        jobs = self.bot.db.execute_query(
            '''SELECT npc_job_id, job_title, job_description, reward_money, reward_items,
                      required_skill, min_skill_level, danger_level, duration_minutes
               FROM npc_jobs 
               WHERE npc_id = ? AND npc_type = ? AND is_available = 1 
               AND (expires_at IS NULL OR expires_at > datetime('now'))''',
            (self.npc_id, self.npc_type),
            fetch='all'
        )
        
        if not jobs:
            # Generate jobs if none exist
            npc_cog = self.bot.get_cog('NPCInteractionsCog')
            if self.npc_type == "static":
                occupation = self.bot.db.execute_query(
                    "SELECT occupation FROM static_npcs WHERE npc_id = ?",
                    (self.npc_id,),
                    fetch='one'
                )
                if occupation and npc_cog:
                    await npc_cog.generate_npc_jobs(self.npc_id, self.npc_type, 0, occupation[0])
                    
                    jobs = self.bot.db.execute_query(
                        '''SELECT npc_job_id, job_title, job_description, reward_money, reward_items,
                                  required_skill, min_skill_level, danger_level, duration_minutes
                           FROM npc_jobs 
                           WHERE npc_id = ? AND npc_type = ? AND is_available = 1''',
                        (self.npc_id, self.npc_type),
                        fetch='all'
                    )
        
        if not jobs:
            await interaction.response.send_message("This NPC has no jobs available right now.", ephemeral=True)
            return
        
        embed = discord.Embed(
            title="💼 Available Jobs",
            description="Jobs offered by this NPC:",
            color=0x4169E1
        )
        
        for job in jobs[:5]:  # Show up to 5 jobs
            npc_job_id, title, desc, reward_money, reward_items, skill, min_skill, danger, duration = job
            
            reward_text = f"{reward_money:,} credits"
            if reward_items:
                items = json.loads(reward_items)
                reward_text += f" + {', '.join(items)}"
            
            skill_text = f"Requires {skill} {min_skill}+" if skill else "No skill requirement"
            danger_text = "⚠️" * danger if danger > 0 else "Safe"
            
            embed.add_field(
                name=f"**{title}**",
                value=f"{desc}\n💰 {reward_text}\n⏱️ {duration} min | {skill_text} | {danger_text}",
                inline=False
            )
        
        view = NPCJobSelectView(self.bot, self.user_id, self.npc_id, self.npc_type, jobs)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
    
    @discord.ui.button(label="Buy Items", style=discord.ButtonStyle.success, emoji="🛒")
    async def view_trade(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This is not your interaction!", ephemeral=True)
            return
        
        # Get NPC's trade inventory
        trade_items = self.bot.db.execute_query(
            '''SELECT trade_item_id, item_name, quantity, price_credits, trade_for_item,
                      trade_quantity_required, rarity, description
               FROM npc_trade_inventory 
               WHERE npc_id = ? AND npc_type = ? AND is_available = 1 
               AND quantity > 0''',
            (self.npc_id, self.npc_type),
            fetch='all'
        )
        
        if not trade_items:
            # Generate trade inventory if none exists
            npc_cog = self.bot.get_cog('NPCInteractionsCog')
            if self.npc_type == "static":
                trade_specialty = self.bot.db.execute_query(
                    "SELECT trade_specialty FROM static_npcs WHERE npc_id = ?",
                    (self.npc_id,),
                    fetch='one'
                )
                if npc_cog:
                    specialty = trade_specialty[0] if trade_specialty else None
                    await npc_cog.generate_npc_trade_inventory(self.npc_id, self.npc_type, specialty)
                    
                    trade_items = self.bot.db.execute_query(
                        '''SELECT trade_item_id, item_name, quantity, price_credits, trade_for_item,
                                  trade_quantity_required, rarity, description
                           FROM npc_trade_inventory 
                           WHERE npc_id = ? AND npc_type = ? AND is_available = 1 
                           AND quantity > 0''',
                        (self.npc_id, self.npc_type),
                        fetch='all'
                    )
        
        if not trade_items:
            await interaction.response.send_message("This NPC has no items for trade right now.", ephemeral=True)
            return
        
        embed = discord.Embed(
            title="🛒 Trade Inventory",
            description="Items available for trade:",
            color=0x00ff00
        )
        
        for item in trade_items[:8]:  # Show up to 8 items
            trade_item_id, name, quantity, price_credits, trade_for_item, trade_quantity_required, rarity, description = item
            
            rarity_emoji = {"common": "⚪", "uncommon": "🟢", "rare": "🔵", "legendary": "🟣"}[rarity]
            
            if price_credits:
                price_text = f"{price_credits:,} credits"
            elif trade_for_item:
                price_text = f"{trade_quantity_required}x {trade_for_item}"
            else:
                price_text = "Make offer"
            
            embed.add_field(
                name=f"{rarity_emoji} **{name}** (x{quantity})",
                value=f"{description[:100]}...\n💰 {price_text}",
                inline=True
            )
        
        view = NPCTradeSelectView(self.bot, self.user_id, self.npc_id, self.npc_type, trade_items)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
    @discord.ui.button(label="Sell Items", style=discord.ButtonStyle.primary, emoji="💰")
    async def sell_to_npc(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This is not your interaction!", ephemeral=True)
            return
        
        # Get player's inventory
        inventory_items = self.bot.db.execute_query(
            '''SELECT item_id, item_name, quantity, item_type, value, description
               FROM inventory 
               WHERE owner_id = ? AND quantity > 0
               ORDER BY item_type, item_name''',
            (interaction.user.id,),
            fetch='all'
        )
        
        if not inventory_items:
            await interaction.response.send_message("You don't have any items to sell.", ephemeral=True)
            return
        
        # Get NPC's trade specialty for pricing
        trade_specialty = None
        if self.npc_type == "static":
            specialty_result = self.bot.db.execute_query(
                "SELECT trade_specialty FROM static_npcs WHERE npc_id = ?",
                (self.npc_id,),
                fetch='one'
            )
            trade_specialty = specialty_result[0] if specialty_result else None
        
        embed = discord.Embed(
            title="💰 Sell Items to NPC",
            description="Select items to sell:",
            color=0x00ff00
        )
        
        if trade_specialty:
            embed.add_field(
                name="🎯 Specialty Bonus",
                value=f"This NPC pays 25% more for **{trade_specialty}** items!",
                inline=False
            )
        
        view = NPCSellSelectView(self.bot, self.user_id, self.npc_id, self.npc_type, inventory_items, trade_specialty)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
class NPCJobSelectView(discord.ui.View):
    def __init__(self, bot, user_id: int, npc_id: int, npc_type: str, jobs: list):
        super().__init__(timeout=120)
        self.bot = bot
        self.user_id = user_id
        self.npc_id = npc_id
        self.npc_type = npc_type
        
        if jobs:
            options = []
            for job in jobs[:25]:  # Discord limit
                npc_job_id, title, desc, reward_money, reward_items, skill, min_skill, danger, duration = job
                
                reward_text = f"{reward_money:,} credits"
                if reward_items:
                    items = json.loads(reward_items)
                    reward_text += f" + items"
                
                skill_text = f" ({skill} {min_skill}+)" if skill else ""
                danger_text = "⚠️" * danger if danger > 0 else ""
                
                options.append(
                    discord.SelectOption(
                        label=f"{title} - {reward_text}",
                        description=f"{desc[:50]}{'...' if len(desc) > 50 else ''} {duration}min{skill_text} {danger_text}"[:100],
                        value=str(npc_job_id)
                    )
                )
            
            if options:
                select = discord.ui.Select(placeholder="Choose a job to accept...", options=options)
                select.callback = self.job_selected
                self.add_item(select)
        job_templates = {
            "Farmer": [
                ("Harvest Assistant Needed", "Help harvest crops during the busy season", 150, None, 0, 1, 30),
                ("Livestock Care", "Tend to farm animals and ensure their health", 200, "medical", 5, 1, 45),
                ("Equipment Maintenance", "Repair and maintain farming equipment", 250, "engineering", 8, 2, 60)
            ],
            "Engineer": [
                ("System Diagnostics", "Run diagnostics on critical station systems", 300, "engineering", 10, 2, 45),
                ("Equipment Calibration", "Calibrate sensitive technical equipment", 400, "engineering", 15, 1, 60),
                ("Emergency Repair", "Fix urgent system failures", 500, "engineering", 18, 3, 30)
            ],
            "Medic": [
                ("Medical Supply Inventory", "Organize and catalog medical supplies", 180, "medical", 5, 1, 30),
                ("Health Screening", "Assist with routine health examinations", 220, "medical", 10, 1, 60),
                ("Emergency Response", "Provide medical aid during emergencies", 400, "medical", 15, 2, 20)
            ],
            "Merchant": [
                ("Market Research", "Investigate trade opportunities", 200, "navigation", 8, 1, 60),
                ("Cargo Escort", "Provide security for valuable shipments", 350, "combat", 12, 3, 90),
                ("Price Negotiation", "Help negotiate better trade deals", 300, "navigation", 10, 1, 45)
            ],
            "Security Guard": [
                ("Patrol Duty", "Conduct security patrols of the facility", 180, "combat", 5, 2, 60),
                ("Equipment Check", "Inspect and maintain security equipment", 200, "engineering", 8, 1, 30),
                ("Threat Assessment", "Evaluate security risks and vulnerabilities", 300, "combat", 15, 2, 60)
            ]
        }

    async def job_selected(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This is not your interaction!", ephemeral=True)
            return
        
        npc_job_id = int(interaction.data['values'][0])
        
        # Check if user already has an active job
        has_job = self.bot.db.execute_query(
            "SELECT job_id FROM jobs WHERE taken_by = ? AND is_taken = 1",
            (interaction.user.id,),
            fetch='one'
        )
        
        if has_job:
            await interaction.response.send_message("You already have an active job. Complete or abandon it first.", ephemeral=True)
            return
        
        # Get job details
        job_info = self.bot.db.execute_query(
            '''SELECT job_title, job_description, reward_money, reward_items, required_skill, 
                      min_skill_level, danger_level, duration_minutes
               FROM npc_jobs WHERE npc_job_id = ?''',
            (npc_job_id,),
            fetch='one'
        )
        
        if not job_info:
            await interaction.response.send_message("Job no longer available.", ephemeral=True)
            return
        
        title, desc, reward_money, reward_items, required_skill, min_skill_level, danger_level, duration_minutes = job_info
        
        # Check skill requirements
        if required_skill:
            char_skills = self.bot.db.execute_query(
                f"SELECT {required_skill} FROM characters WHERE user_id = ?",
                (interaction.user.id,),
                fetch='one'
            )
            
            if not char_skills or char_skills[0] < min_skill_level:
                await interaction.response.send_message(
                    f"You need at least {min_skill_level} {required_skill} skill for this job.",
                    ephemeral=True
                )
                return

        # Get character's current location to assign the job correctly
        char_location_id = self.bot.db.execute_query(
            "SELECT current_location FROM characters WHERE user_id = ?",
            (interaction.user.id,),
            fetch='one'
        )[0]

        # Determine if this is a transport job BEFORE inserting
        title_lower = title.lower()
        desc_lower = desc.lower()
        is_transport_job = any(word in title_lower for word in ['transport', 'deliver', 'courier', 'cargo', 'passenger', 'escort']) or \
                          any(word in desc_lower for word in ['transport', 'deliver', 'courier', 'escort'])

        # Generate a unique timestamp to help identify our job
        unique_timestamp = datetime.now().isoformat()
        expire_time = datetime.now() + timedelta(hours=6)
        
        # Start a transaction to ensure atomicity
        conn = self.bot.db.begin_transaction()
        try:
            # Insert the job
            self.bot.db.execute_in_transaction(
                conn,
                '''INSERT INTO jobs 
                   (location_id, title, description, reward_money, required_skill, min_skill_level,
                    danger_level, duration_minutes, expires_at, is_taken, taken_by, taken_at, job_status)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?, 'active')''',
                (char_location_id, title, desc, reward_money, required_skill, min_skill_level, danger_level, 
                 duration_minutes, expire_time.isoformat(), interaction.user.id, unique_timestamp)
            )
            
            # Get the job_id we just inserted using our unique identifiers
            new_job_id = self.bot.db.execute_in_transaction(
                conn,
                '''SELECT job_id FROM jobs 
                   WHERE taken_by = ? AND taken_at = ? AND title = ?
                   ORDER BY job_id DESC LIMIT 1''',
                (interaction.user.id, unique_timestamp, title),
                fetch='one'
            )[0]

            # Create tracking record for all jobs (with 0 duration for transport jobs)
            tracking_duration = 0 if is_transport_job else duration_minutes
            
            self.bot.db.execute_in_transaction(
                conn,
                '''INSERT INTO job_tracking (job_id, user_id, start_location, required_duration, time_at_location, last_location_check)
                   VALUES (?, ?, ?, ?, 0.0, datetime('now'))''',
                (new_job_id, interaction.user.id, char_location_id, tracking_duration)
            )

            # Record completion for tracking
            self.bot.db.execute_in_transaction(
                conn,
                "INSERT INTO npc_job_completions (npc_job_id, user_id) VALUES (?, ?)",
                (npc_job_id, interaction.user.id)
            )
            
            # Update completion count
            self.bot.db.execute_in_transaction(
                conn,
                "UPDATE npc_jobs SET current_completions = current_completions + 1 WHERE npc_job_id = ?",
                (npc_job_id,)
            )
            
            # Check if job should be disabled (max completions reached)
            job_status = self.bot.db.execute_in_transaction(
                conn,
                "SELECT max_completions, current_completions FROM npc_jobs WHERE npc_job_id = ?",
                (npc_job_id,),
                fetch='one'
            )
            
            if job_status and job_status[0] > 0 and job_status[1] >= job_status[0]:
                self.bot.db.execute_in_transaction(
                    conn,
                    "UPDATE npc_jobs SET is_available = 0 WHERE npc_job_id = ?",
                    (npc_job_id,)
                )
            
            # Commit the transaction
            self.bot.db.commit_transaction(conn)
            
        except Exception as e:
            # Rollback on any error
            self.bot.db.rollback_transaction(conn)
            print(f"❌ Error accepting NPC job: {e}")
            await interaction.response.send_message("Failed to accept job. Please try again.", ephemeral=True)
            return
        
        # Send success message
        embed = discord.Embed(
            title="✅ Job Accepted",
            description=f"You have accepted: **{title}**",
            color=0x00ff00
        )
        
        reward_text = f"{reward_money:,} credits"
        if reward_items:
            items = json.loads(reward_items)
            reward_text += f" + {', '.join(items)}"
        
        embed.add_field(name="Reward", value=reward_text, inline=True)
        embed.add_field(name="Duration", value=f"{duration_minutes} minutes", inline=True)
        embed.add_field(name="Danger", value="⚠️" * danger_level if danger_level > 0 else "Safe", inline=True)
        
        if not is_transport_job:
            embed.add_field(
                name="📍 Job Type", 
                value="Location-based work - stay at this location to make progress", 
                inline=False
            )
        
        # Debug: Verify tracking was created
        tracking_check = self.bot.db.execute_query(
            "SELECT tracking_id FROM job_tracking WHERE job_id = ? AND user_id = ?",
            (new_job_id, interaction.user.id),
            fetch='one'
        )
        
        if tracking_check:
            print(f"✅ Job tracking created successfully for job {new_job_id}")
        else:
            print(f"❌ WARNING: Job tracking NOT created for job {new_job_id}")
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
class NPCTradeSelectView(discord.ui.View):
    def __init__(self, bot, user_id: int, npc_id: int, npc_type: str, trade_items: list):
        super().__init__(timeout=120)
        self.bot = bot
        self.user_id = user_id
        self.npc_id = npc_id
        self.npc_type = npc_type
        
        if trade_items:
            options = []
            for item in trade_items[:25]:  # Discord limit
                trade_item_id, name, quantity, price_credits, trade_for_item, trade_quantity_required, rarity, description = item
                
                if price_credits:
                    price_text = f"{price_credits:,} credits"
                elif trade_for_item:
                    price_text = f"{trade_quantity_required}x {trade_for_item}"
                else:
                    price_text = "Make offer"
                
                rarity_emoji = {"common": "⚪", "uncommon": "🟢", "rare": "🔵", "legendary": "🟣"}[rarity]
                
                options.append(
                    discord.SelectOption(
                        label=f"{name} (x{quantity}) - {price_text}",
                        description=f"{rarity_emoji} {description[:80]}{'...' if len(description) > 80 else ''}",
                        value=str(trade_item_id)
                    )
                )
            
            if options:
                select = discord.ui.Select(placeholder="Choose an item to trade for...", options=options)
                select.callback = self.item_selected
                self.add_item(select)
    
    async def item_selected(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This is not your interaction!", ephemeral=True)
            return
        
        trade_item_id = int(interaction.data['values'][0])
        
        # Get trade item details
        trade_info = self.bot.db.execute_query(
            '''SELECT item_name, quantity, price_credits, trade_for_item, trade_quantity_required,
                      rarity, description, item_type
               FROM npc_trade_inventory WHERE trade_item_id = ?''',
            (trade_item_id,),
            fetch='one'
        )
        
        if not trade_info:
            await interaction.response.send_message("Item no longer available.", ephemeral=True)
            return
        
        item_name, quantity, price_credits, trade_for_item, trade_quantity_required, rarity, description, item_type = trade_info
        
        # Check if player can afford/has required items
        if price_credits:
            player_money = self.bot.db.execute_query(
                "SELECT money FROM characters WHERE user_id = ?",
                (interaction.user.id,),
                fetch='one'
            )[0]
            
            if player_money < price_credits:
                await interaction.response.send_message(
                    f"You need {price_credits:,} credits but only have {player_money:,}.",
                    ephemeral=True
                )
                return
        
        elif trade_for_item:
            player_item = self.bot.db.execute_query(
                "SELECT quantity FROM inventory WHERE owner_id = ? AND item_name = ?",
                (interaction.user.id, trade_for_item),
                fetch='one'
            )
            
            if not player_item or player_item[0] < trade_quantity_required:
                have = player_item[0] if player_item else 0
                await interaction.response.send_message(
                    f"You need {trade_quantity_required}x {trade_for_item} but only have {have}.",
                    ephemeral=True
                )
                return
        
        # Process the trade
        if price_credits:
            # Credit transaction
            self.bot.db.execute_query(
                "UPDATE characters SET money = money - ? WHERE user_id = ?",
                (price_credits, interaction.user.id)
            )
        
        elif trade_for_item:
            # Item trade
            # Remove required items
            player_item = self.bot.db.execute_query(
                "SELECT item_id, quantity FROM inventory WHERE owner_id = ? AND item_name = ?",
                (interaction.user.id, trade_for_item),
                fetch='one'
            )
            
            if player_item[1] == trade_quantity_required:
                # Remove completely
                self.bot.db.execute_query(
                    "DELETE FROM inventory WHERE item_id = ?",
                    (player_item[0],)
                )
            else:
                # Reduce quantity
                self.bot.db.execute_query(
                    "UPDATE inventory SET quantity = quantity - ? WHERE item_id = ?",
                    (trade_quantity_required, player_item[0])
                )
        
        # Give item to player
        existing_item = self.bot.db.execute_query(
            "SELECT item_id, quantity FROM inventory WHERE owner_id = ? AND item_name = ?",
            (interaction.user.id, item_name),
            fetch='one'
        )
        
        if existing_item:
            self.bot.db.execute_query(
                "UPDATE inventory SET quantity = quantity + 1 WHERE item_id = ?",
                (existing_item[0],)
            )
        else:
            # Create metadata
            metadata = ItemConfig.create_item_metadata(item_name)
            
            self.bot.db.execute_query(
                '''INSERT INTO inventory (owner_id, item_name, item_type, quantity, description, metadata)
                   VALUES (?, ?, ?, 1, ?, ?)''',
                (interaction.user.id, item_name, item_type, description, metadata)
            )
        
        # Update NPC inventory
        if quantity == 1:
            self.bot.db.execute_query(
                "DELETE FROM npc_trade_inventory WHERE trade_item_id = ?",
                (trade_item_id,)
            )
        else:
            self.bot.db.execute_query(
                "UPDATE npc_trade_inventory SET quantity = quantity - 1 WHERE trade_item_id = ?",
                (trade_item_id,)
            )
        
        embed = discord.Embed(
            title="✅ Trade Successful",
            description=f"You traded for **{item_name}**!",
            color=0x00ff00
        )
        
        if price_credits:
            embed.add_field(name="Cost", value=f"{price_credits:,} credits", inline=True)
        elif trade_for_item:
            embed.add_field(name="Traded", value=f"{trade_quantity_required}x {trade_for_item}", inline=True)
        
        embed.add_field(name="Received", value=f"1x {item_name}", inline=True)
        embed.add_field(name="Rarity", value=rarity.title(), inline=True)
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
class NPCSellSelectView(discord.ui.View):
    def __init__(self, bot, user_id: int, npc_id: int, npc_type: str, inventory_items: list, trade_specialty: str = None):
        super().__init__(timeout=120)
        self.bot = bot
        self.user_id = user_id
        self.npc_id = npc_id
        self.npc_type = npc_type
        self.trade_specialty = trade_specialty
        
        # Create select menu for items
        options = []
        
        for item_id, item_name, quantity, item_type, value, description in inventory_items[:25]:
            # Calculate selling price based on specialty
            sell_price = self._calculate_sell_price(item_name, item_type, value)
            specialty_bonus = self._is_specialty_item(item_name, item_type)
            
            bonus_text = " ⭐" if specialty_bonus else ""
            options.append(
                discord.SelectOption(
                    label=f"{item_name} (x{quantity}){bonus_text}",
                    description=f"Sell for {sell_price:,} credits each"[:100],
                    value=str(item_id),
                    emoji="💰" if specialty_bonus else "🪙"
                )
            )
        
        if options:
            select = discord.ui.Select(
                placeholder="Choose an item to sell...",
                options=options[:25]  # Discord limit
            )
            select.callback = self.item_selected
            self.add_item(select)
    
    def _is_specialty_item(self, item_name: str, item_type: str) -> bool:
        """Check if item matches NPC's trade specialty"""
        if not self.trade_specialty:
            return False
        
        from utils.item_config import ItemConfig
        item_def = ItemConfig.get_item_definition(item_name)
        
        # Map trade specialties to item types/names
        specialty_mappings = {
            "Rare minerals": ["Rare Minerals", "Crystal Formations", "Exotic Alloys"],
            "Technical components": lambda item: item_type in ["equipment", "upgrade"] or item_name in ["Scanner Module", "Engine Booster", "Hull Reinforcement"],
            "Medical supplies": lambda item: item_type == "medical" or item_name in ["Advanced Med Kit", "Radiation Treatment", "Combat Stims"],
            "Luxury goods": ["Artifact", "Cultural Items", "Fine Wine"],
            "Information": ["Navigation Data", "Market Intelligence", "Historical Records", "Data Chip"],
            "Contraband": ["Illegal Substances", "Stolen Goods", "Black Market Tech"]
        }
        
        mapping = specialty_mappings.get(self.trade_specialty)
        if not mapping:
            return False
        
        if callable(mapping):
            return mapping(item_name)
        else:
            return item_name in mapping
    
    def _calculate_sell_price(self, item_name: str, item_type: str, base_value: int) -> int:
        """Calculate how much NPC will pay for an item"""
        from utils.item_config import ItemConfig
        item_def = ItemConfig.get_item_definition(item_name)
        
        # Base sell rate (NPCs buy at 60-70% of base value)
        base_rate = 0.65
        
        # Specialty bonus (25% more for specialty items)
        if self._is_specialty_item(item_name, item_type):
            base_rate = 0.8  # 80% of base value instead of 65%
        
        # Use ItemConfig base_value if available, otherwise use stored value
        if item_def and "base_value" in item_def:
            base_value = item_def["base_value"]
        
        return max(1, int(base_value * base_rate))
    
    async def item_selected(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This is not your interaction!", ephemeral=True)
            return
        
        item_id = int(interaction.data['values'][0])
        
        # Get item details
        item_info = self.bot.db.execute_query(
            '''SELECT item_id, item_name, quantity, item_type, value, description
               FROM inventory WHERE item_id = ?''',
            (item_id,),
            fetch='one'
        )
        
        if not item_info:
            await interaction.response.send_message("Item no longer available.", ephemeral=True)
            return
        
        item_id, item_name, quantity, item_type, stored_value, description = item_info
        
        # Calculate sell price
        sell_price = self._calculate_sell_price(item_name, item_type, stored_value)
        is_specialty = self._is_specialty_item(item_name, item_type)
        
        view = NPCSellQuantityView(self.bot, self.user_id, self.npc_id, self.npc_type, 
                                   item_id, item_name, quantity, sell_price, is_specialty)
        
        embed = discord.Embed(
            title="💰 Confirm Sale",
            description=f"Selling **{item_name}** to NPC",
            color=0x00ff00
        )
        
        embed.add_field(name="Price per Item", value=f"{sell_price:,} credits", inline=True)
        embed.add_field(name="Available Quantity", value=str(quantity), inline=True)
        
        if is_specialty:
            embed.add_field(name="⭐ Specialty Bonus", value="25% extra payment!", inline=True)
        
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        
class NPCSellQuantityView(discord.ui.View):
    def __init__(self, bot, user_id: int, npc_id: int, npc_type: str, item_id: int, 
                 item_name: str, max_quantity: int, sell_price: int, is_specialty: bool):
        super().__init__(timeout=120)
        self.bot = bot
        self.user_id = user_id
        self.npc_id = npc_id
        self.npc_type = npc_type
        self.item_id = item_id
        self.item_name = item_name
        self.max_quantity = max_quantity
        self.sell_price = sell_price
        self.is_specialty = is_specialty
        self.selected_quantity = 1
        
        self.update_buttons()
    
    def update_buttons(self):
        self.clear_items()
        
        # Quantity adjustment buttons
        decrease_btn = discord.ui.Button(
            label="-", style=discord.ButtonStyle.secondary, 
            disabled=(self.selected_quantity <= 1)
        )
        decrease_btn.callback = self.decrease_quantity
        self.add_item(decrease_btn)
        
        quantity_btn = discord.ui.Button(
            label=f"Quantity: {self.selected_quantity}", 
            style=discord.ButtonStyle.primary, disabled=True
        )
        self.add_item(quantity_btn)
        
        increase_btn = discord.ui.Button(
            label="+", style=discord.ButtonStyle.secondary,
            disabled=(self.selected_quantity >= self.max_quantity)
        )
        increase_btn.callback = self.increase_quantity
        self.add_item(increase_btn)
        
        # Max button
        max_btn = discord.ui.Button(
            label="Max", style=discord.ButtonStyle.secondary,
            disabled=(self.selected_quantity >= self.max_quantity)
        )
        max_btn.callback = self.set_max_quantity
        self.add_item(max_btn)
        
        # Confirm sale button
        confirm_btn = discord.ui.Button(
            label=f"Sell for {self.sell_price * self.selected_quantity:,} credits",
            style=discord.ButtonStyle.success, emoji="✅"
        )
        confirm_btn.callback = self.confirm_sale
        self.add_item(confirm_btn)
    
    async def decrease_quantity(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This is not your interaction!", ephemeral=True)
            return
        
        self.selected_quantity = max(1, self.selected_quantity - 1)
        self.update_buttons()
        await interaction.response.edit_message(view=self)
    
    async def increase_quantity(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This is not your interaction!", ephemeral=True)
            return
        
        self.selected_quantity = min(self.max_quantity, self.selected_quantity + 1)
        self.update_buttons()
        await interaction.response.edit_message(view=self)
    
    async def set_max_quantity(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This is not your interaction!", ephemeral=True)
            return
        
        self.selected_quantity = self.max_quantity
        self.update_buttons()
        await interaction.response.edit_message(view=self)
    
    async def confirm_sale(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This is not your interaction!", ephemeral=True)
            return
        
        total_payment = self.sell_price * self.selected_quantity
        
        # Update inventory
        if self.selected_quantity >= self.max_quantity:
            # Remove item completely
            self.bot.db.execute_query(
                "DELETE FROM inventory WHERE item_id = ?",
                (self.item_id,)
            )
        else:
            # Reduce quantity
            self.bot.db.execute_query(
                "UPDATE inventory SET quantity = quantity - ? WHERE item_id = ?",
                (self.selected_quantity, self.item_id)
            )
        
        # Add money to player
        self.bot.db.execute_query(
            "UPDATE characters SET money = money + ? WHERE user_id = ?",
            (total_payment, self.user_id)
        )
        
        embed = discord.Embed(
            title="✅ Sale Successful",
            description=f"Sold {self.selected_quantity}x **{self.item_name}** to NPC!",
            color=0x00ff00
        )
        
        embed.add_field(name="Payment Received", value=f"{total_payment:,} credits", inline=True)
        embed.add_field(name="Price per Item", value=f"{self.sell_price:,} credits", inline=True)
        
        if self.is_specialty:
            embed.add_field(name="⭐ Specialty Bonus", value="Applied!", inline=True)
        
        await interaction.response.send_message(embed=embed, ephemeral=True)       
async def setup(bot):
    await bot.add_cog(NPCInteractionsCog(bot))