"""
Cálculo de IVA débito, crédito, neto y proyección del F29.
"""
from dataclasses import dataclass

import pandas as pd


# Tipos de documentos que generan débito/crédito fiscal
TIPOS_DEBITO = {33, 39}    # facturas electrónicas y boletas
TIPOS_CREDITO = {33}       # facturas de compra con IVA recuperable
TIPOS_NC = {61}            # notas de crédito (ya corregidas en parser)
TIPOS_EXENTOS = {34}       # facturas exentas (sin IVA)


@dataclass
class ResumenMes:
    # --- Ventas ---
    ventas_neto: int
    ventas_iva_debito: int
    ventas_total: int
    num_docs_venta: int
    num_docs_venta_con_iva: int

    # --- Compras ---
    compras_neto: int
    compras_iva_credito: int      # crédito fiscal efectivo (corregido)
    compras_total: int
    num_docs_compra: int
    num_docs_tipo33: int
    num_docs_tipo34: int
    num_docs_tipo61: int

    # --- IVA neto ---
    remanente_anterior: int
    iva_neto: int                 # débito - crédito - remanente (>0 paga, <0 a favor)

    # --- F29 ---
    ppm_tasa: float
    ppm_monto: int
    impuesto_unico: int
    f29_total: int


def calcular_resumen(
    df_compras: pd.DataFrame,
    df_ventas: pd.DataFrame,
    remanente_anterior: int = 0,
    ppm_tasa: float = 0.01,
    impuesto_unico: int = 0,
) -> ResumenMes:
    """Calcula todos los valores del resumen mensual a partir de los DataFrames."""

    # -----------------------------------------------------------------------
    # Ventas
    # -----------------------------------------------------------------------
    v_con_iva = df_ventas[df_ventas["Tipo Doc"].isin(TIPOS_DEBITO)]
    ventas_neto = int(df_ventas["Monto Neto"].sum())
    ventas_iva = int(v_con_iva["Monto IVA"].sum()) if "Monto IVA" in df_ventas.columns else 0
    ventas_total = int(df_ventas["Monto total"].sum()) if "Monto total" in df_ventas.columns else 0

    # -----------------------------------------------------------------------
    # Compras
    # -----------------------------------------------------------------------
    c_con_iva = df_compras[df_compras["Tipo Doc"].isin(TIPOS_CREDITO)]
    compras_neto = int(df_compras["Monto Neto"].sum())
    compras_iva = int(df_compras["Monto IVA Recuperable"].sum()) if "Monto IVA Recuperable" in df_compras.columns else 0
    compras_total = int(df_compras["Monto Total"].sum()) if "Monto Total" in df_compras.columns else 0

    # -----------------------------------------------------------------------
    # IVA neto
    # -----------------------------------------------------------------------
    iva_neto = ventas_iva - compras_iva - remanente_anterior

    # -----------------------------------------------------------------------
    # F29
    # -----------------------------------------------------------------------
    ppm_monto = int(ventas_neto * ppm_tasa)
    f29_total = iva_neto + ppm_monto + impuesto_unico if iva_neto > 0 else ppm_monto + impuesto_unico

    # -----------------------------------------------------------------------
    # Conteo de documentos
    # -----------------------------------------------------------------------
    num_tipo33 = int((df_compras["Tipo Doc"] == 33).sum())
    num_tipo34 = int((df_compras["Tipo Doc"] == 34).sum())
    num_tipo61 = int((df_compras["Tipo Doc"] == 61).sum())

    return ResumenMes(
        ventas_neto=ventas_neto,
        ventas_iva_debito=ventas_iva,
        ventas_total=ventas_total,
        num_docs_venta=len(df_ventas),
        num_docs_venta_con_iva=len(v_con_iva),
        compras_neto=compras_neto,
        compras_iva_credito=compras_iva,
        compras_total=compras_total,
        num_docs_compra=len(df_compras),
        num_docs_tipo33=num_tipo33,
        num_docs_tipo34=num_tipo34,
        num_docs_tipo61=num_tipo61,
        remanente_anterior=remanente_anterior,
        iva_neto=iva_neto,
        ppm_tasa=ppm_tasa,
        ppm_monto=ppm_monto,
        impuesto_unico=impuesto_unico,
        f29_total=f29_total,
    )


def resumen_por_tipo(df: pd.DataFrame, col_iva: str) -> pd.DataFrame:
    """Agrupa el DataFrame por Tipo Doc y retorna totales por tipo."""
    if df.empty:
        return pd.DataFrame()
    cols = ["Tipo Doc", "Monto Neto", col_iva, "Monto Total"] if "Monto Total" in df.columns else ["Tipo Doc", "Monto Neto", col_iva]
    cols_presentes = [c for c in cols if c in df.columns]
    return (
        df[cols_presentes]
        .groupby("Tipo Doc", as_index=False)
        .agg({c: "sum" for c in cols_presentes if c != "Tipo Doc"} | {"Tipo Doc": "first"})
        .assign(cantidad=df.groupby("Tipo Doc").size().values)
        .sort_values("Tipo Doc")
        .reset_index(drop=True)
    )


NOMBRE_TIPO_DOC = {
    33: "Factura electrónica",
    34: "Factura exenta",
    39: "Boleta electrónica",
    46: "Factura de compra",
    52: "Guía de despacho",
    56: "Nota de débito",
    61: "Nota de crédito",
}


def label_tipo_doc(codigo: int) -> str:
    return NOMBRE_TIPO_DOC.get(int(codigo), f"Tipo {codigo}")
