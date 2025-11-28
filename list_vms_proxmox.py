"""
Proxmox VM and LXC Container Listing Module
"""

from proxmox_client import get_proxmox_client, get_default_node
from typing import Optional, List, Dict


def list_vms(
    node: Optional[str] = None,
    status: Optional[str] = None,
    vm_type: Optional[str] = None  # "qemu", "lxc", or None for both
) -> List[Dict]:
    """
    Lists all VMs and/or LXC containers in Proxmox.
    
    Args:
        node: Specific node name (None = all nodes)
        status: Filter by status (running, stopped, etc.)
        vm_type: Filter by type ("qemu", "lxc", or None for both)
    
    Returns:
        List of VMs/containers with their details
    
    Example:
        >>> # List all VMs and containers
        >>> all_vms = list_vms()
        >>> # List only running QEMU VMs
        >>> running_vms = list_vms(status="running", vm_type="qemu")
        >>> # List only LXC containers
        >>> containers = list_vms(vm_type="lxc")
    """
    proxmox = get_proxmox_client()
    all_vms = []
    
    # Get list of nodes
    if node:
        nodes = [node]
    else:
        try:
            nodes = [n['node'] for n in proxmox.nodes.get()]
        except:
            # Fallback to default node if cluster info not available
            nodes = [get_default_node()]
    
    for node_name in nodes:
        # List QEMU VMs
        if vm_type is None or vm_type == "qemu":
            try:
                qemu_vms = _list_qemu_vms(proxmox, node_name, status)
                all_vms.extend(qemu_vms)
            except Exception as e:
                print(f"Error listing QEMU VMs on node {node_name}: {e}")
        
        # List LXC containers
        if vm_type is None or vm_type == "lxc":
            try:
                lxc_containers = _list_lxc_containers(proxmox, node_name, status)
                all_vms.extend(lxc_containers)
            except Exception as e:
                print(f"Error listing LXC containers on node {node_name}: {e}")
    
    return all_vms


def _list_qemu_vms(proxmox, node: str, status: Optional[str] = None) -> List[Dict]:
    """Lists QEMU VMs on a specific node"""
    vms = proxmox.nodes(node).qemu.get()
    result = []
    
    for vm in vms:
        # Filter by status if specified
        if status and vm.get('status') != status:
            continue
        
        # Get detailed configuration
        try:
            vm_config = proxmox.nodes(node).qemu(vm['vmid']).config.get()
            
            # Try to get IP address
            ip_address = None
            if vm.get('status') == 'running':
                try:
                    agent_info = proxmox.nodes(node).qemu(vm['vmid']).agent('network-get-interfaces').get()
                    for iface in agent_info.get('result', []):
                        if iface.get('name') != 'lo':
                            for ip_info in iface.get('ip-addresses', []):
                                if ip_info.get('ip-address-type') == 'ipv4':
                                    ip_address = ip_info.get('ip-address')
                                    break
                        if ip_address:
                            break
                except:
                    pass  # Guest agent not available
            
            result.append({
                'vmid': vm['vmid'],
                'name': vm['name'],
                'node': node,
                'type': 'qemu',
                'status': vm['status'],
                'cpu': vm.get('cpus', 0),
                'memory': vm.get('maxmem', 0) // (1024**2),  # Convert to MB
                'disk': vm.get('maxdisk', 0) // (1024**3),   # Convert to GB
                'uptime': vm.get('uptime', 0),
                'ip': ip_address,
                'template': vm_config.get('template', 0) == 1
            })
        except Exception as e:
            # If we can't get config, add basic info
            result.append({
                'vmid': vm['vmid'],
                'name': vm.get('name', f"vm-{vm['vmid']}"),
                'node': node,
                'type': 'qemu',
                'status': vm.get('status', 'unknown'),
                'cpu': vm.get('cpus', 0),
                'memory': vm.get('maxmem', 0) // (1024**2),
                'disk': vm.get('maxdisk', 0) // (1024**3),
                'uptime': vm.get('uptime', 0),
                'ip': None,
                'error': str(e)
            })
    
    return result


def _list_lxc_containers(proxmox, node: str, status: Optional[str] = None) -> List[Dict]:
    """Lists LXC containers on a specific node"""
    containers = proxmox.nodes(node).lxc.get()
    result = []
    
    for ct in containers:
        # Filter by status if specified
        if status and ct.get('status') != status:
            continue
        
        # Get detailed configuration
        try:
            ct_config = proxmox.nodes(node).lxc(ct['vmid']).config.get()
            
            # Try to get IP address
            ip_address = None
            if ct.get('status') == 'running':
                try:
                    interfaces = proxmox.nodes(node).lxc(ct['vmid']).interfaces.get()
                    for iface in interfaces:
                        if iface.get('name') == 'eth0':
                            inet = iface.get('inet')
                            if inet:
                                ip_address = inet.split('/')[0]  # Remove CIDR notation
                                break
                except:
                    pass  # Interface info not available
            
            result.append({
                'vmid': ct['vmid'],
                'name': ct.get('name', ct_config.get('hostname', f"ct-{ct['vmid']}")),
                'node': node,
                'type': 'lxc',
                'status': ct['status'],
                'cpu': ct.get('cpus', 0),
                'memory': ct.get('maxmem', 0) // (1024**2),  # Convert to MB
                'disk': ct.get('maxdisk', 0) // (1024**3),   # Convert to GB
                'uptime': ct.get('uptime', 0),
                'ip': ip_address,
                'template': ct_config.get('template', 0) == 1
            })
        except Exception as e:
            # If we can't get config, add basic info
            result.append({
                'vmid': ct['vmid'],
                'name': ct.get('name', f"ct-{ct['vmid']}"),
                'node': node,
                'type': 'lxc',
                'status': ct.get('status', 'unknown'),
                'cpu': ct.get('cpus', 0),
                'memory': ct.get('maxmem', 0) // (1024**2),
                'disk': ct.get('maxdisk', 0) // (1024**3),
                'uptime': ct.get('uptime', 0),
                'ip': None,
                'error': str(e)
            })
    
    return result


def find_vm_by_name(name: str, node: Optional[str] = None) -> Optional[Dict]:
    """
    Finds a VM or container by name.
    
    Args:
        name: VM/container name
        node: Specific node (None = search all nodes)
    
    Returns:
        VM/container info or None if not found
    
    Example:
        >>> vm = find_vm_by_name("my-vm")
        >>> if vm:
        >>>     print(f"Found VM {vm['vmid']} on node {vm['node']}")
    """
    all_vms = list_vms(node=node)
    for vm in all_vms:
        if vm['name'] == name:
            return vm
    return None


def find_vm_by_id(vmid: int, node: Optional[str] = None) -> Optional[Dict]:
    """
    Finds a VM or container by VMID.
    
    Args:
        vmid: VM/container ID
        node: Specific node (None = search all nodes)
    
    Returns:
        VM/container info or None if not found
    """
    all_vms = list_vms(node=node)
    for vm in all_vms:
        if vm['vmid'] == vmid:
            return vm
    return None
