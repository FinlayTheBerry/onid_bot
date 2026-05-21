#!/bin/python

import json
import os
import datetime
import time
import sys
import asyncio
import socket
import requests
import discord
import smtplib
from email.message import EmailMessage
import hmac
import hashlib
import base64
import secrets
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

# Bot authentication url:
# https://discord.com/oauth2/authorize?client_id={CLIENTID}

# region File IO
def IO_RealPath(filePath):
    return os.path.realpath(os.path.expanduser(filePath))
def IO_GetEnvironmentDir():
    return os.path.dirname(IO_RealPath(__file__))
def IO_WriteFile(filePath, contents, binary=False):
    filePath = IO_RealPath(filePath)
    fd = os.open(filePath, os.O_WRONLY | os.O_TRUNC)
    with open(fd, "wb" if binary else "w", encoding=None if binary else "utf-8") as f:
        f.write(contents)
def IO_AppendFile(filePath, contents, binary=False):
    filePath = IO_RealPath(filePath)
    fd = os.open(filePath, os.O_WRONLY | os.O_APPEND)
    with open(fd, "ab" if binary else "a", encoding=None if binary else "utf-8") as f:
        f.write(contents)
def IO_CreateFile(filePath, contents, mode, binary=False):
    filePath = IO_RealPath(filePath)
    fd = os.open(filePath, os.O_WRONLY | os.O_CREAT | os.O_EXCL, mode)
    with open(fd, "wb" if binary else "w", encoding=None if binary else "utf-8") as f:
        f.write(contents)
def IO_ReadFile(filePath, defaultContents=None, binary=False):
    filePath = IO_RealPath(filePath)
    try:
        with open(filePath, "rb" if binary else "r", encoding=None if binary else "utf-8") as f:
            return f.read()
    except FileNotFoundError:
        if defaultContents != None:
            return defaultContents
        else:
            raise
    if defaultContents != None and not os.path.exists(filePath):
        return defaultContents
def IO_SerializeJson(obj, compact=False):
    return json.dumps(obj, separators=(',', ':') if compact else None, indent=None if compact else 4)
def IO_DeserializeJson(jsonString):
    return json.loads(jsonString)
def IO_GetEpoch():
    return time.time()
def IO_FormatEpoch(epoch):
    timestamp = datetime.datetime.fromtimestamp(epoch)
    return timestamp.strftime("%I:%M%p %m/%d").lower()
# endregion

# region Logs
def LOG_Generic(message, log_type, ansi_color):
    formatted_message = f"{log_type} - {IO_FormatEpoch(IO_GetEpoch())} {int(IO_GetEpoch())} - {message}"
    print(f"\033[{ansi_color}m{formatted_message}\033[0m", flush=True)
    log_path = os.path.join(IO_GetEnvironmentDir(), "log.txt")
    if not os.path.exists(log_path):
        IO_CreateFile(log_path, f"{formatted_message}\n", 0o600)
    else:
        IO_AppendFile(log_path, f"{formatted_message}\n")
def LOG_Info(message):
    LOG_Generic(message, "Info", "37")
def LOG_Warning(message):
    LOG_Generic(message, "Warning", "33")
def LOG_Error(message):
    LOG_Generic(message, "ERROR", "31")
def LOG_Exception(ex):
    tb = ex.__traceback__
    tb_data = None
    while tb is not None:
        if IO_RealPath(tb.tb_frame.f_code.co_filename) == IO_RealPath(__file__):
            message = repr(ex)
            funcname = "<module>" if tb.tb_frame.f_code.co_name == "<module>" else tb.tb_frame.f_code.co_name + "()"
            lineno = tb.tb_lineno
            line = IO_ReadFile(tb.tb_frame.f_code.co_filename).splitlines()[lineno - 1].strip()
            tb_data = { "message": message, "funcname": funcname, "lineno": lineno, "line": line }
        tb = tb.tb_next
    if tb_data == None:
        LOG_Generic(f"{repr(ex)} at unknown location", "PY_EX", "31")
    else:
        LOG_Generic(f"{tb_data['message']} in {tb_data['funcname']} line {tb_data['lineno']}: {tb_data['line']}", "PY_EX", "31")
# endregion

