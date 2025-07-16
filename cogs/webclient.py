# cogs/webclient.py
import discord
from discord.ext import commands, tasks
from discord import app_commands
import asyncio
import json
import hashlib
import secrets
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set, Tuple
import aiohttp
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Depends, Request, Response
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from pydantic import BaseModel
import os
import re
from threading import Thread
import logging

# Suppress FastAPI/Uvicorn logs
logging.getLogger("uvicorn").setLevel(logging.WARNING)
logging.getLogger("uvicorn.access").setLevel(logging.WARNING)

class WebClientSession:
    def __init__(self, session_id: str, user_id: int, character_name: str):
        self.session_id = session_id
        self.user_id = user_id
        self.character_name = character_name
        self.websocket: Optional[WebSocket] = None
        self.last_activity = datetime.utcnow()
        self.current_location: Optional[int] = None
        self.current_channel_id: Optional[int] = None

class CommandRequest(BaseModel):
    command: str
    args: List[str] = []

class MessageRequest(BaseModel):
    content: str
    location_id: Optional[int] = None

class WebClient(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = bot.db
        self.app = None
        self.host = "0.0.0.0"
        self.port = 8091  # Different port from web map
        self.is_running = False
        self.server_thread = None
        
        # Session management
        self.sessions: Dict[str, WebClientSession] = {}
        self.websocket_clients: Set[WebSocket] = set()
        self.user_websockets: Dict[int, WebSocket] = {}  # user_id -> websocket
        
        # Message queue for syncing
        self.message_queue = asyncio.Queue()
        
        # Start message processor
        # Start message processor
        self.process_messages.start()
        
        # Create web directories
        self._create_web_directories()
        
    def cog_unload(self):
        """Clean up when cog is unloaded"""
        self.process_messages.cancel()
        if self.is_running:
            self.is_running = False
            # Clean up websockets
            for ws in self.websocket_clients.copy():
                asyncio.create_task(ws.close())
    
    def _create_web_directories(self):
        """Create necessary directories for web client"""
        os.makedirs("web/client/static/css", exist_ok=True)
        os.makedirs("web/client/static/js", exist_ok=True)
        os.makedirs("web/client/templates", exist_ok=True)
        
    async def cog_load(self):
        """Called when the cog is loaded"""
        print("✅ WebClient cog loaded")
        
        # Check if web map is running and auto-start if configured
        webmap_cog = self.bot.get_cog('WebMap')
        if webmap_cog and webmap_cog.is_running:
            # Delay start to ensure web map is fully initialized
            await asyncio.sleep(2)
            # Auto-start web client on same settings as web map
            await self._auto_start_webclient()
    
    async def _auto_start_webclient(self):
        """Auto-start web client when web map starts"""
        if not self.is_running:
            print("🚀 Auto-starting web client alongside web map...")
            self._setup_routes()
            self._create_client_files()
            
            # Start server in thread
            self.server_thread = Thread(target=self._run_server, daemon=True)
            self.server_thread.start()
            self.is_running = True
            
            # Start update loop
            asyncio.create_task(self._start_session_cleanup_loop())
            
            print(f"✅ Web client started on http://localhost:{self.port}")
    
    def _setup_routes(self):
        """Set up FastAPI routes for the web client"""
        self.app = FastAPI()
        
        # Serve static files
        self.app.mount("/static", StaticFiles(directory="web/client/static"), name="static")
        
        @self.app.get("/", response_class=HTMLResponse)
        async def home():
            """Serve the main client page"""
            with open("web/client/templates/index.html", "r") as f:
                return f.read()
        
        @self.app.get("/api/check-auth")
        async def check_auth(session_id: str):
            """Check if a session is valid"""
            if session_id in self.sessions:
                session = self.sessions[session_id]
                session.last_activity = datetime.utcnow()
                return {"authenticated": True, "character": session.character_name}
            return {"authenticated": False}
        
        @self.app.post("/api/login")
        async def login(credentials: dict):
            """Authenticate user with Discord ID and password"""
            try:
                discord_id = credentials.get("discord_id", "").strip()
                password = credentials.get("password", "")
                
                # Validate Discord ID
                try:
                    user_id = int(discord_id)
                except ValueError:
                    raise HTTPException(status_code=400, detail="Invalid Discord ID")
                
                # Check if user has a character
                char_data = self.db.execute_query(
                    """SELECT c.name, c.current_location, c.is_logged_in, wp.password_hash 
                       FROM characters c
                       LEFT JOIN web_passwords wp ON c.user_id = wp.user_id
                       WHERE c.user_id = ?""",
                    (user_id,),
                    fetch='one'
                )
                
                if not char_data:
                    raise HTTPException(status_code=404, detail="No character found for this Discord ID")
                
                char_name, current_location, is_logged_in, password_hash = char_data
                
                # Check password
                if not password_hash:
                    raise HTTPException(status_code=403, detail="No password set. Use /character password in Discord")
                
                # Verify password
                if not self._verify_password(password, password_hash):
                    raise HTTPException(status_code=401, detail="Invalid password")
                
                # Check if already logged in on Discord
                if is_logged_in:
                    raise HTTPException(status_code=403, detail="Character is already logged in on Discord")
                
                # Create session
                session_id = str(uuid.uuid4())
                session = WebClientSession(session_id, user_id, char_name)
                session.current_location = current_location
                self.sessions[session_id] = session
                
                # Log in the character
                self.db.execute_query(
                    "UPDATE characters SET is_logged_in = 1, login_time = CURRENT_TIMESTAMP WHERE user_id = ?",
                    (user_id,)
                )
                
                # Record web session
                self.db.execute_query(
                    """INSERT INTO web_sessions (session_id, user_id, created_at, last_activity)
                       VALUES (?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)""",
                    (session_id, user_id)
                )
                
                return {
                    "success": True,
                    "session_id": session_id,
                    "character_name": char_name,
                    "location_id": current_location
                }
                
            except HTTPException:
                raise
            except Exception as e:
                print(f"Login error: {e}")
                raise HTTPException(status_code=500, detail="Login failed")
        
        @self.app.post("/api/logout")
        async def logout(data: dict):
            """Log out from web client"""
            session_id = data.get("session_id")
            if session_id in self.sessions:
                session = self.sessions[session_id]
                
                # Log out character
                self.db.execute_query(
                    "UPDATE characters SET is_logged_in = 0 WHERE user_id = ?",
                    (session.user_id,)
                )
                
                # Remove session
                del self.sessions[session_id]
                self.db.execute_query(
                    "DELETE FROM web_sessions WHERE session_id = ?",
                    (session_id,)
                )
                
                # Close websocket if exists
                if session.user_id in self.user_websockets:
                    ws = self.user_websockets[session.user_id]
                    await ws.close()
                    del self.user_websockets[session.user_id]
                
                return {"success": True}
            
            return {"success": False, "error": "Invalid session"}
        
        @self.app.get("/api/location/{location_id}")
        async def get_location_info(location_id: int, session_id: str):
            """Get location information"""
            if session_id not in self.sessions:
                raise HTTPException(status_code=401, detail="Unauthorized")
            
            location = self.db.execute_query(
                """SELECT l.*, 
                   (SELECT COUNT(*) FROM characters WHERE current_location = l.location_id AND is_logged_in = 1) as player_count
                   FROM locations l WHERE l.location_id = ?""",
                (location_id,),
                fetch='one'
            )
            
            if not location:
                raise HTTPException(status_code=404, detail="Location not found")
            
            # Get players at location
            players = self.db.execute_query(
                "SELECT name FROM characters WHERE current_location = ? AND is_logged_in = 1",
                (location_id,),
                fetch='all'
            )
            
            return {
                "location": {
                    "id": location[0],
                    "name": location[1],
                    "description": location[2],
                    "type": location[3],
                    "player_count": location[-1],
                    "players": [p[0] for p in players]
                }
            }
        
        @self.app.post("/api/command")
        async def execute_command(request: CommandRequest, session_id: str = None):
            """Execute a bot command through the web client"""
            if not session_id or session_id not in self.sessions:
                raise HTTPException(status_code=401, detail="Unauthorized")
            
            session = self.sessions[session_id]
            
            # Block admin commands
            blocked_commands = ['admin', 'setup', 'reset', 'backup', 'webmap', 'webclient']
            if any(request.command.startswith(cmd) for cmd in blocked_commands):
                raise HTTPException(status_code=403, detail="This command is not available through the web client")
            
            # Queue command for processing
            await self.message_queue.put({
                'type': 'command',
                'user_id': session.user_id,
                'command': request.command,
                'args': request.args,
                'session_id': session_id
            })
            
            return {"success": True, "message": "Command queued for processing"}
        
        @self.app.post("/api/message")
        async def send_message(request: MessageRequest, session_id: str = None):
            """Send a regular message to the game"""
            if not session_id or session_id not in self.sessions:
                raise HTTPException(status_code=401, detail="Unauthorized")
            
            session = self.sessions[session_id]
            
            # Queue message for processing
            await self.message_queue.put({
                'type': 'message',
                'user_id': session.user_id,
                'content': request.content,
                'location_id': request.location_id or session.current_location,
                'session_id': session_id
            })
            
            return {"success": True}
        
        @self.app.websocket("/ws/{session_id}")
        async def websocket_endpoint(websocket: WebSocket, session_id: str):
            """WebSocket connection for real-time updates"""
            if session_id not in self.sessions:
                await websocket.close(code=4001, reason="Unauthorized")
                return
            
            session = self.sessions[session_id]
            await websocket.accept()
            
            # Store websocket references
            self.websocket_clients.add(websocket)
            session.websocket = websocket
            self.user_websockets[session.user_id] = websocket
            
            try:
                # Send initial data
                await websocket.send_json({
                    "type": "connected",
                    "character": session.character_name,
                    "location_id": session.current_location
                })
                
                # Keep connection alive
                while True:
                    try:
                        data = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
                        # Handle ping/pong
                        if data == "ping":
                            await websocket.send_text("pong")
                    except asyncio.TimeoutError:
                        # Send periodic ping
                        try:
                            await websocket.send_text("ping")
                        except:
                            break
                            
            except WebSocketDisconnect:
                pass
            finally:
                # Clean up
                self.websocket_clients.discard(websocket)
                if session.user_id in self.user_websockets:
                    del self.user_websockets[session.user_id]
                session.websocket = None
    
    def _hash_password(self, password: str) -> str:
        """Hash a password using SHA256"""
        salt = secrets.token_hex(16)
        pwd_hash = hashlib.sha256(f"{salt}{password}".encode()).hexdigest()
        return f"{salt}:{pwd_hash}"
    
    def _verify_password(self, password: str, stored_hash: str) -> bool:
        """Verify a password against stored hash"""
        try:
            salt, hash_value = stored_hash.split(':')
            pwd_hash = hashlib.sha256(f"{salt}{password}".encode()).hexdigest()
            return pwd_hash == hash_value
        except:
            return False
    
    @tasks.loop(seconds=1)
    async def process_messages(self):
        """Process queued messages and commands"""
        try:
            while not self.message_queue.empty():
                msg_data = await self.message_queue.get()
                
                if msg_data['type'] == 'command':
                    await self._process_command(msg_data)
                elif msg_data['type'] == 'message':
                    await self._process_message(msg_data)
                    
        except Exception as e:
            print(f"Error processing messages: {e}")
    
    async def _process_command(self, data: dict):
        """Process a command from web client"""
        user_id = data['user_id']
        command = data['command']
        args = data['args']
        
        # Get user and their current location
        user = self.bot.get_user(user_id)
        if not user:
            return
        
        # Find appropriate channel for command execution
        char_data = self.db.execute_query(
            "SELECT current_location FROM characters WHERE user_id = ?",
            (user_id,),
            fetch='one'
        )
        
        if not char_data:
            return
        
        location_id = char_data[0]
        location_data = self.db.execute_query(
            "SELECT channel_id FROM locations WHERE location_id = ?",
            (location_id,),
            fetch='one'
        )
        
        if not location_data or not location_data[0]:
            # Send error back to web client
            if user_id in self.user_websockets:
                await self.user_websockets[user_id].send_json({
                    "type": "error",
                    "message": "Cannot execute commands in locations without Discord channels"
                })
            return
        
        channel_id = location_data[0]
        channel = self.bot.get_channel(channel_id)
        
        if not channel:
            return
        
        # Create a fake interaction context for command execution
        # This is a simplified approach - you may need to enhance this
        # based on your specific command requirements
        try:
            # Format command string
            full_command = f"/{command}"
            if args:
                full_command += " " + " ".join(args)
            
            # Send notification to web client
            if user_id in self.user_websockets:
                await self.user_websockets[user_id].send_json({
                    "type": "command_executed",
                    "command": full_command
                })
            
            # Note: Actual command execution would require more complex interaction handling
            # This is a placeholder for the command routing system
            
        except Exception as e:
            print(f"Error executing command: {e}")
            if user_id in self.user_websockets:
                await self.user_websockets[user_id].send_json({
                    "type": "error",
                    "message": f"Command execution failed: {str(e)}"
                })
    
    async def _process_message(self, data: dict):
        """Process a regular message from web client"""
        user_id = data['user_id']
        content = data['content']
        location_id = data['location_id']
        
        # Get location channel
        location_data = self.db.execute_query(
            "SELECT channel_id, name FROM locations WHERE location_id = ?",
            (location_id,),
            fetch='one'
        )
        
        if not location_data or not location_data[0]:
            return
        
        channel_id, location_name = location_data
        channel = self.bot.get_channel(channel_id)
        
        if channel:
            # Get character name
            char_name = self.db.execute_query(
                "SELECT name FROM characters WHERE user_id = ?",
                (user_id,),
                fetch='one'
            )[0]
            
            # Send message to Discord channel
            embed = discord.Embed(
                description=content,
                color=0x00ff00,
                timestamp=datetime.utcnow()
            )
            embed.set_author(name=f"{char_name} (Web)", icon_url="https://i.imgur.com/WmgKGNp.png")
            embed.set_footer(text=f"Sent from web client • {location_name}")
            
            await channel.send(embed=embed)
    
    async def _start_session_cleanup_loop(self):
        """Clean up expired sessions"""
        while self.is_running:
            try:
                # Remove sessions inactive for more than 30 minutes
                expired = []
                for session_id, session in self.sessions.items():
                    if datetime.utcnow() - session.last_activity > timedelta(minutes=30):
                        expired.append(session_id)
                
                for session_id in expired:
                    session = self.sessions[session_id]
                    
                    # Log out character
                    self.db.execute_query(
                        "UPDATE characters SET is_logged_in = 0 WHERE user_id = ?",
                        (session.user_id,)
                    )
                    
                    # Close websocket
                    if session.websocket:
                        await session.websocket.close()
                    
                    # Remove session
                    del self.sessions[session_id]
                    self.db.execute_query(
                        "DELETE FROM web_sessions WHERE session_id = ?",
                        (session_id,)
                    )
                
                await asyncio.sleep(300)  # Check every 5 minutes
                
            except Exception as e:
                print(f"Session cleanup error: {e}")
                await asyncio.sleep(300)
    
    def _run_server(self):
        """Run the FastAPI server"""
        if not self.app:
            return
        
        try:
            import uvicorn
            uvicorn.run(
                self.app,
                host=self.host,
                port=self.port,
                log_level="warning",
                access_log=False
            )
        except Exception as e:
            print(f"❌ Error running web client server: {e}")
            self.is_running = False
    
    def _create_client_files(self):
        """Create the web client HTML, CSS, and JavaScript files"""
        # Create main HTML
        self._create_client_html()
        
        # Create CSS
        self._create_client_css()
        
        # Create JavaScript
        self._create_client_javascript()
    
    def _create_client_html(self):
        """Create the main client HTML file"""
        html_content = '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Galaxy Web Client</title>
    <link rel="stylesheet" href="/static/css/client.css">
    <link href="https://fonts.googleapis.com/css2?family=Share+Tech+Mono&family=Orbitron:wght@400;700;900&display=swap" rel="stylesheet">
</head>
<body class="theme-blue">
    <!-- Login Screen -->
    <div id="login-screen" class="screen active">
        <div class="login-container">
            <div class="login-header">
                <div class="status-light"></div>
                <h1>GALACTIC NETWORK ACCESS</h1>
            </div>
            <form id="login-form" class="login-form">
                <div class="form-group">
                    <label for="discord-id">Discord ID</label>
                    <input type="text" id="discord-id" name="discord_id" required 
                           placeholder="Your Discord User ID" autocomplete="off">
                    <small>Right-click your profile in Discord → Copy User ID</small>
                </div>
                <div class="form-group">
                    <label for="password">Password</label>
                    <input type="password" id="password" name="password" required 
                           placeholder="Character Password">
                    <small>Set with /character password in Discord</small>
                </div>
                <button type="submit" class="btn-primary">AUTHENTICATE</button>
                <div id="login-error" class="error-message"></div>
            </form>
        </div>
    </div>

    <!-- Game Screen -->
    <div id="game-screen" class="screen">
        <header class="game-header">
            <div class="header-info">
                <div class="status-indicator">
                    <div class="status-light"></div>
                    <span id="character-name">LOADING...</span>
                </div>
                <div class="location-info">
                    <span id="current-location">UNKNOWN LOCATION</span>
                </div>
            </div>
            <div class="header-actions">
                <button id="btn-commands" class="btn-header">Commands</button>
                <button id="btn-logout" class="btn-header">Logout</button>
            </div>
        </header>

        <main class="game-content">
            <!-- Chat/Message Area -->
            <div class="chat-container">
                <div id="message-area" class="message-area">
                    <!-- Messages will appear here -->
                </div>
                <div class="input-container">
                    <input type="text" id="message-input" placeholder="Type a message or /command..." 
                           autocomplete="off">
                    <button id="send-button">SEND</button>
                </div>
            </div>

            <!-- Side Panel -->
            <aside class="side-panel">
                <div class="panel-section">
                    <h3>Location</h3>
                    <div id="location-details" class="panel-content">
                        <!-- Location info -->
                    </div>
                </div>
                <div class="panel-section">
                    <h3>Players Here</h3>
                    <div id="players-list" class="panel-content">
                        <!-- Player list -->
                    </div>
                </div>
                <div class="panel-section">
                    <h3>Quick Actions</h3>
                    <div class="quick-actions">
                        <button class="btn-action" data-command="status">Status</button>
                        <button class="btn-action" data-command="here">Location</button>
                        <button class="btn-action" data-command="inventory">Inventory</button>
                        <button class="btn-action" data-command="travel routes">Routes</button>
                    </div>
                </div>
            </aside>
        </main>

        <!-- Command Modal -->
        <div id="command-modal" class="modal">
            <div class="modal-content">
                <div class="modal-header">
                    <h2>Available Commands</h2>
                    <button class="close-modal">&times;</button>
                </div>
                <div class="modal-body">
                    <div class="command-category">
                        <h3>Character</h3>
                        <div class="command-list">
                            <div class="command-item">/status - View your character status</div>
                            <div class="command-item">/inventory - Check your inventory</div>
                            <div class="command-item">/reputation - View faction standings</div>
                        </div>
                    </div>
                    <div class="command-category">
                        <h3>Location</h3>
                        <div class="command-list">
                            <div class="command-item">/here - Current location info</div>
                            <div class="command-item">/look - Examine surroundings</div>
                            <div class="command-item">/area list - List available areas</div>
                        </div>
                    </div>
                    <div class="command-category">
                        <h3>Travel</h3>
                        <div class="command-list">
                            <div class="command-item">/travel routes - View available routes</div>
                            <div class="command-item">/travel go [destination] - Travel to location</div>
                            <div class="command-item">/travel status - Check travel progress</div>
                        </div>
                    </div>
                    <div class="command-category">
                        <h3>Economy</h3>
                        <div class="command-list">
                            <div class="command-item">/jobs - View available jobs</div>
                            <div class="command-item">/trade - Access trading</div>
                            <div class="command-item">/ship fuel - Check/buy fuel</div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <div class="scanlines"></div>
    <script src="/static/js/client.js"></script>
</body>
</html>'''
        
        with open("web/client/templates/index.html", "w", encoding='utf-8') as f:
            f.write(html_content)
    
    def _create_client_css(self):
        """Create the client CSS file matching web map theme"""
        css_content = '''/* Galaxy Web Client CSS - Matching Web Map Theme */
:root {
    /* Default blue theme - matches web map */
    --primary-color: #00ffff;
    --secondary-color: #00cccc;
    --accent-color: #0088cc;
    --warning-color: #ff8800;
    --success-color: #00ff88;
    --error-color: #ff3333;
    
    --primary-bg: #000408;
    --secondary-bg: #0a0f1a;
    --accent-bg: #1a2332;
    --text-primary: #e0ffff;
    --text-secondary: #88ccdd;
    --text-muted: #556677;
    --border-color: #003344;
    --shadow-dark: rgba(0, 0, 0, 0.9);
    
    --glow-primary: rgba(0, 255, 255, 0.6);
    --glow-secondary: rgba(0, 204, 204, 0.4);
    --gradient-holo: linear-gradient(135deg, rgba(0, 255, 255, 0.1), rgba(0, 204, 204, 0.2));
    --gradient-panel: linear-gradient(145deg, rgba(10, 15, 26, 0.95), rgba(26, 35, 50, 0.95));
}

/* Theme variations - same as web map */
.theme-amber {
    --primary-color: #ffaa00;
    --secondary-color: #cc8800;
    --accent-color: #ff6600;
    --glow-primary: rgba(255, 170, 0, 0.6);
    --glow-secondary: rgba(204, 136, 0, 0.4);
}

.theme-green {
    --primary-color: #00ff88;
    --secondary-color: #00cc66;
    --accent-color: #00aa44;
    --glow-primary: rgba(0, 255, 136, 0.6);
    --glow-secondary: rgba(0, 204, 102, 0.4);
}

.theme-red {
    --primary-color: #ff4444;
    --secondary-color: #cc2222;
    --accent-color: #aa0000;
    --glow-primary: rgba(255, 68, 68, 0.6);
    --glow-secondary: rgba(204, 34, 34, 0.4);
}

.theme-purple {
    --primary-color: #aa44ff;
    --secondary-color: #8822cc;
    --accent-color: #6600aa;
    --glow-primary: rgba(170, 68, 255, 0.6);
    --glow-secondary: rgba(136, 34, 204, 0.4);
}

* {
    margin: 0;
    padding: 0;
    box-sizing: border-box;
}

body {
    font-family: 'Share Tech Mono', monospace;
    background: var(--primary-bg);
    color: var(--text-primary);
    overflow: hidden;
    height: 100vh;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}

/* Scanlines effect */
.scanlines {
    position: fixed;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    background: repeating-linear-gradient(
        0deg,
        rgba(0, 0, 0, 0) 0px,
        rgba(0, 255, 255, 0.03) 1px,
        rgba(0, 0, 0, 0) 2px,
        rgba(0, 0, 0, 0) 3px
    );
    pointer-events: none;
    z-index: 9999;
    opacity: 0.3;
}

/* Screen management */
.screen {
    display: none;
    width: 100%;
    height: 100vh;
}

.screen.active {
    display: flex;
}

/* Login Screen */
#login-screen {
    align-items: center;
    justify-content: center;
    background: radial-gradient(ellipse at center, var(--accent-bg) 0%, var(--primary-bg) 100%);
}

