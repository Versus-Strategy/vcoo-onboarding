#!/usr/bin/env python3
"""
vcoo-pdf.py — Generación profesional de PDFs con branding VCOO
=================================================================
Uso: vcoo-pdf.py <acción> <output-path> [args...]

Acciones:
  invoice <output.pdf> <cliente> <importe> <concepto> [items-json]
  report  <output.pdf> <title> [body]
  quote   <output.pdf> <cliente> <servicios-json>
  text    <output.pdf> <content>

Con plantillas y branding:
  vcoo-pdf.py --brand assets/brand.yaml invoice factura.pdf "Cliente" 1250 "Concepto"

Variables de entorno:
  VCOO_BRAND   = ruta al brand.yaml (default: assets/brand.yaml)
  VCOO_TEMPLATE_DIR = directorio de plantillas (default: templates/)

Ejemplos:
  vcoo-pdf.py invoice factura.pdf "Cliente SA" 1250.00 "Consultoría Marzo"
  vcoo-pdf.py quote presupuesto.pdf "Cliente SA" '[{"servicio":"CORE","precio":1000}]'
  vcoo-pdf.py text documento.pdf "Hola mundo"
"""

import json, os, sys, yaml
from datetime import datetime

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm, cm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.colors import HexColor, black, white
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer,
                                 Table, TableStyle, PageBreak, HRFlowable,
                                 Image)
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
from reportlab.lib.utils import open_for_read

# ─── Rutas ───────────────────────────────────────────────────
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
VCOO_DIR = os.path.dirname(SCRIPT_DIR)  # vcoo-template root
DEFAULT_BRAND = os.getenv("VCOO_BRAND", os.path.join(VCOO_DIR, "assets", "brand.yaml"))
TEMPLATE_DIR = os.getenv("VCOO_TEMPLATE_DIR", os.path.join(VCOO_DIR, "templates"))

# ─── Cargar brand ──────────────────────────────────────────────
def load_brand(brand_path=None):
    """Load brand identity from YAML"""
    path = brand_path or DEFAULT_BRAND
    if not os.path.exists(path):
        return None, f"Brand file no encontrado: {path}"
    try:
        with open(path) as f:
            brand = yaml.safe_load(f)
        return brand.get("brand", brand), None
    except Exception as e:
        return None, f"Error cargando brand: {e}"

def brand_color(brand, key, fallback="#1a1a2e"):
    """Get color from brand config"""
    colors = brand.get("colors", {}) if brand else {}
    return HexColor(colors.get(key, fallback))

def brand_font(brand, key="body", fallback="Helvetica"):
    """Get font name from brand config"""
    fonts = brand.get("fonts", {}) if brand else {}
    return fonts.get(key, fallback)

# ─── Cargar template ──────────────────────────────────────────
def load_template(action):
    """Load template YAML for the given action"""
    template_path = os.path.join(TEMPLATE_DIR, f"{action}.yaml")
    if not os.path.exists(template_path):
        return None
    try:
        with open(template_path) as f:
            tpl = yaml.safe_load(f)
        return tpl.get("template", tpl)
    except Exception:
        return None

# ─── Estilos (con brand) ──────────────────────────────────────
def make_styles(brand):
    """Create paragraph styles from brand config"""
    c = lambda k: brand_color(brand, k)
    f = lambda k: brand_font(brand, k)
    sizes = brand.get("fonts", {}).get("sizes", {}) if brand else {}

    return {
        "title": ParagraphStyle(
            "BrandTitle", fontSize=sizes.get("title", 24),
            textColor=c("primary"), fontName=f("heading"),
            spaceAfter=6*mm, alignment=TA_RIGHT
        ),
        "heading1": ParagraphStyle(
            "BrandH1", fontSize=sizes.get("heading1", 16),
            textColor=c("primary"), fontName=f("heading"),
            spaceAfter=4*mm
        ),
        "heading2": ParagraphStyle(
            "BrandH2", fontSize=sizes.get("heading2", 14),
            textColor=c("secondary"), fontName=f("body"),
            spaceAfter=3*mm
        ),
        "body": ParagraphStyle(
            "BrandBody", fontSize=sizes.get("body", 10),
            leading=14, textColor=c("text"), fontName=f("body"),
            spaceAfter=3*mm
        ),
        "bold": ParagraphStyle(
            "BrandBold", fontSize=sizes.get("body", 10),
            textColor=c("text"), fontName=f("heading"),
            spaceAfter=3*mm
        ),
        "small": ParagraphStyle(
            "BrandSmall", fontSize=sizes.get("small", 8),
            textColor=c("muted"), fontName=f("body"),
        ),
        "title_left": ParagraphStyle(
            "BrandTitleLeft", fontSize=sizes.get("title", 24),
            textColor=c("primary"), fontName=f("heading"),
            spaceAfter=6*mm
        ),
    }