# region Environment
ENV = None
def ENV_Load():
    global ENV
    env_path = os.path.join(IO_GetEnvironmentDir(), "environment.json")
    ENV = IO_DeserializeJson(IO_ReadFile(env_path))
# endregion

# region Database
DB = None
def DB_Load():
    global DB
    db_path = os.path.join(IO_GetEnvironmentDir(), "database.json")
    DB = IO_DeserializeJson(IO_ReadFile(db_path))
    DB = { int(key): value for key, value in DB.items() }
def DB_Backup():
    db_path = os.path.join(IO_GetEnvironmentDir(), "database.json")
    backups_dir_path = os.path.join(IO_GetEnvironmentDir(), "backups")
    if not os.path.exists(backups_dir_path):
        os.mkdir(backups_dir_path, mode=0o700)
    backup_path = os.path.join(backups_dir_path, f"{int(IO_GetEpoch())}.json")
    IO_CreateFile(backup_path, IO_ReadFile(db_path), 0o600)
def DB_Save():
    db_path = os.path.join(IO_GetEnvironmentDir(), "database.json")
    IO_WriteFile(db_path, IO_SerializeJson(DB))
    backups_dir_path = os.path.join(IO_GetEnvironmentDir(), "backups")
    latest_backup_time = float("-inf")
    if os.path.exists(backups_dir_path):
        for backup_name in os.listdir(backups_dir_path):
            backup_time = int(os.path.splitext(backup_name)[0])
            if backup_time > latest_backup_time:
                latest_backup_time = backup_time
    if int(IO_GetEpoch()) - latest_backup_time > 24 * 60 * 60:
        DB_Backup()
def DB_Set(discord_user_id, onid_email, onid_name, notes=None):
    if discord_user_id in DB and notes == None:
        notes = DB[discord_user_id]['notes']
    elif notes == None:
        notes = ""
    DB[discord_user_id] = { "onid_email": onid_email, "onid_name": onid_name, "notes": notes }
    DB_Save()
# endregion

# region OSU API
def OSU_LookupOnidName(onid_email):
    # Get a token
    response = requests.post("https://api.oregonstate.edu/oauth2/token", data={"grant_type": "client_credentials"}, auth=(ENV['osu_api_id'], ENV['osu_api_secret']))
    response.raise_for_status()
    token = response.json()['access_token']

    # Send a request
    headers = { "Authorization": f"Bearer {token}", "Accept": "application/json" }
    response = requests.get(f"https://api.oregonstate.edu/v2/directory?filter[emailAddress]={onid_email}", headers=headers)
    response.raise_for_status()
    data = response.json()['data']

    # Return output or None
    if len(data) == 1:
        output = f"{data[0]['attributes']['firstName']} {data[0]['attributes']['lastName']}"
        return output
    else:
        return None
# endregion

# region COE SMTP
def SMTP_SendEmail(to, subject, body, body_html):
    SMTP_SERVER = "mail.engr.oregonstate.edu"
    SMTP_PORT = 465

    msg = EmailMessage()
    msg['Subject'] = subject
    msg['From'] = f"{ENV['email_username']}@oregonstate.edu"
    msg['To'] = to
    msg.set_content(body)
    msg.add_alternative(body_html, subtype="html")

    with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT) as smtp_server:
        smtp_server.login(ENV['email_username'], ENV['email_password'])
        smtp_server.send_message(msg)
# endregion

# region Tokens And Crypto
def TOKEN_SerializeAndSign(token_data):
    token_data["timestamp"] = int(IO_GetEpoch())
    payload = IO_SerializeJson(token_data, compact=True).encode("utf-8")
    nonce = secrets.token_bytes(16)
    b64_nonce = base64.urlsafe_b64encode(nonce).decode("utf-8").rstrip("=")
    encryptor = Cipher(algorithms.AES(bytes.fromhex(ENV['encryption_key'])), modes.CTR(nonce)).encryptor()
    ciphertext = encryptor.update(payload) + encryptor.finalize()
    b64_ciphertext = base64.urlsafe_b64encode(ciphertext).decode("utf-8").rstrip("=")
    signature = hmac.new(bytes.fromhex(ENV['signing_key']), f"{b64_nonce}.{b64_ciphertext}".encode("utf-8"), hashlib.sha256).digest()
    b64_signature = base64.urlsafe_b64encode(signature).decode("utf-8").rstrip("=")
    return f"{b64_nonce}.{b64_ciphertext}.{b64_signature}"
