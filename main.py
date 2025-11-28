"""
MIauCloudWeave - Proxmox API Backend
Manages VMs and LXC containers on Proxmox VE for cluster deployment
"""

import urllib.request
import urllib.parse
import json
import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List
from dotenv import load_dotenv
import time
from datetime import datetime, timedelta
import paramiko
import openai

# Proxmox modules
from proxmox_client import get_proxmox_client, get_default_node, test_connection
from create_vm_proxmox import create_vm
from list_vms_proxmox import list_vms, find_vm_by_name
from delete_vm_proxmox import delete_vm
from vm_operations_proxmox import start_vm, stop_vm, restart_vm, get_vm_status
from swarm_coordinator import get_swarm_info_via_ssh, prepare_worker_script, prepare_manager_script
from ai_executor import execute_ai_command

load_dotenv()

# Telegram Configuration
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://innwater.eurecatprojects.com/lite-llm/")

# Initialize OpenAI Client
ai_client = None
if OPENAI_API_KEY:
    try:
        ai_client = openai.Client(api_key=OPENAI_API_KEY, base_url=OPENAI_BASE_URL)
    except Exception as e:
        print(f"Failed to initialize OpenAI client: {e}")

# In-memory storage for instance credentials
_instance_credentials = {}


def log_to_telegram(message: str):
    """Send log message to Telegram"""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print(f"Telegram logger not configured. Message: {message}")
        return
    
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    data = urllib.parse.urlencode({"chat_id": TELEGRAM_CHAT_ID, "text": message}).encode()
    try:
        req = urllib.request.Request(url, data=data)
        urllib.request.urlopen(req)
    except Exception as e:
        print(f"Failed to send Telegram log: {e}")


# FastAPI App with metadata
app = FastAPI(
    title="MIauCloudWeave - Proxmox API",
    description="""
    🚀 **API para gestión de infraestructura en Proxmox VE**
    
    Esta API permite gestionar máquinas virtuales (QEMU) y contenedores LXC en Proxmox,
    con soporte para despliegue automático de clusters Docker Swarm y Kubernetes.
    
    ## Características
    
    * 🖥️ **VMs QEMU**: Máquinas virtuales completas
    * 📦 **Contenedores LXC**: Contenedores ligeros y rápidos
    * 🐳 **Docker Swarm**: Despliegue automático de clusters
    * ☸️ **Kubernetes**: Instalación de K3s
    * 🤖 **AI Integration**: Comandos en lenguaje natural
    * 📱 **Telegram**: Notificaciones en tiempo real
    
    ## Endpoints Principales
    
    * `/proxmox/*` - Gestión de VMs y contenedores
    * `/cluster/*` - Despliegue de clusters
    * `/ai/*` - Integración con AI
    * `/credentials` - Gestión de credenciales
    """,
    version="2.0.0",
    contact={
        "name": "MIauCloudWeave Team",
        "url": "https://github.com/your-repo",
    },
    license_info={
        "name": "MIT",
    },
)

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000", 
        "http://127.0.0.1:3000", 
        "http://localhost:4321", 
        "http://127.0.0.1:4321"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

