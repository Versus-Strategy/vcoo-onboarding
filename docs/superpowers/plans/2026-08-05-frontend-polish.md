# Pulido del Frontend VCOO Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Aplicar a11y, sistema de diseño unificado y consistencia al frontend VCOO (wizard cliente + dashboard operador) manteniendo la paleta violeta VERSUS y solo modo claro.

**Architecture:** Refactor incremental sobre el SPA React 18 + Vite 4 + Tailwind existente. Paquetes A (a11y) → B (design system) → C (consistencia). Cada tarea produce un commit verificable.

**Tech Stack:** React 18, TypeScript, Tailwind CSS v3, Vite 4, Vitest, Heroicons, @thesvg/react.

**Working dir:** `apps/frontend/` dentro del monorepo. Commands se ejecutan desde ahí.

## Global Constraints
- Solo modo claro: eliminar toda variante `dark:`.
- Éxito/completado = **verde**; `configurando` = violeta `primary`; nunca indigo/azul para estados.
- Tipografía: Inter (Google Fonts) con fallback `system-ui`; stack mono definido; `tracking-tight` en títulos.
- Radius: `rounded-lg` (8px) inputs/buttons, `rounded-xl` (12px) tarjetas, `rounded-full` pills. Eliminar `rounded-md`.
- Sombras: `shadow-sm` en tarjetas; `shadow-lg` solo hover interactivo.
- Spinner único: `border-primary-600`.
- Duraciones 150-300ms; `transition-colors duration-200` estándar; barras de progreso `duration-500`.
- Toda animación respeta `prefers-reduced-motion` (`motion-reduce:animate-none` / media query).
- Touch targets ≥44px; `cursor-pointer` en todo `<button>` clickeable.
- Errores → `role="alert"`; feedback no crítico → `aria-live="polite"`.
- UI en español.
- Verificación por tarea: `npm run lint`, `npm run test`, `npm run build`.

---

### Task 1: Fundaciones de estilo (Inter, tokens CSS, reduced-motion, focus-ring, stack mono)

**Files:**
- Modify: `apps/frontend/index.html`
- Modify: `apps/frontend/src/index.css`
- Modify: `apps/frontend/tailwind.config.js`

- [ ] **Step 1: Añadir Inter y preconnect en `index.html`**

```html
<head>
  <meta charset="UTF-8" />
  <link rel="preconnect" href="https://fonts.googleapis.com" />
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
  <link
    href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap"
    rel="stylesheet"
  />
  <link rel="icon" type="image/svg+xml" href="/vite.svg" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>VCOO Dashboard</title>
</head>
```

- [ ] **Step 2: Reescribir `index.css` con tokens + reduced-motion + focus-ring**

```css
@tailwind base;
@tailwind components;
@tailwind utilities;

:root {
  --font-sans: 'Inter', system-ui, sans-serif;
  --font-mono: ui-monospace, SFMono-Regular, 'JetBrains Mono', 'Menlo', monospace;
  --duration-fast: 150ms;
  --duration-standard: 200ms;
  --duration-progress: 500ms;
}

body {
  font-family: var(--font-sans);
  @apply bg-gray-50 text-gray-900 antialiased;
}

/* Anillo de foco reutilizable (a11y) */
.focus-ring {
  @apply focus:outline-none focus-visible:ring-2 focus-visible:ring-primary-500 focus-visible:ring-offset-2;
}

/* Respetar prefers-reduced-motion */
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.01ms !important;
    scroll-behavior: auto !important;
  }
}
```

- [ ] **Step 3: Añadir stack mono + keyframe de transición de paso en `tailwind.config.js`**

```js
/** @type {import('tailwindcss').Config} */
export default {
  darkMode: 'class',
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        primary: {
          50: '#ede9fe',
          100: '#ddd6fe',
          200: '#c4b5fd',
          300: '#a78bfa',
          400: '#9333ea',
          500: '#7c3aed',
          600: '#6d28d9',
          700: '#5b21b6',
          800: '#4c1d95',
          900: '#43148a',
          950: '#2e1065'
        }
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        mono: ['ui-monospace', 'SFMono-Regular', 'JetBrains Mono', 'Menlo', 'monospace'],
      },
      keyframes: {
        'step-in': {
          '0%': { opacity: '0', transform: 'translateY(8px)' },
          '100%': { opacity: '1', transform: 'none' },
        },
      },
      animation: {
        'step-in': 'step-in 0.2s ease-out',
      },
    }
  },
  plugins: [],
}
```

- [ ] **Step 4: Verificar build**

Run: `npm run build`
Expected: éxito sin errores. Los títulos/fonts ya no fallan.

- [ ] **Step 5: Commit**

