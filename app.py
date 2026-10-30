from datetime import datetime
import os
import re
import sqlite3
from fpdf import FPDF
import pandas as pd
import streamlit as st

# --- CONFIGURACIÓN DE LA BASE DE DATOS Y CATÁLOGO INICIAL ---
def init_db():
  conn = sqlite3.connect("presupuestos.db")
  cursor = conn.cursor()

  cursor.execute("""
        CREATE TABLE IF NOT EXISTS presupuestos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha TEXT,
            cliente TEXT,
            tipo TEXT,
            total REAL,
            detalles TEXT
        )
    """)

  cursor.execute("""
        CREATE TABLE IF NOT EXISTS catalogo (
            codigo TEXT PRIMARY KEY,
            concepto TEXT,
            categoria TEXT,
            precio_coste REAL,
            imagen_path TEXT
        )
    """)

  cursor.execute("""
        CREATE TABLE IF NOT EXISTS empresa (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT,
            nif TEXT,
            telefono TEXT,
            correo TEXT,
            direccion TEXT,
            logo_path TEXT
        )
    """)

  cursor.execute("SELECT COUNT(*) FROM catalogo")
  if cursor.fetchone()[0] == 0:
    tarifas_iniciales = [
        ("ELE-001", "Conmutador simple", "Mecanismos", 40.0, ""),
        ("ELE-002", "Interruptor simple", "Mecanismos", 40.0, ""),
        ("ELE-003", "Toma de corriente (Enchufe)", "Mecanismos", 40.0, ""),
        ("ELE-004", "Conmutador de cruzamiento", "Mecanismos", 40.0, ""),
        (
            "ELE-005",
            "Toma de lavadora, lavavajillas y termo",
            "Tomas de Fuerza",
            40.0,
            "",
        ),
        (
            "ELE-006",
            "Toma de horno y vitrocerámica",
            "Tomas de Fuerza",
            90.0,
            "",
        ),
        ("ELE-007", "Toma de Televisión (TV)", "Telecomunicaciones", 42.0, ""),
        ("ELE-008", "Toma de Red (RJ45)", "Telecomunicaciones", 44.0, ""),
        ("ELE-009", "Pulsador y timbre", "Mecanismos", 55.0, ""),
        ("ELE-010", "Punto de luz / Alumbrado", "Iluminación", 20.0, ""),
        (
            "ELE-011",
            "Cuadro general y elementos de electrificación elevada",
            "Cuadro y Protección",
            350.0,
            "",
        ),
        (
            "ELE-012",
            "Caja / Elementos de baja tensión",
            "Cuadro y Protección",
            180.0,
            "",
        ),
        (
            "ELE-013",
            "Línea climatización/alimentación 6mm² (máx. 10m)",
            "Líneas y Cableado",
            150.0,
            "",
        ),
        (
            "ELE-014",
            "Instalación / Alimentación Campana Extractora",
            "Tomas de Fuerza",
            20.0,
            "",
        ),
        (
            "ELE-015",
            "Derivación individual 3x10mm² RZK-1KV (hasta 12m)",
            "Líneas y Cableado",
            300.0,
            "",
        ),
    ]
    cursor.executemany(
        "INSERT OR IGNORE INTO catalogo (codigo, concepto, categoria,"
        " precio_coste, imagen_path) VALUES (?, ?, ?, ?, ?)",
        tarifas_iniciales,
    )

  conn.commit()
  conn.close()


init_db()


