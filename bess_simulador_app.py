import streamlit as st
import pandas as pd
import numpy as np
import numpy_financial as npf
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import textwrap
import os
from datetime import timedelta
from dateutil.relativedelta import relativedelta

RESULT_KEYS = [
    "resultado",
    "mensual",
    "fi_date",
    "ff_date",
    "ingreso_anual",
    "inversion",
    "van",
    "tir",
    "tir_equity",
    "ciclos_anuales",
    "cyc_min",
    "cyc_max",
    "degradacion",
    "flujo_caja",
    "sens_dur",
    "horas_optimas",
    "capex_bateria",
    "coste_desarrollo",
    "flujos_anuales",
    "flujos_equity",
    "intereses_anuales",
    "amortizacion_anual",
    "sens_margen",
    "margen_optimo",
]

def reset_sidebar():
    """Clear session state and reload the app."""
    for k in list(st.session_state.keys()):
        del st.session_state[k]
    st.experimental_rerun()

TECHS = {
    "Li-ion LFP": {
        "costo": (220, 240),
        "ciclos": (6000, 10000),
        "degrad": (1.5, 2.5),
    },
    "Li-ion NMC": {
        "costo": (250, 280),
        "ciclos": (4000, 7000),
        "degrad": (2.5, 4.0),
    },
    "Sodio-ion (Na-ion)": {
        "costo": (280, 320),
        "ciclos": (3000, 6000),
        "degrad": (2.0, 3.0),
    },
}

st.set_page_config(page_title="Simulador de BESS", layout="wide")

# Initialize session state variables for results
for k in RESULT_KEYS:
    st.session_state.setdefault(k, None)

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
            alt_path = "data/precios_italia_2024.xlsx"
            if os.path.exists(alt_path):
                path = alt_path
            else:
                alt_path2 = "data/precios_italia.xlsx"
                if os.path.exists(alt_path2):
                    path = alt_path2
                else:
                    st.error(f"Archivo predeterminado no encontrado: {path}")
                    st.stop()
        df = pd.read_excel(path, sheet_name=zona)
    df["Fecha"] = pd.to_datetime(df["Fecha"])
    return df

# --- Simulación ---
def simular(
    precios,
    potencia_mw,
    duracion_h,
    ef_carga,
    ef_descarga,
    estrategia,
    umbral_carga=0.25,
    umbral_descarga=0.75,
    margen=0,
    horario=None,
    coste_carga=0.0,
    coste_descarga=0.0,
):
    energia_mwh = potencia_mw * duracion_h
    capacidad_actual = 0
    resultados = []

    media_global = precios["Precio"].mean()
    media_d = (
        precios.groupby(precios["Fecha"].dt.date)["Precio"].mean().to_dict()
    )
    p_inf_d = (
        precios.groupby(precios["Fecha"].dt.date)["Precio"]
        .quantile(umbral_carga)
        .to_dict()
    )
    p_sup_d = (
        precios.groupby(precios["Fecha"].dt.date)["Precio"]
        .quantile(umbral_descarga)
        .to_dict()
    )

    for _, row in precios.iterrows():
        precio = row["Precio"]
        fecha_d = row["Fecha"].date()
        p_inf = p_inf_d.get(fecha_d, media_global)
        p_sup = p_sup_d.get(fecha_d, media_global)
        media_dia = media_d.get(fecha_d, media_global)
        estado = "Reposo"
        carga = descarga = 0

        if estrategia == "Percentiles":
            if precio < p_inf and capacidad_actual < energia_mwh:
                carga = potencia_mw * ef_carga
                capacidad_actual += carga
                estado = "Carga"
            elif precio > p_sup and capacidad_actual > 0:
                descarga = min(potencia_mw * ef_descarga, capacidad_actual)
                capacidad_actual -= descarga
                estado = "Descarga"

        elif estrategia == "Margen fijo":
            if precio < media_dia - margen and capacidad_actual < energia_mwh:
                carga = potencia_mw * ef_carga
                capacidad_actual += carga
                estado = "Carga"
            elif precio > media_dia + margen and capacidad_actual > 0:
                descarga = min(potencia_mw * ef_descarga, capacidad_actual)
                capacidad_actual -= descarga
                estado = "Descarga"

        elif estrategia == "Programada" and horario is not None:
            accion = horario.get(row["Fecha"].hour)
            if accion == "C" and capacidad_actual < energia_mwh:
                carga = potencia_mw * ef_carga
                capacidad_actual += carga
                estado = "Carga"
            elif accion == "D" and capacidad_actual > 0:
                descarga = min(potencia_mw * ef_descarga, capacidad_actual)
                capacidad_actual -= descarga
                estado = "Descarga"

        coste_c = coste_carga * carga
        coste_d = coste_descarga * descarga
        benef_bruto = precio * descarga - precio * carga
        benef_neto = benef_bruto - coste_c - coste_d

        resultados.append({
            "Fecha": row["Fecha"],
            "Precio": precio,
            "Carga (MWh)": carga,
            "Descarga (MWh)": descarga,
            "Coste carga (€)": coste_c,
            "Coste descarga (€)": coste_d,
            "Beneficio bruto (€)": benef_bruto,
            "Beneficio neto (€)": benef_neto,
            "SOC (MWh)": capacidad_actual,
            "Estado": estado,
        })

    return pd.DataFrame(resultados)

