
import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime

# --- CONFIGURACIÓN INICIAL ---
st.set_page_config(page_title="Simulador BESS - Naturgy", layout="wide")
st.title("🔋 Simulador de BESS - Naturgy")

# --- CARGA DE DATOS ---
def cargar_datos_excel():
    df = pd.read_excel("precios_estimados_2024.xlsx")
    df["Fecha"] = pd.to_datetime(df["Fecha"])
    return df

@st.cache_data
def cargar_datos_omie():
    try:
        url = "https://www.omie.es/sites/default/files/dados/AGNO_2024/INT_PBC_EV_H_1.csv"
        df = pd.read_csv(url, sep=";", encoding="latin1")
        df["Fecha"] = pd.to_datetime(df["Fecha"])
        df["Hora"] = df["Hora"].astype(int)
        zonas = ["NORTE", "SUR", "CENTRO"]
        for zona in zonas:
            df[zona] = df["Precio"]
        return df[["Fecha", "Hora"] + zonas]
    except Exception as e:
        st.error(f"No se pudieron descargar los datos: {e}")
        return None

fuente = st.sidebar.radio("Fuente de precios", ["Excel local", "OMIE (online)"])
if fuente == "Excel local":
    precios = cargar_datos_excel()
else:
    precios = cargar_datos_omie()

if precios is not None:
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
            if len(grupo) < 24:
                continue
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

        st.header("📊 Parámetros seleccionados")
        st.markdown(f"- **Zona:** {zona}")
        st.markdown(f"- **Potencia:** {potencia_mw} MW")
        st.markdown(f"- **Duración:** {duracion_h} h")
        st.markdown(f"- **Eficiencias:** carga {ef_carga}%, descarga {ef_descarga}%")
        st.markdown(f"- **OPEX anual:** {coste_mantenimiento} €/kW")

        st.header("📈 Resultados anuales")
        total_ingresos = resultado["Ingresos"].sum()
        total_costes = resultado["Costes"].sum()
        total_beneficio = resultado["Beneficio"].sum()
        capex_estimado = potencia_mw * duracion_h * 400  # €/kWh
        opex_total = potencia_mw * 1000 * coste_mantenimiento

        col1, col2, col3 = st.columns(3)
        col1.metric("Ingresos [€]", f"{total_ingresos:,.0f}")
        col2.metric("Costes [€]", f"{total_costes:,.0f}")
        col3.metric("Beneficio neto [€]", f"{total_beneficio - opex_total:,.0f}")

        st.header("📅 Análisis horario")
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
