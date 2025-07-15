#!/usr/bin/env python3
"""
Discord RPG Bot Setup Script
Configures bot token, web map settings, and database path
"""

import os
import re
import sys
import shutil
from datetime import datetime

# Default values
DEFAULTS = {
    'bot_token': 'YOUR_TOKEN_HERE',
    'web_auto_start': False,
    'web_auto_start_time': 30,  # Changed from 'web_auto_start_delay' to match config.py
    'db_path': 'thequietend.db'
}

class BotSetup:
    def __init__(self):
        self.config_file = 'config.py'
        self.database_file = 'database.py'
        self.backup_dir = 'setup_backups'
        
    def create_backup(self, filepath):
        """Create a backup of the file before modifying"""
        if os.path.exists(filepath):
            if not os.path.exists(self.backup_dir):
                os.makedirs(self.backup_dir)
            
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_name = f"{os.path.basename(filepath)}.{timestamp}.bak"
            backup_path = os.path.join(self.backup_dir, backup_name)
            
            shutil.copy2(filepath, backup_path)
            print(f"✅ Backup created: {backup_path}")
    
    def read_current_config(self):
        """Read current configuration values"""
        current = DEFAULTS.copy()
        
        # Read config.py
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # Extract bot token
                token_match = re.search(r"'token':\s*'([^']*)'", content)
                if token_match:
                    current['bot_token'] = token_match.group(1)
                
                # Extract web auto start
                auto_start_match = re.search(r"'auto_start':\s*(True|False)", content)
                if auto_start_match:
                    current['web_auto_start'] = auto_start_match.group(1) == 'True'
                
                # Extract auto start time (corrected from auto_start_delay)
                time_match = re.search(r"'auto_start_time':\s*(\d+)", content)
                if time_match:
                    current['web_auto_start_time'] = int(time_match.group(1))
                    
            except Exception as e:
                print(f"⚠️ Error reading config.py: {e}")
        
        # Read database.py
        if os.path.exists(self.database_file):
            try:
                with open(self.database_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # Extract db_path
                db_match = re.search(r'db_path\s*=\s*"([^"]+)"', content)
                if db_match:
                    current['db_path'] = db_match.group(1)
                    
            except Exception as e:
                print(f"⚠️ Error reading database.py: {e}")
        
        return current
    
    def update_config_py(self, token, auto_start, time):
        """Update config.py with new values"""
        if not os.path.exists(self.config_file):
            print("❌ config.py not found!")
            return False
        
        self.create_backup(self.config_file)
        
        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            # Process line by line for more precise control
            for i, line in enumerate(lines):
                # Update token
                if "'token':" in line:
                    lines[i] = re.sub(r"'token':\s*'[^']*'", f"'token': '{token}'", line)
                
                # Update auto_start
                elif "'auto_start':" in line and 'auto_start_time' not in line:
                    auto_start_str = 'True' if auto_start else 'False'
                    lines[i] = re.sub(r"'auto_start':\s*(True|False)", f"'auto_start': {auto_start_str}", line)
                
                # Update auto_start_time - handle this very carefully
                elif "'auto_start_time':" in line:
                    # Find the position of the colon after 'auto_start_time'
                    key_end = line.find("'auto_start_time':") + len("'auto_start_time':")
                    # Find the comma after the value
                    comma_pos = line.find(',', key_end)
                    
                    if comma_pos != -1:
                        # Preserve the spacing and comment
                        before_key = line[:key_end]
                        after_comma = line[comma_pos:]
                        # Reconstruct the line with the new value
                        lines[i] = f"{before_key} {time}{after_comma}"
                    else:
                        # No comma found, just replace the number
                        lines[i] = re.sub(r"'auto_start_time':\s*\d+", f"'auto_start_time': {time}", line)
            
            # Write back the modified content
            with open(self.config_file, 'w', encoding='utf-8') as f:
                f.writelines(lines)
            
            print("✅ config.py updated successfully!")
            return True
            
        except Exception as e:
            print(f"❌ Error updating config.py: {e}")
            return False
    
    def update_database_py(self, db_path):
        """Update database.py with new database path"""
        if not os.path.exists(self.database_file):
            print("❌ database.py not found!")
            return False
        
        self.create_backup(self.database_file)
        
        try:
            with open(self.database_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Update db_path in the __init__ method
            content = re.sub(
                r'(def __init__\s*\(\s*self\s*,\s*db_path\s*=\s*)"[^"]+"',
                rf'\1"{db_path}"',
                content
            )
            
            with open(self.database_file, 'w', encoding='utf-8') as f:
                f.write(content)
            
            print("✅ database.py updated successfully!")
            return True
            
        except Exception as e:
            print(f"❌ Error updating database.py: {e}")
            return False
    
    def get_user_input(self, prompt, current_value, value_type='str', allow_skip=True):
        """Get user input with validation"""
        if value_type == 'bool':
            current_display = 'True' if current_value else 'False'
        else:
            current_display = current_value
        
        if allow_skip:
            print(f"\n{prompt}")
            print(f"Current value: {current_display}")
            print("Press Enter to keep current value, or type new value:")
        else:
            print(f"\n{prompt}")
            
        user_input = input("> ").strip()
        
        if not user_input and allow_skip:
            return current_value
        
        if value_type == 'bool':
            if user_input.lower() in ['true', 't', 'yes', 'y', '1']:
                return True
            elif user_input.lower() in ['false', 'f', 'no', 'n', '0']:
                return False
            else:
                print("⚠️ Invalid input. Please enter True/False")
                return self.get_user_input(prompt, current_value, value_type, allow_skip)
        
        elif value_type == 'int':
            try:
                value = int(user_input)
                # Ensure time value is positive
                if value <= 0:
                    print("⚠️ Invalid input. Please enter a positive number")
                    return self.get_user_input(prompt, current_value, value_type, allow_skip)
                return value
            except ValueError:
                print("⚠️ Invalid input. Please enter a number")
                return self.get_user_input(prompt, current_value, value_type, allow_skip)
        
        return user_input
    
    def run(self):
        """Main setup process"""
        print("=" * 60)
        print("🚀 DISCORD RPG BOT SETUP")
        print("=" * 60)
        print("\nThis script will help you configure your bot.")
        print("Press Enter to keep current values, or type new values.")
        print("\n" + "=" * 60)
        
        # Read current configuration
        current = self.read_current_config()
        
        # Show current configuration
        print("\n📋 CURRENT CONFIGURATION:")
        print(f"  Bot Token: {'***' + current['bot_token'][-10:] if len(current['bot_token']) > 10 and current['bot_token'] != DEFAULTS['bot_token'] else current['bot_token']}")
        print(f"  Web Map Auto-Start: {current['web_auto_start']}")
        print(f"  Web Map Start Time: {current['web_auto_start_time']} seconds")
        print(f"  Database Path: {current['db_path']}")
        
        # Ask if user wants to reset to defaults
        print("\n" + "=" * 60)
        reset = self.get_user_input(
            "Do you want to reset all values to defaults? (yes/no)",
            False,
            'bool',
            False
        )
        
        if reset:
            new_config = DEFAULTS.copy()
            print("\n✅ Values reset to defaults")
        else:
            # Get new values, starting with the current configuration
            new_config = current.copy()
            
            # Bot Token
            print("\n" + "=" * 60)
            print("📝 BOT TOKEN CONFIGURATION")
            print("Get your token from: https://discord.com/developers/applications")
            new_config['bot_token'] = self.get_user_input(
                "Enter Bot Token:",
                new_config['bot_token'],
                'str'
            )
            
            # Web Map Auto-Start
            print("\n" + "=" * 60)
            print("🗺️ WEB MAP CONFIGURATION")
            new_config['web_auto_start'] = self.get_user_input(
                "Enable Web Map Auto-Start? (true/false):",
                new_config['web_auto_start'],
                'bool'
            )
            
            # Auto-Start Time - Always allow updating this value
            new_config['web_auto_start_time'] = self.get_user_input(
                "Web Map Start Time (seconds after bot startup):",
                new_config['web_auto_start_time'],
                'int'
            )
            
            # Database Path
            print("\n" + "=" * 60)
            print("💾 DATABASE CONFIGURATION")
            print("Examples: 'rpg_game.db', 'data/game.db', 'C:/bots/rpg.db'")
            new_config['db_path'] = self.get_user_input(
                "Enter Database Path:",
                new_config['db_path'],
                'str'
            )
        
        # Confirm changes
        print("\n" + "=" * 60)
        print("📋 NEW CONFIGURATION:")
        print(f"  Bot Token: {'***' + new_config['bot_token'][-10:] if len(new_config['bot_token']) > 10 and new_config['bot_token'] != DEFAULTS['bot_token'] else new_config['bot_token']}")
        print(f"  Web Map Auto-Start: {new_config['web_auto_start']}")
        print(f"  Web Map Start Time: {new_config['web_auto_start_time']} seconds")
        print(f"  Database Path: {new_config['db_path']}")
        
        print("\n" + "=" * 60)
        confirm = self.get_user_input(
            "Apply these changes? (yes/no)",
            True,
            'bool',
            False
        )
        
        if not confirm:
            print("\n❌ Setup cancelled. No changes were made.")
            return
        
        # Apply changes
        print("\n🔄 Applying changes...")
        
        success = True
        
        # Update config.py
        if not self.update_config_py(
            new_config['bot_token'],
            new_config['web_auto_start'],
            new_config['web_auto_start_time']
        ):
            success = False
        
        # Update database.py
        if not self.update_database_py(new_config['db_path']):
            success = False
        
        # Final status
        print("\n" + "=" * 60)
        if success:
            print("✅ SETUP COMPLETE!")
            print("\nYour bot is now configured. You can run bot.py to start!")
            if new_config['bot_token'] == DEFAULTS['bot_token']:
                print("\n⚠️ WARNING: You haven't set a valid bot token yet!")
                print("   The bot won't start until you set a real token.")
        else:
            print("❌ SETUP FAILED!")
            print("\nSome files could not be updated. Check the error messages above.")
            print("Backups of original files are saved in 'setup_backups' folder.")
        
        print("\n" + "=" * 60)

if __name__ == "__main__":
    try:
        setup = BotSetup()
        setup.run()
    except KeyboardInterrupt:
        print("\n\n❌ Setup cancelled by user.")
    except Exception as e:
        print(f"\n\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
    
    print("\nPress Enter to exit...")
    input()