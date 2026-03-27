#!/usr/bin/python3

import json
import os
import requests
from datetime import datetime, timezone
import time
import discord
import sys
import secrets
import smtplib
from email.message import EmailMessage
import asyncio
import time
import socket

# Bot authentication url:
# https://discord.com/oauth2/authorize?client_id={CLIENTID}

# region File IO
def IO_RealPath(filePath):
    return os.path.realpath(os.path.expanduser(filePath))
def IO_GetScriptDir():
    return os.path.dirname(IO_RealPath(__file__))
def IO_WriteFile(filePath, contents, binary=False):
    filePath = IO_RealPath(filePath)
    with open(filePath, "wb" if binary else "w", encoding=None if binary else "utf-8") as f:
        f.write(contents)
def IO_ReadFile(filePath, defaultContents=None, binary=False):
    filePath = IO_RealPath(filePath)
    if defaultContents != None and not os.path.exists(filePath):
        return defaultContents
    with open(filePath, "rb" if binary else "r", encoding=None if binary else "utf-8") as f:
        return f.read()
def IO_SerializeJson(obj, compact=False):
    return json.dumps(obj, indent=None if compact else 4)
def IO_DeserializeJson(jsonString):
    return json.loads(jsonString)
def IO_GetEpoch():
    return time.time() + time.localtime().tm_gmtoff
def IO_GetTime():
    epoch = IO_GetEpoch()
    timestamp = datetime.fromtimestamp(epoch, tz=timezone.utc)
    return timestamp.strftime("%I:%M%p %m/%d").lower()
# endregion

# region Logs
def Log_Generic(message, log_type, ansi_color):
    padding = " " * (8 - len(log_type)) if len(log_type) < 8 else ""
    formatted_message = f"{log_type}{padding}({IO_GetTime()} {int(IO_GetEpoch())}): {message}"
    print(f"\033[{ansi_color}m{formatted_message}\033[0m", flush=True)
    log_path = os.path.join(IO_GetScriptDir(), "log.txt")
    log_contents = ""
    if os.path.exists(log_path):
        log_contents = IO_ReadFile(log_path)
    IO_WriteFile(log_path, log_contents + f"{formatted_message}\n")
def Log_Info(message):
    Log_Generic(message, "Info", "37")
def Log_Warning(message):
    Log_Generic(message, "Warning", "33")
def Log_Error(message):
    Log_Generic(message, "ERROR", "31")
def Log_Exception(ex):
    tb = ex.__traceback__
    while tb is not None:
        if IO_RealPath(tb.tb_frame.f_code.co_filename) == IO_RealPath(__file__):
            message = str(ex)
            funcname = "<module>" if tb.tb_frame.f_code.co_name == "<module>" else tb.tb_frame.f_code.co_name + "()"
            lineno = tb.tb_lineno
            line = IO_ReadFile(tb.tb_frame.f_code.co_filename).splitlines()[lineno - 1].strip()
            Log_Generic(f"{message} in {funcname} line {lineno}: {line}", "ERROR", "31")
            return
        tb = tb.tb_next
    Log_Generic(f"{str(ex)} at unknown location", "ERROR", "31")
# endregion

# region Randomness
def GetRandomCode():
    charset = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    output = []
    for _ in range(6):
        while True:
            i = int.from_bytes(secrets.token_bytes(1), byteorder="little") & 0x3F
            if i > 35:
                continue
            output.append(charset[i])
            break
    return "".join(output)
# endregion

# region Environment
ENV = None
def Env_Load():
    global ENV
    env_path = os.path.join(IO_GetScriptDir(), "environment.json")
    if os.stat(env_path).st_mode != 33152:
        raise Exception("Insecure permissions on environment.json. Try chmod 600 environment.json")
    ENV = IO_DeserializeJson(IO_ReadFile(env_path))
Env_Load()
# endregion

# Working with the main user database.
DB = None
def DB_Load():
    global DB
    db_path = os.path.join(IO_GetScriptDir(), "database.json")
    if os.path.isfile(db_path):
        DB = IO_DeserializeJson(IO_ReadFile(db_path))
        DB = { int(key): value for key, value in DB.items() }
    else:
        DB = {}
        DB_Save()
def DB_Backup():
    db_path = os.path.join(IO_GetScriptDir(), "database.json")
    backup_file_name = f"backups/{int(IO_GetEpoch())}.json"
    backup_path = os.path.join(IO_GetScriptDir(), backup_file_name)
    IO_WriteFile(backup_path, IO_ReadFile(db_path))
    Log_Info(f"Backed up database.json to {backup_file_name}.")
