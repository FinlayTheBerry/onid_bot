#!/usr/bin/python

import json
import os
import datetime
import time
import asyncio
from aiohttp import web
import ssl

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
    if epoch == float("inf") or epoch == float("-inf"):
        return "NONE_TIME"
    timestamp = datetime.datetime.fromtimestamp(epoch)
    return timestamp.strftime("%I:%M%p %m/%d").lower()
# endregion

# region Logs
def LOG_Generic(message, log_type, ansi_color):
    formatted_message = f"{log_type} - {IO_FormatEpoch(IO_GetEpoch())} {int(IO_GetEpoch())} - {message}"
    print(f"\033[{ansi_color}m{formatted_message}\033[0m", flush=True)
    log_path = os.path.join(IO_GetEnvironmentDir(), "ONIDbot.log")
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
    LOG_Generic(LOG_FormatException(ex), "PY_EX", "31")
def LOG_FormatException(ex):
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
        return f"{repr(ex)} at unknown location"
    else:
        return f"{tb_data['message']} in {tb_data['funcname']} line {tb_data['lineno']}: {tb_data['line']}"
# endregion

# region Environment
ENV = None
def ENV_Load():
    global ENV
    env_path = os.path.join(IO_GetEnvironmentDir(), "environment.json")
    ENV = IO_DeserializeJson(IO_ReadFile(env_path))
# endregion

async def API_ClientHandler(request):
    action = request.rel_url.query.get("f", "")
    print("Action: " + action)
    if action == "ping":
        return web.Response(text="{\"state\":\"success\",\"title\":\"pong\",\"message\":\"pong\"}", status=200)
    elif action == "verify":
        code = request.rel_url.query.get("c", "")
        print(code)
        return web.Response(text="{\"state\":\"success\",\"title\":\"Verified\",\"message\":\"Wahoo\"}", status=200)
    else:
        return web.Response(text="{\"state\":\"failure\",\"title\":\"Unknown API\",\"message\":\"Unknown api endpoint.\"}", status=200)

async def API_RunServer():
    app = web.Application()
    app.add_routes([ web.get("/API", API_ClientHandler) ])
    
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain("./ONIDbot.crt", "./ONIDbot.key")

    context.load_verify_locations("./ONIDbot.crt")
    context.verify_mode = ssl.CERT_REQUIRED

    context.minimum_version = ssl.TLSVersion.TLSv1_2
    context.maximum_version = ssl.TLSVersion.TLSv1_2

    context.options |= ssl.OP_NO_COMPRESSION
    context.options |= ssl.OP_CIPHER_SERVER_PREFERENCE
    
    SECURE_CIPHERS = (
        "ECDHE-ECDSA-AES256-GCM-SHA384:"
        "ECDHE-RSA-AES256-GCM-SHA384:"
        "ECDHE-ECDSA-CHACHA20-POLY1305:"
        "ECDHE-RSA-CHACHA20-POLY1305"
    )
    context.set_ciphers(SECURE_CIPHERS)
    
    runner = web.AppRunner(app)
    await runner.setup()    
    site = web.TCPSite(runner, "0.0.0.0", ENV["api_port"], ssl_context=context)
    await site.start()
    print(f"Listening on port {ENV['api_port']}")
    await asyncio.Event().wait()

async def Main():
    ENV_Load()
    await asyncio.gather(API_RunServer())
asyncio.run(Main())
