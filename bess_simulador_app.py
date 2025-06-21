
import streamlit as st
import pandas as pd
import numpy as np
import altair as alt
from datetime import datetime
import matplotlib.pyplot as plt

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="Simulador BESS - Naturgy", layout="wide")
st.markdown("<h1 style='display: inline-block;'>🔋 Simulador de BESS - Naturgy</h1>", unsafe_allow_html=True)
st.markdown(
    "<div style='position:absolute; top:10px; right:10px;'>"
    "<img src='https://upload.wikimedia.org/wikipedia/commons/thumb/b/b1/Naturgy_logo.svg/320px-Naturgy_logo.svg.png' "
    "style='height:50px;'/></div>",
    unsafe_allow_html=True
)

# --- FUNCIÓN PARA CARGAR DATOS DESDE EXCEL ---
def cargar_datos_excel():
    try:
        df = pd.read_excel("precios_estimados_2024.xlsx")
        df["Fecha"] = pd.to_datetime(df["Fecha"])
        return df
    except Exception as e:
        st.error(f"❌ Error cargando Excel: {e}")
        return None

# --- FUNCIÓN PARA GENERAR DATOS SIMULADOS ---
@st.cache_data
def cargar_datos_omie():
    try:
        st.warning("🔧 No se pudieron descargar los datos reales de OMIE. Usando datos simulados.")
        fechas = pd.date_range("2024-01-01", periods=24*365, freq="H")
        df = pd.DataFrame({
            "Fecha": fechas.date,
            "Hora": fechas.hour,
            "NORTE": np.random.uniform(30, 160, len(fechas)),
            "SUR": np.random.uniform(35, 165, len(fechas)),
            "CENTRO": np.random.uniform(40, 170, len(fechas)),
        })
        return df
    except Exception as e:
        st.error(f"No se pudieron generar datos: {e}")
        return None


# --- PARÁMETROS DE ENTRADA ---
st.sidebar.header("⚙️ Parámetros del sistema")
modo_datos = st.sidebar.radio("Origen de datos", ["Excel local", "Datos simulados"])
zona = st.sidebar.selectbox("Zona de operación", ["NORTE", "SUR", "CENTRO"])
potencia_mw = st.sidebar.number_input("Potencia [MW]", min_value=1.0, value=10.0)
duracion_h = st.sidebar.number_input("Duración [h]", min_value=0.5, value=2.0)
ef_carga = st.sidebar.slider("Eficiencia carga [%]", 50, 100, 95)
ef_descarga = st.sidebar.slider("Eficiencia descarga [%]", 50, 100, 95)
ciclos_dia = st.sidebar.slider("Máx. ciclos por día", 1, 3, 1)
coste_opex = st.sidebar.number_input("OPEX [€/kW/año]", value=15.0)
coste_capex_kwh = st.sidebar.number_input("CAPEX [€/kWh]", value=400.0)
porcentaje_deuda = st.sidebar.slider("Deuda sobre inversión [%]", 0, 100, 70)
interes_deuda = st.sidebar.slider("Interés deuda [%]", 0.0, 10.0, 4.0)
anios = 15

if modo_datos == "Excel local":
    precios = cargar_datos_excel()
else:
    precios = cargar_datos_omie()

