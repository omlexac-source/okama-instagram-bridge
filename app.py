"""
Okama Instagram Control - Webhook Server (Production)
Receives WhatsApp messages, filters by authorized number,
parses commands, and executes actions.
Deploy on Render.com (free tier) or any cloud provider.
"""

import hashlib
import hmac
import json
import logging
import os
import re
import sys
import threading
from pathlib import Path

import requests
from flask import Flask, request, jsonify

app = Flask(__name__)

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)

GRAPH_API_BASE = "https://graph.facebook.com/v21.0"

# ---------------------------------------------------------------------------
# Config loaded from environment variables
# ---------------------------------------------------------------------------

CONFIG = {
    "verify_token": os.environ.get("WHATSAPP_VERIFY_TOKEN", ""),
    "app_secret": os.environ.get("WHATSAPP_APP_SECRET", ""),
    "authorized_number": os.environ.get("AUTHORIZED_PHONE_NUMBER", ""),
    "whatsapp_phone_number_id": os.environ.get("WHATSAPP_PHONE_NUMBER_ID", ""),
    "whatsapp_access_token": os.environ.get("WHATSAPP_ACCESS_TOKEN", ""),
    "auto_reply": os.environ.get("AUTO_REPLY", "true").lower() == "true",
}

logger.info(f"Authorized number configured: {CONFIG['authorized_number'] or 'ANY (NOT SET!)'}")


# ===========================================================================
# Security helpers
# ===========================================================================

def verify_signature(payload: bytes, signature: str, app_secret: str) -> bool:
    """Verify X-Hub-Signature-256 from Meta."""
    if not app_secret or not signature:
        return False
    expected = hmac.new(
        app_secret.encode("utf-8"),
        payload,
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(f"sha256={expected}", signature)


# ===========================================================================
# WhatsApp reply sender
# ===========================================================================

def send_whatsapp_reply(to_number: str, message: str) -> bool:
    """Send a WhatsApp text reply via Cloud API."""
    phone_number_id = CONFIG["whatsapp_phone_number_id"]
    access_token = CONFIG["whatsapp_access_token"]

    if not phone_number_id or not access_token:
        logger.error("WhatsApp credentials not configured, cannot send reply")
        return False

    url = f"{GRAPH_API_BASE}/{phone_number_id}/messages"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": to_number,
        "type": "text",
        "text": {"body": message},
    }

    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=10)
        if resp.status_code == 200:
            logger.info(f"Reply sent to {to_number}")
            return True
        else:
            logger.error(f"Failed to send reply: {resp.status_code} {resp.text}")
            return False
    except Exception as e:
        logger.error(f"Error sending reply: {e}")
        return False


# ===========================================================================
# Command Parser
# ===========================================================================

def normalize_text(text: str) -> str:
    text = text.strip().lower()
    text = re.sub(r"\s+", " ", text)
    return text


def extract_urls(text: str) -> list:
    url_pattern = r"https?://[^\s,]+"
    return re.findall(url_pattern, text)


def extract_caption(text: str) -> str:
    text_lower = text.lower()
    markers = [
        "caption", "leyenda", "texto", "text", "con texto",
        "with caption", "with text", "titled", "titulado",
        "descripcion", "description", "desc",
    ]
    for marker in markers:
        if marker in text_lower:
            idx = text_lower.index(marker) + len(marker)
            remaining = text[idx:].strip()
            remaining = re.sub(r"^[\"'\s:]+", "", remaining)
            return remaining.strip()
    return ""


