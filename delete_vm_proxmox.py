"""
Proxmox VM and LXC Container Deletion Module
"""

from proxmox_client import get_proxmox_client, get_default_node
from list_vms_proxmox import find_vm_by_name, find_vm_by_id
from typing import Optional
import time


def delete_vm(
    vmid: Optional[int] = None,
    name: Optional[str] = None,
    node: Optional[str] = None,
    force: bool = True,
    purge: bool = True
) -> bool:
    """
    Deletes a VM or LXC container from Proxmox.
    
    Args:
        vmid: VM/Container ID
        name: VM/Container name (if vmid not provided)
        node: Node where the VM/container is located
        force: Force stop if running
        purge: Remove from all backups and snapshots
    
    Returns:
        True if deleted successfully
    
    Raises:
        ValueError: If VM/container not found or invalid parameters
    
    Example:
        >>> # Delete by VMID
        >>> delete_vm(vmid=100, node="pve")
        >>> # Delete by name
        >>> delete_vm(name="my-vm")
    """
    proxmox = get_proxmox_client()
    
    # If vmid not provided, search by name
    if vmid is None and name:
        vm_info = find_vm_by_name(name, node)
        if not vm_info:
            raise ValueError(f"VM/Container with name '{name}' not found")
        vmid = vm_info['vmid']
        node = vm_info['node']
        vm_type = vm_info['type']
    elif vmid and not node:
        # Search for VM by ID across all nodes
        vm_info = find_vm_by_id(vmid)
        if not vm_info:
            raise ValueError(f"VM/Container with ID {vmid} not found")
        node = vm_info['node']
        vm_type = vm_info['type']
    elif vmid and node:
        # Check if it's QEMU or LXC
        try:
            proxmox.nodes(node).qemu(vmid).status.current.get()
            vm_type = 'qemu'
        except:
            try:
                proxmox.nodes(node).lxc(vmid).status.current.get()
                vm_type = 'lxc'
            except:
                raise ValueError(f"VM/Container {vmid} not found on node {node}")
    else:
        raise ValueError("Must provide either vmid or name")
    
    node = node or get_default_node()
    
    # Delete based on type
    if vm_type == 'qemu':
        return _delete_qemu_vm(proxmox, node, vmid, force, purge)
    elif vm_type == 'lxc':
        return _delete_lxc_container(proxmox, node, vmid, force, purge)
    else:
        raise ValueError(f"Unknown VM type: {vm_type}")


def _delete_qemu_vm(proxmox, node: str, vmid: int, force: bool, purge: bool) -> bool:
    """Deletes a QEMU VM"""
    try:
        # Check current status
        vm_status = proxmox.nodes(node).qemu(vmid).status.current.get()
        
        # Stop VM if running
        if vm_status['status'] == 'running':
            if force:
                print(f"Stopping VM {vmid}...")
                proxmox.nodes(node).qemu(vmid).status.stop.post()
                # Wait for VM to stop
                for _ in range(30):
                    time.sleep(2)
                    status = proxmox.nodes(node).qemu(vmid).status.current.get()
                    if status['status'] == 'stopped':
                        break
            else:
                raise ValueError(f"VM {vmid} is running. Use force=True to stop it before deletion.")
        
        # Delete the VM
        print(f"Deleting QEMU VM {vmid}...")
        delete_params = {}
        if purge:
            delete_params['purge'] = 1
        
        proxmox.nodes(node).qemu(vmid).delete(**delete_params)
        return True
        
    except Exception as e:
        print(f"Error deleting QEMU VM {vmid}: {e}")
        raise


def _delete_lxc_container(proxmox, node: str, vmid: int, force: bool, purge: bool) -> bool:
    """Deletes an LXC container"""
    try:
        # Check current status
        ct_status = proxmox.nodes(node).lxc(vmid).status.current.get()
        
        # Stop container if running
        if ct_status['status'] == 'running':
            if force:
                print(f"Stopping container {vmid}...")
                proxmox.nodes(node).lxc(vmid).status.stop.post()
                # Wait for container to stop
                for _ in range(30):
                    time.sleep(2)
                    status = proxmox.nodes(node).lxc(vmid).status.current.get()
                    if status['status'] == 'stopped':
                        break
            else:
                raise ValueError(f"Container {vmid} is running. Use force=True to stop it before deletion.")
        
        # Delete the container
        print(f"Deleting LXC container {vmid}...")
        delete_params = {}
        if purge:
            delete_params['purge'] = 1
        
        proxmox.nodes(node).lxc(vmid).delete(**delete_params)
        return True
        
    except Exception as e:
        print(f"Error deleting LXC container {vmid}: {e}")
        raise


def delete_multiple_vms(
    vmids: Optional[list] = None,
    names: Optional[list] = None,
    node: Optional[str] = None,
    force: bool = True
) -> dict:
    """
    Deletes multiple VMs/containers.
    
    Args:
        vmids: List of VM/container IDs
        names: List of VM/container names
        node: Node name
        force: Force stop if running
    
    Returns:
        Dictionary with results for each VM/container
    
    Example:
        >>> results = delete_multiple_vms(names=["vm1", "vm2", "vm3"])
        >>> for name, success in results.items():
        >>>     print(f"{name}: {'deleted' if success else 'failed'}")
    """
    results = {}
    
    if vmids:
        for vmid in vmids:
            try:
                delete_vm(vmid=vmid, node=node, force=force)
                results[f"vmid-{vmid}"] = True
            except Exception as e:
                results[f"vmid-{vmid}"] = False
                print(f"Failed to delete VM {vmid}: {e}")
    
    if names:
        for name in names:
            try:
                delete_vm(name=name, node=node, force=force)
                results[name] = True
            except Exception as e:
                results[name] = False
                print(f"Failed to delete VM {name}: {e}")
    
    return results
