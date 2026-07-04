# Cómo probar el onboarding de VCOO como si fueras un cliente

Esta guía muestra paso a paso cómo crear una máquina virtual limpia (Ubuntu 22.04) con Multipass, ejecutar el *one‑liner* oficial de VCOO y verificar que el agente queda activo, tal como lo haría cualquier cliente.

---

## 1. Prerrequisitos en tu máquina host

| Herramienta | Por qué la necesitas | Instalación rápida |
|-------------|---------------------|--------------------|
| **Multipass** | Orquesta VMs Ubuntu 22.04 de forma ligera. | `sudo snap install multipass --classic` (o sigue la guía oficial <https://multipass.run>) |
| **curl / wget** | Descarga el *one‑liner* y el tarball de la plantilla. | Ya viene en la mayoría de distros. |
| **git** (opcional) | Si quieres inspeccionar el código o crear tu propio fork. | `sudo apt-get install -y git` |
| **Conexión a internet** | Para descargar dependencias y los artefactos de VCOO. | — |

---

## 2. Usar el script de prueba (recomendado)

El repositorio ya incluye un script que automatiza todo el proceso:

```
/home/ubuntu/versus/vcoo-onboarding/run_vcoo_test.sh
```

Ejecutarlo:

```bash
cd /home/ubuntu/versus/vcoo-onboarding
chmod +x run_vcoo_test.sh
./run_vcoo_test.sh
```

El script hará:

1. Detener (si existía) y restaurar una VM llamada **vcoo-test** a partir de un snapshot limpio (`clean-base`).  
2. Arrancar la VM.  
3. Dentro de la VM, instalar Python 3.11 (si falta) y crear el symlink `/usr/local/bin/python3 → /usr/bin/python3.11`.  
4. Ejecutar el *one‑liner* oficial:  

   ```bash
   curl -fsSL https://vcoo-onboarding.vercel.app/install.sh | bash -s
   ```

5. Al final, verificar:
   - Que `hermes` esté en el `PATH` del usuario `ubuntu`.  
   - Que los servicios `vcoo-health-reporter` y `vcoo-hermes-gateway` estén activos (se ejecutan como *user‑services* bajo `systemd --user`).  
   - Que la respuesta a un token caducado devuelva un JSON 400 estructurado.

Cuando el script termina verás algo como:

```
╔═══════════════════════════════════════════════════════════════════════════════════════════════════════════╗
║              ✓ Instalación completa!                ║
╚══════════════════════════════════════════════════════════════════════════════════════════════════════╝
   Próximos pasos:
     1. Configura los módulos contratados:
        - Google OAuth:  https://vcoo-onboarding.vercel.app/setup/
        - Trello:        Configurar API key en el panel
        - GitHub:        gh auth login
     2. Verifica el estado de los servicios:
        systemctl status vcoo-health-reporter
        systemctl status vcoo-hermes-gateway
     3. Edita tu configuración:
         hermes config edit
     4. Envía un mensaje a MAGI desde Discord o Telegram
```

> **Si prefieres hacerlo “a mano”** (para entender cada paso), sigue la sección 3.

---

## 3. Procedimiento manual (paso a paso)

### 3.1 Crear y lanzar una VM limpia

```bash
# 1️⃣ Crear una VM llamada vcoo-test basada en Ubuntu 22.04
multipass launch --name vcoo-test 22.04

# 2️⃣ (Opcional) Crear un snapshot limpio para poder volver a él rápidamente
multipass snapshot vcoo.test clean-base
```

### 3.2 Entrar a la VM y preparar el entorno

```bash
multipass shell vcoo-test   # te deja dentro como usuario ubuntu
```

Dentro de la VM:

```bash
# Actualizar e instalar python3.11 y venv (si no vienen)
sudo apt-get update -qq
sudo apt-get install -y -qq python3.11 python3.11-venv

# Crear symlink para que `python3` apunte a 3.11 (requerido por el one‑liner)
if [ ! -L /usr/local/bin/python3 ] || [ ! -e /usr/local/bin/python3 ]; then
    sudo ln -sf /usr/bin/python3.11 /usr/local/bin/python3
fi

# Asegurarnos de que estamos en el home del usuario ubuntu
export HOME=/home/ubuntu
cd $HOME
```

### 3.3 Ejecutar el one‑liner de VCOO

```bash
echo "▶️  Ejecutando one‑liner de VCOO..."
curl -fsSL https://vcoo-onboarding.vercel.app/install.sh | bash -s
```

El instalador hará:

* Descargar la plantilla (`template.tar.gz`) desde Vercel.  
* Descomprimirla en `~/.vcoo/template`.  
* Ejecutar el script `install.sh` de la plantilla, que:
  - Instala **uv** (gestor de paquetes rápido).  
  - Clona el repositorio de **Hermes Agent** y crea un entorno virtual.  
  - Instala todas las dependencias (incluidas las skills de VCOO).  
  - Copia los scripts de integración (`vcoo-email.py`, `vcoo-google.py`, …) a `~/.hermes/scripts/vcoo/`.  
  - Configura los *cron jobs* (health‑check, email‑scan, etc.).  
  - Deja un mensaje final con los próximos pasos.

### 3.4 Verificar que el agente está disponible

Después de que el instalador termine (verás el recuadro “✓ Instalación Completa!”), ejecuta:

```bash
# 1️⃣ Comprobar que hermes está en el PATH
which hermes
# debería imprimir algo como: /home/ubuntu/.local/bin/hermes

# 2️⃣ Ver la versión
hermes --version
# ej.: Hermes Agent v0.17.0 (2026.6.19) · upstream d6269da7

# 3️⃣ Listar los cron jobs de VCOO (deberían estar activos)
hermes cron status
# Salida esperada (ejemplo):
# [✓]   Cron activado: vcoo-email-scan (every 60m)
# [✓]   Cron activado: vcoo-health-check (every 30m)
```

> **Nota:** Los chequeos del script original mostraron “Hermes no encontrado en PATH” y servicios “inactive” porque se ejecutaron como **root**, mientras la instalación real es de usuario (`ubuntu`). Al cambiar al usuario `ubuntu` (o salir de la shell de root) todo aparecerá correcto.

Para comprobar explícitamente como usuario:

```bash
sudo -u ubuntu -i   # o simplemente salir de la shell de root y volver a ser ubuntu
which hermes
hermes --version
hermes cron status
```

### 3.5 (Opcional) Activar los servicios como systemd (para que arranquen en boot)

Si deseas que los servicios estén disponibles incluso sin una sesión de usuario iniciada, sigue la sugerencia del instalador:

```bash
hermes gateway install --system   # instala vcoo-health-reporter y vcoo-hermes-gateway como servicios systemd
hermes gateway start              # o simplemente reinicia la VM
```

Después de eso:

```bash
systemctl status vcoo-health-reporter
systemctl status vcoo-hermes-gateway
```

Deberían mostrar **active (running)**.

### 3.6 Probar el envío de un mensaje a MAGI

1. Asegúrate de tener al menos un canal de Discord o Telegram donde el agente esté “paired”.  
   - Si no lo tienes, ejecuta `hermes pairing list` (debería mostrarte los canales vinculados).  
   - Si no hay ninguno, sigue las instrucciones de `hermes setup` para vincular un canal.

2. Envía un mensaje de prueba, por ejemplo:

   ```bash
   hermes -z "Hola, MAGI. ¿Cómo estás?"
   ```

   El agente debería responder en el mismo canal (Discord/Telegram) con un mensaje de ayuda.

---

## 4. Qué hacer si algo falla

| Síntoma | Posible causa | Acción correctiva |
|---------|----------------|-------------------|
| `which hermes` devuelve nada | El instalador no terminó o se interrumpió. | Vuelve a ejecutar el one‑liner dentro de la VM (`curl -fsSL https://vcoo-onboarding.vercel.app/install.sh | bash -s`). Revisa la salida en busca de errores de red o de permisos. |
| `hermes cron status` muestra “No jobs found” | Los cron jobs de usuario no se iniciaron porque el entorno de usuario no está activo. | Ejecuta `hermes setup` (modo interactivo) o bien instala los jobs como sistema: `hermes gateway install --system`. |
| El one‑liner se queda colgado en “Downloading template…” | Problemas de conectividad a `https://vcoo-onboarding.vercel.app/template.tar.gz`. | Prueba con `curl -I https://vcoo-onboarding.vercel.app/template.tar.gz` desde dentro de la VM; si falla, verifica DNS o proxy. |
| Los servicios `vcoo-health-reporter` o `vcoo-hermes-gateway` aparecen como “failed” | Falta alguna dependencia (por ejemplo, `uv` no se instaló correctamente). | Revisa los logs del servicio: `journalctl --user -u vcoo-health-reporter -b` (o `systemctl status …` si lo instalaste como sistema). |
| Al enviar un mensaje a MAGI no recibes respuesta | El agente no está emparejado con el canal o el token de Discord/Telegram no está configurado. | Ejecuta `hermes pairing list` para ver los canales vinculados; si falta, sigue `hermes setup` y permite que el agente genere el enlace de autorización. |

---

## 5. Resumen rápido (comando único)

Si lo que quieres es **una sola línea** que deje la VM lista y te muestre el resultado final, puedes usar:

```bash
multipass launch --name vcoo-test 22.04 && \
multipass exec vcoo-test -- sudo -u ubuntu -i bash -c '
  export HOME=/home/ubuntu
  if ! command -v python3.11 &>/dev/null; then
    sudo apt-get update -qq && sudo apt-get install -y -qq python3.11 python3.11-venv
  fi
  if [ ! -L /usr/local/bin/python3 ] || [ ! -e /usr/local/bin/python3 ]; then
    sudo ln -sf /usr/bin/python3.11 /usr/local/bin/python3
  fi
  echo "▶️  Ejecutando one‑liner…"
  curl -fsSL https://vcoo-onboarding.vercel.app/install.sh | bash -s
  echo "▶️  Verificando instalación…"
  which hermes
  hermes --version
  hermes cron status
'
```

Al final de esa cadena verás la versión de Hermes, la lista de cron jobs activos y, si todo salió bien, el mensaje final del instalador.

---

### 🎉 ¡Listo!

Con cualquiera de los dos caminos (script automatizado o pasos manuales) tendrás una máquina virtual Ubuntu 22.04 con VCOO totalmente onboarded, tal como lo haría cualquier cliente que siga el *one‑liner* público. Ahora puedes:

* Probar la configuración de módulos (Google OAuth, Trello, GitHub, etc.).  
* Editar la configuración del agente con `hermes config edit`.  
* Enviar comandos a MAGI desde Discord o Telegram y ver que responde.  

Si necesitas automatizar aún más la prueba (por ejemplo, en un pipeline de CI), simplemente reutiliza el script `run_vcoo_test.sh` o el bloque de comandos de la sección **5**.

¡Éxitos con tu prueba! Si surge cualquier otro detalle, avísame y afinamos el proceso. 🚀