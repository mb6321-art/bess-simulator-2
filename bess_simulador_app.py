
# Simulador interactivo BESS - Merchant Model (Streamlit)
import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

st.set_page_config(layout="wide")
st.title("🔋 Simulador BESS - Merchant (Italia 2024)")

# ---- Sidebar parámetros ----
st.sidebar.header("Configuración del sistema")
zonas = ["NORD", "CNOR", "CSUD", "SUD", "CALA", "SICI", "SARD"]
zona = st.sidebar.selectbox("Zona", zonas)
potencia = st.sidebar.number_input("Potencia (MW)", value=50, min_value=1)
duracion = st.sidebar.slider("Duración (horas)", 1, 6, 4)
eficiencia = st.sidebar.slider("Eficiencia (%)", 50, 100, 90) / 100
ciclos_dia = st.sidebar.slider("Ciclos por día", 1, 2, 1)

energia_mwh = potencia * duracion

# ---- Datos horarios (simulados por ahora) ----
@st.cache_data
def cargar_precios():
    df = pd.read_excel("precios_estimados_2024.xlsx")
    df["Precio"] = df[zona]
    df["Dia"] = df["Fecha"].dt.date
    return df

df = cargar_precios()

# ---- Simulación merchant ----
df["Operación"] = "Reposo"
df["Energía (MWh)"] = 0.0
df["Ingreso (€)"] = 0.0

for dia, grupo in df.groupby("Dia"):
    grupo = grupo.sort_values("Precio")
    carga = grupo.head(duracion)
    descarga = grupo.tail(duracion)

    df.loc[carga.index, "Operación"] = "Carga"
    df.loc[carga.index, "Energía (MWh)"] = energia_mwh
    df.loc[carga.index, "Ingreso (€)"] = -energia_mwh * carga["Precio"]

    energia_descargada = energia_mwh * eficiencia
    df.loc[descarga.index, "Operación"] = "Descarga"
    df.loc[descarga.index, "Energía (MWh)"] = energia_descargada
    df.loc[descarga.index, "Ingreso (€)"] = energia_descargada * descarga["Precio"]

# ---- KPIs ----
ingresos_totales = df["Ingreso (€)"].sum()
capex = energia_mwh * 1000 * 240
opex = potencia * 7000
flujo = ingresos_totales - opex
payback = capex / flujo if flujo > 0 else None
irr = (flujo / capex) * 100

st.subheader("Resultados Anuales")
kpis = {
    "Ingresos anuales (€)": ingresos_totales,
    "CAPEX total (€)": capex,
    "OPEX anual (€)": opex,
    "Flujo neto (€)": flujo,
    "Payback (años)": round(payback, 2) if payback else "-",
    "IRR estimada (%)": round(irr, 2)
}
st.table(pd.DataFrame(kpis.items(), columns=["Métrica", "Valor"]))

# ---- Gráfico de ingresos diarios ----
df_dia = df.groupby("Dia")["Ingreso (€)"].sum()
st.subheader("Gráfico de ingresos netos diarios")
st.line_chart(df_dia)

# ---- Análisis por día ----
st.subheader("Análisis horario de un día")
fecha_sel = st.date_input("Selecciona un día", value=pd.to_datetime("2024-07-15"))
df_dia_sel = df[df["Dia"] == fecha_sel]

fig, ax1 = plt.subplots(figsize=(10, 4))
ax1.plot(df_dia_sel["Hora"], df_dia_sel["Precio"], label="Precio €/MWh", color="black")
ax1.set_ylabel("Precio €/MWh", color="black")
ax1.set_xlabel("Hora del día")

# Colores
for _, row in df_dia_sel.iterrows():
    if row["Operación"] == "Carga":
        ax1.bar(row["Hora"], row["Energía (MWh)"], color="green", alpha=0.5)
    elif row["Operación"] == "Descarga":
        ax1.bar(row["Hora"], row["Energía (MWh)"], color="red", alpha=0.5)

st.pyplot(fig)

# Exportar
st.download_button("📥 Descargar resultados (CSV)", data=df.to_csv(index=False), file_name="resultados_BESS.csv")
