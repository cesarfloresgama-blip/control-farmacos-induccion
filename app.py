import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from streamlit_gsheets import GSheetsConnection
import os

# Configuración inicial de la página web
st.set_page_config(
    page_title="Inmunosupresores - Trasplante Renal INCICh",
    page_icon="💊",
    layout="wide"
)

# Conexión con Google Sheets
conn = st.connection("gsheets", type=GSheetsConnection)

def cargar_datos(worksheet_name):
    try:
        df = conn.read(worksheet=worksheet_name, ttl="0s")
        return df.dropna(how="all")
    except Exception:
        return pd.DataFrame()

# ---------------------------------------------------------
# 1. FOTO DE ENCABEZADO (INSTITUTO NACIONAL DE CARDIOLOGÍA)
# ---------------------------------------------------------
if os.path.exists("incich.jpg"):
    col_i1, col_i2, col_i3 = st.columns([1, 2, 1])  # El espacio del centro (2) define el tamaño
    with col_i2:
        st.image("incich.jpg", use_container_width=True)

# ---------------------------------------------------------
# 2. CONTROL DE ACCESO CON USUARIOS AUTORIZADOS
# ---------------------------------------------------------
USUARIOS_AUTORIZADOS = [
    "Blanca_Jareth",
    "Residente_Nefro",
    "Elisa_Mendoza",
    "César_FG"
]

if "autenticado" not in st.session_state:
    st.session_state.autenticado = False

if "usuario" not in st.session_state:
    st.session_state.usuario = ""

if not st.session_state.autenticado:
    st.title("🏥 Central de Enfermería de Nefrología - INCICh")
    st.subheader("Control de Inmunosupresores en Trasplante Renal")
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        with st.form("login_form"):
            st.markdown("### Acceso al Sistema")
            usuario_input = st.selectbox("Selecciona tu Usuario", USUARIOS_AUTORIZADOS)
            pass_input = st.text_input("Contraseña", type="password")
            submit = st.form_submit_button("Ingresar")
            
            if submit:
                if pass_input.lower().strip() == "inducciontrasplanterenal":
                    st.session_state.autenticado = True
                    st.session_state.usuario = usuario_input
                    st.rerun()
                else:
                    st.error("❌ Contraseña incorrecta.")
    st.stop()

# ---------------------------------------------------------
# 3. INTERFAZ PRINCIPAL
# ---------------------------------------------------------
st.sidebar.title(f"👤 {st.session_state.usuario}")
st.sidebar.caption("Instituto Nacional de Cardiología Ignacio Chávez")
if st.sidebar.button("Cerrar Sesión"):
    st.session_state.autenticado = False
    st.session_state.usuario = ""
    st.rerun()

# Encabezado institucional ajustado
st.title("💊 Bitácora de Inmunosupresores para Trasplante Renal-INCICh 🫘")
st.caption("Control de entradas, salidas y monitoreo de caducidades en tiempo real")

# Cargar bases de datos desde Google Sheets
df_activos = cargar_datos("Existencias")
df_inactivos = cargar_datos("Bajas")

# ---------------------------------------------------------
# 4. ALERTAS DE CADUCIDAD AUTOMÁTICAS
# ---------------------------------------------------------
hoy = datetime.now().date()
limite_alerta = hoy + timedelta(days=60)

if not df_activos.empty:
    for idx, row in df_activos.iterrows():
        try:
            cad = datetime.strptime(str(row["Caducidad"]), "%Y-%m-%d").date()
        except Exception:
            try:
                cad = datetime.strptime(str(row["Caducidad"]), "%d/%m/%Y").date()
            except Exception:
                continue

        if cad <= hoy:
            st.error(f"🚨 **¡CADUCADO!** {row['Fármaco']} | Lote: `{row['Lote']}` | Venció el {cad.strftime('%d/%m/%Y')}")
        elif cad <= limite_alerta:
            dias = (cad - hoy).days
            st.warning(f"⚠️ **PRÓXIMO A CADUCAR** ({dias} días) | {row['Fármaco']} | Lote: `{row['Lote']}` | Fecha: {cad.strftime('%d/%m/%Y')}")

st.divider()

# ---------------------------------------------------------
# 5. PESTAÑAS DE TRABAJO
# ---------------------------------------------------------
tab_stock, tab_alta, tab_baja, tab_historico = st.tabs([
    "📊 Existencias (Stock)", 
    "➕ Alta (Entrada)", 
    "➖ Baja (Salida)", 
    "📜 Histórico de Bajas"
])

# --- PESTAÑA 1: EXISTENCIAS ---
with tab_stock:
    st.header("Inventario Actual en Resguardo")
    if df_activos.empty:
        st.info("No hay fármacos registrados en el inventario de Google Sheets.")
    else:
        st.dataframe(df_activos, use_container_width=True, hide_index=True)

