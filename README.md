# Simulador de BESS

Esta aplicación permite evaluar la operación y rentabilidad de un sistema de almacenamiento en baterías (BESS) a partir de precios horarios de la electricidad.

## Instalación

```bash
pip install -r requirements.txt
```

## Ejecución

```bash
streamlit run bess_simulador_app.py
```

## Datos de ejemplo

Por defecto se cargan los precios del archivo `Precios_Mercado_Italiano_2024.xlsx`, ubicado en la raíz del proyecto y con una hoja por zona del mercado italiano. Puedes subir tu propio archivo (CSV o XLSX) desde la barra lateral.

## Parámetros principales

- Potencia y duración de la batería
- Eficiencias de carga y descarga
- Estrategia de operación (percentiles, margen fijo o programada)
- Umbrales y márgenes de precios
- Costes de desarrollo y CAPEX por tecnología
- OPEX anual y coste de operación
- Modelo financiero con tasa de descuento, apalancamiento y coste de financiación

Los resultados se muestran en tablas y gráficas, con opción de descarga en CSV.

La interfaz incluye pestañas para consultar los datos, gráficos y los indicadores económicos.
Puedes restablecer los valores con el botón **Restablecer parámetros** y
encontrar ayuda básica en la barra lateral.
En la pestaña de gráficas puedes desplazarte entre días con un deslizador situado bajo la figura
para ver los precios y el estado de carga horarios de la fecha seleccionada.
El estado de carga se muestra en un segundo eje vertical para facilitar su lectura.
La pestaña de gráficas incluye además un histograma con el flujo de caja anual durante los 15 años de la simulación.
