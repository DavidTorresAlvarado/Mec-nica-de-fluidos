import streamlit as st
import streamlit.components.v1 as components
import numpy as np
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
    g = config.GRAVEDAD
    D = config.DIAMETRO_TUBERIA
    
    propiedades = config.BASE_FLUIDOS[nombre_fluido]
    rho_f = propiedades["rho_f"]
    mu = propiedades["mu"]
    nu = propiedades["nu"]
    
    r = rad * 1e-3
    drho = rho_s - rho_f
    abs_drho = abs(drho)

    Wp_stokes = (2/9) * g * (r**2) * abs_drho / mu
    Re_p0 = 2 * r * Wp_stokes / nu
    Wp_mag = Wp_stokes / (1 + 0.15 * (Re_p0**0.687)) if Re_p0 > 0.5 else Wp_stokes
    
    Wp = np.sign(drho) * Wp_mag
    Re_p_real = 2 * r * Wp_mag / nu

    Re_D = max(1, vel * D / nu)
    if Re_D > 4000: f = 0.316 / (Re_D**0.25)
    elif Re_D > 2300: f = 0.025
    else: f = 64 / Re_D

    u_star = vel * math.sqrt(f / 8)
    Wt = 2.5 * u_star
    ratio = Wp_mag / Wt if Wt > 0 else 999

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

lista_fluidos = list(config.BASE_FLUIDOS.keys())
fluido_seleccionado = st.sidebar.selectbox("Fluido Portador", lista_fluidos)

st.sidebar.markdown("---")
vel = st.sidebar.slider("Velocidad de Flujo ($v$) [m/s]", 0.1, 4.0, 1.2, 0.1)
conc = st.sidebar.slider("Concentración de Sólidos (%)", 5, 55, 20, 1)
rad = st.sidebar.slider("Radio de Partícula ($r_p$) [mm]", 0.1, 2.5, 0.5, 0.1)

st.sidebar.markdown("---")
st.sidebar.subheader("Propiedades de la Partícula")
rho_s = st.sidebar.number_input("Densidad del Sólido ($\\rho_s$) [kg/m³]", min_value=100.0, max_value=8000.0, value=2650.0, step=50.0)
st.sidebar.caption("💡 Para ver la partícula flotar, pon una densidad menor a la del fluido (ej. Agua = 1000). Para suspensión, pon una casi idéntica.")

# =============================================================================
# 4. EJECUCIÓN Y VISUALIZACIÓN
# =============================================================================
Wp, Wt, ratio, Re_p_real, Re_D, f, drho_calculado, regimen = calcular_fisica_fluido(vel, rad, rho_s, fluido_seleccionado)

tab_diseno, tab_calculos = st.tabs(["🎨 Simulación e Hidráulica", "🧮 Memoria de Cálculo"])