def parse_command(message: str) -> dict:
    """Parse a WhatsApp message into a structured command."""
    text = normalize_text(message)
    result = {"action": "unknown", "media_type": "image", "media_urls": [], "caption": "", "raw": message}

    # Help
    if text in ("help", "ayuda", "?", "h", "commands", "comandos"):
        result["action"] = "help"
        return result

    # Status
    if text in ("status", "estado", "config", "configuracion"):
        result["action"] = "status"
        return result

    # Check if it's a publish command
    publish_verbs = ["post", "publish", "publicar", "subir", "compartir", "enviar"]
    if not any(v in text for v in publish_verbs):
        return result

    # Determine media type
    if any(k in text for k in ["carousel", "carrusel", "multiple", "varias", "album"]):
        result["media_type"] = "carousel"
    elif any(k in text for k in ["reel", "reels", "short", "corto"]):
        result["media_type"] = "reel"
    elif any(k in text for k in ["video", "mp4", "movie", "pelicula"]):
        result["media_type"] = "video"
    elif any(k in text for k in ["image", "images", "photo", "foto", "picture", "pic", "imagen"]):
        result["media_type"] = "image"
    else:
        urls = extract_urls(text)
        if urls:
            if any(u.lower().endswith((".mp4", ".mov", ".avi")) for u in urls):
                result["media_type"] = "video"
            else:
                result["media_type"] = "image"

    # Extract URLs and caption
    result["media_urls"] = extract_urls(text)
    result["caption"] = extract_caption(message)

    if not result["media_urls"] and result["media_type"] in ("image", "video", "reel"):
        return {"action": "unknown", "media_type": result["media_type"], "media_urls": [], "caption": "", "raw": message}

    if result["media_type"] == "carousel" and len(result["media_urls"]) < 2:
        all_urls = re.findall(r"https?://[^\s]+", message)
        if len(all_urls) >= 2:
            result["media_urls"] = all_urls
        else:
            return {"action": "unknown", "media_type": "carousel", "media_urls": [], "caption": "", "raw": message}

    result["action"] = f"publish_{result['media_type']}"
    return result


def get_help_text() -> str:
    return (
        "*Comandos disponibles para Instagram:*\n\n"
        "*Publicar foto:*\n"
        "post image <URL> caption <texto>\n"
        "publicar foto <URL> leyenda <texto>\n\n"
        "*Publicar video / reel:*\n"
        "post reel <URL> caption <texto>\n"
        "publicar reel <URL> leyenda <texto>\n\n"
        "*Publicar carrusel (2-10 fotos):*\n"
        "post carousel <URL1>, <URL2> caption <texto>\n"
        "publicar carrusel <URL1>, <URL2> leyenda <texto>\n\n"
        "*Otras:*\n"
        "help / ayuda - Ver este mensaje\n"
        "status / estado - Ver configuracion\n\n"
        "Las imagenes deben estar en URLs publicas. Maximo 25 publicaciones por dia."
    )


# ===========================================================================
# Action execution (Instagram placeholder + general commands)
# ===========================================================================

def execute_command(cmd: dict) -> str:
    """Execute the parsed command and return a response message."""
    action = cmd["action"]

    if action == "help":
        return get_help_text()

    elif action == "status":
        wa_ok = bool(CONFIG["whatsapp_phone_number_id"] and CONFIG["whatsapp_access_token"])
        auth_num = CONFIG["authorized_number"] or "(NO CONFIGURADO - ACEPTA TODOS)"
        return (
            "*Estado del sistema:*\n\n"
            f"WhatsApp Business: {'Conectado' if wa_ok else 'NO conectado'}\n"
            f"Numero autorizado: {auth_num}\n\n"
            "Instagram aun no configurado. Dame INSTAGRAM_USER_ID e INSTAGRAM_ACCESS_TOKEN para completar."
        )

    elif action.startswith("publish_"):
        media_type = cmd["media_type"]
        urls = cmd["media_urls"]
        caption = cmd["caption"]

        if not urls:
            return "*Error:* No encontre ninguna URL de imagen o video en tu mensaje."

        # For now, Instagram publishing requires IG credentials which the user hasn't provided yet
        ig_user_id = os.environ.get("INSTAGRAM_USER_ID", "")
        ig_token = os.environ.get("INSTAGRAM_ACCESS_TOKEN", "")

        if not ig_user_id or not ig_token:
            return (
                "*Comando recibido:*\n"
                f"Tipo: {media_type}\n"
                f"URLs: {len(urls)}\n"
                f"Caption: {caption or '(sin texto)'}\n\n"
                "Instagram aun no esta configurado. Dame tu INSTAGRAM_USER_ID e INSTAGRAM_ACCESS_TOKEN para que publique automaticamente."
            )

        # TODO: Implement Instagram publishing here once credentials are available
        return (
            f"*Comando recibido:* {media_type}\n"
            f"URLs: {', '.join(urls)}\n"
            f"Caption: {caption}\n\n"
            "(Instagram publishing no implementado - falta configurar IG)"
        )

    else:
        return (
            "*No entendi el comando.*\n\n"
            f"Recibi: '{cmd['raw'][:100]}'\n\n"
            f"{get_help_text()}"
        )


