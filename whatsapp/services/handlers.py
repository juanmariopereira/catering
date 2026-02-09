"""
Procesa mensajes entrantes de WhatsApp y decide la respuesta:
- estado de cuenta (cuando el cliente lo pide)
- registro de reclamos
- mensaje de ayuda
"""
import re
import logging
from datetime import date

from django.utils import timezone

from .whatsapp_api import send_whatsapp_text, get_cliente_by_phone, is_whatsapp_configured
from .estado_cuenta import build_estado_cuenta_texto
from whatsapp.models import Reclamo

logger = logging.getLogger(__name__)

# Palabras clave para detectar intención (minúsculas)
ESTADO_CUENTA_KEYWORDS = [
    "estado de cuenta",
    "estado cuenta",
    "cuenta",
    "saldo",
    "debo",
    "deuda",
    "pendiente",
    "cobro",
    "factura",
]
RECLAMO_KEYWORDS = [
    "reclamo",
    "queja",
    "problema",
    "mal",
    "error",
    "no llegó",
    "no llego",
    "falta",
    "reclamo",
]


def _normalize_for_match(text: str) -> str:
    if not text:
        return ""
    text = text.lower().strip()
    text = re.sub(r"\s+", " ", text)
    return text


def _wants_estado_cuenta(text: str) -> bool:
    normalized = _normalize_for_match(text)
    if len(normalized) < 3:
        return False
    return any(kw in normalized for kw in ESTADO_CUENTA_KEYWORDS)


def _wants_reclamo(text: str) -> bool:
    normalized = _normalize_for_match(text)
    return any(kw in normalized for kw in RECLAMO_KEYWORDS)


def _mensaje_ayuda() -> str:
    return (
        "Hola 👋 Soy el asistente de *Catering Healthy Life*.\n\n"
        "Podés escribir:\n"
        "• *Estado de cuenta* o *saldo* — te envío tu resumen de cobros y pagos.\n"
        "• *Reclamo* o *queja* — registramos tu mensaje y te responderemos pronto.\n\n"
        "Cualquier otra consulta la tomamos como reclamo/consulta y te contestamos a la brevedad."
    )


def _mensaje_no_cliente() -> str:
    return (
        "No encontramos tu número asociado a un cliente. "
        "Por favor verificá que estés escribiendo desde el teléfono registrado o contactá a atención al cliente."
    )


def process_incoming_message(
    from_phone: str,
    message_id: str | None,
    text: str,
    save_reclamo_if_unknown: bool = True,
) -> str | None:
    """
    Procesa un mensaje entrante y opcionalmente envía respuesta por WhatsApp.
    from_phone: número del remitente (con código de país).
    message_id: id del mensaje en WhatsApp (para guardar en Reclamo).
    text: cuerpo del mensaje.
    save_reclamo_if_unknown: si True, mensajes no reconocidos se guardan como reclamo/consulta.

    Devuelve un string con el tipo de acción realizada ('estado_cuenta', 'reclamo', 'ayuda', 'unknown')
    o None si no se procesó.
    """
    if not text or not text.strip():
        return None
    text = text.strip()
    cliente = get_cliente_by_phone(from_phone)
    action = None

    if _wants_estado_cuenta(text):
        action = "estado_cuenta"
        if cliente:
            hoy = timezone.now().date()
            # Últimos 12 meses por defecto
            from datetime import timedelta
            fd = hoy - timedelta(days=365)
            msg = build_estado_cuenta_texto(cliente, fecha_desde=fd, fecha_hasta=hoy)
            send_whatsapp_text(from_phone, msg)
        else:
            send_whatsapp_text(from_phone, _mensaje_no_cliente())

    elif _wants_reclamo(text) or not cliente:
        # Cualquier mensaje que parezca reclamo, o si no es cliente (consultas genéricas)
        action = "reclamo"
        tipo = "reclamo" if _wants_reclamo(text) else "consulta"
        Reclamo.objects.create(
            cliente=cliente,
            telefono_whatsapp=from_phone,
            mensaje=text,
            mensaje_id_whatsapp=message_id or "",
            tipo=tipo,
        )
        if cliente:
            send_whatsapp_text(
                from_phone,
                "Recibimos tu mensaje. Nos pondremos en contacto a la brevedad. Gracias.",
            )
        else:
            send_whatsapp_text(
                from_phone,
                "Gracias por escribirnos. No encontramos tu número como cliente; "
                "igual registramos tu mensaje y te responderemos pronto.",
            )

    elif "ayuda" in _normalize_for_match(text) or "hola" in _normalize_for_match(text) or "opciones" in _normalize_for_match(text):
        action = "ayuda"
        send_whatsapp_text(from_phone, _mensaje_ayuda())

    else:
        if save_reclamo_if_unknown:
            action = "reclamo"
            Reclamo.objects.create(
                cliente=cliente,
                telefono_whatsapp=from_phone,
                mensaje=text,
                mensaje_id_whatsapp=message_id or "",
                tipo="consulta",
            )
            send_whatsapp_text(
                from_phone,
                "Gracias por tu mensaje. Lo registramos y te responderemos a la brevedad.",
            )
        else:
            action = "unknown"

    return action
