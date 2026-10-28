# IVA SII — Gestión tributaria mensual

Aplicación web en Python (Streamlit) que automatiza el cierre mensual de IVA de una empresa chilena a partir de los archivos del **Registro de Compras y Ventas (RCV)** del SII: calcula el IVA a pagar, proyecta el Formulario 29 y avisa cuándo conviene reinvertir para reducir el impuesto.

## Qué problema resuelve?

Cada mes una pyme chilena debe cruzar sus compras y ventas, calcular débito y crédito fiscal, descontar remanentes y estimar cuánto pagará en el F29. Normalmente se hace a mano en Excel y los errores (como notas de crédito con signo equivocado) pasan desapercibidos. Esta herramienta lo hace en segundos y deja un historial.

## Funcionalidades

- **Carga de archivos**: CSV del RCV del SII (compras y ventas) o un XLSX con hojas `Compras` y `Ventas`.
- **Limpieza automática**: descarta filas de totales, normaliza fechas (texto o serial Excel) y números, e infiere el período (AAAAMM) desde el nombre del archivo.
- **Corrección de notas de crédito (tipo 61)**: el SII a veces las entrega con IVA positivo; se invierten a negativo y se informa al usuario.
- **Cálculo mensual**: IVA débito, IVA crédito, remanente del mes anterior e IVA neto (a pagar o a favor).
- **Proyección F29**: IVA neto + PPM (tasa configurable sobre ventas netas) + Impuesto Único de 2ª categoría, con fecha de vencimiento (día 12 del mes siguiente).
- **Alerta de reinversión**: si el IVA neto supera un umbral, calcula el crédito fiscal, la compra neta y el total de factura necesarios para llegar a un monto objetivo, y avisa si quedan pocos días para el cierre.
- **Historial mensual**: guarda cada cierre en JSON y grafica la evolución de débito, crédito y IVA neto (Plotly).

## Stack

Python 3.10+ · Streamlit · pandas · openpyxl · Plotly · pytest

## Estructura

```
.
├── app.py                 # Interfaz Streamlit (UI y orquestación)
├── logic/
│   ├── parser.py          # Lectura/limpieza de CSV y XLSX, corrección de NC
│   ├── calculos.py        # IVA débito/crédito/neto y proyección F29
│   └── alertas.py         # Alerta de reinversión y vencimiento F29
├── tests/                 # Tests unitarios (pytest)
├── data/
│   └── historial.ejemplo.json   # Formato del historial (el real no se versiona)
└── requirements.txt
```

La lógica de negocio está separada de la interfaz (`logic/` no depende de Streamlit), lo que permite testearla de forma aislada.

## Instalación y uso

```bash
git clone https://github.com/jpablopenac/EstimadorIVA
cd IVA
python -m venv .venv
.venv\Scripts\activate        # Windows  (Linux/macOS: source .venv/bin/activate)
pip install -r requirements.txt
streamlit run app.py
```

1. Configura RUT, nombre, umbral de alerta y tasa PPM en la barra lateral.
2. Sube los archivos de compras y ventas del mes.
3. Ingresa remanente anterior e Impuesto Único si corresponde y presiona **Calcular**.
4. Guarda el resumen en el historial.

### Tests

```bash
python -m pytest
```

## Privacidad de los datos

Los archivos cargados se procesan en memoria. El historial se guarda localmente en `data/historial.json`, que está en `.gitignore` para no publicar información tributaria real. Copia `data/historial.ejemplo.json` para ver el formato.

## Posibles mejoras

**Funcionales**

- Soportar más tipos de documento (notas de débito 56, facturas de compra 46, IVA no recuperable, activo fijo e IVA de uso común) en el cálculo de crédito fiscal.
- Calcular PPM según la regla real del SII (tasa variable por régimen y ventas de períodos anteriores) y el reajuste por IPC del remanente.
- Ajustar el vencimiento del F29 cuando cae en fin de semana o feriado, y considerar el plazo extendido para pago electrónico.
- Incluir el periodo en el nombre del archivo mediante selector manual cuando no se pueda inferir.
- Exportar el resumen y la proyección F29 a PDF/Excel.
- Comparativo mes a mes y contra el mismo mes del año anterior; proyección de IVA con series de tiempo.
- Sugerencias de reinversión personalizables según el giro (hoy son una lista fija).

**Técnicas**

- Reemplazar el historial en JSON por SQLite (o una base de datos) con soporte multiempresa y edición/borrado de períodos.
- Separar `app.py` en páginas/componentes (Streamlit multipage) y mover el formateo de pesos y meses a un módulo común; eliminar código duplicado en las tablas de compras/ventas.
- Detección de encoding y separador del CSV en lugar de asumir `latin1` y `;`; validación del esquema con mensajes de error claros (por ejemplo con `pandera` o `pydantic`).
- Usar `Decimal` o enteros consistentes en lugar de `int(...)` sobre floats para los montos.
- Ampliar los tests: casos del parser con archivos de ejemplo sintéticos, `alertas.py` y pruebas de la UI (`streamlit.testing`).
- CI con GitHub Actions (pytest + ruff/mypy), type hints completos y `pyproject.toml`.
- Dockerfile y despliegue (Streamlit Community Cloud) con autenticación si se publica.
- Integración directa con la API del SII para descargar el RCV sin subir archivos manualmente.

## Aviso

Es una herramienta de apoyo para estimar el F29; no reemplaza la asesoría de un contador ni la declaración oficial en sii.cl.