# --- Startup Scripts ---
STARTUP_SCRIPTS = {
    "kubernetes": """
apt-get update
apt-get install -y curl
curl -sfL https://get.k3s.io | sh -
""",
    "docker-swarm": """
apt-get update
apt-get install -y docker.io docker-compose
systemctl enable docker
systemctl start docker
usermod -aG docker ubuntu
timeout 60s bash -c 'until docker info; do sleep 2; done'
docker swarm init || true
docker run -d -p 8000:8000 -p 9443:9443 --name portainer --restart=always -v /var/run/docker.sock:/var/run/docker.sock -v portainer_data:/data portainer/portainer-ce:latest
""",
    "docker-swarm-manager": """
set -x
export DEBIAN_FRONTEND=noninteractive

log_telegram() {
    MSG="$1"
    curl -s -X POST https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage \\
        -d chat_id={TELEGRAM_CHAT_ID} \\
        -d text="🔹 [Proxmox-Manager] $MSG" >/dev/null || true
}

HOSTNAME=$(hostname)
PUBLIC_IP=$(hostname -I | awk '{print $1}')

log_telegram "🚀 [Manager] Iniciando configuración en $HOSTNAME
⏱️ Tiempo estimado: 3-5 minutos
📍 IP: $PUBLIC_IP"

# Firewall configuration
iptables -F
iptables -P INPUT ACCEPT
iptables -P FORWARD ACCEPT
iptables -P OUTPUT ACCEPT
ufw disable || true

# Allow Swarm and Portainer ports
iptables -A INPUT -p tcp --dport 2377 -j ACCEPT
iptables -A INPUT -p tcp --dport 7946 -j ACCEPT
iptables -A INPUT -p udp --dport 7946 -j ACCEPT
iptables -A INPUT -p udp --dport 4789 -j ACCEPT
iptables -A INPUT -p tcp --dport 9443 -j ACCEPT
iptables -A INPUT -p tcp --dport 8000 -j ACCEPT

# Wait for apt lock
while fuser /var/lib/dpkg/lock >/dev/null 2>&1 ; do sleep 1 ; done
while fuser /var/lib/apt/lists/lock >/dev/null 2>&1 ; do sleep 1 ; done

log_telegram "📦 [Manager] Instalando Docker, Docker Compose, curl y jq..."
apt-get update
apt-get install -y docker.io docker-compose curl jq

systemctl enable docker
systemctl start docker
usermod -aG docker ubuntu

log_telegram "🌐 [Manager] IP detectada: ${PUBLIC_IP}"

# Initialize Swarm
log_telegram "🐝 [Manager] Inicializando Docker Swarm..."
docker swarm init --advertise-addr ${PUBLIC_IP} || true

timeout 60s bash -c 'until docker info; do sleep 2; done'

# Get tokens
WORKER_TOKEN=$(docker swarm join-token -q worker)
MANAGER_TOKEN=$(docker swarm join-token -q manager)

# Save tokens
cat > /tmp/swarm_info.json <<EOF
{
  "vpn_ip": "${PUBLIC_IP}",
  "worker_token": "${WORKER_TOKEN}",
  "manager_token": "${MANAGER_TOKEN}"
}
EOF

# Install Portainer
docker run -d -p 8000:8000 -p 9443:9443 --name portainer --restart=always \\
  -v /var/run/docker.sock:/var/run/docker.sock -v portainer_data:/data \\
  portainer/portainer-ce:latest

log_telegram "🎨 [Manager] Desplegando Portainer..."
timeout 60s bash -c 'until curl -k -s https://localhost:9443 >/dev/null; do sleep 2; done'

log_telegram "✅ [Manager] ¡SWARM MANAGER LISTO!

🎯 Acceso a Portainer:
   https://${PUBLIC_IP}:9443

📊 Estado del Cluster:
   • Manager: $HOSTNAME (${PUBLIC_IP})
   • Puertos abiertos: 2377, 7946, 4789, 9443, 8000"
echo "Swarm manager initialized. Public IP: ${PUBLIC_IP}"
""",
    "docker-swarm-worker": """
set -x
export DEBIAN_FRONTEND=noninteractive

log_telegram() {
    MSG="$1"
    curl -s -X POST https://api.telegram.org/botTELEGRAM_BOT_TOKEN_PLACEHOLDER/sendMessage \\
        -d chat_id=TELEGRAM_CHAT_ID_PLACEHOLDER \\
        -d text="🔸 [Proxmox-Worker] $MSG" >/dev/null || true
}

HOSTNAME=$(hostname)
WORKER_IP=$(hostname -I | awk '{print $1}')
log_telegram "🔧 [Worker] Iniciando configuración en $HOSTNAME
📍 IP Local: $WORKER_IP"

# Firewall
iptables -F
ufw disable || true

# Wait for apt lock
while fuser /var/lib/dpkg/lock >/dev/null 2>&1 ; do sleep 1 ; done
while fuser /var/lib/apt/lists/lock >/dev/null 2>&1 ; do sleep 1 ; done

log_telegram "📦 [Worker] Instalando Docker..."
apt-get update
apt-get install -y docker.io docker-compose curl

systemctl enable docker
systemctl start docker
usermod -aG docker ubuntu

timeout 60s bash -c 'until docker info; do sleep 2; done'

MANAGER_IP_CLEAN=$(echo MANAGER_IP_PLACEHOLDER | cut -d':' -f1)
log_telegram "🔗 [Worker] Conectando al Swarm Manager...
📡 Manager IP: $MANAGER_IP_CLEAN"

# Join swarm
docker swarm join --token WORKER_TOKEN_PLACEHOLDER MANAGER_IP_PLACEHOLDER:2377

log_telegram "✅ [Worker] ¡Worker conectado exitosamente!

📊 Información del nodo:
   • Hostname: $HOSTNAME
   • IP Local: $WORKER_IP
   • Manager: $MANAGER_IP_CLEAN"

echo "Joined swarm as worker"
""",
    "redis": """
apt-get update
apt-get install -y redis-server
systemctl enable redis-server
systemctl start redis-server
sed -i 's/bind 127.0.0.1 ::1/bind 0.0.0.0/' /etc/redis/redis.conf
systemctl restart redis-server
""",
    "portainer": """
apt-get update
apt-get install -y docker.io docker-compose
systemctl enable docker
systemctl start docker
usermod -aG docker ubuntu
timeout 60s bash -c 'until docker info; do sleep 2; done'
docker run -d -p 8000:8000 -p 9443:9443 --name portainer --restart=always -v /var/run/docker.sock:/var/run/docker.sock -v portainer_data:/data portainer/portainer-ce:latest
"""
}

