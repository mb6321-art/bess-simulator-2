import streamlit as st
import pandas as pd
import numpy as np
import numpy_financial as npf
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import textwrap
import os

RESULT_KEYS = [
    "resultado",
    "mensual",
    "fi_date",
    "ff_date",
    "ingreso_anual",
    "inversion",
    "van",
    "tir",
    "tir_equity",
    "ciclos_anuales",
    "cyc_min",
    "cyc_max",
    "degradacion",
    "flujo_caja",
    "sens_dur",
    "horas_optimas",
]

def reset_sidebar():
    """Clear session state and reload the app."""
    for k in list(st.session_state.keys()):
        del st.session_state[k]
    st.experimental_rerun()

TECHS = {
    "Li-ion LFP": {"costo": (220, 240), "ciclos": (6000, 8000)},
    "Li-ion NMC": {"costo": (250, 280), "ciclos": (3000, 4000)},
    "Sodio-ion (Na-ion)": {"costo": (280, 320), "ciclos": (4000, 5000)},
}

st.set_page_config(page_title="Simulador de BESS", layout="wide")

# Initialize session state variables for results
for k in RESULT_KEYS:
    st.session_state.setdefault(k, None)

# --- Cargar datos ---
@st.cache_data
def cargar_datos(zona, archivo=None):
    if archivo is not None:
        if archivo.name.endswith(".csv"):
            df = pd.read_csv(archivo)
        else:
            df = pd.read_excel(archivo)
    else:
        path = "Precios_Mercado_Italiano_2024.xlsx"
        if not os.path.exists(path):
            alt_path = "data/precios_italia_2024.xlsx"
            if os.path.exists(alt_path):
                path = alt_path
            else:
                alt_path2 = "data/precios_italia.xlsx"
                if os.path.exists(alt_path2):
                    path = alt_path2
                else:
                    st.error(f"Archivo predeterminado no encontrado: {path}")
                    st.stop()
        df = pd.read_excel(path, sheet_name=zona)
    df["Fecha"] = pd.to_datetime(df["Fecha"])
    return df

# --- Simulación ---
def simular(precios, potencia_mw, duracion_h, ef_carga, ef_descarga,
            estrategia, umbral_carga=0.25, umbral_descarga=0.75,
            margen=0, horario=None):
    energia_mwh = potencia_mw * duracion_h
    capacidad_actual = 0
    resultados = []

    p_inf = precios["Precio"].quantile(umbral_carga)
    p_sup = precios["Precio"].quantile(umbral_descarga)
    media = precios["Precio"].mean()

    for _, row in precios.iterrows():
        precio = row["Precio"]
        estado = "Reposo"
        carga = descarga = ingreso = 0

        if estrategia == "Percentiles":
            if precio < p_inf and capacidad_actual < energia_mwh:
                carga = potencia_mw * ef_carga
                capacidad_actual += carga
                estado = "Carga"
                ingreso = -precio * carga
            elif precio > p_sup and capacidad_actual > 0:
                descarga = min(potencia_mw * ef_descarga, capacidad_actual)
                capacidad_actual -= descarga
                estado = "Descarga"
                ingreso = precio * descarga

        elif estrategia == "Margen fijo":
            if precio < media - margen and capacidad_actual < energia_mwh:
                carga = potencia_mw * ef_carga
                capacidad_actual += carga
                estado = "Carga"
                ingreso = -precio * carga
            elif precio > media + margen and capacidad_actual > 0:
                descarga = min(potencia_mw * ef_descarga, capacidad_actual)
                capacidad_actual -= descarga
                estado = "Descarga"
                ingreso = precio * descarga

        elif estrategia == "Programada" and horario is not None:
            accion = horario.get(row["Fecha"].hour)
            if accion == "C" and capacidad_actual < energia_mwh:
                carga = potencia_mw * ef_carga
                capacidad_actual += carga
                estado = "Carga"
                ingreso = -precio * carga
            elif accion == "D" and capacidad_actual > 0:
                descarga = min(potencia_mw * ef_descarga, capacidad_actual)
                capacidad_actual -= descarga
                estado = "Descarga"
                ingreso = precio * descarga

        resultados.append({
            "Fecha": row["Fecha"],
            "Precio": precio,
            "Carga (MWh)": carga,
            "Descarga (MWh)": descarga,
            "SOC (MWh)": capacidad_actual,
            "Estado": estado,
            "Beneficio (€)": ingreso
        })

    return pd.DataFrame(resultados)

