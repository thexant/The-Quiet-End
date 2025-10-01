#!/usr/bin/env python3
"""
Discord RPG Bot Setup Script
Configures credentials and basic runtime settings via the .env file.
"""

from __future__ import annotations

from collections import OrderedDict
from datetime import datetime
from pathlib import Path
from typing import Dict

ENV_FILE = Path('.env')
BACKUP_DIR = Path('setup_backups')

DEFAULTS: OrderedDict[str, str] = OrderedDict(
    [
        ('DISCORD_TOKEN', ''),
        ('COMMAND_PREFIX', '!'),
        ('ACTIVITY_NAME', 'Entropy'),
        ('ALLOWED_GUILD_ID', ''),
        (
            'DATABASE_URL',
            'postgresql://thequietend_user:thequietend_pass@postgres:5432/thequietend_db',
        ),
    ]
)


class EnvSetup:
    def __init__(self) -> None:
        self.additional_entries: Dict[str, str] = {}

    def create_backup(self, filepath: Path) -> None:
        """Create a timestamped backup of the .env file."""
        if not filepath.exists():
            return

        BACKUP_DIR.mkdir(exist_ok=True)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_name = f"{filepath.name}.{timestamp}.bak"
        backup_path = BACKUP_DIR / backup_name
        backup_path.write_text(filepath.read_text(encoding='utf-8'), encoding='utf-8')
        print(f"✅ Backup created: {backup_path}")

    def read_env(self) -> Dict[str, str]:
        """Load existing values from the .env file, falling back to defaults."""
        values: Dict[str, str] = DEFAULTS.copy()
        self.additional_entries = {}

        if not ENV_FILE.exists():
            return values

        try:
            for line in ENV_FILE.read_text(encoding='utf-8').splitlines():
                stripped = line.strip()
                if not stripped or stripped.startswith('#') or '=' not in line:
                    continue

                key, raw_value = line.split('=', 1)
                key = key.strip()
                value = raw_value.strip()

                if key in values:
                    values[key] = value
                else:
                    self.additional_entries[key] = value
        except Exception as exc:
            print(f"⚠️ Error reading {ENV_FILE}: {exc}")

        return values

    def mask_token(self, token: str) -> str:
        if not token:
            return '<not set>'
        return f"***{token[-10:]}" if len(token) > 10 else token

    def get_user_input(self, prompt: str, current_value: str, allow_empty: bool = True) -> str:
        print(f"\n{prompt}")
        print(f"Current value: {current_value if current_value else '<not set>'}")
        if allow_empty:
            print("Press Enter to keep the current value or type a new one:")
        else:
            print("Enter a new value:")

        value = input("> ").strip()
        if not value and allow_empty:
            return current_value
        return value

    def confirm(self, prompt: str, default: bool = True) -> bool:
        default_str = 'Y/n' if default else 'y/N'
        while True:
            choice = input(f"{prompt} ({default_str}): ").strip().lower()
            if not choice:
                return default
            if choice in {'y', 'yes'}:
                return True
            if choice in {'n', 'no'}:
                return False
            print("⚠️ Please answer yes or no.")

    def write_env(self, values: Dict[str, str]) -> None:
        """Write updated values to the .env file."""
        self.create_backup(ENV_FILE)

        lines = [
            "# Discord Bot Configuration",
            f"DISCORD_TOKEN={values['DISCORD_TOKEN']}",
            f"COMMAND_PREFIX={values['COMMAND_PREFIX']}",
            f"ACTIVITY_NAME={values['ACTIVITY_NAME']}",
        ]

        if values['ALLOWED_GUILD_ID']:
            lines.append(f"ALLOWED_GUILD_ID={values['ALLOWED_GUILD_ID']}")
        else:
            lines.append("# ALLOWED_GUILD_ID=your_guild_id_here  # Optional: Set to restrict to single guild")

        lines.extend(
            [
                "",
                "# Database URL for PostgreSQL connection",
                f"DATABASE_URL={values['DATABASE_URL']}",
            ]
        )

        if self.additional_entries:
            lines.extend(["", "# Additional environment values"])
            for key, value in self.additional_entries.items():
                lines.append(f"{key}={value}")

        ENV_FILE.write_text("\n".join(lines) + "\n", encoding='utf-8')
        print(f"✅ Updated {ENV_FILE}")

    def run(self) -> None:
        print("=" * 60)
        print("🚀 DISCORD RPG BOT SETUP")
        print("=" * 60)
        print("\nThis script configures your .env file for the bot.")
        print("Press Enter to keep existing values or type new ones.")
        print("\n" + "=" * 60)

        values = self.read_env()

        print("\n📋 CURRENT CONFIGURATION:")
        print(f"  Bot Token: {self.mask_token(values['DISCORD_TOKEN'])}")
        print(f"  Command Prefix: {values['COMMAND_PREFIX'] or '<not set>'}")
        print(f"  Activity Name: {values['ACTIVITY_NAME'] or '<not set>'}")
        print(
            "  Allowed Guild ID: "
            + (values['ALLOWED_GUILD_ID'] or 'None (bot can join any guild)')
        )
        print(f"  Database URL: {values['DATABASE_URL']}")

        print("\n" + "=" * 60)
        reset = self.confirm("Reset all values to defaults?", default=False)

        if reset:
            new_values = DEFAULTS.copy()
            self.additional_entries = {}
            print("\n✅ Values reset to defaults")
        else:
            new_values = values.copy()

            print("\n" + "=" * 60)
            print("📝 BOT TOKEN CONFIGURATION")
            print("Get your token from: https://discord.com/developers/applications")
            new_values['DISCORD_TOKEN'] = self.get_user_input(
                "Enter Bot Token:", new_values['DISCORD_TOKEN'], allow_empty=False
            )

            print("\n" + "=" * 60)
            print("⚙️ BOT BEHAVIOUR SETTINGS")
            new_values['COMMAND_PREFIX'] = self.get_user_input(
                "Command prefix (used for text commands):", new_values['COMMAND_PREFIX']
            )
            new_values['ACTIVITY_NAME'] = self.get_user_input(
                "Activity status text:", new_values['ACTIVITY_NAME']
            )
            new_values['ALLOWED_GUILD_ID'] = self.get_user_input(
                "Limit the bot to a single guild ID (leave blank for all guilds):",
                new_values['ALLOWED_GUILD_ID'],
            )

            print("\n" + "=" * 60)
            print("🗄️ DATABASE SETTINGS")
            new_values['DATABASE_URL'] = self.get_user_input(
                "Database URL for the bot:", new_values['DATABASE_URL']
            )

        print("\n" + "=" * 60)
        print("📋 NEW CONFIGURATION:")
        print(f"  Bot Token: {self.mask_token(new_values['DISCORD_TOKEN'])}")
        print(f"  Command Prefix: {new_values['COMMAND_PREFIX'] or '<not set>'}")
        print(f"  Activity Name: {new_values['ACTIVITY_NAME'] or '<not set>'}")
        print(
            "  Allowed Guild ID: "
            + (new_values['ALLOWED_GUILD_ID'] or 'None (bot can join any guild)')
        )
        print(f"  Database URL: {new_values['DATABASE_URL']}")

        print("\n" + "=" * 60)
        if not self.confirm("Apply these changes?", default=True):
            print("\n❌ Setup cancelled. No changes were made.")
            return

        print("\n🔄 Applying changes...")
        self.write_env(new_values)

        print("\n" + "=" * 60)
        print("✅ SETUP COMPLETE!")
        print("Your credentials and settings are saved to .env.")
        if not new_values['DISCORD_TOKEN']:
            print("\n⚠️ WARNING: You haven't set a bot token yet!")
            print("   The bot won't start until DISCORD_TOKEN is configured.")
        print("\nYou can now start the bot with python bot.py or via Docker.")
        print("=" * 60)


if __name__ == "__main__":
    try:
        EnvSetup().run()
    except KeyboardInterrupt:
        print("\n\n❌ Setup cancelled by user.")
    except Exception as exc:
        print(f"\n\n❌ Unexpected error: {exc}")
        raise
    finally:
        input("\nPress Enter to exit...")