# --- PESTAÑA 2: ALTA DE MEDICAMENTO ---
OPCIONES_FARMACOS = [
    "Tacrolimus 1 mg",
    "Tacrolimus 5 mg",
    "Micofenolato 500 mg",
    "Ac Micofenólico 360 mg",
    "Basiliximab (frasco)",
    "Timoglobulina (frasco)",
    "Rituximab 500 mg",
    "Rituximab 100 mg",
    "Inmunoglobulina (frasco)",
    "OTRO"
]

with tab_alta:
    st.header("Registrar Ingreso de Fármaco")
    with st.form("form_alta", clear_on_submit=True):
        col_a1, col_a2 = st.columns(2)
        with col_a1:
            med_opcion = st.selectbox("Fármaco", OPCIONES_FARMACOS)
            med_final = st.text_input("Especificar Nombre del Fármaco").strip() if med_opcion == "OTRO" else med_opcion
            lote_input = st.text_input("Número de Lote").strip().upper()

        with col_a2:
            caducidad_input = st.date_input("Fecha de Caducidad", min_value=hoy)
            cantidad_input = st.number_input("Cantidad de Unidades", min_value=1, step=1)

        btn_alta = st.form_submit_button("💾 Guardar Entrada en Google Sheets")

        if btn_alta:
            if not med_final or not lote_input:
                st.error("Por favor completa todos los campos requeridos.")
            else:
                nuevo_registro = pd.DataFrame([{
                    "Fármaco": med_final,
                    "Lote": lote_input,
                    "Caducidad": caducidad_input.strftime("%Y-%m-%d"),
                    "Cantidad": int(cantidad_input),
                    "Registró": st.session_state.usuario,
                    "Fecha Registro": datetime.now().strftime("%d/%m/%Y %H:%M")
                }])
                
                df_actualizado = pd.concat([df_activos, nuevo_registro], ignore_index=True)
                conn.update(worksheet="Existencias", data=df_actualizado)
                st.success(f"✅ Registrado exitosamente por **{st.session_state.usuario}**.")
                st.rerun()

# --- PESTAÑA 3: BAJA DE MEDICAMENTO ---
with tab_baja:
    st.header("Registrar Salida / Despacho")
    if df_activos.empty:
        st.info("No hay inventario disponible para dar de baja.")
    else:
        opciones = [
            f"{row['Fármaco']} | Lote: {row['Lote']} | Disponibles: {row['Cantidad']} unidades"
            for idx, row in df_activos.iterrows()
        ]
        idx_sel = st.selectbox("Seleccionar Fármaco y Lote", range(len(opciones)), format_func=lambda x: opciones[x])
        fila_sel = df_activos.iloc[idx_sel]

        with st.form("form_baja"):
            col_b1, col_b2 = st.columns(2)
            with col_b1:
                cant_baja = st.number_input("Cantidad a dar de baja", min_value=1, max_value=int(fila_sel["Cantidad"]), step=1)
            with col_b2:
                motivo = st.text_input("Motivo (ej. Aplicación a Paciente X, Merma)").strip()

            btn_baja = st.form_submit_button("🔴 Confirmar Baja")

            if btn_baja:
                # 1. Registrar la salida en la pestaña "Bajas"
                nueva_baja = pd.DataFrame([{
                    "Fármaco": fila_sel["Fármaco"],
                    "Lote": fila_sel["Lote"],
                    "Cantidad": int(cant_baja),
                    "Caducidad": str(fila_sel["Caducidad"]),
                    "Motivo": motivo if motivo else "Sin especificación",
                    "Atendió": st.session_state.usuario,
                    "Fecha Baja": datetime.now().strftime("%d/%m/%Y %H:%M")
                }])
                df_bajas_actualizado = pd.concat([df_inactivos, nueva_baja], ignore_index=True)
                conn.update(worksheet="Bajas", data=df_bajas_actualizado)

                # 2. Descontar del inventario activo en "Existencias"
                df_activos.at[idx_sel, "Cantidad"] = int(fila_sel["Cantidad"]) - int(cant_baja)
                if df_activos.at[idx_sel, "Cantidad"] <= 0:
                    df_activos = df_activos.drop(idx_sel)

                conn.update(worksheet="Existencias", data=df_activos)
                st.success(f"✅ Salida registrada exitosamente por **{st.session_state.usuario}**.")
                st.rerun()

# --- PESTAÑA 4: HISTÓRICO DE BAJAS ---
with tab_historico:
    st.header("Historial de Salidas y Mermas")
    if df_inactivos.empty:
        st.info("No hay registros de bajas hasta el momento.")
    else:
        st.dataframe(df_inactivos, use_container_width=True, hide_index=True)
