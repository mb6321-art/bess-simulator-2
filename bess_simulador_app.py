import streamlit as st
from financial_module import calcular_estudio_financiero
from utils import cargar_datos, simular_bateria, mostrar_parametros, exportar_pdf

st.set_page_config(page_title="Simulador de BESS - Naturgy", layout="wide")

st.image("assets/naturgy_logo.png", width=180)
st.title("Simulador de BESS - Naturgy")

# Selección de escenario
escenario = st.sidebar.selectbox("Escenario", ["Merchant 100%"])

# Parámetros generales
zona, potencia, duracion, ef_carga, ef_descarga, opex, precio_energia, tasa_descuento = mostrar_parametros()

# Botón para ejecutar simulación
if st.sidebar.button("▶️ Ejecutar simulación"):
    precios = cargar_datos("data/precios_simulados.xlsx", zona)
    resultado, resumen_diario = simular_bateria(precios, potencia, duracion, ef_carga, ef_descarga)

    st.subheader("📊 Parámetros seleccionados")
    st.markdown(
        f"**Zona:** {zona}  
"
        f"**Potencia:** {potencia} MW  
"
        f"**Duración:** {duracion} h  
"
        f"**Eficiencias:** carga {ef_carga}%, descarga {ef_descarga}%  
"
        f"**OPEX anual:** {opex} €/kW  
"
        f"**Precio energía:** {precio_energia} €/MWh  
"
        f"**Tasa de descuento:** {tasa_descuento} %"
    )

    st.subheader("🔋 Análisis diario del sistema")
    dia = st.selectbox("Seleccionar día:", sorted(resultado["Fecha"].dt.date.unique()))
    exportar_pdf(resultado, dia)

    st.subheader("📈 Estudio financiero")
    calcular_estudio_financiero(resumen_diario, potencia, duracion, opex, precio_energia, tasa_descuento)