# ─── Renderizador de secciones ────────────────────────────────
def render_section(section, data, styles, brand, doc_elements):
    """Render a template section into the document"""
    st = styles
    colors = brand.get("colors", {}) if brand else {}
    p_c = lambda k: brand_color(brand, k)
    section_type = section.get("type", "")

    if section_type == "header":
        # Title + document label
        company = brand.get("company", {}) if brand else {}
        cname = company.get("name", "VERSUS Strategy SL")
        label = data.get("document_label", section.get("label", "Documento"))
        doc_elements.append(Paragraph(f"<b>{cname}</b>", st["title"]))
        doc_elements.append(Paragraph(label, st["heading1"]))
        doc_elements.append(HRFlowable(width="100%", thickness=1, color=p_c("accent")))
        doc_elements.append(Spacer(1, 3*mm))

    elif section_type == "spacer":
        doc_elements.append(Spacer(1, section.get("height_mm", 5)*mm))

    elif section_type == "info_table":
        cols = section.get("columns", [])
        rows = [[Paragraph(f"<b>{c['label']}:</b>", st["bold"]),
                 Paragraph(str(data.get(c["field"], "")), st["body"])]
                for c in cols]
        lw = section.get("style", {}).get("label_width_mm", 40)*mm
        vw = section.get("style", {}).get("value_width_mm", 110)*mm
        t = Table(rows, colWidths=[lw, vw])
        t.setStyle(TableStyle([
            ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 10),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3*mm),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ]))
        doc_elements.append(t)

    elif section_type in ("items_table",):
        cols = section.get("columns", [])
        header_row = [Paragraph(f"<b>{c['header']}</b>", st["bold"]) for c in cols]
        items = data.get("items", [])
        data_rows = []
        for item in items:
            row = []
            for col in cols:
                val = str(item.get(col["field"], ""))
                align = col.get("align", "left")
                ps = ParagraphStyle("cell", parent=st["body"],
                                    alignment=TA_RIGHT if align == "right" else TA_LEFT)
                row.append(Paragraph(val, ps))
            data_rows.append(row)

        footer = section.get("footer", [])
        footer_rows = []
        for f_item in footer:
            flabel = f_item.get("label", "")
            fval = str(data.get(f_item.get("field"), ""))
            fstyle = f_item.get("style", "normal")
            fcolor = f_item.get("color", "")
            if fstyle == "bold_highlight":
                fill = p_c("primary")
                txt_c = white
            else:
                fill = HexColor(colors.get("light", "#f8f9fa"))
                txt_c = p_c("text")

            lbl = Paragraph(f"<b>{flabel}</b>",
                ParagraphStyle("fl", parent=st["bold"], textColor=txt_c))
            val = Paragraph(f"<b>{fval}</b>",
                ParagraphStyle("fv", parent=st["bold"], textColor=txt_c))
            footer_rows.append([lbl, val])

        widths = [c.get("width_mm", 40)*mm for c in cols]
        all_data = [header_row] + data_rows
        if footer_rows:
            all_data += footer_rows

        t = Table(all_data, colWidths=widths)
        ts = [
            ("BACKGROUND", (0, 0), (-1, 0), p_c("primary")),
            ("TEXTCOLOR", (0, 0), (-1, 0), white),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("GRID", (0, 0), (-1, -len(footer_rows)-1), 0.5, HexColor(colors.get("border", "#dfe6e9"))),
            ("TOPPADDING", (0, 0), (-1, -1), 3*mm),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3*mm),
        ]
        # Align columns
        for i, col in enumerate(cols):
            if col.get("align") == "right":
                ts.append(("ALIGN", (i, 1), (i, -1), "RIGHT"))
            elif col.get("align") == "center":
                ts.append(("ALIGN", (i, 1), (i, -1), "CENTER"))

        # Footer styling
        for i, f_item in enumerate(footer):
            row_idx = len(all_data) - len(footer_rows) + i
            fstyle = f_item.get("style", "normal")
            if fstyle == "bold_highlight":
                ts.append(("BACKGROUND", (0, row_idx), (-1, row_idx), p_c("primary")))
                ts.append(("TEXTCOLOR", (0, row_idx), (-1, row_idx), white))
            else:
                ts.append(("BACKGROUND", (0, row_idx), (-1, row_idx),
                          HexColor(colors.get("light", "#f8f9fa"))))

        t.setStyle(TableStyle(ts))
        doc_elements.append(t)

    elif section_type == "title_block":
        title = data.get(section.get("field", "title"), "")
        doc_elements.append(Paragraph(title, st["title_left"]))

    elif section_type == "metadata":
        for entry in section.get("fields", []):
            val = data.get(entry["field"], "")
            if val:
                doc_elements.append(
                    Paragraph(f"<b>{entry['label']}:</b> {val}", st["body"]))

    elif section_type == "body":
        body = data.get(section.get("field", "body"), "")
        for para in body.split("\n\n"):
            doc_elements.append(Paragraph(para.replace("\n", "<br/>"), st["body"]))

    elif section_type == "footer_text":
        text = section.get("text", "")
        if text:
            doc_elements.append(Paragraph(text, st["small"]))

    elif section_type == "rule":
        doc_elements.append(HRFlowable(width="100%", thickness=1,
                                        color=p_c(section.get("color", "border"))))

