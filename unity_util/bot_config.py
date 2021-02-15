import os
from datetime import datetime

def get_env(key, required=False, or_else=None):
    value = os.environ.get(key)

    if required and or_else:
        print(f"get_env(): for {key}, or_else parameter was ignored because this variable is required")

    if value is not None:
        return value
    else:
        if required:
            raise RuntimeError(f"Required environment variable {key} is missing.")
        else:
            return or_else


MONGODB_HOST = get_env("MONGODB_HOST", or_else="127.0.0.1")
MONGODB_PORT = get_env("MONGODB_PORT", or_else="27017")
MONGODB_USERNAME = get_env("MONGODB_USERNAME", required=True)
MONGODB_PASSWORD = get_env("MONGODB_PASSWORD", required=True)
MONGODB_DATABASE = get_env("MONGODB_DATABASE", or_else="hwsuk")

DISCORD_SERVER_ID = get_env("DISCORD_SERVER_ID", required=True)
DISCORD_TOKEN = get_env("DISCORD_TOKEN", required=True)
DISCORD_PREFIX = get_env("DISCORD_PREFIX", or_else="!")
DISCORD_UPDATER_ROLE = get_env("DISCORD_UPDATER_ROLE", or_else="718267453272096778")
DISCORD_VERIFIED_ROLE = get_env("DISCORD_VERIFIED_ROLE", or_else="292033619197820929")

PRAW_CLIENT_ID = get_env("PRAW_CLIENT_ID", required=True)
PRAW_CLIENT_SECRET = get_env("PRAW_CLIENT_SECRET", required=True)
PRAW_PASSWORD = get_env("PRAW_PASSWORD", required=True)
PRAW_USER_AGENT = get_env("PRAW_USER_AGENT",
                          or_else="Checks if users are banned for our synced discord and keeps flairs synced")
PRAW_USERNAME = get_env("PRAW_USERNAME", or_else="HWSUKMods")

REACTION_CHANNEL_ID = int(get_env("REACTION_CHANNEL_ID", required=True))
MOD_CHANNEL_ID = int(get_env("MOD_CHANNEL_ID", required=True))
REACTION_THRESHOLD = int(get_env("REACTION_THRESHOLD", required=True))

EMBED_REMOVER_CHANNEL_ID = int(get_env("EMBED_REMOVER_CHANNEL_ID", or_else=312673813311651853))

BUY_SELL_CHANNEL_ID = int(get_env("BUY_SELL_CHANNEL_ID", required=True))
BUY_SELL_LIMIT_SECONDS = int(get_env("BUY_SELL_LIMIT_SECONDS", or_else=259200))
BUY_SELL_BACKUP_DM_CHANNEL_ID = int(get_env("BUY_SELL_BACKUP_DM_CHANNEL_ID", or_else=292032782409007115))

DVLA_API_KEY = get_env("DVLA_API_KEY", required=True)

REPORT_CHANNEL_ID = int(get_env("REPORT_CHANNEL_ID", or_else="810214651433582633"))

LOGGING_FILENAME = get_env("LOGGING_FILENAME", or_else=f'bot-{datetime.now().strftime("%m-%d-%Y-%H%M%S")}.log')