.login-container {
    background: var(--gradient-panel);
    border: 2px solid var(--border-color);
    border-radius: 12px;
    padding: 3rem;
    width: 90%;
    max-width: 400px;
    box-shadow: 
        0 0 50px var(--glow-primary),
        0 10px 30px var(--shadow-dark),
        inset 0 1px 0 rgba(255, 255, 255, 0.1);
}

.login-header {
    text-align: center;
    margin-bottom: 2rem;
}

.login-header h1 {
    font-family: 'Orbitron', monospace;
    font-size: 1.5rem;
    color: var(--primary-color);
    text-shadow: 0 0 20px var(--glow-primary);
    margin-top: 1rem;
}

.status-light {
    width: 12px;
    height: 12px;
    background: var(--success-color);
    border-radius: 50%;
    display: inline-block;
    box-shadow: 0 0 10px var(--success-color);
    animation: pulse 2s infinite;
}

@keyframes pulse {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.5; }
}

.form-group {
    margin-bottom: 1.5rem;
}

.form-group label {
    display: block;
    margin-bottom: 0.5rem;
    color: var(--text-secondary);
    font-size: 0.9rem;
}

.form-group input {
    width: 100%;
    padding: 0.75rem;
    background: rgba(0, 0, 0, 0.5);
    border: 1px solid var(--border-color);
    border-radius: 4px;
    color: var(--text-primary);
    font-family: inherit;
    font-size: 1rem;
    transition: all 0.3s ease;
}

