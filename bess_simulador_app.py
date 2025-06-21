import streamlit as st
import pandas as pd
import numpy as np
import numpy_financial as npf
import matplotlib.pyplot as plt

st.set_page_config(page_title="Simulador de BESS - Naturgy", layout="wide")
st.title("🔋 Simulador de BESS - Naturgy")

# --- CARGA DE DATOS ---
@st.cache_data
def cargar_datos(opcion):
    if opcion == "Desde Excel":
        try:
            df = pd.read_excel("precios_estimados_2024.xlsx")
            df["Fecha"] = pd.to_datetime(df["Fecha"])
            return df
        except Exception as e:
            st.error(f"Error al cargar Excel: {e}")
            return None
    else:
        st.warning("No se pudieron descargar los datos reales de OMIE. Usando datos simulados.")
        return pd.read_excel("precios_estimados_2024.xlsx")

origen_datos = st.sidebar.radio("Origen de datos", ["Desde Excel", "OMIE (simulado)"])
precios = cargar_datos(origen_datos)

if precios is not None:
    zona_list = [c for c in precios.columns if c not in ["Fecha", "Hora"]]
    st.sidebar.header("⚙️ Parámetros del sistema")
    zona = st.sidebar.selectbox("Zona de operación", zona_list)
    potencia_mw = st.sidebar.number_input("Potencia [MW]", min_value=1.0, value=10.0)
    duracion_h = st.sidebar.number_input("Duración [h]", min_value=0.5, value=2.0)
    ef_carga = st.sidebar.slider("Eficiencia carga [%]", 50, 100, 95)
    ef_descarga = st.sidebar.slider("Eficiencia descarga [%]", 50, 100, 95)
    ciclos_dia = st.sidebar.slider("Máx. ciclos por día", 1, 5, 1)
    coste_opex = st.sidebar.number_input("Coste OPEX [€/kW/año]", value=15.0)
    financiacion = st.sidebar.slider("Financiación del proyecto [%]", 0, 100, 70)

    def simular(precios, zona, potencia, duracion, ef_in, ef_out):
        df = precios[["Fecha", "Hora", zona]].copy()
        df = df.rename(columns={zona: "Precio"})
        df["Día"] = df["Fecha"].dt.date
        df["Carga"] = 0.0
        df["Descarga"] = 0.0
        df["Estado"] = ""

        energia = potencia * duracion
        resultados = []

        for dia, grupo in df.groupby("Día"):
            g = grupo.sort_values("Precio")
            cargas = g.head(int(duracion)).copy()
            cargas["Carga"] = energia / duracion
            cargas["Estado"] = "Carga"

            g2 = grupo.sort_values("Precio", ascending=False)
            descargas = g2.head(int(duracion)).copy()
            descargas["Descarga"] = energia * (ef_in/100) * (ef_out/100) / duracion
            descargas["Estado"] = "Descarga"

            resultado_dia = grupo.copy()
            resultado_dia.update(cargas.set_index("Fecha"))
            resultado_dia.update(descargas.set_index("Fecha"))
            resultados.append(resultado_dia)

        df_final = pd.concat(resultados).sort_values("Fecha")
        df_final["Ingresos"] = df_final["Descarga"] * df_final["Precio"]
        df_final["Costes"] = df_final["Carga"] * df_final["Precio"]
        df_final["Beneficio"] = df_final["Ingresos"] - df_final["Costes"]

        return df_final

    if st.sidebar.button("▶️ Ejecutar simulación"):
        resultado = simular(precios, zona, potencia_mw, duracion_h, ef_carga, ef_descarga)

        st.subheader("📊 Parámetros seleccionados")
        st.markdown(f"""**Zona:** {zona}  
**Potencia:** {potencia_mw} MW  
**Duración:** {duracion_h} h  
**Eficiencias:** carga {ef_carga}%, descarga {ef_descarga}%  
**OPEX anual:** {coste_opex} €/kW""")

        st.subheader("📈 Resultados anuales")
        ingresos = resultado["Ingresos"].sum()
        costes = resultado["Costes"].sum()
        beneficio = ingresos - costes - potencia_mw * 1000 * coste_opex
        capex = potencia_mw * duracion_h * 400
        st.metric("Ingresos [€]", f"{ingresos:,.0f}")
        st.metric("Costes [€]", f"{costes:,.0f}")
        st.metric("Beneficio neto [€]", f"{beneficio:,.0f}")

        st.subheader("📅 Análisis horario")
        fecha_sel = st.date_input("Selecciona un día", value=resultado["Fecha"].dt.date.min())
        df_dia = resultado[resultado["Fecha"].dt.date == fecha_sel]

        fig, ax1 = plt.subplots(figsize=(12, 4))
        ax1.plot(df_dia["Hora"], df_dia["Precio"], color="gray", label="Precio [€/MWh]")
        ax1.set_ylabel("Precio [€/MWh]", color="gray")
        ax2 = ax1.twinx()
        ax2.bar(df_dia["Hora"], df_dia["Carga"], width=0.4, color="green", label="Carga")
        ax2.bar(df_dia["Hora"] + 0.4, df_dia["Descarga"], width=0.4, color="red", label="Descarga")
        ax2.set_ylabel("Energía [MWh]")
        fig.legend(loc="upper right")
        st.pyplot(fig)

        st.dataframe(df_dia[["Fecha", "Precio", "Carga", "Descarga", "Ingresos", "Costes", "Beneficio"]].round(2))

        st.subheader("📉 Flujo de caja y rentabilidades")
        flujo_caja = [-capex] + [beneficio] * 15
        tir_proyecto = npf.irr(flujo_caja)

        equity = capex * (1 - financiacion / 100)
        flujo_equity = [-equity] + [beneficio] * 15
        tir_equity = npf.irr(flujo_equity)

        st.metric("TIR Proyecto [%]", f"{tir_proyecto*100:.2f}")
        st.metric("TIR Equity [%]", f"{tir_equity*100:.2f}")

        st.line_chart(pd.Series(flujo_caja, name="Flujo de Caja", index=range(16)))

# Si no hay datos, mostrar mensaje de error
else:
    st.error("No se pudo cargar ningún conjunto de datos.")