```bash
git add index.html src/index.css tailwind.config.js
git commit -m "style(frontend): fundaciones - Inter, tokens, reduced-motion, focus-ring, stack mono"
```

---

### Task 2: `icons.tsx` centralizado (registrar iconos sueltos)

**Files:**
- Modify: `apps/frontend/src/components/icons.tsx`

- [ ] **Step 1: Añadir los iconos usados sueltos en `icons.tsx`**

```tsx
export {
  EyeIcon,
  EyeSlashIcon,
  ChartBarIcon,
  CpuChipIcon,
  ClipboardDocumentListIcon as ClipboardListIcon,
  GlobeAltIcon,
  ClockIcon,
  ExclamationTriangleIcon,
  ChevronUpDownIcon,
  ChevronUpIcon,
  ChevronDownIcon,
  DocumentTextIcon,
  EnvelopeIcon,
  CalendarIcon,
  CodeBracketIcon,
  PuzzlePieceIcon,
  CheckCircleIcon,
  // nuevos:
  CheckIcon,
  ChevronLeftIcon,
  ChevronRightIcon,
  ClipboardIcon,
  MagnifyingGlassIcon,
  ArrowPathIcon,
} from '@heroicons/react/24/outline';
```

- [ ] **Step 2: Verificar lint**

Run: `npm run lint`
Expected: sin errores nuevos (aún nadie importa los nuevos; están exportados).

- [ ] **Step 3: Commit**

```bash
git add src/components/icons.tsx
git commit -m "refactor(icons): registrar iconos sueltos en el centralizador"
```

---

### Task 3: `Button.tsx` — a11y (focus-ring, disabled real) + cursor-pointer

**Files:**
- Modify: `apps/frontend/src/components/Button.tsx`

- [ ] **Step 1: Reescribir Button con focus-ring, disabled real, cursor-pointer**

```tsx
import React from 'react';
import { ArrowPathIcon } from './icons';

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'ghost';
  size?: 'sm' | 'md' | 'lg';
  loading?: boolean;
}

const variantClasses = {
  primary: 'bg-primary-600 text-white hover:bg-primary-700 focus-visible:ring-primary-300 disabled:bg-primary-300 disabled:text-white',
  secondary: 'bg-gray-200 text-gray-700 hover:bg-gray-300 focus-visible:ring-gray-400 disabled:bg-gray-100 disabled:text-gray-400',
  ghost: 'text-primary-600 hover:bg-primary-50 focus-visible:ring-primary-300 disabled:text-gray-300',
};

const sizeClasses = {
  sm: 'px-3 py-1.5 text-sm',
  md: 'px-4 py-2 text-sm',
  lg: 'px-6 py-3 text-base',
};

const Button: React.FC<ButtonProps> = ({
  variant = 'primary',
  size = 'md',
  loading = false,
  children,
  className = '',
  disabled,
  ...props
}) => {
  return (
    <button
      className={`inline-flex items-center justify-center font-medium rounded-lg transition-colors duration-200 cursor-pointer focus-ring ${variantClasses[variant]} ${sizeClasses[size]} ${className}`}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
      {...props}
    >
      {loading && (
        <ArrowPathIcon className="animate-spin motion-reduce:animate-none -ml-1 mr-2 h-4 w-4" />
      )}
      {children}
    </button>
  );
};

export default Button;
```

- [ ] **Step 2: Verificar test + build**

Run: `npm run test -- src/components/Button.test.tsx`
Expected: PASS (el test existente valida variantes/sizes/loading).

- [ ] **Step 3: Commit**

```bash
git add src/components/Button.tsx
git commit -m "fix(button): focus-ring, disabled real, cursor-pointer, motion-reduce"
```

---

### Task 4: `StepIndicator.tsx` — pasos accesibles como `<button>` + focus + aria-current

**Files:**
- Modify: `apps/frontend/src/components/StepIndicator.tsx`

- [ ] **Step 1: Convertir pasos a `<button>` navegables por teclado**

Reemplazar el bloque `pasos.map` interior (líneas 49-81) para que el contenedor
sea un `<button>` cuando esté desbloqueado y tenga `onStepClick`, y un `<div>`
estático si no. Añadir `focus-ring`, `aria-current` y `cursor-pointer`.