# ─── Acciones ─────────────────────────────────────────────────

def make_invoice(output_path, client_name, amount, concept, items_json=None,
                 brand=None, template=None):
    """Generate invoice with branding"""
    brand = brand or {}
    tpl = template or load_template("invoice")
    styles = make_styles(brand)

    # Build data
    now = datetime.now().strftime("%d/%m/%Y")
    subtotal = float(amount)
    vat = subtotal * 0.21
    total = subtotal + vat

    data = {
        "document_label": "FACTURA",
        "client_name": client_name,
        "date": now,
        "invoice_number": f"INV-{datetime.now().strftime('%Y%m%d-%H%M')}",
        "concept": concept,
        "subtotal": f"{subtotal:.2f} €",
        "vat": f"{vat:.2f} €",
        "grand_total": f"{total:.2f} €",
        "items": json.loads(items_json) if items_json else [
            {"qty": "1", "description": concept, "unit_price": f"{subtotal:.2f} €",
             "total": f"{subtotal:.2f} €"}
        ],
    }

    doc = SimpleDocTemplate(
        output_path, pagesize=A4,
        leftMargin=20*mm, rightMargin=20*mm,
        topMargin=25*mm, bottomMargin=20*mm
    )
    elements = []
    if tpl:
        for section in tpl.get("sections", []):
            render_section(section, data, styles, brand, elements)
    else:
        # Fallback to old behavior
        p_c = lambda k: brand_color(brand, k)
        elements.append(Paragraph(f"<b>VERSUS Strategy SL</b>", styles["title"]))
        elements.append(Paragraph("FACTURA", styles["heading1"]))
        elements.append(HRFlowable(width="100%", thickness=1, color=p_c("accent")))
        elements.append(Spacer(1, 5*mm))
        rows = [["Cliente:", client_name], ["Fecha:", now],
                ["Concepto:", concept], ["Importe:", f"{subtotal:.2f} € (ex-IVA)"]]
        t = Table(rows, colWidths=[40*mm, 110*mm])
        t.setStyle(TableStyle([("FONTNAME",(0,0),(0,-1),"Helvetica-Bold"),
                               ("FONTSIZE",(0,0),(-1,-1),11),
                               ("BOTTOMPADDING",(0,0),(-1,-1),4*mm)]))
        elements.append(t)
        elements.append(Spacer(1, 10*mm))
        total_data = [["TOTAL (IVA 21% incluido):", f"{total:.2f} €"]]
        tt = Table(total_data, colWidths=[100*mm, 50*mm])
        tt.setStyle(TableStyle([
            ("BACKGROUND",(0,0),(-1,-1),p_c("primary")),
            ("TEXTCOLOR",(0,0),(-1,-1),white),
            ("FONTNAME",(0,0),(-1,-1),"Helvetica-Bold"),
            ("FONTSIZE",(0,0),(-1,-1),14),
            ("ALIGN",(0,0),(-1,-1),"CENTER"),
            ("TOPPADDING",(0,0),(-1,-1),5*mm),
            ("BOTTOMPADDING",(0,0),(-1,-1),5*mm),
        ]))
        elements.append(tt)
        elements.append(Spacer(1, 5*mm))
        elements.append(Paragraph("* Precios exentos de IVA.", styles["small"]))

    doc.build(elements)
    print(f"✅ Factura creada: {output_path}")