.form-group input:focus {
    outline: none;
    border-color: var(--primary-color);
    box-shadow: 0 0 10px var(--glow-primary);
}

.form-group small {
    display: block;
    margin-top: 0.25rem;
    color: var(--text-muted);
    font-size: 0.75rem;
}

.btn-primary {
    width: 100%;
    padding: 1rem;
    background: linear-gradient(145deg, var(--primary-color), var(--secondary-color));
    border: none;
    border-radius: 4px;
    color: var(--primary-bg);
    font-family: inherit;
    font-size: 1rem;
    font-weight: bold;
    cursor: pointer;
    text-transform: uppercase;
    letter-spacing: 1px;
    transition: all 0.3s ease;
    box-shadow: 0 0 20px var(--glow-primary);
}

.btn-primary:hover {
    transform: translateY(-2px);
    box-shadow: 0 0 30px var(--glow-primary);
}

.error-message {
    margin-top: 1rem;
    padding: 0.75rem;
    background: rgba(255, 0, 0, 0.1);
    border: 1px solid var(--error-color);
    border-radius: 4px;
    color: var(--error-color);
    font-size: 0.9rem;
    display: none;
}

.error-message.show {
    display: block;
}

/* Game Screen */
#game-screen {
    flex-direction: column;
}

.game-header {
    background: var(--gradient-panel);
    border-bottom: 2px solid var(--border-color);
    padding: 1rem 2rem;
    display: flex;
    justify-content: space-between;
    align-items: center;
    box-shadow: 0 2px 10px var(--shadow-dark);
}