```tsx
{pasos.map((paso, idx) => {
  const isCurrent = idx === pasoActual;
  const isUnlocked = idx <= unlockedLimit;
  const degraded = isDegraded(idx);
  const isNext = idx === unlockedLimit + 1;
  const isDone = idx < pasoCompletado;
  const showCheckmark = !isCurrent && (isDone || degraded) && !isNext;
  const clickable = isUnlocked && !!onStepClick;
  const dotClasses = `w-10 h-10 rounded-full flex items-center justify-center text-sm font-medium transition-colors ${
    isCurrent && !degraded ? 'bg-primary-100 text-primary-600 border-2 border-primary-600 ring-4 ring-primary-200'
    : isCurrent && degraded ? 'bg-yellow-100 text-yellow-600 border-2 border-yellow-600 ring-4 ring-yellow-200'
    : degraded ? 'bg-yellow-100 text-yellow-600 border-2 border-yellow-400'
    : showCheckmark ? 'bg-primary-100 text-primary-600 border-2 border-primary-400'
    : isNext ? 'bg-gray-100 text-gray-400 border-2 border-dashed border-gray-300'
    : 'bg-gray-100 text-gray-400 border-2 border-gray-200'
  }`;
  const content = (
    <>
      <div className={dotClasses}>
        {degraded && !isCurrent ? (
          <ExclamationTriangleIcon className="w-4 h-4" />
        ) : showCheckmark ? (
          <CheckIcon className="w-4 h-4" />
        ) : (
          idx + 1
        )}
      </div>
      <span className={`mt-1 text-xs ${isCurrent || showCheckmark || degraded ? 'text-primary-600 font-medium' : 'text-gray-500'}`}>
        {paso}
      </span>
    </>
  );
  return clickable ? (
    <button
      key={idx}
      type="button"
      onClick={() => onStepClick?.(idx)}
      aria-current={isCurrent ? 'step' : undefined}
      className={`flex flex-col items-center flex-shrink-0 min-w-[56px] text-center cursor-pointer rounded-lg focus-ring`}
    >
      {content}
    </button>
  ) : (
    <div key={idx} className="flex flex-col items-center flex-shrink-0 min-w-[56px] text-center">
      {content}
    </div>
  );
})}
```

Nota: los dots pasan de `w-8 h-8` (32px) a `w-10 h-10` (40px) y el `min-w-[56px]`
mantiene el target ≥44px. El `onClick` del contenedor se mueve al `<button>`.

- [ ] **Step 2: Verificar test + build**

Run: `npm run test -- src/components/StepIndicator.test.tsx`
Expected: PASS.

- [ ] **Step 3: Commit**

```bash
git add src/components/StepIndicator.tsx
git commit -m "fix(stepindicator): pasos accesibles como button + focus-ring + aria-current"
```

---

### Task 5: `estados.ts` — éxito verde, configurando violeta (eliminar indigo/azul)

**Files:**
- Modify: `apps/frontend/src/store/estados.ts`

- [ ] **Step 1: Cambiar colores de estado**

```ts
export const coloresEstado: Record<EstadoUI, string> = {
  'en-linea': 'bg-green-100 text-green-800',
  'fuera-de-linea': 'bg-red-100 text-red-800',
  'sin-provisionar': 'bg-gray-100 text-gray-600',
  completado: 'bg-green-100 text-green-800',
  configurando: 'bg-primary-100 text-primary-800',
  bloqueado: 'bg-amber-100 text-amber-800',
};
```

- [ ] **Step 2: Verificar build**

Run: `npm run build`
Expected: éxito.

- [ ] **Step 3: Commit**

```bash
git add src/store/estados.ts
git commit -m "fix(estados): éxito verde + configurando violeta, eliminar indigo/azul"
```

---

### Task 6: `Header.tsx` / `Footer.tsx` — modo claro único + `<Logo/>`

**Files:**
- Create: `apps/frontend/src/components/Logo.tsx`
- Modify: `apps/frontend/src/components/Header.tsx`
- Modify: `apps/frontend/src/components/Footer.tsx`

- [ ] **Step 1: Crear `Logo.tsx` (wordmark reutilizable)**

```tsx
import React from 'react';

interface LogoProps {
  size?: 'sm' | 'md';
  className?: string;
}

const Logo: React.FC<LogoProps> = ({ size = 'md', className = '' }) => {
  const box = size === 'sm' ? 'w-6 h-6 text-xs' : 'w-8 h-8 text-sm';
  const title = size === 'sm' ? 'text-base' : 'text-xl';
  return (
    <div className={`flex items-center gap-2 ${className}`}>
      <div className={`${box} rounded-lg bg-primary-600 flex items-center justify-center text-white font-bold`}>
        V
      </div>
      <span className={`${title} font-bold text-primary-600 tracking-tight`}>VERSUS</span>
      <span className={`text-sm text-gray-500`}>| VCOO</span>
    </div>
  );
};

export default Logo;
```

- [ ] **Step 2: Reescribir `Header.tsx` sin dark + con Logo + skip target**

