
import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

# --- CONFIGURACIÓN INICIAL ---
st.set_page_config(page_title="Simulador BESS - Naturgy", layout="wide")
st.title("🔋 Simulador de BESS - Naturgy")

# --- CARGA DE DATOS ---
@st.cache_data
def cargar_datos():
    df = pd.read_excel("precios_estimados_2024.xlsx")
    df["Fecha"] = pd.to_datetime(df["Fecha"])
    return df

precios = cargar_datos()
zona_list = [c for c in precios.columns if c not in ["Fecha", "Hora"]]

# --- PARÁMETROS ---
st.sidebar.header("⚙️ Parámetros del sistema")
zona = st.sidebar.selectbox("Zona de operación", zona_list)
potencia_mw = st.sidebar.number_input("Potencia [MW]", min_value=1.0, value=10.0)
duracion_h = st.sidebar.number_input("Duración [h]", min_value=0.5, value=2.0)
ef_carga = st.sidebar.slider("Eficiencia carga [%]", 50, 100, 95)
ef_descarga = st.sidebar.slider("Eficiencia descarga [%]", 50, 100, 95)
ciclos_dia = st.sidebar.slider("Máx. ciclos por día", 1, 5, 1)
coste_mantenimiento = st.sidebar.number_input("Coste OPEX [€/kW/año]", value=15.0)

# --- SIMULACIÓN ---
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

if st.button("▶️ Ejecutar simulación"):
    resultado = simular(precios, zona, potencia_mw, duracion_h, ef_carga, ef_descarga)

    st.subheader("📈 Resultados anuales")
    total_ingresos = resultado["Ingresos"].sum()
    total_costes = resultado["Costes"].sum()
    total_beneficio = resultado["Beneficio"].sum()
    capex_estimado = potencia_mw * duracion_h * 400  # €/kWh
    opex_total = potencia_mw * 1000 * coste_mantenimiento

    st.markdown(f"**Ingresos:** €{total_ingresos:,.0f}")
    st.markdown(f"**Costes:** €{total_costes:,.0f}")
    st.markdown(f"**Beneficio neto anual:** €{total_beneficio - opex_total:,.0f}")
    st.markdown(f"**OPEX estimado:** €{opex_total:,.0f}")
    st.markdown(f"**CAPEX estimado:** €{capex_estimado:,.0f}")

    st.subheader("📅 Selección de día para análisis horario")
    fecha_sel = st.date_input("Selecciona un día", value=resultado["Fecha"].dt.date.min())
    df_dia = resultado[resultado["Fecha"].dt.date == fecha_sel]

    fig, ax1 = plt.subplots(figsize=(12, 4))
    ax1.plot(df_dia["Hora"], df_dia["Precio"], color="gray", label="Precio [€/MWh]")
    ax1.set_ylabel("Precio [€/MWh]", color="gray")

    ax2 = ax1.twinx()
    ax2.bar(df_dia["Hora"], df_dia["Carga"], width=0.4, color="green", label="Carga")
    ax2.bar(df_dia["Hora"] + 0.4, df_dia["Descarga"], width=0.4, color="red", label="Descarga")
    ax2.set_ylabel("Energía [MWh]")

    fig.legend(loc="upper right")
    st.pyplot(fig)

    st.dataframe(df_dia[["Fecha", "Precio", "Carga", "Descarga", "Ingresos", "Costes", "Beneficio"]].round(2))
