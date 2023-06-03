# Relayer
A Star Sonata chat relay bot.

## Setup
Install [Docker](https://hub.docker.com/search?q=&type=edition&offering=community) and [docker-compose](https://docs.docker.com/compose/install/)

Sign up for [Discord Developer](https://discord.com/developers/applications) and create a bot.

Head to the OAuth2 tab, under the *OAuth2 URL Generator* section, check the *bot* scope and copy the generated URL. Paste this in your browser's address bar to invite the bot to your Discord server.

```bash
# clone a copy of the repository
git clone git@github.com:Delph/Relayer.git
cd Relayer

# grab the SS API dependency
git submodule update --init --recursive

# configure
nano bot.env
nano mapping.json

# build image
docker-compose build

# run it
docker-compose up -d
```

## Configuration
### bot.env
`bot.env` loads some core information required for the bot to run, all the keys listed in the sample below are required.
`RELAY_CHARACTER` is the character you wish to use to log in as, numbered in order they appear in the client, with `0` being the first one (i.e., 0 is the first character, `1` is the second character, `4` is the fifth character).

Sample file:
```
DISCORD_TOKEN=YourDiscordBotToken

# relay user
RELAY_USERNAME=ssUsername
RELAY_PASSWORD=ssPassword
RELAY_CHARACTER=0
```

### mapping.json
`mapping.json` defines what messages get relayed from what channels to what channels.

Sample file:
```json
[
  {
    "DISCORD_CHANNEL": 1,
    "STARSONATA_CHANNEL": "TEAM",
    "MODE": "rw"
  },
  {
    "DISCORD_CHANNEL": 2,
    "STARSONATA_CHANNEL": "ALL",
    "MODE": "r"
  }
]
```
* `DISCORD_CHANNEL` is the channel ID (turn on *Developer Mode* in *Settings -> Appearance*, right click on a channel to get it's ID).
* `STARSONATA_CHANEL` is the channel in game, valid options are `ALL`, `GALAXY`, `TEAM`, `TRADE`, `SQUAD` and `HELP`. Note that while `SQUAD` and `GALAXY` are options, the bot has no squad functionality and galaxy chat is unlikely to work.
* `MODE` is the relay mode, which can either be **r**ead, **w**rite, or both (`rw` or `wr`). Read means the messages are relayed to Discord, write means the messages are relayed to the game. **Do not use write mode for public chats**.

You can have as many relay options as you want and overlapping channels (e.g., you could setup an `#announcements` channel which is write only, and a team relay which is read-write).

### alerts.json
`alerts.json` defines what messages the bot should send alerts for.
Sample file:
```json
[
  {
    "name": "attack",
    "pattern": "^\\[WARNING\\] Base (?P<base>.*?) in (?P<galaxy>.*?) is under attack from player (?P<player>.*?)(?: on team (?P<team>.*?))?$",
    "channels": [804411672609161359],
    "message": "Station {base} in {galaxy} is under attack by {player} on team {team}",
    "mentions": [674207458045984801],
    "ignore": ["team=Deep Space Federation"]
  },
  {
    "name": "cutoff",
    "pattern": "^The following galax(?:ies are|y is) cut off from your HQ galaxy and will be unowned after 24 hours: (?P<galaxy>.*) \\((?P<time>.*)\\)$",
    "channels": [804411672609161359],
    "message": "{galaxy} is cutoff from the HQ",
    "mentions": [720637616621355029]
  }
]
```
* `name` is an internal name used to reference the alert
* `pattern` is a Python regular expression to match an incoming message from Star Sonata against. Regular expressions can be tested on [regex101.com](https://regex101.com). Note that named capture groups are used in the pattern
* `channels` is a list of channel IDs of where to send the alert to
* `message` is the message to send to `channels`, any captured value from `pattern` can be used and substituted
* `mentions` is a list of user or role IDs to mention in the message (although, this could be baked directly into `message`).
* `ignore` is a list of conditions on when to ignore an alert, again, matching on captured groups from `pattern`. This allows you filter out self-attack alerts and such.

You can have as many alerts as you wish, but do note they are only one way.

## Commands
Currently the bot has one command, `!restart`, occasionally the connection to the game server can be lost and the bot doesn't become aware to automatically reconnect to it. In these instances the restart command can be used.
