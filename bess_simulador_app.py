
import streamlit as st
import pandas as pd
import numpy as np
import numpy_financial as npf
import io

st.set_page_config(page_title="Simulador de BESS", layout="wide")

# --- Funciones ---
@st.cache_data
def cargar_datos(zona):
    path = f"data/precios_italia.xlsx"
    df = pd.read_excel(path, sheet_name=zona)
    df["Fecha"] = pd.to_datetime(df["Fecha"])
    return df

def simular(precios, potencia_mw, duracion_h, ef_carga, ef_descarga):
    energia_mwh = potencia_mw * duracion_h
    capacidad_actual = 0
    resultados = []
    ingresos_totales = []

    for i, row in precios.iterrows():
        precio = row["Precio"]
        estado = "Reposo"
        carga = descarga = ingreso = 0
        if precio < precios["Precio"].quantile(0.25) and capacidad_actual < energia_mwh:
            carga = potencia_mw * ef_carga
            capacidad_actual += carga
            estado = "Carga"
            ingreso = -precio * carga
        elif precio > precios["Precio"].quantile(0.75) and capacidad_actual > 0:
            descarga = potencia_mw * ef_descarga
            descarga = min(descarga, capacidad_actual)
            capacidad_actual -= descarga
            estado = "Descarga"
            ingreso = precio * descarga

        resultados.append({
            "Fecha": row["Fecha"],
            "Precio": precio,
            "Carga (MWh)": carga if estado == "Carga" else 0,
            "Descarga (MWh)": descarga if estado == "Descarga" else 0,
            "SOC (MWh)": capacidad_actual,
            "Estado": estado,
            "Beneficio (€)": ingreso
        })
        ingresos_totales.append(ingreso)

    return pd.DataFrame(resultados), ingresos_totales

# --- Interfaz ---
st.title("🔋 Simulador de BESS - Merchant")

st.sidebar.header("🔧 Parámetros de simulación")

zona = st.sidebar.selectbox("Zona", ["NORTE", "CENTRO_NORTE", "CENTRO_SUD", "SUD"])
potencia_mw = st.sidebar.slider("Potencia (MW)", 1, 100, 10)
duracion_h = st.sidebar.slider("Duración (h)", 1, 10, 4)
ef_carga = st.sidebar.slider("Eficiencia de carga (%)", 50, 100, 95) / 100
ef_descarga = st.sidebar.slider("Eficiencia de descarga (%)", 50, 100, 95) / 100
capex_kw = st.sidebar.number_input("CAPEX (€/kW)", value=600)
opex_kw = st.sidebar.number_input("OPEX anual (€/kW)", value=15)
coste_mwh = st.sidebar.number_input("Coste operación (€/MWh cargado)", value=0.0)
tasa_descuento = st.sidebar.number_input("Tasa de descuento (%)", min_value=0.0, max_value=20.0, value=7.0)

if st.sidebar.button("▶️ Ejecutar simulación"):
    precios = cargar_datos(zona)
    resultado_df, ingresos = simular(precios, potencia_mw, duracion_h, ef_carga, ef_descarga)

    st.subheader("📊 Parámetros seleccionados")
    st.markdown(f"""
    - **Zona**: {zona}  
    - **Potencia**: {potencia_mw} MW  
    - **Duración**: {duracion_h} h  
    - **Eficiencias**: carga {ef_carga*100:.0f}%, descarga {ef_descarga*100:.0f}%  
    - **CAPEX**: {capex_kw} €/kW  
    - **OPEX anual**: {opex_kw} €/kW  
    - **Coste variable**: {coste_mwh} €/MWh  
    - **Tasa de descuento**: {tasa_descuento:.1f}%
    """)

    st.subheader("📈 Resultados horarios")
    st.dataframe(resultado_df.head(100), use_container_width=True)

    # CSV download
    csv = resultado_df.to_csv(index=False).encode("utf-8")
    st.download_button("📥 Descargar resultados horarios (CSV)", data=csv, file_name="resultados_bess.csv", mime="text/csv")

    st.subheader("📉 Resultados económicos")
    ingreso_anual = sum(ingresos)
    inversion = -potencia_mw * 1000 * capex_kw
    flujo_caja = [inversion] + [ingreso_anual - potencia_mw * 1000 * opex_kw] * 15
    van = npf.npv(tasa_descuento/100, flujo_caja)
    tir = npf.irr(flujo_caja)

    st.markdown(f"""
    - **Ingreso anual estimado**: {ingreso_anual:,.0f} €  
    - **Inversión inicial**: {inversion:,.0f} €  
    - **VAN (15 años)**: {van:,.0f} €  
    - **TIR estimada**: {tir*100:.2f} %
    """)
