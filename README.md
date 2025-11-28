# MIauCloudWeave - Proxmox Backend

API backend para gestionar máquinas virtuales (VMs) y contenedores LXC en Proxmox VE, con soporte para despliegue de clusters Docker Swarm y Kubernetes.

## 🚀 Características

- ✅ **Gestión de VMs QEMU**: Crear, listar, eliminar, iniciar, detener VMs
- ✅ **Gestión de Contenedores LXC**: Soporte completo para contenedores ligeros
- ✅ **Clusters Docker Swarm**: Despliegue automático de manager + workers
- ✅ **Kubernetes (K3s)**: Instalación automatizada de clusters K3s
- ✅ **Servicios**: Redis, Portainer
- ✅ **Integración AI**: Comandos en lenguaje natural con OpenAI
- ✅ **Logging Telegram**: Notificaciones en tiempo real

## 📋 Requisitos

- Python 3.8+
- Servidor Proxmox VE 7.0+
- Acceso a la API de Proxmox (usuario/contraseña o API token)

## 🔧 Instalación

1. **Clonar el repositorio**:
```bash
git clone <repo-url>
cd MIauCloudWeave-Proxmox-back
```

2. **Instalar dependencias**:
```bash
pip install -r requirements.txt
```

3. **Configurar variables de entorno**:
```bash
cp .env.example .env
nano .env
```

Edita el archivo `.env` con tu configuración de Proxmox:

```bash
# Proxmox Configuration
PROXMOX_HOST=192.168.1.100
PROXMOX_PORT=8006
PROXMOX_USER=root@pam
PROXMOX_PASSWORD=tu_password
PROXMOX_VERIFY_SSL=false
PROXMOX_NODE=pve
PROXMOX_STORAGE=local-lvm
PROXMOX_BRIDGE=vmbr0

# Telegram (opcional)
TELEGRAM_BOT_TOKEN=tu_bot_token
TELEGRAM_CHAT_ID=tu_chat_id

# OpenAI (opcional)
OPENAI_API_KEY=tu_api_key
```

4. **Iniciar el servidor**:
```bash
python main.py
```

El servidor estará disponible en `http://localhost:8001`

## 📚 Uso

### Test de Conexión

```bash
curl http://localhost:8001/proxmox/test
```

### Crear una VM

```bash
curl -X POST http://localhost:8001/proxmox/create \
  -H "Content-Type: application/json" \
  -d '{
    "name": "test-vm",
    "vm_type": "qemu",
    "cores": 2,
    "memory": 2048,
    "disk_size": 10
  }'
```

### Crear un Contenedor LXC

```bash
curl -X POST http://localhost:8001/proxmox/create \
  -H "Content-Type: application/json" \
  -d '{
    "name": "test-container",
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
      "memory": 2048,
      "disk_size": 20
    },
    "workers": [
      {
        "name": "swarm-worker",
        "vm_type": "lxc",
        "cores": 1,
        "memory": 1024,
        "disk_size": 10,
        "count": 2
      }
    ]
  }'
```

### Iniciar/Detener VM

```bash
# Iniciar
curl -X POST http://localhost:8001/proxmox/start \
  -H "Content-Type: application/json" \
  -d '{"name": "test-vm"}'

# Detener
curl -X POST http://localhost:8001/proxmox/stop \
  -H "Content-Type: application/json" \
  -d '{"name": "test-vm"}'
```

### Eliminar VM

```bash
curl -X POST http://localhost:8001/proxmox/delete \
  -H "Content-Type: application/json" \
  -d '{"name": "test-vm", "force": true}'
```

## 🤖 Integración AI

Puedes usar comandos en lenguaje natural:

```bash
curl -X POST http://localhost:8001/ai/ask \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "crea un cluster de docker swarm con 3 nodos"
  }'
```

## 📡 Endpoints Disponibles

| Endpoint | Método | Descripción |
|----------|--------|-------------|
| `/` | GET | Información de la API |
| `/proxmox/test` | GET | Test de conexión |
| `/proxmox/create` | POST | Crear VM/LXC |
| `/proxmox/list` | GET/POST | Listar VMs/LXC |
| `/proxmox/delete` | POST | Eliminar VM/LXC |
| `/proxmox/start` | POST | Iniciar VM/LXC |
| `/proxmox/stop` | POST | Detener VM/LXC |
| `/proxmox/restart` | POST | Reiniciar VM/LXC |
| `/proxmox/status` | GET/POST | Estado de VM/LXC |
| `/cluster/create` | POST | Crear cluster Swarm |
| `/credentials` | GET | Obtener credenciales |
| `/ai/ask` | POST | Preguntar a la AI |
| `/ai/execute` | POST | Ejecutar comando AI |

## 🔐 Autenticación en Proxmox

### Opción 1: Usuario y Contraseña

```bash
PROXMOX_USER=root@pam
PROXMOX_PASSWORD=tu_password
```

### Opción 2: API Token (Recomendado)

1. En Proxmox Web UI: `Datacenter > Permissions > API Tokens`
2. Crear nuevo token
3. Configurar en `.env`:

```bash
PROXMOX_USER=root@pam
PROXMOX_TOKEN_NAME=api-token-id
PROXMOX_TOKEN_VALUE=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
```

## 🐳 Clusters Soportados

- **Docker Swarm**: Manager + Workers con Portainer UI
- **Kubernetes (K3s)**: Cluster ligero de Kubernetes
- **Redis**: Servidor Redis standalone
- **Portainer**: UI de gestión de contenedores

## 📝 Notas

- Las VMs QEMU requieren templates o ISOs configuradas en Proxmox
- Los contenedores LXC requieren templates descargadas en Proxmox
- Para obtener IPs automáticamente, instala `qemu-guest-agent` en las VMs
- Los scripts de cluster requieren Ubuntu/Debian como sistema operativo

## 🛠️ Desarrollo

### Estructura del Proyecto

```
.
├── main.py                    # API principal
├── proxmox_client.py          # Cliente de Proxmox
├── create_vm_proxmox.py       # Creación de VMs/LXC
├── list_vms_proxmox.py        # Listado de VMs/LXC
├── delete_vm_proxmox.py       # Eliminación de VMs/LXC
├── vm_operations_proxmox.py   # Operaciones (start/stop/restart)
├── swarm_coordinator.py       # Coordinación de Swarm
├── ai_executor.py             # Ejecución de comandos AI
├── requirements.txt           # Dependencias
└── .env.example               # Ejemplo de configuración
```

## 🤝 Contribuir

Las contribuciones son bienvenidas! Por favor, abre un issue o pull request.

## 📄 Licencia

MIT License
