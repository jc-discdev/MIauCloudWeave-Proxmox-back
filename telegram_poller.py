import os
import time
import json
import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
BACKEND_URL = "http://localhost:8001"

if not TELEGRAM_BOT_TOKEN:
    print("❌ Error: TELEGRAM_BOT_TOKEN not found in .env")
    exit(1)

print(f"🤖 Telegram Bot Poller started for bot: {TELEGRAM_BOT_TOKEN[:10]}...")
print(f"📡 Backend URL: {BACKEND_URL}")

def get_updates(offset=None):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getUpdates"
    params = {'timeout': 30, 'offset': offset}
    try:
        response = requests.get(url, params=params)
        return response.json()
    except Exception as e:
        print(f"Error getting updates: {e}")
        return None

def send_message(chat_id, text):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    data = {'chat_id': chat_id, 'text': text, 'parse_mode': 'Markdown'}
    try:
        requests.post(url, data=data)
    except Exception as e:
        print(f"Error sending message: {e}")

def handle_list_command(chat_id):
    send_message(chat_id, "🔍 Buscando VMs y contenedores activos...")
    
    try:
        # Get Proxmox VMs and containers
        proxmox_res = requests.get(f"{BACKEND_URL}/proxmox/list")
        proxmox_data = proxmox_res.json()
        
        message = "📊 **Estado del Cluster Proxmox**\n\n"
        
        if proxmox_data.get('success') and proxmox_data.get('vms'):
            # Separate by type
            qemu_vms = [vm for vm in proxmox_data['vms'] if vm.get('type') == 'qemu']
            lxc_containers = [vm for vm in proxmox_data['vms'] if vm.get('type') == 'lxc']
            
            # QEMU VMs Section
            if qemu_vms:
                message += "🖥️ **Máquinas Virtuales (QEMU)**\n"
                for vm in qemu_vms:
                    name = vm.get('name', 'N/A')
                    status = vm.get('status', 'N/A')
                    ip = vm.get('ip', 'N/A')
                    cpu = vm.get('cpu', '?')
                    memory = vm.get('memory', '?')
                    vmid = vm.get('vmid', '?')
                    
                    icon = "🟢" if status == "running" else "🔴"
                    message += f"{icon} *{name}* (ID: {vmid})\n"
                    message += f"   IP: `{ip}`\n"
                    message += f"   Specs: {cpu} vCPU | {memory} MB RAM\n"
                    message += f"   Estado: {status}\n\n"
            
            # LXC Containers Section
            if lxc_containers:
                message += "📦 **Contenedores (LXC)**\n"
                for ct in lxc_containers:
                    name = ct.get('name', 'N/A')
                    status = ct.get('status', 'N/A')
                    ip = ct.get('ip', 'N/A')
                    cpu = ct.get('cpu', '?')
                    memory = ct.get('memory', '?')
                    vmid = ct.get('vmid', '?')
                    
                    icon = "🟢" if status == "running" else "🔴"
                    message += f"{icon} *{name}* (ID: {vmid})\n"
                    message += f"   IP: `{ip}`\n"
                    message += f"   Specs: {cpu} vCPU | {memory} MB RAM\n"
                    message += f"   Estado: {status}\n\n"
            
            if not qemu_vms and not lxc_containers:
                message += "_No hay VMs ni contenedores activos_\n"
        else:
            message += "_No hay VMs ni contenedores activos_\n"
        
        # Add summary
        total_vms = len(proxmox_data.get('vms', []))
        running_vms = len([vm for vm in proxmox_data.get('vms', []) if vm.get('status') == 'running'])
        message += f"\n📈 **Resumen**: {running_vms}/{total_vms} activos"
        
        send_message(chat_id, message)
        
    except Exception as e:
        send_message(chat_id, f"❌ Error al conectar con el backend: {str(e)}")

def handle_credentials_command(chat_id):
    """Get stored credentials for all instances"""
    send_message(chat_id, "🔐 Obteniendo credenciales...")
    
    try:
        creds_res = requests.get(f"{BACKEND_URL}/credentials")
        creds_data = creds_res.json()
        
        if creds_data.get('success') and creds_data.get('credentials'):
            message = "🔑 **Credenciales Almacenadas**\n\n"
            
            for name, creds in creds_data['credentials'].items():
                message += f"*{name}*\n"
                message += f"   Usuario: `{creds.get('username', 'N/A')}`\n"
                message += f"   Password: `{creds.get('password', 'N/A')}`\n"
                message += f"   IP: `{creds.get('ip', 'N/A')}`\n"
                message += f"   Tipo: {creds.get('type', 'N/A')}\n"
                message += f"   VMID: {creds.get('vmid', 'N/A')}\n\n"
            
            send_message(chat_id, message)
        else:
            send_message(chat_id, "ℹ️ No hay credenciales almacenadas")
    
    except Exception as e:
        send_message(chat_id, f"❌ Error al obtener credenciales: {str(e)}")

def handle_help_command(chat_id):
    """Show available commands"""
    message = """🤖 **MIauCloudWeave - Proxmox Manager Bot**

**Comandos disponibles:**

/start - Iniciar el bot
/list - Ver todas las VMs y contenedores
/credentials - Ver credenciales almacenadas
/help - Mostrar esta ayuda

**Características:**
• Gestión de VMs QEMU
• Gestión de contenedores LXC
• Clusters Docker Swarm
• Notificaciones automáticas
"""
    send_message(chat_id, message)

def main():
    offset = None
    while True:
        updates = get_updates(offset)
        if updates and updates.get('ok'):
            for update in updates['result']:
                offset = update['update_id'] + 1
                
                if 'message' in update and 'text' in update['message']:
                    text = update['message']['text']
                    chat_id = update['message']['chat']['id']
                    
                    print(f"📩 Received: {text} from {chat_id}")
                    
                    if text == '/start':
                        send_message(chat_id, "👋 ¡Hola! Soy tu Proxmox Cloud Manager Bot.\n\nUsa /help para ver los comandos disponibles.")
                    elif text == '/list':
                        handle_list_command(chat_id)
                    elif text == '/credentials':
                        handle_credentials_command(chat_id)
                    elif text == '/help':
                        handle_help_command(chat_id)
                    else:
                        send_message(chat_id, f"❓ Comando no reconocido: {text}\n\nUsa /help para ver los comandos disponibles.")
        
        time.sleep(1)

if __name__ == "__main__":
    try:
        # Check if requests is installed
        import requests
        main()
    except ImportError:
        print("❌ Error: 'requests' library is missing.")
        print("Run: pip install requests")
