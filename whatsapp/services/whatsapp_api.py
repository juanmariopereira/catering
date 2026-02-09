"""
Cliente para WhatsApp Cloud API (Meta).
Envía mensajes de texto y expone si la integración está configurada.
"""
import re
import logging

import httpx
from django.conf import settings

from clients.models import Cliente

logger = logging.getLogger(__name__)

# URL base de la API de WhatsApp Cloud
WHATSAPP_API_BASE = "https://graph.facebook.com/v21.0"


def _get_config():
    """Obtiene token y phone_number_id desde settings (variables de entorno)."""
    token = getattr(settings, 'WHATSAPP_ACCESS_TOKEN', None) or getattr(settings, 'WHATSAPP_TOKEN', None)
    phone_id = getattr(settings, 'WHATSAPP_PHONE_NUMBER_ID', None)
    return token, phone_id


def is_whatsapp_configured():
    """True si hay token y phone_number_id configurados."""
    token, phone_id = _get_config()
    return bool(token and phone_id)


def _normalize_phone(phone: str) -> str:
    """Deja solo dígitos del número para comparar."""
    if not phone:
        return ""
    return re.sub(r"\D", "", str(phone)).strip()


def get_cliente_by_phone(phone_whatsapp: str) -> Cliente | None:
    """
    Busca un cliente por teléfono.
    Normaliza ambos números (solo dígitos) y compara; acepta con/sin código de país.
    """
    if not phone_whatsapp:
        return None
    normalized = _normalize_phone(phone_whatsapp)
    if not normalized:
        return None
    # Buscar por coincidencia exacta o por sufijo (ej. 59171234567 vs 71234567)
    for cliente in Cliente.objects.filter(activo=True).iterator():
        tel = _normalize_phone(cliente.telefono)
        if not tel:
            continue
        if normalized == tel:
            return cliente
        # Sin código de país en BD: 71234567 vs 59171234567
        if normalized.endswith(tel) or tel.endswith(normalized):
            return cliente
    return None


def send_whatsapp_text(to_phone: str, text: str) -> bool:
    """
    Envía un mensaje de texto por WhatsApp Cloud API.
    to_phone: número con código de país, sin '+', ej. '59171234567'.
    Devuelve True si se envió correctamente.
    """
    token, phone_id = _get_config()
    if not token or not phone_id:
        logger.warning("WhatsApp no configurado: falta WHATSAPP_ACCESS_TOKEN o WHATSAPP_PHONE_NUMBER_ID")
        return False
    to_phone = _normalize_phone(to_phone)
    if not to_phone:
        logger.warning("send_whatsapp_text: número de destino vacío")
        return False
    url = f"{WHATSAPP_API_BASE}/{phone_id}/messages"
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": to_phone,
        "type": "text",
        "text": {"body": text[:4096]},  # límite de caracteres por mensaje
    }
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    try:
        with httpx.Client(timeout=15.0) as client:
            resp = client.post(url, json=payload, headers=headers)
        if resp.status_code in (200, 201):
            return True
        logger.warning(
            "WhatsApp API error: status=%s body=%s",
            resp.status_code,
            resp.text[:500],
        )
        return False
    except Exception as e:
        logger.exception("send_whatsapp_text failed: %s", e)
        return False