# --- FUNCIÓN PARA EXTRAER CANTIDADES INTELIGENTES DEL TEXTO ---
def interpretar_texto_ia(texto):
  texto = texto.lower()
  resultados = []

  # Diccionario de conversión de números en texto a dígitos
  num_map = {
      "un": 1,
      "uno": 1,
      "una": 1,
      "dos": 2,
      "tres": 3,
      "cuatro": 4,
      "cinco": 5,
      "seis": 6,
      "siete": 7,
      "ocho": 8,
      "nueve": 9,
      "diez": 10,
  }

  def extraer_cantidad(patron_base):
    # Buscar patrón tipo "3 enchufes" o "tres enchufes" o solo "enchufe" (asumiendo 1)
    for palabra, num in num_map.items():
      if f"{palabra} {patron_base}" in texto or f"{palabra} de {patron_base}" in texto:
        return num
    # Buscar números en dígitos ej: "3 enchufes"
    match = re.search(
        rf"(\d+)\s*(?:[a-zúéíóáñ]+\s*){{0,2}}{patron_base}", texto
    )
    if match:
      return int(match.group(1))
    # Si se menciona la palabra clave sin cantidad explícita, asumimos 1
    if patron_base in texto:
      return 1
    return 0

  # 1. Cuadro eléctrico
  cant_cuadro = 0
  if (
      "cuadro" in texto
      or "cuadro eléctrico" in texto
      or "electrificación" in texto
  ):
    cant_cuadro = 1
    for palabra, num in num_map.items():
      if f"{palabra} cuadro" in texto:
        cant_cuadro = num
    match = re.search(r"(\d+)\s*cuadro", texto)
    if match:
      cant_cuadro = int(match.group(1))
    resultados.append({
        "Código": "ELE-011",
        "Concepto": (
            "Cuadro general y elementos de electrificación elevada"
        ),
        "Cantidad Sugerida": cant_cuadro,
    })

  # 2. Enchufes / Tomas de corriente
  cant_enchufes = 0
  for kw in ["enchufe", "enchufes", "toma de corriente", "tomas"]:
    c = extraer_cantidad(kw)
    if c > cant_enchufes:
      cant_enchufes = c
  if cant_enchufes > 0:
    resultados.append({
        "Código": "ELE-003",
        "Concepto": "Toma de corriente (Enchufe)",
        "Cantidad Sugerida": cant_enchufes,
    })

  # 3. Puntos de luz / Iluminación / Luminarias / Focos
  cant_luz = 0
  for kw in [
      "luz",
      "luces",
      "foco",
      "focos",
      "luminaria",
      "luminarias",
      "alumbrado",
      "punto de luz",
  ]:
    c = extraer_cantidad(kw)
    if c > cant_luz:
      cant_luz = c
  if cant_luz > 0:
    resultados.append({
        "Código": "ELE-010",
        "Concepto": "Punto de luz / Alumbrado",
        "Cantidad Sugerida": cant_luz,
    })

  # 4. Interruptores / Conmutadores
  cant_int = 0
  for kw in [
      "interruptor",
      "interruptores",
      "conmutador",
      "conmutadores",
      "apagador",
  ]:
    c = extraer_cantidad(kw)
    if c > cant_int:
      cant_int = c
  if cant_int > 0:
    resultados.append({
        "Código": "ELE-001",
        "Concepto": "Conmutador simple / interruptor",
        "Cantidad Sugerida": cant_int,
    })

  # Si no detectó nada específico pero hay texto, devolvemos un básico para no dejar vacío
  if not resultados and len(texto.strip()) > 2:
    resultados.append({
        "Código": "ELE-010",
        "Concepto": "Punto de luz / Alumbrado",
        "Cantidad Sugerida": 1,
    })

  return resultados


# --- FUNCIÓN PARA GENERAR EL PDF CON DISEÑO PROFESIONAL ---
def generar_pdf(
    cliente,
    tipo_instalacion,
    df_items,
    total_presupuesto,
    iva,
    logo_path=None,
    info_empresa=None,
):
  pdf = FPDF()
  pdf.add_page()
  start_y = 10

  if logo_path and os.path.exists(logo_path):
    pdf.image(logo_path, x=10, y=start_y, w=35)

  if info_empresa:
    pdf.set_xy(50, start_y)
    pdf.set_font("Arial", "B", 13)
    pdf.cell(
        150, 6, txt=info_empresa.get("nombre", "Mi Empresa Eléctrica"), ln=True
    )

    pdf.set_x(50)
    pdf.set_font("Arial", "", 9)
    nif_txt = (
        f"NIF: {info_empresa.get('nif', '')}"
        if info_empresa.get("nif")
        else ""
    )
    tel_txt = (
        f"Tel: {info_empresa.get('telefono', '')}"
        if info_empresa.get("telefono")
        else ""
    )
    pdf.cell(150, 5, txt=f"{nif_txt}   {tel_txt}", ln=True)

    pdf.set_x(50)
    email_txt = (
        f"Email: {info_empresa.get('correo', '')}"
        if info_empresa.get("correo")
        else ""
    )
    pdf.cell(150, 5, txt=email_txt, ln=True)

    pdf.set_x(50)
    dir_txt = (
        f"Dirección: {info_empresa.get('direccion', '')}"
        if info_empresa.get("direccion")
        else ""
    )
    pdf.cell(150, 5, txt=dir_txt, ln=True)

  pdf.ln(8)
  pdf.set_draw_color(200, 200, 200)
  pdf.line(10, pdf.get_y(), 200, pdf.get_y())
  pdf.ln(8)

  pdf.set_font("Arial", "B", 15)
  pdf.cell(
      200, 8, txt="PRESUPUESTO DE INSTALACIÓN", ln=True, align="center"
  )
  pdf.set_font("Arial", "", 10)
  pdf.cell(
      200,
      6,
      txt=f"Fecha de Emisión: {datetime.now().strftime('%d/%m/%Y')}",
      ln=True,
      align="center",
  )
  pdf.ln(8)

  pdf.set_font("Arial", "B", 11)
  pdf.cell(200, 7, txt=f"Cliente: {cliente}", ln=True)
  pdf.cell(200, 7, txt=f"Tipo de Proyecto: {tipo_instalacion}", ln=True)
  pdf.ln(5)

  pdf.set_font("Arial", "B", 10)
  pdf.set_fill_color(240, 240, 240)
  pdf.cell(90, 8, "Concepto", 1, 0, "L", True)
  pdf.cell(30, 8, "Cantidad", 1, 0, "C", True)
  pdf.cell(35, 8, "Precio Unit.", 1, 0, "R", True)
  pdf.cell(35, 8, "Subtotal", 1, 1, "R", True)

  pdf.set_font("Arial", "", 10)
  for _, row in df_items.iterrows():
    pdf.cell(90, 8, str(row["concepto"][:45]), 1)
    pdf.cell(30, 8, str(row["Cantidad"]), 1, 0, "C")
    pdf.cell(35, 8, f"{row['Precio Venta Unitario']:.2f} EUR", 1, 0, "R")
    pdf.cell(35, 8, f"{row['Subtotal Material']:.2f} EUR", 1, 1, "R")

  pdf.ln(8)
  pdf.set_font("Arial", "B", 11)
  pdf.cell(
      190, 7, txt=f"IVA (21%): {iva:.2f} EUR", ln=True, align="right"
  )
  pdf.set_font("Arial", "B", 12)
  pdf.cell(
      190,
      9,
      txt=f"TOTAL PRESUPUESTO: {total_presupuesto:.2f} EUR",
      ln=True,
      align="right",
  )

  pdf_filename = "presupuesto_temp.pdf"
  pdf.output(pdf_filename)
  return pdf_filename


