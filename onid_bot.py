#!/usr/bin/env python

# import discord
import json
import os
import math
import requests
from datetime import datetime, timezone
import time
import discord
import sys
import secrets
import smtplib
from email.message import EmailMessage
import email.utils

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
    return int(time.time()) + time.localtime().tm_gmtoff
def IO_GetTime():
    epoch = IO_GetEpoch()
    timestamp = datetime.fromtimestamp(epoch, tz=timezone.utc)
    return timestamp.strftime("%I:%M%p %m/%d").lower()
# endregion

# region Logs
def Log_Generic(message, log_type, ansi_color):
    padding = " " * (8 - len(log_type)) if len(log_type) < 8 else ""
    formatted_message = f"{log_type}{padding}({IO_GetTime()} {IO_GetEpoch()}): {message}"
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
    else:
        DB = {}
        DB_Save()
def DB_Backup():
    db_path = os.path.join(IO_GetScriptDir(), "database.json")
    backup_path = os.path.join(IO_GetScriptDir(), f"backups/{IO_GetEpoch()}.json")
    IO_WriteFile(backup_path, IO_ReadFile(db_path))
    Log_Info(f"Backed up database.json to {backup_path}.")
def DB_Save():
    db_path = os.path.join(IO_GetScriptDir(), "database.json")
    IO_WriteFile(db_path, IO_SerializeJson(DB))
    backups_dir_path = os.path.join(IO_GetScriptDir(), "backups")
    if not os.path.isdir(backups_dir_path):
        os.mkdir(backups_dir_path)
        Log_Warning(f"{backups_dir_path} did not exist so it was created.")
    latest_backup_time = 0
    for backup_path in os.listdir(backups_dir_path):
        if not os.path.isfile(backup_path):
            Log_Warning(f"{backup_path} is not a file.")
            continue
        try:
            backup_time = int(os.path.splitext(backup_path)[0])
        except:
            Log_Warning(f"{backup_path} is not a valid file name.")
            continue
        if backup_time > latest_backup_time:
            latest_backup_time = backup_time
    if IO_GetEpoch() - latest_backup_time > 24 * 60 * 60:
        DB_Backup()
DB_Load()

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

    # Manual Override For christj@oregonstate.edu
    if onid_email == "christj@oregonstate.edu":
        data = [ { "attributes": { "firstName": "Finlay", "lastName": "Christ" } } ]

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
    msg["From"] = email.utils.formataddr(("ONIDbot", f"{ENV["email_username"]}@oregonstate.edu"))
    msg["To"] = to
    msg.set_content(body)
    msg.add_alternative(body_html, subtype="html")

    with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT) as smtp_server:
        smtp_server.set_debuglevel(1)
        smtp_server.login(f"{ENV["email_username"]}@oregonstate.edu", ENV["email_password"])
        smtp_server.send_message(msg)
def SMTP_SendCode(to, code):
    body = IO_ReadFile(os.path.join(IO_GetScriptDir(), "email", "email.txt")).replace("##CODE##", code)
    body_html = IO_ReadFile(os.path.join(IO_GetScriptDir(), "email", "email.html")).replace("##CODE##", code)
    SMTP_SendEmail(to, f"{code} - ONIDBot Verification Code", body, body_html)
# endregion

# region Codes
codes = {}
def GetRandomCode():
    charset = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    output = []
    for _ in range(6):
        while True:
            i = int.from_bytes(secrets.token_bytes(1)) & 0x3F
            if i > 35:
                continue
            output.append(charset[i])
            break
    return "".join(output)
# endregion

# region Discord
discord_client = discord.Client(intents=discord.Intents.default())
discord_command_tree = discord.app_commands.CommandTree(discord_client)
class ButtonsView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
    @discord.ui.button(label="Get Verification Code!", style=discord.ButtonStyle.primary, emoji="\U00000031\U0000fe0f\U000020e3", custom_id="get_code_button")
    async def get_code_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            await interaction.response.send_modal(OnidInputModal())
        except BaseException as ex:
            Log_Exception(ex)
            raise ex
    @discord.ui.button(label="Enter Verification Code!", style=discord.ButtonStyle.primary, emoji="\U00000032\U0000fe0f\U000020e3", custom_id="enter_code_button")
    async def enter_code_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
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
            await interaction.response.defer(ephemeral=True)
            # TODO
            onid_email = str(self.onid_input.value).strip().lower()
            if not onid_email.endswith("@oregonstate.edu") or len(onid_email) <= len("@oregonstate.edu"):
                await interaction.followup.send(f"The ONID you entered doesn't look quite right. Please try again.", ephemeral=True, wait=True)
                return
            onid_name = await OSU_LookupOnidNameAsync(onid_email)
            if onid_name == None:
                await interaction.followup.send(f"The ONID you entered doesn't look quite right. Please try again.", ephemeral=True, wait=True)
                return            
            code = GetRandomCode()
            codes[interaction.user.id] = { "time": IO_GetEpoch(), "code": code, "onid_email": onid_email, "onid_name": onid_name }
            Log_Info(f"Created code {code} for {interaction.user.mention} {interaction.user.id} on {interaction.guild.name} {interaction.guild.id} for {onid_name} {onid_email}")
            
            await discord_client.application.owner.send(f"{discord_client.application.owner.mention} YO MAMA SO FAT")

            email = IO_ReadFile("./email/email.html").replace("##CODE##", str(code))
            await MS_SendEmailAsync(onid_email, f"{code} - ONIDbot Verification Code", email)
            await interaction.followup.send(f"A verification code has been sent to {onid_email}.\n\nPlease allow up to 15 minutes for the code to arive, and **check spam.**", ephemeral=True, wait=True)
            # END TODO
        except BaseException as ex:
            Log_Exception(ex)
            raise ex
