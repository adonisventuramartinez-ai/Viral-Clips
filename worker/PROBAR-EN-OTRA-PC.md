# Probar el worker en la PC del hermano (más potente, con Docker)

La web puede estar abierta en cualquier PC: el worker solo necesita `worker/.env` para conectarse a Supabase y recoger trabajos.

**Regla de oro: solo UN worker activo a la vez.** Si el de tu PC y el del hermano están prendidos, se pelean los mismos trabajos.

---

## Opción 1 — Probar sin mover nada (rápida)

1. En tu PC el worker ya está corriendo. Verifícalo con `VER-LOGS-DOCKER-LOCAL.bat`.
2. En la PC de tu hermano abre la web de ClipForge y genera un clip corto desde `/en-vivo` o `/crear → ✨ Transformar`.
3. El clip lo procesa **tu PC**. Mira el avance en los logs de tu PC.

Sirve para comprobar que la web sigue conectando con Supabase, pero no aprovecha la PC buena.

---

## Opción 2 — Pasar el worker a la PC buena (recomendado)

### 1) Apaga el worker de tu PC

En una terminal:

```
cd C:\DockerVM\vagrant
vagrant ssh -c "cd /vagrant && docker-compose down"
vagrant halt
```

### 2) Copia la carpeta `worker` a la otra PC

Copia toda la carpeta `worker`, **incluido el archivo `.env`** (ahí están las llaves; no lo pegues en el chat).

No tires `work\`, `logs\` ni `__pycache__` porque pesan y no sirven. Desde tu PC puedes empaquetar solo lo necesario:

```
robocopy "C:\Users\nino\Documents\Viral-Clips-1\worker" "C:\ClipForge\worker" /E /XD work logs __pycache__ /XF *.log
```

Luego pasa `C:\ClipForge\worker` a la PC del hermano (USB, OneDrive, etc.).

### 3) En la PC del hermano

1. Instala **Docker Desktop** si no lo tiene (Windows 10/11 con WSL2). Ábrelo y espera a que el icono quede sin errores.
   - Si esa PC es Windows 10 LTSC sin WSL, usa el método Vagrant: sigue `DOCKER-LOCAL.md` y el `Vagrantfile.docker-local` que ya están en el repo.
2. Pega la carpeta, por ejemplo en `C:\ClipForge\worker`.
3. Doble clic en **`INICIAR-SIEMPRE.bat`**.
   - La primera vez tarda varios minutos porque descarga/compila la imagen.
4. Doble clic en **`VER-LOGS.bat`**. Debe aparecer:

```
Worker listo (encuadres, directos con chat, Modo Transformar y Crear con IA), esperando trabajos…
```

### 4) Haz la prueba

Desde cualquier PC abre la web y genera un clip corto:

- `/en-vivo` → pega el link del vivo de Alofoke → espera 2-3 min → genera clip, o
- `/crear` → sube video corto → **✨ Transformar**.

Ve a `/biblioteca`, reproduce el clip y revisa que el texto aparezca justo cuando se oye la voz.

### 5) Volver a tu PC (si quieres)

1. En la PC del hermano: `DETENER-WORKER.bat`.
2. En tu PC: doble clic en `INICIAR-DOCKER-LOCAL.bat`.

---

## Si el texto sigue desfasado

Edita `SUB_SYNC_OFFSET` en `worker/.env` de la PC que esté corriendo el worker:

- Se oye antes que el texto → `-0.5`
- El texto sale antes que la voz → `-0.2`
- Valor actual → `-0.35`

Para aplicar, en la PC con Docker Desktop: doble clic en `DETENER-WORKER.bat` y luego `INICIAR-SIEMPRE.bat`.
En tu PC con Vagrant:

```
cd C:\DockerVM\vagrant
vagrant ssh -c "cd /vagrant && docker-compose up -d --force-recreate"
```
