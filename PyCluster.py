#!/bin/python

import json
import os
import datetime
import time
import sys
import asyncio
import socket
import subprocess
import math

# region File IO
def IO_RealPath(filePath):
    return os.path.realpath(os.path.expanduser(filePath))
def IO_GetScriptDir():
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
def RunCommand(command, echo=False, capture=False, input=None, check=True, env=None):
    if echo and capture:
        raise Exception("Command cannot be run with both echo and capture.")
    result = subprocess.run(command, stdout=(None if echo else subprocess.PIPE), stderr=(None if echo else subprocess.STDOUT), input=input, env=env, check=False, shell=True, text=True)
    if check and result.returncode != 0:
        LOG_Error(result.stdout)
        raise Exception(f"Sub-process returned non-zero exit code.\nExitCode: {result.returncode}\nCmdLine: {command}")
    if capture and not check:
        return result.stdout.strip(), result.returncode
    elif capture:
        return result.stdout.strip()
    elif not check:
        return result.returncode
    else:
        return
# endregion

# region Logs
def LOG_Generic(message, log_type, ansi_color):
    formatted_message = f"{log_type} - {IO_FormatEpoch(IO_GetEpoch())} {int(IO_GetEpoch())} - {MY_HOSTNAME} - {message}"
    print(f"\033[{ansi_color}m{formatted_message}\033[0m", flush=True)
    log_path = os.path.join(IO_GetScriptDir(), "log.txt")
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
    while tb is not None:
        if IO_RealPath(tb.tb_frame.f_code.co_filename) == IO_RealPath(__file__):
            message = repr(ex)
            funcname = "<module>" if tb.tb_frame.f_code.co_name == "<module>" else tb.tb_frame.f_code.co_name + "()"
            lineno = tb.tb_lineno
            line = IO_ReadFile(tb.tb_frame.f_code.co_filename).splitlines()[lineno - 1].strip()
            LOG_Generic(f"{message} in {funcname} line {lineno}: {line}", "PY_EX", "31")
            return
        tb = tb.tb_next
    LOG_Generic(f"{repr(ex)} at unknown location", "PY_EX", "31")
# endregion

# region Environment
ENV = None
def ENV_Load():
    global ENV
    env_path = os.path.join(IO_GetScriptDir(), "environment.json")
    ENV = IO_DeserializeJson(IO_ReadFile(env_path))
    ENV['hosts'] = []
    for i in range(len(ENV['hostnames'])):
        ENV['hosts'].append( { "name": ENV['hostnames'][i], "ip": socket.gethostbyname(ENV['hostnames'][i]) } )
# endregion

# region State
START_TIME = IO_GetEpoch()
MY_HOSTNAME = socket.gethostname()
MY_HOST = { "name": MY_HOSTNAME, "ip": socket.gethostbyname(MY_HOSTNAME) }

NO_RESTART = False
# endregion

# region PyCluster Helpers
def CheckService():
    return RunCommand(ENV['service_check_command'], check=False) == 0
def StartService():
    return RunCommand(ENV['service_start_command'])
def StopService():
    return RunCommand(ENV['service_stop_command'])

def StartNode(host):
    command = ENV['start_node_command'].replace("{HOST_IP}", host['ip'])
    RunCommand(command)

async def SendRequest(host, request):
    reader, writer = await asyncio.wait_for(asyncio.open_connection(host['ip'], ENV['port']), timeout=2.0)
    try:
        writer.write((request + os.linesep).encode())
        await writer.drain()
        response = await asyncio.wait_for(reader.readline(), timeout=2.0)
        return response.decode().rstrip(os.linesep)
    finally:
        writer.close()
        await writer.wait_closed()
async def HandleRequest(reader, writer):
    try:
        request = await asyncio.wait_for(reader.readline(), timeout=2.0)
        request = request.decode().rstrip(os.linesep)
        response = InvokeRequest(request)
        writer.write((response + os.linesep).encode())
        await writer.drain()
        if response == "BYE":
            sys.exit(0)
    finally:
        writer.close()
        await writer.wait_closed()

def InvokeRequest(request):
    global NO_RESTART
    if request == "status":
        service_up = CheckService()
        return IO_SerializeJson({ "reachable": True, "node_up": True, "service_up": service_up, "birth": START_TIME, "no_restart": NO_RESTART }, compact=True)
    elif request == "no_restart":
        NO_RESTART = True
        return ""
    elif request == "stop":
        return "BYE"
    else:
        raise Exception(f"Invalid request {request}.")
