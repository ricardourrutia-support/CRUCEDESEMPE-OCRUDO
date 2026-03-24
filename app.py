import streamlit as st
import pandas as pd
from io import BytesIO
from datetime import date

st.set_page_config(page_title="Cruce Evolutivo vs Ventas", layout="wide")
st.title("🔀 Cruce: Evolutivo Tiempo Losa vs Ventas (Id Pax)")

st.markdown("""
Esta herramienta cruza las reservas del **Evolutivo** con los reportes de **Ventas** para extraer el **Id Pax**. 
Las reservas que no encuentren coincidencia de Id Pax serán omitidas en el reporte final.
""")

st.header("1. Cargar Archivos")
col1, col2 = st.columns(2)

with col1:
    evolutivo_file = st.file_uploader("📥 Sube el reporte Evolutivo (.csv)", type=["csv"])

with col2:
    ventas_files = st.file_uploader("📥 Sube los reportes de Ventas (.csv)", type=["csv"], accept_multiple_files=True)

st.header("2. Rango de Fechas (Evolutivo)")
col3, col4 = st.columns(2)
# Por defecto configurado a tu requerimiento inicial
date_from = col3.date_input("Desde:", date(2026, 2, 1))
date_to = col4.date_input("Hasta:", date(2026, 3, 24))

if date_from > date_to:
    st.error("❌ La fecha inicial no puede ser mayor que la final.")
    st.stop()

st.divider()

if st.button("🔄 Generar Cruce"):
    if not evolutivo_file or not ventas_files:
        st.error("❌ Debes cargar el archivo Evolutivo y al menos un reporte de Ventas.")
        st.stop()

    try:
        # === 1. PROCESAR EVOLUTIVO ===
        st.info("⏳ Procesando archivo Evolutivo...")
        df_evo = pd.read_csv(evolutivo_file, sep=';', encoding='utf-8-sig')
        df_evo.columns = df_evo.columns.astype(str).str.strip().str.replace('\ufeff', '')
        
        # Diccionario para traducir meses en español
        meses = {'enero': 1, 'febrero': 2, 'marzo': 3, 'abril': 4, 'mayo': 5, 'junio': 6, 
                 'julio': 7, 'agosto': 8, 'septiembre': 9, 'octubre': 10, 'noviembre': 11, 'diciembre': 12}
        
        # Función para limpiar la fecha "6 de marzo de 2026"
        def parse_spanish_date(date_str):
            try:
                parts = str(date_str).lower().strip().split(' de ')
                if len(parts) == 3:
                    return pd.Timestamp(year=int(parts[2]), month=meses[parts[1]], day=int(parts[0]))
            except: 
                pass
            return pd.NaT

        df_evo['fecha_real'] = df_evo['Día de tm_start_local_at'].apply(parse_spanish_date)
        
        # Filtrar por fechas seleccionadas
        start_date = pd.to_datetime(date_from)
        end_date = pd.to_datetime(date_to)
        df_evo = df_evo[(df_evo['fecha_real'] >= start_date) & (df_evo['fecha_real'] <= end_date)].copy()
        df_evo = df_evo.drop(columns=['fecha_real'])
        
        # Estandarizar ID
        df_evo['id_reservation_id'] = df_evo['id_reservation_id'].astype(str).str.strip().str.upper()

        # === 2. PROCESAR VENTAS ===
        st.info("⏳ Procesando reportes de Ventas...")
        df_export_list = []
        for file in ventas_files:
            file.seek(0)
            try:
                temp_df = pd.read_csv(file, sep=',', encoding='utf-8-sig', on_bad_lines='skip')
                # Si el delimitador no era coma, intentar con punto y coma
                if len(temp_df.columns) < 2:
                    file.seek(0)
                    temp_df = pd.read_csv(file, sep=';', encoding='utf-8-sig', on_bad_lines='skip')
                
                # Estandarizar nombres de columnas del archivo de ventas
                temp_df.columns = temp_df.columns.astype(str).str.strip().str.replace('\ufeff', '')
                
                # Solo necesitamos Id Reserva e Id Pax
                if 'Id Reserva' in temp_df.columns and 'Id Pax' in temp_df.columns:
                    df_export_list.append(temp_df[['Id Reserva', 'Id Pax']])
            except Exception as e:
                st.warning(f"No se pudo procesar el archivo {file.name}: {e}")

        if not df_export_list:
            st.error("❌ No se encontraron columnas 'Id Reserva' ni 'Id Pax' en los archivos de ventas subidos.")
            st.stop()

        df_export = pd.concat(df_export_list, ignore_index=True)
        df_export = df_export.drop_duplicates(subset=['Id Reserva'])
        df_export['Id Reserva'] = df_export['Id Reserva'].astype(str).str.strip().str.upper()

        # === 3. CRUCE FINAL ===
        st.info("⏳ Cruzando datos y limpiando registros sin Id Pax...")
        df_final = pd.merge(df_evo, df_export, left_on='id_reservation_id', right_on='Id Reserva', how='left')
        
        # Eliminar las filas que no encontraron el Id Pax (Huérfanos)
        df_final = df_final.dropna(subset=['Id Pax'])
        
        # Limpiar columnas redundantes
        if 'Id Reserva' in df_final.columns:
            df_final = df_final.drop(columns=['Id Reserva'])

        st.success(f"✅ ¡Cruce completado! Se generaron {len(df_final)} registros exactos.")

        # === 4. MOSTRAR PREVIEW Y DESCARGAR ===
        st.dataframe(df_final.head(50), use_container_width=True)

        def to_excel(df):
            output = BytesIO()
            writer = pd.ExcelWriter(output, engine="xlsxwriter")
            df.to_excel(writer, index=False, sheet_name="Evolutivo_Enriquecido")
            writer.close()
            return output.getvalue()

        excel_bytes = to_excel(df_final)
        st.download_button(
            label="⬇ Descargar Excel Completo", 
            data=excel_bytes, 
            file_name="Cruce_Evolutivo_IdPax.xlsx", 
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

    except Exception as e:
        st.error(f"❌ Ocurrió un error inesperado durante el cruce: {e}")