if precios is not None and st.sidebar.button("▶️ Ejecutar simulación"):

    energia_mwh = potencia_mw * duracion_h
    df = precios[["Fecha", "Hora", zona]].copy()
    df = df.rename(columns={zona: "Precio"})
    df["Día"] = pd.to_datetime(df["Fecha"])
    df["Carga"] = 0.0
    df["Descarga"] = 0.0
    df["SOC"] = 0.0

    resultados = []
    for dia, grupo in df.groupby("Día"):
        grupo = grupo.copy()
        grupo.sort_values("Precio", inplace=True)
        carga_horas = grupo.head(int(duracion_h))
        descarga_horas = grupo.tail(int(duracion_h))

        grupo.loc[carga_horas.index, "Carga"] = energia_mwh / duracion_h
        grupo.loc[descarga_horas.index, "Descarga"] = (energia_mwh * ef_carga/100 * ef_descarga/100) / duracion_h

        grupo["SOC"] = grupo["Carga"].cumsum() - grupo["Descarga"].cumsum()
        resultados.append(grupo)

    df_sim = pd.concat(resultados)
    df_sim["Ingresos"] = df_sim["Descarga"] * df_sim["Precio"]
    df_sim["Costes"] = df_sim["Carga"] * df_sim["Precio"]
    df_sim["Beneficio"] = df_sim["Ingresos"] - df_sim["Costes"]

    st.subheader("📊 Parámetros seleccionados")
    st.markdown(f"""**Zona:** {zona}  
**Potencia:** {potencia_mw} MW  
**Duración:** {duracion_h} h  
**Eficiencias:** carga {ef_carga}%, descarga {ef_descarga}%  
**OPEX anual:** {coste_opex} €/kW""")

    # --- CÁLCULO FLUJO DE CAJA Y TIR ---
    ingresos_anuales = df_sim["Ingresos"].sum()
    costes_anuales = df_sim["Costes"].sum()
    beneficio_anual = ingresos_anuales - costes_anuales - (potencia_mw * 1000 * coste_opex)
    capex_total = potencia_mw * duracion_h * 1000 * coste_capex_kwh / 1000

    flujo_caja = [-capex_total] + [beneficio_anual] * anios
    tir_proyecto = np.irr(flujo_caja)

    equity = capex_total * (1 - porcentaje_deuda / 100)
    deuda = capex_total * (porcentaje_deuda / 100)
    pago_anual_deuda = np.pmt(interes_deuda / 100, anios, -deuda)
    beneficio_equity = beneficio_anual - pago_anual_deuda
    flujo_equity = [-equity] + [beneficio_equity] * anios
    tir_equity = np.irr(flujo_equity)

    col1, col2, col3 = st.columns(3)
    col1.metric("Ingresos [€]", f"{ingresos_anuales:,.0f}")
    col2.metric("Costes [€]", f"{costes_anuales:,.0f}")
    col3.metric("Beneficio neto [€]", f"{beneficio_anual:,.0f}")

    col4, col5 = st.columns(2)
    col4.metric("TIR Proyecto", f"{tir_proyecto*100:.2f}%")
    col5.metric("TIR Equity", f"{tir_equity*100:.2f}%")

    st.subheader("📉 Flujo de caja (15 años)")
    flujo_df = pd.DataFrame({
        "Año": list(range(0, anios+1)),
        "Flujo de Caja Proyecto (€)": flujo_caja,
        "Flujo de Caja Equity (€)": flujo_equity
    })
    chart = alt.Chart(flujo_df.melt("Año")).mark_line(point=True).encode(
        x="Año:O",
        y="value:Q",
        color="variable:N"
    ).properties(height=300)
    st.altair_chart(chart, use_container_width=True)


    # --- ANÁLISIS HORARIO INTERACTIVO ---
    st.subheader("📅 Análisis horario")

    fecha_sel = st.date_input("Selecciona un día", value=df_sim["Día"].min())
    df_dia = df_sim[df_sim["Día"] == pd.to_datetime(fecha_sel)].copy()

    if not df_dia.empty:
        df_dia["Hora_str"] = df_dia["Hora"].astype(str) + ":00"

        base = alt.Chart(df_dia).encode(x=alt.X("Hora_str:N", title="Hora"))

        linea_precio = base.mark_line(strokeWidth=2, color="gray").encode(
            y=alt.Y("Precio:Q", title="Precio [€/MWh]"),
            tooltip=["Hora", "Precio"]
        ).properties(title="Precio, Carga, Descarga y SOC por hora")

        barras_carga = base.mark_bar(color="green").encode(
            y=alt.Y("Carga:Q", title="Energía [MWh]"),
            tooltip=["Carga"]
        )

        barras_descarga = base.mark_bar(color="red").encode(
            y=alt.Y("Descarga:Q"),
            tooltip=["Descarga"]
        )

        linea_soc = base.mark_line(strokeDash=[5,5], color="blue").encode(
            y=alt.Y("SOC:Q", title="Estado de carga [MWh]"),
            tooltip=["SOC"]
        )

        final_chart = alt.layer(linea_precio, barras_carga, barras_descarga, linea_soc).resolve_scale(
            y='independent'
        ).properties(width=800, height=300)

        st.altair_chart(final_chart, use_container_width=True)

        st.dataframe(df_dia[["Fecha", "Hora", "Precio", "Carga", "Descarga", "SOC", "Ingresos", "Costes", "Beneficio"]].round(2))
    else:
        st.warning("⚠️ No hay datos para esta fecha.")
