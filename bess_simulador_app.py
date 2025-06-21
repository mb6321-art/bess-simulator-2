
import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import numpy_financial as npf

st.set_page_config(page_title="Simulador de BESS - Naturgy", layout="wide")

# --- LOGO Y TÍTULO ---
col1, col2 = st.columns([6, 1])
with col1:
    st.title("Simulador de BESS - Naturgy")
with col2:
    st.image("https://upload.wikimedia.org/wikipedia/commons/thumb/2/29/Naturgy_logo.svg/2560px-Naturgy_logo.svg.png", width=120)

# --- PARÁMETROS ---
st.sidebar.header("⚙️ Parámetros del sistema")
escenario = st.sidebar.selectbox("Escenario", ["Merchant 100%"])
zona = st.sidebar.selectbox("Zona de operación", ["NORTE", "CENTRO", "SUR"])
potencia_mw = st.sidebar.number_input("Potencia [MW]", min_value=1.0, value=10.0)
duracion_h = st.sidebar.number_input("Duración [h]", min_value=0.5, value=2.0)
ef_carga = st.sidebar.slider("Eficiencia carga [%]", 50, 100, 95)
ef_descarga = st.sidebar.slider("Eficiencia descarga [%]", 50, 100, 95)
ciclos_dia = st.sidebar.slider("Máx. ciclos por día", 1, 5, 1)
coste_mantenimiento = st.sidebar.number_input("Coste OPEX [€/kW/año]", value=15.0)
tasa_descuento = st.sidebar.number_input("Tasa de descuento [%]", value=7.0)
financiacion_pct = st.sidebar.slider("Financiación (% sobre CAPEX)", 0, 100, 70)

@st.cache_data
def cargar_datos():
    df = pd.read_excel("precios_italia_2024.xlsx")
    df["Fecha"] = pd.to_datetime(df["Fecha"])
    return df

precios = cargar_datos()

def simular(precios, zona, potencia, duracion, ef_in, ef_out):
    df = precios[["Fecha", "Hora", zona]].copy()
    df = df.rename(columns={zona: "Precio"})
    df["Día"] = df["Fecha"].dt.date
    df["Carga"] = 0.0
    df["Descarga"] = 0.0
    df["SOC"] = 0.0

    energia = potencia * duracion
    df_resultados = []

    for dia, grupo in df.groupby("Día"):
        grupo = grupo.copy().sort_values("Hora")
        grupo["SOC"] = 0.0
        carga_horas = grupo.nsmallest(int(duracion), "Precio").copy()
        descarga_horas = grupo.nlargest(int(duracion), "Precio").copy()

        grupo.loc[carga_horas.index, "Carga"] = energia / duracion
        grupo.loc[descarga_horas.index, "Descarga"] = energia * (ef_in/100) * (ef_out/100) / duracion

        grupo["SOC"] = np.cumsum(grupo["Carga"] - grupo["Descarga"])
        df_resultados.append(grupo)

    df_final = pd.concat(df_resultados)
    df_final["Ingresos"] = df_final["Descarga"] * df_final["Precio"]
    df_final["Costes"] = df_final["Carga"] * df_final["Precio"]
    df_final["Beneficio"] = df_final["Ingresos"] - df_final["Costes"]

    return df_final

if st.button("▶️ Ejecutar simulación"):
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
    capex = potencia_mw * duracion_h * 400  # €/kWh
    opex_total = potencia_mw * 1000 * coste_mantenimiento

    st.metric("Ingresos [€]", f"{total_ingresos:,.0f}")
    st.metric("Costes [€]", f"{total_costes:,.0f}")
    st.metric("Beneficio neto [€]", f"{total_beneficio - opex_total:,.0f}")

    st.subheader("💰 Análisis financiero")
    flujo_caja = [-capex] + [total_beneficio - opex_total] * 15
    tir_proyecto = npf.irr(flujo_caja) * 100
    van = npf.npv(tasa_descuento/100, flujo_caja)
    equity = capex * (1 - financiacion_pct / 100)
    flujo_equity = [-equity] + [total_beneficio - opex_total - (capex * financiacion_pct / 100 * 0.05)] * 15
    tir_equity = npf.irr(flujo_equity) * 100

    st.markdown(f"**TIR del Proyecto:** {tir_proyecto:.2f} %")
    st.markdown(f"**TIR del Equity:** {tir_equity:.2f} %")
    st.markdown(f"**VAN:** €{van:,.0f}")

    st.subheader("📅 Análisis horario")
    fecha_sel = st.date_input("Selecciona un día", value=resultado["Fecha"].dt.date.min())
    df_dia = resultado[resultado["Fecha"].dt.date == fecha_sel]

    fig, ax1 = plt.subplots(figsize=(12, 5))
    ax1.plot(df_dia["Hora"], df_dia["Precio"], color="black", label="Precio [€/MWh]")
    ax1.set_ylabel("Precio [€/MWh]", color="black")
    ax2 = ax1.twinx()
    ax2.bar(df_dia["Hora"], df_dia["Carga"], width=0.4, color="green", label="Carga")
    ax2.bar(df_dia["Hora"] + 0.4, df_dia["Descarga"], width=0.4, color="red", label="Descarga")
    ax2.plot(df_dia["Hora"], df_dia["SOC"], color="blue", linestyle="--", label="SOC")
    ax2.set_ylabel("Energía [MWh]")
    fig.legend(loc="upper right")
    st.pyplot(fig)
