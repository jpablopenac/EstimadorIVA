"""
Tests de cálculo de IVA con los datos reales de abril 2026.
"""
import pandas as pd
import pytest

from logic.calculos import calcular_resumen


# ---------------------------------------------------------------------------
# Datos reales abril 2026 (del SPEC)
# ---------------------------------------------------------------------------

VENTAS_NETO = 22_870_728
IVA_DEBITO = 4_345_438
VENTAS_TOTAL = 27_216_166

COMPRAS_NETO = 6_857_176
IVA_CREDITO = 1_302_864
COMPRAS_TOTAL = 8_357_077

IVA_NETO_ESPERADO = 3_042_574
PPM_MONTO_ESPERADO = 228_707
IMPUESTO_UNICO = 483_099
F29_TOTAL_ESPERADO = 3_754_380


def _df_ventas_minimo() -> pd.DataFrame:
    """DataFrame de ventas con los totales exactos del caso real (una fila por tipo)."""
    return pd.DataFrame([
        {"Nro": i + 1, "Tipo Doc": 33, "Monto Neto": 0,
         "Monto IVA": 0, "Monto total": 0}
        for i in range(7)
    ] + [
        # Última fila absorbe todos los totales para evitar redondeo
        {"Nro": 8, "Tipo Doc": 33, "Monto Neto": VENTAS_NETO,
         "Monto IVA": IVA_DEBITO, "Monto total": VENTAS_TOTAL}
    ])


def _df_compras_minimo() -> pd.DataFrame:
    """DataFrame de compras con los totales exactos del caso real."""
    rows = []
    # 41 facturas tipo 33 con valores 0
    for i in range(41):
        rows.append({
            "Nro": i + 1, "Tipo Doc": 33,
            "Monto Neto": 0, "Monto IVA Recuperable": 0, "Monto Total": 0,
        })
    # Factura 42: las facturas tipo 33 tienen IVA_CREDITO + 3838 (la NC resta -3838 después)
    # para que la suma neta quede en IVA_CREDITO = 1_302_864
    IVA_TIPO33 = IVA_CREDITO + 3_838   # 1_306_702
    rows.append({
        "Nro": 42, "Tipo Doc": 33,
        "Monto Neto": COMPRAS_NETO,
        "Monto IVA Recuperable": IVA_TIPO33,
        "Monto Total": COMPRAS_TOTAL,
    })
    # 10 facturas tipo 34 (sin IVA)
    for i in range(10):
        rows.append({
            "Nro": 43 + i, "Tipo Doc": 34,
            "Monto Neto": 100_000, "Monto IVA Recuperable": 0, "Monto Total": 100_000,
        })
    # 1 nota de crédito tipo 61 (ya corregida — valor negativo)
    rows.append({
        "Nro": 53, "Tipo Doc": 61,
        "Monto Neto": -20_168, "Monto IVA Recuperable": -3_838, "Monto Total": -24_006,
    })
    return pd.DataFrame(rows)


class TestCalculoIVA:
    def test_iva_neto_correcto(self):
        r = calcular_resumen(
            df_compras=_df_compras_minimo(),
            df_ventas=_df_ventas_minimo(),
        )
        assert r.iva_neto == IVA_NETO_ESPERADO, (
            f"IVA neto {r.iva_neto} difiere del esperado {IVA_NETO_ESPERADO}"
        )

    def test_f29_total_correcto(self):
        """Verificación del ejemplo real del SPEC."""
        assert IVA_NETO_ESPERADO + PPM_MONTO_ESPERADO + IMPUESTO_UNICO == F29_TOTAL_ESPERADO

    def test_f29_calculado(self):
        r = calcular_resumen(
            df_compras=_df_compras_minimo(),
            df_ventas=_df_ventas_minimo(),
            ppm_tasa=0.01,
            impuesto_unico=IMPUESTO_UNICO,
        )
        # F29 = IVA neto + PPM + Imp. Único (con tolerancia de redondeo)
        assert abs(r.f29_total - F29_TOTAL_ESPERADO) < 5_000

    def test_ppm_sobre_ventas_netas(self):
        r = calcular_resumen(
            df_compras=_df_compras_minimo(),
            df_ventas=_df_ventas_minimo(),
            ppm_tasa=0.01,
        )
        assert abs(r.ppm_monto - PPM_MONTO_ESPERADO) < 500

    def test_remanente_reduce_iva(self):
        remanente = 500_000
        r = calcular_resumen(
            df_compras=_df_compras_minimo(),
            df_ventas=_df_ventas_minimo(),
            remanente_anterior=remanente,
        )
        r_sin = calcular_resumen(
            df_compras=_df_compras_minimo(),
            df_ventas=_df_ventas_minimo(),
        )
        assert r.iva_neto == r_sin.iva_neto - remanente

    def test_iva_neto_negativo_no_suma_al_f29(self):
        """Si hay remanente a favor, el F29 no incluye IVA negativo."""
        remanente = 10_000_000
        r = calcular_resumen(
            df_compras=_df_compras_minimo(),
            df_ventas=_df_ventas_minimo(),
            remanente_anterior=remanente,
            ppm_tasa=0.01,
            impuesto_unico=IMPUESTO_UNICO,
        )
        assert r.iva_neto < 0
        assert r.f29_total == r.ppm_monto + IMPUESTO_UNICO

    def test_conteo_documentos(self):
        r = calcular_resumen(
            df_compras=_df_compras_minimo(),
            df_ventas=_df_ventas_minimo(),
        )
        assert r.num_docs_tipo33 == 42
        assert r.num_docs_tipo34 == 10
        assert r.num_docs_tipo61 == 1
        assert r.num_docs_compra == 53
        assert r.num_docs_venta == 8
