"""
Lectura y limpieza de archivos RCV del SII (CSV) y del contador (XLSX).
"""
import io
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

import pandas as pd


# ---------------------------------------------------------------------------
# Definición de columnas
# ---------------------------------------------------------------------------

COLS_COMPRA = [
    "Nro", "Tipo Doc", "Tipo Compra", "RUT Proveedor", "Razon Social", "Folio",
    "Fecha Docto", "Fecha Recepcion", "Fecha Acuse", "Monto Exento", "Monto Neto",
    "Monto IVA Recuperable", "Monto Iva No Recuperable", "Codigo IVA No Rec.",
    "Monto Total", "Monto Neto Activo Fijo", "IVA Activo Fijo", "IVA uso Comun",
    "Impto. Sin Derecho a Credito", "IVA No Retenido", "Tabacos Puros",
    "Tabacos Cigarrillos", "Tabacos Elaborados", "NCE o NDE sobre Fact. de Compra",
    "Codigo Otro Impuesto", "Valor Otro Impuesto", "Tasa Otro Impuesto", "Extra",
]

COLS_VENTA = [
    "Nro", "Tipo Doc", "Tipo Venta", "Rut cliente", "Razon Social", "Folio",
    "Fecha Docto", "Fecha Recepcion", "Fecha Acuse Recibo", "Fecha Reclamo",
    "Monto Exento", "Monto Neto", "Monto IVA", "Monto total",
    "IVA Retenido Total", "IVA Retenido Parcial", "IVA no retenido",
    "IVA propio", "IVA Terceros", "RUT Emisor Liquid. Factura",
    "Neto Comision Liquid. Factura", "Exento Comision Liquid. Factura",
    "IVA Comision Liquid. Factura", "IVA fuera de plazo",
    "Tipo Docto. Referencia", "Folio Docto. Referencia",
    "Num. Ident. Receptor Extranjero", "Nacionalidad Receptor Extranjero",
    "Credito empresa constructora", "Impto. Zona Franca (Ley 18211)",
    "Garantia Dep. Envases", "Indicador Venta sin Costo",
    "Indicador Servicio Periodico", "Monto No facturable",
    "Total Monto Periodo", "Venta Pasajes Transporte Nacional",
    "Venta Pasajes Transporte Internacional", "Numero Interno",
    "Codigo Sucursal", "NCE o NDE sobre Fact. de Compra",
    "Codigo Otro Imp.", "Valor Otro Imp.", "Tasa Otro Imp.", "Extra",
]

NUM_COLS_COMPRA = [
    "Monto Exento", "Monto Neto", "Monto IVA Recuperable",
    "Monto Iva No Recuperable", "Monto Total", "Monto Neto Activo Fijo",
    "IVA Activo Fijo", "IVA uso Comun", "Valor Otro Impuesto",
]

NUM_COLS_VENTA = [
    "Monto Exento", "Monto Neto", "Monto IVA", "Monto total",
]


# ---------------------------------------------------------------------------
# Resultado del parsing
# ---------------------------------------------------------------------------

@dataclass
class ParseResult:
    df_compras: pd.DataFrame
    df_ventas: pd.DataFrame
    fuente: str                          # "csv_sii" | "xlsx_contador"
    periodo: Optional[str] = None        # "AAAAMM" inferido del nombre de archivo
    avisos: list[str] = field(default_factory=list)
    nc_corregidas: int = 0
    diferencia_nc: int = 0


# ---------------------------------------------------------------------------
# Helpers internos
# ---------------------------------------------------------------------------

def _to_numeric_cols(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    for c in cols:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0).astype(int)
    return df


def _filtrar_filas_reales(df: pd.DataFrame) -> pd.DataFrame:
    """Descarta filas de totales/resumen al pie del archivo (Nro no numérico)."""
    mask = pd.to_numeric(df["Nro"], errors="coerce").notna()
    return df[mask].copy()


