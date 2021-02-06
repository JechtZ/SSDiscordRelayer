import asyncio
import datetime
from datetime import datetime
import discord
import pytz
import os
import random
import re
import requests
import xml.etree.ElementTree as ElementTree
import math
import sys
import json

import settings

from StarSonataAPI import *
from StarSonataAPI.message_types import *

import struct

client = discord.Client()
ss = StarSonataAPI()


# read the mapping
channel_mappings = []
with open('mapping.json', 'r') as f:
  channel_mappings = json.loads(f.read())


def recv_mapping(channel):
  channels = []
  for mapping in channel_mappings:
    if TextMessage.channel_to_recv(mapping['STARSONATA_CHANNEL']) != channel:
      continue
    if mapping['MODE'] == 'READ' or mapping['MODE'] == 'BOTH':
      channels.append(client.get_channel(id=mapping['DISCORD_CHANNEL']))
  return channels

def send_mapping(channel):
  channels = []
  for mapping in channel_mappings:
    if mapping['DISCORD_CHANNEL'] != channel:
      continue
    if mapping['MODE'] == 'WRITE' or mapping['MODE'] == 'BOTH':
      channels.append(TextMessage.channel_to_send(mapping['STARSONATA_CHANNEL']))
  return channels


async def bboard():
  channel = client.get_channel(id=int(os.environ.get('BULLETIN_BOARD_CH')))
  post_id = None
  source = 'http://starsonata.com/ss_api/bboard.xml'

  regexp = re.compile(r'@((?:[^@:#]|(?:```))+?)#\d{4}?')

  while not client.is_closed():
    with requests.get(source) as request:
      tree = ElementTree.fromstring(request.content)

      update = datetime.now(pytz.timezone('America/New_York'))
      update_str = 'Last updated: %s (%s)\n' % (update.strftime('%Y-%m-%d %H:%M:%S'), 'EDT' if update.dst() else 'EST')
      update_len = len(update_str)

      posts = []
      for entry in tree:
        notice = regexp.sub(r'\1', entry.attrib['notice'])
        posts.append({
          'author': entry.attrib['author'],
          'credits': float(entry.attrib['credits']),
          'notice': notice
        })
      posts.sort(key=lambda p: p['credits'])

      content = ''
      for post in posts:
        old = content
        content = '%s\n%s at %s credits\n%s\n%s' % (
          post['notice'],
          post['author'],
          f"{int(post['credits']):,}",
          '=' * 10,
          content
        )
        if len(content) + update_len + 3 > 2000:
          content = old
          break
      content = '\n%s\n\n%s' % (content, update_str)

    if post_id is None:
      try:
        message = await channel.fetch_message(channel.last_message_id)
        if message:
          post_id = message.id
      except:
        pass
    if post_id:
      message = await channel.fetch_message(post_id)
      await message.edit(content=content)
    else:
      post_id = (await channel.send(content)).id
    await asyncio.sleep(300)


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

  message = ''
  if username in tm:
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

print(f'BobboBot running on discord.py version {discord.__version__}')
print('Starting bot')
client.run(os.environ.get('DISCORD_TOKEN'))