def resumen_mensual(df):
    return (
        df.resample("M", on="Fecha")
          .agg({"Carga (MWh)": "sum",
                "Descarga (MWh)": "sum",
                "Beneficio (€)": "sum"})
          .rename_axis("Mes")
    )

def analizar_duracion(precios, potencia_mw, max_h, ef_carga, ef_descarga,
                       estrategia, umbral_carga, umbral_descarga, margen,
                       horario, degradacion, capex_kw, coste_desarrollo_mw,
                       opex_kw, tasa_descuento):
    """Calculate VAN for each duration from 1 to max_h."""
    datos = []
    for h in range(1, max_h + 1):
        res = simular(precios, potencia_mw, h, ef_carga, ef_descarga,
                       estrategia, umbral_carga, umbral_descarga,
                       margen, horario)
        ingreso_anual = res["Beneficio (€)"].sum()
        capex_total = potencia_mw * 1000 * capex_kw + potencia_mw * coste_desarrollo_mw
        inversion = -capex_total
        ingresos = [ingreso_anual * (1 - degradacion / 100) ** i for i in range(15)]
        flujo = [inversion] + [ingresos[i] - potencia_mw * 1000 * opex_kw for i in range(15)]
        van = npf.npv(tasa_descuento / 100, flujo)
        datos.append({"Duración (h)": h, "VAN": van})
    df = pd.DataFrame(datos)
    opt = df.loc[df["VAN"].idxmax(), "Duración (h)"]
    return df, opt

# --- Interfaz ---
st.title("🔋 Simulador de BESS")

with st.sidebar:
    st.header("🔧 Parámetros de simulación")
    archivo = st.file_uploader("Archivo de precios", type=["xlsx", "csv"])
    zona = st.selectbox(
        "Zona",
        ["NORD", "CNORD", "CSUD", "SUD", "SARD", "SICILY", "BZ"],
    )
    tecnologia = st.selectbox("Tecnología", list(TECHS.keys()))
    cap_min, cap_max = TECHS[tecnologia]["costo"]
    cyc_min, cyc_max = TECHS[tecnologia]["ciclos"]
    st.caption(f"Vida útil estimada: {cyc_min:,}-{cyc_max:,} ciclos")
    degradacion = st.slider(
        "Degradación anual (%)", min_value=0.0, max_value=5.0, value=2.0, step=0.1
    )
    potencia_mw = st.slider("Potencia (MW)", 1, 100, 10)
    duracion_h = st.slider("Duración (h)", 1, 10, 4)
    analizar_opt = st.checkbox("Analizar duración óptima")
    max_h = st.slider("Duración máxima a evaluar", 1, 10, 6) if analizar_opt else 0
    ef_carga = st.slider("Eficiencia de carga (%)", 50, 100, 95) / 100
    ef_descarga = st.slider("Eficiencia de descarga (%)", 50, 100, 95) / 100

    estrategia = st.selectbox(
        "Estrategia", ["Percentiles", "Margen fijo", "Programada"]
    )
    umbral_carga = st.slider("Umbral de carga", 0.0, 1.0, 0.25, 0.05)
    umbral_descarga = st.slider("Umbral de descarga", 0.0, 1.0, 0.75, 0.05)
    st.caption(
        "La batería se carga cuando el precio está por debajo del percentil "
        "seleccionado en 'Umbral de carga' y se descarga cuando supera el "
        "percentil indicado en 'Umbral de descarga'."
    )

    st.markdown("### Parámetros económicos")
    coste_desarrollo_mw = st.slider(
        "Costes Desarrollo (€/MW)",
        min_value=10000,
        max_value=30000,
        value=20000,
        step=1000,
    )
    capex_kw = st.slider(
        "CAPEX (€/kW)",
        min_value=cap_min,
        max_value=cap_max,
        value=(cap_min + cap_max) // 2,
    )
    opex_kw = st.slider(
        "OPEX anual (€/kW)",
        min_value=5.0,
        max_value=8.0,
        value=6.5,
        step=0.1,
    )
    coste_mwh = st.number_input("Coste operación (€/MWh cargado)", value=0.0)
    if estrategia == "Margen fijo":
        margen = st.number_input("Margen (€/MWh)", value=10.0)
    else:
        margen = 0.0

    st.markdown("#### Modelo")
    tasa_descuento = st.number_input("Tasa de descuento (%)", 0.0, 20.0, 7.0)
    ratio_apalancamiento = st.slider(
        "Ratio de apalancamiento (%)", 0, 100, 20, step=1
    )
    coste_financiacion = st.number_input("Coste financiación (%)", 0.0, 20.0, 5.0)

    iniciar = st.button("▶️ Ejecutar simulación")
    if st.button("Restablecer parámetros"):
        reset_sidebar()

    with st.expander("Ayuda"):
        help_text = """
<small>
1. Ajusta los parámetros y pulsa **Ejecutar simulación**.<br>
2. Usa **Restablecer parámetros** para volver a los valores por defecto.<br>
3. En las pestañas de la derecha encontrarás los datos, las gráficas y los indicadores económicos.<br><br>
**Estrategias**<br>
- **Percentiles**: la batería se carga cuando el precio está por debajo del percentil indicado en *Umbral de carga* (por ejemplo 0.25) y se descarga por encima del valor elegido en *Umbral de descarga* (por ejemplo 0.75).<br>
- **Margen fijo**: se calcula el precio medio del período. Se carga si el precio cae por debajo de media&nbsp;&minus;&nbsp;margen y se descarga si supera media&nbsp;+&nbsp;margen. Ejemplo: con margen 10&nbsp;€/MWh y media 100, se compra a menos de 90 y se vende por encima de 110.<br>
- **Programada**: se suministra un CSV con columnas `hora` y `accion` (C=cargar, D=descargar) que define las horas de operación diaria, por ejemplo `0,C` `1,C` `16,D` `17,D`.
</small>
"""
        st.markdown(help_text, unsafe_allow_html=True)

