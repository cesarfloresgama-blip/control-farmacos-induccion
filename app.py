import streamlit as st
import pandas as pd
from datetime import datetime, timedelta

# Configuración inicial de la página web
st.set_page_config(
    page_title="Control de Fármacos - Inducción Renal",
    page_icon="💊",
    layout="wide"
)

# ---------------------------------------------------------
# 1. INICIALIZACIÓN DE VARIABLES EN SESIÓN (PERSISTENCIA)
# ---------------------------------------------------------
if "farmacos_activos" not in st.session_state:
    st.session_state.farmacos_activos = []

if "farmacos_inactivos" not in st.session_state:
    st.session_state.farmacos_inactivos = []

if "autenticado" not in st.session_state:
    st.session_state.autenticado = False

if "usuario" not in st.session_state:
    st.session_state.usuario = ""

# ---------------------------------------------------------
# 2. CONTROL DE ACCESO (LOGIN)
# ---------------------------------------------------------
if not st.session_state.autenticado:
    st.title("🏥 Central de Enfermería de Nefrología")
    st.subheader("Control de Fármacos de Inducción en Trasplante Renal")
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        with st.form("login_form"):
            st.markdown("### Acceso al Sistema")
            usuario_input = st.text_input("Usuario")
            pass_input = st.text_input("Contraseña", type="password")
            submit = st.form_submit_button("Ingresar")
            
            if submit:
                if pass_input.lower().strip() == "inducciontrasplanterenal" and usuario_input.strip() != "":
                    st.session_state.autenticado = True
                    st.session_state.usuario = usuario_input.strip()
                    st.rerun()
                else:
                    st.error("❌ Usuario o contraseña incorrectos.")
    st.stop()

# ---------------------------------------------------------
# 3. INTERFAZ PRINCIPAL Y BARRA LATERAL
# ---------------------------------------------------------
st.sidebar.title(f"👤 {st.session_state.usuario}")
st.sidebar.caption("Central de Enfermería - Nefrología")
if st.sidebar.button("Cerrar Sesión"):
    st.session_state.autenticado = False
    st.session_state.usuario = ""
    st.rerun()

st.title("💊 Bitácora de Fármacos de Inducción")
st.caption("Control de entradas, salidas y monitoreo de caducidades")

# ---------------------------------------------------------
# 4. MONITOR AUTOMÁTICO DE ALERTAS DE CADUCIDAD
# ---------------------------------------------------------
hoy = datetime.now().date()
limite_alerta = hoy + timedelta(days=60)

for item in st.session_state.farmacos_activos:
    cad = item["caducidad"]
    if cad <= hoy:
        st.error(f"🚨 **¡CADUCADO!** {item['medicamento']} | Lote: `{item['lote']}` | Venció el {cad.strftime('%d/%m/%Y')}")
    elif cad <= limite_alerta:
        dias = (cad - hoy).days
        st.warning(f"⚠️ **PRÓXIMO A CADUCAR** ({dias} días) | {item['medicamento']} | Lote: `{item['lote']}` | Fecha: {cad.strftime('%d/%m/%Y')}")

st.divider()

# ---------------------------------------------------------
# 5. MÓDULOS DEL SISTEMA (PESTAÑAS)
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
    if not st.session_state.farmacos_activos:
        st.info("No hay fármacos registrados en el inventario.")
    else:
        df_activos = pd.DataFrame(st.session_state.farmacos_activos)
        
        # Métricas rápidas
        col_m1, col_m2 = st.columns(2)
        col_m1.metric("Total de Lotes Activos", len(df_activos))
        col_m2.metric("Total de Unidades Disponibles", df_activos["cantidad"].sum())
        
        # Formato de visualización
        df_display = df_activos.copy()
        df_display["caducidad"] = df_display["caducidad"].apply(lambda x: x.strftime("%d/%m/%Y"))
        df_display.columns = ["Fármaco", "Lote", "Caducidad", "Unidades", "Registró", "Fecha Registro"]
        
        st.dataframe(df_display, use_container_width=True, hide_index=True)