def make_report(output_path, title, body="", brand=None, template=None):
    """Generate report with branding"""
    brand = brand or {}
    tpl = template or load_template("report")
    styles = make_styles(brand)

    now = datetime.now().strftime("%d/%m/%Y %H:%M")
    data = {"document_label": "INFORME", "title": title, "body": body,
            "date": now, "author": "MAGI", "recipient": "—"}

    doc = SimpleDocTemplate(output_path, pagesize=A4,
                            leftMargin=20*mm, rightMargin=20*mm,
                            topMargin=25*mm, bottomMargin=20*mm)
    elements = []
    if tpl:
        for section in tpl.get("sections", []):
            render_section(section, data, styles, brand, elements)
    else:
        p_c = lambda k: brand_color(brand, k)
        elements.append(Paragraph(f"<b>VERSUS Strategy SL</b>", styles["title"]))
        elements.append(Paragraph(title, styles["heading1"]))
        elements.append(HRFlowable(width="100%", thickness=1, color=p_c("accent")))
        elements.append(Spacer(1, 5*mm))
        elements.append(Paragraph(f"Generado por MAGI — {now}", styles["small"]))
        elements.append(Spacer(1, 5*mm))
        if body:
            elements.append(Paragraph(body.replace("\n", "<br/>"), styles["body"]))
        elements.append(Spacer(1, 10*mm))

    doc.build(elements)
    print(f"✅ Informe creado: {output_path}")