def TOKEN_DeserializeAndVerify(token):
    sections = token.split(".")
    if len(sections) != 3:
        return None
    b64_nonce = sections[0]
    b64_ciphertext = sections[1]
    b64_signature = sections[2]
    good_signature = hmac.new(bytes.fromhex(ENV['signing_key']), f"{b64_nonce}.{b64_ciphertext}".encode("utf-8"), hashlib.sha256).digest()
    b64_good_signature = base64.urlsafe_b64encode(good_signature).decode("utf-8").rstrip("=")
    if not hmac.compare_digest(b64_signature, b64_good_signature):
        return None
    nonce = base64.urlsafe_b64decode(b64_nonce.encode("utf-8") + b"===")
    ciphertext = base64.urlsafe_b64decode(b64_ciphertext.encode("utf-8") + b"===")
    decryptor = Cipher(algorithms.AES(bytes.fromhex(ENV['encryption_key'])), modes.CTR(nonce)).decryptor()
    payload = (decryptor.update(ciphertext) + decryptor.finalize()).decode("utf-8")
    return IO_DeserializeJson(payload)
def TOKEN_IsExpired(token_data):
    if int(IO_GetEpoch()) - token_data['timestamp'] > (60 * 60 * 24):
        return True
    return False
# endregion

discord_client = discord.Client(intents=discord.Intents.default())
discord_command_tree = discord.app_commands.CommandTree(discord_client)

# region Discord Helpers
def DIS_FormatUser(user):
    return f"User(\"{user.display_name}\", \"{user.name}\", {user.id})"
def DIS_FormatChannel(channel):
    return f"Channel(\"{channel.name}\", {channel.id})"
def DIS_FormatGuild(guild):
    return f"Guild(\"{guild.name}\", {guild.id})"
async def DIS_FetchGuild(guild_id):
    guild = discord_client.get_guild(guild_id)
    if guild is None:
        guild = await discord_client.fetch_guild(guild_id)
    return guild
async def DIS_FetchChannel(channel_id):
    channel = discord_client.get_channel(channel_id)
    if channel is None:
        channel = await discord_client.fetch_channel(channel_id)
    return channel
async def DIS_FetchUser(user_id):
    user = discord_client.get_user(user_id)
    if user is None:
        user = await discord_client.fetch_user(user_id)
    return user
async def DIS_FetchMember(member_id, guild):
    member = guild.get_member(member_id)
    if member is None:
        member = await guild.fetch_member(member_id)
    return member
def DIS_GetVerifiedRole(guild):
    for role in guild.roles:
        if role.name.lower() == "verified":
            return role
    return None
# endregion

# region Discord Interactions
@discord_client.event
async def on_ready():
    try:
        await discord_command_tree.sync()
        discord_client.add_view(GetVerifiedView())
        await discord_client.change_presence(activity=discord.CustomActivity("🛡️ Verifying OSU Students..."), status=discord.Status.online)
        LOG_Info(f"Bot Online - {socket.gethostname()} - {DIS_FormatUser(discord_client.user)}")
    except Exception as ex:
        LOG_Exception(ex)
@discord_client.event
async def on_guild_join(guild: discord.Guild):
    try:
        LOG_Info(f"Join Guild - {DIS_FormatGuild(guild)}")
    except Exception as ex:
        LOG_Exception(ex)