def resumen_mensual(df):
    return (
        df.resample("M", on="Fecha")
          .agg({"Carga (MWh)": "sum",
                "Descarga (MWh)": "sum",
                "Beneficio neto (€)": "sum"})
          .rename_axis("Mes")
    )

def analizar_duracion(
    precios,
    potencia_mw,
    max_h,
    ef_carga,
    ef_descarga,
    estrategia,
    umbral_carga,
    umbral_descarga,
    margen,
    horario,
    degradacion,
    capex_kwh,
    coste_desarrollo_mw,
    opex_kw,
    tasa_descuento,
    coste_carga,
    coste_descarga,
):
    """Calculate VAN for each duration from 1 to max_h."""
    datos = []
    for h in range(1, max_h + 1):
        res = simular(
            precios,
            potencia_mw,
            h,
            ef_carga,
            ef_descarga,
            estrategia,
            umbral_carga,
            umbral_descarga,
            margen,
            horario,
            coste_carga=coste_carga,
            coste_descarga=coste_descarga,
        )
        ingreso_anual = res["Beneficio neto (€)"].sum()
        capex_bat = potencia_mw * h * 1000 * capex_kwh
        coste_dev = potencia_mw * coste_desarrollo_mw
        capex_total = capex_bat + coste_dev
        inversion = -capex_total
        ingresos = [ingreso_anual * (1 - degradacion / 100) ** i for i in range(15)]
        flujo = [inversion] + [ingresos[i] - potencia_mw * 1000 * opex_kw for i in range(15)]
        van = npf.npv(tasa_descuento / 100, flujo)
        datos.append({"Duración (h)": h, "VAN": van})
    df = pd.DataFrame(datos)
    opt = df.loc[df["VAN"].idxmax(), "Duración (h)"]
    return df, opt