.header-info {
    display: flex;
    align-items: center;
    gap: 2rem;
}

.status-indicator {
    display: flex;
    align-items: center;
    gap: 0.5rem;
}

.location-info {
    color: var(--text-secondary);
    font-size: 0.9rem;
}

.header-actions {
    display: flex;
    gap: 1rem;
}

.btn-header {
    padding: 0.5rem 1rem;
    background: rgba(0, 0, 0, 0.5);
    border: 1px solid var(--border-color);
    border-radius: 4px;
    color: var(--text-primary);
    font-family: inherit;
    font-size: 0.8rem;
    cursor: pointer;
    transition: all 0.3s ease;
}

.btn-header:hover {
    border-color: var(--primary-color);
    box-shadow: 0 0 10px var(--glow-primary);
}

.game-content {
    flex: 1;
    display: flex;
    overflow: hidden;
}

/* Chat Container */
.chat-container {
    flex: 1;
    display: flex;
    flex-direction: column;
    background: var(--secondary-bg);
}

.message-area {
    flex: 1;
    overflow-y: auto;
    padding: 1rem;
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
}

.message {
    background: rgba(0, 0, 0, 0.3);
    border-left: 3px solid var(--primary-color);
    padding: 0.75rem;
    border-radius: 4px;
    animation: messageSlide 0.3s ease;
}

@keyframes messageSlide {
    from {
        opacity: 0;
        transform: translateX(-20px);
    }
    to {
        opacity: 1;
        transform: translateX(0);
    }
}

.message-header {
    display: flex;
    justify-content: space-between;
    margin-bottom: 0.25rem;
}

.message-author {
    color: var(--primary-color);
    font-weight: bold;
}

.message-time {
    color: var(--text-muted);
    font-size: 0.8rem;
}

.message-content {
    color: var(--text-primary);
}

.system-message {
    background: rgba(0, 100, 100, 0.1);
    border-left-color: var(--accent-color);
    font-style: italic;
}

.error-message {
    background: rgba(255, 0, 0, 0.1);
    border-left-color: var(--error-color);
}

.input-container {
    display: flex;
    padding: 1rem;
    background: var(--accent-bg);
    border-top: 1px solid var(--border-color);
}

#message-input {
    flex: 1;
    padding: 0.75rem;
    background: rgba(0, 0, 0, 0.5);
    border: 1px solid var(--border-color);
    border-radius: 4px 0 0 4px;
    color: var(--text-primary);
    font-family: inherit;
    font-size: 1rem;
}

