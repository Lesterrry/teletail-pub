#!/usr/bin/env python3
'''''''''''''''''''''''''''''
COPYRIGHT LESTERRRY,
2022

'''''''''''''''''''''''''''''
from telethon import TelegramClient, events, sync
from telethon.tl.types import Channel, UserStatusOnline, UpdateUserStatus, Dialog, User, PeerNotifySettings, PeerUser, MessageMediaPhoto, MessageMediaDocument
from aioconsole import ainput
from datetime import datetime, timezone
from pathlib import Path
import yaml
import asyncio
import os
import fcntl
import sys

RED = "\033[31m"
GRN = "\033[32m"
ORG = "\033[33m"
CYN = "\033[36m"
MAG = "\033[95m"
GRA = "\033[90m"
BLD = "\033[1m"
RES = "\033[0m"

def my_except_hook(exctype, value, traceback):
	if exctype is KeyboardInterrupt:
		print(STRINGS['keyboard_interrupt'])
		return
	print(f'{RED + BLD}FATAL:{RES} {value}')
	exit(1)
sys.excepthook = my_except_hook

API_ID = ***
API_HASH = ***
CLIENT = TelegramClient('session_name', API_ID, API_HASH)
VERSION = "Teletail 0.2.2"
MARKERS = {
	'role_bot': f"{CYN}[BOT]{RES}",
	'role_channel': f"{CYN}[CHANNEL]{RES}",
	'message_edited': f"{ORG}[:]{RES}",
	'message_deleted': f"{RED}[X]{RES}",
	'message_foreign': f"{MAG}[/]{RES}",
	'status_online': f"{GRN}[*]{RES}",
	'status_unread': f"{ORG}[?]{RES}",
	'type_none': "<NONE>",
	'type_photo': "<PHOTO>",
	'type_voice': "<VOICE>",
	'type_sticker': "<STICKER>",
	'type_videomsg': "<VIDEOMSG>",
	'type_document': "<DOC>",
	'type_media': "<MEDIA>",
	'type_unknown': "<UNKNOWN>",
	'misc_arrow': "=>",
	'misc_reversed_arrow': "<=",
	'misc_outcoming_arrow': f"{GRA}>>{RES}",
	'misc_incoming_arrow': f"{GRN}<<{RES}",
	'misc_reply_outcoming_arrow': f"{GRA}>+{RES}",
	'misc_reply_incoming_arrow': f"{CYN}<+{RES}",
	'misc_divider': "========================================"
}
STRINGS = {
	'starting': "Starting...",
	'loading_chats': "Loading chats...",
	'loading_chat': "Loading chat...",
	'saved_messages': f"{CYN}Saved Messages{RES}",
	'by_you': "You: ",
	'all_chats': "All chats",
	'some_chats': "Some chats",
	'erroneous': f"{ORG}WARNING:{RES} Erroneous expression",
	'sending_disabled': f"{ORG}WARNING:{RES} Can't send anything here",
	'switching_disabled': f"{ORG}WARNING:{RES} Can't switch mode",
	'unknown_command': f"{ORG}WARNING:{RES} Unknown shout-command, use !commands",
	'disconnected': "Disconnected",
	'connected': "Connected",
	'exiting': "Exited Teletail",
	'keyboard_interrupt': " Use !exit or !выход to quit Teletail",
	'config_load_fail': f"{ORG}WARNING:{RES} unable to load config file",
	'update_fail': f"{RED}ERROR:{RES} unable to unblock update queue"
}
DEFAULT_CONFIG = {
	'send_read_receipts': True
}
COMMANDS = f"{BLD}INFO:{RES} commands(команды) sleep(сон) exit(выход) chats(чаты) upd(обн) ok(ок) config(конфиг)"

chats = []
messages = []
unread_outcoming_chat_ids = []
foreign_messaging_users_ids = []
state = 0
cached_state = None
current_chat = None
current_user_online = False
console_size_y, console_size_x = None, None
trailer_message, trailer_message_shown = None, 0
config = None
busy = False

class UnblockTTY:
	def __enter__(self):
		self.fd = sys.stdin.fileno()
		self.flags_save = fcntl.fcntl(self.fd, fcntl.F_GETFL)
		flags = self.flags_save & ~os.O_NONBLOCK
		fcntl.fcntl(self.fd, fcntl.F_SETFL, flags)

	def __exit__(self, *args):
		fcntl.fcntl(self.fd, fcntl.F_SETFL, self.flags_save)