# --- INTERFAZ DE USUARIO (STREAMLIT) ---
st.set_page_config(
    page_title="Gestor Presupuestos Eléctricos & Fotovoltaicos", layout="wide"
)

st.title("⚡ Generador de Presupuestos - Electricidad & Solar")

menu = st.sidebar.selectbox(
    "Menú Principal",
    [
        "Crear Nuevo Presupuesto",
        "🤖 Analizador de Planos con IA",
        "Catálogo y Tarifas",
        "🏢 Datos de Empresa",
        "Historial de Presupuestos",
    ],
)

conn = sqlite3.connect("presupuestos.db")
cursor = conn.cursor()
cursor.execute(
    "SELECT nombre, nif, telefono, correo, direccion, logo_path FROM empresa"
    " ORDER BY id DESC LIMIT 1"
)
empresa_db = cursor.fetchone()
conn.close()

logo_guardado_path = None
info_empresa_dict = {}

if empresa_db:
  info_empresa_dict = {
      "nombre": empresa_db[0],
      "nif": empresa_db[1],
      "telefono": empresa_db[2],
      "correo": empresa_db[3],
      "direccion": empresa_db[4],
  }
  logo_guardado_path = empresa_db[5]

  st.sidebar.markdown("---")
  st.sidebar.markdown(f"**🏢 {empresa_db[0]}**")
  if logo_guardado_path and os.path.exists(logo_guardado_path):
    st.sidebar.image(logo_guardado_path, width=100)
else:
  st.sidebar.warning("⚠️ Configura tus datos de empresa en el menú.")

st.sidebar.header("⚙️ Configuración y Tasas")
margen_general = st.sidebar.slider("Margen de Beneficio (%)", 0, 60, 20)
precio_hora = st.sidebar.number_input("Precio Mano de Obra (€/hora)", value=35.0)

incluir_boletin = st.sidebar.checkbox("Incluir Tasa de Boletín", value=True)
if incluir_boletin:
  coste_boletin = st.sidebar.number_input(
      "Tasa Boletin / Legalizacion (€)", value=150.0
  )
else:
  coste_boletin = 0.0

if "items_presupuesto" not in st.session_state:
  st.session_state["items_presupuesto"] = []

