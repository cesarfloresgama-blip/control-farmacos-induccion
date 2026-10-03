import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import os
import gspread
from google.oauth2.service_account import Credentials

# ---------------------------------------------------------
# CONFIGURACIÓN INICIAL DE LA PÁGINA
# ---------------------------------------------------------
st.set_page_config(
    page_title="Inmunosupresores - Trasplante Renal INCICh",
    page_icon="💊",
    layout="wide"
)

ID_HOJA_DEFAULT = "16UZ-5ZwwP44qGTyawhGzYE7vcovRxzFL10AmAYdzLJs"

# ---------------------------------------------------------
# LIMPIADOR Y SANITIZADOR DE CLAVE RSA PEM
# ---------------------------------------------------------
def reconstruir_clave_pem(raw_pk):
    if not raw_pk:
        return ""
    pk = str(raw_pk).strip()
    
    # Remover comillas envueltas dobles o simples
    while (pk.startswith('"') and pk.endswith('"')) or (pk.startswith("'") and pk.endswith("'")):
        pk = pk[1:-1].strip()
    
    # Reemplazar diagonales literales \n por saltos de línea reales
    pk = pk.replace("\\n", "\n").replace("\r", "")
    
    begin_tag = "-----BEGIN PRIVATE KEY-----"
    end_tag = "-----END PRIVATE KEY-----"
    
    if begin_tag in pk and end_tag in pk:
        start_idx = pk.find(begin_tag)
        end_idx = pk.find(end_tag) + len(end_tag)
        pem_block = pk[start_idx:end_idx]
        
        # Limpiar espacios en cada línea
        lineas = [line.strip() for line in pem_block.split("\n") if line.strip()]
        return "\n".join(lineas) + "\n"
    
    return pk

# ---------------------------------------------------------
# CONEXIÓN CON GOOGLE SHEETS
# ---------------------------------------------------------
@st.cache_resource(ttl=300)
def conectar_google_sheets():
    if "connections" not in st.secrets or "gsheets" not in st.secrets["connections"]:
        return None, "", "No se encontró la sección [connections.gsheets] en los Secrets de Streamlit Cloud."

    raw_secrets = dict(st.secrets["connections"]["gsheets"])
    bot_email = raw_secrets.get("client_email", "")

    # Reparar clave privada
    if "private_key" in raw_secrets:
        raw_secrets["private_key"] = reconstruir_clave_pem(raw_secrets["private_key"])

    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]

    try:
        creds = Credentials.from_service_account_info(raw_secrets, scopes=scopes)
        gc = gspread.authorize(creds)
    except Exception as e:
        return None, bot_email, f"Error de autenticación RSA/JSON: {e}"

    try:
        sh = gc.open_by_key(ID_HOJA_DEFAULT)
        return sh, bot_email, ""
    except gspread.exceptions.SpreadsheetNotFound:
        return None, bot_email, "SpreadsheetNotFound: El bot no tiene acceso a la hoja de cálculo. Asegúrate de compartirla con el correo del bot como Editor."
    except Exception as e:
        return None, bot_email, f"Error al abrir la hoja de cálculo: {e}"

sh, bot_email, error_msg = conectar_google_sheets()

COLS_EXISTENCIAS = ["Fármaco", "Lote", "Caducidad", "Cantidad", "Registró", "Fecha Registro"]
COLS_BAJAS = ["Fármaco", "Lote", "Cantidad", "Caducidad", "Motivo", "Atendió", "Fecha Baja"]

def obtener_o_crear_pestana(sh_obj, nombre_pestana, columnas):
    try:
        ws = sh_obj.worksheet(nombre_pestana)
    except gspread.exceptions.WorksheetNotFound:
        ws = sh_obj.add_worksheet(title=nombre_pestana, rows=100, cols=15)
        ws.append_row(columnas)
    return ws

def cargar_datos(nombre_pestana, columnas_default):
    if sh is None:
        return pd.DataFrame(columns=columnas_default)
    try:
        ws = obtener_o_crear_pestana(sh, nombre_pestana, columnas_default)
        rows = ws.get_all_values()
        if not rows or len(rows) <= 1:
            if rows and len(rows) == 1:
                return pd.DataFrame(columns=rows[0])
            return pd.DataFrame(columns=columnas_default)
        return pd.DataFrame(rows[1:], columns=rows[0])
    except Exception as e:
        st.error(f"Error cargando '{nombre_pestana}': {e}")
        return pd.DataFrame(columns=columnas_default)

def guardar_datos(nombre_pestana, df, columnas_default):
    if sh is None:
        st.error("❌ No hay conexión con la base de datos de Google Sheets.")
        return False
    try:
        ws = obtener_o_crear_pestana(sh, nombre_pestana, columnas_default)
        ws.clear()
        content = [df.columns.tolist()] + df.astype(str).values.tolist()
        try:
            ws.update(content)
        except TypeError:
            ws.update('A1', content)
        return True
    except Exception as e:
        st.error(f"❌ Error al guardar en '{nombre_pestana}': {e}")
        return False

# ---------------------------------------------------------
# 1. FOTO DE ENCABEZADO (INSTITUTO NACIONAL DE CARDIOLOGÍA)
# ---------------------------------------------------------
if os.path.exists("incich.jpg"):
    col_i1, col_i2, col_i3 = st.columns([2, 1, 2])
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

# DIAGNÓSTICO DE CONEXIÓN
if sh is None:
    st.error("🚨 **Atención: No se pudo conectar con Google Sheets**")
    st.code(error_msg, language="text")
    
    if bot_email:
        st.warning(f"""
        ### 🔑 Asegúrate de compartir tu hoja con el correo del Bot:
        **Correo del Bot:** `{bot_email}`
        """)
    st.divider()

# Cargar bases de datos desde Google Sheets
df_activos = cargar_datos("Existencias", COLS_EXISTENCIAS)
df_inactivos = cargar_datos("Bajas", COLS_BAJAS)

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
                
                df_actualizado = pd.concat([df_activos, nuevo_registro], ignore_index=True)
                
                if guardar_datos("Existencias", df_actualizado, COLS_EXISTENCIAS):
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
                
                df_bajas_actualizado = pd.concat([df_inactivos, nueva_baja], ignore_index=True)

                df_activos.at[idx_sel, "Cantidad"] = int(fila_sel["Cantidad"]) - int(cant_baja)
                if int(df_activos.at[idx_sel, "Cantidad"]) <= 0:
                    df_activos = df_activos.drop(idx_sel).reset_index(drop=True)

                ok_bajas = guardar_datos("Bajas", df_bajas_actualizado, COLS_BAJAS)
                ok_stock = guardar_datos("Existencias", df_activos, COLS_EXISTENCIAS)

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
