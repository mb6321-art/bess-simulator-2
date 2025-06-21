import numpy as np
import streamlit as st
import matplotlib.pyplot as plt

def calcular_estudio_financiero(resumen_diario, potencia, duracion, opex, precio_energia, tasa_descuento):
    ingresos_anuales = resumen_diario["Beneficio Diario"].sum() * 365 / len(resumen_diario)
    opex_total = potencia * 1000 * opex
    flujo_caja = [-potencia * duracion * 400]  # inversión inicial a 400€/kWh
    for i in range(15):
        neto = ingresos_anuales - opex_total
        flujo_caja.append(neto)

    van = np.npv(tasa_descuento / 100, flujo_caja)
    tir = np.irr(flujo_caja)

    st.markdown(f"**VAN (15 años):** {van:,.0f} €")
    st.markdown(f"**TIR:** {tir*100:.2f} %")

    fig, ax = plt.subplots()
    ax.bar(range(16), flujo_caja)
    ax.set_xlabel("Año")
    ax.set_ylabel("Flujo de caja (€)")
    ax.set_title("Flujos de caja anuales")
    st.pyplot(fig)