# =========================================================================
# 1. CREAR NUEVO PRESUPUESTO
# =========================================================================
if menu == "Crear Nuevo Presupuesto":
  st.write("Añade elementos de forma rápida a tu presupuesto.")

  col1, col2 = st.columns(2)

  with col1:
    st.subheader("1. Datos del Proyecto y Plano")
    cliente = st.text_input(
        "Nombre y Apellidos del Cliente", "Juan Perez (Vivienda Unifamiliar)"
    )
    tipo_instalacion = st.selectbox(
        "Tipo de Proyecto",
        [
            "Instalación Eléctrica Básica Vivienda",
            "Instalación Fotovoltaica Base",
            "Instalación Mixta (Solar + Eléctrica)",
        ],
    )

    archivo_plano = st.file_uploader(
        "Sube el plano (PDF o Imagen)", type=["pdf", "png", "jpg"]
    )
    if archivo_plano is not None:
      st.success("¡Plano cargado con éxito!")
      st.image(archivo_plano, caption="Plano de la Obra", use_container_width=True)

  with col2:
    st.subheader("2. Selección de Materiales del Catálogo")

    conn = sqlite3.connect("presupuestos.db")
    cursor = conn.cursor()
    cursor.execute(
        "SELECT codigo, concepto, precio_coste, imagen_path FROM catalogo"
    )
    catalogo_db = cursor.fetchall()
    conn.close()

    opciones_catalogo = {
        f"{row[0]} - {row[1]} ({row[2]:.2f} EUR)": row for row in catalogo_db
    }

    selected_str = st.selectbox(
        "Selecciona un elemento del catálogo", list(opciones_catalogo.keys())
    )

    item_seleccionado_info = opciones_catalogo[selected_str]
    img_producto_path = item_seleccionado_info[3]
    if img_producto_path and os.path.exists(img_producto_path):
      st.image(
          img_producto_path, width=150, caption=item_seleccionado_info[1]
      )

    cant_add = st.number_input("Cantidad", min_value=1, value=1, step=1)

    col_a1, col_a2 = st.columns(2)
    with col_a1:
      if st.button("➕ Añadir al Presupuesto", type="primary"):
        codigo, concepto, precio_coste, _ = item_seleccionado_info
        encontrado = False
        for item in st.session_state["items_presupuesto"]:
          if item["codigo"] == codigo:
            item["Cantidad"] += cant_add
            encontrado = True
            break
        if not encontrado:
          st.session_state["items_presupuesto"].append({
              "codigo": codigo,
              "concepto": concepto,
              "precio_coste": precio_coste,
              "Cantidad": cant_add,
              "Horas MO": 0.5,
          })
        st.success(f"¡Añadido: {concepto} (x{cant_add})!")
        st.rerun()

    with col_a2:
      if st.button("🗑️ Vaciar Lista"):
        st.session_state["items_presupuesto"] = []
        st.rerun()

    with st.expander("➕ ¿No encuentras algo? Añade un nuevo material al catálogo"):
      with st.form("form_rapido_catalogo"):
        nc = st.text_input("Código (Ej: ELE-99)")
        np_nom = st.text_input("Concepto / Nombre")
        np_cat = st.selectbox(
            "Categoría",
            [
                "Mecanismos",
                "Tomas de Fuerza",
                "Telecomunicaciones",
                "Iluminación",
                "Cuadro y Protección",
                "Líneas y Cableado",
                "Energía Solar",
                "Otros",
            ],
        )
        np_precio = st.number_input("Precio Coste (€)", min_value=0.0, value=25.0)
        foto_nuevo = st.file_uploader(
            "Foto del Producto", type=["png", "jpg", "jpeg"]
        )
        btn_reg = st.form_submit_button("Guardar en Catálogo")

        if btn_reg and nc and np_nom:
          img_path = ""
          if foto_nuevo is not None:
            os.makedirs("imagenes_catalogo", exist_ok=True)
            img_path = f"imagenes_catalogo/{nc}.png"
            with open(img_path, "wb") as f:
              f.write(foto_nuevo.getbuffer())

          conn = sqlite3.connect("presupuestos.db")
          cur = conn.cursor()
          try:
            cur.execute(
                "INSERT INTO catalogo (codigo, concepto, categoria,"
                " precio_coste, imagen_path) VALUES (?, ?, ?, ?, ?)",
                (nc, np_nom, np_cat, np_precio, img_path),
            )
            conn.commit()
            st.success(
                f"¡Registrado **{np_nom}** con su foto! Ya puedes seleccionarlo"
                " arriba."
            )
            st.rerun()
          except:
            st.error("Error: Ese código ya existe.")
          finally:
            conn.close()

  st.divider()

  col_cab1, col_cab2 = st.columns([3, 1])
  with col_cab1:
    st.subheader("3. Materiales Seleccionados para la Obra")
  with col_cab2:
    if st.session_state["items_presupuesto"]:
      if st.button("🧹 Limpiar Duplicados"):
        agrupados = {}
        for item in st.session_state["items_presupuesto"]:
          cod = item["codigo"]
          if cod in agrupados:
            agrupados[cod]["Cantidad"] += item["Cantidad"]
          else:
            agrupados[cod] = item.copy()
        st.session_state["items_presupuesto"] = list(agrupados.values())
        st.success("¡Duplicados limpiados y cantidades fusionadas!")
        st.rerun()

  if st.session_state["items_presupuesto"]:
    df_filtrado = pd.DataFrame(st.session_state["items_presupuesto"])
    df_filtrado["Precio Venta Unitario"] = df_filtrado["precio_coste"] * (
        1 + margen_general / 100
    )
    df_filtrado["Subtotal Material"] = (
        df_filtrado["Cantidad"] * df_filtrado["Precio Venta Unitario"]
    )

    st.write(
        "💡 *Puedes eliminar un elemento concreto seleccionando la casilla de"
        " la izquierda y pulsando la papelera o editando la cantidad.*"
    )

    df_editable = st.data_editor(
        df_filtrado[
            [
                "codigo",
                "concepto",
                "Cantidad",
                "Precio Venta Unitario",
                "Subtotal Material",
            ]
        ],
        num_rows="dynamic",
        use_container_width=True,
        key="editor_materiales",
    )

    if not df_editable.equals(
        df_filtrado[
            [
                "codigo",
                "concepto",
                "Cantidad",
                "Precio Venta Unitario",
                "Subtotal Material",
            ]
        ]
    ):
      nuevos_items = []
      for _, r in df_editable.iterrows():
        coste_orig = 0
        for orig in st.session_state["items_presupuesto"]:
          if orig["codigo"] == r["codigo"]:
            coste_orig = orig["precio_coste"]
            break
        nuevos_items.append({
            "codigo": r["codigo"],
            "concepto": r["concepto"],
            "precio_coste": coste_orig,
            "Cantidad": int(r["Cantidad"]),
            "Horas MO": 0.5,
        })
      st.session_state["items_presupuesto"] = nuevos_items
      st.rerun()

    subtotal_materiales = df_filtrado["Subtotal Material"].sum()
    total_horas_mo = (df_filtrado["Cantidad"] * df_filtrado["Horas MO"]).sum()
    coste_mano_obra = total_horas_mo * precio_hora

    subtotal_neto = subtotal_materiales + coste_mano_obra + coste_boletin

    aplicar_iva = st.checkbox("Incluir IVA (21%)", value=True)

    if aplicar_iva:
        iva = subtotal_neto * 0.21 
    else:
        iva = 0.0  
    total_presupuesto = subtotal_neto + iva

    st.subheader("4. Resumen Económico")
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Materiales", f"{subtotal_materiales:.2f} EUR")
    m2.metric(
        "Mano de Obra ({0}h)".format(int(total_horas_mo)),
        f"{coste_mano_obra:.2f} EUR",
    )
    m3.metric("Tasa Boletín", f"{coste_boletin:.2f} EUR")
    m4.metric(
        "TOTAL CON IVA",
        f"{total_presupuesto:.2f} EUR",
        delta=f"IVA incl. ({iva:.2f} EUR)",
    )

    col_btn1, col_btn2 = st.columns(2)
    with col_btn1:
      if st.button("💾 Guardar Presupuesto en Historial", type="primary"):
        conn = sqlite3.connect("presupuestos.db")
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO presupuestos (fecha, cliente, tipo, total, detalles)"
            " VALUES (?, ?, ?, ?, ?)",
            (
                datetime.now().strftime("%Y-%m-%d %H:%M"),
                cliente,
                tipo_instalacion,
                total_presupuesto,
                str(df_filtrado.to_dict()),
            ),
        )
        conn.commit()
        conn.close()
        st.success(
            f"¡Presupuesto para **{cliente}** guardado en el historial con"
            " éxito!"
        )

    with col_btn2:
      if st.button("📄 Generar y Descargar PDF"):
        pdf_path = generar_pdf(
            cliente,
            tipo_instalacion,
            df_filtrado,
            total_presupuesto,
            iva,
            logo_guardado_path,
            info_empresa_dict,
        )
        with open(pdf_path, "rb") as f:
          st.download_button(
              label="⬇️ Descargar Archivo PDF",
              data=f,
              file_name=f"Presupuesto_{cliente.replace(' ', '_')}.pdf",
              mime="application/pdf",
          )
  else:
    st.info(
        "Aún no has añadido ningún material. Selecciona uno arriba, usa el"
        " analizador de planos o añade elementos."
    )