def DB_Save():
    db_path = os.path.join(IO_GetScriptDir(), "database.json")
    IO_WriteFile(db_path, IO_SerializeJson(DB))
    backups_dir_path = os.path.join(IO_GetScriptDir(), "backups")
    latest_backup_time = 0
    for backup_path in os.listdir(backups_dir_path):
        if not os.path.isfile(os.path.join(backups_dir_path, backup_path)):
            raise Exception(f"{backup_path} is not a file.")
        backup_time = int(os.path.splitext(backup_path)[0])
        if backup_time > latest_backup_time:
            latest_backup_time = backup_time
    if int(IO_GetEpoch()) - latest_backup_time > 24 * 60 * 60:
        DB_Backup()

# region OSU API
def OSU_LookupOnidName(onid_email):
    # Get a token
    response = requests.post("https://api.oregonstate.edu/oauth2/token", data={"grant_type": "client_credentials"}, auth=(ENV["osu_api_id"], ENV["osu_api_secret"]))
    response.raise_for_status()
    token = response.json()["access_token"]

    # Send a request
    headers = { "Authorization": f"Bearer {token}", "Accept": "application/json" }
    response = requests.get(f"https://api.oregonstate.edu/v2/directory?filter[emailAddress]={onid_email}", headers=headers)
    response.raise_for_status()
    data = response.json()["data"]

    # Manual overrides
    if onid_email == "christj@oregonstate.edu":
        data = [ { "attributes": { "firstName": "Finlay", "lastName": "Christ" } } ]
    elif onid_email == "indoor.rockclimbing@oregonstate.edu":
        data = [ { "attributes": { "firstName": "Indoor", "lastName": "RockClimbing" } } ]

    # Return output or None
    if len(data) == 1:
        output = f"{data[0]['attributes']['firstName']} {data[0]['attributes']['lastName']}"
        Log_Info(f"OSU directory lookup for {onid_email} returned {output}.")
        return output
    else:
        Log_Warning(f"OSU directory lookup for {onid_email} returned no data.")
        return None
# endregion

# region COE SMTP
def SMTP_SendEmail(to, subject, body, body_html):
    SMTP_SERVER = "mail.engr.oregonstate.edu"
    SMTP_PORT = 465

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = f"{ENV['email_username']}@oregonstate.edu"
    msg["To"] = to
    msg.set_content(body)
    msg.add_alternative(body_html, subtype="html")

    with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT) as smtp_server:
        smtp_server.login(ENV["email_username"], ENV["email_password"])
        smtp_server.send_message(msg)

    Log_Info(f"Sent email to \"{to}\" with subject \"{subject}\".")
def SMTP_SendCode(to, code):
    body = IO_ReadFile(os.path.join(IO_GetScriptDir(), "email", "email.txt")).replace("##CODE##", code)
    body_html = IO_ReadFile(os.path.join(IO_GetScriptDir(), "email", "email.html")).replace("##CODE##", code)
    SMTP_SendEmail(to, f"{code} - ONIDbot Verification Code", body, body_html)
# endregion

REQUESTS = {}

# region Discord
discord_client = discord.Client(intents=discord.Intents.default())
discord_command_tree = discord.app_commands.CommandTree(discord_client)
async def guild_verify(interaction: discord.Interaction, already_verified):
    onid_email = DB[interaction.user.id]["onid_email"]
    onid_name = DB[interaction.user.id]["onid_name"]

    verified_role = None
    for guild_role in interaction.guild.roles:
        if guild_role.name == "ONID-Verified":
            verified_role = guild_role
            break

    if verified_role == None:
        Log_Info(f"Verified @{interaction.user.name} <@{interaction.user.id}> as \"{onid_name}\" {onid_email} on \"{interaction.guild.name}\" {interaction.guild.id} but failed to assign ONID-Verified role because it does not exist.")
        if already_verified:
            await interaction.followup.send(f"You are already verified however this server doesn't have an \"ONID-Verified\" role to give you. Please reach out to the server administrators to create this role.", ephemeral=True, wait=True)
        else:
            await interaction.followup.send(f"You have been successfully verified however this server doesn't have an \"ONID-Verified\" role to give you. Please reach out to the server administrators to create this role.", ephemeral=True, wait=True)
        return

    try:
        await interaction.user.add_roles(verified_role)
    except discord.errors.Forbidden as ex:
        Log_Info(f"Failed to assign ONID-Verified role to @{interaction.user.name} <@{interaction.user.id}> on \"{interaction.guild.name}\" {interaction.guild.id} due to insufficient permissions.")
        if already_verified:
            await interaction.followup.send(f"You are already verified however {discord_client.user.mention} doesn't have permission to assign you the ONID-Verified role. Please reach out to the server administrators to grant {discord_client.user.mention} this permission.", ephemeral=True, wait=True)
        else:
            await interaction.followup.send(f"You have been successfully verified however {discord_client.user.mention} doesn't have permission to assign you the ONID-Verified role. Please reach out to the server administrators to grant {discord_client.user.mention} this permission.", ephemeral=True, wait=True)
        return

    try:
        await interaction.user.edit(nick=onid_name)
    except discord.errors.Forbidden as ex:
        Log_Info(f"Failed to nick @{interaction.user.name} <@{interaction.user.id}> to \"{onid_name}\" on \"{interaction.guild.name}\" {interaction.guild.id} due to insufficient permissions.")

    if already_verified:
        await interaction.followup.send(f"You are already verified as \"{onid_name}\" {onid_email}. The ONID-Verified role has been assigned to you on this server.", ephemeral=True, wait=True)
    else:
        await interaction.followup.send(f"You have successfully verified as \"{onid_name}\" {onid_email}.", ephemeral=True, wait=True)

    Log_Info(f"Verified @{interaction.user.name} <@{interaction.user.id}> as \"{onid_name}\" {onid_email} on \"{interaction.guild.name}\" {interaction.guild.id}.")
