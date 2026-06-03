import streamlit as st
import numpy as np
import plotly.graph_objects as go
import math
import config 

# =============================================================================
# 1. CONFIGURACIÓN DE LA PÁGINA Y ESTILOS
# =============================================================================
st.set_page_config(page_title="Simulador Mecánica de Fluidos", layout="wide")

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Crimson+Text:ital,wght@0,400;0,600;1,400&display=swap');
    html, body, [class*="css"] { font-family: 'Crimson Text', serif; font-size: 19px; }
    h1, h2, h3, h4 { color: #1a6bbf; font-weight: 600; }
    .stMetric label { font-size: 16px !important; font-weight: bold; }
</style>
""", unsafe_allow_html=True)

# =============================================================================
# 2. FUNCIONES DE LÓGICA Y CÁLCULOS
# =============================================================================
def calcular_fisica_fluido(vel, rad, rho_s, nombre_fluido):
    """Ejecuta los modelos matemáticos consultando la base de datos de config.py"""
    
    g = config.GRAVEDAD
    D = config.DIAMETRO_TUBERIA
    
    # 1. Consulta a la Base de Datos
    propiedades = config.BASE_FLUIDOS[nombre_fluido]
    rho_f = propiedades["rho_f"]
    mu = propiedades["mu"]
    nu = propiedades["nu"]
    
    # 2. Cálculo de densidades
    r = rad * 1e-3
    drho = rho_s - rho_f
    abs_drho = abs(drho)

    # 3. Sedimentación (Stokes + Schiller-Naumann)
    Wp_stokes = (2/9) * g * (r**2) * abs_drho / mu
    Re_p0 = 2 * r * Wp_stokes / nu
    Wp_mag = Wp_stokes / (1 + 0.15 * (Re_p0**0.687)) if Re_p0 > 0.5 else Wp_stokes
    
    # Signo de la velocidad (positivo = cae, negativo = flota)
    Wp = np.sign(drho) * Wp_mag
    Re_p_real = 2 * r * Wp_mag / nu

    # 4. Fricción y Reynolds de la Tubería
    Re_D = max(1, vel * D / nu)
    if Re_D > 4000: f = 0.316 / (Re_D**0.25)
    elif Re_D > 2300: f = 0.025
    else: f = 64 / Re_D

    # 5. Turbulencia
    u_star = vel * math.sqrt(f / 8)
    Wt = 2.5 * u_star
    ratio = Wp_mag / Wt if Wt > 0 else 999

    # 6. Selección de Patrón Visual
    if ratio < 0.35:
        regimen = {"name": "Homogéneo", "color": config.COLOR_HOMOGENEO, "desc": "Suspensión total. La turbulencia vence completamente a la gravedad."}
    elif ratio < 1.2:
        regimen = {"name": "Heterogéneo", "color": config.COLOR_HETEROGENEO, "desc": "Gradiente de concentración. Competencia entre gravedad y turbulencia."}
    elif ratio < 2.5:
        regimen = {"name": "Saltación", "color": config.COLOR_SALTACION, "desc": "Partículas avanzan por brincos en el fondo de la tubería."}
    else:
        regimen = {"name": "Lecho Estático", "color": config.COLOR_LECHO, "desc": "Depósito estacionario. Riesgo de taponamiento de la tubería."}

    return Wp, Wt, ratio, Re_p_real, Re_D, f, drho, regimen

# =============================================================================
# 3. INTERFAZ DE USUARIO (Panel Lateral)
# =============================================================================
st.title("Simulador de Flujo Multifásico Sólido-Líquido")

st.sidebar.header("Condiciones de Operación")

# AQUÍ IMPLEMENTAMOS LA BASE DE DATOS COMO UN MENÚ DESPLEGABLE
lista_fluidos = list(config.BASE_FLUIDOS.keys())
fluido_seleccionado = st.sidebar.selectbox("Seleccione el Fluido Portador", lista_fluidos)

st.sidebar.markdown("---")
vel = st.sidebar.slider("Velocidad del Fluido (m/s)", 0.1, 4.0, 1.2, 0.1)
conc = st.sidebar.slider("Concentración de Sólidos (%)", 5, 55, 20, 1)
rad = st.sidebar.slider("Radio de Partícula (mm)", 0.1, 2.5, 0.5, 0.1)

# En lugar de pedir Delta Rho, pedimos la densidad del sólido real
st.sidebar.markdown("---")
st.sidebar.subheader("Propiedades de la Partícula")
rho_s = st.sidebar.number_input("Densidad del Sólido (kg/m³)", min_value=100.0, max_value=8000.0, value=2650.0, step=50.0)
st.sidebar.caption("Ejemplos: Carbón (~1300), Arena de cuarzo (~2650), Acero (~7800), Poliestireno (~1050)")

# =============================================================================
# 4. EJECUCIÓN
# =============================================================================
Wp, Wt, ratio, Re_p_real, Re_D, f, drho_calculado, regimen = calcular_fisica_fluido(vel, rad, rho_s, fluido_seleccionado)

tab_diseno, tab_calculos = st.tabs(["🎨 Diseño e Hidráulica", "🧮 Memoria de Cálculo"])

with tab_diseno:
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("W_p (Sedimentación)", f"{Wp:.4f} m/s")
    col2.metric("W_t (Turbulencia)", f"{Wt:.4f} m/s")
    col3.metric("Relación W_p / W_t", f"{ratio:.3f}")
    col4.metric("Régimen Previsto", regimen["name"])

    st.markdown(f"#### <span style='color:{regimen['color']}'>{regimen['name']}</span>", unsafe_allow_html=True)
    st.info(regimen["desc"])
    
    n_particles = min(600, int(conc * 10))
    x_pos = np.random.uniform(0, 10, n_particles)

    if regimen["name"] == 'Homogéneo': y_pos = np.random.uniform(0.05, 0.95, n_particles)
    elif regimen["name"] == 'Heterogéneo': y_pos = np.random.beta(2, 4, n_particles) * 0.9
    elif regimen["name"] == 'Saltación': y_pos = np.random.beta(1, 8, n_particles) * 0.5 + 0.02
    else: y_pos = np.random.uniform(0.02, 0.15, n_particles)

    if drho_calculado < 0: y_pos = 1 - y_pos # Si flota, las partículas se van al techo

    fig = go.Figure()
    fig.add_shape(type="rect", x0=0, y0=0, x1=10, y1=1, line=dict(color="#4a5575", width=3), fillcolor="#e6e9f2", opacity=0.4)
    fig.add_trace(go.Scatter(x=x_pos, y=y_pos, mode='markers', marker=dict(size=rad*8 + 3, color=regimen["color"], opacity=0.75)))
    fig.update_layout(xaxis=dict(visible=False, range=[0, 10]), yaxis=dict(visible=False, range=[0, 1]), margin=dict(l=10, r=10, t=10, b=10), height=260)
    st.plotly_chart(fig, use_container_width=True)

with tab_calculos:
    # Mostramos las propiedades extraídas de la base de datos
    props = config.BASE_FLUIDOS[fluido_seleccionado]
    
    st.subheader(f"Auditoría del Fluido: {fluido_seleccionado}")
    c1, c2, c3, c4 = st.columns(4)
    c1.markdown(f"**$\\rho_f$:** `{props['rho_f']} kg/m³`")
    c2.markdown(f"**$\\mu$:** `{props['mu']} Pa·s`")
    c3.markdown(f"**$\\Delta\\rho$:** `{drho_calculado} kg/m³`")
    c4.markdown(f"**Reynolds ($Re_D$):** `{Re_D:.0f}`")
    
    st.markdown("---")
    st.markdown("#### Corrección de Schiller-Naumann")
    st.latex(r'W_{p, \text{stokes}} = \frac{2}{9} \frac{g \cdot r^2 \cdot |\rho_s - \rho_f|}{\mu}')
    st.latex(r'W_t = 2.5 \cdot v \cdot \sqrt{\frac{f}{8}}')