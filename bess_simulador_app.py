
# Simulador interactivo BESS - Merchant Model (Streamlit, versión completa)
import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime

st.set_page_config(layout="wide", page_title="Simulador BESS Merchant", page_icon="🔋")
st.title("🔋 Simulador de BESS en el mercado Merchant - Italia 2024")

# ---- Sidebar parámetros ----
st.sidebar.header("⚙️ Configuración del sistema")
zona = st.sidebar.selectbox("Zona eléctrica", ["NORD", "CNOR", "CSUD", "SUD", "CALA", "SICI", "SARD"])
potencia = st.sidebar.number_input("Potencia nominal (MW)", min_value=1, max_value=1000, value=50)
duracion = st.sidebar.slider("Duración del sistema (h)", 1, 6, 4)
ef = st.sidebar.slider("Eficiencia del sistema (%)", 50, 100, 90)
eficiencia = ef / 100
ciclos_dia = st.sidebar.slider("Ciclos por día", 1, 2, 1)
capex = st.sidebar.number_input("CAPEX (€/kWh)", min_value=100, max_value=1000, value=240)
opex = st.sidebar.number_input("OPEX anual (€/MW)", min_value=1000, max_value=20000, value=7000)
vida_util = st.sidebar.slider("Vida útil (años)", 1, 30, 15)

energia_total_mwh = potencia * duracion

# ---- Cargar datos horarios (precios simulados) ----
@st.cache_data
def cargar_datos():
    df = pd.read_excel("precios_estimados_2024.xlsx")
    df["Precio"] = df[zona]
    df["Dia"] = df["Fecha"].dt.date
    return df

df = cargar_datos()

# ---- Simulación ----
df["Operación"] = "Reposo"
df["Energía (MWh)"] = 0.0
df["Ingreso (€)"] = 0.0

for dia, grupo in df.groupby("Dia"):
    grupo_ordenado = grupo.sort_values("Precio")
    carga = grupo_ordenado.head(duracion)
    descarga = grupo_ordenado.tail(duracion)

    df.loc[carga.index, "Operación"] = "Carga"
    df.loc[carga.index, "Energía (MWh)"] = energia_total_mwh
    df.loc[carga.index, "Ingreso (€)"] = -energia_total_mwh * carga["Precio"]

    energia_descargada = energia_total_mwh * eficiencia
    df.loc[descarga.index, "Operación"] = "Descarga"
    df.loc[descarga.index, "Energía (MWh)"] = energia_descargada
    df.loc[descarga.index, "Ingreso (€)"] = energia_descargada * descarga["Precio"]

# ---- KPIs ----
ingresos_totales = df["Ingreso (€)"].sum()
capex_total = energia_total_mwh * 1000 * capex
opex_total = potencia * opex
flujo_neto = ingresos_totales - opex_total
payback = capex_total / flujo_neto if flujo_neto > 0 else None
irr = (flujo_neto / capex_total) * 100 if capex_total > 0 else 0

col1, col2 = st.columns(2)

with col1:
    st.metric("Ingresos anuales (€)", f"{ingresos_totales:,.0f}")
    st.metric("OPEX anual (€)", f"{opex_total:,.0f}")
    st.metric("Flujo neto (€)", f"{flujo_neto:,.0f}")

with col2:
    st.metric("CAPEX total (€)", f"{capex_total:,.0f}")
    st.metric("Payback (años)", f"{payback:.1f}" if payback else "-")
    st.metric("IRR estimada (%)", f"{irr:.2f}%")

# ---- Gráfico ingresos diarios ----
st.subheader("📈 Ingresos netos diarios")
df_dia = df.groupby("Dia")["Ingreso (€)"].sum()
st.line_chart(df_dia)

# ---- Análisis horario por día ----
st.subheader("🔍 Análisis horario por día")
fecha_sel = st.date_input("Selecciona un día del año", value=datetime(2024, 7, 15))
df_dia_sel = df[df["Dia"] == fecha_sel]

fig, ax = plt.subplots(figsize=(10, 4))
ax.plot(df_dia_sel["Hora"], df_dia_sel["Precio"], label="Precio €/MWh", color="black")
ax.set_ylabel("Precio €/MWh")
ax.set_xlabel("Hora")

for _, row in df_dia_sel.iterrows():
    color = "green" if row["Operación"] == "Carga" else "red" if row["Operación"] == "Descarga" else "gray"
    ax.bar(row["Hora"], row["Energía (MWh)"], color=color, alpha=0.4)

st.pyplot(fig)

# ---- Exportar ----
st.download_button("📥 Descargar resultados (CSV)", data=df.to_csv(index=False), file_name="resultados_BESS.csv")