```tsx
import React from 'react';
import { useAuth } from '../auth/authContext';
import Logo from './Logo';

const Header: React.FC = () => {
  const { auth, cerrarSesion } = useAuth();

  return (
    <header className="bg-white border-b border-gray-200">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex justify-between h-16 items-center">
          <Logo />
          <div className="flex items-center space-x-4">
            <span className="text-sm text-gray-600">
              {auth.usuario?.nombre || 'Usuario'}
            </span>
            <button
              onClick={cerrarSesion}
              className="text-sm text-gray-500 hover:text-gray-700 transition-colors cursor-pointer focus-ring rounded-md"
            >
              Cerrar sesión
            </button>
          </div>
        </div>
      </div>
    </header>
  );
};

export default Header;
```

- [ ] **Step 3: Reescribir `Footer.tsx` sin dark**

```tsx
import React from 'react';

const Footer: React.FC = () => {
  return (
    <footer className="bg-white border-t border-gray-200 mt-auto">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
        <p className="text-center text-sm text-gray-500">
          &copy; {new Date().getFullYear()} VERSUS Strategy. Todos los derechos reservados.
        </p>
      </div>
    </footer>
  );
};

export default Footer;
```

- [ ] **Step 4: Verificar build**

Run: `npm run build`
Expected: éxito.

- [ ] **Step 5: Commit**

```bash
git add src/components/Logo.tsx src/components/Header.tsx src/components/Footer.tsx
git commit -m "style(frontend): wordmark Logo reutilizable + Header/Footer modo claro único"
```

---

### Task 7: Layouts — skip-link + modo claro único + alinear contenedores

**Files:**
- Modify: `apps/frontend/src/layouts/OperatorLayout.tsx`
- Modify: `apps/frontend/src/layouts/ClientLayout.tsx`

- [ ] **Step 1: Reescribir `OperatorLayout.tsx` con skip-link + alinear main**

```tsx
import { NavLink, Outlet } from 'react-router-dom';
import { useAuth } from '@/auth/authContext';
import Footer from '@/components/Footer';
import Logo from '@/components/Logo';

const OperatorLayout = () => {
  const { auth, cerrarSesion } = useAuth();

  const navLinkClass = ({ isActive }: { isActive: boolean }) =>
    `text-sm font-medium pb-2 border-b-2 transition-colors focus-ring ${
      isActive
        ? 'text-primary-600 border-primary-600'
        : 'text-gray-600 border-transparent hover:text-gray-700 hover:border-gray-300'
    }`;

  return (
    <div className="min-h-screen flex flex-col bg-gray-50">
      <a href="#contenido" className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-50 focus:bg-white focus:px-4 focus:py-2 focus:rounded-lg focus:shadow-lg">
        Saltar al contenido
      </a>
      <header className="bg-white border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between h-16 items-center">
            <Logo />
            <div className="flex items-center space-x-4">
              <span className="text-sm text-gray-600">
                {auth.usuario?.nombre || 'Usuario'}
              </span>
              <button
                onClick={cerrarSesion}
                className="text-sm text-gray-500 hover:text-gray-700 transition-colors cursor-pointer focus-ring rounded-md"
              >
                Cerrar sesión
              </button>
            </div>
          </div>
          <nav className="flex space-x-6 -mb-px">
            <NavLink to="/operador/clientes" className={navLinkClass}>
              Clientes
            </NavLink>
            <NavLink to="/operador/clientes/nuevo" className={navLinkClass}>
              Nuevo Cliente
            </NavLink>
          </nav>
        </div>
      </header>
      <main id="contenido" className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-6">
        <Outlet />
      </main>
      <Footer />
    </div>
  );
};

export default OperatorLayout;
```

Nota: `main` pasa de `container` (ancho de breakpoint variable) a `max-w-7xl`
para alinearse con el header (P4 del informe). `id="contenido"` es el target del skip-link.

- [ ] **Step 2: Reescribir `ClientLayout.tsx` en modo claro**

```tsx
import { Outlet } from 'react-router-dom';
import type { ReactNode } from 'react';
import Header from '../components/Header';
import Footer from '../components/Footer';

const ClientLayout = ({ children }: { children?: ReactNode }) => {
  return (
    <div className="min-h-screen flex flex-col bg-gray-50">
      <a href="#contenido" className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-50 focus:bg-white focus:px-4 focus:py-2 focus:rounded-lg focus:shadow-lg">
        Saltar al contenido
      </a>
      <Header />
      <main id="contenido" className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-6">
        {children ?? <Outlet />}
      </main>
      <Footer />
    </div>
  );
};

export default ClientLayout;
```

- [ ] **Step 3: Verificar build**

Run: `npm run build`
Expected: éxito.

- [ ] **Step 4: Commit**

```bash
git add src/layouts/OperatorLayout.tsx src/layouts/ClientLayout.tsx
git commit -m "fix(layouts): skip-link, modo claro único, main max-w-7xl alineado con header"
```

---