def _normalizar_fechas(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    """Convierte DD/MM/AAAA (str) o serial Excel (int) a datetime."""
    for c in cols:
        if c not in df.columns:
            continue
        serie = df[c]
        # Intentar parsear como DD/MM/YYYY primero
        parsed = pd.to_datetime(serie, dayfirst=True, errors="coerce")
        # Para los que fallaron (pueden ser seriales Excel)
        mask_nan = parsed.isna()
        if mask_nan.any():
            numeric = pd.to_numeric(serie[mask_nan], errors="coerce")
            excel_dates = pd.TimedeltaIndex(numeric[numeric.notna()], unit="D") + datetime(1899, 12, 30)
            parsed[mask_nan & numeric.notna()] = excel_dates
        df[c] = parsed
    return df


def _inferir_periodo(nombre_archivo: str) -> Optional[str]:
    """Extrae AAAAMM del nombre de archivo RCV del SII."""
    match = re.search(r"(\d{6})(?:\.csv|\.xlsx)?$", nombre_archivo, re.IGNORECASE)
    if match:
        return match.group(1)
    return None


def _corregir_notas_credito(df_compras: pd.DataFrame) -> tuple[pd.DataFrame, int, int]:
    """
    Las NC (tipo 61) en compras deben restar crédito fiscal.
    El CSV del SII a veces las registra con IVA positivo — se fuerza a negativo.
    Retorna (df_corregido, cantidad_corregidas, diferencia_pesos).
    """
    mask_nc = (
        (df_compras["Tipo Doc"] == 61)
        & (df_compras["Monto IVA Recuperable"] > 0)
    )
    n = int(mask_nc.sum())
    if n == 0:
        return df_compras, 0, 0

    diferencia = int(df_compras.loc[mask_nc, "Monto IVA Recuperable"].sum()) * 2
    df_compras = df_compras.copy()
    for col in ("Monto IVA Recuperable", "Monto Neto", "Monto Total"):
        if col in df_compras.columns:
            df_compras.loc[mask_nc, col] *= -1

    return df_compras, n, diferencia


# ---------------------------------------------------------------------------
# Lectura CSV del SII
# ---------------------------------------------------------------------------

def _leer_csv_compras(fileobj) -> pd.DataFrame:
    content = fileobj.read()
    df = pd.read_csv(
        io.BytesIO(content),
        sep=";",
        encoding="latin1",
        header=None,
        skiprows=1,
        names=COLS_COMPRA,
        on_bad_lines="skip",
    )
    df = _filtrar_filas_reales(df)
    df["Tipo Doc"] = pd.to_numeric(df["Tipo Doc"], errors="coerce").fillna(0).astype(int)
    df = _to_numeric_cols(df, NUM_COLS_COMPRA)
    df = _normalizar_fechas(df, ["Fecha Docto", "Fecha Recepcion"])
    return df


def _leer_csv_ventas(fileobj) -> pd.DataFrame:
    content = fileobj.read()
    df = pd.read_csv(
        io.BytesIO(content),
        sep=";",
        encoding="latin1",
        header=None,
        skiprows=1,
        names=COLS_VENTA,
        on_bad_lines="skip",
    )
    df = _filtrar_filas_reales(df)
    df["Tipo Doc"] = pd.to_numeric(df["Tipo Doc"], errors="coerce").fillna(0).astype(int)
    df = _to_numeric_cols(df, NUM_COLS_VENTA)
    df = _normalizar_fechas(df, ["Fecha Docto", "Fecha Recepcion"])
    return df


# ---------------------------------------------------------------------------
# Lectura XLSX del contador
# ---------------------------------------------------------------------------

def _leer_xlsx(fileobj) -> tuple[pd.DataFrame, pd.DataFrame]:
    content = fileobj.read()
    xl = pd.ExcelFile(io.BytesIO(content), engine="openpyxl")

    hojas = [h.lower() for h in xl.sheet_names]

    def _hoja(nombre: str) -> str:
        for real, low in zip(xl.sheet_names, hojas):
            if low == nombre.lower():
                return real
        raise ValueError(f"Hoja '{nombre}' no encontrada en el XLSX.")

    df_compras = xl.parse(_hoja("Compras"))
    df_ventas = xl.parse(_hoja("Ventas"))

    # Normalizar columnas al mismo esquema que el CSV
    df_compras.columns = [str(c).strip() for c in df_compras.columns]
    df_ventas.columns = [str(c).strip() for c in df_ventas.columns]

    # Filtrar filas de resumen/F29 al pie
    df_compras = _filtrar_filas_reales(df_compras)
    df_ventas = _filtrar_filas_reales(df_ventas)

    # Unificar nombre de columna IVA en ventas (el XLSX puede llamarla distinto)
    for alias in ("Monto IVA", "IVA", "Monto Iva"):
        if alias in df_ventas.columns and "Monto IVA" not in df_ventas.columns:
            df_ventas = df_ventas.rename(columns={alias: "Monto IVA"})
            break

    df_compras["Tipo Doc"] = pd.to_numeric(df_compras.get("Tipo Doc", 0), errors="coerce").fillna(0).astype(int)
    df_ventas["Tipo Doc"] = pd.to_numeric(df_ventas.get("Tipo Doc", 0), errors="coerce").fillna(0).astype(int)

    df_compras = _to_numeric_cols(df_compras, NUM_COLS_COMPRA)
    df_ventas = _to_numeric_cols(df_ventas, NUM_COLS_VENTA)

    df_compras = _normalizar_fechas(df_compras, ["Fecha Docto", "Fecha Recepcion"])
    df_ventas = _normalizar_fechas(df_ventas, ["Fecha Docto", "Fecha Recepcion"])

    return df_compras, df_ventas


# ---------------------------------------------------------------------------
# Función pública principal
# ---------------------------------------------------------------------------

def parsear_archivos(
    archivo_compras,
    archivo_ventas,
    nombre_compras: str = "",
    nombre_ventas: str = "",
) -> ParseResult:
    """
    Parsea los archivos de compras y ventas (CSV o XLSX) y retorna un ParseResult.
    `archivo_compras` / `archivo_ventas` son file-like objects (UploadedFile de Streamlit).
    """
    avisos: list[str] = []

    # Detectar formato por extensión
    ext_c = nombre_compras.lower().split(".")[-1] if nombre_compras else ""
    ext_v = nombre_ventas.lower().split(".")[-1] if nombre_ventas else ""

    # Si ambos son XLSX, asumir un único archivo con dos hojas
    if ext_c in ("xlsx", "xls") or ext_v in ("xlsx", "xls"):
        fuente = "xlsx_contador"
        # Preferir el archivo de compras como contenedor si tiene ambas hojas
        try:
            df_compras, df_ventas = _leer_xlsx(archivo_compras)
        except Exception:
            df_compras = _leer_csv_compras(archivo_compras)
            df_ventas = _leer_csv_ventas(archivo_ventas)
            fuente = "csv_sii"
    else:
        fuente = "csv_sii"
        df_compras = _leer_csv_compras(archivo_compras)
        df_ventas = _leer_csv_ventas(archivo_ventas)

    # Corrección de NC tipo 61
    df_compras, nc_n, nc_diff = _corregir_notas_credito(df_compras)
    if nc_n > 0:
        avisos.append(
            f"Se detectaron {nc_n} nota(s) de crédito (tipo 61) con IVA positivo en el archivo "
            f"de compras. Se corrigieron automáticamente. "
            f"Diferencia ajustada: ${nc_diff:,.0f}"
        )

    periodo = _inferir_periodo(nombre_compras) or _inferir_periodo(nombre_ventas)

    return ParseResult(
        df_compras=df_compras,
        df_ventas=df_ventas,
        fuente=fuente,
        periodo=periodo,
        avisos=avisos,
        nc_corregidas=nc_n,
        diferencia_nc=nc_diff,
    )
