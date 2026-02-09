"""
Webhook para WhatsApp Cloud API.
GET: verificación (Meta envía hub.mode, hub.verify_token, hub.challenge).
POST: mensajes entrantes (payload con entry -> changes -> value -> messages).
"""
import json
import logging
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from .models import Reclamo
from .services.handlers import process_incoming_message
from .services.whatsapp_api import is_whatsapp_configured

logger = logging.getLogger(__name__)

VERIFY_TOKEN = getattr(settings, 'WHATSAPP_VERIFY_TOKEN', 'catering_verify_token')


def _extract_incoming_text(payload: dict) -> list[tuple[str, str, str | None]]:
    """
    Extrae de un payload de webhook los mensajes de texto entrantes.
    Devuelve lista de (from_phone, text, message_id).
    """
    results = []
    try:
        for entry in payload.get('entry', []):
            for change in entry.get('changes', []):
                if change.get('field') != 'messages':
                    continue
                value = change.get('value', {})
                for msg in value.get('messages', []):
                    if msg.get('type') != 'text':
                        continue
                    from_wa_id = msg.get('from')
                    body = (msg.get('text') or {}).get('body', '').strip()
                    msg_id = msg.get('id')
                    if from_wa_id and body:
                        results.append((from_wa_id, body, msg_id))
    except Exception as e:
        logger.exception("Error extrayendo mensajes del webhook: %s", e)
    return results


@csrf_exempt
@require_http_methods(['GET', 'POST'])
def webhook(request):
    """
    GET: verificación del webhook por Meta.
    POST: recibe mensajes entrantes y los procesa.
    """
    if request.method == 'GET':
        mode = request.GET.get('hub.mode')
        token = request.GET.get('hub.verify_token')
        challenge = request.GET.get('hub.challenge')
        if mode == 'subscribe' and token == VERIFY_TOKEN and challenge:
            return HttpResponse(challenge, content_type='text/plain')
        return HttpResponse('Forbidden', status=403)

    if not is_whatsapp_configured():
        return JsonResponse({'error': 'WhatsApp not configured'}, status=503)
    try:
        payload = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    for from_phone, text, message_id in _extract_incoming_text(payload):
        try:
            process_incoming_message(from_phone, message_id, text)
        except Exception as e:
            logger.exception("Error procesando mensaje WhatsApp from=%s: %s", from_phone, e)
    return JsonResponse({'ok': True})


@login_required
def reclamos_lista(request):
    """Lista de reclamos/consultas recibidos por WhatsApp (solo staff)."""
    reclamos = Reclamo.objects.select_related('cliente').order_by('-fecha_recibido')[:200]
    return render(request, 'whatsapp/reclamos_lista.html', {'reclamos': reclamos})
