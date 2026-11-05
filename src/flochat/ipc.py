"""Bounded authenticated local JSON IPC. Never pickle, HTTP, OAuth or a write API."""

from __future__ import annotations

import base64
import ctypes
import hashlib
import hmac
import json
import os
import secrets
import socket
import stat
import time
from pathlib import Path

from flochat.errors import FloChatError

MAX_FRAME = 524288


def runtime_path(config):
    return Path(str(config.resolved_db_path.resolve()) + ".panel.json")


def _protect(data, decrypt=False):
    if os.name != "nt":
        return data

    class Blob(ctypes.Structure):
        _fields_ = [("size", ctypes.c_ulong), ("data", ctypes.POINTER(ctypes.c_ubyte))]

    buffer = ctypes.create_string_buffer(data)
    source = Blob(len(data), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_ubyte)))
    target = Blob()
    api = ctypes.windll.crypt32
    if decrypt:
        ok = api.CryptUnprotectData(
            ctypes.byref(source), None, None, None, None, 1, ctypes.byref(target)
        )
    else:
        ok = api.CryptProtectData(
            ctypes.byref(source), None, None, None, None, 1, ctypes.byref(target)
        )
    if not ok:
        raise FloChatError("Current-user DPAPI protection failed; IPC is unavailable.")
    try:
        return ctypes.string_at(target.data, target.size)
    finally:
        ctypes.windll.kernel32.LocalFree(target.data)