def make_quote(output_path, client_name, servicios_json, brand=None, template=None):
    """Generate quote with branding"""
    brand = brand or {}
    tpl = template or load_template("quote")
    styles = make_styles(brand)
    servicios = json.loads(servicios_json) if isinstance(servicios_json, str) else servicios_json

    now = datetime.now().strftime("%d/%m/%Y")
    total = sum(s.get("precio", 0) for s in servicios)
    items = []
    for s in servicios:
        price = s.get("precio", 0)
        items.append({
            "service": s.get("servicio", "?"),
            "description": s.get("descripcion", ""),
            "price": f"{price:.2f} €",
            "total": f"{price:.2f} €",
        })

    data = {
        "document_label": "PRESUPUESTO",
        "client_name": client_name,
        "date": now,
        "valid_until": datetime.now().strftime("%d/%m/%Y"),
        "grand_total": f"{total:.2f} €",
        "items": items,
    }

    doc = SimpleDocTemplate(output_path, pagesize=A4,
                            leftMargin=20*mm, rightMargin=20*mm,
                            topMargin=25*mm, bottomMargin=20*mm)
    elements = []
    if tpl:
        for section in tpl.get("sections", []):
            render_section(section, data, styles, brand, elements)
    else:
        p_c = lambda k: brand_color(brand, k)
        elements.append(Paragraph(f"<b>VERSUS Strategy SL</b>", styles["title"]))
        elements.append(Paragraph(f"Presupuesto para: {client_name}", styles["heading1"]))
        elements.append(HRFlowable(width="100%", thickness=1, color=p_c("accent")))
        elements.append(Spacer(1, 5*mm))
        elements.append(Paragraph(f"Fecha: {now}", styles["body"]))
        elements.append(Spacer(1, 5*mm))
        header = [["Servicio", "Descripción", "Precio"]]
        rows = [[s.get("servicio","?"), s.get("descripcion",""),
                 f"{s.get('precio',0):.2f} €"] for s in servicios]
        table_data = header + rows + [["", "TOTAL", f"{total:.2f} €"]]
        t = Table(table_data, colWidths=[50*mm, 70*mm, 30*mm])
        ts = [
            ("BACKGROUND",(0,0),(-1,0),p_c("primary")),
            ("TEXTCOLOR",(0,0),(-1,0),white),
            ("GRID",(0,0),(-1,-2),0.5,HexColor("#cccccc")),
            ("FONTNAME",(0,-1),(-1,-1),"Helvetica-Bold"),
            ("BACKGROUND",(0,-1),(-1,-1),HexColor("#f8f9fa")),
            ("ALIGN",(2,1),(2,-1),"RIGHT"),
            ("TOPPADDING",(0,0),(-1,-1),3*mm),
            ("BOTTOMPADDING",(0,0),(-1,-1),3*mm),
        ]
        t.setStyle(TableStyle(ts))
        elements.append(t)
        elements.append(Spacer(1, 5*mm))
        elements.append(Paragraph("* Precios exentos de IVA. Válido 30 días.", styles["small"]))

    doc.build(elements)
    print(f"✅ Presupuesto creado: {output_path}")

def make_text(output_path, content, brand=None):
    """Generate text PDF"""
    brand = brand or {}
    styles = make_styles(brand)
    doc = SimpleDocTemplate(output_path, pagesize=A4,
                            leftMargin=20*mm, rightMargin=20*mm,
                            topMargin=25*mm, bottomMargin=20*mm)
    elements = []
    for para in content.split("\n\n"):
        elements.append(Paragraph(para.replace("\n", "<br/>"), styles["body"]))
    doc.build(elements)
    print(f"✅ PDF creado: {output_path}")

# ─── CLI ──────────────────────────────────────────────────────
if __name__ == "__main__":
    brand = None
    brand_path = DEFAULT_BRAND
    template = None

    # Parse --brand flag if present
    args = sys.argv[1:]
    if "--brand" in args:
        idx = args.index("--brand")
        if idx + 1 < len(args):
            brand_path = args[idx + 1]
        args = args[:idx] + args[idx+2:]

    # Load brand
    brand_data, err = load_brand(brand_path)
    if err:
        print(f"⚠️  {err}")

    if len(args) < 2:
        print(__doc__)
        sys.exit(1)

    action = args[0]
    output = args[1]

    try:
        if action == "invoice":
            # format: invoice <output> <cliente> <importe> <concepto> [items-json]
            # args[0]=action, args[1]=output, args[2]=cliente, args[3]=importe
            cliente = args[2]
            importe = args[3]
            raw_concept = " ".join(args[4:])
            items_json = None
            concepto = raw_concept
            if args[4:] and args[-1].startswith("["):
                items_json = args[-1]
                concepto = " ".join(args[4:-1])
            make_invoice(output, cliente, importe, concepto,
                         items_json=items_json, brand=brand_data, template=template)
        elif action == "report":
            make_report(output, args[2], " ".join(args[3:]),
                        brand=brand_data, template=template)
        elif action == "quote":
            servicios = " ".join(args[3:]) if len(args) > 3 else "[]"
            make_quote(output, args[2], servicios,
                       brand=brand_data, template=template)
        elif action == "text":
            make_text(output, " ".join(args[2:]), brand=brand_data)
        else:
            print(f"❌ Acción desconocida: {action}")
            print(__doc__)
            sys.exit(1)
    except (IndexError, ValueError) as e:
        print(f"❌ Error: {e}")
        print("   Revisa los argumentos. Usa --help para ayuda.")
        sys.exit(1)
