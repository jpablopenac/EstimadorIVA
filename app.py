"""
App IVA SII — Mi Empresa
Gestión tributaria mensual: cálculo de IVA y proyección F29.
"""
import json
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from logic.alertas import SUGERENCIAS_DEFAULT, calcular_alerta, fecha_vencimiento_f29
from logic.calculos import NOMBRE_TIPO_DOC, calcular_resumen, label_tipo_doc
from logic.parser import parsear_archivos

# ---------------------------------------------------------------------------
# Configuración de página
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="IVA SII — Mi Empresa",
    page_icon="📊",
    layout="wide",
)

DATA_DIR = Path(__file__).parent / "data"
HISTORIAL_PATH = DATA_DIR / "historial.json"

# ---------------------------------------------------------------------------
# Sidebar — configuración
# ---------------------------------------------------------------------------
with st.sidebar:
    st.title("⚙️ Configuración")
    rut_empresa = st.text_input("RUT empresa", value="11111111-1")
    nombre_empresa = st.text_input("Nombre empresa", value="Mi Empresa")

    st.divider()
    st.subheader("Parámetros IVA")
    umbral_alerta = st.number_input(
        "Umbral alerta IVA ($)",
        min_value=0,
        value=500_000,
        step=50_000,
        format="%d",
        help="Si el IVA neto supera este monto, se activa la alerta de reinversión.",
    )
    umbral_objetivo = st.number_input(
        "Objetivo reinversión ($)",
        min_value=0,
        value=0,
        step=50_000,
        format="%d",
        help="IVA neto al que se quiere llegar comprando activos.",
    )

    st.divider()
    st.subheader("Parámetros F29")
    ppm_tasa = st.number_input(
        "Tasa PPM (%)",
        min_value=0.0,
        max_value=10.0,
        value=1.0,
        step=0.1,
        format="%.1f",
    ) / 100.0


# ---------------------------------------------------------------------------
# Helpers de formato
# ---------------------------------------------------------------------------

def pesos(valor: int) -> str:
    return f"${valor:,.0f}".replace(",", ".")


def _color_metrica(valor: int) -> str:
    return "normal" if valor <= 0 else "inverse"


# ---------------------------------------------------------------------------
# Título principal
# ---------------------------------------------------------------------------
st.title(f"📊 {nombre_empresa} — Gestión IVA Mensual")

# ---------------------------------------------------------------------------
# SECCIÓN 1: Carga de archivos
# ---------------------------------------------------------------------------
st.header("1. Cargar archivos del mes")

col_c, col_v = st.columns(2)
with col_c:
    archivo_compras = st.file_uploader(
        "Archivo Compras (CSV del SII o XLSX del contador)",
        type=["csv", "xlsx", "xls"],
        key="compras",
    )
with col_v:
    archivo_ventas = st.file_uploader(
        "Archivo Ventas (CSV del SII)",
        type=["csv", "xlsx", "xls"],
        key="ventas",
        help="Si cargaste un XLSX con ambas hojas en Compras, deja este campo vacío.",
    )

remanente = st.number_input(
    "Remanente crédito fiscal mes anterior ($)",
    min_value=0,
    value=0,
    step=1_000,
    format="%d",
    help="Si el mes pasado quedó IVA a favor, ingrésalo aquí para descontarlo.",
)
impuesto_unico = st.number_input(
    "Impuesto Único 2ª categoría — retención trabajadores ($)",
    min_value=0,
    value=0,
    step=1_000,
    format="%d",
)

calcular = st.button("▶ Calcular", type="primary", use_container_width=True)

# ---------------------------------------------------------------------------
# Procesamiento
# ---------------------------------------------------------------------------
if calcular and archivo_compras:
    with st.spinner("Procesando archivos..."):
        try:
            result = parsear_archivos(
                archivo_compras=archivo_compras,
                archivo_ventas=archivo_ventas if archivo_ventas else archivo_compras,
                nombre_compras=archivo_compras.name,
                nombre_ventas=archivo_ventas.name if archivo_ventas else "",
            )
            resumen = calcular_resumen(
                df_compras=result.df_compras,
                df_ventas=result.df_ventas,
                remanente_anterior=int(remanente),
                ppm_tasa=ppm_tasa,
                impuesto_unico=int(impuesto_unico),
            )
            alerta = calcular_alerta(
                iva_neto=resumen.iva_neto,
                umbral_alerta=int(umbral_alerta),
                umbral_objetivo=int(umbral_objetivo),
            )

            st.session_state["result"] = result
            st.session_state["resumen"] = resumen
            st.session_state["alerta"] = alerta

        except Exception as e:
            st.error(f"Error al procesar los archivos: {e}")
            st.stop()

