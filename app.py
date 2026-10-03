import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import os
import gspread

# ---------------------------------------------------------
# CONFIGURACIÓN INICIAL DE LA PÁGINA
# ---------------------------------------------------------
st.set_page_config(
    page_title="Inmunosupresores - Trasplante Renal INCICh",
    page_icon="💊",
    layout="wide"
)

# ID exacto de tu Hoja de Cálculo en Google Sheets
ID_HOJA_DEFAULT = "16UZ-5ZwwP44qGTyawhGzYE7vcovRxzFL10AmAYdzLJs"

# ---------------------------------------------------------
# CONEXIÓN DIRECTA Y DIAGNÓSTICO DE GOOGLE SHEETS
# ---------------------------------------------------------
@st.cache_resource(ttl=3600)
def iniciar_conexion_gsheets():
    if "connections" not in st.secrets or "gsheets" not in st.secrets["connections"]:
        raise ValueError("No se encontró la sección [connections.gsheets] en los Secrets de Streamlit Cloud.")

    raw_secrets = dict(st.secrets["connections"]["gsheets"])
    spreadsheet_url = raw_secrets.get("spreadsheet", "")

    # Filtrar solo campos oficiales de credenciales de Google
    creds_keys = [
        "type", "project_id", "private_key_id", "private_key",
        "client_email", "client_id", "auth_uri", "token_uri",
        "auth_provider_x509_cert_url", "client_x509_cert_url"
    ]
    creds_dict = {k: raw_secrets[k] for k in creds_keys if k in raw_secrets}

    # Limpieza estricta del formato de la clave privada RSA
    if "private_key" in creds_dict and isinstance(creds_dict["private_key"], str):
        pk = creds_dict["private_key"].replace("\\n", "\n").replace("\r", "").strip()
        if (pk.startswith('"') and pk.endswith('"')) or (pk.startswith("'") and pk.endswith("'")):
            pk = pk[1:-1].strip().replace("\\n", "\n")
        if not pk.endswith("\n"):
            pk += "\n"
        creds_dict["private_key"] = pk

    gc = gspread.service_account_from_dict(creds_dict)
    
    # Apertura del libro de trabajo
    try:
        sh = gc.open_by_key(ID_HOJA_DEFAULT)
    except Exception:
        if spreadsheet_url:
            sh = gc.open_by_url(spreadsheet_url)
        else:
            raise

    bot_email = creds_dict.get("client_email", "")
    return sh, bot_email

# Intentar conectar con la base de datos
try:
    sh, bot_email = iniciar_conexion_gsheets()
    conexion_ok = True
    error_conexion = ""
except Exception as e:
    sh = None
    bot_email = ""
    conexion_ok = False
    error_conexion = str(e)

def cargar_datos(worksheet_name):
    if not conexion_ok or sh is None:
        return pd.DataFrame()
    try:
        ws = sh.worksheet(worksheet_name)
        rows = ws.get_all_values()
        if not rows or len(rows) <= 1:
            if rows and len(rows) == 1:
                return pd.DataFrame(columns=rows[0])
            return pd.DataFrame()
        return pd.DataFrame(rows[1:], columns=rows[0])
    except Exception:
        return pd.DataFrame()

def guardar_datos(worksheet_name, df):
    if not conexion_ok or sh is None:
        st.error("❌ No hay conexión con la base de datos de Google Sheets.")
        return False
    try:
        ws = sh.worksheet(worksheet_name)
        ws.clear()
        content = [df.columns.tolist()] + df.astype(str).values.tolist()
        try:
            ws.update(content)
        except TypeError:
            ws.update('A1', content)
        return True
    except Exception as e:
        st.error(f"❌ Error al guardar en '{worksheet_name}': {e}")
        return False

# ---------------------------------------------------------
# 1. FOTO DE ENCABEZADO (INSTITUTO NACIONAL DE CARDIOLOGÍA)
# ---------------------------------------------------------
if os.path.exists("incich.jpg"):
    col_i1, col_i2, col_i3 = st.columns([1, 2, 1])
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

# Encabezado institucional
st.title("💊 Bitácora de Inmunosupresores para Trasplante Renal-INCICh 🫘")
st.caption("Control de entradas, salidas y monitoreo de caducidades en tiempo real")

# Mostrar advertencia de diagnóstico si la conexión falló
if not conexion_ok:
    st.error(f"⚠️ **Atención:** No se pudo establecer conexión con Google Sheets.")
    st.caption(f"Detalle técnico del error: `{error_conexion}`")
    if bot_email:
        st.warning(f"👉 Confirma que la hoja de cálculo esté compartida con rol de **Editor** al correo del bot:\n`{bot_email}`")
    st.divider()

# Cargar bases de datos desde Google Sheets
df_activos = cargar_datos("Existencias")
df_inactivos = cargar_datos("Bajas")

# ---------------------------------------------------------
# 4. ALERTAS DE CADUCIDAD AUTOMÁTICAS
# ---------------------------------------------------------
hoy = datetime.now().date()
limite_alerta = hoy + timedelta(days=60)

if not df_activos.empty and "Caducidad" in df_activos.columns:
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
        st.info("No hay fármacos registrados en el inventario.")
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
                
                if df_activos.empty:
                    df_activos = pd.DataFrame(columns=["Fármaco", "Lote", "Caducidad", "Cantidad", "Registró", "Fecha Registro"])
                
                df_actualizado = pd.concat([df_activos, nuevo_registro], ignore_index=True)
                
                if guardar_datos("Existencias", df_actualizado):
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
                nueva_baja = pd.DataFrame([{
                    "Fármaco": fila_sel["Fármaco"],
                    "Lote": fila_sel["Lote"],
                    "Cantidad": int(cant_baja),
                    "Caducidad": str(fila_sel["Caducidad"]),
                    "Motivo": motivo if motivo else "Sin especificación",
                    "Atendió": st.session_state.usuario,
                    "Fecha Baja": datetime.now().strftime("%d/%m/%Y %H:%M")
                }])
                
                if df_inactivos.empty:
                    df_inactivos = pd.DataFrame(columns=["Fármaco", "Lote", "Cantidad", "Caducidad", "Motivo", "Atendió", "Fecha Baja"])
                
                df_bajas_actualizado = pd.concat([df_inactivos, nueva_baja], ignore_index=True)

                df_activos.at[idx_sel, "Cantidad"] = int(fila_sel["Cantidad"]) - int(cant_baja)
                if int(df_activos.at[idx_sel, "Cantidad"]) <= 0:
                    df_activos = df_activos.drop(idx_sel).reset_index(drop=True)

                ok_bajas = guardar_datos("Bajas", df_bajas_actualizado)
                ok_stock = guardar_datos("Existencias", df_activos)

                if ok_bajas and ok_stock:
                    st.success(f"✅ Salida registrada exitosamente por **{st.session_state.usuario}**.")
                    st.rerun()

# --- PESTAÑA 4: HISTÓRICO DE BAJAS ---
with tab_historico:
    st.header("Historial de Salidas y Mermas")
    if df_inactivos.empty:
        st.info("No hay registros de bajas hasta el momento.")
    else:
        st.dataframe(df_inactivos, use_container_width=True, hide_index=True)