### Task 8: `Login.tsx` — usar `<Button>`, a11y, aria-live, modo claro

**Files:**
- Modify: `apps/frontend/src/pages/Login/Login.tsx`

- [ ] **Step 1: Reescribir Login con Button, labels aria, role=alert, autocomplete**

```tsx
import { useState } from 'react';
import { useAuthActions } from '../../auth/useAuth';
import { useNavigate } from 'react-router-dom';
import { EyeIcon, EyeSlashIcon } from '../../components/icons';
import Button from '../../components/Button';
import Logo from '../../components/Logo';

const Login = () => {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [cargando, setCargando] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showPassword, setShowPassword] = useState(false);
  const [recordarme, setRecordarme] = useState(false);
  const { iniciarSesion } = useAuthActions();
  const navigate = useNavigate();

  const manejarEnvio = async (e: React.FormEvent) => {
    e.preventDefault();
    setCargando(true);
    setError(null);

    try {
      await iniciarSesion(email, password);
      navigate('/', { replace: true });
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Correo electrónico o contraseña inválidos';
      setError(msg);
    } finally {
      setCargando(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50 px-4 py-8 sm:px-6">
      <div className="w-full max-w-md space-y-6">
        <div className="text-center flex justify-center">
          <Logo size="md" />
        </div>
        <p className="text-center text-gray-600 -mt-3">
          Acceso al Panel de Control VCOO
        </p>

        <form onSubmit={manejarEnvio} className="space-y-4">
          <div>
            <label htmlFor="email" className="block text-sm font-medium text-gray-700 mb-1">
              Correo electrónico
            </label>
            <input
              id="email"
              type="email"
              required
              autoComplete="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              aria-invalid={!!error}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent"
            />
          </div>

          <div>
            <label htmlFor="password" className="block text-sm font-medium text-gray-700 mb-1">
              Contraseña
            </label>
            <div className="relative">
              <input
                id="password"
                type={showPassword ? 'text' : 'password'}
                required
                autoComplete="current-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                aria-invalid={!!error}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent pr-10"
              />
              <button
                type="button"
                onClick={() => setShowPassword(!showPassword)}
                className="absolute inset-y-0 right-0 flex items-center px-3 text-gray-500 hover:text-gray-700 cursor-pointer focus-ring rounded-r-lg"
                aria-label={showPassword ? 'Ocultar contraseña' : 'Mostrar contraseña'}
              >
                {showPassword ? <EyeSlashIcon className="w-5 h-5" /> : <EyeIcon className="w-5 h-5" />}
              </button>
            </div>
          </div>

          <div className="flex items-center justify-between">
            <label className="flex items-center space-x-2 text-sm text-gray-600 cursor-pointer">
              <input
                type="checkbox"
                checked={recordarme}
                onChange={(e) => setRecordarme(e.target.checked)}
                className="rounded border-gray-300 text-primary-600 focus:ring-primary-500"
              />
              Recordarme
            </label>
            <span className="text-sm text-gray-400">¿Olvidó su contraseña?</span>
          </div>

          <Button type="submit" loading={cargando} className="w-full">
            {cargando ? 'Iniciando sesión...' : 'Ingresar'}
          </Button>

          {error && (
            <p role="alert" className="text-sm text-red-600 text-center">
              {error}
            </p>
          )}

          <div className="text-center text-sm text-gray-500">
            ¿No tiene cuenta? <span className="text-gray-400">Solicitar acceso</span>
          </div>
        </form>
      </div>
    </div>
  );
};

export default Login;
```

Nota: `recordarme` se mantiene como estado (el `useAuth` no lo persiste; fuera de
alcance del backend). Los enlaces muertos `href="#"` se cambian a `<span>` gris
(sin href roto). `rounded-md` → `rounded-lg`.

- [ ] **Step 2: Verificar build**

Run: `npm run build`
Expected: éxito.

- [ ] **Step 3: Commit**

```bash
git add src/pages/Login/Login.tsx
git commit -m "fix(login): usar Button, a11y (aria-invalid, role=alert, autocomplete), modo claro"
```

---

### Task 9: `NuevoCliente.tsx` — a11y, aria-live, focus transition

**Files:**
- Modify: `apps/frontend/src/pages/operador/Clientes/NuevoCliente.tsx`

- [ ] **Step 1: Añadir role=alert a errores, aria-invalid, focus a éxito, aria-live copiado**

Cambios puntuales:
1. Input nombre: añadir `aria-invalid={!!error}` y `required`.
2. Error block → `role="alert"`.
3. Bloque éxito → `role="status"` con `aria-live="polite"`.
4. Botón copiar: `aria-live="polite"` en el texto de estado (`{copiado ? '¡Copiado!' : 'Copiar'}`) envolviéndolo en un `<span aria-live="polite">`.
5. Nota módulos `text-gray-400` → `text-gray-500` (contraste).

