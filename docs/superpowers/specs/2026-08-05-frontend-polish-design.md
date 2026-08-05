# Pulido del Frontend VCOO — Design Doc

**Fecha:** 2026-08-05
**Estado:** Aprobado por Jorge (brainstorming, decisiones fijadas)
**Ámbito:** `apps/frontend/` del monorepo `vcoo-onboarding`

## Contexto

Se auditaron los 3 frentes del frontend (wizard de onboarding del cliente, dashboard
del operador, y sistema de diseño) con subagentes + skills `ui-ux-pro-max` y
`popular-web-designs`. La base es sólida: paleta violeta VERSUS coherente, 0 hex
sueltos, fuente única, iconos SVG correctos, `Button`/`StepIndicator`/`DataTable`
bien centralizados. Los problemas reales son **accesibilidad ausente**, **sistema
de diseño sin tokens** y **duplicación de lógica**.

**Principio rector:** refinar, no reemplazar. Toda animación respeta
`prefers-reduced-motion`.

## Decisiones fijadas (aprobadas por el usuario)

1. **Éxito/"completado" → verde** en todo el app (semántica universal de "ok").
   Eliminar el `indigo` de `estados.ts:65`.
2. **Solo modo claro.** Se elimina la implementación dark rota/incompleta. No hay
   dark mode; todos los layouts son claros y coherentes.
3. **Tipografía: cargar Inter** (Google Fonts) para identidad pulida (estilo
   Linear/Vercel), con stack fallback a `system-ui`. Añadir stack **mono** y
   `tracking-tight` en títulos.

## Alcance (3 paquetes)

### Paquete A — Accesibilidad (P0)
- Convertir filas de proveedor/modelo y pasos del `StepIndicator` de `<div onClick>`
  a `<button>` + `focus-visible:ring-2` + `aria-current`.
- Errores/toasts → `role="alert"` / `aria-live="polite"` (Login, NuevoCliente,
  DetalleCliente, SetupWizard).
- Contraste: `text-gray-400` → `gray-500` mínimo en etiquetas de sección; arreglar
  `disabled:opacity-50`.
- Labels + `aria-invalid`/`aria-describedby` en inputs (API key/base URL/login).
- Skip-link en ambos layouts; `aria-sort` + `<button>` en headers de tabla;
  touch targets ≥44px; `cursor-pointer` en todos los `<button>`.
- `@media (prefers-reduced-motion: reduce)` global en `index.css`.

### Paquete B — Sistema de diseño unificado
- `estados.ts`: `completado` → verde; `configurando` → violeta (identidad), no azul.
- Chips de módulos (`bg-blue-100 text-blue-800`) → violeta `primary-100/800`.
- Radius único (lg/xl/full): eliminar `rounded-md` de Login → `rounded-lg`.
- Sombras uniformes → `shadow-sm` en tarjetas.
- Spinner único `border-primary-600` (hoy hay 5 colores); duraciones 150-300ms.
- Login usa el componente `<Button>` real (no reimplementa con `rounded-md`).
- Inter + stack mono + `tracking-tight` en títulos.
- Wordmark `<Logo/>` reutilizable (VERSUS | VCOO).
- `.focus-ring` util compartido en `index.css`.

### Paquete C — Consistencia y mantenibilidad
- `Clientes.tsx`: extraer `ClienteCard` (móvil) y tabla a componentes; eliminar
  duplicación tabla/tarjetas (~180 líneas).
- Registrar iconos sueltos (CheckIcon, Chevron*, Clipboard, MagnifyingGlass,
  ArrowPath, ExclamationTriangle) en `icons.tsx`.
- Transición de paso del wizard (`animate-step-in`, `motion-reduce:animate-none`).
- CTA de cierre en paso Finalización + botón "Verificar instalación" en paso 1.
- Header/Footer sin variantes `dark:` (modo claro único).
- Skeletons con `aria-busy`/`role="status"`.

## No hacer (YAGNI)
- No introducir GSAP/framer (el stack CSS es suficiente).
- No paginar/virtualizar Clientes (volumen bajo; viable hoy).
- No refactor de `DataTable` completo en Servicios (fuera de alcance salvo lo de Clientes).
- No enlaces de Login "Olvidó contraseña"/"Solicitar acceso" (sin backend aún):
  se dejan como están pero se quita `href="#"` muerto (→ `type="button"` no-enlace o se marcan).

## Archivos afectados
- `src/index.css`, `tailwind.config.js`, `index.html`
- `src/components/`: `Button.tsx`, `StepIndicator.tsx`, `icons.tsx`, `Header.tsx`,
  `Footer.tsx`, `StatusBadge.tsx`, `Logo.tsx` (nuevo)
- `src/layouts/`: `OperatorLayout.tsx`, `ClientLayout.tsx`
- `src/store/estados.ts`
- `src/pages/Login/Login.tsx`
- `src/pages/operador/Clientes/`: `Clientes.tsx`, `DetalleCliente.tsx`, `NuevoCliente.tsx`, `ClienteCard.tsx` (nuevo)
- `src/pages/public/SetupWizard/SetupWizard.tsx`

## Verificación
- `npm run lint`, `npm run test` (vitest), `npm run build` desde `apps/frontend/`.
- Tests existentes de Button/DataTable/StatusBadge/StepIndicator/SetupWizard deben seguir pasando.