SERVICE_INFO = {
    "kubernetes": {
        "ports": [6443],
        "protocol": "tcp",
        "instructions": "K3s is installing. Access via port 6443. Config at /etc/rancher/k3s/k3s.yaml"
    },
    "docker-swarm": {
        "ports": [2377, 7946, 4789, 9443, 8000],
        "protocol": "tcp/udp",
        "instructions": "Docker Swarm initialized. Portainer UI available at https://<IP>:9443"
    },
    "docker-swarm-manager": {
        "ports": [2377, 7946, 4789, 8000, 9443],
        "protocol": "tcp",
        "instructions": "Docker Swarm Manager. Portainer at https://<IP>:9443"
    },
    "docker-swarm-worker": {
        "ports": [2377, 7946, 4789],
        "protocol": "tcp",
        "instructions": "Docker Swarm Worker. Connected to manager."
    },
    "redis": {
        "ports": [6379],
        "protocol": "tcp",
        "instructions": "Redis server running on port 6379."
    },
    "portainer": {
        "ports": [9443, 8000],
        "protocol": "tcp",
        "instructions": "Portainer UI available at https://<IP>:9443"
    }
}

# --- Request Models ---

class ProxmoxCreateRequest(BaseModel):
    node: Optional[str] = None
    name: str
    vm_type: str = "qemu"  # "qemu" or "lxc"
    cores: int = 2
    memory: int = 2048
    disk_size: int = 10
    template: Optional[int] = None
    iso: Optional[str] = None
    lxc_template: Optional[str] = None
    storage: Optional[str] = None
    bridge: Optional[str] = None
    cluster_type: Optional[str] = None
    count: int = 1
    ssh_key: Optional[str] = None
    password: Optional[str] = None
    start: bool = True


class ProxmoxListRequest(BaseModel):
    node: Optional[str] = None
    status: Optional[str] = None
    vm_type: Optional[str] = None


class ProxmoxDeleteRequest(BaseModel):
    vmid: Optional[int] = None
    name: Optional[str] = None
    node: Optional[str] = None
    force: bool = True


class ProxmoxActionRequest(BaseModel):
    vmid: Optional[int] = None
    name: Optional[str] = None
    node: Optional[str] = None


class ClusterCreateRequest(BaseModel):
    manager: ProxmoxCreateRequest
    workers: Optional[List[ProxmoxCreateRequest]] = None
    total_nodes: Optional[int] = None


class AIRequest(BaseModel):
    prompt: str
    context: Optional[str] = None


# --- Endpoints ---

@app.get("/", tags=["General"], summary="API Information")
def root():
    """Get API information, version, and available endpoints"""
    return {
        "name": "MIauCloudWeave - Proxmox API",
        "version": "2.0.0",
        "provider": "Proxmox VE",
        "endpoints": [
            "/proxmox/test",
            "/proxmox/create",
            "/proxmox/list",
            "/proxmox/delete",
            "/proxmox/start",
            "/proxmox/stop",
            "/proxmox/restart",
            "/proxmox/status",
            "/cluster/create",
            "/credentials",
            "/ai/ask",
            "/ai/execute"
        ]
    }


@app.get("/proxmox/test", tags=["Proxmox"], summary="Test Connection")
def api_proxmox_test():
    """Test connection to Proxmox server and return version information"""
    try:
        result = test_connection()
        if result['success']:
            log_to_telegram(f"✅ Proxmox connection test successful: v{result['version']}")
        return result
    except Exception as e:
        log_to_telegram(f"❌ Proxmox connection test failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/proxmox/create", tags=["Proxmox"], summary="Create VM/Container")
