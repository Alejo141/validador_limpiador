import streamlit as st
import pandas as pd
import re
import unicodedata
from io import BytesIO

st.set_page_config(
    layout="wide",
    page_title="Validador y limpiador",
    page_icon="🔍"
)

st.title("🔍 Validador")

# Palabras clave para detectar columnas importantes
palabras_clave = [
    "marca", "serial", "serial interno", "nombre", "apellidos", "vereda",
    "municipio", "localidad", "nombre localidad", "departamento", "niu", "referencia"
]

# Columnas que deben ir en mayúscula
columnas_mayus = [
    "nombre", "apellidos", "vereda", "marca",
    "municipio", "localidad", "nombre localidad", "departamento"
]

def limpiar_texto(texto, convertir_mayuscula=False, nombre_columna=""):
    if pd.isnull(texto):
        return texto
    texto = str(texto).strip()

    columna_minus = nombre_columna.lower()
    if "serial interno" in columna_minus or "niu" in columna_minus or "referencia" in columna_minus:
        texto = re.sub(r"[^\w\s\-]", "", texto)  # permite guiones
    else:
        texto = re.sub(r"[^\w\s]", "", texto)

    texto = re.sub(r"\s{2,}", " ", texto)
    texto = unicodedata.normalize("NFD", texto).encode("ascii", "ignore").decode("utf-8")  # quitar tildes/ñ

    if convertir_mayuscula:
        texto = texto.upper()

    return texto.strip()

def detectar_errores(texto):
    errores = []
    if pd.isnull(texto):
        return errores
    texto = str(texto)
    if re.search(r"[^\w\s]", texto):
        errores.append("Caracter especial")
    if "ñ" in texto.lower():
        errores.append("Letra ñ")
    if re.search(r"[áéíóúÁÉÍÓÚ]", texto):
        errores.append("Tilde")
    if "." in texto:
        errores.append("Punto")
    if re.search(r"\s{2,}", texto):
        errores.append("Doble espacio")
    return errores

def corregir_duplicados(df, col_serial, col_niu):
    df = df.copy()

    # Paso 1: Normalizar seriales para búsqueda insensible a mayúsculas
    seriales_norm = df[col_serial].astype(str).str.lower()

    # Paso 2: Detectar duplicados ignorando mayúsculas
    duplicados_mask = seriales_norm.duplicated(keep=False)
    duplicados_df = df[duplicados_mask]

    ajustes_realizados = []

    if not duplicados_df.empty:
        st.warning("⚠️ Se encontraron duplicados en la columna de serial (sin distinguir mayúsculas):")
        st.dataframe(duplicados_df[[col_niu, col_serial]])

        contador = {}
        for idx in duplicados_df.index:
            original = df.at[idx, col_serial]
            original_norm = str(original).lower()

            if original_norm not in contador:
                contador[original_norm] = 1
            else:
                contador[original_norm] += 1

            nuevo_valor = f"{original}N{contador[original_norm]}"
            
            # Asegurar que el nuevo valor también sea único ignorando mayúsculas
            while nuevo_valor.lower() in df[col_serial].str.lower().values:
                contador[original_norm] += 1
                nuevo_valor = f"{original}N{contador[original_norm]}"
            
            df.at[idx, col_serial] = nuevo_valor

            ajustes_realizados.append({
                "NIU": df.at[idx, col_niu] if col_niu else "Desconocido",
                "Duplicado original": original,
                "Nuevo valor": nuevo_valor
            })
    else:
        st.success("✅ No se encontraron duplicados en la columna serial.")

    return df, ajustes_realizados


# Subir archivo
uploaded_file = st.file_uploader("📤 Carga un archivo Excel o CSV", type=["xlsx", "xls", "csv"])

if uploaded_file:
    ext = uploaded_file.name.split(".")[-1]
    if ext == "csv":
        df = pd.read_csv(uploaded_file)
    else:
        df = pd.read_excel(uploaded_file)

    # 👉 Solo convertir columnas que contengan "fecha" en el nombre
    for col in df.columns:
        if "fecha" in col.lower():
            try:
                df[col] = pd.to_datetime(df[col], errors="raise")
                df[col] = df[col].dt.strftime('%Y-%m-%d')
            except:
                st.warning(f"No se pudo convertir la columna '{col}' a formato fecha.")

    st.subheader("👀 Vista previa del archivo")
    st.dataframe(df.head())

    # Detectar columnas relevantes
    columnas_revisar = [col for col in df.columns if any(p in col.lower() for p in palabras_clave)]
    columnas_niu = [col for col in df.columns if "niu" in col.lower() or "referencia" in col.lower()]
    columnas_serial = [col for col in df.columns if "serial" in col.lower()]

    if columnas_revisar:
        st.subheader("🔍 Columnas identificadas para revisión:")
        st.write(columnas_revisar)

        resumen_errores = {}

        for col in columnas_revisar:
            resumen_errores[col] = []
            for i, valor in enumerate(df[col]):
                errores = detectar_errores(valor)
                if errores:
                    resumen_errores[col].append({
                        "fila": i + 2,
                        "valor": valor,
                        "errores": ", ".join(errores)
                    })

        for col, errores in resumen_errores.items():
            if errores:
                st.warning(f"⚠️ Errores en columna '{col}':")
                st.dataframe(pd.DataFrame(errores))
            else:
                st.success(f"✅ Sin errores en la columna '{col}'.")

        if st.button("🧼 Limpiar texto y convertir a mayúsculas (si aplica)"):
            for col in columnas_revisar:
                convertir = any(p in col.lower() for p in columnas_mayus)
                df[col] = df[col].apply(lambda x: limpiar_texto(x, convertir_mayuscula=convertir, nombre_columna=col))
            st.success("Texto limpiado correctamente ✅")

            # Detectar y corregir duplicados
            if columnas_serial:
                col_serial = columnas_serial[0]
                col_niu = columnas_niu[0] if columnas_niu else None
                df, ajustes = corregir_duplicados(df, col_serial, col_niu)

                if ajustes:
                    st.warning("♻️ Se detectaron duplicados en serial y fueron corregidos:")
                    st.dataframe(pd.DataFrame(ajustes))
                else:
                    st.success("✅ No se encontraron duplicados en la columna serial.")

            st.subheader("📄 Vista previa del archivo limpio")
            st.dataframe(df.head())

            # Descargar archivos
            output_excel = BytesIO()
            df.to_excel(output_excel, index=False, engine="openpyxl")
            output_excel.seek(0)
            output_csv = df.to_csv(index=False).encode("utf-8")

            col1, col2 = st.columns(2)
            with col1:
                st.download_button(
                    label="⬇️ Descargar como Excel",
                    data=output_excel,
                    file_name="archivo_limpio.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
            with col2:
                st.download_button(
                    label="⬇️ Descargar como CSV",
                    data=output_csv,
                    file_name="archivo_limpio.csv",
                    mime="text/csv"
                )
    else:
        st.info("ℹ️ No se encontraron columnas relacionadas con serial, nombre, vereda, municipio o similares.")
