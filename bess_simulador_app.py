
import streamlit as st
import pandas as pd
import numpy as np
import numpy_financial as npf

st.set_page_config(page_title="Simulador de BESS - Naturgy", layout="wide")

@st.cache_data
def cargar_datos(zona):
    path = "data/precios_italia.xlsx"
    xls = pd.ExcelFile(path)
    df = pd.read_excel(xls, sheet_name=zona)
    df["Fecha"] = pd.to_datetime(df["Fecha"])
    return df

def simular(precios, potencia_mw, duracion_h, ef_carga, ef_descarga, opex_kw, capex_kw):
    resultados = []
    energia_mwh = potencia_mw * duracion_h
    for dia, grupo in precios.groupby(precios["Fecha"].dt.date):
        grupo = grupo.copy()
        grupo["Estado"] = ""
        grupo["SOC"] = 0.0
        grupo["Beneficio"] = 0.0
        grupo = grupo.sort_values(by="Precio")
        grupo.iloc[:duracion_h, grupo.columns.get_loc("Estado")] = "Carga"
        grupo.iloc[-duracion_h:, grupo.columns.get_loc("Estado")] = "Descarga"
        grupo["SOC"] = np.where(grupo["Estado"] == "Carga", 1.0, np.where(grupo["Estado"] == "Descarga", 0.0, np.nan))
        grupo["SOC"].ffill(inplace=True)
        grupo["Beneficio"] = np.where(grupo["Estado"] == "Descarga", grupo["Precio"] * energia_mwh * ef_descarga, 0) -                              np.where(grupo["Estado"] == "Carga", grupo["Precio"] * energia_mwh / ef_carga, 0)
        resultados.append(grupo)
    df_resultado = pd.concat(resultados)
    return df_resultado

st.title("Simulador de BESS - Naturgy")

zona = st.sidebar.selectbox("Zona", ["NORTE", "SUD", "CNOR", "CSUD"])
potencia_mw = st.sidebar.slider("Potencia (MW)", 1, 100, 10)
duracion_h = st.sidebar.select_slider("Duración (h)", options=list(range(1, 25)), value=6)
ef_carga = st.sidebar.slider("Eficiencia de carga (%)", 50, 100, 95) / 100
ef_descarga = st.sidebar.slider("Eficiencia de descarga (%)", 50, 100, 95) / 100
opex_kw = st.sidebar.number_input("OPEX anual (€/kW)", value=15.0)
capex_kw = st.sidebar.number_input("CAPEX (€/kW)", value=800.0)

if st.sidebar.button("▶️ Ejecutar simulación"):
    precios = cargar_datos(zona)
    resultado = simular(precios, potencia_mw, duracion_h, ef_carga, ef_descarga, opex_kw, capex_kw)
    st.subheader("📊 Parámetros seleccionados")
    st.markdown(f'''
    - **Zona:** {zona}
    - **Potencia:** {potencia_mw} MW
    - **Duración:** {duracion_h} h
    - **Eficiencia de carga:** {ef_carga*100:.0f}%
    - **Eficiencia de descarga:** {ef_descarga*100:.0f}%
    - **OPEX:** {opex_kw} €/kW
    - **CAPEX:** {capex_kw} €/kW
    ''')
    st.dataframe(resultado)