# Events
@CLIENT.on(events.MessageEdited)
async def handler(event):
	if event.out or state != 2:
		return
	for i in messages:
		if i.id == event.original_update.message.id:
			dated = get_datetime_string()
			messages.insert(0, f"{GRA}{dated} {MARKERS['message_edited']}{trim_string(i.message, 20)} {MARKERS['misc_arrow']} {trim_string(event.message.message, 20)}")
			messages.pop()
			with UnblockTTY():
				clear_console()
				print_messages(messages, True)
			return
@CLIENT.on(events.MessageDeleted)
async def handler(event):
	if state != 2:
		return
	for i in messages:
		if i.id == event.deleted_id:
			dated = get_datetime_string()
			messages.insert(0, f"{GRA}{dated} {MARKERS['message_deleted']}{trim_string(i.message, 20)}")
			messages.pop()
			with UnblockTTY():
				clear_console()
				print_messages(messages, True)
			return
@CLIENT.on(events.MessageRead)
async def handler(event):
	global busy
	if not await busy_watchdog():
		return
	busy = True
	try:
		unread_outcoming_chat_ids.remove(event.original_update.peer.user_id)
	except:
		None
	match state:
		case 2:
			with UnblockTTY():
				clear_console()
				print_messages(messages, True)
		case 1:
			with UnblockTTY():
				clear_console()
				await init_chats(False)
	busy = False
@CLIENT.on(events.UserUpdate)
async def handler(event):
	global current_user_online, busy
	if type(event.original_update) is UpdateUserStatus:
		if not await busy_watchdog():
			return
		busy = True
		match state:
			case 1:
				with UnblockTTY():
					clear_console()
					await init_chats(False)
			case 2:
				if event.original_update.user_id != current_chat.message.peer_id.user_id:
					busy = False
					return
				current_user_online = type(event.original_update.status) is UserStatusOnline
				with UnblockTTY():
					clear_console()
					print_messages(messages, True)
		busy = False
@CLIENT.on(events.NewMessage)
async def handler(event):
	global messages, busy
	if not await busy_watchdog():
		return
	busy = True
	match state:
		case 1:
			with UnblockTTY():
				clear_console()
				await init_chats(False)
		case 2:
			if event.peer_id != current_chat.message.peer_id:
				if type(event.peer_id) is not PeerUser or event.peer_id.user_id in foreign_messaging_users_ids:
					busy = False
					return
				dated = get_datetime_string()
				messages.insert(0, f"{GRA}{dated} {MARKERS['message_foreign']}{get_name_from_chat(event.peer_id.user_id)}")
				foreign_messaging_users_ids.append(event.peer_id.user_id)
			else:	
				messages.insert(0, event.message)
			if len(messages) > 19:
				messages.pop()
			with UnblockTTY():
				clear_console()
				print_messages(messages, True)
				if config['send_read_receipts']:
					await event.message.mark_read()
		case _:
			busy = False
			return
	if not event.out:
		print('\a', end='', flush=True)
	busy = False

# Main interfaces
async def init_chats(loading):
	global current_chat, chats, messages, foreign_messaging_users_ids
	if loading:
		print_CR(STRINGS['loading_chats'])
	if len(messages) > 0:
		del messages[:]
	if len(chats) > 0:
		del chats[:]
	if len(foreign_messaging_users_ids) > 0:
		del foreign_messaging_users_ids[:]
	current_chat = None
	async for i in CLIENT.iter_dialogs():
		if not i.archived:
			chats.append(i)
	print_chats(loading)
def print_chats(loading):
	count = 1
	not_shown = False
	# has_pins = False
	for dialog in chats:
		if count > (console_size_y / 2) - 2 :
			not_shown = True
			break
		if not dialog.archived:
			# TODO (Maybe)
			# if dialog.pinned:
			# 	has_pins = True
			# elif has_pins:
			# 	print(MARKERS['misc_divider'])
			# 	count += 1
			# 	has_pins = False
			if dialog.is_user and dialog.entity.bot:
				role = MARKERS['role_bot']
			elif not dialog.is_user and not dialog.is_group:
				role = MARKERS['role_channel']
			else:
				role = ""
			online = MARKERS['status_online'] if type(dialog.entity) is User and type(dialog.entity.status) is UserStatusOnline and not dialog.entity.is_self else ""
			unread = MARKERS['status_unread'] if type(dialog.entity) is User and dialog.entity.id in unread_outcoming_chat_ids else ""
			name = STRINGS['saved_messages'] if type(dialog.entity) is User and dialog.entity.is_self else trim_string(dialog.name, 40)
			unread_count = f"{(MAG if dialog.dialog.notify_settings.silent is None and dialog.dialog.notify_settings.mute_until is None else GRA)}[{dialog.unread_count}]{RES}" if dialog.unread_count > 0 else ""
			spacer = " " if count < 10 else ""
			print(f"{count}. {spacer}{online}{unread}{role}{unread_count}{name}")
			message = MARKERS['type_none'] if dialog.message.message is None else trim_string(dialog.message.message, console_size_x - 15).replace('\n', ' ')
			media = get_media_description(dialog.message.media)
			out = STRINGS['by_you'] if dialog.message.out else ""
			print(f"        {GRA}{out}{media}{message}{RES}")
			count += 1
	shown = STRINGS['some_chats'] if not_shown else STRINGS['all_chats']
	print_trailer(shown, VERSION)
	if not loading:
		print_pointer()
