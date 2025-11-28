"""
Proxmox VM and LXC Container Creation Module
Supports both QEMU VMs and LXC containers
"""

from proxmox_client import get_proxmox_client, get_default_node, get_default_storage, get_default_bridge
import secrets
import string
import time
import os
from typing import Optional, Dict, List


def generate_password(length: int = 14) -> str:
    """
    Generates a secure random password.
    
    Args:
        length: Password length
    
    Returns:
        Secure password string
    """
    alphabet = string.ascii_letters + string.digits + "!@#$%&*()-_=+"
    while True:
        pw = ''.join(secrets.choice(alphabet) for _ in range(length))
        if (any(c.islower() for c in pw) and any(c.isupper() for c in pw)
                and any(c.isdigit() for c in pw) and any(c in "!@#$%&*()-_=+" for c in pw)):
            return pw


def create_vm(
    node: Optional[str] = None,
    vmid: Optional[int] = None,
    name: str = "vm",
    vm_type: str = "qemu",  # "qemu" or "lxc"
    cores: int = 2,
    memory: int = 2048,  # MB
    disk_size: int = 10,  # GB
    template: Optional[int] = None,  # Template VMID to clone
    iso: Optional[str] = None,  # ISO file for QEMU
    lxc_template: Optional[str] = None,  # LXC template name
    storage: Optional[str] = None,
    bridge: Optional[str] = None,
    startup_script: Optional[str] = None,
    count: int = 1,
    ssh_key: Optional[str] = None,
    password: Optional[str] = None,
    start: bool = True
) -> List[Dict]:
    """
    Creates one or more VMs or LXC containers in Proxmox.
    
    Args:
        node: Proxmox node name (default from env)
        vmid: VM/Container ID (auto-assigned if None)
        name: Base name for VM/Container
        vm_type: "qemu" for VM or "lxc" for container
        cores: Number of CPU cores
        memory: RAM in MB
        disk_size: Disk size in GB
        template: Template VMID to clone (for QEMU)
        iso: ISO file name (for QEMU, e.g., "local:iso/ubuntu-22.04.iso")
        lxc_template: LXC template (e.g., "ubuntu-22.04-standard_22.04-1_amd64.tar.zst")
        storage: Storage pool (default from env)
        bridge: Network bridge (default from env)
        startup_script: Cloud-init or startup script
        count: Number of VMs/containers to create
        ssh_key: SSH public key
        password: Password (auto-generated if None)
        start: Start VM/container after creation
    
    Returns:
        List of created VMs/containers with their details
    
    Example:
        >>> # Create a QEMU VM
        >>> vms = create_vm(name="test-vm", vm_type="qemu", cores=2, memory=2048)
        >>> # Create an LXC container
        >>> containers = create_vm(name="test-ct", vm_type="lxc", cores=1, memory=512)
    """
    proxmox = get_proxmox_client()
    node = node or get_default_node()
    storage = storage or get_default_storage()
    bridge = bridge or get_default_bridge()
    
    results = []
    
    for i in range(count):
        # Generate unique VMID if not provided
        if vmid is None:
            current_vmid = proxmox.cluster.nextid.get()
        else:
            current_vmid = vmid + i
        
        # Generate unique name for multiple VMs
        vm_name = f"{name}-{i+1}" if count > 1 else name
        
        # Generate password if not provided
        vm_password = password or generate_password()
        
        try:
            if vm_type == "qemu":
                # Create QEMU VM
                vm_info = _create_qemu_vm(
                    proxmox, node, current_vmid, vm_name, cores, memory, disk_size,
                    template, iso, storage, bridge, startup_script, ssh_key, vm_password, start
                )
            elif vm_type == "lxc":
                # Create LXC Container
                vm_info = _create_lxc_container(
                    proxmox, node, current_vmid, vm_name, cores, memory, disk_size,
                    lxc_template, storage, bridge, startup_script, ssh_key, vm_password, start
                )
            else:
                raise ValueError(f"Invalid vm_type: {vm_type}. Must be 'qemu' or 'lxc'")
            
            results.append(vm_info)
            
        except Exception as e:
            print(f"Error creating {vm_type} {vm_name}: {e}")
            results.append({
                'vmid': current_vmid,
                'name': vm_name,
                'error': str(e),
                'success': False
            })
    
    return results


