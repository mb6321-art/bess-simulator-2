import pandas as pd
import streamlit as st
import matplotlib.pyplot as plt

def cargar_datos(ruta, zona):
    df = pd.read_excel(ruta, sheet_name=zona)
    df["Fecha"] = pd.to_datetime(df["Fecha"])
    return df

def mostrar_parametros():
    zona = st.sidebar.selectbox("Zona", ["NORTE", "SUR", "ESTE", "OESTE"])
    potencia = st.sidebar.number_input("Potencia [MW]", 1.0, 100.0, 10.0, step=1.0)
    duracion = st.sidebar.number_input("Duración [h]", 1.0, 10.0, 4.0, step=1.0)
    ef_carga = st.sidebar.slider("Eficiencia carga [%]", 50, 100, 95)
    ef_descarga = st.sidebar.slider("Eficiencia descarga [%]", 50, 100, 95)
    opex = st.sidebar.number_input("OPEX anual [€/kW]", 0.0, 100.0, 15.0)
    precio_energia = st.sidebar.number_input("Precio energía vendida [€/MWh]", 0.0, 300.0, 90.0)
    tasa_descuento = st.sidebar.number_input("Tasa de descuento [%]", 0.0, 20.0, 7.0)
    return zona, potencia, duracion, ef_carga, ef_descarga, opex, precio_energia, tasa_descuento

def simular_bateria(precios, potencia, duracion, ef_carga, ef_descarga):
    energia = potencia * duracion
    precios["Hora"] = precios["Fecha"].dt.hour
    precios["SOC [%]"] = ((precios["Hora"] + 1) / 24 * 100).astype(int)
    precios["Estado"] = ["Carga" if h < 12 else "Descarga" for h in precios["Hora"]]
    precios["Beneficio Diario"] = precios["Precio"].apply(lambda p: (p - 10) * 0.8)
    resumen_diario = precios.groupby(precios["Fecha"].dt.date)["Beneficio Diario"].sum().reset_index()
    return precios, resumen_diario

def exportar_pdf(df, dia):
    st.markdown(f"**Día seleccionado:** {dia}")
    fig, ax = plt.subplots()
    sel = df[df["Fecha"].dt.date == dia]
    ax.plot(sel["Fecha"].dt.hour, sel["SOC [%]"], label="SOC [%]")
    ax.set_xlabel("Hora")
    ax.set_ylabel("SOC [%]")
    ax.set_xticks(range(0, 24))
    ax.legend()
    st.pyplot(fig)