async def init_messages(chat):
	global messages, state, current_chat, current_user_online
	print_CR(STRINGS['loading_chat'])
	if chat.is_user or chat.is_group:
		state = 2
	else:
		state = 3
	current_chat = chat
	current_user_online = type(chat.entity) is User and type(chat.entity.status) is UserStatusOnline and not chat.entity.is_self
	messages = await CLIENT.get_messages(chat, limit=20)
	print_messages(messages, False)
	if config['send_read_receipts']:
		await chat.message.mark_read()
def print_messages(messages, with_pointer):
	last_date = None
	for message in reversed(messages):
		if type(message) is str:
			print(message)
		else:
			date_obj = message.date.replace(tzinfo=timezone.utc).astimezone(tz=None)
			day = date_obj.strftime('%a %d.%m.%y')
			if last_date != day:
				print(f"{GRA}{day}{RES}")
				last_date = day
			date_string = date_obj.strftime('%H:%M')
			if message.reply_to is not None:
				dated = get_datetime_string()
				reply_to = MARKERS['type_unknown']
				for i in messages:
					if type(i) is str:
						continue
					if i.id == message.reply_to.reply_to_msg_id:
						reply_to = trim_string(i.message, 20)
				text = f"{reply_to} {MARKERS['misc_reversed_arrow']} {trim_string(message.message, 500)}"
				out = f"{MARKERS['misc_reply_outcoming_arrow']} " if message.out else f"{MARKERS['misc_reply_incoming_arrow']} "
			else:
				text = f" {MARKERS['type_none']}" if message.message is None else trim_string(message.message, 500)
				out = f"{MARKERS['misc_outcoming_arrow']} " if message.out else f"{MARKERS['misc_incoming_arrow']} "
			media = get_media_description(message.media)
			print(f"{GRA}{date_string}{RES} {out}{media}{text}")
	online = f"{MARKERS['status_online']}" if current_user_online else ""
	unread = f"{MARKERS['status_unread']}" if type(current_chat.entity) is User and current_chat.entity.id in unread_outcoming_chat_ids else ""
	print_trailer(f"{unread}{online}{current_chat.name}", VERSION)
	if with_pointer:
		print_pointer()

# Working with input
async def handle_input():
	while True:
		line = await ainput(get_pointer())
		if len(line) < 1:
			continue
		if line[0] == '!':
			await handle_shout_command(line)
		else:
			match state:
				case 1:
					with UnblockTTY():
						try:
							chat = chats[int(line) - 1]
							clear_trailer()
							clear_console()
							await init_messages(chat)
						except:
							update_trailer(STRINGS['erroneous'])
				case 2:
					message = await CLIENT.send_message(current_chat.id, line)
					if current_chat.entity.id not in unread_outcoming_chat_ids and not current_chat.entity.bot:
						unread_outcoming_chat_ids.append(current_chat.entity.id)
					messages.insert(0, message)
					if len(messages) > 19:
						messages.pop()
					with UnblockTTY():
						clear_console()
						print_messages(messages, False)
				case 3:
					update_trailer(STRINGS['sending_disabled'])
async def handle_shout_command(string):
	global state
	global cached_state
	global current_chat
	match string:
		case "!sleep" | "!сон":
			if CLIENT.is_connected():
				await CLIENT.disconnect()
				cached_state = state
				state = 4
				with UnblockTTY():
					clear_console()
					print(STRINGS['disconnected'])
			else:
				with UnblockTTY():
					await CLIENT.connect()
					state = cached_state
					cached_state = None
					await update_state()
		case "!exit" | "!выход":
			await CLIENT.disconnect()
			with UnblockTTY():
				clear_console()
				print(STRINGS['exiting'])
			exit(0)
		case "!chats" | "!чаты":
			match state:
				case 2 | 3:
					state = 1
					await update_state()
				case _:
					update_trailer(STRINGS['switching_disabled'])
		case "!upd" | "!обн":
			update_console_size()
			await update_state()
		case "!commands" | "!команды":
			update_trailer(COMMANDS)
		case "!ok" | "!ок":
			clear_trailer()
			update_state_friendly()
		case "!config" | "!конфиг":
			load_config()
			update_state_friendly()
		case _:
			update_trailer(STRINGS['unknown_command'])