def api_proxmox_create(req: ProxmoxCreateRequest):
    """Create a new QEMU VM or LXC container with optional cluster configuration"""
    log_to_telegram(f"🚀 Creating Proxmox {req.vm_type.upper()}: {req.name} ({req.cluster_type or 'base'})")
    try:
        startup_script = STARTUP_SCRIPTS.get(req.cluster_type) if req.cluster_type else None
        
        # Replace Telegram placeholders in script
        if startup_script and TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
            startup_script = startup_script.replace("{TELEGRAM_BOT_TOKEN}", TELEGRAM_BOT_TOKEN)
            startup_script = startup_script.replace("{TELEGRAM_CHAT_ID}", TELEGRAM_CHAT_ID)
        
        vms = create_vm(
            node=req.node,
            name=req.name,
            vm_type=req.vm_type,
            cores=req.cores,
            memory=req.memory,
            disk_size=req.disk_size,
            template=req.template,
            iso=req.iso,
            lxc_template=req.lxc_template,
            storage=req.storage,
            bridge=req.bridge,
            startup_script=startup_script,
            count=req.count,
            ssh_key=req.ssh_key,
            password=req.password,
            start=req.start
        )
        
        # Log to Telegram and store credentials
        for vm in vms:
            if vm.get('success'):
                msg = f"✅ Proxmox {req.vm_type.upper()} Created!\n"
                msg += f"Name: {vm['name']}\n"
                msg += f"VMID: {vm['vmid']}\n"
                msg += f"IP: {vm.get('ip', 'pending')}\n"
                msg += f"User: {vm['username']}\n"
                msg += f"Password: {vm['password']}\n"
                msg += f"Cluster: {req.cluster_type or 'base'}"
                log_to_telegram(msg)
                
                # Store credentials
                _instance_credentials[vm['name']] = {
                    'username': vm['username'],
                    'password': vm['password'],
                    'ip': vm.get('ip'),
                    'provider': 'proxmox',
                    'node': vm['node'],
                    'vmid': vm['vmid'],
                    'type': vm['type']
                }
        
        return {"success": True, "vms": vms}
    except Exception as e:
        log_to_telegram(f"❌ Error creating Proxmox {req.vm_type}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/proxmox/list", tags=["Proxmox"], summary="List VMs/Containers")
@app.post("/proxmox/list", tags=["Proxmox"], summary="List VMs/Containers")
def api_proxmox_list(req: Optional[ProxmoxListRequest] = None, node: Optional[str] = None, status: Optional[str] = None, vm_type: Optional[str] = None):
    """List all VMs and containers, optionally filtered by node, status, or type"""
    try:
        if req:
            vms = list_vms(node=req.node, status=req.status, vm_type=req.vm_type)
        else:
            vms = list_vms(node=node, status=status, vm_type=vm_type)
        
        return {"success": True, "count": len(vms), "vms": vms}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/proxmox/delete", tags=["Proxmox"], summary="Delete VM/Container")
def api_proxmox_delete(req: ProxmoxDeleteRequest):
    """Delete a VM or container by ID or name, with optional force stop"""
    log_to_telegram(f"🗑️ Deleting Proxmox VM/Container: {req.vmid or req.name}")
    try:
        success = delete_vm(vmid=req.vmid, name=req.name, node=req.node, force=req.force)
        log_to_telegram(f"✅ VM/Container deleted: {req.vmid or req.name}")
        
        # Remove from credentials
        if req.name and req.name in _instance_credentials:
            del _instance_credentials[req.name]
        
        return {"success": success}
    except Exception as e:
        log_to_telegram(f"❌ Error deleting VM/Container: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/proxmox/start", tags=["Proxmox - Operations"], summary="Start VM/Container")
