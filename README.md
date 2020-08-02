# HWSUK Discord Bot

## Deployment requirements

- discord.py
- systemd
- MongoDB
- pymongo
- motor
- praw
- Python >= 3.7

## Environment variables

| Name | Purpose | Required | Default value |
|---|---|---|---|
| `MONGODB_HOST` | The hostname of the MongoDB instance to connect to | No | `127.0.0.1` |
| `MONGODB_PORT` | The port on which the MongoDB instance is listening | No | `27017` |
| `MONGODB_USERNAME` | The username with which to authenticate with MongoDB | Yes | |
| `MONGODB_PASSWORD` | The password with which to authenticate with MongoDB | Yes | |
| `MONGODB_DATABASE` | The name of the database in MongoDB to read/write data | No | `hwsuk` |
| `DISCORD_SERVER_ID` | The server ID that is checked when modifying roles or searching for members | Yes | |
| `PRAW_CLIENT_ID` | The client ID for the application used for PRAW queries | Yes | |
| `PRAW_CLIENT_SECRET` | The client secret for the application used for PRAW queries | Yes | |
| `PRAW_PASSWORD` | The password for the user used for PRAW queries | Yes | |
| `PRAW_USER_AGENT` | The user agent sent to Reddit when making PRAW queries | No | `Checks if users are banned for our synced discord and keeps flairs synced` |
| `PRAW_USERNAME` | The username of the user used for PRAW queries | No | `HWSUKMods` |
| `REACTION_CHANNEL_ID` | The channel ID used for feedback | Yes | |
| `MOD_CHANNEL_ID` | The channel ID used for mod notifications of feedback items | Yes | |
| `REACTION_THRESHOLD` | Determines how many upvotes a feedback submission needs before it is sent to the mods | Yes | |
| `LOGGING_FILENAME` | Determines the naming format used for log files | No | `f'bot-{datetime.now().strftime("%m-%d-%Y-%H%M%S")}.log'` |