async def update_state():
	clear_trailer()
	match state:
		case 1:
			with UnblockTTY():
				clear_console()
				await init_chats(True)
		case 2:
			with UnblockTTY():
				clear_console()
				await init_messages(current_chat)
def update_state_friendly():
	match state:
		case 1:
			with UnblockTTY():
				clear_console()
				print_chats(True)
		case 2:
			with UnblockTTY():
				clear_console()
				print_messages(messages, False)

# Core functions
async def busy_watchdog():
	global busy
	busycounter = 0
	while busy:
		await asyncio.sleep(1)
		busycounter += 1
		if busycounter > 10:
			update_trailer(STRINGS['update_fail'])
			busy = False
			return False
	return True
def get_datetime_string():
	p = "%H:%M"
	return datetime.now().strftime(p)
def trim_string(string, index):
	s = string
	if len(s) > index:
		return f"{s[:index]}..."
	else:
		return s
def update_console_size():
	global console_size_y, console_size_x
	f = os.popen('stty size', 'r')
	console_size_y, console_size_x = [int(i) for i in f.read().split()]
	f.close()
def clear_console():
	print("\033[0;0H", end='')
	for i in range(0, console_size_y * console_size_x):
		print(" ", end='')
	print("\033[0;0H", end='')
# TODO
# def add_tabs_to_string(string):
# 	_, columns = get_console_size()
# 	n = int(columns)
# 	ss = string.split('\n')
# 	for i in range(0, len(ss)):
# 		if len(ss[i]) <= n:
# 			continue
# 		for j in range(1, int((len(ss[i])) / (n if i > 0 else n + 1)) + 1):
# 			if j == 1:
# 				na = n - 9
# 			else:
# 				na = n - 9
# 			ss[i] = ss[i][:na * j] + "\n         " + ss[i][na * j:]
# 	return "\n         ".join(ss)
def print_CR(string):
	print(string, end=f"\033[{len(string)}D", flush=True)
def get_pointer():
	match state:
		case 1:
			p = '#'
		case 2:
			p = '%'
		case 3:
			p = '@'
		case 4:
			p = 'X'
		case _:
			p = ''
	return f"{p} > "
def print_pointer():
	print(get_pointer(), end='', flush=True)
def print_trailer(*stuff):
	global trailer_message, trailer_message_shown
	if trailer_message is None:
		print(get_datetime_string(), *stuff, sep=" • ")
	else:
		print(get_datetime_string(), trailer_message, sep=" • ")
		if trailer_message_shown > 2:
			clear_trailer()
		else:
			trailer_message_shown += 1
def update_trailer(message):
	if 0 <= state <= 3:
		global trailer_message, trailer_message_shown
		trailer_message, trailer_message_shown = message, 0
		update_state_friendly()
	else:
		print(message)
def clear_trailer():
	global trailer_message, trailer_message_shown
	trailer_message, trailer_message_shown = None, 0
def get_media_description(media):
	if media is not None:
		if type(media) is MessageMediaPhoto:
			s = f"{MARKERS['type_photo']} "
		elif type(media) is MessageMediaDocument:
			if media.document.mime_type == "audio/ogg":
				s = f"{MARKERS['type_voice']} "
			elif media.document.mime_type == "image/webp":
				s = f"{MARKERS['type_sticker']} "
			elif media.document.mime_type == "video/mp4":
				s = f"{MARKERS['type_videomsg']} "
			else:
				s = f"{MARKERS['type_document']} "
		else:
			s = f"{MARKERS['type_media']} "
	else:
		s = ""
	return s
def get_name_from_chat(id):
	for i in chats:
		try:
			if i.entity.id == id:
				return i.name
		except:
			None
	return MARKERS['type_unknown']
def load_config():
	global config
	try:
		home = str(Path.home())
		with open(f"{home}/teletail_config.yaml") as config_file:
			config = yaml.safe_load(config_file)
	except:
		update_trailer(STRINGS['config_load_fail'])
		config = DEFAULT_CONFIG

# Fun stuff
def send_animated_heart():
	None

####################################################
# MAIN PROCESS
####################################################
update_console_size()
clear_console()
print_CR(STRINGS['starting'])
load_config()
CLIENT.start()
CLIENT.loop.run_until_complete(init_chats(True))
state = 1
input_task = CLIENT.loop.create_task(handle_input())
CLIENT.loop.run_forever()