class CodeInputModal(discord.ui.Modal):
    def __init__(self):
        super().__init__(title="Verification Code", custom_id="code_input_modal", timeout=None)
    code_input = discord.ui.TextInput(label="Enter your verification code:", placeholder="ABC123", required=True, custom_id="code_text_input")
    async def on_submit(self, interaction: discord.Interaction):
        try:
            await interaction.response.defer(ephemeral=True)
            # TODO
            code = str(self.onid_input.value).strip()

            if not len(code) == 6 or not code.isdigit():
                await interaction.response.send_message(f"The code you entered doesn't look quite right. Please try again.", ephemeral=True)
                return

            # TODO finish this
            code_obj = Code_ParseAndVerify(code)
            discord_id = code_obj["discord_id"]
            onid_email = code_obj["onid_email"]

            if not WatchDogInGoodStanding(discord_id):
                return f"TOO MANY REQUESTS! Please wait 24 hours."
            WatchDogPunish(discord_id)

            DB_Set(discord_id, onid_email)

            discord_server_obj = discord_client.get_guild(ENV["discord_server_id"])
            if discord_server_obj is None:
                discord_server_obj = await discord_client.fetch_guild(ENV["discord_server_id"])

            discord_user_obj = discord_server_obj.get_member(discord_id)
            if discord_user_obj is None:
                discord_user_obj = await discord_server_obj.fetch_member(discord_id)

            await discord_user_obj.add_roles(discord_verified_role)
            await discord_user_obj.remove_roles(discord_unverified_role)
            onid_name = await OSU_LookupOnidNameAsync(onid_email)
            if onid_name == None:
                print(f"Failed to lookup onid name for {onid_email}.")
            else:
                try:
                    await discord_user_obj.edit(nick=onid_name)
                except:
                    print(f"Failed to nick {discord_id}.")

            return f"Success your Discord account (@{discord_user_obj.name}) has been linked with your ONID email ({onid_email}).<br />You may now close this tab and return to Discord."
            # END TODO
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
@discord_command_tree.command(name="post_verification_buttons", description="Posts the get verified button to the current channel.")
async def post_verification_buttons(interaction: discord.Interaction):
    try:
        await interaction.response.defer(ephemeral=True)
        if not interaction.user.guild_permissions.administrator:
            await interaction.followup.send("You need the administrator permission in this server to run this command.", wait=True)
            return
        await interaction.channel.send("", view=ButtonsView())
        await interaction.followup.send("Done!", wait=True)
    except BaseException as ex:
        Log_Exception(ex)
        raise ex
@discord_command_tree.command(name="get_verification_info", description="Posts a bunch of debug information on a target user just for you.")
async def get_user_info(interaction: discord.Interaction, user: discord.Member):
    try:
        await interaction.response.defer(ephemeral=True)
        # TODO
        if not interaction.user.is_verified:
            await interaction.response.send_message("You must be verified by ONIDbot to run this command.", ephemeral=True)
            return
        user_id = str(user.id)
        user_mention = user.mention
        verified_role = any([ role.id == discord_verified_role.id for role in user.roles ])
        unverified_role = any([ role.id == discord_unverified_role.id for role in user.roles ])
        onid_email = DB_Get(user_id)
        onid_name = None if onid_email == None else await OSU_LookupOnidNameAsync(onid_email)
        watchdog_requests = WatchDogQuery(user_id)
        await interaction.response.send_message(f"User: {user_mention}\nUser ID: {user_id}\nVerified Role: {verified_role}\nUnverified Role: {unverified_role}\nONID: {onid_email}\nONID Name: {onid_name}\nWatchDog Requests: {watchdog_requests}", ephemeral=True)
        # END TODO
    except BaseException as ex:
        Log_Exception(ex)
        raise ex
# endregion

# region Main
def Main():
    try:
        discord_client.run(ENV["discord_token"])
        return 0
    except BaseException as ex:
        Log_Exception(ex)
        return 1
sys.exit(Main())
# endregion