# ---------------------------------------------------------------------------
# Mostrar resultados (si ya se calculó)
# ---------------------------------------------------------------------------
if "resumen" not in st.session_state:
    st.info("Carga los archivos del mes y presiona **▶ Calcular** para comenzar.")
    st.stop()

result: object = st.session_state["result"]
resumen = st.session_state["resumen"]
alerta = st.session_state["alerta"]

# Avisos de corrección NC
for aviso in result.avisos:
    st.warning(f"⚠️ {aviso}")

# ---------------------------------------------------------------------------
# SECCIÓN 2: Resumen del mes
# ---------------------------------------------------------------------------
st.header("2. Resumen del mes")

if result.periodo:
    anio = result.periodo[:4]
    mes_num = int(result.periodo[4:6])
    nombres_mes = [
        "", "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
        "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre",
    ]
    st.subheader(f"Período: {nombres_mes[mes_num]} {anio}")

col1, col2, col3 = st.columns(3)
with col1:
    st.metric(
        label="IVA Débito (ventas)",
        value=pesos(resumen.ventas_iva_debito),
        help=f"{resumen.num_docs_venta_con_iva} documentos con IVA de {resumen.num_docs_venta} totales",
    )
    st.caption(f"Neto ventas: {pesos(resumen.ventas_neto)}")

with col2:
    st.metric(
        label="IVA Crédito (compras)",
        value=pesos(resumen.compras_iva_credito),
        help=f"Tipo 33: {resumen.num_docs_tipo33} | Tipo 34: {resumen.num_docs_tipo34} | NC: {resumen.num_docs_tipo61}",
    )
    if remanente > 0:
        st.caption(f"+ Remanente anterior: {pesos(int(remanente))}")
    st.caption(f"Neto compras: {pesos(resumen.compras_neto)}")

with col3:
    if resumen.iva_neto > 0:
        st.metric(label="IVA Neto", value=pesos(resumen.iva_neto))
        st.markdown("🔴 **A PAGAR al SII**")
    else:
        st.metric(label="IVA Neto", value=pesos(abs(resumen.iva_neto)))
        st.markdown("🟢 **Remanente a favor**")

# Fuente de datos
fuente_label = "CSV del SII" if result.fuente == "csv_sii" else "XLSX del contador"
st.caption(f"Fuente: {fuente_label}")

