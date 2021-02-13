import asyncio
import datetime
from datetime import datetime, timedelta
import discord
import pytz
import os
import random
import re
import xml.etree.ElementTree as ElementTree
import math
import sys
import json

from StarSonataAPI import *
from StarSonataAPI.message_types import *

import struct

client = discord.Client()
ss = StarSonataAPI()


# read the mapping
channel_mappings = []
with open('/mapping.json', 'r') as f:
  channel_mappings = json.loads(f.read())

# make sure the mapping is valid
for mapping in channel_mappings:
  if 'STARSONATA_CHANNEL' not in mapping:
    raise KeyError('STARSONATA_CHANNEL')
  if 'DISCORD_CHANNEL' not in mapping:
    raise KeyError('DISCORD_CHANNEL')
  if 'MODE' not in mapping:
    raise KeyError('MODE')


# read alerts
alerts = []
with open('/alerts.json', 'r') as f:
  alerts = json.loads(f.read())

# make sure it's valid/precompile the regex
for alert in alerts:
  alert['_regexp'] = re.compile(alert['pattern'])
  alert['_next'] = datetime.now()


def recv_mapping(channel):
  channels = []
  for mapping in channel_mappings:
    if TextMessage.channel_to_recv(mapping['STARSONATA_CHANNEL']) != channel:
      continue
    if 'r' in mapping['MODE']:
      channels.append(client.get_channel(id=mapping['DISCORD_CHANNEL']))
  return channels


def send_mapping(channel):
  channels = []
  for mapping in channel_mappings:
    if mapping['DISCORD_CHANNEL'] != channel:
      continue
    if 'w' in mapping['MODE']:
      channels.append(TextMessage.channel_to_send(mapping['STARSONATA_CHANNEL']))
  return channels


@ss.on_event(SC_CHARACTERLIST)
async def choose_character(message):
  data = message.payload
  count = struct.unpack('<h', data[:2])[0]
  characters = []
  offset = 2
  for i in range(count):
    character_id = struct.unpack('<I', data[offset:offset+4])[0]
    offset += 4
    name = ''
    while data[offset] != 0:
      name += chr(data[offset])
      offset += 1
    offset += 1 # skip nul terminator
    level = struct.unpack('<i', data[offset:offset+4])[0]
    offset += 4
    money = struct.unpack('<q', data[offset:offset+8])[0]
    offset += 8
    class_name = ''
    while data[offset] != 0:
      class_name += chr(data[offset])
      offset += 1
    offset += 1
    visage = struct.unpack('<i', data[offset:offset+4])[0]
    offset += 4

    has_skins = data[offset]
    offset += 1
    if has_skins:
      pass

    characters.append(Character(character_id, name, class_name, level, money))

  character_index = int(os.environ.get('RELAY_CHARACTER'))
  await ss.character_select(characters[character_index].character_id)


@ss.on_event(SC_TEXTMESSAGE)
async def text_message(message):
  tm = TextMessage()
  tm.buf_in(message.payload)

  for alert in alerts:
    if alert['_next'] > datetime.now():
      continue
    regexp = alert['_regexp']
    match = re.search(regexp, tm.message)
    if match:
      extracted = match.groupdict()
      if 'ignore' in alert:
        ignore = False
        for case in alert['ignore']:
          k,v = case.split('=')
          if k in extracted and extracted[k] == v:
            ignore = True
        if ignore:
          continue
      alert['_next'] = datetime.now() + timedelta(minutes=10)
      message = alert['message'].format(**extracted)
      if 'mentions' in alert and len(alert['mentions']):
        message += ' - ' + ', '.join([f'<@&{id}>' for id in alert['mentions']])

      for channel in alert['channels']:
        await client.get_channel(id=channel).send(message)

  message = ''
  if tm.username is not None:
    message = f'**[{tm.username}]** {tm.message}'
  else:
    message = f'{tm.message}'

  channels = recv_mapping(tm.type)
  for channel in channels:
    await channel.send(message)


@ss.on_event(SC_TEAMMEMBER)
async def team_member(message):
  data = message.payload
  offset = 0
  (persona,) = struct.unpack('<i', data[offset:offset+4])
  offset += 4
  name = ''
  while data[offset] != 0:
    name += chr(data[offset])
    offset += 1
  offset += 1
  (rank, lastOn) = struct.unpack('<hi', data[offset:])

  action = None
  if lastOn == -1:
    action = 'on'
  elif lastOn == 0:
    action = 'off'
  else:
    return

  if os.environ.get('TEAM_MEMBER_STATUS', False):
    message = f'**{name}** has logged {action}'
    channels = recv_mapping(TextMessage.channel_to_recv('TEAM'))
    for channel in channels:
      await channel.send(message)


@client.event
async def on_ready():
  print('Logged in as')
  print(client.user.name)
  print(client.user.id)
  print('------')

  print('Registering tasks')
  if os.environ.get('BULLETIN_BOARD_CH'):
    client.loop.create_task(bboard())

  username = os.environ.get('RELAY_USERNAME')
  password = os.environ.get('RELAY_PASSWORD')

  client.loop.create_task(ss.run(Account(username, password)))


@client.event
async def on_message(message):
  if message.author.id == client.user.id:
    return
  if len(message.embeds):
    return

  if message.content == '!restart':
    sys.exit(0)

  channel = message.channel
  chats = send_mapping(channel.id)
  for chat in chats:
    tm = TextMessage()
    tm.type = chat
    reference = message.reference.resolved if message.reference is not None else None
    if reference is not None:
      if isinstance(reference, discord.DeletedReferencedMessage):
        tm.message = f'[{message.author.display_name} (replying to deleted)] {message.content}'
      else:
        tm.message = f'[{message.author.display_name} (replying to {reference.author.display_name}] {message.content}'
    else:
      tm.message = f'[{message.author.display_name}] {message.content}'
    for mention in message.mentions:
      tm.message = tm.message.replace(f'<@!{mention.id}>', f'@{mention.name}')
    for mention in message.role_mentions:
      tm.message = tm.message.replace(f'<@&{mention.id}>', f'@{mention.name}')
    for mention in message.channel_mentions:
      tm.message = tm.message.replace(f'<#{mention.id}>', f'#{mention.name}')
    await ss.send_message(tm)


# check we have everything set
if os.environ.get('RELAY_USERNAME') is None:
  raise Exception('RELAY_USERNAME not set.')
if os.environ.get('RELAY_PASSWORD') is None:
  raise Exception('RELAY_PASSWORD not set.')
if os.environ.get('RELAY_CHARACTER') is None:
  raise Exception('RELAY_CHARACTER not set.')


print(f'Relayer running on discord.py version {discord.__version__}')
print('Starting bot')
client.run(os.environ.get('DISCORD_TOKEN'))
