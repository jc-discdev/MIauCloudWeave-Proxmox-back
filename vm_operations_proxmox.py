"""
Proxmox VM and LXC Container Operations Module
Handles start, stop, restart, and status operations
"""

from proxmox_client import get_proxmox_client, get_default_node
from list_vms_proxmox import find_vm_by_name, find_vm_by_id
from typing import Optional, Dict
import time


def start_vm(vmid: Optional[int] = None, name: Optional[str] = None, node: Optional[str] = None) -> bool:
    """
    Starts a VM or LXC container.
    
    Args:
        vmid: VM/Container ID
        name: VM/Container name (if vmid not provided)
        node: Node name
    
    Returns:
        True if started successfully
    
    Example:
        >>> start_vm(vmid=100, node="pve")
        >>> start_vm(name="my-vm")
    """
    proxmox = get_proxmox_client()
    vmid, node, vm_type = _resolve_vm(vmid, name, node)
    
    if vm_type == 'qemu':
        proxmox.nodes(node).qemu(vmid).status.start.post()
    elif vm_type == 'lxc':
        proxmox.nodes(node).lxc(vmid).status.start.post()
    
    return True


def stop_vm(vmid: Optional[int] = None, name: Optional[str] = None, node: Optional[str] = None) -> bool:
    """
    Stops a VM or LXC container.
    
    Args:
        vmid: VM/Container ID
        name: VM/Container name (if vmid not provided)
        node: Node name
    
    Returns:
        True if stopped successfully
    """
    proxmox = get_proxmox_client()
    vmid, node, vm_type = _resolve_vm(vmid, name, node)
    
    if vm_type == 'qemu':
        proxmox.nodes(node).qemu(vmid).status.stop.post()
    elif vm_type == 'lxc':
        proxmox.nodes(node).lxc(vmid).status.stop.post()
    
    return True


def restart_vm(vmid: Optional[int] = None, name: Optional[str] = None, node: Optional[str] = None) -> bool:
    """
    Restarts a VM or LXC container.
    
    Args:
        vmid: VM/Container ID
        name: VM/Container name (if vmid not provided)
        node: Node name
    
    Returns:
        True if restarted successfully
    """
    proxmox = get_proxmox_client()
    vmid, node, vm_type = _resolve_vm(vmid, name, node)
    
    if vm_type == 'qemu':
        proxmox.nodes(node).qemu(vmid).status.reboot.post()
    elif vm_type == 'lxc':
        proxmox.nodes(node).lxc(vmid).status.reboot.post()
    
    return True


def shutdown_vm(vmid: Optional[int] = None, name: Optional[str] = None, node: Optional[str] = None, timeout: int = 60) -> bool:
    """
    Gracefully shuts down a VM or LXC container.
    
    Args:
        vmid: VM/Container ID
        name: VM/Container name (if vmid not provided)
        node: Node name
        timeout: Timeout in seconds
    
    Returns:
        True if shutdown successfully
    """
    proxmox = get_proxmox_client()
    vmid, node, vm_type = _resolve_vm(vmid, name, node)
    
    if vm_type == 'qemu':
        proxmox.nodes(node).qemu(vmid).status.shutdown.post(timeout=timeout)
    elif vm_type == 'lxc':
        proxmox.nodes(node).lxc(vmid).status.shutdown.post(timeout=timeout)
    
    return True


def get_vm_status(vmid: Optional[int] = None, name: Optional[str] = None, node: Optional[str] = None) -> Dict:
    """
    Gets the current status of a VM or LXC container.
    
    Args:
        vmid: VM/Container ID
        name: VM/Container name (if vmid not provided)
        node: Node name
    
    Returns:
        Dictionary with status information
    
    Example:
        >>> status = get_vm_status(name="my-vm")
        >>> print(f"Status: {status['status']}, Uptime: {status['uptime']}s")
    """
    proxmox = get_proxmox_client()
    vmid, node, vm_type = _resolve_vm(vmid, name, node)
    
    if vm_type == 'qemu':
        status = proxmox.nodes(node).qemu(vmid).status.current.get()
    elif vm_type == 'lxc':
        status = proxmox.nodes(node).lxc(vmid).status.current.get()
    
    status['vmid'] = vmid
    status['node'] = node
    status['type'] = vm_type
    
    return status


def suspend_vm(vmid: Optional[int] = None, name: Optional[str] = None, node: Optional[str] = None) -> bool:
    """
    Suspends a QEMU VM (not available for LXC).
    
    Args:
        vmid: VM ID
        name: VM name (if vmid not provided)
        node: Node name
    
    Returns:
        True if suspended successfully
    
    Raises:
        ValueError: If trying to suspend an LXC container
    """
    proxmox = get_proxmox_client()
    vmid, node, vm_type = _resolve_vm(vmid, name, node)
    
    if vm_type != 'qemu':
        raise ValueError("Suspend is only available for QEMU VMs, not LXC containers")
    
    proxmox.nodes(node).qemu(vmid).status.suspend.post()
    return True


def resume_vm(vmid: Optional[int] = None, name: Optional[str] = None, node: Optional[str] = None) -> bool:
    """
    Resumes a suspended QEMU VM.
    
    Args:
        vmid: VM ID
        name: VM name (if vmid not provided)
        node: Node name
    
    Returns:
        True if resumed successfully
    """
    proxmox = get_proxmox_client()
    vmid, node, vm_type = _resolve_vm(vmid, name, node)
    
    if vm_type != 'qemu':
        raise ValueError("Resume is only available for QEMU VMs, not LXC containers")
    
    proxmox.nodes(node).qemu(vmid).status.resume.post()
    return True


def reset_vm(vmid: Optional[int] = None, name: Optional[str] = None, node: Optional[str] = None) -> bool:
    """
    Resets a QEMU VM (hard reset, like pressing reset button).
    
    Args:
        vmid: VM ID
        name: VM name (if vmid not provided)
        node: Node name
    
    Returns:
        True if reset successfully
    """
    proxmox = get_proxmox_client()
    vmid, node, vm_type = _resolve_vm(vmid, name, node)
    
    if vm_type != 'qemu':
        raise ValueError("Reset is only available for QEMU VMs, not LXC containers")
    
    proxmox.nodes(node).qemu(vmid).status.reset.post()
    return True


def _resolve_vm(vmid: Optional[int], name: Optional[str], node: Optional[str]) -> tuple:
    """
    Resolves VM/container information from vmid or name.
    
    Returns:
        Tuple of (vmid, node, vm_type)
    
    Raises:
        ValueError: If VM/container not found or invalid parameters
    """
    if vmid is None and name is None:
        raise ValueError("Must provide either vmid or name")
    
    if vmid is None and name:
        vm_info = find_vm_by_name(name, node)
        if not vm_info:
            raise ValueError(f"VM/Container with name '{name}' not found")
        return vm_info['vmid'], vm_info['node'], vm_info['type']
    
    elif vmid and not node:
        vm_info = find_vm_by_id(vmid)
        if not vm_info:
            raise ValueError(f"VM/Container with ID {vmid} not found")
        return vmid, vm_info['node'], vm_info['type']
    
    else:
        # vmid and node provided, need to determine type
        proxmox = get_proxmox_client()
        try:
            proxmox.nodes(node).qemu(vmid).status.current.get()
            return vmid, node, 'qemu'
        except:
            try:
                proxmox.nodes(node).lxc(vmid).status.current.get()
                return vmid, node, 'lxc'
            except:
                raise ValueError(f"VM/Container {vmid} not found on node {node}")