def write_endpoint(config, metadata, key):
    path = runtime_path(config)
    if os.name != "nt" and path.parent.stat().st_mode & 0o022:
        raise FloChatError("IPC requires a directory not writable by other users.")
    temporary = path.with_name(path.name + "." + secrets.token_hex(8))
    fd = os.open(temporary, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as file:
            json.dump({**metadata, "protected_key": base64.b64encode(_protect(key)).decode()}, file)
            file.flush()
            os.fsync(file.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def read_endpoint(config):
    try:
        path = runtime_path(config)
        fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
        with os.fdopen(fd, "r", encoding="utf-8") as file:
            info = os.fstat(file.fileno())
            if not stat.S_ISREG(info.st_mode) or info.st_size > 8192:
                raise ValueError
            if os.name != "nt" and (info.st_uid != os.getuid() or info.st_mode & 0o077):
                raise ValueError
            metadata = json.load(file, object_pairs_hook=_unique_object)
        if not isinstance(metadata, dict) or set(metadata) != {
            "instance",
            "pid",
            "mode",
            "family",
            "endpoint",
            "protected_key",
        }:
            raise ValueError
        if (
            not isinstance(metadata["instance"], str)
            or len(metadata["instance"]) != 36
            or type(metadata["pid"]) is not int
            or metadata["pid"] < 1
            or metadata["mode"] not in ("manual", "persistent")
        ):
            raise ValueError
        family, endpoint = metadata["family"], metadata["endpoint"]
        if family == "unix" and (not isinstance(endpoint, str) or not Path(endpoint).is_absolute()):
            raise ValueError
        if family == "pipe" and (
            not isinstance(endpoint, str) or not endpoint.startswith("\\\\.\\pipe\\FloChat-")
        ):
            raise ValueError
        if family == "loopback" and (type(endpoint) is not int or not 1024 <= endpoint <= 65535):
            raise ValueError
        key = _protect(base64.b64decode(metadata.pop("protected_key"), validate=True), True)
        if len(key) != 32 or metadata["family"] not in ("unix", "pipe", "loopback"):
            raise ValueError
        return metadata, key
    except (OSError, ValueError, TypeError, KeyError, RecursionError):
        raise FloChatError("No trustworthy core endpoint. Start FloChat explicitly.") from None


def encode_frame(key, payload, *, nonce=None):
    body = base64.b64encode(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode()
    ).decode()
    nonce = nonce or secrets.token_hex(16)
    at = int(time.time())
    signature = hmac.new(key, f"{at}:{nonce}:{body}".encode(), hashlib.sha256).hexdigest()
    frame = json.dumps({"at": at, "nonce": nonce, "body": body, "mac": signature}).encode() + b"\n"
    if len(frame) > MAX_FRAME:
        raise FloChatError("IPC message exceeds the local UI size bound.")
    return frame, nonce


def _unique_object(pairs):
    result = {}
    for name, value in pairs:
        if name in result:
            raise ValueError("Duplicate JSON key")
        result[name] = value
    return result


def decode_frame(key, frame):
    if len(frame) > MAX_FRAME:
        raise ValueError("frame too large")
    outer = json.loads(frame, object_pairs_hook=_unique_object)
    if not isinstance(outer, dict) or set(outer) != {"at", "nonce", "body", "mac"}:
        raise ValueError("invalid envelope")
    at, nonce, body, signature = (outer[k] for k in ("at", "nonce", "body", "mac"))
    if type(at) is not int or abs(time.time() - at) > 30:
        raise ValueError("expired envelope")
    if (
        not isinstance(nonce, str)
        or len(nonce) != 32
        or any(c not in "0123456789abcdef" for c in nonce)
    ):
        raise ValueError("invalid nonce")
    if not isinstance(body, str) or not isinstance(signature, str):
        raise ValueError("invalid envelope types")
    if len(signature) != 64 or any(c not in "0123456789abcdef" for c in signature):
        raise ValueError("invalid authentication tag")
    expected = hmac.new(key, f"{at}:{nonce}:{body}".encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(signature, expected):
        raise ValueError("unauthenticated")
    payload = json.loads(
        base64.b64decode(body, validate=True).decode("utf-8"), object_pairs_hook=_unique_object
    )
    if not isinstance(payload, dict):
        raise ValueError("expected object")
    return payload, nonce


def receive(channel):
    if hasattr(channel, "recv_bytes"):
        return channel.recv_bytes(MAX_FRAME)
    with channel.makefile("rb") as file:
        data = file.readline(MAX_FRAME + 1)
    if not data.endswith(b"\n") or len(data) > MAX_FRAME:
        raise ValueError("invalid framing")
    return data


def transmit(channel, frame):
    if hasattr(channel, "send_bytes"):
        channel.send_bytes(frame)
    else:
        channel.sendall(frame)


class Client:
    def __init__(self, config):
        self.config = config
        self.identity = secrets.token_hex(16)

    def call(self, command, **args):
        metadata, key = read_endpoint(self.config)
        payload = {
            "instance": metadata["instance"],
            "client": self.identity,
            "command": command,
            "args": args,
        }
        frame, nonce = encode_frame(key, payload)
        channel = None
        try:
            if metadata["family"] == "pipe":
                from multiprocessing.connection import Client as PipeClient

                channel = PipeClient(metadata["endpoint"], family="AF_PIPE", authkey=None)
            else:
                family = socket.AF_UNIX if metadata["family"] == "unix" else socket.AF_INET
                channel = socket.socket(family, socket.SOCK_STREAM)
                channel.settimeout(180 if command in ("prepare", "confirm", "recover") else 4)
                endpoint = metadata["endpoint"]
                if family == socket.AF_INET:
                    if type(endpoint) is not int or not 1024 <= endpoint <= 65535:
                        raise ValueError("invalid loopback port")
                    endpoint = ("127.0.0.1", endpoint)
                channel.connect(endpoint)
            with channel:
                transmit(channel, frame)
                if hasattr(channel, "poll") and not channel.poll(
                    180 if command in ("prepare", "confirm", "recover") else 4
                ):
                    raise TimeoutError
                reply, _ = decode_frame(key, receive(channel))
            if reply.get("request_nonce") != nonce or type(reply.get("ok")) is not bool:
                raise ValueError("reply mismatch")
            expected_fields = {"ok", "request_nonce", "result" if reply["ok"] else "error"}
            if set(reply) != expected_fields or (
                not reply["ok"] and not isinstance(reply["error"], str)
            ):
                raise ValueError("invalid reply schema")
            if not reply["ok"]:
                raise FloChatError(reply["error"])
            return reply["result"]
        except (OSError, ValueError, TypeError, EOFError, TimeoutError, RecursionError):
            raise FloChatError(
                "Core connection interrupted. A confirmation may have "
                "reached it; inspect history/chat, "
                "never retry automatically. Reopen explicitly; old approvals cannot be restored."
            ) from None
        finally:
            if channel is not None:
                channel.close()
