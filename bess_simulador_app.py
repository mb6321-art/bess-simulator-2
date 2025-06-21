
import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime
import requests
import io

st.set_page_config(page_title="Simulador BESS - Naturgy", layout="wide")
st.title("🔋 Simulador de BESS - Naturgy")

# --- SELECCIÓN DE FUENTE DE DATOS ---
st.sidebar.header("⚙️ Parámetros del sistema")
data_source = st.sidebar.radio("Fuente de datos", ["Excel local", "Descargar OMIE"])

@st.cache_data
def cargar_datos_excel():
    df = pd.read_excel("precios_omie_2024.xlsx")
    df["Fecha"] = pd.to_datetime(df["Fecha"])
    return df

@st.cache_data
def descargar_datos_omie():
    try:
        url = "https://raw.githubusercontent.com/datasets/energy-prices/master/data/europe-daily-electricity-prices.csv"
        content = requests.get(url).content
        df = pd.read_csv(io.StringIO(content.decode('utf-8')))
        df = df[df["Country"] == "Spain"]
        df["Fecha"] = pd.to_datetime(df["Date"])
        df = df[["Fecha", "Price"]].rename(columns={"Price": "NORD"})
        df = df.loc[df["Fecha"].dt.year == 2024]
        df = df.assign(Hora=np.tile(np.arange(24), len(df)//24))
        df = df[["Fecha", "Hora", "NORD"]]
        return df
    except Exception as e:
        st.error(f"No se pudieron descargar los datos: {e}")
        return pd.DataFrame()

if data_source == "Excel local":
    precios = cargar_datos_excel()
else:
    precios = descargar_datos_omie()

zona_list = [c for c in precios.columns if c not in ["Fecha", "Hora"]]
zona = st.sidebar.selectbox("Zona de operación", zona_list)
potencia_mw = st.sidebar.number_input("Potencia [MW]", min_value=1.0, value=10.0)
duracion_h = st.sidebar.number_input("Duración [h]", min_value=0.5, value=2.0)
ef_carga = st.sidebar.slider("Eficiencia carga [%]", 50, 100, 95)
ef_descarga = st.sidebar.slider("Eficiencia descarga [%]", 50, 100, 95)
ciclos_dia = st.sidebar.slider("Máx. ciclos por día", 1, 5, 1)
coste_mantenimiento = st.sidebar.number_input("Coste OPEX [€/kW/año]", value=15.0)

def simular(precios, zona, potencia, duracion, ef_in, ef_out):
    df = precios[["Fecha", "Hora", zona]].copy()
    df = df.rename(columns={zona: "Precio"})
    df["Día"] = df["Fecha"].dt.date
    df["Carga"] = 0.0
    df["Descarga"] = 0.0
    df["Estado"] = ""

    energia = potencia * duracion
    df_resultados = []

    for dia, grupo in df.groupby("Día"):
        g = grupo.sort_values("Precio")
        cargas = g.head(int(duracion)).copy()
        cargas["Carga"] = energia / duracion
        cargas["Estado"] = "Carga"

        g2 = grupo.sort_values("Precio", ascending=False)
        descargas = g2.head(int(duracion)).copy()
        descargas["Descarga"] = energia * (ef_in/100) * (ef_out/100) / duracion
        descargas["Estado"] = "Descarga"

        resultado_dia = grupo.copy()
        resultado_dia.update(cargas.set_index("Fecha"))
        resultado_dia.update(descargas.set_index("Fecha"))
        df_resultados.append(resultado_dia)

    df_final = pd.concat(df_resultados).sort_values("Fecha")
    df_final["Ingresos"] = df_final["Descarga"] * df_final["Precio"]
    df_final["Costes"] = df_final["Carga"] * df_final["Precio"]
    df_final["Beneficio"] = df_final["Ingresos"] - df_final["Costes"]

    return df_final

if st.sidebar.button("▶️ Ejecutar simulación"):
    resultado = simular(precios, zona, potencia_mw, duracion_h, ef_carga, ef_descarga)

    st.header("📌 Parámetros seleccionados")
    st.write({
        "Zona": zona,
        "Potencia (MW)": potencia_mw,
        "Duración (h)": duracion_h,
        "Eficiencia carga (%)": ef_carga,
        "Eficiencia descarga (%)": ef_descarga,
        "OPEX (€/kW/año)": coste_mantenimiento
    })

    st.header("📈 Resultados anuales")
    total_ingresos = resultado["Ingresos"].sum()
    total_costes = resultado["Costes"].sum()
    total_beneficio = resultado["Beneficio"].sum()
    capex_estimado = potencia_mw * duracion_h * 400
    opex_total = potencia_mw * 1000 * coste_mantenimiento

    st.metric("Ingresos", f"€{total_ingresos:,.0f}")
    st.metric("Costes", f"€{total_costes:,.0f}")
    st.metric("Beneficio neto anual", f"€{total_beneficio - opex_total:,.0f}")
    st.metric("OPEX estimado", f"€{opex_total:,.0f}")
    st.metric("CAPEX estimado", f"€{capex_estimado:,.0f}")

    st.subheader("📅 Análisis diario")
    fecha_sel = st.date_input("Selecciona un día", value=resultado["Fecha"].dt.date.min())
    df_dia = resultado[resultado["Fecha"].dt.date == fecha_sel]

    fig, ax1 = plt.subplots(figsize=(12, 4))
    ax1.plot(df_dia["Hora"], df_dia["Precio"], color="gray", label="Precio [€/MWh]")
    ax2 = ax1.twinx()
    ax2.bar(df_dia["Hora"], df_dia["Carga"], width=0.4, color="green", label="Carga")
    ax2.bar(df_dia["Hora"] + 0.4, df_dia["Descarga"], width=0.4, color="red", label="Descarga")
    fig.legend(loc="upper right")
    st.pyplot(fig)
