"""
Genera el texto del estado de cuenta de un cliente para enviar por WhatsApp.
Basado en la lógica de billing.views.estado_cuentas_cliente_detalle.
"""
from datetime import date
from decimal import Decimal

from django.utils import timezone

from billing.models import Cobro
from contracts.models import Contrato
from clients.models import Cliente


def _cobros_filtrados(contrato, fd=None, fh=None):
    cobros = sorted(
        contrato.cobros.all(),
        key=lambda c: (c.periodo_hasta or date.min, c.pk),
        reverse=True,
    )
    if fd is not None:
        cobros = [c for c in cobros if c.periodo_desde >= fd]
    if fh is not None:
        cobros = [c for c in cobros if (c.periodo_hasta or date.min) <= fh]
    return cobros


def build_estado_cuenta_texto(
    cliente: Cliente,
    fecha_desde: date | None = None,
    fecha_hasta: date | None = None,
    max_cobros_por_contrato: int = 15,
) -> str:
    """
    Construye un resumen en texto del estado de cuenta del cliente,
    adecuado para WhatsApp (sin HTML, líneas cortas).
    """
    contratos = (
        Contrato.objects.filter(cliente=cliente)
        .select_related('plan')
        .prefetch_related('cobros__pagos')
        .order_by('-fecha_inicio')
    )
    if not contratos.exists():
        return (
            f"Hola {cliente.nombre}.\n\n"
            "No tenemos registrados contratos ni cobros para tu cuenta. "
            "Si crees que hay un error, por favor contáctanos."
        )
    lineas = [
        f"*Estado de cuenta — {cliente.nombre}*",
        "",
    ]
    total_monto = Decimal("0")
    total_pagado = Decimal("0")
    total_pendiente = Decimal("0")
    for contrato in contratos:
        cobros = _cobros_filtrados(contrato, fecha_desde, fecha_hasta)
        if not cobros:
            continue
        sub_monto = sum(c.monto for c in cobros)
        sub_pagado = sum(c.calcular_monto_pagado() for c in cobros)
        sub_pendiente = sub_monto - sub_pagado
        total_monto += sub_monto
        total_pagado += sub_pagado
        total_pendiente += sub_pendiente
        lineas.append(f"📋 *{contrato.plan.nombre}* ({contrato.get_frecuencia_pago_display()})")
        for cobro in cobros[:max_cobros_por_contrato]:
            vto = cobro.fecha_vencimiento.strftime("%d/%m/%Y") if cobro.fecha_vencimiento else "—"
            periodo = f"{cobro.periodo_desde:%d/%m} - {cobro.periodo_hasta:%d/%m}"
            pend = cobro.monto_pendiente()
            estado = "✅" if cobro.estado == "pagada" else ("⚠️ Vencido" if cobro.estado == "vencida" else "⏳ Pendiente")
            lineas.append(f"  {cobro.numero_cobro or cobro.id} | {periodo} | Vto: {vto}")
            lineas.append(f"    Bs. {cobro.monto:.2f} | Pagado: Bs. {cobro.calcular_monto_pagado():.2f} | Pend: Bs. {pend:.2f} {estado}")
        if len(cobros) > max_cobros_por_contrato:
            lineas.append(f"  ... y {len(cobros) - max_cobros_por_contrato} cobros más.")
        lineas.append(f"  Subtotal: Bs. {sub_monto:.2f} | Pagado: Bs. {sub_pagado:.2f} | Pendiente: Bs. {sub_pendiente:.2f}")
        lineas.append("")
    lineas.append("—" * 20)
    lineas.append(f"*Total cobrado:* Bs. {total_monto:.2f}")
    lineas.append(f"*Total pagado:* Bs. {total_pagado:.2f}")
    lineas.append(f"*Saldo pendiente:* Bs. {total_pendiente:.2f}")
    lineas.append("")
    lineas.append("Gracias por confiar en nosotros. Cualquier duda, respondé por este medio.")
    return "\n".join(lineas)
