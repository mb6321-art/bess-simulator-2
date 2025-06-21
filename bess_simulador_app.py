
import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

# Parámetros iniciales
st.set_page_config(page_title="Simulador de BESS - Naturgy", layout="wide")

st.title("🔋 Simulador de BESS - Naturgy")

# Parámetros de entrada
st.sidebar.subheader("Parámetros de simulación")
zona = st.sidebar.selectbox("Zona", ["NORTE", "SUR", "ESTE", "OESTE"])
potencia_mw = st.sidebar.slider("Potencia (MW)", 1.0, 100.0, 10.0, 1.0)
duracion_h = st.sidebar.slider("Duración (h)", 1.0, 12.0, 6.0, 1.0)
ef_carga = st.sidebar.slider("Eficiencia de carga (%)", 80, 100, 95)
ef_descarga = st.sidebar.slider("Eficiencia de descarga (%)", 80, 100, 95)
opex_anual = st.sidebar.number_input("OPEX anual (€/kW)", min_value=0.0, value=15.0)
precio_mwh = st.sidebar.number_input("Precio inversión (€/MWh)", min_value=0.0, value=400_000.0)

if st.sidebar.button("▶️ Ejecutar simulación"):
    # Simulación de datos de ejemplo
    fechas = pd.date_range("2025-01-01", periods=24, freq="H")
    precios = np.random.uniform(30, 120, size=24)

    df = pd.DataFrame({
        "Fecha": fechas,
        "Precio (€/MWh)": precios,
        "Carga (MWh)": np.where(precios < 60, potencia_mw, 0),
        "Descarga (MWh)": np.where(precios > 100, potencia_mw, 0),
    })

    df["SOC (%)"] = np.cumsum(df["Carga (MWh)"] * ef_carga / 100 - df["Descarga (MWh)"] / (ef_descarga / 100))
    df["SOC (%)"] = df["SOC (%)"].clip(lower=0, upper=duracion_h * potencia_mw)

    st.subheader("📊 Parámetros seleccionados")
    st.markdown(
        f"**Zona:** {zona}<br>"
        f"**Potencia:** {potencia_mw} MW<br>"
        f"**Duración:** {duracion_h} h<br>"
        f"**Eficiencia de carga:** {ef_carga}%<br>"
        f"**Eficiencia de descarga:** {ef_descarga}%<br>"
        f"**OPEX anual:** {opex_anual} €/kW<br>"
        f"**Precio inversión:** {precio_mwh} €/MWh",
        unsafe_allow_html=True
    )

    st.subheader("🔍 Resultado de la simulación")
    st.dataframe(df)

    st.line_chart(df.set_index("Fecha")[["Precio (€/MWh)", "SOC (%)"]])
