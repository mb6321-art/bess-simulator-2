
import streamlit as st
import pandas as pd
import numpy as np
import numpy_financial as npf
import matplotlib.pyplot as plt
import os

st.set_page_config(page_title="Simulador de BESS - Naturgy", layout="wide")

st.title("Simulador de BESS - Naturgy")

# Parámetros
st.sidebar.header("🔧 Parámetros del sistema")
escenario = st.sidebar.selectbox("Escenario", ["Merchant 100%"], index=0)
zona = st.sidebar.selectbox("Zona", ["NORTE", "SUR", "ESTE", "OESTE"])
potencia_mw = st.sidebar.number_input("Potencia BESS (MW)", min_value=1.0, value=10.0, step=1.0)
duracion_h = st.sidebar.number_input("Duración BESS (h)", min_value=1.0, value=6.0, step=1.0)
ef_carga = st.sidebar.slider("Eficiencia de carga (%)", 50, 100, 95)
ef_descarga = st.sidebar.slider("Eficiencia de descarga (%)", 50, 100, 95)
opex_kw = st.sidebar.number_input("OPEX anual (€/kW)", min_value=0.0, value=15.0, step=1.0)
precio_mwh = st.sidebar.number_input("Coste medio energético (€/MWh)", min_value=0.0, value=40.0, step=1.0)
tasa_descuento = st.sidebar.number_input("Tasa de descuento (%)", min_value=0.0, value=7.0, step=0.1) / 100

# Cargar datos de precios
@st.cache_data
def cargar_datos(zona):
    path = os.path.join("data", f"precios_{zona.lower()}.xlsx")
    return pd.read_excel(path)

def simular(precios, potencia_mw, duracion_h, ef_carga, ef_descarga, precio_mwh):
    energia_total_mwh = potencia_mw * duracion_h
    ingresos = []
    soc = 0
    socs = []

    for precio in precios["Precio"]:
        if precio < precio_mwh:
            carga = energia_total_mwh * (ef_carga / 100)
            soc += carga
            ingresos.append(-carga * precio)
        else:
            descarga = min(soc, energia_total_mwh) * (ef_descarga / 100)
            ingresos.append(descarga * precio)
            soc -= descarga
        socs.append(min(soc, energia_total_mwh))
    precios["SOC"] = socs
    precios["Ingresos"] = ingresos
    return precios

# Ejecutar simulación
if st.sidebar.button("▶️ Ejecutar simulación"):
    precios = cargar_datos(zona)
    resultado = simular(precios.copy(), potencia_mw, duracion_h, ef_carga, ef_descarga, precio_mwh)

    st.subheader("📊 Parámetros seleccionados")
    st.markdown(f"""
        **Escenario:** {escenario}  
        **Zona:** {zona}  
        **Potencia:** {potencia_mw} MW  
        **Duración:** {duracion_h} h  
        **Eficiencias:** carga {ef_carga}%, descarga {ef_descarga}%  
        **OPEX anual:** {opex_kw} €/kW  
        **Precio medio energía:** {precio_mwh} €/MWh  
        **Tasa de descuento:** {tasa_descuento * 100:.1f} %
    """)

    st.subheader("📈 Resultado diario")
    st.line_chart(resultado.set_index("Fecha")[["SOC", "Ingresos"]])

    st.subheader("💰 Estudio financiero")
    flujo_caja = [-potencia_mw * 1000 * 500] + [resultado["Ingresos"].sum() - opex_kw * potencia_mw * 1000] * 15
    van = npf.npv(tasa_descuento, flujo_caja)
    tir = npf.irr(flujo_caja)
    st.write(f"**VAN**: {van:,.2f} €")
    st.write(f"**TIR**: {tir * 100:.2f} %")