def analizar_margen(
    precios,
    potencia_mw,
    duracion_h,
    ef_carga,
    ef_descarga,
    estrategia,
    umbral_carga,
    umbral_descarga,
    max_margen,
    horario,
    degradacion,
    capex_kwh,
    coste_desarrollo_mw,
    opex_kw,
    tasa_descuento,
    coste_carga,
    coste_descarga,
    paso=1.0,
):
    """Return TIR for margins from 0 to max_margen."""
    datos = []
    m = 0.0
    while m <= max_margen:
        res = simular(
            precios,
            potencia_mw,
            duracion_h,
            ef_carga,
            ef_descarga,
            estrategia,
            umbral_carga,
            umbral_descarga,
            margen=m,
            horario=horario,
            coste_carga=coste_carga,
            coste_descarga=coste_descarga,
        )
        ingreso_anual = res["Beneficio neto (€)"].sum()
        capex_bat = potencia_mw * duracion_h * 1000 * capex_kwh
        coste_dev = potencia_mw * coste_desarrollo_mw
        capex_total = capex_bat + coste_dev
        inversion = -capex_total
        ingresos = [ingreso_anual * (1 - degradacion / 100) ** i for i in range(15)]
        flujo = [inversion] + [ingresos[i] - potencia_mw * 1000 * opex_kw for i in range(15)]
        tir = npf.irr(flujo)
        datos.append({"Margen (€/MWh)": m, "TIR": tir})
        m += paso
    df = pd.DataFrame(datos)
    opt = df.loc[df["TIR"].idxmax(), "Margen (€/MWh)"]
    return df, opt

# --- Interfaz ---
st.title("🔋 Simulador de BESS")

