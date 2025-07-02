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
