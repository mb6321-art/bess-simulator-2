
# bess_simulador_app.py
import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from io import BytesIO
import base64
import openpyxl
import numpy_financial as npf

st.set_page_config(layout="wide", page_title="Simulador de BESS - Naturgy")

# --------- Estilo inicial ----------
st.markdown("""
    <style>
        .css-18e3th9 {padding-top: 1rem;}
        .css-1d391kg {padding-top: 0;}
        .block-container {padding-top: 2rem;}
    </style>
""", unsafe_allow_html=True)

# --------- Logo ----------
logo_url = "https://upload.wikimedia.org/wikipedia/commons/e/e1/Naturgy_logo.svg"
st.sidebar.image(logo_url, width=150)

# --------- Parámetros ----------
st.title("Simulador de BESS - Naturgy")
st.sidebar.markdown("## Parámetros de simulación")

escenario = st.sidebar.selectbox("Escenario de operación", ["Merchant 100%"], index=0)

zona = st.sidebar.selectbox("Zona", ["NORTE", "CENTRO", "SUR"])
potencia_mw = st.sidebar.slider("Potencia del sistema (MW)", 1.0, 100.0, 10.0)
duracion_h = st.sidebar.slider("Duración del sistema (h)", 1.0, 12.0, 6.0)
ef_carga = st.sidebar.slider("Eficiencia de carga (%)", 70, 100, 95) / 100
ef_descarga = st.sidebar.slider("Eficiencia de descarga (%)", 70, 100, 95) / 100
opex_kw = st.sidebar.number_input("OPEX anual (€/kW)", 0.0, 100.0, 15.0)
tasa_descuento = st.sidebar.number_input("Tasa de descuento (%)", 0.0, 15.0, 7.0) / 100
precio_inversion_kw = st.sidebar.number_input("CAPEX total (€/kW)", 0.0, 2000.0, 500.0)

# --------- Datos de precios ----------
st.sidebar.markdown("### Fuente de precios")
fuente = st.sidebar.radio("Fuente", ["OMIE", "Archivo Excel"])

if fuente == "OMIE":
    st.warning("⚠️ No se pudieron descargar datos reales. Se usarán datos simulados.")
    horas = list(range(24))
    precios = pd.DataFrame({
        "Fecha": pd.date_range("2025-01-01", periods=24, freq="H"),
        "Precio": np.random.uniform(30, 100, 24),
        "Hora": horas
    })
else:
    archivo = st.sidebar.file_uploader("Subir archivo Excel", type=["xlsx"])
    if archivo:
        try:
            precios = pd.read_excel(archivo)
            precios["Hora"] = pd.to_datetime(precios["Fecha"]).dt.hour
        except Exception as e:
            st.error(f"Error al leer el archivo: {e}")
            st.stop()
    else:
        precios = None

# --------- Simulación ----------
def simular(precios, zona, potencia, duracion, ef_c, ef_d):
    resultados = []
    fechas_unicas = precios["Fecha"].dt.date.unique()
    for dia in fechas_unicas:
        grupo = precios[precios["Fecha"].dt.date == dia].copy()
        grupo = grupo.sort_values("Hora")
        grupo["SOC"] = 0.0
        energia_max = potencia * duracion
        energia = 0.0
        ingresos = []
        socs = []

        for _, fila in grupo.iterrows():
            precio = fila["Precio"]
            if precio < grupo["Precio"].mean():
                carga = min(potencia, energia_max - energia) * ef_c
                energia += carga
                ingresos.append(-carga * precio)
            else:
                descarga = min(potencia, energia) / ef_d
                energia -= descarga
                ingresos.append(descarga * precio)
            socs.append(energia / energia_max * 100)

        grupo["Ingresos"] = ingresos
        grupo["SOC"] = socs
        resultados.append(grupo)

    return pd.concat(resultados)

# --------- Ejecutar ----------
if st.sidebar.button("▶ Ejecutar simulación") and precios is not None:
    resultado = simular(precios, zona, potencia_mw, duracion_h, ef_carga, ef_descarga)

    st.subheader("📊 Resultados de la simulación")
    st.markdown(f"**Zona:** {zona} &nbsp;&nbsp;|&nbsp;&nbsp; **Potencia:** {potencia_mw} MW &nbsp;&nbsp;|&nbsp;&nbsp; **Duración:** {duracion_h} h")

    fig, ax1 = plt.subplots(figsize=(10, 4))
    ax2 = ax1.twinx()
    ax1.plot(resultado["Fecha"], resultado["Precio"], label="Precio", marker='o')
    ax2.plot(resultado["Fecha"], resultado["SOC"], label="SOC (%)", color="green", linestyle="--")
    ax1.set_ylabel("€/MWh")
    ax2.set_ylabel("SOC (%)")
    ax1.set_title("Precio horario y nivel de carga")
    ax1.grid(True)
    st.pyplot(fig)

    st.markdown("### 📈 Estudio financiero")
    ingresos_totales = resultado["Ingresos"].sum()
    opex_anual = opex_kw * potencia_mw * 1000
    flujo_caja = [-precio_inversion_kw * potencia_mw * 1000]
    for _ in range(15):
        flujo_caja.append(ingresos_totales - opex_anual)
    van = npf.npv(tasa_descuento, flujo_caja)
    tir = npf.irr(flujo_caja)

    st.markdown(f"- **Ingresos anuales simulados:** {ingresos_totales:,.0f} €")
    st.markdown(f"- **VAN (15 años, tasa {tasa_descuento*100:.1f}%):** {van:,.0f} €")
    st.markdown(f"- **TIR:** {tir*100:.1f} %")