with st.sidebar:
    st.header("🔧 Parámetros de simulación")
    archivo = st.file_uploader("Archivo de precios", type=["xlsx", "csv"])
    zona = st.selectbox(
        "Zona",
        ["NORD", "CNORD", "CSUD", "SUD", "SARD", "SICILY", "BZ"],
    )
    st.markdown("---")
    tecnologia = st.selectbox("Tecnología", list(TECHS.keys()))
    cap_min, cap_max = TECHS[tecnologia]["costo"]
    cyc_min, cyc_max = TECHS[tecnologia]["ciclos"]
    deg_lo, deg_hi = TECHS[tecnologia]["degrad"]
    deg_min = max(0.0, deg_lo - 1.0)
    deg_max = deg_hi + 1.0
    deg_default = (deg_lo + deg_hi) / 2
    st.caption(
        f"Vida útil estimada: {cyc_min:,}-{cyc_max:,} ciclos. "
        f"Degradación típica {deg_lo}-{deg_hi}% anual"
    )
    degradacion = st.slider(
        "Degradación anual (%)", min_value=deg_min, max_value=deg_max,
        value=deg_default, step=0.1
    )
    potencia_mw = st.slider("Potencia (MW)", 1, 100, 10)
    duracion_h = st.slider("Duración (h)", 1, 10, 4)
    analizar_opt = st.checkbox("Analizar duración óptima")
    max_h = st.slider("Duración máxima a evaluar", 1, 10, 6) if analizar_opt else 0
    ef_carga = st.slider("Eficiencia de carga (%)", 50, 100, 95) / 100
    ef_descarga = st.slider("Eficiencia de descarga (%)", 50, 100, 95) / 100
    st.markdown("---")

    st.markdown("### Estrategia")
    estrategia = st.selectbox(
        "Estrategia", ["Percentiles", "Margen fijo", "Programada"]
    )
    umbral_carga = 0.25
    umbral_descarga = 0.75
    margen = 0.0
    analizar_marg = False
    max_margen = 0.0
    horario_file = None
    if estrategia == "Percentiles":
        umbral_carga = st.slider("Umbral de carga", 0.0, 1.0, 0.25, 0.05)
        umbral_descarga = st.slider("Umbral de descarga", 0.0, 1.0, 0.75, 0.05)
        st.caption(
            "La batería se carga cuando el precio está por debajo del percentil"
            "seleccionado en 'Umbral de carga' y se descarga cuando supera el "
            "percentil indicado en 'Umbral de descarga'."
        )
    elif estrategia == "Margen fijo":
        margen = st.number_input("Margen (€/MWh)", value=10.0)
        analizar_marg = st.checkbox("Analizar margen óptimo")
        max_margen = (
            st.slider("Margen máximo a evaluar (€/MWh)", 1.0, 100.0, 20.0)
            if analizar_marg
            else 0
        )
    else:  # Programada
        horario_file = st.file_uploader(
            "Horario (CSV con columnas hora,accion)", type="csv")

    st.markdown("---")
    st.markdown("### Parámetros económicos")
    coste_desarrollo_mw = st.slider(
        "Costes Desarrollo (€/MW)",
        min_value=10000,
        max_value=30000,
        value=20000,
        step=1000,
    )
    capex_kwh = st.slider(
        "CAPEX (€/kWh)",
        min_value=cap_min,
        max_value=cap_max,
        value=(cap_min + cap_max) // 2,
    )
    opex_kw = st.slider(
        "OPEX anual (€/kW)",
        min_value=5.0,
        max_value=8.0,
        value=6.5,
        step=0.1,
    )
    coste_carga = st.number_input("Coste carga (€/MWh)", value=2.0)
    coste_descarga = st.number_input(
        "Coste descarga (€/MWh)", value=2.0
    )

    st.markdown("---")
    st.markdown("#### Modelo")
    tasa_descuento = st.number_input("Tasa de descuento (%)", 0.0, 20.0, 7.0)
    ratio_apalancamiento = st.slider(
        "Ratio de apalancamiento (%)", 0, 100, 20, step=1
    )
    coste_financiacion = st.number_input("Coste financiación (%)", 0.0, 20.0, 5.0)

    iniciar = st.button("▶️ Ejecutar simulación")
    if st.button("Restablecer parámetros"):
        reset_sidebar()

    with st.expander("Ayuda"):
        help_text = """
<small>
**Pasos básicos**<br>
1. Configura la zona, la tecnología y el tamaño de la batería.<br>
2. Selecciona la estrategia de operación e introduce sus parámetros.<br>
3. Ajusta los valores económicos y pulsa **Ejecutar simulación**.<br>
4. Usa **Restablecer parámetros** para volver al estado inicial.<br><br>
**Estrategias disponibles**<br>
- <b>Percentiles</b>: se carga por debajo del `Umbral de carga` y se descarga por encima del `Umbral de descarga` calculados día a día.<br>
- <b>Margen fijo</b>: la referencia es la media diaria; se compra si el precio baja de media&nbsp;&minus;&nbsp;margen y se vende por encima de media&nbsp;+&nbsp;margen.<br>
- <b>Programada</b>: sube un CSV con columnas `hora` y `accion` (C o D) para fijar manualmente la carga y descarga.<br><br>
Tras la simulación se abren tres pestañas:<br>
- <em>Resultados</em> muestra tablas y enlaces de descarga.<br>
- <em>Gráficas</em> incluye un deslizador para elegir el día y filtros por año/mes.<br>
- <em>Resultados económicos</em> resume los flujos de caja y la TIR.<br>
</small>
"""
        st.markdown(help_text, unsafe_allow_html=True)