#message-input:focus {
    outline: none;
    border-color: var(--primary-color);
}

#send-button {
    padding: 0.75rem 1.5rem;
    background: linear-gradient(145deg, var(--primary-color), var(--secondary-color));
    border: none;
    border-radius: 0 4px 4px 0;
    color: var(--primary-bg);
    font-family: inherit;
    font-weight: bold;
    cursor: pointer;
    transition: all 0.3s ease;
}

#send-button:hover {
    box-shadow: 0 0 15px var(--glow-primary);
}

/* Side Panel */
.side-panel {
    width: 300px;
    background: var(--accent-bg);
    border-left: 1px solid var(--border-color);
    padding: 1rem;
    overflow-y: auto;
}

.panel-section {
    margin-bottom: 2rem;
}

.panel-section h3 {
    color: var(--primary-color);
    font-size: 1rem;
    margin-bottom: 1rem;
    text-shadow: 0 0 10px var(--glow-primary);
}

.panel-content {
    background: rgba(0, 0, 0, 0.3);
    border: 1px solid var(--border-color);
    border-radius: 4px;
    padding: 1rem;
    min-height: 100px;
}

.quick-actions {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 0.5rem;
}

.btn-action {
    padding: 0.75rem;
    background: rgba(0, 0, 0, 0.5);
    border: 1px solid var(--border-color);
    border-radius: 4px;
    color: var(--text-primary);
    font-family: inherit;
    font-size: 0.8rem;
    cursor: pointer;
    transition: all 0.3s ease;
}

.btn-action:hover {
    border-color: var(--primary-color);
    background: rgba(0, 255, 255, 0.1);
    box-shadow: 0 0 10px var(--glow-primary);
}

/* Modal */
.modal {
    display: none;
    position: fixed;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    background: rgba(0, 0, 0, 0.8);
    z-index: 1000;
    align-items: center;
    justify-content: center;
}

.modal.show {
    display: flex;
}

.modal-content {
    background: var(--gradient-panel);
    border: 2px solid var(--border-color);
    border-radius: 8px;
    width: 90%;
    max-width: 600px;
    max-height: 80vh;
    overflow: hidden;
    box-shadow: 0 0 50px var(--glow-primary);
}

.modal-header {
    background: rgba(0, 0, 0, 0.5);
    padding: 1rem 1.5rem;
    display: flex;
    justify-content: space-between;
    align-items: center;
    border-bottom: 1px solid var(--border-color);
}

.modal-header h2 {
    color: var(--primary-color);
    font-size: 1.2rem;
}

.close-modal {
    background: none;
    border: none;
    color: var(--text-secondary);
    font-size: 1.5rem;
    cursor: pointer;
    transition: color 0.3s ease;
}

.close-modal:hover {
    color: var(--primary-color);
}

.modal-body {
    padding: 1.5rem;
    overflow-y: auto;
    max-height: calc(80vh - 100px);
}

.command-category {
    margin-bottom: 1.5rem;
}

.command-category h3 {
    color: var(--secondary-color);
    margin-bottom: 0.5rem;
}

.command-list {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
}

.command-item {
    padding: 0.5rem;
    background: rgba(0, 0, 0, 0.3);
    border-left: 2px solid var(--border-color);
    color: var(--text-secondary);
}

/* Responsive Design */
@media (max-width: 768px) {
    .side-panel {
        display: none;
    }
    
    .login-container {
        padding: 2rem;
    }
    
    .game-header {
        padding: 0.75rem 1rem;
    }
    
    .header-info {
        flex-direction: column;
        align-items: flex-start;
        gap: 0.5rem;
    }
}

/* Discord-style Embeds */
.discord-embed {
    background: rgba(0, 0, 0, 0.4);
    border-radius: 4px;
    padding: 1rem;
    margin: 0.5rem 0;
    border-left: 4px solid var(--primary-color);
}

.embed-author {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    margin-bottom: 0.5rem;
    font-size: 0.9rem;
    color: var(--text-secondary);
}

.author-icon {
    width: 24px;
    height: 24px;
    border-radius: 50%;
}

.embed-title {
    font-weight: bold;
    color: var(--primary-color);
    margin-bottom: 0.5rem;
}

.embed-description {
    color: var(--text-primary);
    margin-bottom: 0.5rem;
    white-space: pre-wrap;
}

.embed-fields {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    gap: 0.5rem;
    margin: 0.5rem 0;
}

.embed-field {
    background: rgba(0, 0, 0, 0.2);
    padding: 0.5rem;
    border-radius: 4px;
}

.embed-field.inline {
    grid-column: span 1;
}

.field-name {
    font-weight: bold;
    color: var(--text-secondary);
    margin-bottom: 0.25rem;
    font-size: 0.9rem;
}

.field-value {
    color: var(--text-primary);
    font-size: 0.9rem;
}

.embed-image {
    max-width: 100%;
    border-radius: 4px;
    margin-top: 0.5rem;
}

.embed-footer {
    margin-top: 0.5rem;
    font-size: 0.8rem;
    color: var(--text-muted);
}

/* Ephemeral Messages */
.ephemeral-message {
    background: rgba(100, 50, 200, 0.1);
    border-left-color: var(--accent-color);
    position: relative;
}

.ephemeral-indicator {
    font-size: 0.8rem;
    color: var(--accent-color);
    margin-bottom: 0.5rem;
    font-style: italic;
}

/* Player List Styling */
.player-item {
    padding: 0.5rem;
    border-bottom: 1px solid rgba(255, 255, 255, 0.1);
    color: var(--text-secondary);
}

.player-item:last-child {
    border-bottom: none;
}

.no-players {
    color: var(--text-muted);
    font-style: italic;
    text-align: center;
    padding: 1rem;
}

/* Location Details */
.location-type {
    font-size: 0.8rem;
    color: var(--accent-color);
    text-transform: uppercase;
    margin-bottom: 0.5rem;
}

.location-description {
    color: var(--text-primary);
    line-height: 1.4;
}

/* Scrollbar Styling */
::-webkit-scrollbar {
    width: 8px;
}

::-webkit-scrollbar-track {
    background: var(--primary-bg);
}

::-webkit-scrollbar-thumb {
    background: var(--border-color);
    border-radius: 4px;
}

::-webkit-scrollbar-thumb:hover {
    background: var(--primary-color);
}'''
        
        with open("web/client/static/css/client.css", "w", encoding='utf-8') as f:
            f.write(css_content)
    
    def _create_client_javascript(self):
        """Create the client JavaScript file"""
        js_content = '''// Galaxy Web Client JavaScript
class GalaxyWebClient {
    constructor() {
        this.ws = null;
        this.sessionId = localStorage.getItem('galaxySessionId');
        this.characterName = null;
        this.currentLocation = null;
        
        this.init();
    }
    
    init() {
        // Check authentication on load
        if (this.sessionId) {
            this.checkAuth();
        }
        
        // Set up event listeners
        this.setupEventListeners();
    }
    