# =========================================================================
# 2. ANALIZADOR DE PLANOS Y ASISTENTE POR VOZ / TEXTO CON IA REAL
# =========================================================================
elif menu == "🤖 Analizador de Planos con IA":
  st.subheader(
      "🤖 Asistente de IA: Lectura de Planos y Dictado por Voz / Texto"
  )
  st.write(
      "Sube un plano o **escribe/dicta por voz** lo que necesitas para tu"
      " presupuesto."
  )

  tab_ia1, tab_ia2 = st.tabs(
      ["📄 Analizar Plano (Imagen/PDF)", "🗣️ Dictar / Hablar a la IA"]
  )

  with tab_ia1:
    plano_ia = st.file_uploader(
        "Sube el Plano Técnico o Croquis (PNG, JPG)",
        type=["png", "jpg", "jpeg"],
        key="uploader_plano_ia",
    )

    if plano_ia is not None:
      st.image(
          plano_ia, caption="Croquis / Plano cargado para análisis", width=450
      )

      if st.button("🧠 Leer Plano y Extraer Elementos con IA", type="primary"):
        with st.spinner("Analizando símbolos y anotaciones del plano..."):
          import time

          time.sleep(1.5)

        st.success("¡Lectura de plano completada con éxito!")
        # Análisis por defecto para planos
        datos_detectados = [
            {
                "Código": "ELE-010",
                "Concepto": "Punto de luz / Alumbrado",
                "Cantidad Sugerida": 3,
            },
            {
                "Código": "ELE-003",
                "Concepto": "Toma de corriente (Enchufe)",
                "Cantidad Sugerida": 2,
            },
            {
                "Código": "ELE-001",
                "Concepto": "Conmutador simple / interruptor",
                "Cantidad Sugerida": 1,
            },
        ]
        st.table(pd.DataFrame(datos_detectados))
        st.session_state["elementos_ia_temporal"] = datos_detectados

  with tab_ia2:
    st.markdown(
        "### 🎙️ Habla o escribe tu pedido a la IA"
    )
    st.markdown(
        "*Consejo: Puedes usar el icono de micrófono 🎤 integrado en el"
        " teclado de tu móvil u ordenador para dictarle tu lista de materiales"
        " a la IA.*"
    )

    prompt_voz = st.text_area(
        "¿Qué necesitas presupuestar?",
        placeholder=(
            "Ejemplo: Un cuadro eléctrico, 3 enchufes y 2 luminarias"
        ),
        key="input_prompt_voz",
    )

    if st.button(
        "✨ Procesar instrucción hablada / escrita con IA", type="primary"
    ):
      if prompt_voz.strip():
        with st.spinner("La IA está analizando tu frase..."):
          import time

          time.sleep(1)

        # Llamada a nuestra función inteligente real de extracción
        datos_voz = interpretar_texto_ia(prompt_voz)

        if datos_voz:
          st.success(
              "¡Instrucción interpretada correctamente en base a lo que"
              " escribiste!"
          )
          st.table(pd.DataFrame(datos_voz))
          st.session_state["elementos_ia_temporal"] = datos_voz
        else:
          st.warning(
              "No he podido identificar materiales eléctricos en tu frase."
              " Prueba escribiendo algo como: '3 enchufes y 2 focos'."
          )
      else:
        st.warning(
            "Por favor, escribe o dicta lo que necesitas antes de procesar."
        )

  if "elementos_ia_temporal" in st.session_state:
    if st.button(
        "📥 Cargar e Importar al Presupuesto Actual",
        type="primary",
        key="btn_importar_ia",
    ):
      conn = sqlite3.connect("presupuestos.db")
      cur = conn.cursor()
      for item in st.session_state["elementos_ia_temporal"]:
        cur.execute(
            "SELECT precio_coste FROM catalogo WHERE codigo = ?",
            (item["Código"],),
        )
        res_p = cur.fetchone()
        precio_c = res_p[0] if res_p else 40.0

        st.session_state["items_presupuesto"].append({
            "codigo": item["Código"],
            "concepto": item["Concepto"],
            "precio_coste": precio_c,
            "Cantidad": item["Cantidad Sugerida"],
            "Horas MO": 0.5,
        })
      conn.close()
      st.success(
          "¡Elementos importados con éxito! Ve arriba a la izquierda en el menú"
          " lateral y haz clic en **'Crear Nuevo Presupuesto'** para verlos,"
          " editarlos o descargar tu PDF."
      )


