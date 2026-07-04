---
name: vcoo-behavioral-testing
description: "VCOO Virtual — Módulo BEHAVIORAL TESTER: verifica que el agente VCOO responde correctamente a comandos en lenguaje natural usando sus skills y herramientas integradas."
version: 1.0.0
author: VERSUS Strategy SL
tags: [vcoo, testing, behavioral, qa, agente]
---

# VCOO Behavioral Tester — Verificación del Comportamiento del Agente

## ⚠ INSTRUCCIÓN DE EJECUCIÓN DIRECTA — NO PREGUNTAR

Cuando el usuario diga cualquiera de estas frases de activación:

- *"ejecuta los tests de comportamiento"*
- *"prueba el comportamiento del agente"*
- *"behavioral tests"*
- *"verifica que el agente sepa hacerlo"*
- *"prueba mis capacidades"*
- *"pasa los behavioral tests"*

**Ejecuta inmediatamente** el script de testeo comportamental.

### Orden de ejecución

1. Detectar el directorio de la template (misma lógica que `vcoo-testing`):
   - `~/versus/vcoo-template/` → template
   - `/opt/vcoo-template/` → template (Docker)
2. Ejecutar: `python3 {TEMPLATE_DIR}/scripts/vcoo-behavior-tester.py` desde `{TEMPLATE_DIR}` como working directory.
3. Capturar la salida (stdout + stderr).
4. Analizar el resultado: contar PASS, FAIL, SKIP, WARN.
5. Reportar con el formato de la sección "Formato de reporte".
6. Si hay FAIL, listar las causas concretas (el script ya las muestra).
7. Concluir con recomendación.

## Formato de reporte

Cuando el usuario pida los tests de comportamiento, incluye:

**📋 Reporte de comportamiento — VCOO Agent**

**Entorno:** {local | docker | vps}

| ID | Capacidad | Prompt | Resultado | Detalle |
|----|-----------|--------|-----------|---------|
| 📅 calendar-events | Calendario | ¿Qué tengo esta semana? | 🟢 OK | Listó 4 eventos |
| 📬 email-inbox | Email | Últimos 3 correos | 🟢 OK | Mostró remitentes |
| 📄 generate-invoice | Factura PDF | Factura VERSUS 500€ | 🟢 OK | PDF generado |
| 📁 drive-files | Google Drive | Archivos en Drive | 🔴 FALLÓ | Respondió "no puedo" |
| 📋 trello-boards | Trello | Tableros Trello | ⚠ SKIP | Sin credenciales |

**Resumen: {N} OK · {M} FAIL · {K} SKIP**

**Comportamiento del agente: {X}/{Y} capacidades funcionales ({Z}%)**

**🔴 Fallos:**
- {id}: {causa}

**✅ Conclusión:** {Agente funcional / Revisar fallos / Sin datos}

## Cuándo ejecutarlo

- Cuando el usuario lo solicita explícitamente (ver frases de activación).
- Después de cambios en skills o scripts, para verificar que el agente sigue respondiendo correctamente.
- Como parte de la suite completa de tests (`vcoo-tester.py --phase 9` o `vcoo-tester.py --behavioral`).

## Diferencia con vcoo-tester.py

| Aspecto | vcoo-tester.py | vcoo-behavior-tester.py |
|---------|---------------|------------------------|
| Qué prueba | Scripts, APIs, estructura | Comportamiento del agente |
| Cómo | Ejecuta código directamente | Envía prompts en lenguaje natural |
| Evaluación | PASS/FAIL determinista | LLM judge + side effects |
| Dependencias | Python, scripts | Hermes CLI, OpenRouter |
| Rapidez | Segundos | ~1-2 min por escenario |
