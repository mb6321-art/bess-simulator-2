import streamlit as st
import pandas as pd
import numpy as np
import numpy_financial as npf
import plotly.express as px
import os


def reset_sidebar():
    """Clear session state and reload the app."""
    for k in list(st.session_state.keys()):
        del st.session_state[k]
    st.experimental_rerun()

TECHS = {
    "Li-ion LFP": {"costo": (220, 240), "ciclos": (6000, 8000)},
    "Li-ion NMC": {"costo": (250, 280), "ciclos": (3000, 4000)},
    "Sodio-ion (Na-ion)": {"costo": (280, 320), "ciclos": (4000, 5000)},
}

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
        path = "Precios_Mercado_Italiano_2024.xlsx"
        if not os.path.exists(path):
            alt_path = "data/precios_italia.xlsx"
            if os.path.exists(alt_path):
                path = alt_path
            else:
                st.error(f"Archivo predeterminado no encontrado: {path}")
                st.stop()
        df = pd.read_excel(path, sheet_name=zona)
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
    tecnologia = st.selectbox("Tecnología", list(TECHS.keys()))
    cap_min, cap_max = TECHS[tecnologia]["costo"]
    cyc_min, cyc_max = TECHS[tecnologia]["ciclos"]
    capex_kw = st.slider(
        "CAPEX (€/kW)",
        min_value=cap_min,
        max_value=cap_max,
        value=(cap_min + cap_max) // 2,
    )
    st.caption(f"Vida útil estimada: {cyc_min:,}-{cyc_max:,} ciclos")
    potencia_mw = st.slider("Potencia (MW)", 1, 100, 10)
    duracion_h = st.slider("Duración (h)", 1, 10, 4)
    ef_carga = st.slider("Eficiencia de carga (%)", 50, 100, 95) / 100
    ef_descarga = st.slider("Eficiencia de descarga (%)", 50, 100, 95) / 100

    estrategia = st.selectbox("Estrategia",
                              ["Percentiles", "Margen fijo", "Programada"])
    umbral_carga = st.slider("Umbral de carga", 0.0, 1.0, 0.25, 0.05)
    umbral_descarga = st.slider("Umbral de descarga", 0.0, 1.0, 0.75, 0.05)
    st.caption(
        "La batería se carga cuando el precio está por debajo del percentil "
        "seleccionado en 'Umbral de carga' y se descarga cuando supera el "
        "percentil indicado en 'Umbral de descarga'."
    )
    margen = st.number_input("Margen (€/MWh)", value=10.0)
    opex_kw = st.number_input("OPEX anual (€/kW)", value=15)
    coste_mwh = st.number_input("Coste operación (€/MWh cargado)", value=0.0)
    tasa_descuento = st.number_input("Tasa de descuento (%)", 0.0, 20.0, 7.0)

    iniciar = st.button("▶️ Ejecutar simulación")
    if st.button("Restablecer parámetros"):
        reset_sidebar()

    with st.expander("Ayuda"):
        st.markdown(
            """
            1. Ajusta los parámetros y pulsa **Ejecutar simulación**.
            2. Usa **Restablecer parámetros** para volver a los valores por defecto.
            3. En las pestañas de la derecha encontrarás los datos, las gráficas y
               los indicadores económicos.
            """
        )

if iniciar:
    precios = cargar_datos(zona, archivo)
    fecha_inicio = st.date_input("Desde", precios["Fecha"].min())
    fecha_fin = st.date_input("Hasta", precios["Fecha"].max())
    fecha_inicio = pd.to_datetime(fecha_inicio)
    fecha_fin = pd.to_datetime(fecha_fin)
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

    mensual = resumen_mensual(resultado)

    tab_res, tab_graf, tab_ind = st.tabs(["Resultados", "Gráficas", "Indicadores"])

    with tab_res:
        st.subheader("📈 Resultados horarios")
        st.dataframe(resultado.head(100), use_container_width=True)
        st.subheader("📅 Resumen mensual")
        st.dataframe(mensual, use_container_width=True)
        csv = resultado.to_csv(index=False).encode("utf-8")
        st.download_button("Descargar resultados (CSV)", csv, "resultados_bess.csv")
        csv_m = mensual.to_csv().encode("utf-8")
        st.download_button("Descargar resumen mensual (CSV)", csv_m, "resumen_mensual.csv")

    with tab_graf:
        fig = px.line(resultado, x="Fecha", y=["Precio", "SOC (MWh)"], title="Precio y Estado de Carga")
        st.plotly_chart(fig, use_container_width=True)
        fig_b = px.bar(mensual.reset_index(), x="Mes", y="Beneficio (€)", title="Beneficio mensual")
        st.plotly_chart(fig_b, use_container_width=True)
        cash = -potencia_mw * 1000 * capex_kw + resultado["Beneficio (€)"].cumsum()
        fig_cash = px.line(x=resultado["Fecha"], y=cash, labels={"x": "Fecha", "y": "€"}, title="Flujo de caja acumulado")
        st.plotly_chart(fig_cash, use_container_width=True)

    ingreso_anual = resultado["Beneficio (€)"].sum()
    inversion = -potencia_mw * 1000 * capex_kw
    flujo_caja = [inversion] + [ingreso_anual - potencia_mw * 1000 * opex_kw] * 15
    van = npf.npv(tasa_descuento / 100, flujo_caja)
    tir = npf.irr(flujo_caja)

    total_descarga = resultado["Descarga (MWh)"].sum()
    ciclos_periodo = total_descarga / (potencia_mw * duracion_h)
    dias_periodo = (fecha_fin - fecha_inicio).days + 1
    ciclos_anuales = ciclos_periodo / (dias_periodo / 365)

    with tab_ind:
        st.subheader("📊 Indicadores económicos")
        st.markdown(f"""
        - **Ingreso anual estimado**: {ingreso_anual:,.0f} €
        - **Inversión inicial**: {inversion:,.0f} €
        - **VAN (15 años)**: {van:,.0f} €
        - **TIR estimada**: {tir*100:.2f} %
        - **Ciclos usados al año**: {ciclos_anuales:.1f} (vida útil {cyc_min}-{cyc_max} ciclos)
        """)

else:
    st.info("Configura los parámetros en la barra lateral y pulsa Ejecutar.")
