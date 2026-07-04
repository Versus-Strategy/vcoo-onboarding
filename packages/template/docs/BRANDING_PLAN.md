# Plan: Document Branding + Script Portability

## Problema 1: Shebangs hardcodeados

Los scripts apuntan a `/home/ubuntu/.hermes/scripts/vcoo/.venv/bin/python3`. 
En Docker (usuario root) o en cliente (otro usuario), fallan.

**Solución:** 
- Cambiar shebang a `#!/usr/bin/env python3` en la template
- `install.sh` los reescribe al VCOO venv real durante instalación
- Skills usan los scripts directamente como ejecutables (tienen +x)

## Problema 2: Skills verbosos, MAGI no usa tools nativas

Los skills son párrafos de texto que MAGI tiene que leer e interpretar,
en lugar de tener tools registradas. Por eso a veces tira de pip del
sistema en vez del venv.

**Solución:** 
- Skills simplificados: "Ejecuta `vcoo-pdf.py invoice ...`" (sin `python3` delante)
- El script es directamente ejecutable por su shebang corregido
- MAGI puede invocarlo como cualquier comando del sistema

## Feature 3: Sistema de branding para documentos

Estado actual → los PDFs usan colores hardcodeados sin logo ni fuentes.

**Lo que construimos:**

```
vcoo-template/
├── assets/
│   ├── logo.png              # Logo corporativo VERSUS
│   ├── logo-clientes/        # Logos de clientes
│   └── brand.yaml            # Paleta + fuentes + defaults
├── templates/
│   ├── invoice.yaml          # Plantilla de factura (márgenes, colores, logo)
│   ├── report.yaml           # Plantilla de informe
│   └── quote.yaml            # Plantilla de presupuesto
└── scripts/
    ├── vcoo-pdf.py           # Refactorizado: lee brand.yaml + plantilla
    └── vcoo-brand.py         # Nuevo: gestor de identidad visual
```

Flujo:
```
brand.yaml (colores, logo, fuentes)
    → template YAML (márgenes, layout, secciones)
        → vcoo-pdf.py inyecta datos del cliente
            → PDF profesional con identidad visual
```

## Orden de ejecución

1. Fix shebangs en scripts template
2. Simplificar skills (sin python3, rutas directas)
3. Crear `assets/` + `brand.yaml`
4. Crear `templates/` con plantillas
5. Refactorizar `vcoo-pdf.py` para leer brand + templates
6. Rebuild Docker + validar con tester
7. Probar interacción real desde Discord