- [ ] **Step 2: Verificar build**

Run: `npm run build`
Expected: éxito.

- [ ] **Step 3: Commit**

```bash
git add src/pages/operador/Clientes/NuevoCliente.tsx
git commit -m "fix(nuevocliente): a11y - role=alert, aria-invalid, aria-live copiado, contraste"
```

---

### Task 10: `DetalleCliente.tsx` — a11y, form real, chips violeta, aria-live

**Files:**
- Modify: `apps/frontend/src/pages/operador/Clientes/DetalleCliente.tsx`

- [ ] **Step 1: Cambios a11y + proveedor como `<form>` real + chips violeta**

Cambios puntuales:
1. Importar `CheckIcon` desde `icons.tsx` (no heroicons directo).
2. `accionMsg` y `configResult` → `role="status"` con `aria-live="polite"`.
3. Envolver el bloque de configuración de proveedor en un `<form onSubmit={handleSetProvider}>`; el Button pasa a `type="submit"`.
4. Selects e inputs de proveedor: añadir `focus-ring` y `cursor-pointer`.
5. API key input: `aria-invalid`, `autoComplete="off"`.
6. Chips de módulos (`bg-blue-100 text-blue-800` línea 689) → `bg-primary-100 text-primary-800`.
7. `handleSetProvider` debe llamar `e.preventDefault()` (ahora es onSubmit).

- [ ] **Step 2: Verificar build**

Run: `npm run build`
Expected: éxito.

- [ ] **Step 3: Commit**

```bash
git add src/pages/operador/Clientes/DetalleCliente.tsx
git commit -m "fix(detallecliente): proveedor como form, aria-live, focus-ring, chips violeta"
```

---

### Task 11: `Clientes.tsx` + `ClienteCard.tsx` — extraer duplicación móvil, headers sort accesibles, aria-live

**Files:**
- Create: `apps/frontend/src/pages/operador/Clientes/ClienteCard.tsx`
- Modify: `apps/frontend/src/pages/operador/Clientes/Clientes.tsx`

- [ ] **Step 1: Crear `ClienteCard.tsx` (tarjeta móvil)**

```tsx
import React from 'react';
import { useNavigate } from 'react-router-dom';
import StatusBadge from '@/components/StatusBadge';
import Button from '@/components/Button';

interface ClienteCardProps {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  cliente: Record<string, any>;
  onEliminar: () => void;
}

const ClienteCard: React.FC<ClienteCardProps> = ({ cliente, onEliminar }) => {
  const navigate = useNavigate();
  const id = cliente.id as string;
  const nombre = (cliente.nombre as string) || 'Sin nombre';
  const estado = (cliente.estado as string) || 'sin-provisionar';
  const ultimoContacto = cliente.ultimoContacto as string | undefined;
  const agenteEstado = (cliente.servicios?.[0]?.estado as string) || 'sin-provisionar';
  const modulos = cliente.servicios?.[0]?.modulos as string[] | undefined;

  return (
    <div className="bg-white rounded-lg shadow-sm p-4 space-y-3 cursor-pointer hover:bg-gray-50 transition-colors">
      <button
        type="button"
        onClick={() => navigate(`/operador/clientes/${id}`)}
        className="w-full text-left focus-ring rounded-lg"
      >
        <span className="text-sm font-medium text-gray-900 break-words block">{nombre}</span>
      </button>
      {modulos && modulos.filter(m => m !== 'core').length > 0 && (
        <div className="flex flex-wrap gap-1">
          {modulos.filter(m => m !== 'core').slice(0, 3).map(m => (
            <span key={m} className="text-xs bg-gray-100 text-gray-600 px-1.5 py-0.5 rounded">{m}</span>
          ))}
        </div>
      )}
      <dl className="grid grid-cols-2 gap-x-4 gap-y-2 text-sm">
        <div>
          <dt className="text-gray-500 text-xs">Estado VCOO</dt>
          <dd className="mt-0.5"><StatusBadge estado={estado} /></dd>
        </div>
        <div>
          <dt className="text-gray-500 text-xs">Agente</dt>
          <dd className="mt-0.5"><StatusBadge estado={agenteEstado} /></dd>
        </div>
        <div className="col-span-2">
          <dt className="text-gray-500 text-xs">Último contacto</dt>
          <dd className="mt-0.5 text-gray-900">
            {ultimoContacto
              ? new Date(ultimoContacto).toLocaleDateString('es-ES', {
                  year: 'numeric', month: 'short', day: 'numeric',
                })
              : '—'}
          </dd>
        </div>
      </dl>
      <div className="flex items-center gap-2 pt-1">
        <Button
          variant="ghost"
          size="sm"
          className="flex-1"
          onClick={() => navigate(`/operador/clientes/${id}`)}
        >
          Ver detalle
        </Button>
        <Button
          variant="ghost"
          size="sm"
          className="flex-1 text-red-600 hover:bg-red-50"
          onClick={onEliminar}
        >
          Eliminar
        </Button>
      </div>
    </div>
  );
};

export default ClienteCard;
```