if iniciar:
    precios = cargar_datos(zona, archivo)
    fecha_inicio = st.date_input("Desde", precios["Fecha"].min())
    fecha_fin = st.date_input("Hasta", precios["Fecha"].max())
    fecha_inicio = pd.to_datetime(fecha_inicio)
    fecha_fin = pd.to_datetime(fecha_fin)
    precios = precios[(precios["Fecha"] >= fecha_inicio) &
                      (precios["Fecha"] <= fecha_fin)]
    fi_date = fecha_inicio.date()
    ff_date = fecha_fin.date()

    horario = None
    if estrategia == "Programada":
        horario_file = st.file_uploader(
            "Horario (CSV con columnas hora,accion)", type="csv")
        if horario_file is not None:
            df_hor = pd.read_csv(horario_file)
            horario = {row["hora"]: row["accion"] for _, row in df_hor.iterrows()}

    resultado = simular(
        precios,
        potencia_mw,
        duracion_h,
        ef_carga,
        ef_descarga,
        estrategia,
        umbral_carga,
        umbral_descarga,
        margen,
        horario,
    )

    mensual = resumen_mensual(resultado)

    sens_df = None
    horas_opt = None
    if analizar_opt and max_h > 1:
        sens_df, horas_opt = analizar_duracion(
            precios,
            potencia_mw,
            max_h,
            ef_carga,
            ef_descarga,
            estrategia,
            umbral_carga,
            umbral_descarga,
            margen,
            horario,
            degradacion,
            capex_kw,
            coste_desarrollo_mw,
            opex_kw,
            tasa_descuento,
        )

    ingreso_anual = resultado["Beneficio (€)"].sum()
    capex_total = potencia_mw * 1000 * capex_kw + potencia_mw * coste_desarrollo_mw
    inversion = -capex_total
    ingresos = [ingreso_anual * (1 - degradacion / 100) ** i for i in range(15)]
    flujo_caja = [inversion] + [ingresos[i] - potencia_mw * 1000 * opex_kw for i in range(15)]
    van = npf.npv(tasa_descuento / 100, flujo_caja)
    tir = npf.irr(flujo_caja)

    deuda = capex_total * (ratio_apalancamiento / 100)
    equity = capex_total - deuda
    interes = deuda * (coste_financiacion / 100)
    flujo_equity = [-equity] + [ingresos[i] - potencia_mw * 1000 * opex_kw - interes for i in range(14)] + [ingresos[14] - potencia_mw * 1000 * opex_kw - interes - deuda]
    tir_equity = npf.irr(flujo_equity)

    total_descarga = resultado["Descarga (MWh)"].sum()
    ciclos_periodo = total_descarga / (potencia_mw * duracion_h)
    dias_periodo = (fecha_fin - fecha_inicio).days + 1
    ciclos_anuales = ciclos_periodo / (dias_periodo / 365)

    st.session_state.update(
        {
            "resultado": resultado,
            "mensual": mensual,
            "fi_date": fi_date,
            "ff_date": ff_date,
            "ingreso_anual": ingreso_anual,
            "inversion": inversion,
            "van": van,
            "tir": tir,
            "tir_equity": tir_equity,
            "ciclos_anuales": ciclos_anuales,
            "cyc_min": cyc_min,
            "cyc_max": cyc_max,
            "flujo_caja": flujo_caja,
            "degradacion": degradacion,
            "sens_dur": sens_df,
            "horas_optimas": horas_opt,
        }
    )

    tab_res, tab_graf, tab_ind = st.tabs(["Resultados", "Gráficas", "Indicadores"])

    with tab_res:
        st.subheader("📈 Resultados horarios")
        st.dataframe(resultado.head(100), use_container_width=True)
        st.subheader("📅 Resumen mensual")
        st.dataframe(mensual, use_container_width=True)
        csv = resultado.to_csv(index=False).encode("utf-8")
        st.download_button("Descargar resultados (CSV)", csv, "resultados_bess.csv")
        csv_m = mensual.to_csv().encode("utf-8")
        st.download_button("Descargar resumen mensual (CSV)", csv_m, "resumen_mensual.csv")

    with tab_graf:
        dia = st.slider(
            "Día a visualizar",
            min_value=fi_date,
            max_value=ff_date,
            value=st.session_state.get("dia_graf", fi_date),
            format="YYYY-MM-DD",
            key="dia_graf",
        )
        diario = resultado[resultado["Fecha"].dt.date == dia]
        if not diario.empty:
            fig_d = make_subplots(specs=[[{"secondary_y": True}]])
            fig_d.add_trace(
                go.Scatter(x=diario["Fecha"], y=diario["Precio"], name="Precio"),
                secondary_y=False,
            )
            fig_d.add_trace(
                go.Scatter(x=diario["Fecha"], y=diario["SOC (MWh)"], name="SOC (MWh)"),
                secondary_y=True,
            )
            fig_d.update_layout(title=f"Precio y SOC - {dia}")
            fig_d.update_yaxes(title_text="Precio", secondary_y=False)
            fig_d.update_yaxes(title_text="SOC (MWh)", secondary_y=True)
            st.plotly_chart(fig_d, use_container_width=True)
        else:
            st.info("No hay datos para ese día")

        fig = make_subplots(specs=[[{"secondary_y": True}]])
        fig.add_trace(
            go.Scatter(x=resultado["Fecha"], y=resultado["Precio"], name="Precio"),
            secondary_y=False,
        )
        fig.add_trace(
            go.Scatter(x=resultado["Fecha"], y=resultado["SOC (MWh)"], name="SOC (MWh)"),
            secondary_y=True,
        )
        fig.update_layout(title="Precio y Estado de Carga")
        fig.update_yaxes(title_text="Precio", secondary_y=False)
        fig.update_yaxes(title_text="SOC (MWh)", secondary_y=True)
        st.plotly_chart(fig, use_container_width=True)
        fig_b = px.bar(mensual.reset_index(), x="Mes", y="Beneficio (€)", title="Beneficio mensual")
        st.plotly_chart(fig_b, use_container_width=True)

        years = list(range(16))
        fig_cash = px.bar(x=years, y=flujo_caja,
                          labels={"x": "Año", "y": "Flujo de caja (€)"},
                          title="Flujo de caja anual")
        st.plotly_chart(fig_cash, use_container_width=True)
        if sens_df is not None:
            fig_s = px.line(
                sens_df,
                x="Duración (h)",
                y="VAN",
                markers=True,
                title="VAN según duración",
            )
            fig_s.add_vline(x=horas_opt, line_dash="dash", line_color="red")
            st.plotly_chart(fig_s, use_container_width=True)
    with tab_ind:
        st.subheader("📊 Indicadores económicos")
        info_text = textwrap.dedent(
            f"""
            - **Ingreso anual estimado**: {ingreso_anual:,.0f} €
            - **Inversión inicial**: {inversion:,.0f} €
            - **VAN (15 años)**: {van:,.0f} €
            - **TIR proyecto**: {tir*100:.2f} %
            - **TIR equity**: {tir_equity*100:.2f} %
            - **Ciclos usados al año**: {ciclos_anuales:.1f} (vida útil {cyc_min}-{cyc_max} ciclos)
            - **Degradación anual**: {degradacion:.1f} %
            {f"- **Duración óptima**: {horas_opt} h" if horas_opt else ""}
            """
        )
        st.markdown(info_text)
else:
    st.info("Configura los parámetros en la barra lateral y pulsa Ejecutar.")