# --- PESTAÑA 2: ALTA DE MEDICAMENTO ---
with tab_alta:
    st.header("Registrar Ingreso de Fármaco")
    with st.form("form_alta", clear_on_submit=True):
        col_a1, col_a2 = st.columns(2)
        
        with col_a1:
            med_opcion = st.selectbox(
                "Fármaco de Inducción",
                ["BASILIXIMAB", "TIMOGLOBULINA", "ALEMTUZUMAB", "TACROLIMUS", "OTRO"]
            )
            if med_opcion == "OTRO":
                med_final = st.text_input("Especificar Nombre del Fármaco").strip().upper()
            else:
                med_final = med_opcion
                
            lote_input = st.text_input("Número de Lote").strip().upper()

        with col_a2:
            caducidad_input = st.date_input("Fecha de Caducidad", min_value=hoy)
            cantidad_input = st.number_input("Cantidad de Unidades", min_value=1, step=1)

        btn_alta = st.form_submit_button("💾 Guardar Entrada en Inventario")

        if btn_alta:
            if not med_final or not lote_input:
                st.error("Por favor completa el nombre del fármaco y el lote.")
            else:
                st.session_state.farmacos_activos.append({
                    "medicamento": med_final,
                    "lote": lote_input,
                    "caducidad": caducidad_input,
                    "cantidad": int(cantidad_input),
                    "usuario": st.session_state.usuario,
                    "fecha_registro": datetime.now().strftime("%d/%m/%Y %H:%M")
                })
                st.success(f"✅ Se ingresaron {cantidad_input} unidades de **{med_final}** (Lote: {lote_input}).")
                st.rerun()

# --- PESTAÑA 3: BAJA DE MEDICAMENTO ---
with tab_baja:
    st.header("Registrar Salida / Despacho")
    if not st.session_state.farmacos_activos:
        st.info("No hay fármacos disponibles en el inventario para dar de baja.")
    else:
        # Generar lista de opciones descriptivas
        opciones = [
            f"{item['medicamento']} | Lote: {item['lote']} | Disponibles: {item['cantidad']} unidades"
            for item in st.session_state.farmacos_activos
        ]
        
        idx_seleccionado = st.selectbox(
            "Seleccionar Fármaco y Lote a descontar",
            range(len(opciones)),
            format_func=lambda x: opciones[x]
        )
        
        item_sel = st.session_state.farmacos_activos[idx_seleccionado]
        
        with st.form("form_baja"):
            col_b1, col_b2 = st.columns(2)
            with col_b1:
                cant_baja = st.number_input(
                    "Cantidad a dar de baja", 
                    min_value=1, 
                    max_value=int(item_sel["cantidad"]), 
                    step=1
                )
            with col_b2:
                motivo = st.text_input("Motivo (ej. Aplicación a Paciente X, Merma, Expiración)").strip()
                
            btn_baja = st.form_submit_button("🔴 Confirmar Baja")
            
            if btn_baja:
                # Descontar del inventario activo
                item_sel["cantidad"] -= int(cant_baja)
                
                # Registrar en histórico
                st.session_state.farmacos_inactivos.append({
                    "medicamento": item_sel["medicamento"],
                    "lote": item_sel["lote"],
                    "cantidad": int(cant_baja),
                    "caducidad": item_sel["caducidad"].strftime("%d/%m/%Y"),
                    "motivo": motivo if motivo else "Sin especificación",
                    "usuario": st.session_state.usuario,
                    "fecha_baja": datetime.now().strftime("%d/%m/%Y %H:%M")
                })
                
                # Si las unidades llegan a 0, remover el lote activo
                if item_sel["cantidad"] == 0:
                    st.session_state.farmacos_activos.pop(idx_seleccionado)
                    
                st.success(f"✅ Se descontaron {cant_baja} unidades del lote **{item_sel['lote']}**.")
                st.rerun()

# --- PESTAÑA 4: HISTÓRICO DE BAJAS ---
with tab_historico:
    st.header("Historial de Salidas y Mermas")
    if not st.session_state.farmacos_inactivos:
        st.info("No hay registros de bajas hasta el momento.")
    else:
        df_inactivos = pd.DataFrame(st.session_state.farmacos_inactivos)
        df_inactivos.columns = ["Fármaco", "Lote", "Cantidad Baja", "Caducidad", "Motivo", "Atendió", "Fecha/Hora Baja"]
        st.dataframe(df_inactivos, use_container_width=True, hide_index=True)