class ButtonsView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
    @discord.ui.button(label="Enter ONID Email!", style=discord.ButtonStyle.primary, emoji="\U00000031\U0000fe0f\U000020e3", custom_id="get_code_button")
    async def get_code_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            if interaction.user.id in DB:
                await interaction.response.defer(ephemeral=True)
                await guild_verify(interaction, already_verified=True)
            else:
                await interaction.response.send_modal(OnidInputModal())
        except BaseException as ex:
            Log_Exception(ex)
            raise ex
    @discord.ui.button(label="Enter Verification Code!", style=discord.ButtonStyle.primary, emoji="\U00000032\U0000fe0f\U000020e3", custom_id="enter_code_button")
    async def enter_code_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            if interaction.user.id in DB:
                await interaction.response.defer(ephemeral=True)
                await guild_verify(interaction, already_verified=True)
            else:
                await interaction.response.send_modal(CodeInputModal())
        except BaseException as ex:
            Log_Exception(ex)
            raise ex
class OnidInputModal(discord.ui.Modal):
    def __init__(self):
        super().__init__(title="ONID Email Address", custom_id="onid_input_modal", timeout=None)
    onid_input = discord.ui.TextInput(label="Enter your ONID email address:", placeholder="onid@oregonstate.edu", required=True, custom_id="onid_text_input")
    async def on_submit(self, interaction: discord.Interaction):
        try:
            if interaction.user.id in DB:
                return # Hard bail and fail interaction
            await interaction.response.defer(ephemeral=True)
            onid_email = str(self.onid_input.value).strip().lower()
            if not onid_email.endswith("@oregonstate.edu") or len(onid_email) <= len("@oregonstate.edu"):
                await interaction.followup.send(f"The ONID you entered doesn't look quite right. Please try again.", ephemeral=True, wait=True)
                return
            onid_name = OSU_LookupOnidName(onid_email)
            if onid_name == None:
                await interaction.followup.send(f"The ONID you entered doesn't look quite right. Please try again.", ephemeral=True, wait=True)
                return
            code = GetRandomCode()
            request = { "time": IO_GetEpoch(), "code": code, "onid_email": onid_email, "onid_name": onid_name }
            REQUESTS[interaction.user.id] = request
            Log_Info(f"Created code {code} for @{interaction.user.name} <@{interaction.user.id}> on \"{interaction.guild.name}\" {interaction.guild.id} for \"{onid_name}\" {onid_email}")
            SMTP_SendCode(onid_email, code)
            await interaction.followup.send(f"A verification code has been sent to **{onid_email}**.\n\nCodes can take up to 5 minutes to arive. Check your **SPAM** folder before requesting a new code.", ephemeral=True, wait=True)
        except BaseException as ex:
            Log_Exception(ex)
            raise ex
