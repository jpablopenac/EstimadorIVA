"""
Lógica de alertas de reinversión y cálculo de compras necesarias.
"""
from dataclasses import dataclass
from datetime import date, datetime


TASA_IVA = 0.19


@dataclass
class AlertaReinversion:
    activa: bool
    iva_neto: int
    umbral_alerta: int
    umbral_objetivo: int
    credito_necesario: int        # IVA adicional que se necesita como crédito
    compra_neta_necesaria: int    # monto neto a comprar para generar ese crédito
    compra_total_necesaria: int   # compra_neta + IVA (lo que sale la factura)
    dias_para_fin_mes: int
    aviso_ventana: bool           # True si quedan ≤ 10 días para cierre


SUGERENCIAS_DEFAULT = [
    "Equipos y maquinaria industrial",
    "Herramientas, repuestos y consumibles del giro",
    "Vehículos de trabajo o transporte de carga",
    "Equipos computacionales y tecnología",
    "Insumos y materiales con factura electrónica (tipo 33)",
]


def calcular_alerta(
    iva_neto: int,
    umbral_alerta: int = 500_000,
    umbral_objetivo: int = 0,
    fecha_ref: date | None = None,
) -> AlertaReinversion:
    """
    Evalúa si se activa la alerta de reinversión y calcula cuánto comprar.
    `fecha_ref` es la fecha de referencia (hoy por defecto) para calcular
    los días que faltan para el fin del mes.
    """
    if fecha_ref is None:
        fecha_ref = date.today()

    # Días para fin del mes actual
    if fecha_ref.month == 12:
        primer_dia_sig = date(fecha_ref.year + 1, 1, 1)
    else:
        primer_dia_sig = date(fecha_ref.year, fecha_ref.month + 1, 1)
    dias_para_fin = (primer_dia_sig - fecha_ref).days

    activa = iva_neto > umbral_alerta
    credito_necesario = max(0, iva_neto - umbral_objetivo) if activa else 0
    compra_neta = int(credito_necesario / TASA_IVA) if credito_necesario > 0 else 0
    compra_total = compra_neta + credito_necesario

    return AlertaReinversion(
        activa=activa,
        iva_neto=iva_neto,
        umbral_alerta=umbral_alerta,
        umbral_objetivo=umbral_objetivo,
        credito_necesario=credito_necesario,
        compra_neta_necesaria=compra_neta,
        compra_total_necesaria=compra_total,
        dias_para_fin_mes=dias_para_fin,
        aviso_ventana=dias_para_fin <= 10,
    )


def fecha_vencimiento_f29(periodo: str | None) -> str:
    """
    Retorna la fecha de vencimiento del F29 para un período AAAAMM.
    El F29 vence el día 12 del mes siguiente.
    """
    if not periodo or len(periodo) < 6:
        return "día 12 del mes siguiente"
    try:
        anio = int(periodo[:4])
        mes = int(periodo[4:6])
        if mes == 12:
            mes_sig, anio_sig = 1, anio + 1
        else:
            mes_sig, anio_sig = mes + 1, anio
        nombres_mes = [
            "", "enero", "febrero", "marzo", "abril", "mayo", "junio",
            "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
        ]
        return f"12 de {nombres_mes[mes_sig]} {anio_sig}"
    except (ValueError, IndexError):
        return "día 12 del mes siguiente"