# ---------------------------------------------------------------------------
# Detalle de documentos
# ---------------------------------------------------------------------------
with st.expander("📋 Ver detalle de documentos"):
    tab_comp, tab_vent = st.tabs(["Compras", "Ventas"])

    with tab_comp:
        if not result.df_compras.empty:
            df_show = result.df_compras.copy()
            df_show["Tipo Doc (nombre)"] = df_show["Tipo Doc"].apply(label_tipo_doc)
            cols_show = [c for c in [
                "Nro", "Tipo Doc (nombre)", "Razon Social", "Folio",
                "Fecha Docto", "Monto Neto", "Monto IVA Recuperable", "Monto Total",
            ] if c in df_show.columns]
            st.dataframe(
                df_show[cols_show].rename(columns={
                    "Monto IVA Recuperable": "IVA Recuperable",
                    "Tipo Doc (nombre)": "Tipo Doc",
                }),
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.info("Sin datos de compras.")

    with tab_vent:
        if not result.df_ventas.empty:
            df_show = result.df_ventas.copy()
            df_show["Tipo Doc (nombre)"] = df_show["Tipo Doc"].apply(label_tipo_doc)
            cols_show = [c for c in [
                "Nro", "Tipo Doc (nombre)", "Razon Social", "Folio",
                "Fecha Docto", "Monto Neto", "Monto IVA", "Monto total",
            ] if c in df_show.columns]
            st.dataframe(
                df_show[cols_show].rename(columns={
                    "Tipo Doc (nombre)": "Tipo Doc",
                }),
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.info("Sin datos de ventas.")

# ---------------------------------------------------------------------------
# Resumen por tipo de documento
# ---------------------------------------------------------------------------
with st.expander("📊 Resumen por tipo de documento"):
    col_tc, col_tv = st.columns(2)

    with col_tc:
        st.subheader("Compras")
        if not result.df_compras.empty:
            grp = (
                result.df_compras
                .groupby("Tipo Doc")
                .agg(
                    Cantidad=("Nro", "count"),
                    Neto=("Monto Neto", "sum"),
                    IVA=("Monto IVA Recuperable", "sum"),
                )
                .reset_index()
            )
            grp["Tipo Doc"] = grp["Tipo Doc"].apply(label_tipo_doc)
            grp["Neto"] = grp["Neto"].apply(pesos)
            grp["IVA"] = grp["IVA"].apply(pesos)
            st.dataframe(grp, hide_index=True, use_container_width=True)

    with col_tv:
        st.subheader("Ventas")
        if not result.df_ventas.empty:
            col_iva_v = "Monto IVA" if "Monto IVA" in result.df_ventas.columns else "Monto total"
            grp = (
                result.df_ventas
                .groupby("Tipo Doc")
                .agg(
                    Cantidad=("Nro", "count"),
                    Neto=("Monto Neto", "sum"),
                    IVA=(col_iva_v, "sum"),
                )
                .reset_index()
            )
            grp["Tipo Doc"] = grp["Tipo Doc"].apply(label_tipo_doc)
            grp["Neto"] = grp["Neto"].apply(pesos)
            grp["IVA"] = grp["IVA"].apply(pesos)
            st.dataframe(grp, hide_index=True, use_container_width=True)

# ---------------------------------------------------------------------------
# SECCIÓN 3: Proyección F29
# ---------------------------------------------------------------------------
st.header("3. Proyección F29")

vencimiento = fecha_vencimiento_f29(result.periodo)

col_f1, col_f2 = st.columns([2, 1])

with col_f1:
    data_f29 = {
        "Concepto": [
            "IVA neto",
            f"PPM ({ppm_tasa*100:.1f}% sobre ventas netas)",
            "Impuesto Único 2ª categoría",
            "TOTAL F29 estimado",
        ],
        "Monto": [
            pesos(max(0, resumen.iva_neto)),
            pesos(resumen.ppm_monto),
            pesos(resumen.impuesto_unico),
            pesos(resumen.f29_total),
        ],
    }
    df_f29 = pd.DataFrame(data_f29)
    st.dataframe(df_f29, hide_index=True, use_container_width=True)
    st.caption(f"📅 Vence: {vencimiento}")

with col_f2:
    fig = go.Figure(go.Bar(
        x=["IVA neto", "PPM", "Imp. Único"],
        y=[max(0, resumen.iva_neto), resumen.ppm_monto, resumen.impuesto_unico],
        marker_color=["#E74C3C", "#3498DB", "#F39C12"],
        text=[
            pesos(max(0, resumen.iva_neto)),
            pesos(resumen.ppm_monto),
            pesos(resumen.impuesto_unico),
        ],
        textposition="outside",
    ))
    fig.update_layout(
        title="Composición F29",
        yaxis_title="Pesos CLP",
        height=300,
        margin=dict(t=40, b=20, l=10, r=10),
    )
    st.plotly_chart(fig, use_container_width=True)

st.metric("F29 total estimado", pesos(resumen.f29_total))

# ---------------------------------------------------------------------------
# SECCIÓN 4: Alerta de reinversión
# ---------------------------------------------------------------------------
st.header("4. Alerta de reinversión")

if alerta.activa:
    st.error(
        f"⚠️ **ALERTA:** El IVA a pagar (${resumen.iva_neto:,.0f}) supera el umbral de "
        f"${umbral_alerta:,.0f}."
    )

    col_a1, col_a2 = st.columns(2)
    with col_a1:
        st.markdown(f"""
**Para reducir el IVA a pagar a {pesos(umbral_objetivo)}, necesitas:**

| | Monto |
|---|---|
| Crédito fiscal adicional necesario | **{pesos(alerta.credito_necesario)}** |
| Compra neta (sin IVA) | **{pesos(alerta.compra_neta_necesaria)}** |
| Total factura (con IVA 19%) | **{pesos(alerta.compra_total_necesaria)}** |
""")

    with col_a2:
        if alerta.aviso_ventana:
            st.warning(
                f"⏰ Quedan solo **{alerta.dias_para_fin_mes} días** para el cierre del mes. "
                "Las facturas deben estar recibidas y aceptadas (o sin rechazo en 8 días) "
                "para que el IVA sea recuperable en este período."
            )
        else:
            st.info(
                f"📅 Quedan **{alerta.dias_para_fin_mes} días** para el cierre del mes."
            )

    st.subheader("💡 Sugerencias de activos para reinvertir")
    for i, sug in enumerate(SUGERENCIAS_DEFAULT, 1):
        st.markdown(f"{i}. {sug}")

else:
    if resumen.iva_neto <= 0:
        st.success(f"✅ Tienes remanente a favor de {pesos(abs(resumen.iva_neto))}. No hay IVA a pagar este mes.")
    else:
        st.success(
            f"✅ El IVA a pagar ({pesos(resumen.iva_neto)}) está bajo el umbral de alerta "
            f"({pesos(int(umbral_alerta))}). No se requiere acción."
        )

# ---------------------------------------------------------------------------
# Guardar en historial
# ---------------------------------------------------------------------------
st.divider()
if st.button("💾 Guardar resumen en historial"):
    DATA_DIR.mkdir(exist_ok=True)
    historial: list = []
    if HISTORIAL_PATH.exists():
        with open(HISTORIAL_PATH, encoding="utf-8") as f:
            historial = json.load(f)

    entrada = {
        "periodo": result.periodo or "desconocido",
        "rut": rut_empresa,
        "empresa": nombre_empresa,
        "ventas_neto": resumen.ventas_neto,
        "ventas_iva_debito": resumen.ventas_iva_debito,
        "compras_neto": resumen.compras_neto,
        "compras_iva_credito": resumen.compras_iva_credito,
        "remanente_anterior": resumen.remanente_anterior,
        "iva_neto": resumen.iva_neto,
        "ppm_monto": resumen.ppm_monto,
        "impuesto_unico": resumen.impuesto_unico,
        "f29_total": resumen.f29_total,
        "nc_corregidas": result.nc_corregidas,
        "diferencia_nc": result.diferencia_nc,
    }

    # Reemplazar si ya existe el período
    historial = [h for h in historial if h.get("periodo") != entrada["periodo"]]
    historial.append(entrada)
    historial.sort(key=lambda x: x.get("periodo", ""))

    with open(HISTORIAL_PATH, "w", encoding="utf-8") as f:
        json.dump(historial, f, ensure_ascii=False, indent=2)

    st.success(f"✅ Resumen del período {entrada['periodo']} guardado correctamente.")

# ---------------------------------------------------------------------------
# SECCIÓN 5: Historial mensual
# ---------------------------------------------------------------------------
st.header("5. Historial mensual")

if HISTORIAL_PATH.exists():
    with open(HISTORIAL_PATH, encoding="utf-8") as f:
        historial = json.load(f)

    if historial:
        df_hist = pd.DataFrame(historial)

        # Tabla resumen
        df_tabla = df_hist[[
            "periodo", "ventas_iva_debito", "compras_iva_credito", "iva_neto", "f29_total"
        ]].copy()
        df_tabla.columns = ["Período", "IVA Débito", "IVA Crédito", "IVA Neto", "F29 Total"]
        for col in ["IVA Débito", "IVA Crédito", "IVA Neto", "F29 Total"]:
            df_tabla[col] = df_tabla[col].apply(pesos)
        st.dataframe(df_tabla, hide_index=True, use_container_width=True)

        # Gráfico de líneas
        fig2 = go.Figure()
        fig2.add_trace(go.Scatter(
            x=df_hist["periodo"], y=df_hist["ventas_iva_debito"],
            name="IVA Débito", line=dict(color="#E74C3C"),
        ))
        fig2.add_trace(go.Scatter(
            x=df_hist["periodo"], y=df_hist["compras_iva_credito"],
            name="IVA Crédito", line=dict(color="#2ECC71"),
        ))
        fig2.add_trace(go.Scatter(
            x=df_hist["periodo"], y=df_hist["iva_neto"],
            name="IVA Neto", line=dict(color="#3498DB", dash="dash"),
        ))
        fig2.update_layout(
            title="Evolución mensual del IVA",
            xaxis_title="Período",
            yaxis_title="Pesos CLP",
            height=350,
            legend=dict(orientation="h", yanchor="bottom", y=1.02),
        )
        st.plotly_chart(fig2, use_container_width=True)
    else:
        st.info("Aún no hay datos en el historial. Calcula un mes y guárdalo.")
else:
    st.info("Aún no hay historial guardado.")
