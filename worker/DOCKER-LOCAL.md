# Worker 24/7 en Docker local (Windows sin WSL)

Este PC usa **Vagrant + VirtualBox + Ubuntu + Docker Engine** porque Docker Desktop no funciona en Windows 10 LTSC 2019 sin WSL.

El `Vagrantfile` vive en `C:\DockerVM\vagrant\Vagrantfile` y una copia de respaldo está en `worker/Vagrantfile.docker-local`. Instala Docker 20.10 y reemplaza el `docker-compose` 1.17 de Ubuntu por el 1.29.2 (el 1.17 no entiende el formato `3.7` del `docker-compose.yml`).

## Encender

1. Doble clic en `INICIAR-DOCKER-LOCAL.bat`.
   - Levanta la VM `clipforge-docker` (3 CPU / 4 GB RAM).
   - Construye y enciende el contenedor `clipforge-worker`.
   - Muestra los logs; `Ctrl+C` solo cierra la ventana, **el worker sigue corriendo**.

## Que arranque solo al prender la PC

Copia `INICIAR-DOCKER-LOCAL-SIEMPRE.bat` en el Inicio de Windows:

- `Win + R` → escribe `shell:startup` → Enter.
- Pega una copia del `.bat` ahí (no muevas el original).

Ese script levanta la VM y el contenedor en segundo plano y escribe en `worker/logs/inicio-docker-local.log` si algo falla.

## Ver logs / apagar

- `VER-LOGS-DOCKER-LOCAL.bat` → estado del contenedor y logs en vivo.
- Para apagar: desde una terminal, `cd C:\DockerVM\vagrant` y `vagrant ssh -c "cd /vagrant && docker-compose down"`.

## Sincronía de voz y subtítulos

`worker/.env` acepta `SUB_SYNC_OFFSET` (segundos). Por defecto es `-0.35`: el texto entra 0.35 s antes, porque Whisper/Groq marca la palabra tarde y se oía el audio "adelantado".

- Si aún se oye antes que el texto: baja a `-0.5`.
- Si el texto sale antes que la voz: sube a `-0.2` (o `0` para desactivar).

Cambiar el valor requiere reconstruir: `vagrant ssh -c "cd /vagrant && docker-compose up -d --build"`.