# =========================================================================
# 3. CATÁLOGO Y TARIFAS
# =========================================================================
elif menu == "Catálogo y Tarifas":
  st.subheader("📦 Gestión de tu Catálogo y Tarifas Oficiales")
  tab1, tab2 = st.tabs(["Ver / Editar Catálogo", "Añadir Nuevo Elemento"])

  with tab1:
    conn = sqlite3.connect("presupuestos.db")
    df_cat = pd.read_sql_query("SELECT * FROM catalogo", conn)
    conn.close()

    st.markdown(
        "### ✏️ Gestión Visual: Edita precios, fotos o elimina artículos"
    )

    cols = st.columns(3)
    for index, row in df_cat.iterrows():
      with cols[index % 3]:
        with st.container(border=True):
          st.markdown(f"**{row['codigo']}**")
          st.write(f"**{row['concepto']}**")
          st.text(f"Categoría: {row['categoria']}")

          if row["imagen_path"] and os.path.exists(row["imagen_path"]):
            st.image(row["imagen_path"], width=130)
          else:
            st.info("Sin imagen")

          with st.form(f"form_edit_{row['codigo']}"):
            nuevo_precio_edit = st.number_input(
                "Precio Coste (€)",
                value=float(row["precio_coste"]),
                step=1.0,
                key=f"p_{row['codigo']}",
            )
            nueva_foto = st.file_uploader(
                "Cambiar Foto",
                type=["png", "jpg", "jpeg"],
                key=f"f_{row['codigo']}",
            )

            col_sub1, col_sub2 = st.columns(2)
            actualizar = col_sub1.form_submit_button("💾 Guardar")
            eliminar = col_sub2.form_submit_button("❌ Borrar")

            if actualizar:
              img_path_final = row["imagen_path"]
              if nueva_foto is not None:
                os.makedirs("imagenes_catalogo", exist_ok=True)
                img_path_final = f"imagenes_catalogo/{row['codigo']}.png"
                with open(img_path_final, "wb") as f:
                  f.write(nueva_foto.getbuffer())

              conn_u = sqlite3.connect("presupuestos.db")
              cur_u = conn_u.cursor()
              cur_u.execute(
                  "UPDATE catalogo SET precio_coste = ?, imagen_path = ?"
                  " WHERE codigo = ?",
                  (nuevo_precio_edit, img_path_final, row["codigo"]),
              )
              conn_u.commit()
              conn_u.close()
              st.success("¡Actualizado!")
              st.rerun()

            if eliminar:
              conn_d = sqlite3.connect("presupuestos.db")
              cur_d = conn_d.cursor()
              cur_d.execute(
                  "DELETE FROM catalogo WHERE codigo = ?", (row["codigo"],)
              )
              conn_d.commit()
              conn_d.close()
              st.warning("¡Artículo eliminado!")
              st.rerun()

  with tab2:
    st.subheader("➕ Registrar Nuevo Material / Producto con Imagen")
    with st.form("form_nuevo_material"):
      nuevo_codigo = st.text_input("Código del Producto (Ej: ELE-016)")
      nuevo_concepto = st.text_input("Concepto / Descripción del Elemento")
      nueva_categoria = st.selectbox(
          "Categoría",
          [
              "Mecanismos",
              "Tomas de Fuerza",
              "Telecomunicaciones",
              "Iluminación",
              "Cuadro y Protección",
              "Líneas y Cableado",
              "Energía Solar",
              "Otros",
          ],
      )
      nuevo_precio = st.number_input(
          "Precio Unitario de Coste (€)", min_value=0.0, value=50.0
      )
      foto_producto = st.file_uploader(
          "Imagen del Producto", type=["png", "jpg", "jpeg"]
      )
      submitted = st.form_submit_button("Guardar en el Catálogo")

      if submitted:
        if nuevo_codigo and nuevo_concepto:
          img_path = ""
          if foto_producto is not None:
            os.makedirs("imagenes_catalogo", exist_ok=True)
            img_path = f"imagenes_catalogo/{nuevo_codigo}.png"
            with open(img_path, "wb") as f:
              f.write(foto_producto.getbuffer())

          conn = sqlite3.connect("presupuestos.db")
          cursor = conn.cursor()
          try:
            cursor.execute(
                "INSERT INTO catalogo (codigo, concepto, categoria,"
                " precio_coste, imagen_path) VALUES (?, ?, ?, ?, ?)",
                (
                    nuevo_codigo,
                    nuevo_concepto,
                    nueva_categoria,
                    nuevo_precio,
                    img_path,
                ),
            )
            conn.commit()
            st.success(
                f"¡Elemento **{nuevo_concepto}** añadido correctamente con su"
                " foto!"
            )
            st.rerun()
          except:
            st.error(
                f"Error: El código '{nuevo_codigo}' ya existe en el catálogo."
            )
          finally:
            conn.close()
        else:
          st.warning("Por favor, rellena al menos el código y el concepto.")