    setupEventListeners() {
        // Login form
        const loginForm = document.getElementById('login-form');
        if (loginForm) {
            loginForm.addEventListener('submit', (e) => this.handleLogin(e));
        }
        
        // Message input
        const messageInput = document.getElementById('message-input');
        const sendButton = document.getElementById('send-button');
        
        if (messageInput) {
            messageInput.addEventListener('keypress', (e) => {
                if (e.key === 'Enter') {
                    this.sendMessage();
                }
            });
        }
        
        if (sendButton) {
            sendButton.addEventListener('click', () => this.sendMessage());
        }
        
        // Logout button
        const logoutBtn = document.getElementById('btn-logout');
        if (logoutBtn) {
            logoutBtn.addEventListener('click', () => this.logout());
        }
        
        // Commands button
        const commandsBtn = document.getElementById('btn-commands');
        if (commandsBtn) {
            commandsBtn.addEventListener('click', () => this.showCommandsModal());
        }
        
        // Quick action buttons
        document.querySelectorAll('.btn-action').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const command = e.target.dataset.command;
                this.executeCommand(command);
            });
        });
        
        // Modal close
        document.querySelectorAll('.close-modal').forEach(btn => {
            btn.addEventListener('click', () => this.closeModal());
        });
    }
    
    async checkAuth() {
        try {
            const response = await fetch(`/api/check-auth?session_id=${this.sessionId}`);
            const data = await response.json();
            
            if (data.authenticated) {
                this.characterName = data.character;
                this.showGameScreen();
                this.connectWebSocket();
            } else {
                localStorage.removeItem('galaxySessionId');
                this.sessionId = null;
            }
        } catch (error) {
            console.error('Auth check failed:', error);
            localStorage.removeItem('galaxySessionId');
            this.sessionId = null;
        }
    }
    
    async handleLogin(e) {
        e.preventDefault();
        
        const discordId = document.getElementById('discord-id').value;
        const password = document.getElementById('password').value;
        const errorDiv = document.getElementById('login-error');
        
        try {
            const response = await fetch('/api/login', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    discord_id: discordId,
                    password: password
                })
            });
            
            const data = await response.json();
            
            if (data.success) {
                this.sessionId = data.session_id;
                this.characterName = data.character_name;
                this.currentLocation = data.location_id;
                
                localStorage.setItem('galaxySessionId', this.sessionId);
                
                this.showGameScreen();
                this.connectWebSocket();
                this.loadLocationInfo();
            } else {
                errorDiv.textContent = data.detail || 'Login failed';
                errorDiv.classList.add('show');
            }
        } catch (error) {
            errorDiv.textContent = 'Connection error. Please try again.';
            errorDiv.classList.add('show');
        }
    }
    
    showGameScreen() {
        document.getElementById('login-screen').classList.remove('active');
        document.getElementById('game-screen').classList.add('active');
        
        document.getElementById('character-name').textContent = this.characterName;
    }
    
    connectWebSocket() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws/${this.sessionId}`;
        
        this.ws = new WebSocket(wsUrl);
        
        this.ws.onopen = () => {
            console.log('Connected to game server');
            this.addSystemMessage('Connected to galactic network');
        };
        
        this.ws.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                this.handleWebSocketMessage(data);
            } catch (error) {
                console.error('Failed to parse message:', error);
            }
        };
        
        this.ws.onerror = (error) => {
            console.error('WebSocket error:', error);
            this.addSystemMessage('Connection error', 'error');
        };
        
        this.ws.onclose = () => {
            console.log('Disconnected from server');
            this.addSystemMessage('Disconnected from galactic network', 'error');
            
            // Attempt reconnection after 5 seconds
            setTimeout(() => {
                if (this.sessionId) {
                    this.connectWebSocket();
                }
            }, 5000);
        };
        
        // Periodic ping to keep connection alive
        setInterval(() => {
            if (this.ws && this.ws.readyState === WebSocket.OPEN) {
                this.ws.send('ping');
            }
        }, 25000);
    }
    
    handleWebSocketMessage(data) {
        switch (data.type) {
            case 'message':
                // Regular or bot messages
                if (data.embeds && data.embeds.length > 0) {
                    this.displayEmbedsMessage(data);
                } else {
                    this.addMessage(data.author, data.content, data.timestamp);
                }
                break;
            
            case 'ephemeral':
                // Private messages just for this user
                this.displayEphemeralMessage(data);
                break;
            
            case 'system':
                this.addSystemMessage(data.content, data.level);
                break;
            
            // ... other cases ...
        }
    }

    displayEmbedsMessage(data) {
        const messageArea = document.getElementById('message-area');
        const messageDiv = document.createElement('div');
        messageDiv.className = 'message embed-container';
        
        let html = `
            <div class="message-header">
                <span class="message-author">${data.author}</span>
                <span class="message-time">${new Date(data.timestamp).toLocaleTimeString()}</span>
            </div>
        `;
        
        if (data.content) {
            html += `<div class="message-content">${data.content}</div>`;
        }
        
        // Render each embed
        data.embeds.forEach(embed => {
            html += '<div class="discord-embed" style="';
            if (embed.color) {
                const color = '#' + embed.color.toString(16).padStart(6, '0');
                html += `border-left: 4px solid ${color};`;
            }
            html += '">';
            
            if (embed.author && embed.author.name) {
                html += `<div class="embed-author">`;
                if (embed.author.icon_url) {
                    html += `<img src="${embed.author.icon_url}" class="author-icon">`;
                }
                html += `<span>${embed.author.name}</span></div>`;
            }
            
            if (embed.title) {
                html += `<div class="embed-title">${embed.title}</div>`;
            }
            
            if (embed.description) {
                html += `<div class="embed-description">${embed.description}</div>`;
            }
            
            if (embed.fields && embed.fields.length > 0) {
                html += '<div class="embed-fields">';
                embed.fields.forEach(field => {
                    html += `
                        <div class="embed-field ${field.inline ? 'inline' : ''}">
                            <div class="field-name">${field.name}</div>
                            <div class="field-value">${field.value}</div>
                        </div>
                    `;
                });
                html += '</div>';
            }
            
            if (embed.image) {
                html += `<img src="${embed.image}" class="embed-image">`;
            }
            
            if (embed.footer) {
                html += `<div class="embed-footer">${embed.footer}</div>`;
            }
            
            html += '</div>';
        });
        
        messageDiv.innerHTML = html;
        messageArea.appendChild(messageDiv);
        messageArea.scrollTop = messageArea.scrollHeight;
    }

    displayEphemeralMessage(data) {
        const messageArea = document.getElementById('message-area');
        const messageDiv = document.createElement('div');
        messageDiv.className = 'message ephemeral-message';
        
        let html = `
            <div class="ephemeral-indicator">🔒 Only visible to you</div>
        `;
        
        if (data.content) {
            html += `<div class="message-content">${data.content}</div>`;
        }
        
        if (data.embed) {
            // Render the embed similar to above
            html += this.renderEmbed(data.embed);
        }
        
        messageDiv.innerHTML = html;
        messageArea.appendChild(messageDiv);
        messageArea.scrollTop = messageArea.scrollHeight;
    }
    
    async sendMessage() {
        const input = document.getElementById('message-input');
        const content = input.value.trim();
        
        if (!content) return;
        
        // Check if it's a command
        if (content.startsWith('/')) {
            const parts = content.substring(1).split(' ');
            const command = parts[0];
            const args = parts.slice(1);
            
            await this.executeCommand(command, args);
        } else {
            // Regular message
            try {
                await fetch('/api/message', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({
                        content: content,
                        location_id: this.currentLocation,
                        session_id: this.sessionId
                    })
                });
                
                // Clear input
                input.value = '';
            } catch (error) {
                this.addSystemMessage('Failed to send message', 'error');
            }
        }
    }
    
    async executeCommand(command, args = []) {
        try {
            const response = await fetch(`/api/command?session_id=${this.sessionId}`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    command: command,
                    args: args
                })
            });
            
            const data = await response.json();
            
            if (!data.success) {
                this.addSystemMessage(data.message || 'Command failed', 'error');
            }
        } catch (error) {
            this.addSystemMessage('Failed to execute command', 'error');
        }
    }
    
    async loadLocationInfo() {
        if (!this.currentLocation) return;
        
        try {
            const response = await fetch(`/api/location/${this.currentLocation}?session_id=${this.sessionId}`);
            const data = await response.json();
            
            if (data.location) {
                this.updateLocation(data.location);
                this.updatePlayersList(data.location.players);
            }
        } catch (error) {
            console.error('Failed to load location info:', error);
        }
    }
    
    updateLocation(location) {
        this.currentLocation = location.id;
        document.getElementById('current-location').textContent = location.name.toUpperCase();
        
        const locationDetails = document.getElementById('location-details');
        locationDetails.innerHTML = `
            <div class="location-type">${location.type}</div>
            <div class="location-description">${location.description || 'No description available'}</div>
        `;
    }
    
    updatePlayersList(players) {
        const playersList = document.getElementById('players-list');
        
        if (players && players.length > 0) {
            playersList.innerHTML = players.map(player => 
                `<div class="player-item">${player}</div>`
            ).join('');
        } else {
            playersList.innerHTML = '<div class="no-players">No other players here</div>';
        }
    }
    
    addMessage(author, content, timestamp) {
        const messageArea = document.getElementById('message-area');
        const messageDiv = document.createElement('div');
        messageDiv.className = 'message';
        
        const time = timestamp ? new Date(timestamp).toLocaleTimeString() : new Date().toLocaleTimeString();
        
        messageDiv.innerHTML = `
            <div class="message-header">
                <span class="message-author">${author}</span>
                <span class="message-time">${time}</span>
            </div>
            <div class="message-content">${content}</div>
        `;
        
        messageArea.appendChild(messageDiv);
        messageArea.scrollTop = messageArea.scrollHeight;
    }
    
    addSystemMessage(content, level = 'info') {
        const messageArea = document.getElementById('message-area');
        const messageDiv = document.createElement('div');
        messageDiv.className = `message system-message ${level}-message`;
        
        messageDiv.innerHTML = `
            <div class="message-content">${content}</div>
        `;
        
        messageArea.appendChild(messageDiv);
        messageArea.scrollTop = messageArea.scrollHeight;
    }
    
    handleCommandResponse(data) {
        if (data.embed) {
            // Display embed-style response
            this.displayEmbed(data.embed);
        } else if (data.content) {
            this.addSystemMessage(data.content);
        }
    }
    
    displayEmbed(embed) {
        const messageArea = document.getElementById('message-area');
        const embedDiv = document.createElement('div');
        embedDiv.className = 'message embed-message';
        
        let embedHtml = '<div class="embed">';
        
        if (embed.title) {
            embedHtml += `<div class="embed-title">${embed.title}</div>`;
        }
        
        if (embed.description) {
            embedHtml += `<div class="embed-description">${embed.description}</div>`;
        }
        
        if (embed.fields) {
            embedHtml += '<div class="embed-fields">';
            embed.fields.forEach(field => {
                embedHtml += `
                    <div class="embed-field">
                        <div class="field-name">${field.name}</div>
                        <div class="field-value">${field.value}</div>
                    </div>
                `;
            });
            embedHtml += '</div>';
        }
        
        embedHtml += '</div>';
        embedDiv.innerHTML = embedHtml;
        
        messageArea.appendChild(embedDiv);
        messageArea.scrollTop = messageArea.scrollHeight;
    }
    
    showCommandsModal() {
        document.getElementById('command-modal').classList.add('show');
    }
    
    closeModal() {
        document.querySelectorAll('.modal').forEach(modal => {
            modal.classList.remove('show');
        });
    }
    
    async logout() {
        try {
            await fetch('/api/logout', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    session_id: this.sessionId
                })
            });
        } catch (error) {
            console.error('Logout error:', error);
        }
        
        // Clear session
        localStorage.removeItem('galaxySessionId');
        this.sessionId = null;
        
        // Close websocket
        if (this.ws) {
            this.ws.close();
        }
        
        // Return to login screen
        document.getElementById('game-screen').classList.remove('active');
        document.getElementById('login-screen').classList.add('active');
        
        // Clear form
        document.getElementById('login-form').reset();
        document.getElementById('login-error').classList.remove('show');
    }
}

// Initialize client when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    window.galaxyClient = new GalaxyWebClient();
});'''
        
        with open("web/client/static/js/client.js", "w", encoding='utf-8') as f:
            f.write(js_content)
    
    # Discord Event Listeners for Message Syncing
    @commands.Cog.listener()
    async def on_message(self, message):
        """Sync Discord messages to web clients"""
        if message.author.bot:
            return
        
        # Check if message is in a location channel
        location_data = self.db.execute_query(
            "SELECT location_id, name FROM locations WHERE channel_id = ?",
            (message.channel.id,),
            fetch='one'
        )
        
        if location_data:
            location_id, location_name = location_data
            
            # Find all web clients at this location
            for session in self.sessions.values():
                if session.current_location == location_id and session.websocket:
                    try:
                        await session.websocket.send_json({
                            "type": "message",
                            "author": message.author.display_name,
                            "content": message.content,
                            "timestamp": message.created_at.isoformat(),
                            "location": location_name
                        })
                    except:
                        pass
    
    # Command for setting web client password
    @app_commands.command(name="password", description="Set or change your web client password")
    @app_commands.describe(
        action="Choose to set or remove your password",
        new_password="Your new password (only shown once)"
    )
    @app_commands.choices(action=[
        app_commands.Choice(name="Set/Change Password", value="set"),
        app_commands.Choice(name="Remove Password", value="remove")
    ])
    async def set_password(self, interaction: discord.Interaction, 
                          action: app_commands.Choice[str],
                          new_password: str = None):
        """Set or change web client password"""
        
        # Check if user has a character
        char_data = self.db.execute_query(
            "SELECT name FROM characters WHERE user_id = ?",
            (interaction.user.id,),
            fetch='one'
        )
        
        if not char_data:
            await interaction.response.send_message(
                "You need to create a character first!",
                ephemeral=True
            )
            return
        
        if action.value == "set":
            if not new_password:
                await interaction.response.send_message(
                    "You must provide a password when setting one!",
                    ephemeral=True
                )
                return
            
            # Validate password
            if len(new_password) < 6:
                await interaction.response.send_message(
                    "Password must be at least 6 characters long!",
                    ephemeral=True
                )
                return
            
            # Hash the password
            password_hash = self._hash_password(new_password)
            
            # Check if password exists
            existing = self.db.execute_query(
                "SELECT user_id FROM web_passwords WHERE user_id = ?",
                (interaction.user.id,),
                fetch='one'
            )
            
            if existing:
                # Update existing password
                self.db.execute_query(
                    "UPDATE web_passwords SET password_hash = ?, updated_at = CURRENT_TIMESTAMP WHERE user_id = ?",
                    (password_hash, interaction.user.id)
                )
            else:
                # Insert new password
                self.db.execute_query(
                    "INSERT INTO web_passwords (user_id, password_hash) VALUES (?, ?)",
                    (interaction.user.id, password_hash)
                )
            
            embed = discord.Embed(
                title="🔐 Web Client Password Set",
                description="Your password has been set successfully!",
                color=0x00ff00
            )
            embed.add_field(
                name="Important",
                value="Save this information to access the web client:",
                inline=False
            )
            embed.add_field(
                name="Discord ID",
                value=f"`{interaction.user.id}`",
                inline=True
            )
            embed.add_field(
                name="Password",
                value="The password you just set",
                inline=True
            )
            embed.add_field(
                name="Web Client URL",
                value=f"http://localhost:{self.port}",
                inline=False
            )
            embed.set_footer(text="⚠️ This is the only time you'll see this information!")
            
        else:  # Remove password
            self.db.execute_query(
                "DELETE FROM web_passwords WHERE user_id = ?",
                (interaction.user.id,)
            )
            
            embed = discord.Embed(
                title="🔓 Password Removed",
                description="Your web client password has been removed.",
                color=0xff9900
            )
            embed.add_field(
                name="Note",
                value="You will no longer be able to access the web client until you set a new password.",
                inline=False
            )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @app_commands.command(name="webclient", description="Get information about the web client")
    async def webclient_info(self, interaction: discord.Interaction):
        """Show web client information and status"""
        
        embed = discord.Embed(
            title="🌐 Galaxy Web Client",
            description="Access the game from your web browser!",
            color=0x00ffff
        )
        
        if self.is_running:
            embed.add_field(
                name="Status",
                value="🟢 Online",
                inline=True
            )
            embed.add_field(
                name="URL",
                value=f"http://localhost:{self.port}",
                inline=True
            )
            
            # Check if user has password set
            has_password = self.db.execute_query(
                "SELECT user_id FROM web_passwords WHERE user_id = ?",
                (interaction.user.id,),
                fetch='one'
            )
            
            if has_password:
                embed.add_field(
                    name="Your Access",
                    value="✅ Password is set",
                    inline=True
                )
            else:
                embed.add_field(
                    name="Your Access",
                    value="❌ No password set\nUse `/password` to set one",
                    inline=True
                )
            
            embed.add_field(
                name="Features",
                value="• Real-time gameplay\n• Message syncing with Discord\n• Full command access\n• Mobile-friendly interface",
                inline=False
            )
            
            embed.add_field(
                name="How to Connect",
                value="1. Set a password with `/password`\n2. Visit the URL above\n3. Login with your Discord ID and password",
                inline=False
            )
        else:
            embed.add_field(
                name="Status",
                value="⚫ Offline",
                inline=True
            )
            embed.add_field(
                name="Info",
                value="The web client is not currently running.",
                inline=False
            )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    async def sync_discord_message(self, message: discord.Message, message_type: str = "normal"):
        """Sync a Discord message to web clients at the same location"""
        
        # Get location from channel
        location_data = self.db.execute_query(
            "SELECT location_id, name FROM locations WHERE channel_id = ?",
            (message.channel.id,),
            fetch='one'
        )
        
        if not location_data:
            return
        
        location_id, location_name = location_data
        
        # Format message data
        message_data = {
            "type": "message",
            "author": message.author.display_name,
            "author_id": str(message.author.id),
            "content": message.content,
            "timestamp": message.created_at.isoformat(),
            "location": location_name,
            "message_type": message_type,
            "embeds": []
        }
        
        # Process embeds
        for embed in message.embeds:
            embed_data = {
                "title": embed.title,
                "description": embed.description,
                "color": embed.color.value if embed.color else None,
                "fields": [
                    {"name": field.name, "value": field.value, "inline": field.inline}
                    for field in embed.fields
                ],
                "footer": embed.footer.text if embed.footer else None,
                "thumbnail": embed.thumbnail.url if embed.thumbnail else None,
                "image": embed.image.url if embed.image else None,
                "author": {
                    "name": embed.author.name if embed.author else None,
                    "icon_url": embed.author.icon_url if embed.author else None
                }
            }
            message_data["embeds"].append(embed_data)
        
        # Send to all web clients at this location
        for session in self.sessions.values():
            if session.current_location == location_id and session.websocket:
                try:
                    await session.websocket.send_json(message_data)
                except Exception as e:
                    print(f"Failed to sync message to web client {session.session_id}: {e}")

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Enhanced message listener with full sync support"""
        
        # Skip bot messages unless they're game responses
        if message.author.bot:
            # Check if it's a game bot response (has embeds or specific format)
            if message.embeds or (message.author.id == self.bot.user.id):
                await self.sync_discord_message(message, "bot_response")
            return
        
        # Sync player messages
        await self.sync_discord_message(message, "player")

    async def sync_interaction_response(self, interaction: discord.Interaction, 
                                       content: str = None, embed: discord.Embed = None, 
                                       ephemeral: bool = False):
        """Sync interaction responses (including ephemeral) to web clients"""
        
        if not ephemeral:
            return  # Non-ephemeral will be caught by on_message
        
        # Get user's web session
        session = None
        for s in self.sessions.values():
            if s.user_id == interaction.user.id:
                session = s
                break
        
        if not session or not session.websocket:
            return
        
        # Format ephemeral message
        message_data = {
            "type": "ephemeral",
            "content": content,
            "timestamp": datetime.utcnow().isoformat(),
            "embed": None
        }
        
        if embed:
            message_data["embed"] = {
                "title": embed.title,
                "description": embed.description,
                "color": embed.color.value if embed.color else None,
                "fields": [
                    {"name": field.name, "value": field.value, "inline": field.inline}
                    for field in embed.fields
                ],
                "footer": embed.footer.text if embed.footer else None
            }
        
        try:
            await session.websocket.send_json(message_data)
        except Exception as e:
            print(f"Failed to sync ephemeral to web client: {e}")



_original_send_message = discord.InteractionResponse.send_message

async def patched_send_message(self, content=None, *, embed=None, embeds=None, 
                              view=None, ephemeral=False, **kwargs):
    """Patched send_message to sync ephemeral messages"""
    
    # Build kwargs for original call
    call_kwargs = {"ephemeral": ephemeral}
    if content is not None:
        call_kwargs["content"] = content
    if view is not None:
        call_kwargs["view"] = view
    
    # Handle embed vs embeds
    if embeds is not None:
        call_kwargs["embeds"] = embeds
    elif embed is not None:
        call_kwargs["embed"] = embed
    
    # Add any additional kwargs
    call_kwargs.update(kwargs)
    
    # Call original
    result = await _original_send_message(self, **call_kwargs)
    
    # Sync to web client if ephemeral
    if ephemeral:
        bot = self._parent.client if hasattr(self._parent, 'client') else None
        if bot:
            webclient = bot.get_cog('WebClient')
            if webclient:
                await webclient.sync_interaction_response(
                    self._parent, content, embed or (embeds[0] if embeds else None), ephemeral
                )
    
    return result



async def setup(bot):
    await bot.add_cog(WebClient(bot))