class CodeInputModal(discord.ui.Modal):
    def __init__(self):
        super().__init__(title="Verification Code", custom_id="code_input_modal", timeout=None)
    code_input = discord.ui.TextInput(label="Enter your verification code:", placeholder="ABC123", required=True, custom_id="code_text_input")
    async def on_submit(self, interaction: discord.Interaction):
        try:
            if interaction.user.id in DB:
                return # Hard bail and fail interaction
            await interaction.response.defer(ephemeral=True)
            code = str(self.code_input.value).strip().upper()
            if not len(code) == 6 or not all([ c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789" for c in code ]):
                await interaction.followup.send(f"The code you entered doesn't look quite right. It may have expired. Please try again.", ephemeral=True, wait=True)
                return
            request = None
            if interaction.user.id in REQUESTS:
                request = REQUESTS[interaction.user.id]
            if request == None or request["code"] != code or IO_GetEpoch() - request["time"] > 900.0:
                await interaction.followup.send(f"The code you entered doesn't look quite right. It may have expired. Please try again.", ephemeral=True, wait=True)
                return
            DB[interaction.user.id] = { "onid_email": request["onid_email"], "onid_name": request["onid_name"], "notes": "" }
            DB_Save()
            del REQUESTS[interaction.user.id]
            await guild_verify(interaction, already_verified=False)
        except BaseException as ex:
            Log_Exception(ex)
            raise ex
@discord_client.event
async def on_ready():
    try:
        await discord_command_tree.sync()
        discord_client.add_view(ButtonsView())
        await discord_client.change_presence(activity=discord.CustomActivity("Verifying ONID email addresses..."), status=discord.Status.online)
        Log_Info(f"Online as {discord_client.user}")
    except BaseException as ex:
        Log_Exception(ex)
        raise ex
@discord_command_tree.command(name="post_verification_buttons", description="Posts the verification buttons to the current channel.")
async def post_verification_buttons(interaction: discord.Interaction):
    try:
        await interaction.response.defer(ephemeral=True)
        if not interaction.user.guild_permissions.administrator:
            await interaction.followup.send("You need the administrator permission in this server to run this command.", wait=True)
            return
        try:
            await interaction.channel.send("", view=ButtonsView())
        except discord.errors.Forbidden as ex:
                Log_Info(f"Failed to post verification buttons on \"{interaction.guild.name}\" {interaction.guild.id} due to insufficient permissions.")
                await interaction.followup.send(f"{discord_client.user.mention} does not have permission to post messages in this channel and therefore could not post the verification buttons.", ephemeral=True, wait=True)
                return
        await interaction.followup.send("Done!", wait=True)
    except BaseException as ex:
        Log_Exception(ex)
        raise ex
@discord_command_tree.command(name="get_verification_info", description="Prints weather a given Discord account is ONID verified.")
async def get_verification_info(interaction: discord.Interaction, user: discord.Member):
    try:
        await interaction.response.defer(ephemeral=True)
        if not interaction.user.id in DB:
            await interaction.followup.send("You must be verified by ONIDbot to run this command.", ephemeral=True, wait=True)
            return
        if user.id in DB:
            await interaction.followup.send(f"{user.mention} is verified as \"{DB[user.id]['onid_name']}\" {DB[user.id]['onid_email']}.", ephemeral=True, wait=True)
        else:
            await interaction.followup.send(f"{user.mention} is not verified.", ephemeral=True, wait=True)
    except BaseException as ex:
        Log_Exception(ex)
        raise ex
# endregion

# region Launch Time Cluster
START_TIME = IO_GetEpoch()
IS_PRIMARY = False
async def CLUSTER_GetLaunchTime(hostname):
    try:
        reader, writer = await asyncio.wait_for(asyncio.open_connection(hostname, ENV["cluster_port"]), timeout=2.0)
        data = await reader.read(256)
        writer.close()
        await writer.wait_closed()
        return float(data.decode().strip())
    except Exception:
        return float("inf")
async def CLUSTER_HandleRequest(reader, writer):
    try:
        writer.write(str(START_TIME).encode())
        await writer.drain()
    finally:
        writer.close()
        await writer.wait_closed()
async def CLUSTER_Run():
    global IS_PRIMARY

    my_hostname = socket.gethostname()

    cluster_state = {}
    for hostname in ENV["cluster_hostnames"]:
        if hostname == my_hostname:
            continue
        cluster_state[hostname] = (await CLUSTER_GetLaunchTime(hostname)) == float("inf")

    async with await asyncio.start_server(CLUSTER_HandleRequest, "0.0.0.0", ENV["cluster_port"]):
        print(f"Joined cluster on {my_hostname}:{ENV['cluster_port']}...")

        while True:
            min_peer_launch_time = float("inf")
            for hostname in ENV["cluster_hostnames"]:
                if hostname == my_hostname:
                    continue

                peer_launch_time = await CLUSTER_GetLaunchTime(hostname)
                if peer_launch_time < min_peer_launch_time:
                    min_peer_launch_time = peer_launch_time

                if cluster_state[hostname] != (peer_launch_time == float("inf")) and IS_PRIMARY:
                    Log_Warning(f"Hostname {hostname} is now {'down' if (peer_launch_time == float('inf')) else 'up'}.")
                cluster_state[hostname] = peer_launch_time == float("inf")

            if START_TIME < min_peer_launch_time:
                if not IS_PRIMARY:
                    IS_PRIMARY = True
                    Log_Info(f"{my_hostname} Taking over as primary...")
                    DB_Load()
                    asyncio.create_task(discord_client.start(ENV["discord_token"]))

            await asyncio.sleep(ENV["heartbeat_interval"])
# endregion

# region Main
def Main():
    try:
        asyncio.run(CLUSTER_Run())
    except KeyboardInterrupt:
        sys.exit(0)
    except BaseException as ex:
        Log_Exception(ex)
        sys.exit(1)
Main()
# endregion