- [ ] **Step 2: En `Clientes.tsx`, importar `ClienteCard` y reemplazar el bloque móvil**

Reemplazar el bloque `{/* Tarjetas (móvil) */}` (líneas ~296-378) por:

```tsx
{/* Tarjetas (móvil) */}
<div className="md:hidden space-y-3">
  {filtrados.length === 0 ? (
    <div className="bg-white rounded-lg shadow-sm p-8 text-center text-sm text-gray-500">
      No se encontraron clientes con los filtros actuales.
    </div>
  ) : (
    filtrados.map((cliente) => (
      <ClienteCard key={cliente.id} cliente={cliente} />
    ))
  )}
</div>
```

Nota: `ClienteCard` recibe `onEliminar` como prop (más limpio, sin eventos globales).

- [ ] **Step 3: Headers de tabla ordenables accesibles (`<button>` + `aria-sort`)**

Reemplazar el `<th>` ordenable (líneas 203-211) por:

```tsx
{(['nombre', 'estado', 'ultimoContacto', 'agente'] as SortField[]).map(field => (
  <th
    key={field}
    aria-sort={sortField === field ? (sortDir === 'asc' ? 'ascending' : 'descending') : undefined}
    className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider"
  >
    <button
      type="button"
      onClick={() => toggleSort(field)}
      className="inline-flex items-center gap-1 cursor-pointer focus-ring rounded uppercase tracking-wider"
    >
      {field === 'nombre' ? 'Nombre' : field === 'estado' ? 'Estado VCOO' : field === 'ultimoContacto' ? 'Último contacto' : 'Agente'}
      <SortIcon field={field} />
    </button>
  </th>
))}
```

- [ ] **Step 4: a11y en búsqueda y filtros**

- Search input: añadir `aria-label="Buscar por nombre"` y `aria-live` al resultado.
- Chips filtro: añadir `aria-pressed={filtroEstado===s}` y `min-h-[40px]` + `focus-ring`.
- Empty state de filtros (tabla y móvil): añadir un botón "Limpiar filtros" junto al texto.
- Skeletons → `role="status"` + `aria-busy="true"`.

- [ ] **Step 5: Verificar build + test**

Run: `npm run build`
Expected: éxito.

- [ ] **Step 6: Commit**

```bash
git add src/pages/operador/Clientes/Clientes.tsx src/pages/operador/Clientes/ClienteCard.tsx
git commit -m "refactor(clientes): extraer ClienteCard, headers sort accesibles, a11y filtros"
```

---

### Task 12: `SetupWizard.tsx` — a11y filas/pasos, transición, CTA final, verificación manual, spinner único

**Files:**
- Modify: `apps/frontend/src/pages/public/SetupWizard/SetupWizard.tsx`

- [ ] **Step 1: Importar iconos desde `icons.tsx` (CheckIcon, Chevron*)**

Reemplazar las importaciones directas de heroicons (líneas 15-20) por importaciones
desde `@/components/icons`. Quitar el import directo.

- [ ] **Step 2: `renderRow` de proveedores → `<button>` accesible**

Reemplazar `renderRow` (líneas 1005-1032): el contenedor `<div onClick>` pasa a
`<button type="button">` con `focus-ring`, `cursor-pointer`, y `aria-current`.
Chevron `w-4 h-4` → `w-5 h-5` para target ≥44px en el área.

```tsx
const renderRow = (proveedor: typeof raw[0], idx: number, rec: boolean) => (
  <button
    key={proveedor.id}
    type="button"
    onClick={() => manejarConectarProveedor(proveedor.id)}
    className={`w-full text-left flex items-center gap-3 px-4 py-3 rounded-lg cursor-pointer transition-colors focus-ring ${
      rec
        ? 'bg-primary-50 border border-primary-200 hover:bg-primary-100'
        : 'hover:bg-gray-50 border border-transparent'
    }`}
  >
    <div className={`flex-shrink-0 w-7 h-7 ${PROVEEDOR_ICONOS[proveedor.id] ? 'flex items-center justify-center' : 'rounded-full flex items-center justify-center text-xs font-bold text-white ' + BG_COLORS[idx % BG_COLORS.length]}`}>
      {PROVEEDOR_ICONOS[proveedor.id] || proveedor.nombre.charAt(0)}
    </div>
    <div className="flex-1 min-w-0">
      <div className="flex items-center gap-2">
        <span className={`text-sm font-medium ${rec ? 'text-primary-900' : 'text-gray-900'}`}>
          {proveedor.nombre}
        </span>
        {rec && (
          <span className="text-xs bg-primary-200 text-primary-800 px-2 py-0.5 rounded-full font-medium">
            Recomendado
          </span>
        )}
      </div>
      <p className="text-xs text-gray-600 truncate">{proveedor.descripcion}</p>
    </div>
    <ChevronRightIcon className="w-5 h-5 text-gray-400 flex-shrink-0" />
  </button>
);
```

