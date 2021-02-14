# HWSUK Discord Bot

## Deployment requirements

- MongoDB
- Python >= 3.7

## Environment variables

| Name                            | Purpose                                                                               | Required | Default value                                                               |
| ------------------------------- | ------------------------------------------------------------------------------------- | -------- | --------------------------------------------------------------------------- |
| `MONGODB_HOST`                  | The hostname of the MongoDB instance to connect to                                    | No       | `127.0.0.1`                                                                 |
| `MONGODB_PORT`                  | The port on which the MongoDB instance is listening                                   | No       | `27017`                                                                     |
| `MONGODB_USERNAME`              | The username with which to authenticate with MongoDB                                  | Yes      |                                                                             |
| `MONGODB_PASSWORD`              | The password with which to authenticate with MongoDB                                  | Yes      |                                                                             |
| `MONGODB_DATABASE`              | The name of the database in MongoDB to read/write data                                | No       | `hwsuk`                                                                     |
| `DISCORD_SERVER_ID`             | The server ID that is checked when modifying roles or searching for members           | Yes      |                                                                             |
| `PRAW_CLIENT_ID`                | The client ID for the application used for PRAW queries                               | Yes      |                                                                             |
| `PRAW_CLIENT_SECRET`            | The client secret for the application used for PRAW queries                           | Yes      |                                                                             |
| `PRAW_PASSWORD`                 | The password for the user used for PRAW queries                                       | Yes      |                                                                             |
| `PRAW_USER_AGENT`               | The user agent sent to Reddit when making PRAW queries                                | No       | `Checks if users are banned for our synced discord and keeps flairs synced` |
| `PRAW_USERNAME`                 | The username of the user used for PRAW queries                                        | No       | `HWSUKMods`                                                                 |
| `REACTION_CHANNEL_ID`           | The channel ID used for feedback                                                      | Yes      |                                                                             |
| `MOD_CHANNEL_ID`                | The channel ID used for mod notifications of feedback items                           | Yes      |                                                                             |
| `REACTION_THRESHOLD`            | Determines how many upvotes a feedback submission needs before it is sent to the mods | Yes      |                                                                             |
| `BUY_SELL_CHANNEL_ID`           | The channel ID used for removing too frequent posts                                   | Yes      |                                                                             |
| `BUY_SELL_BACKUP_DM_CHANNEL_ID` | The channel ID used for notifying users of removed posts if they have DMs disabled    | No       | `292032782409007115`                                                        |
| `BUY_SELL_LIMIT_SECONDS`        | The number of seconds that each user post is limited to                               | Yes      | `259200`                                                                    |
| `DVLA_API_KEY`                  | Key for the DVLA API                                                                  | Yes      |                                                                             |
| `LOGGING_FILENAME`              | Determines the naming format used for log files                                       | No       | `f'bot-{datetime.now().strftime("%m-%d-%Y-%H%M%S")}.log'`                   |

## Contributing to this project

Please run black before committing code to this repo

```py
python3 -m black .
```