def _create_qemu_vm(
    proxmox, node, vmid, name, cores, memory, disk_size,
    template, iso, storage, bridge, startup_script, ssh_key, password, start
) -> Dict:
    """Creates a QEMU VM"""
    
    # Base configuration
    config = {
        'vmid': vmid,
        'name': name,
        'cores': cores,
        'memory': memory,
        'net0': f'virtio,bridge={bridge}',
        'ostype': 'l26',  # Linux 2.6+
        'agent': 'enabled=1',  # Enable QEMU guest agent
    }
    
    # Method 1: Clone from template (FASTEST)
    if template:
        print(f"Cloning VM from template {template}...")
        proxmox.nodes(node).qemu(template).clone.post(
            newid=vmid,
            name=name,
            full=1  # Full clone
        )
        # Wait for clone to complete
        time.sleep(5)
        
        # Update configuration
        proxmox.nodes(node).qemu(vmid).config.put(
            cores=cores,
            memory=memory
        )
    
    # Method 2: Create from ISO
    else:
        if not iso:
            # Use default Ubuntu ISO if available
            iso = os.getenv('PROXMOX_DEFAULT_ISO', 'local:iso/ubuntu-22.04-server.iso')
        
        config.update({
            'ide2': f'{iso},media=cdrom',
            'scsi0': f'{storage}:{disk_size}',
            'scsihw': 'virtio-scsi-pci',
            'boot': 'order=scsi0;ide2',
            'serial0': 'socket',  # For console access
            'vga': 'serial0'
        })
        
        print(f"Creating VM from ISO {iso}...")
        proxmox.nodes(node).qemu.create(**config)
    
    # Configure cloud-init if available
    if startup_script or ssh_key or password:
        cloud_init_config = {
            'ciuser': 'ubuntu',
            'cipassword': password,
            'ipconfig0': 'ip=dhcp',
            'nameserver': '8.8.8.8'
        }
        
        if ssh_key:
            cloud_init_config['sshkeys'] = ssh_key.replace('\n', '%0A')
        
        # Add cloud-init drive
        try:
            proxmox.nodes(node).qemu(vmid).config.put(**cloud_init_config)
            
            # Add custom startup script if provided
            if startup_script:
                # Create cloud-init user-data snippet
                snippet_content = f"""#cloud-config
password: {password}
chpasswd: {{ expire: False }}
ssh_pwauth: True
runcmd:
  - |
{startup_script}
"""
                # Note: Uploading snippets requires additional API calls
                # For now, we'll use the basic cloud-init config
                
        except Exception as e:
            print(f"Warning: Could not configure cloud-init: {e}")
    
    # Start the VM if requested
    if start:
        print(f"Starting VM {vmid}...")
        proxmox.nodes(node).qemu(vmid).status.start.post()
        time.sleep(10)  # Wait for VM to start
    
    # Get VM status and IP
    vm_status = proxmox.nodes(node).qemu(vmid).status.current.get()
    ip_address = _get_vm_ip(proxmox, node, vmid, vm_type='qemu')
    
    return {
        'vmid': vmid,
        'name': name,
        'node': node,
        'type': 'qemu',
        'ip': ip_address,
        'password': password,
        'username': 'ubuntu',
        'cores': cores,
        'memory': memory,
        'disk_size': disk_size,
        'status': vm_status.get('status', 'unknown'),
        'success': True
    }


def _create_lxc_container(
    proxmox, node, vmid, name, cores, memory, disk_size,
    lxc_template, storage, bridge, startup_script, ssh_key, password, start
) -> Dict:
    """Creates an LXC container"""
    
    # Get LXC template
    if not lxc_template:
        lxc_template = os.getenv('PROXMOX_LXC_TEMPLATE', 'ubuntu-22.04-standard_22.04-1_amd64.tar.zst')
    
    # Determine template storage and path
    iso_storage = os.getenv('PROXMOX_ISO_STORAGE', 'local')
    template_path = f'{iso_storage}:vztmpl/{lxc_template}'
    
    # Base configuration
    config = {
        'vmid': vmid,
        'hostname': name,
        'cores': cores,
        'memory': memory,
        'swap': 512,
        'rootfs': f'{storage}:{disk_size}',
        'ostemplate': template_path,
        'net0': f'name=eth0,bridge={bridge},ip=dhcp',
        'unprivileged': 1,  # Unprivileged container (more secure)
        'features': 'nesting=1',  # Enable nesting for Docker
        'password': password,
        'start': 1 if start else 0
    }
    
    if ssh_key:
        config['ssh-public-keys'] = ssh_key
    
    print(f"Creating LXC container from template {lxc_template}...")
    proxmox.nodes(node).lxc.create(**config)
    
    # Wait for container to be created
    time.sleep(5)
    
    # Execute startup script if provided
    if startup_script and start:
        time.sleep(10)  # Wait for container to fully start
        try:
            # Execute script inside container
            script_lines = startup_script.strip().split('\n')
            for line in script_lines:
                if line.strip():
                    proxmox.nodes(node).lxc(vmid).exec.post(command=line)
        except Exception as e:
            print(f"Warning: Could not execute startup script: {e}")
    
    # Get container status and IP
    ct_status = proxmox.nodes(node).lxc(vmid).status.current.get()
    ip_address = _get_vm_ip(proxmox, node, vmid, vm_type='lxc')
    
    return {
        'vmid': vmid,
        'name': name,
        'node': node,
        'type': 'lxc',
        'ip': ip_address,
        'password': password,
        'username': 'root',
        'cores': cores,
        'memory': memory,
        'disk_size': disk_size,
        'status': ct_status.get('status', 'unknown'),
        'success': True
    }


def _get_vm_ip(proxmox, node, vmid, vm_type='qemu', max_attempts=30) -> Optional[str]:
    """
    Attempts to get the IP address of a VM or container.
    
    Args:
        proxmox: Proxmox API client
        node: Node name
        vmid: VM/Container ID
        vm_type: 'qemu' or 'lxc'
        max_attempts: Maximum number of attempts
    
    Returns:
        IP address or None
    """
    for attempt in range(max_attempts):
        try:
            if vm_type == 'qemu':
                # Try to get IP from QEMU guest agent
                agent_info = proxmox.nodes(node).qemu(vmid).agent('network-get-interfaces').get()
                for iface in agent_info.get('result', []):
                    if iface.get('name') != 'lo':
                        for ip_info in iface.get('ip-addresses', []):
                            if ip_info.get('ip-address-type') == 'ipv4':
                                return ip_info.get('ip-address')
            
            elif vm_type == 'lxc':
                # Get IP from LXC container config
                config = proxmox.nodes(node).lxc(vmid).config.get()
                # Try to get from interfaces
                interfaces = proxmox.nodes(node).lxc(vmid).interfaces.get()
                for iface in interfaces:
                    if iface.get('name') == 'eth0':
                        inet = iface.get('inet')
                        if inet:
                            return inet.split('/')[0]  # Remove CIDR notation
        
        except Exception as e:
            pass  # IP not available yet
        
        time.sleep(2)
    
    return None
