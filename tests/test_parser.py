"""
Tests del parser CSV/XLSX — corrección de NC tipo 61 y lectura de columnas.
"""
import io

import pandas as pd
import pytest

from logic.parser import (
    COLS_COMPRA,
    _corregir_notas_credito,
    _filtrar_filas_reales,
    _inferir_periodo,
)


class TestFiltrarFilasReales:
    def test_descarta_filas_sin_nro_numerico(self):
        df = pd.DataFrame({
            "Nro": ["1", "2", "Total", ""],
            "Tipo Doc": [33, 34, None, None],
        })
        resultado = _filtrar_filas_reales(df)
        assert len(resultado) == 2
        assert list(resultado["Nro"]) == ["1", "2"]

    def test_conserva_todos_si_todos_son_numericos(self):
        df = pd.DataFrame({"Nro": [1, 2, 3], "Tipo Doc": [33, 33, 34]})
        assert len(_filtrar_filas_reales(df)) == 3


class TestCorregirNC:
    def _df_con_nc(self, iva_positivo: bool) -> pd.DataFrame:
        return pd.DataFrame([
            {"Tipo Doc": 33, "Monto IVA Recuperable": 3_838, "Monto Neto": 20_168, "Monto Total": 24_006},
            {
                "Tipo Doc": 61,
                "Monto IVA Recuperable": 3_838 if iva_positivo else -3_838,
                "Monto Neto": 20_168 if iva_positivo else -20_168,
                "Monto Total": 24_006 if iva_positivo else -24_006,
            },
        ])

    def test_corrige_nc_con_iva_positivo(self):
        df, n, diff = _corregir_notas_credito(self._df_con_nc(iva_positivo=True))
        assert n == 1
        assert diff == 3_838 * 2  # diferencia = 2 × IVA (de positivo a negativo)
        nc_row = df[df["Tipo Doc"] == 61].iloc[0]
        assert nc_row["Monto IVA Recuperable"] == -3_838
        assert nc_row["Monto Neto"] == -20_168

    def test_no_toca_nc_ya_negativa(self):
        df_original = self._df_con_nc(iva_positivo=False)
        df, n, diff = _corregir_notas_credito(df_original)
        assert n == 0
        assert diff == 0
        nc_row = df[df["Tipo Doc"] == 61].iloc[0]
        assert nc_row["Monto IVA Recuperable"] == -3_838

    def test_diferencia_correcta_caso_real(self):
        """
        Caso real abril 2026:
        CSV SII: IVA crédito = 1.310.540 (inflado)
        Correcto:           = 1.302.864
        Diferencia:            7.676 = 3.838 × 2
        """
        df = pd.DataFrame([
            {"Tipo Doc": 61, "Monto IVA Recuperable": 3_838, "Monto Neto": 0, "Monto Total": 0},
        ])
        _, n, diff = _corregir_notas_credito(df)
        assert diff == 7_676


class TestInferirPeriodo:
    def test_csv_sii_compras(self):
        assert _inferir_periodo("RCV_COMPRA_REGISTRO_11111111-1_202604.csv") == "202604"

    def test_csv_sii_ventas(self):
        assert _inferir_periodo("RCV_VENTA_11111111-1_202604.csv") == "202604"

    def test_sin_periodo(self):
        assert _inferir_periodo("mis_compras.xlsx") is None

    def test_periodo_otro_mes(self):
        assert _inferir_periodo("RCV_COMPRA_REGISTRO_11111111-1_202512.csv") == "202512"
