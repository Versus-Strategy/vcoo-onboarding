---
name: vcoo-pdf
description: "VCOO Virtual — Generación de documentos PDF profesionales (facturas, informes, presupuestos)"
version: 1.0.2
author: VERSUS Strategy SL
tags: [vcoo, pdf, reportlab, documentos, facturas]
---

# VCOO PDF — Generación de Documentos

## Descripción
El módulo PDF permite al agente VCOO generar documentos profesionales en formato PDF:
- **Facturas**: Con formato corporativo, IVA incluido
- **Presupuestos**: Tabla de servicios con precios
- **Informes**: Documentos con título, cuerpo y pie
- **Textos**: Cualquier contenido a PDF

## Script
`~/.hermes/scripts/vcoo/vcoo-pdf.py` (usa shebang → VCOO venv automáticamente)

## Uso

Los PDFs se generan en el **directorio de trabajo actual**. Usa nombres descriptivos.

### Factura
```bash
~/.hermes/scripts/vcoo/vcoo-pdf.py invoice factura_cliente.pdf "Cliente SA" 1250.00 "Consultoría COO Virtual - Marzo 2026"
```

### Presupuesto
```bash
~/.hermes/scripts/vcoo/vcoo-pdf.py quote presupuesto_cliente.pdf "Cliente SA" \
  '[{"servicio":"CORE","descripcion":"Setup VCOO Virtual","precio":1000},{"servicio":"OFFICE","descripcion":"Google Workspace","precio":250}]'
```

### Informe
```bash
~/.hermes/scripts/vcoo/vcoo-pdf.py report informe_proyecto.pdf "Informe Mensual" "Cuerpo del informe..."
```

### Texto simple
```bash
~/.hermes/scripts/vcoo/vcoo-pdf.py text documento.pdf "Contenido del documento"
```

## Formato
- Tamaño: A4
- Márgenes: 20mm
- Colores corporativos: #1a1a2e (primario), #e94560 (acento)
- Fuente: Helvetica

## Integración con MAIL
Los PDFs generados pueden adjuntarse a correos electrónicos usando el módulo MAIL. Estrategia recomendada:
1. Generar PDF con vcoo-pdf
2. Enviar por email con vcoo-email (requiere enviar como attachment mediante Gmail API)
3. Archivar copia en Google Drive con vcoo-google

## Dependencias
- ReportLab 5.0+ (en el VCOO venv)
- WeasyPrint 69+ (en el VCOO venv, para conversiones avanzadas)