def api_proxmox_start(req: ProxmoxActionRequest):
    """Start a stopped VM or container"""
    log_to_telegram(f"▶️ Starting VM/Container: {req.vmid or req.name}")
    try:
        start_vm(vmid=req.vmid, name=req.name, node=req.node)
        log_to_telegram(f"✅ VM/Container started: {req.vmid or req.name}")
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/proxmox/stop", tags=["Proxmox - Operations"], summary="Stop VM/Container")
def api_proxmox_stop(req: ProxmoxActionRequest):
    """Stop a running VM or container"""
    log_to_telegram(f"⏸️ Stopping VM/Container: {req.vmid or req.name}")
    try:
        stop_vm(vmid=req.vmid, name=req.name, node=req.node)
        log_to_telegram(f"✅ VM/Container stopped: {req.vmid or req.name}")
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/proxmox/restart", tags=["Proxmox - Operations"], summary="Restart VM/Container")
def api_proxmox_restart(req: ProxmoxActionRequest):
    """Restart a VM or container"""
    log_to_telegram(f"🔄 Restarting VM/Container: {req.vmid or req.name}")
    try:
        restart_vm(vmid=req.vmid, name=req.name, node=req.node)
        log_to_telegram(f"✅ VM/Container restarted: {req.vmid or req.name}")
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/proxmox/status")
@app.post("/proxmox/status")
def api_proxmox_status(req: Optional[ProxmoxActionRequest] = None, vmid: Optional[int] = None, name: Optional[str] = None, node: Optional[str] = None):
    """Get VM or LXC container status"""
    try:
        if req:
            status = get_vm_status(vmid=req.vmid, name=req.name, node=req.node)
        else:
            status = get_vm_status(vmid=vmid, name=name, node=node)
        
        return {"success": True, "status": status}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/cluster/create", tags=["Clusters"], summary="Create Docker Swarm Cluster")
def api_cluster_create(req: ClusterCreateRequest):
    """Create a complete Docker Swarm cluster with manager and worker nodes"""
    log_to_telegram(f"🚀 Starting Proxmox cluster creation")
    
    try:
        # Step 1: Create manager
        manager_req = req.manager
        manager_req.cluster_type = "docker-swarm-manager"
        
        log_to_telegram(f"📍 Creating Swarm manager: {manager_req.name}")
        
        manager_result = api_proxmox_create(manager_req)
        manager_vm = manager_result['vms'][0]
        manager_ip = manager_vm.get('ip')
        manager_password = manager_vm['password']
        
        if not manager_ip:
            raise ValueError("Manager IP not available")
        
        log_to_telegram(f"⏳ Waiting for manager to initialize Swarm...")
        time.sleep(30)  # Wait for manager to initialize
        
        # Step 2: Get swarm info via SSH
        try:
            swarm_info = get_swarm_info_via_ssh(manager_ip, password=manager_password, max_retries=20)
            worker_token = swarm_info['worker_token']
            
            log_to_telegram(f"✅ Manager ready! IP: {manager_ip}")
        except Exception as e:
            log_to_telegram(f"❌ Failed to get swarm info: {e}")
            return {"success": False, "error": str(e), "manager": manager_result}
        
        # Step 3: Create workers
        worker_results = []
        if req.workers:
            for worker_req in req.workers:
                worker_req.cluster_type = "docker-swarm-worker"
                
                # Prepare worker script with token and manager IP
                worker_script = prepare_worker_script(
                    STARTUP_SCRIPTS["docker-swarm-worker"],
                    worker_token,
                    manager_ip,
                    telegram_token=TELEGRAM_BOT_TOKEN,
                    telegram_chat_id=TELEGRAM_CHAT_ID
                )
                
                # Override startup script
                original_cluster_type = worker_req.cluster_type
                worker_req.cluster_type = None  # Disable auto script
                
                log_to_telegram(f"📍 Creating worker: {worker_req.name}")
                
                # Create worker with custom script
                worker_vms = create_vm(
                    node=worker_req.node,
                    name=worker_req.name,
                    vm_type=worker_req.vm_type,
                    cores=worker_req.cores,
                    memory=worker_req.memory,
                    disk_size=worker_req.disk_size,
                    template=worker_req.template,
                    iso=worker_req.iso,
                    lxc_template=worker_req.lxc_template,
                    storage=worker_req.storage,
                    bridge=worker_req.bridge,
                    startup_script=worker_script,
                    count=worker_req.count,
                    ssh_key=worker_req.ssh_key,
                    password=worker_req.password,
                    start=worker_req.start
                )
                
                worker_results.extend(worker_vms)
                
                # Log worker credentials
                for worker in worker_vms:
                    if worker.get('success'):
                        msg = f"🔑 [Worker] Credenciales:\n"
                        msg += f"Nombre: {worker['name']}\n"
                        msg += f"IP: {worker.get('ip', 'pending')}\n"
                        msg += f"Usuario: {worker['username']}\n"
                        msg += f"Contraseña: {worker['password']}"
                        log_to_telegram(msg)
                        
                        # Store credentials
                        _instance_credentials[worker['name']] = {
                            'username': worker['username'],
                            'password': worker['password'],
                            'ip': worker.get('ip'),
                            'provider': 'proxmox',
                            'node': worker['node'],
                            'vmid': worker['vmid'],
                            'type': worker['type'],
                            'role': 'worker'
                        }
        
        log_to_telegram(f"✅ Cluster created! Manager: {manager_ip}, Workers: {len(worker_results)}")
        
        return {
            "success": True,
            "manager": manager_result,
            "workers": worker_results,
            "portainer_url": f"https://{manager_ip}:9443"
        }
        
    except Exception as e:
        log_to_telegram(f"❌ Cluster creation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/credentials", tags=["Credentials"], summary="Get Credentials")