async def GetHostStatus(host):
    ping_host_command = ENV['ping_host_command'].replace("{HOST_IP}", host['ip'])
    if RunCommand(ping_host_command, check=False) != 0:
        return { "reachable": False, "node_up": False, "service_up": False, "birth": float("inf"), "no_restart": False }
    try:
        return IO_DeserializeJson(await SendRequest(host, "status"))
    except:
        return { "reachable": True, "node_up": False, "service_up": False, "birth": float("inf"), "no_restart": False }

async def Heartbeat():
    restart_needed = []
    min_birth = float("inf")
    for host in ENV['hosts']:
        if host['ip'] == MY_HOST['ip']:
            continue
        status = await GetHostStatus(host)
        if status['birth'] < min_birth:
            min_birth = status['birth']
        if status['reachable'] and not status['node_up']:
            restart_needed.append(host)
    eldest = START_TIME < min_birth
    service_up = CheckService()

    if eldest:
        if not service_up:
            LOG_Info(f"{MY_HOST['name']} is eldest but service is down. Starting...")
            StartService()
        if not NO_RESTART and IO_GetEpoch() - min(START_TIME, min_birth) > 10:
            for host in restart_needed:
                LOG_Info(f"{MY_HOST['name']} is eldest restarting {host['name']}...")
                StartNode(host)
    elif not eldest:
        if service_up:
            LOG_Error(f"{MY_HOST['name']} is not eldest but service is up. Killing...")
            StopService()
# endregion

# region PyCluster Launch Intents
async def Run():
    server = await asyncio.start_server(HandleRequest, "0.0.0.0", ENV['port'])
    try:
        LOG_Info(f"{MY_HOST['name']} joined cluster.")
        while True:
            try:
                await Heartbeat()
                await asyncio.sleep(ENV['interval'])
            except Exception as ex:
                LOG_Exception(ex)
    finally:
        try:
            if CheckService():
                StopService()
        except Exception as ex:
            LOG_Exception(ex)
        try:
            server.close()
            await server.wait_closed()
        except Exception as ex:
            LOG_Exception(ex)
async def Start():
    for host in ENV['hosts']:
        status = await GetHostStatus(host)
        if status['reachable'] and not status['node_up']:
            print(f"Starting {host['name']}...")
            StartNode(host)
            await asyncio.sleep(0.25)
    print("Started all hosts.")
async def Stop():
    print("Disabling restart...")
    for host in ENV['hosts']:
        try:
            await SendRequest(host, "no_restart")
        except:
            pass
    print("Stopping cluster nodes...")
    for host in ENV['hosts']:
        try:
            await SendRequest(host, "stop")
        except:
            pass
    print("Cluster has been stopped.")
async def Status():
    # { "reachable": True, "node_up": False, "service_up": False, "birth": float("inf"), "no_restart": False }
    BLUE = "\033[1;34m"
    GREEN = "\033[1;32m"
    YELLOW = "\033[1;33m"
    RED = "\033[1;31m"
    RESET = "\033[0m"
    for host in ENV['hosts']:
        status = await GetHostStatus(host)
        if status['reachable'] and status['node_up'] and status['service_up'] and math.isfinite(status['birth']) and status['birth'] > 0 and not status['no_restart']:
            print(BLUE, end="")
        elif status['reachable'] and status['node_up'] and not status['service_up'] and math.isfinite(status['birth']) and status['birth'] > 0 and not status['no_restart']:
            print(GREEN, end="")
        elif not status['reachable'] and not status['node_up'] and not status['service_up'] and status['birth'] == float("inf") and not status['no_restart']:
            print(YELLOW, end="")
        else:
            print(RED, end="")
        print(f"Hostname {host['name']} - Reachable {status['reachable']} - Node Up {status['node_up']} - Service Up {status['service_up']} - Birth {IO_FormatEpoch(status['birth'])} - No Restart {status['no_restart']}", end="")
        print(RESET)
# endregion

# region Main
async def Main():
    try:
        ENV_Load()
        if len(sys.argv) == 2 and sys.argv[1] == "run":
            await Run()
        elif len(sys.argv) == 2 and sys.argv[1] == "start":
            await Start()
        elif len(sys.argv) == 2 and sys.argv[1] == "stop":
            await Stop()
        elif len(sys.argv) == 2 and sys.argv[1] == "status":
            await Status()
        else:
            raise Exception("No verb specified. Try \"pycluster start\".")
        sys.exit(0)
    except KeyboardInterrupt:
        sys.exit(0)
    except Exception as ex:
        LOG_Exception(ex)
        sys.exit(1)
asyncio.run(Main())
# endregion