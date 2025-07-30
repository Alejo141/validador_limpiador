import streamlit as st
import pandas as pd
import re
import unicodedata
from io import BytesIO

st.set_page_config(
    layout="wide",        # 🔁 Esto activa el ancho completo
    page_title="Validador y limpiador", 
    page_icon="🔍"
)

st.title("🔍 Validador")

# Palabras clave para detectar columnas importantes
palabras_clave = [
    "marca", "serial", "serial interno", "nombre", "apellidos", "vereda",
    "municipio", "localidad", "nombre localidad", "departamento", "niu", "referencia"
]

# Columnas que se deben convertir a mayúsculas
columnas_mayus = [
    "nombre", "apellidos", "vereda", "marca",
    "municipio", "localidad", "nombre localidad", "departamento"
]

def limpiar_texto(texto, convertir_mayuscula=False, nombre_columna=""):
    if pd.isnull(texto):
        return texto
    texto = str(texto).strip()  # elimina espacios al inicio/final

    # Conservar guion solo si es 'serial interno'
    columna_minus = nombre_columna.lower()
    if "serial interno" in columna_minus or "niu" in columna_minus or "referencia" in columna_minus:
        texto = re.sub(r"[^\w\s\-]", "", texto)  # permite letras, números, guion y espacio
    else:
        texto = re.sub(r"[^\w\s]", "", texto)    # quitar todo lo que no sea letra, número o espacio

    texto = re.sub(r"\s{2,}", " ", texto)  # quitar dobles espacios
    texto = unicodedata.normalize("NFD", texto).encode("ascii", "ignore").decode("utf-8")  # quitar tildes y ñ

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
    duplicados = df[df.duplicated(subset=[col_serial], keep=False)]
    ajustes_realizados = []

    if not duplicados.empty:
        contador = {}
        for idx, row in duplicados.iterrows():
            valor = row[col_serial]
            if valor not in contador:
                contador[valor] = 1
            else:
                contador[valor] += 1
            nuevo_valor = f"{valor}N{contador[valor]}"
            while nuevo_valor in df[col_serial].values:
                contador[valor] += 1
                nuevo_valor = f"{valor}N{contador[valor]}"
            df.at[idx, col_serial] = nuevo_valor
            ajustes_realizados.append({
                "NIU": row[col_niu] if col_niu else "Desconocido",
                "Duplicado original": valor,
                "Nuevo valor": nuevo_valor
            })
    return df, ajustes_realizados

# Subir archivo
uploaded_file = st.file_uploader("📤 Carga un archivo Excel o CSV", type=["xlsx", "xls", "csv"])

if uploaded_file:
    ext = uploaded_file.name.split(".")[-1]
    if ext == "csv":
        df = pd.read_csv(uploaded_file)
    else:
        df = pd.read_excel(uploaded_file)

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

        # Botón para limpiar y convertir
        if st.button("🧼 Limpiar texto y convertir a mayúsculas (si aplica)"):
            for col in columnas_revisar:
                convertir = any(p in col.lower() for p in columnas_mayus)
                df[col] = df[col].apply(lambda x: limpiar_texto(x, convertir_mayuscula=convertir, nombre_columna=col))
            st.success("Texto limpiado correctamente ✅")

            # Detectar y corregir duplicados en seriales
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

            # Opciones de descarga
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
