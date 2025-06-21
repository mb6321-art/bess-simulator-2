
import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import numpy_financial as npf

st.set_page_config(page_title="Simulador de BESS - Naturgy", layout="wide")

st.sidebar.image("https://upload.wikimedia.org/wikipedia/commons/thumb/5/51/Logo_Naturgy.svg/2560px-Logo_Naturgy.svg.png", width=150)
st.title("🔋 Simulador de BESS - Naturgy")

@st.cache_data
def cargar_datos_excel():
    return pd.read_excel("precios_estimados_2024.xlsx", parse_dates=["Fecha"])

# Selección fuente de datos
fuente = st.sidebar.radio("📊 Fuente de datos", ["Excel local (2024)", "Datos reales OMIE (simulado)"])

# Carga de datos
zonas = []
try:
    if fuente == "Excel local (2024)":
        precios = cargar_datos_excel()
    else:
        raise Exception("Datos reales no disponibles actualmente.")
    zonas = [c for c in precios.columns if c not in ["Fecha", "Hora"]]
except Exception as exc:
    st.error(f"No se pudieron cargar los datos: {exc}")
    st.stop()

# Parámetros
st.sidebar.header("⚙️ Parámetros del sistema")
zona = st.sidebar.selectbox("Zona de operación", zonas)
potencia_mw = st.sidebar.number_input("Potencia [MW]", min_value=1.0, value=10.0)
duracion_h = st.sidebar.number_input("Duración [h]", min_value=0.5, value=2.0)
ef_carga = st.sidebar.slider("Eficiencia carga [%]", 50, 100, 95)
ef_descarga = st.sidebar.slider("Eficiencia descarga [%]", 50, 100, 95)
ciclos_dia = st.sidebar.slider("Máx. ciclos por día", 1, 5, 1)
coste_mantenimiento = st.sidebar.number_input("Coste OPEX [€/kW/año]", value=15.0)
porcentaje_deuda = st.sidebar.slider("Financiación vía deuda [%]", 0, 100, 50)

# Simulación
def simular(precios, zona, potencia, duracion, ef_in, ef_out):
    df = precios[["Fecha", "Hora", zona]].copy()
    df = df.rename(columns={zona: "Precio"})
    df["Día"] = df["Fecha"].dt.date
    df["Carga"] = 0.0
    df["Descarga"] = 0.0

    energia = potencia * duracion
    df_resultados = []

    for dia, grupo in df.groupby("Día"):
        g = grupo.sort_values("Precio")
        cargas = g.head(int(duracion)).copy()
        cargas["Carga"] = energia / duracion

        g2 = grupo.sort_values("Precio", ascending=False)
        descargas = g2.head(int(duracion)).copy()
        descargas["Descarga"] = energia * (ef_in/100) * (ef_out/100) / duracion

        resultado_dia = grupo.copy()
        resultado_dia.loc[cargas.index, "Carga"] = cargas["Carga"]
        resultado_dia.loc[descargas.index, "Descarga"] = descargas["Descarga"]

        df_resultados.append(resultado_dia)

    df_final = pd.concat(df_resultados).sort_values(["Fecha", "Hora"])
    df_final["Ingresos"] = df_final["Descarga"] * df_final["Precio"]
    df_final["Costes"] = df_final["Carga"] * df_final["Precio"]
    df_final["Beneficio"] = df_final["Ingresos"] - df_final["Costes"]
    df_final["Estado de carga"] = (df_final["Carga"].cumsum() - df_final["Descarga"].cumsum()).clip(lower=0)

    return df_final

if st.sidebar.button("▶️ Ejecutar simulación"):
    resultado = simular(precios, zona, potencia_mw, duracion_h, ef_carga, ef_descarga)

    st.subheader("📊 Parámetros seleccionados")
    st.markdown(f"**Zona:** {zona}")
    st.markdown(f"**Potencia:** {potencia_mw} MW")
    st.markdown(f"**Duración:** {duracion_h} h")
    st.markdown(f"**Eficiencias:** carga {ef_carga}%, descarga {ef_descarga}%")
    st.markdown(f"**OPEX anual:** {coste_mantenimiento} €/kW")

    st.subheader("📈 Resultados anuales")
    total_ingresos = resultado["Ingresos"].sum()
    total_costes = resultado["Costes"].sum()
    total_beneficio = resultado["Beneficio"].sum()
    capex = potencia_mw * duracion_h * 400
    opex_total = potencia_mw * 1000 * coste_mantenimiento

    st.metric("Ingresos [€]", f"{total_ingresos:,.0f}")
    st.metric("Costes [€]", f"{total_costes:,.0f}")
    st.metric("Beneficio neto [€]", f"{total_beneficio - opex_total:,.0f}")

    st.subheader("📅 Análisis horario")
    fecha_sel = st.date_input("Selecciona un día", value=resultado["Fecha"].dt.date.min())
    df_dia = resultado[resultado["Fecha"].dt.date == fecha_sel]

    fig, ax1 = plt.subplots(figsize=(12, 4))
    ax1.plot(df_dia["Hora"], df_dia["Precio"], color="gray", label="Precio [€/MWh]")
    ax1.set_ylabel("Precio [€/MWh]", color="gray")

    ax2 = ax1.twinx()
    ax2.bar(df_dia["Hora"], df_dia["Carga"], width=0.4, color="green", label="Carga")
    ax2.bar(df_dia["Hora"] + 0.4, df_dia["Descarga"], width=0.4, color="red", label="Descarga")
    ax2.plot(df_dia["Hora"], df_dia["Estado de carga"], color="blue", label="SOC", linestyle="--")
    ax2.set_ylabel("Energía [MWh]")

    fig.legend(loc="upper right")
    st.pyplot(fig)

    st.dataframe(df_dia[["Fecha", "Precio", "Carga", "Descarga", "Estado de carga", "Ingresos", "Costes", "Beneficio"]].round(2))

    st.subheader("💰 Análisis financiero a 15 años")
    flujo_caja = [-capex] + [total_beneficio - opex_total] * 15
    tir_proyecto = npf.irr(flujo_caja)
    deuda = capex * (porcentaje_deuda / 100)
    equity = capex - deuda
    flujo_equity = [-equity] + [total_beneficio - opex_total - deuda * 0.07] * 15
    tir_equity = npf.irr(flujo_equity)

    st.markdown(f"**TIR Proyecto:** {tir_proyecto*100:.2f}%")
    st.markdown(f"**TIR Equity (deuda al {porcentaje_deuda}%):** {tir_equity*100:.2f}%")

    st.line_chart(pd.Series(flujo_caja, name="Flujo de caja anual"))