if iniciar:
    precios = cargar_datos(zona, archivo)
    start_default = precios["Fecha"].min().date()
    fecha_inicio = st.date_input("Desde", start_default)
    fi_dt = pd.to_datetime(fecha_inicio)
    fecha_fin_dt = fi_dt + relativedelta(years=15) - timedelta(days=1)
    fecha_fin_dt = min(fecha_fin_dt, pd.to_datetime(precios["Fecha"].max()))
    st.caption(f"Se simula hasta {fecha_fin_dt.date()} (máximo 15 años)")
    precios = precios[(precios["Fecha"] >= fi_dt) &
                      (precios["Fecha"] <= fecha_fin_dt)]
    fi_date = fi_dt.date()
    ff_date = fecha_fin_dt.date()

    horario = None
    if estrategia == "Programada" and horario_file is not None:
        df_hor = pd.read_csv(horario_file)
        horario = {row["hora"]: row["accion"] for _, row in df_hor.iterrows()}

    resultado = simular(
        precios,
        potencia_mw,
        duracion_h,
        ef_carga,
        ef_descarga,
        estrategia,
        umbral_carga,
        umbral_descarga,
        margen,
        horario,
        coste_carga,
        coste_descarga,
    )

    mensual = resumen_mensual(resultado)

    sens_df = None
    horas_opt = None
    sens_mar = None
    margen_opt = None
    if analizar_opt and max_h > 1:
        sens_df, horas_opt = analizar_duracion(
            precios,
            potencia_mw,
            max_h,
            ef_carga,
            ef_descarga,
            estrategia,
            umbral_carga,
            umbral_descarga,
            margen,
            horario,
            degradacion,
            capex_kwh,
            coste_desarrollo_mw,
            opex_kw,
            tasa_descuento,
            coste_carga,
            coste_descarga,
        )

    if estrategia == "Margen fijo" and analizar_marg and max_margen > 0:
        sens_mar, margen_opt = analizar_margen(
            precios,
            potencia_mw,
            duracion_h,
            ef_carga,
            ef_descarga,
            estrategia,
            umbral_carga,
            umbral_descarga,
            max_margen,
            horario,
            degradacion,
            capex_kwh,
            coste_desarrollo_mw,
            opex_kw,
            tasa_descuento,
            coste_carga,
            coste_descarga,
        )

    ingreso_anual = resultado["Beneficio neto (€)"].sum()
    capex_bateria = potencia_mw * duracion_h * 1000 * capex_kwh
    coste_desarrollo = potencia_mw * coste_desarrollo_mw
    capex_total = capex_bateria + coste_desarrollo
    inversion = -capex_total
    ingresos = [ingreso_anual * (1 - degradacion / 100) ** i for i in range(15)]
    flujo_anual = [ingresos[i] - potencia_mw * 1000 * opex_kw for i in range(15)]
    flujo_caja = [inversion] + flujo_anual
    van = npf.npv(tasa_descuento / 100, flujo_caja)
    tir = npf.irr(flujo_caja)

    deuda = capex_total * (ratio_apalancamiento / 100)
    equity = capex_total - deuda
    tasa_mensual = (coste_financiacion / 100) / 12
    meses = 15 * 12
    pago_mes = -npf.pmt(tasa_mensual, meses, deuda) if deuda else 0
    saldo = deuda
    flujo_equity = [-equity]
    flujos_equity_anual = []
    intereses_anuales = []
    amortizacion_anual = []
    for year in range(15):
        interes_anual = 0
        principal_anual = 0
        for _ in range(12):
            interes_mes = saldo * tasa_mensual
            principal_mes = pago_mes - interes_mes
            saldo -= principal_mes
            interes_anual += interes_mes
            principal_anual += principal_mes
        pago_total = interes_anual + principal_anual
        flujo_equity.append(
            ingresos[year] - potencia_mw * 1000 * opex_kw - pago_total
        )
        flujos_equity_anual.append(
            ingresos[year] - potencia_mw * 1000 * opex_kw - pago_total
        )
        intereses_anuales.append(interes_anual)
        amortizacion_anual.append(principal_anual)
    tir_equity = npf.irr(flujo_equity)

    total_descarga = resultado["Descarga (MWh)"].sum()
    ciclos_periodo = total_descarga / (potencia_mw * duracion_h)
    dias_periodo = (fecha_fin_dt - fi_dt).days + 1
    ciclos_anuales = ciclos_periodo / (dias_periodo / 365)

    st.session_state.update(
        {
            "resultado": resultado,
            "mensual": mensual,
            "fi_date": fi_date,
            "ff_date": ff_date,
            "ingreso_anual": ingreso_anual,
            "inversion": inversion,
            "van": van,
            "tir": tir,
            "tir_equity": tir_equity,
            "ciclos_anuales": ciclos_anuales,
            "cyc_min": cyc_min,
            "cyc_max": cyc_max,
            "flujo_caja": flujo_caja,
            "flujos_anuales": flujo_anual,
            "flujos_equity": flujos_equity_anual,
            "intereses_anuales": intereses_anuales,
            "amortizacion_anual": amortizacion_anual,
            "capex_bateria": capex_bateria,
            "coste_desarrollo": coste_desarrollo,
            "degradacion": degradacion,
            "sens_dur": sens_df,
            "horas_optimas": horas_opt,
            "sens_margen": sens_mar,
            "margen_optimo": margen_opt,
        }
    )

    tab_res, tab_graf, tab_ind = st.tabs(["Resultados", "Gráficas", "Resultados económicos"])

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
        dia = st.slider(
            "Día a visualizar",
            min_value=fi_date,
            max_value=ff_date,
            value=st.session_state.get("dia_graf", fi_date),
            format="YYYY-MM-DD",
            key="dia_graf",
        )
        diario = resultado[resultado["Fecha"].dt.date == dia]
        if not diario.empty:
            fig_d = make_subplots(specs=[[{"secondary_y": True}]])
            fig_d.add_trace(
                go.Scatter(x=diario["Fecha"], y=diario["Precio"], name="Precio"),
                secondary_y=False,
            )
            fig_d.add_trace(
                go.Scatter(x=diario["Fecha"], y=diario["SOC (MWh)"], name="SOC (MWh)"),
                secondary_y=True,
            )
            fig_d.update_layout(title=f"Precio y SOC - {dia}")
            fig_d.update_yaxes(title_text="Precio", secondary_y=False)
            fig_d.update_yaxes(title_text="SOC (MWh)", secondary_y=True)
            st.plotly_chart(fig_d, use_container_width=True)
        else:
            st.info("No hay datos para ese día")

        years_avail = sorted(resultado["Fecha"].dt.year.unique())
        year_sel = st.selectbox("Año", years_avail, key="sel_year")
        months_avail = sorted(
            resultado[resultado["Fecha"].dt.year == year_sel]["Fecha"].dt.month.unique()
        )
        month_sel = st.selectbox("Mes", months_avail, key="sel_month")
        periodo = resultado[(resultado["Fecha"].dt.year == year_sel) &
                            (resultado["Fecha"].dt.month == month_sel)]
        if not periodo.empty:
            fig = make_subplots(specs=[[{"secondary_y": True}]])
            fig.add_trace(
                go.Scatter(x=periodo["Fecha"], y=periodo["Precio"], name="Precio"),
                secondary_y=False,
            )
            fig.add_trace(
                go.Scatter(x=periodo["Fecha"], y=periodo["SOC (MWh)"], name="SOC (MWh)"),
                secondary_y=True,
            )
            fig.update_layout(title=f"Precio y Estado de Carga - {year_sel}-{month_sel:02d}")
            fig.update_yaxes(title_text="Precio", secondary_y=False)
            fig.update_yaxes(title_text="SOC (MWh)", secondary_y=True)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No hay datos para ese período")
        fig_b = px.bar(mensual.reset_index(), x="Mes", y="Beneficio neto (€)", title="Beneficio mensual")
        st.plotly_chart(fig_b, use_container_width=True)

        if sens_df is not None:
            fig_s = px.line(
                sens_df,
                x="Duración (h)",
                y="VAN",
                markers=True,
                title="VAN según duración",
            )
            fig_s.add_vline(x=horas_opt, line_dash="dash", line_color="red")
            st.plotly_chart(fig_s, use_container_width=True)

        if sens_mar is not None:
            fig_m = px.line(
                sens_mar,
                x="Margen (€/MWh)",
                y="TIR",
                markers=True,
                title="TIR según margen",
            )
            fig_m.add_vline(x=margen_opt, line_dash="dash", line_color="red")
            st.plotly_chart(fig_m, use_container_width=True)
else:
    st.info("Configura los parámetros en la barra lateral y pulsa Ejecutar.")
