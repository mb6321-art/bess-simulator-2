import streamlit as st
import pandas as pd
import numpy as np
import numpy_financial as npf
import plotly.express as px

st.set_page_config(page_title="Simulador de BESS", layout="wide")

# --- Cargar datos ---
@st.cache_data
def cargar_datos(zona, archivo=None):
    if archivo is not None:
        if archivo.name.endswith(".csv"):
            df = pd.read_csv(archivo)
        else:
            df = pd.read_excel(archivo)
    else:
        df = pd.read_excel("data/precios_italia_2024.xlsx", sheet_name=zona)
    df["Fecha"] = pd.to_datetime(df["Fecha"])
    return df

# --- Simulación ---
def simular(precios, potencia_mw, duracion_h, ef_carga, ef_descarga,
            estrategia, umbral_carga=0.25, umbral_descarga=0.75,
            margen=0, horario=None):
    energia_mwh = potencia_mw * duracion_h
    capacidad_actual = 0
    resultados = []

    p_inf = precios["Precio"].quantile(umbral_carga)
    p_sup = precios["Precio"].quantile(umbral_descarga)
    media = precios["Precio"].mean()

    for _, row in precios.iterrows():
        precio = row["Precio"]
        estado = "Reposo"
        carga = descarga = ingreso = 0

        if estrategia == "Percentiles":
            if precio < p_inf and capacidad_actual < energia_mwh:
                carga = potencia_mw * ef_carga
                capacidad_actual += carga
                estado = "Carga"
                ingreso = -precio * carga
            elif precio > p_sup and capacidad_actual > 0:
                descarga = min(potencia_mw * ef_descarga, capacidad_actual)
                capacidad_actual -= descarga
                estado = "Descarga"
                ingreso = precio * descarga

        elif estrategia == "Margen fijo":
            if precio < media - margen and capacidad_actual < energia_mwh:
                carga = potencia_mw * ef_carga
                capacidad_actual += carga
                estado = "Carga"
                ingreso = -precio * carga
            elif precio > media + margen and capacidad_actual > 0:
                descarga = min(potencia_mw * ef_descarga, capacidad_actual)
                capacidad_actual -= descarga
                estado = "Descarga"
                ingreso = precio * descarga

        elif estrategia == "Programada" and horario is not None:
            accion = horario.get(row["Fecha"].hour)
            if accion == "C" and capacidad_actual < energia_mwh:
                carga = potencia_mw * ef_carga
                capacidad_actual += carga
                estado = "Carga"
                ingreso = -precio * carga
            elif accion == "D" and capacidad_actual > 0:
                descarga = min(potencia_mw * ef_descarga, capacidad_actual)
                capacidad_actual -= descarga
                estado = "Descarga"
                ingreso = precio * descarga

        resultados.append({
            "Fecha": row["Fecha"],
            "Precio": precio,
            "Carga (MWh)": carga,
            "Descarga (MWh)": descarga,
            "SOC (MWh)": capacidad_actual,
            "Estado": estado,
            "Beneficio (€)": ingreso
        })

    return pd.DataFrame(resultados)

def resumen_mensual(df):
    return (
        df.resample("M", on="Fecha")
          .agg({"Carga (MWh)": "sum",
                "Descarga (MWh)": "sum",
                "Beneficio (€)": "sum"})
          .rename_axis("Mes")
    )

# --- Interfaz ---
st.title("🔋 Simulador de BESS")

with st.sidebar:
    st.header("🔧 Parámetros de simulación")
    archivo = st.file_uploader("Archivo de precios", type=["xlsx", "csv"])
    zona = st.selectbox(
        "Zona",
        ["NORD", "CNORD", "CSUD", "SUD", "SARD", "SICILY", "BZ"],
    )
    potencia_mw = st.slider("Potencia (MW)", 1, 100, 10)
    duracion_h = st.slider("Duración (h)", 1, 10, 4)
    ef_carga = st.slider("Eficiencia de carga (%)", 50, 100, 95) / 100
    ef_descarga = st.slider("Eficiencia de descarga (%)", 50, 100, 95) / 100

    estrategia = st.selectbox("Estrategia",
                              ["Percentiles", "Margen fijo", "Programada"])
    umbral_carga = st.slider("Umbral de carga", 0.0, 1.0, 0.25, 0.05)
    umbral_descarga = st.slider("Umbral de descarga", 0.0, 1.0, 0.75, 0.05)
    margen = st.number_input("Margen (€/MWh)", value=10.0)

    capex_kw = st.number_input("CAPEX (€/kW)", value=600)
    opex_kw = st.number_input("OPEX anual (€/kW)", value=15)
    coste_mwh = st.number_input("Coste operación (€/MWh cargado)", value=0.0)
    tasa_descuento = st.number_input("Tasa de descuento (%)", 0.0, 20.0, 7.0)

    iniciar = st.button("▶️ Ejecutar simulación")

if iniciar:
    precios = cargar_datos(zona, archivo)
    fecha_inicio = st.date_input("Desde", precios["Fecha"].min())
    fecha_fin = st.date_input("Hasta", precios["Fecha"].max())
    precios = precios[(precios["Fecha"] >= fecha_inicio) &
                      (precios["Fecha"] <= fecha_fin)]

    horario = None
    if estrategia == "Programada":
        horario_file = st.file_uploader(
            "Horario (CSV con columnas hora,accion)", type="csv")
        if horario_file is not None:
            df_hor = pd.read_csv(horario_file)
            horario = {row["hora"]: row["accion"] for _, row in df_hor.iterrows()}

    resultado = simular(precios, potencia_mw, duracion_h,
                        ef_carga, ef_descarga, estrategia,
                        umbral_carga, umbral_descarga, margen, horario)

    st.subheader("📈 Resultados horarios")
    st.dataframe(resultado.head(100), use_container_width=True)
    fig = px.line(resultado, x="Fecha", y=["Precio", "SOC (MWh)"],
                  title="Precio y Estado de Carga")
    st.plotly_chart(fig, use_container_width=True)

    mensual = resumen_mensual(resultado)
    st.subheader("📅 Resumen mensual")
    st.dataframe(mensual, use_container_width=True)

    csv = resultado.to_csv(index=False).encode("utf-8")
    st.download_button("Descargar resultados (CSV)", csv, "resultados_bess.csv")
    csv_m = mensual.to_csv().encode("utf-8")
    st.download_button("Descargar resumen mensual (CSV)",
                       csv_m, "resumen_mensual.csv")

    ingreso_anual = resultado["Beneficio (€)"].sum()
    inversion = -potencia_mw * 1000 * capex_kw
    flujo_caja = [inversion] + \
        [ingreso_anual - potencia_mw * 1000 * opex_kw] * 15
    van = npf.npv(tasa_descuento / 100, flujo_caja)
    tir = npf.irr(flujo_caja)

    st.subheader("📊 Indicadores económicos")
    st.markdown(f"""
    - **Ingreso anual estimado**: {ingreso_anual:,.0f} €
    - **Inversión inicial**: {inversion:,.0f} €
    - **VAN (15 años)**: {van:,.0f} €
    - **TIR estimada**: {tir*100:.2f} %
    """)
else:
    st.info("Configura los parámetros en la barra lateral y pulsa Ejecutar.")
