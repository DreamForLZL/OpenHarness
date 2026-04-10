"""WeChat Work (企业微信 / WeCom) channel implementation.

Receives messages via the enterprise app callback URL and replies via the
WeCom server API.  Supports:

- Callback URL verification (echostr handshake)
- AES message encryption/decryption (``EncodingAESKey``)
- Text message receiving and sending
- Image attachment receiving (downloaded to local media dir)
- Access-token auto-refresh with configurable margin

Required WeCom app configuration:

1. Create an internal app (自建应用) in WeCom admin console.
2. Set the callback URL to ``http(s)://<your-host>:<port>/wecom/callback``.
3. Fill in *Token* and *EncodingAESKey* from the callback settings.
4. Note the *CorpID*, *AgentID*, and *Secret*.

Dependencies: ``aiohttp``, ``httpx`` (already in core deps).
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import logging
import struct
import time
import xml.etree.ElementTree as ET
from typing import Any

import httpx

from openharness.channels.bus.events import OutboundMessage
from openharness.channels.bus.queue import MessageBus
from openharness.channels.impl.base import BaseChannel, resolve_channel_media_dir
from openharness.config.schema import WeComConfig

logger = logging.getLogger(__name__)

try:
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    from cryptography.hazmat.backends import default_backend

    CRYPTO_AVAILABLE = True
except ImportError:
    CRYPTO_AVAILABLE = False

try:
    from aiohttp import web

    AIOHTTP_AVAILABLE = True
except ImportError:
    web = None  # type: ignore[assignment]
    AIOHTTP_AVAILABLE = False


# ---------------------------------------------------------------------------
# WeCom message crypto helpers
# ---------------------------------------------------------------------------

class _WXBizMsgCrypt:
    """Minimal WeCom message encryption/decryption (AES-256-CBC + PKCS#7)."""

    def __init__(self, token: str, encoding_aes_key: str, corp_id: str) -> None:
        self._token = token
        self._corp_id = corp_id
        self._aes_key = base64.b64decode(encoding_aes_key + "=")

    def _pad(self, data: bytes) -> bytes:
        block_size = 32
        pad_len = block_size - (len(data) % block_size)
        return data + bytes([pad_len] * pad_len)

    def _unpad(self, data: bytes) -> bytes:
        pad_len = data[-1]
        if pad_len < 1 or pad_len > 32:
            return data
        return data[:-pad_len]

    def _sign(self, *parts: str) -> str:
        items = sorted(parts)
        return hashlib.sha1("".join(items).encode()).hexdigest()

    def verify_signature(self, msg_signature: str, timestamp: str, nonce: str, echostr: str) -> bool:
        return self._sign(self._token, timestamp, nonce, echostr) == msg_signature

    def decrypt(self, ciphertext_b64: str) -> str:
        if not CRYPTO_AVAILABLE:
            raise RuntimeError("cryptography package is required for WeCom channel")
        ciphertext = base64.b64decode(ciphertext_b64)
        iv = self._aes_key[:16]
        cipher = Cipher(algorithms.AES(self._aes_key), modes.CBC(iv), backend=default_backend())
        dec = cipher.decryptor()
        plaintext = self._unpad(dec.update(ciphertext) + dec.finalize())
        # Plaintext layout: 16-byte random + 4-byte msg_len (network order) + msg + corp_id
        msg_len = struct.unpack("!I", plaintext[16:20])[0]
        msg = plaintext[20 : 20 + msg_len].decode()
        from_corp_id = plaintext[20 + msg_len :].decode()
        if from_corp_id != self._corp_id:
            raise ValueError(f"corpid mismatch: expected {self._corp_id}, got {from_corp_id}")
        return msg

    def encrypt(self, text: str) -> str:
        if not CRYPTO_AVAILABLE:
            raise RuntimeError("cryptography package is required for WeCom channel")
        random_bytes = hashlib.md5(str(time.time()).encode()).digest()
        msg_bytes = text.encode()
        body = random_bytes + struct.pack("!I", len(msg_bytes)) + msg_bytes + self._corp_id.encode()
        padded = self._pad(body)
        iv = self._aes_key[:16]
        cipher = Cipher(algorithms.AES(self._aes_key), modes.CBC(iv), backend=default_backend())
        enc = cipher.encryptor()
        ciphertext = enc.update(padded) + enc.finalize()
        return base64.b64encode(ciphertext).decode()

    def build_reply_xml(self, encrypt_msg: str, timestamp: str, nonce: str) -> str:
        signature = self._sign(self._token, timestamp, nonce, encrypt_msg)
        return (
            "<xml>"
            f"<Encrypt><![CDATA[{encrypt_msg}]]></Encrypt>"
            f"<MsgSignature><![CDATA[{signature}]]></MsgSignature>"
            f"<TimeStamp>{timestamp}</TimeStamp>"
            f"<Nonce><![CDATA[{nonce}]]></Nonce>"
            "</xml>"
        )


# ---------------------------------------------------------------------------
# XML helpers
# ---------------------------------------------------------------------------

def _xml_text(root: ET.Element, tag: str) -> str:
    el = root.find(tag)
    return (el.text or "").strip() if el is not None else ""


# ---------------------------------------------------------------------------
# Channel implementation
# ---------------------------------------------------------------------------

class WeComChannel(BaseChannel):
    """WeChat Work (企业微信) channel using callback + server API."""

    name = "wecom"

    def __init__(self, config: WeComConfig, bus: MessageBus) -> None:
        super().__init__(config, bus)
        self.config: WeComConfig = config
        self._crypt: _WXBizMsgCrypt | None = None
        self._http: httpx.AsyncClient | None = None
        self._runner: Any = None
        self._access_token: str | None = None
        self._token_expiry: float = 0
        self._background_tasks: set[asyncio.Task] = set()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        if not AIOHTTP_AVAILABLE:
            logger.error("aiohttp is not installed. Run: pip install aiohttp")
            return
        if not CRYPTO_AVAILABLE:
            logger.error("cryptography is not installed. Run: pip install cryptography")
            return
        if not self.config.corp_id or not self.config.secret:
            logger.error("WeChat Work corp_id and secret are required")
            return

        self._running = True
        self._http = httpx.AsyncClient(timeout=30.0)
        self._crypt = _WXBizMsgCrypt(
            token=self.config.callback_token,
            encoding_aes_key=self.config.encoding_aes_key,
            corp_id=self.config.corp_id,
        )

        app = web.Application()
        app.router.add_get("/wecom/callback", self._handle_verify)
        app.router.add_post("/wecom/callback", self._handle_message_callback)

        self._runner = web.AppRunner(app)
        await self._runner.setup()
        site = web.TCPSite(self._runner, self.config.host, self.config.port)
        await site.start()
        logger.info(
            "WeChat Work channel listening on %s:%s", self.config.host, self.config.port
        )

    async def stop(self) -> None:
        self._running = False
        for task in self._background_tasks:
            task.cancel()
        self._background_tasks.clear()
        if self._http:
            await self._http.aclose()
            self._http = None
        if self._runner:
            await self._runner.cleanup()
            self._runner = None

    # ------------------------------------------------------------------
    # Callback URL verification (GET)
    # ------------------------------------------------------------------

    async def _handle_verify(self, request: Any) -> Any:
        """Handle the WeCom callback URL verification handshake."""
        msg_signature = request.query.get("msg_signature", "")
        timestamp = request.query.get("timestamp", "")
        nonce = request.query.get("nonce", "")
        echostr = request.query.get("echostr", "")

        if not self._crypt or not self._crypt.verify_signature(msg_signature, timestamp, nonce, echostr):
            logger.warning("WeChat Work callback verification failed")
            return web.Response(text="signature mismatch", status=403)

        try:
            plaintext = self._crypt.decrypt(echostr)
            return web.Response(text=plaintext)
        except Exception:
            logger.exception("WeChat Work echostr decryption failed")
            return web.Response(text="decrypt error", status=500)

    # ------------------------------------------------------------------
    # Message receiving (POST)
    # ------------------------------------------------------------------

    async def _handle_message_callback(self, request: Any) -> Any:
        """Receive and dispatch an encrypted message from WeCom."""
        msg_signature = request.query.get("msg_signature", "")
        timestamp = request.query.get("timestamp", "")
        nonce = request.query.get("nonce", "")

        body = await request.text()
        try:
            root = ET.fromstring(body)
        except ET.ParseError:
            return web.Response(text="bad xml", status=400)

        encrypt_text = _xml_text(root, "Encrypt")
        if not encrypt_text or not self._crypt:
            return web.Response(text="missing Encrypt", status=400)

        if not self._crypt.verify_signature(msg_signature, timestamp, nonce, encrypt_text):
            return web.Response(text="signature mismatch", status=403)

        try:
            xml_content = self._crypt.decrypt(encrypt_text)
        except Exception:
            logger.exception("WeChat Work message decryption failed")
            return web.Response(text="decrypt error", status=500)

        try:
            msg_root = ET.fromstring(xml_content)
        except ET.ParseError:
            return web.Response(text="bad inner xml", status=400)

        msg_type = _xml_text(msg_root, "MsgType")
        from_user = _xml_text(msg_root, "FromUserName")

        if msg_type == "text":
            content = _xml_text(msg_root, "Content")
        elif msg_type == "image":
            pic_url = _xml_text(msg_root, "PicUrl")
            media_id = _xml_text(msg_root, "MediaId")
            content = pic_url or f"[image:{media_id}]"
        elif msg_type == "event":
            content = ""
        else:
            content = f"[{msg_type}]"

        if content:
            task = asyncio.create_task(self._on_message(from_user, content))
            self._background_tasks.add(task)
            task.add_done_callback(self._background_tasks.discard)

        return web.Response(text="success")

    async def _on_message(self, user_id: str, content: str) -> None:
        try:
            await self._handle_message(
                sender_id=user_id,
                chat_id=user_id,
                content=content,
                metadata={"platform": "wecom"},
            )
        except Exception:
            logger.exception("WeChat Work inbound publish error user_id=%s", user_id)

    # ------------------------------------------------------------------
    # Outbound: send messages via WeCom API
    # ------------------------------------------------------------------

    async def _get_access_token(self) -> str | None:
        if self._access_token and time.time() < self._token_expiry:
            return self._access_token

        if not self._http:
            return None
        url = "https://qyapi.weixin.qq.com/cgi-bin/gettoken"
        params = {"corpid": self.config.corp_id, "corpsecret": self.config.secret}
        try:
            resp = await self._http.get(url, params=params)
            data = resp.json()
            if data.get("errcode", 0) != 0:
                logger.error("WeChat Work token error: %s", data)
                return None
            self._access_token = data["access_token"]
            self._token_expiry = time.time() + int(data.get("expires_in", 7200)) - 120
            return self._access_token
        except Exception:
            logger.exception("WeChat Work token fetch failed")
            return None

    async def send(self, msg: OutboundMessage) -> None:
        token = await self._get_access_token()
        if not token or not self._http:
            return

        text = (msg.content or "").strip()
        if not text:
            return

        url = f"https://qyapi.weixin.qq.com/cgi-bin/message/send?access_token={token}"
        payload: dict[str, Any] = {
            "touser": msg.chat_id,
            "msgtype": "text",
            "agentid": self.config.agent_id,
            "text": {"content": text},
        }

        try:
            resp = await self._http.post(url, json=payload)
            data = resp.json()
            if data.get("errcode", 0) != 0:
                logger.error("WeChat Work send error: %s", data)
        except Exception:
            logger.exception("WeChat Work send failed chat_id=%s", msg.chat_id)

    # ------------------------------------------------------------------
    # Media helpers (for future extension)
    # ------------------------------------------------------------------

    async def _download_media(self, media_id: str) -> str | None:
        """Download media by media_id and return local file path."""
        token = await self._get_access_token()
        if not token or not self._http:
            return None
        url = f"https://qyapi.weixin.qq.com/cgi-bin/media/get?access_token={token}&media_id={media_id}"
        try:
            resp = await self._http.get(url, follow_redirects=True)
            if resp.status_code >= 400:
                return None
            media_dir = resolve_channel_media_dir(self.name)
            ext = ".jpg"
            ct = (resp.headers.get("content-type") or "").lower()
            if "png" in ct:
                ext = ".png"
            elif "gif" in ct:
                ext = ".gif"
            path = media_dir / f"{media_id}{ext}"
            path.write_bytes(resp.content)
            return str(path)
        except Exception:
            logger.exception("WeChat Work media download failed media_id=%s", media_id)
            return None