class GetVerifiedView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
    @discord.ui.button(label="Get Verified!", style=discord.ButtonStyle.primary, emoji="🛡️", custom_id="get_verified_button")
    async def DIS_GetVerifiedButton(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            if interaction.user.id in DB:
                await interaction.response.defer(ephemeral=True)
                verified_role = DIS_GetVerifiedRole(interaction.guild)
                if verified_role == None:
                    LOG_Warning(f"Get Verified - Refresh - Role Missing - {DIS_FormatUser(interaction.user)} - {DIS_FormatGuild(interaction.guild)}")
                    await interaction.followup.send(f"The Verified role does not exist on this server so ONIDbot couldn't give it to you. Please contact the server administrators to report this issue so they can create the Verified role.", ephemeral=True)
                    return
                try:
                    await interaction.user.add_roles(verified_role)
                except discord.errors.Forbidden as ex:
                    LOG_Warning(f"Get Verified - Refresh - No Manage Roles Perm - {DIS_FormatUser(interaction.user)} - {DIS_FormatGuild(interaction.guild)}")
                    await interaction.followup.send(f"ONIDbot doesn't have permission to give you the Verified role on this server. Please contact the server administrators to report this issue so they can grant ONIDbot the needed permissions.", ephemeral=True)
                    return
                LOG_Info(f"Get Verified - Refresh - Verified - {DIS_FormatUser(interaction.user)} - {DIS_FormatGuild(interaction.guild)}")
                await interaction.followup.send(f"You are already verified with ONIDbot and have been given the Verified role on this server as well.", ephemeral=True)
                return
            else:
                LOG_Info(f"Get Verified - Modal - Sending Modal - {DIS_FormatUser(interaction.user)} - {DIS_FormatGuild(interaction.guild)}")
                await interaction.response.send_modal(OnidInputModal())
                return
        except Exception as ex:
            LOG_Exception(ex)
class OnidInputModal(discord.ui.Modal):
    def __init__(self):
        super().__init__(title="Enter OSU Email", custom_id="onid_input_modal", timeout=None)
    onid_input = discord.ui.TextInput(label="Enter your @oregonstate.edu email address:", placeholder="onid@oregonstate.edu", required=True, custom_id="onid_text_input")
    async def on_submit(self, interaction: discord.Interaction):
        try:
            await interaction.response.defer(ephemeral=True)
            if interaction.user.id in DB:
                verified_role = DIS_GetVerifiedRole(interaction.guild)
                if verified_role == None:
                    LOG_Warning(f"Onid Input - Refresh - Role Missing - {DIS_FormatUser(interaction.user)} - {DIS_FormatGuild(interaction.guild)}")
                    await interaction.followup.send(f"The Verified role does not exist on this server so ONIDbot couldn't give it to you. Please contact the server administrators to report this issue so they can create the Verified role.", ephemeral=True)
                    return
                try:
                    await interaction.user.add_roles(verified_role)
                except discord.errors.Forbidden as ex:
                    LOG_Warning(f"Onid Input - Refresh - No Manage Roles Perm - {DIS_FormatUser(interaction.user)} - {DIS_FormatGuild(interaction.guild)}")
                    await interaction.followup.send(f"ONIDbot doesn't have permission to give you the Verified role on this server. Please contact the server administrators to report this issue so they can grant ONIDbot the needed permissions.", ephemeral=True)
                    return
                LOG_Info(f"Onid Input - Refresh - Verified - {DIS_FormatUser(interaction.user)} - {DIS_FormatGuild(interaction.guild)}")
                await interaction.followup.send(f"You are already verified with ONIDbot and have been given the Verified role on this server as well.", ephemeral=True)
                return
            else:
                onid_email = str(self.onid_input.value).strip().lower()
                if not onid_email.endswith("@oregonstate.edu"):
                    LOG_Warning(f"Onid Input - Flow - Bad Suffix - \"{self.onid_input.value}\" - {DIS_FormatUser(interaction.user)} - {DIS_FormatGuild(interaction.guild)}")
                    await interaction.followup.send(f"The email address provided must end with @oregonstate.edu. Please try again.", ephemeral=True)
                    return
                onid_name = OSU_LookupOnidName(onid_email)
                if onid_name == None:
                    LOG_Warning(f"Onid Input - Flow - No Directory - \"{self.onid_input.value}\" - {DIS_FormatUser(interaction.user)} - {DIS_FormatGuild(interaction.guild)}")
                    await interaction.followup.send(f"That email address couldn't be found in the OSU directory. If you have multiple OSU emails, use the one with first name then first letter of last name. So John Doe would use doej@oregonstate.edu. Please try again.", ephemeral=True)
                    return
                token_data = { "guild_id": interaction.guild.id, "user_id": interaction.user.id, "onid_email": onid_email, "onid_name": onid_name }
                token = TOKEN_SerializeAndSign(token_data)
                subject = IO_ReadFile(os.path.join(IO_GetEnvironmentDir(), "email", "subject.txt")).replace("{TOKEN}", token).replace("{ENV_NAME}", os.path.basename(os.getcwd()))
                body = IO_ReadFile(os.path.join(IO_GetEnvironmentDir(), "email", "email.txt")).replace("{TOKEN}", token).replace("{ENV_NAME}", os.path.basename(os.getcwd()))
                body_html = IO_ReadFile(os.path.join(IO_GetEnvironmentDir(), "email", "email.html")).replace("{TOKEN}", token).replace("{ENV_NAME}", os.path.basename(os.getcwd()))
                SMTP_SendEmail(onid_email, subject, body, body_html)
                LOG_Info(f"Onid Input - Flow - Email Sent - \"{self.onid_input.value}\" - {DIS_FormatUser(interaction.user)} - {DIS_FormatGuild(interaction.guild)} - {IO_SerializeJson(token_data, compact=True)}")
                await interaction.followup.send(f"A verification link has been sent to **{onid_email}**.\n\nLinks can take up to 5 minutes to arrive. Please, check your **SPAM** folder before requesting a new link.", ephemeral=True)
                return
        except Exception as ex:
            LOG_Exception(ex)
@discord_command_tree.command(name="post_verification_button", description="Posts the verification instructions and button in the current channel.")
async def DIS_PostVerificationButton(interaction: discord.Interaction):
    try:
        await interaction.response.defer(ephemeral=True)
        if not interaction.user.guild_permissions.administrator:
            LOG_Info(f"Post Button - No Admin - {DIS_FormatUser(interaction.user)} - {DIS_FormatGuild(interaction.guild)}")
            await interaction.followup.send("You need the administrator permission on this server to run this command.")
            return
        try:
            message = f"Welcome to the {interaction.guild.name} Discord server!\n\n:shield: To gain access to the rest of the server, you must **verify** your status as an OSU student.\n\n:one: Enter your **@oregonstate.edu** email address and wait for a confirmation email.\n:two: Next, click the provided link and the rest of the server will be **unlocked** for you.\n\n:interrobang: If you need help, feel free to DM me (<@{discord_client.application.owner.id}>) anytime."
            await interaction.channel.send(message, view=GetVerifiedView())
        except discord.errors.Forbidden as ex:
            LOG_Info(f"Post Button - EPERM - {DIS_FormatUser(interaction.user)} - {DIS_FormatGuild(interaction.guild)}")
            await interaction.followup.send(f"{discord_client.user.mention} does not have permission to post messages in this channel and therefore could not post the verification buttons.", ephemeral=True)
            return
        LOG_Info(f"Post Button - Success - {DIS_FormatUser(interaction.user)} - {DIS_FormatGuild(interaction.guild)}")
        await interaction.followup.send("Done!")
        return
    except Exception as ex:
        LOG_Exception(ex)
@discord_command_tree.command(name="get_verification_info", description="Prints all the information ONIDbot has about a given Discord user.")
async def DIS_GetVerificationInfo(interaction: discord.Interaction, user: discord.User):
    try:
        await interaction.response.defer(ephemeral=True)
        if not interaction.user.id in DB:
            LOG_Warning(f"Get Info - Requester Not Verified - {DIS_FormatUser(interaction.user)} - {DIS_FormatUser(user)} - {DIS_FormatGuild(interaction.guild)}")
            await interaction.followup.send("You must be verified by ONIDbot to run this command.", ephemeral=True)
            return
        elif user.id in DB:
            LOG_Info(f"Get Info - Success (Verified) - {DIS_FormatUser(interaction.user)} - {DIS_FormatUser(user)} - \"{DB[user.id]['onid_name']}\" {DB[user.id]['onid_email']} - {DIS_FormatGuild(interaction.guild)}")
            await interaction.followup.send(f"{user.mention} is verified as \"{DB[user.id]['onid_name']}\" {DB[user.id]['onid_email']}.", ephemeral=True)
            return
        else:
            LOG_Info(f"Get Info - Success (Not Verified) - {DIS_FormatUser(interaction.user)} - {DIS_FormatUser(user)} - {DIS_FormatGuild(interaction.guild)}")
            await interaction.followup.send(f"{user.mention} is not verified.", ephemeral=True)
            return
    except Exception as ex:
        LOG_Exception(ex)
@discord_command_tree.command(name="debug_verification", description="Used to debug ONIDbot. Restricted to ONIDbot developers only.")
async def DIS_DebugVerification(interaction: discord.Interaction, command: str):
    try:
        await interaction.response.defer(ephemeral=True)
        if not interaction.user.id in ENV["debug_users"]:
            LOG_Info(f"Debug - Untrusted User - {DIS_FormatUser(interaction.user)} - {DIS_FormatGuild(interaction.guild)}")
            await interaction.followup.send("You must be an ONIDbot developer to run this command.", ephemeral=True)
            return

        try:
            command = command.split(" ", maxsplit=1)
            verb = command[0].lower()
            args = None
            if len(command) > 1:
                args = command[1]

            if verb == "rename_role":
                discord_guild_id = args.split(" ", maxsplit=1)[0]
                guild = await DIS_FetchGuild(discord_guild_id)
                for role in guild.roles:
                    if role.name == "ONID-Verified":
                        await role.edit(name="Verified")
                        await interaction.followup.send("Done!", ephemeral=True)
                        return
                await interaction.followup.send("No role with target name :(", ephemeral=True)
            elif verb == "token_info":
                data = TOKEN_DeserializeAndVerify(args)
                await interaction.followup.send(IO_SerializeJson(data), ephemeral=True)
            elif verb == "db_unverify":
                if not int(args) in DB:
                    raise Exception(f"{int(args)} not in DB.")
                del DB[int(args)]
                DB_Save()
                await interaction.followup.send("Done!", ephemeral=True)
            elif verb == "manual_verify":
                discord_user_id, discord_guild_id, onid_email, onid_name = args.split(" ", maxsplit=3)
                response = await DIS_Verify(discord_user_id, discord_guild_id, onid_email, onid_name)
                if response != None:
                    raise Exception(response)
                await interaction.followup.send("Done!", ephemeral=True)
            elif verb == "dis_get_guild":
                discord_guild = await discord_client.fetch_guild(int(args))
                await interaction.followup.send(DIS_FormatGuild(discord_guild), ephemeral=True)
            elif verb == "dis_get_channel":
                discord_channel = await discord_client.fetch_channel(int(args))
                await interaction.followup.send(DIS_FormatChannel(discord_channel), ephemeral=True)
            elif verb == "dis_get_user":
                discord_user = await discord_client.fetch_user(int(args))
                await interaction.followup.send(DIS_FormatUser(discord_user), ephemeral=True)
            elif verb == "dis_rm_message":
                discord_channel_id, discord_message_id = args.split(" ")
                discord_channel = await discord_client.fetch_channel(int(discord_channel_id))
                discord_message = await discord_channel.fetch_message(int(discord_message_id))
                await discord_message.delete()
                await interaction.followup.send("Done!", ephemeral=True)
            elif verb == "dis_post_button":
                discord_channel = await discord_client.fetch_channel(int(args))
                await discord_channel.send("", view=GetVerifiedView())
                await interaction.followup.send("Done!", ephemeral=True)
            elif verb == "dis_post_instructions":
                discord_channel = await discord_client.fetch_channel(int(args))
                message = f"Welcome to the {discord_channel.guild.name} Discord server!\n\n:shield: To gain access to the rest of the server, you must **verify** your status as an OSU student.\n\n:one: Enter your **@oregonstate.edu** email address and wait for a confirmation email.\n:two: Next, click the provided link and the rest of the server will be **unlocked** for you.\n\n:interrobang: If you need help, feel free to DM me (<@{discord_client.application.owner.id}>) anytime."
                await discord_channel.send(message)
                await interaction.followup.send("Done!", ephemeral=True)
            elif verb == "osu_api_lookup":
                data = OSU_LookupOnidName(args)
                await interaction.followup.send(data, ephemeral=True)
            elif verb == "env_reload":
                ENV_Load()
                await interaction.followup.send("Done!", ephemeral=True)
            elif verb == "db_get":
                await interaction.followup.send(IO_SerializeJson(DB[int(args)]), ephemeral=True)
            elif verb == "db_reload":
                DB_Load()
                await interaction.followup.send("Done!", ephemeral=True)
            elif verb == "db_save":
                DB_Save()
                await interaction.followup.send("Done!", ephemeral=True)
            elif verb == "db_backup":
                DB_Backup()
                await interaction.followup.send("Done!", ephemeral=True)
            else:
                raise Exception(f"Unknown verb {verb}.")
        except Exception as ex:
            await interaction.followup.send(repr(ex), ephemeral=True)
    except Exception as ex:
        LOG_Exception(ex)
# endregion

# region API Server
async def API_ProcessRequest(request):
    try:
        data = TOKEN_DeserializeAndVerify(request)
        if data is None:
            LOG_Warning(f"API - Invalid Token - {request}")
            return "error", "Invalid Link", f"This link is invalid. Please request a new one from ONIDbot. If the issue persists please DM @finlaytheberry to report this issue."
        if TOKEN_IsExpired(data):
            LOG_Warning(f"API - Expired Token - {IO_SerializeJson(data, compact=True)}")
            return "error", "Link Expired", "This link has expired. Please request a new one from ONIDbot."

        DB_Set(data['user_id'], data['guild_id'], data['onid_name'])

        guild = await DIS_FetchGuild(data['guild_id'])
        if guild == None:
            LOG_Warning(f"API - Bad Guild ID - {IO_SerializeJson(data, compact=True)}")
            return "error", "An Error Occurred", f"Please DM @finlaytheberry to report this issue. Error details: An internal server error occurred."
        member = await DIS_FetchMember(data['user_id'], guild)
        if member == None:
            LOG_Warning(f"API - Bad User ID - {DIS_FormatGuild(guild)} - {IO_SerializeJson(data, compact=True)}")
            return "error", "An Error Occurred", f"Please DM @finlaytheberry to report this issue. Error details: An internal server error occurred."

        verified_role = DIS_GetVerifiedRole(guild)
        if verified_role == None:
            LOG_Warning(f"API - Role Missing - {DIS_FormatUser(member)} - {DIS_FormatGuild(guild)} - {IO_SerializeJson(data, compact=True)}")
            return "error", "Role Missing", f"The Verified role does not exist on the <strong>{guild.name}</strong> Discord server so ONIDbot couldn't give it to you. Please contact the server administrators to report this issue so they can create the Verified role."
        try:
            await member.add_roles(verified_role)
        except discord.errors.Forbidden as ex:
            LOG_Warning(f"API - No Manage Roles Perm - {DIS_FormatUser(member)} - {DIS_FormatGuild(guild)} - {IO_SerializeJson(data, compact=True)}")
            return "error", "Permission Denied", f"ONIDbot doesn't have permission to give you the Verified role on the <strong>{guild.name}</strong> Discord server. Please contact the server administrators to report this issue so they can grant ONIDbot the needed permissions."

        LOG_Info(f"API - Verified - {DIS_FormatUser(member)} - {DIS_FormatGuild(guild)} - {IO_SerializeJson(data, compact=True)}")
        return "success", "Verified!", f"You have been verified on the <strong>{guild.name}</strong> Discord server. You can safely close this window and return to Discord."
    except Exception as ex:
        LOG_Exception(ex)
        return "error", "An Error Occurred", f"Please DM @finlaytheberry to report this issue. Error details: An internal server error occurred."
async def API_ClientHandler(reader, writer):
    try:
        try:
            request = (await asyncio.wait_for(reader.readline(), timeout=2.0)).decode("utf-8").rstrip("\n")
            state, title, message = await API_ProcessRequest(request)
            response = (IO_SerializeJson({ "state": state, "title": title, "message": message }, compact=True) + "\n").encode("utf-8")
            writer.write(response)
            await asyncio.wait_for(writer.drain(), timeout=2.0)
        finally:
            writer.close()
            await asyncio.wait_for(writer.wait_closed(), timeout=2.0)
    except Exception as ex:
        LOG_Exception(ex)
async def API_RunServer():
    server = await asyncio.start_server(API_ClientHandler, "0.0.0.0", ENV['api_port'])
    LOG_Info(f"API Online - {socket.gethostname()}:{ENV['api_port']}.")
    async with server:
        await server.serve_forever()
# endregion

# region Main
async def Main():
    try:
        ENV_Load()
        DB_Load()
        await asyncio.gather(API_RunServer(), discord_client.start(ENV['discord_token']))
    except KeyboardInterrupt:
        sys.exit(0)
    except Exception as ex:
        LOG_Exception(ex)
        sys.exit(1)
asyncio.run(Main())
# endregion