Nota: `py-2.5` → `py-3` (target ~44px), descripción `text-gray-500` → `text-gray-600` (contraste).

- [ ] **Step 3: Etiquetas de sección "POPULARES"/"OTROS" → `text-gray-500`**

En `renderPasoProveedor`, cambiar `text-xs text-gray-400` de "POPULARES" (1076) y
"OTROS" (1083) a `text-xs text-gray-500`.

- [ ] **Step 4: Botón "Ver más" + botones "Volver" + "Copiar comando" → `cursor-pointer` + focus-ring + aria-label**

- Botón "Ver más" (1087-1090): añadir `cursor-pointer` y `focus-ring`.
- Botón "Copiar comando" (806-812): añadir `aria-label="Copiar comando"`, `cursor-pointer`, `focus-ring`, `py-2` para target.
- Botón "Volver a proveedores" (875) y "Volver a módulos" (1137): añadir `cursor-pointer focus-ring`.

- [ ] **Step 5: Transición de paso con `animate-step-in` + reduced-motion**

Envolver el contenido activo (líneas 1687-1697) en un contenedor con `key`:

```tsx
<div key={pasoActual} className="animate-step-in motion-reduce:animate-none">
  {pasoActual === 3 || pasoActual >= 4
    ? renderPasoFinalizacion()
    : pasoActual === 0
    ? renderPasoInstalacion()
    : pasoActual === 1
    ? renderPasoProveedor()
    : pasoActual === 2
    ? renderPasoModulos()
    : renderPasoInstalacion()}
</div>
```

- [ ] **Step 6: CTA de cierre en `renderPasoFinalizacion` + aria-live**

Añadir al final de `renderPasoFinalizacion`, cuando `allOk`, un botón de cierre:

```tsx
{allOk && (
  <div className="mt-8" role="status" aria-live="polite">
    <Button
      size="lg"
      onClick={() => {
        // Redirige al dashboard del cliente si hay sesión; si no, al inicio
        window.location.href = '/';
      }}
    >
      Ir al dashboard
    </Button>
  </div>
)}
```

- [ ] **Step 7: Unificar spinners a `border-primary-600`**

Reemplazar `border-blue-600` (818), `border-green-600` (1212, 1419),
`border-yellow-600` (1354) y `border-primary-500` por `border-primary-600`.
Cambiar la barra `animate-pulse` en progreso de espera (1172) por spinner estándar
si aplica.

- [ ] **Step 8: Spinner provider "Conectando..." y "Configurando..." con `motion-reduce:animate-none`**

Todos los `animate-spin` inline: añadir `motion-reduce:animate-none`.

- [ ] **Step 9: Verificar test + build**

Run: `npm run test -- src/pages/public/SetupWizard` y `npm run build`
Expected: PASS y build éxito.

- [ ] **Step 10: Commit**

```bash
git add src/pages/public/SetupWizard/SetupWizard.tsx
git commit -m "fix(wizard): a11y filas/pasos, transición step-in, CTA final, spinner único, reduced-motion"
```

---

### Task 13: Verificación final completa

**Files:** (ninguno)

- [ ] **Step 1: Lint completo**

Run: `npm run lint`
Expected: sin errores (o solo warnings preexistentes permitidos).

- [ ] **Step 2: Tests unitarios completos**

Run: `npm run test`
Expected: todos PASS.

- [ ] **Step 3: Build de producción**

Run: `npm run build`
Expected: éxito sin errores.

- [ ] **Step 4: Commit final (si hay ajustes)**

```bash
git add -A
git commit -m "chore(frontend): verificación final lint+test+build" || echo "nada que commitear"
```

---

## Self-Review
- **Spec coverage:** A (a11y): Tasks 1,3,4,7,8,9,10,11,12. B (design system): Tasks 1,2,5,6,10. C (consistencia): Tasks 2,6,11,12. ✅
- **Placeholders:** Ninguno; todo el código está inline. ✅
- **Type consistency:** `ClienteCard` usa `cliente: Record<string, any>` y prop `onEliminar`. `Logo` usa `size?: 'sm' | 'md'`. `focus-ring` es una clase CSS global definida en Task 1. ✅