# ===========================================================================
# Async message processing
# ===========================================================================

def process_message_async(sender: str, message_text: str):
    """Process message in background thread."""
    logger.info(f"Processing message from {sender}: {message_text[:100]}")

    cmd = parse_command(message_text)
    logger.info(f"Parsed action: {cmd['action']}")

    response = execute_command(cmd)

    if CONFIG["auto_reply"]:
        send_whatsapp_reply(sender, response)


# ===========================================================================
# Flask routes
# ===========================================================================

@app.route("/", methods=["GET"])
def root():
    return jsonify({
        "status": "ok",
        "service": "okama-instagram-bridge",
        "version": "1.0.0"
    })


@app.route("/health", methods=["GET"])
def health():
    wa_ok = bool(CONFIG["whatsapp_phone_number_id"] and CONFIG["whatsapp_access_token"])
    return jsonify({
        "status": "healthy",
        "whatsapp_connected": wa_ok,
        "authorized_number_set": bool(CONFIG["authorized_number"]),
    })


@app.route("/webhook", methods=["GET"])
def webhook_verify():
    """Handle webhook verification from Meta (GET request)."""
    mode = request.args.get("hub.mode", "")
    token = request.args.get("hub.verify_token", "")
    challenge = request.args.get("hub.challenge", "")

    logger.info(f"Verification request: mode={mode}, token={token}")

    if mode == "subscribe" and token == CONFIG["verify_token"]:
        logger.info("Webhook verification successful")
        return challenge, 200
    else:
        logger.warning(f"Verification failed: token mismatch or wrong mode")
        return "Verification failed", 403


@app.route("/webhook", methods=["POST"])
def webhook_receive():
    """Handle incoming WhatsApp messages (POST request)."""
    raw_body = request.get_data()

    # Verify signature if app secret is configured
    signature = request.headers.get("X-Hub-Signature-256", "")
    if CONFIG["app_secret"] and not verify_signature(raw_body, signature, CONFIG["app_secret"]):
        logger.warning("Invalid signature, rejecting request")
        return "Invalid signature", 403

    try:
        data = json.loads(raw_body)
    except json.JSONDecodeError:
        logger.error("Invalid JSON payload")
        return "Invalid JSON", 400

    # Extract and process messages
    try:
        entries = data.get("entry", [])
        for entry in entries:
            for change in entry.get("changes", []):
                value = change.get("value", {})
                messages = value.get("messages", [])
                for msg in messages:
                    if msg.get("type") != "text":
                        continue

                    sender = msg.get("from", "")
                    message_text = msg.get("text", {}).get("body", "")

                    logger.info(f"Message from {sender}: {message_text[:80]}")

                    # Filter by authorized number
                    if CONFIG["authorized_number"]:
                        auth = CONFIG["authorized_number"].lstrip("+")
                        sender_clean = sender.lstrip("+")
                        if sender_clean != auth:
                            logger.warning(f"Rejected message from unauthorized number: {sender}")
                            continue

                    # Process in background
                    thread = threading.Thread(
                        target=process_message_async,
                        args=(sender, message_text),
                    )
                    thread.daemon = True
                    thread.start()

    except Exception as e:
        logger.exception("Error processing webhook")

    return "EVENT_RECEIVED", 200


# ===========================================================================
# Entry point
# ===========================================================================

if __name__ == "__main__":
    # Development only - production uses Gunicorn
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=False)
