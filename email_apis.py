import os
import json
import time
import datetime
from time import timezone
import requests
import base64
import smtplib
from email.message import EmailMessage

InitTasks = []

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
    log_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), "log.txt")
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
        if os.path.realpath(tb.tb_frame.f_code.co_filename) == os.path.realpath(__file__):
            message = str(ex)
            funcname = "<module>" if tb.tb_frame.f_code.co_name == "<module>" else tb.tb_frame.f_code.co_name + "()"
            lineno = tb.tb_lineno
            line = IO_ReadFile(tb.tb_frame.f_code.co_filename).splitlines()[lineno - 1].strip()
            Log_Generic(f"{message} in {funcname} line {lineno}: {line}", "ERROR", "31")
            return
        tb = tb.tb_next
    Log_Generic(f"{str(ex)} at unknown location", "ERROR", "31")
# endregion

# region MSAuth
# Thunderbird Client ID
MS_ClientID = "9e5f94bc-e8a4-4e73-b8be-63364c29d753"
# Oregon State University Tenant ID
MS_TenantID = "ce6d05e1-3c5e-4d62-87a8-4c4a2713c113"
MS_Scopes = "offline_access https://graph.microsoft.com/Mail.Send"
MS_RefreshToken = None
def MS_LoadRefreshToken():
    global MS_RefreshToken
    refresh_token_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), "msauth_token")
    if os.path.isfile(refresh_token_path):
        MS_RefreshToken = IO_ReadFile(refresh_token_path)
def MS_SaveRefreshToken():
    refresh_token_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), "msauth_token")
    IO_WriteFile(refresh_token_path, MS_RefreshToken)
def MS_DoManualAuthFlow():
    global MS_RefreshToken

    # Tenant id is required for rooted scope paths on the device code endpoint.
    device_code_request_data = { "client_id": MS_ClientID, "scope": MS_Scopes }
    device_code_request = requests.post("https://login.microsoftonline.com/" + MS_TenantID + "/oauth2/v2.0/devicecode", data=device_code_request_data)
    device_code_request.raise_for_status()
    device_code_response = device_code_request.json()
    Log_Info(device_code_response["message"])

    start = time.time()
    while time.time() - start < int(device_code_response["expires_in"]):
        time.sleep(int(device_code_response["interval"]))
        token_request_data = {
            "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
            "client_id": MS_ClientID,
            "device_code": device_code_response["device_code"],
        }
        token_request = requests.post("https://login.microsoftonline.com/" + MS_TenantID + "/oauth2/v2.0/token", data=token_request_data)
        if token_request.ok:
            token = token_request.json()
            MS_RefreshToken = token["refresh_token"]
            MS_SaveRefreshToken()
            return token["access_token"]
        else:
            token_request_error = token_request.json()["error"]
            if token_request_error == "authorization_pending":
                continue
            else:
                raise Exception(token_request_error)
    raise Exception("Timed out waiting for device authorization.")
def MS_GetAccessToken():
    global MS_RefreshToken

    try:
        if MS_RefreshToken == None:
            MS_LoadRefreshToken()

        token_request_data = {
            "grant_type": "refresh_token",
            "client_id": MS_ClientID,
            "refresh_token": MS_RefreshToken,
            "scope": MS_Scopes,
        }
        token_request = requests.post("https://login.microsoftonline.com/" + MS_TenantID + "/oauth2/v2.0/token", data=token_request_data)
        token_request.raise_for_status()
        token = token_request.json()

        MS_RefreshToken = token["refresh_token"]
        MS_SaveRefreshToken()
        return token["access_token"]
    except:
        return MS_DoManualAuthFlow()
def MS_EmailFromToken(access_token):
    token_body = access_token.split(".")[1]
    token_body += "=" * (-len(token_body) % 4)
    token_json = base64.urlsafe_b64decode(token_body).decode("utf-8")
    token_object = json.loads(token_json)
    return token_object["upn"]
InitTasks.append(MS_LoadRefreshToken)
# endregion

# region MS Graph
def GRAPH_SendEmail(to, subject, body_html):
    access_token = MS_GetAccessToken()
    from_address = MS_EmailFromToken(access_token)
    Log_Info(f"Sending email from {from_address} to {to}: {subject}")
    headers = { "Authorization": f"Bearer {access_token}", "Accept": "application/json", "Content-type": "application/json" }
    request = {
        "message": {
            "subject": subject,
            "body": { "contentType": "HTML", "content": body_html }, # MSGRAPH auto-generates the text email from the HTML.
            "toRecipients": [ { "emailAddress": { "address": to } } ]
        },
        "saveToSentItems": "false"
    }
    response = requests.post(f"https://graph.microsoft.com/v1.0/users/{from_address}/sendMail", json=request, headers=headers)
    response.raise_for_status()
# endregion

# region MS SMTP
def MSSMTP_SendEmail(to, subject, body, body_html):
    access_token = MS_GetAccessToken()
    from_address = MS_EmailFromToken(access_token)
    
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = from_address
    msg["To"] = to
    msg.set_content(body)
    msg.add_alternative(body_html, subtype="html")
    
    Log_Info(f"Sending email from {from_address} to {to}: {subject}")
    with smtplib.SMTP("smtp.office365.com", 587) as smtp_server:
        smtp_server.set_debuglevel(1)
        smtp_server.starttls()
        smtp_server.ehlo() # Required before auth. Handshake to agree on supported features.
        auth_code = base64.b64encode(("user=" + from_address + "\x01auth=Bearer " + access_token + "\x01\x01").encode("utf-8")).decode("utf-8")
        code, resp = smtp_server.docmd("AUTH", "XOAUTH2 " + auth_code)
        if code != 235:
            raise Exception("SMTP auth failure " + str(code) + " " + resp.decode(encoding="utf-8"))
        smtp_server.send_message(msg)
# endregion

# region COE SMTP
SMTP_SERVER = "mail.engr.oregonstate.edu"
SMTP_PORT = 465
def SMTP_SendEmail(username, password, to, subject, body, body_html):
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = f"{username}@oregonstate.edu"
    msg["To"] = to
    msg.set_content(body)
    msg.add_alternative(body_html, subtype="html")

    with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT) as smtp_server:
        smtp_server.set_debuglevel(1)
        smtp_server.login(username, password)
        smtp_server.send_message(msg)
# endregion