def api_get_credentials(instance_name: Optional[str] = None):
    """Retrieve stored credentials for VMs/containers (username, password, IP)"""
    try:
        if instance_name:
            if instance_name in _instance_credentials:
                return {
                    "success": True,
                    "instance_name": instance_name,
                    "credentials": _instance_credentials[instance_name]
                }
            else:
                return {
                    "success": False,
                    "message": f"No credentials found for instance: {instance_name}"
                }
        else:
            return {
                "success": True,
                "count": len(_instance_credentials),
                "credentials": _instance_credentials
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/ai/ask", tags=["AI Assistant"], summary="Ask AI")
def api_ai_ask(req: AIRequest):
    """Ask the AI assistant for infrastructure advice or generate commands"""
    if not ai_client:
        raise HTTPException(status_code=503, detail="AI service not configured (missing API key)")
    
    try:
        system_prompt = """You are an expert Cloud Architect Assistant for 'MIauCloudWeave - Proxmox Manager'.
Your goal is to help users design and manage infrastructure on Proxmox VE.

Capabilities of this platform:
1. Create VMs (QEMU) and LXC Containers on Proxmox
2. Docker Swarm: Automated setup of Swarm clusters (Manager + Workers)
3. Kubernetes (K3s): Lightweight K8s clusters
4. Services: Redis, Portainer (management UI)
5. Management: Start, Stop, Restart, Delete VMs/Containers

**CRITICAL INSTRUCTION - When to return JSON:**

If the user's message contains ANY of these action keywords/phrases, you MUST return ONLY a JSON object:
- CREATE: "create", "crea", "deploy", "despliega", "provision", "launch", "start"
- DELETE: "delete", "elimina", "borra", "remove", "destroy", "terminate"
- LIST: "list", "lista", "show", "muestra", "ver", "get", "dame"

**JSON Format (NO markdown, NO backticks):**
{"command": "create_vm|create_cluster|delete_vm|list_vms", "parameters": {...}, "explanation": "I will..."}

**Examples:**

User: "create a swarm with 3 nodes"
Response: {"command": "create_cluster", "parameters": {"manager": {"name": "swarm-manager", "vm_type": "qemu", "cores": 2, "memory": 2048}, "workers": [{"name": "swarm-worker", "vm_type": "lxc", "cores": 1, "memory": 1024, "count": 2}]}, "explanation": "I will create a Docker Swarm cluster with 1 manager and 2 workers."}

User: "listame mis VMs"
Response: {"command": "list_vms", "parameters": {}, "explanation": "I will list all your VMs and containers."}

User: "what is docker swarm?" (question, not action)
Response: Docker Swarm is a container orchestration platform...

**REMEMBER:** If user wants to DO something (action verb), return JSON. If user asks ABOUT something (question), return text.
"""
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": req.prompt}
        ]
        
        if req.context:
            messages.insert(1, {"role": "system", "content": f"Current Context: {req.context}"})

        response = ai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages
        )
        
        return {"response": response.choices[0].message.content}
        
    except Exception as e:
        log_to_telegram(f"❌ AI Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/ai/execute", tags=["AI Assistant"], summary="Execute AI Command")
def api_ai_execute(command_json: dict):
    """Execute a command that was generated by the AI assistant"""
    if not ai_client:
        raise HTTPException(status_code=503, detail="AI service not configured")
    
    try:
        result = execute_ai_command(
            command_json=command_json,
            api_create_func=api_proxmox_create,
            api_cluster_create_func=api_cluster_create,
            api_delete_func=api_proxmox_delete,
            api_list_func=api_proxmox_list,
            log_telegram_func=log_to_telegram
        )
        
        return result
        
    except Exception as e:
        log_to_telegram(f"❌ AI Execution Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