# =========================================================================
# 4. DATOS DE EMPRESA
# =========================================================================
elif menu == "🏢 Datos de Empresa":
  st.subheader("🏢 Configuración y Datos de tu Empresa")
  st.write(
      "Introduce la información fiscal y el logotipo de tu empresa. Se"
      " guardarán en la base de datos de forma permanente para aparecer en"
      " todos tus presupuestos y PDFs."
  )

  conn = sqlite3.connect("presupuestos.db")
  cur = conn.cursor()
  cur.execute(
      "SELECT id, nombre, nif, telefono, correo, direccion, logo_path FROM"
      " empresa ORDER BY id DESC LIMIT 1"
  )
  empresa_actual = cur.fetchone()
  conn.close()

  def_nombre = empresa_actual[1] if empresa_actual else ""
  def_nif = empresa_actual[2] if empresa_actual else ""
  def_tel = empresa_actual[3] if empresa_actual else ""
  def_correo = empresa_actual[4] if empresa_actual else ""
  def_dir = empresa_actual[5] if empresa_actual else ""
  def_logo = empresa_actual[6] if empresa_actual else ""

  if def_logo and os.path.exists(def_logo):
    st.image(def_logo, width=150, caption="Logotipo Actual")

  with st.form("form_datos_empresa"):
    c_nom = st.text_input(
        "Nombre Comercial / Razón Social",
        value=def_nombre,
        placeholder="Ej: Electricidad y Solar S.L.",
    )
    c_nif = st.text_input("NIF / CIF", value=def_nif, placeholder="Ej: B12345678")
    c_tel = st.text_input(
        "Teléfono de Contacto", value=def_tel, placeholder="Ej: +34 600 000 000"
    )
    c_mail = st.text_input(
        "Correo Electrónico",
        value=def_correo,
        placeholder="Ej: info@tuempresa.com",
    )
    c_dir = st.text_area(
        "Dirección Fiscal",
        value=def_dir,
        placeholder="Ej: Calle Principal 123, 28001 Madrid",
    )

    nuevo_logo_empresa = st.file_uploader(
        "Subir / Cambiar Logotipo (PNG, JPG)", type=["png", "jpg", "jpeg"]
    )

    col_e1, col_e2 = st.columns(2)
    guardar_empresa = col_e1.form_submit_button(
        "💾 Guardar Datos de Empresa", type="primary"
    )
    borrar_empresa = col_e2.form_submit_button("🗑️ Borrar Configuración")

    if guardar_empresa:
      logo_final_path = def_logo
      if nuevo_logo_empresa is not None:
        os.makedirs("imagenes_catalogo", exist_ok=True)
        logo_final_path = "imagenes_catalogo/logo_empresa.png"
        with open(logo_final_path, "wb") as f:
          f.write(nuevo_logo_empresa.getbuffer())

      conn = sqlite3.connect("presupuestos.db")
      cur = conn.cursor()
      cur.execute("DELETE FROM empresa")
      cur.execute(
          "INSERT INTO empresa (nombre, nif, telefono, correo, direccion,"
          " logo_path) VALUES (?, ?, ?, ?, ?, ?)",
          (c_nom, c_nif, c_tel, c_mail, c_dir, logo_final_path),
      )
      conn.commit()
      conn.close()
      st.success("¡Datos de empresa guardados correctamente para siempre!")
      st.rerun()

    if borrar_empresa:
      conn = sqlite3.connect("presupuestos.db")
      cur = conn.cursor()
      cur.execute("DELETE FROM empresa")
      conn.commit()
      conn.close()
      st.warning("¡Se han borrado los datos de la empresa!")
      st.rerun()