with tab_diseno:
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Sedimentación ($W_p$)", f"{Wp:.4f} m/s")
    col2.metric("Turbulencia ($W_t$)", f"{Wt:.4f} m/s")
    col3.metric("Relación ($W_p / W_t$)", f"{ratio:.3f}")
    col4.metric("Régimen Previsto", regimen["name"])

    st.markdown(f"#### <span style='color:{regimen['color']}'>{regimen['name']}</span>", unsafe_allow_html=True)
    st.info(regimen["desc"])
    
    # -------------------------------------------------------------------------
    # MOTOR GRÁFICO HTML5 CANVAS (CERO LAG, 60 FPS)
    # -------------------------------------------------------------------------
    html_canvas = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ margin: 0; overflow: hidden; }}
            canvas {{
                background-color: #e6e9f2;
                border: 3px solid #4a5575;
                border-radius: 8px;
                width: 100%;
                height: 280px;
                display: block;
            }}
        </style>
    </head>
    <body>
        <canvas id="simCanvas"></canvas>
        <script>
            const canvas = document.getElementById('simCanvas');
            const ctx = canvas.getContext('2d');
            
            // Ajustar resolución interna del canvas
            canvas.width = canvas.clientWidth;
            canvas.height = canvas.clientHeight;

            // Variables inyectadas desde Python
            const n_particles = {min(500, int(conc * 12))};
            const radius = Math.max(2, {rad * 4});
            const color = "{regimen['color']}";
            const vel_base = {vel * 3}; 
            const drho = {drho_calculado};
            const regimen_name = "{regimen['name']}";

            // Lógica de Flotabilidad Suave (Mapeo con Arcotangente)
            // Si drho es 0, shift es 0. Si drho es muy grande, shift tiende a +/- 1
            let buoyancyShift = Math.atan(drho / 250) / (Math.PI / 2); 
            
            let amplitude = 0.1;
            
            // Ajustamos cómo afecta la turbulencia según el régimen
            if (regimen_name === "Homogéneo") {{
                amplitude = 0.4; // Se esparcen por todo el tubo
                buoyancyShift *= 0.1; // La turbulencia vence la flotabilidad
            }} else if (regimen_name === "Heterogéneo") {{
                amplitude = 0.2;
                buoyancyShift *= 0.7; 
            }} else if (regimen_name === "Saltación") {{
                amplitude = 0.05;
                buoyancyShift *= 0.9;
            }} else {{ // Lecho Estático
                amplitude = 0.01;
                buoyancyShift = Math.sign(drho) * 0.95; 
            }}

            // Centro objetivo en Y (0.5 es la mitad del tubo)
            const targetBaseY = canvas.height * (0.5 + buoyancyShift * 0.4);

            let particles = [];
            for(let i=0; i<n_particles; i++) {{
                particles.push({{
                    x: Math.random() * canvas.width,
                    y: targetBaseY + (Math.random() - 0.5) * canvas.height * amplitude * 2,
                    offset: Math.random() * Math.PI * 2, // Desfase para el movimiento sinusoidal
                    speedX: vel_base + Math.random() * (vel_base * 0.2)
                }});
            }}

            function animate() {{
                ctx.clearRect(0, 0, canvas.width, canvas.height);
                
                for(let i=0; i<n_particles; i++) {{
                    let p = particles[i];
                    
                    // Movimiento horizontal
                    p.x += p.speedX;
                    if(p.x > canvas.width + radius) {{
                        p.x = -radius;
                        // Al reaparecer, se posicionan suavemente dentro de su rango
                        p.y = targetBaseY + (Math.random() - 0.5) * canvas.height * amplitude * 2;
                    }}

                    // Calcular la posición Y deseada para este cuadro
                    let myTargetY = targetBaseY;

                    // Añadir turbulencia (onda sinusoidal suave)
                    myTargetY += Math.sin(p.x * 0.03 + p.offset) * canvas.height * amplitude;

                    // Físicas específicas de rebote para Saltación (sólo si se hunden)
                    if (regimen_name === "Saltación" && drho > 0) {{
                        myTargetY = canvas.height * 0.88 - Math.abs(Math.sin(p.x * 0.06 + p.offset)) * canvas.height * 0.15;
                    }}

                    // Suavizado del movimiento vertical (Easing)
                    p.y += (myTargetY - p.y) * 0.05;

                    // Dibujar la partícula
                    ctx.beginPath();
                    ctx.arc(p.x, p.y, radius, 0, Math.PI * 2);
                    ctx.fillStyle = color;
                    ctx.globalAlpha = 0.8;
                    ctx.fill();
                }}
                
                requestAnimationFrame(animate);
            }}
            
            // Iniciar ciclo de animación
            animate();
        </script>
    </body>
    </html>
    """
    
    # Incrustamos el Canvas en Streamlit
    components.html(html_canvas, height=290)

with tab_calculos:
    props = config.BASE_FLUIDOS[fluido_seleccionado]
    
    st.subheader(f"Auditoría del Fluido: {fluido_seleccionado}")
    c1, c2, c3, c4 = st.columns(4)
    c1.markdown(f"**Densidad ($\\rho_f$):** `{props['rho_f']} kg/m³`")
    c2.markdown(f"**Viscosidad ($\\mu$):** `{props['mu']} Pa·s`")
    c3.markdown(f"**Diferencial ($\\Delta\\rho$):** `{drho_calculado} kg/m³`")
    c4.markdown(f"**Reynolds de Tubería ($Re_D$):** `{Re_D:.0f}`")
    
    st.markdown("---")
    st.markdown("#### Corrección de Arrastre de Schiller-Naumann")
    st.latex(r'W_{p, \text{stokes}} = \frac{2}{9} \frac{g \cdot r_p^2 \cdot |\rho_s - \rho_f|}{\mu}')
    st.latex(r'W_t = 2.5 \cdot v \cdot \sqrt{\frac{f}{8}}')
    st.markdown("---")
    st.markdown("#### Criterio de Estabilidad Numérica")
    st.latex(r'Re_p = \frac{2 \cdot r_p \cdot W_p}{\nu}')