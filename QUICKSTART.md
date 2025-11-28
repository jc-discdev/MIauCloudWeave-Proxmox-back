# Quick Start Guide

## 🚀 Inicio Rápido

### 1. Configuración Inicial

```bash
# Copiar archivo de configuración
cp .env.example .env

# Editar con tus credenciales de Proxmox
nano .env
```

### 2. Iniciar el Servidor

```bash
# Opción 1: Script automático (recomendado)
./start.sh

# Opción 2: Manual
pip install -r requirements.txt
python main.py
```

### 3. Acceder a la Documentación

Una vez iniciado el servidor, accede a:

- **API Docs (Swagger)**: http://localhost:8001/docs
- **ReDoc**: http://localhost:8001/redoc
- **API Root**: http://localhost:8001

## 📖 Ejemplos de Uso

### Crear una VM

```bash
curl -X POST http://localhost:8001/proxmox/create \
  -H "Content-Type: application/json" \
  -d '{
    "name": "mi-vm",
    "vm_type": "qemu",
    "cores": 2,
    "memory": 2048,
    "disk_size": 20
  }'
```

### Crear un Contenedor LXC

```bash
curl -X POST http://localhost:8001/proxmox/create \
  -H "Content-Type: application/json" \
  -d '{
    "name": "mi-contenedor",
    "vm_type": "lxc",
    "cores": 1,
    "memory": 512,
    "disk_size": 8
  }'
```

### Listar VMs y Contenedores

```bash
curl http://localhost:8001/proxmox/list
```

### Crear Cluster Docker Swarm

```bash
curl -X POST http://localhost:8001/cluster/create \
  -H "Content-Type: application/json" \
  -d '{
    "manager": {
      "name": "swarm-manager",
      "vm_type": "qemu",
      "cores": 2,
      "memory": 2048
    },
    "workers": [{
      "name": "swarm-worker",
      "vm_type": "lxc",
      "cores": 1,
      "memory": 1024,
      "count": 2
    }]
  }'
```

## 🔧 Configuración Avanzada

### Variables de Entorno Importantes

```bash
# Proxmox
PROXMOX_HOST=192.168.1.100
PROXMOX_NODE=pve
PROXMOX_STORAGE=local-lvm

# Telegram (opcional)
TELEGRAM_BOT_TOKEN=your_token
TELEGRAM_CHAT_ID=your_chat_id

# OpenAI (opcional)
OPENAI_API_KEY=your_key
```

### Telegram Bot

Para usar el bot de Telegram:

```bash
# En otra terminal
python telegram_poller.py
```

Comandos disponibles:
- `/start` - Iniciar bot
- `/list` - Ver VMs y contenedores
- `/credentials` - Ver credenciales
- `/help` - Ayuda

## 🧪 Testing

```bash
# Test de conexión
curl http://localhost:8001/proxmox/test

# Test completo
./test_api.sh
```

## 📚 Más Información

- Ver `README.md` para documentación completa
- Ver `MIGRATION.md` para detalles de migración desde GCP/AWS
- Acceder a `/docs` para documentación interactiva