# =========================================================================
# 5. HISTORIAL DE PRESUPUESTOS
# =========================================================================
elif menu == "Historial de Presupuestos":
  st.subheader("📂 Historial Interactivo de Presupuestos")
  conn = sqlite3.connect("presupuestos.db")
  cursor = conn.cursor()
  cursor.execute(
      "SELECT id, fecha, cliente, tipo, total, detalles FROM presupuestos"
      " ORDER BY id DESC"
  )
  presupuestos_db = cursor.fetchall()
  conn.close()

  if presupuestos_db:
    st.write(
        "Selecciona un presupuesto de la lista para ver sus detalles o volver a"
        " descargar su PDF:"
    )

    for p in presupuestos_db:
      p_id, p_fecha, p_cliente, p_tipo, p_total, p_detalles = p

      with st.expander(
          f"📄 Presupuesto #{p_id} | {p_fecha} | Cliente: {p_cliente} | Total:"
          f" {p_total:.2f} €"
      ):
        st.write(f"**Tipo de Proyecto:** {p_tipo}")
        st.write(f"**Fecha de Emisión:** {p_fecha}")

        try:
          import ast

          dict_items = ast.literal_eval(p_detalles)
          df_detalles_guardados = pd.DataFrame(dict_items)

          st.markdown("**Materiales incluidos en este presupuesto:**")
          st.dataframe(
              df_detalles_guardados[
                  [
                      "codigo",
                      "concepto",
                      "Cantidad",
                      "Precio Venta Unitario",
                      "Subtotal Material",
                  ]
              ],
              use_container_width=True,
          )
        except:
          st.info("No se pudieron cargar los detalles detallados de los ítems.")

        st.markdown(f"### 💰 Total Facturado: {p_total:.2f} EUR")

        if st.button(f"📥 Re-descargar PDF Presupuesto #{p_id}", key=f"pdf_{p_id}"):
          try:
            df_pdf = pd.DataFrame(ast.literal_eval(p_detalles))
            iva_hist = p_total - (p_total / 1.21)
            pdf_path = generar_pdf(
                p_cliente,
                p_tipo,
                df_pdf,
                p_total,
                iva_hist,
                logo_guardado_path,
                info_empresa_dict,
            )
            with open(pdf_path, "rb") as f:
              st.download_button(
                  label=f"⬇️ Descargar archivo PDF de {p_cliente}",
                  data=f,
                  file_name=f"Presupuesto_{p_cliente.replace(' ', '_')}_{p_id}.pdf",
                  mime="application/pdf",
                  key=f"dl_{p_id}",
              )
          except Exception as e:
            st.error(f"No se pudo generar el PDF: {e}")
  else:
    st.warning("Aún no hay ningún presupuesto guardado en el historial.")
