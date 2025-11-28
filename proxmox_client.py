"""
Proxmox API Client Module
Provides centralized connection management for Proxmox VE API
"""

from proxmoxer import ProxmoxAPI
import os
from typing import Optional


def get_proxmox_client(
    host: Optional[str] = None,
    port: Optional[int] = None,
    user: Optional[str] = None,
    password: Optional[str] = None,
    token_name: Optional[str] = None,
    token_value: Optional[str] = None,
    verify_ssl: Optional[bool] = None
) -> ProxmoxAPI:
    """
    Creates and returns a Proxmox API client.
    
    Priority: function parameters > environment variables
    
    Authentication methods:
    1. API Token (recommended): PROXMOX_TOKEN_NAME + PROXMOX_TOKEN_VALUE
    2. User/Password: PROXMOX_USER + PROXMOX_PASSWORD
    
    Args:
        host: Proxmox host (without https://)
        port: Proxmox port (default: 8006)
        user: Username (e.g., root@pam)
        password: Password
        token_name: API token name
        token_value: API token value
        verify_ssl: Verify SSL certificate
    
    Returns:
        ProxmoxAPI client instance
    
    Raises:
        ValueError: If credentials are not configured
    
    Example:
        >>> proxmox = get_proxmox_client()
        >>> print(proxmox.version.get())
    """
    # Get configuration from parameters or environment
    host = host or os.getenv('PROXMOX_HOST')
    port = port or int(os.getenv('PROXMOX_PORT', '8006'))
    user = user or os.getenv('PROXMOX_USER')
    password = password or os.getenv('PROXMOX_PASSWORD')
    token_name = token_name or os.getenv('PROXMOX_TOKEN_NAME')
    token_value = token_value or os.getenv('PROXMOX_TOKEN_VALUE')
    
    if verify_ssl is None:
        verify_ssl = os.getenv('PROXMOX_VERIFY_SSL', 'false').lower() == 'true'
    
    if not host:
        raise ValueError("PROXMOX_HOST not configured. Please set it in .env file.")
    
    # Authentication by API Token (recommended)
    if token_name and token_value:
        try:
            return ProxmoxAPI(
                host,
                port=port,
                user=user,
                token_name=token_name,
                token_value=token_value,
                verify_ssl=verify_ssl
            )
        except Exception as e:
            raise ValueError(f"Failed to connect to Proxmox with API token: {e}")
    
    # Authentication by username/password
    elif user and password:
        try:
            return ProxmoxAPI(
                host,
                port=port,
                user=user,
                password=password,
                verify_ssl=verify_ssl
            )
        except Exception as e:
            raise ValueError(f"Failed to connect to Proxmox with user/password: {e}")
    
    else:
        raise ValueError(
            "Proxmox credentials not configured. "
            "Please set either (PROXMOX_USER + PROXMOX_PASSWORD) or "
            "(PROXMOX_TOKEN_NAME + PROXMOX_TOKEN_VALUE) in .env file."
        )


def get_default_node() -> str:
    """
    Returns the default Proxmox node from environment.
    
    Returns:
        Node name (e.g., 'pve')
    
    Raises:
        ValueError: If PROXMOX_NODE is not configured
    """
    node = os.getenv('PROXMOX_NODE')
    if not node:
        raise ValueError("PROXMOX_NODE not configured. Please set it in .env file.")
    return node


def get_default_storage() -> str:
    """
    Returns the default storage pool from environment.
    
    Returns:
        Storage name (e.g., 'local-lvm')
    """
    return os.getenv('PROXMOX_STORAGE', 'local-lvm')


def get_default_bridge() -> str:
    """
    Returns the default network bridge from environment.
    
    Returns:
        Bridge name (e.g., 'vmbr0')
    """
    return os.getenv('PROXMOX_BRIDGE', 'vmbr0')


def test_connection() -> dict:
    """
    Tests the connection to Proxmox and returns version info.
    
    Returns:
        Dictionary with Proxmox version information
    
    Example:
        >>> info = test_connection()
        >>> print(f"Connected to Proxmox {info['version']}")
    """
    try:
        proxmox = get_proxmox_client()
        version_info = proxmox.version.get()
        return {
            'success': True,
            'version': version_info.get('version'),
            'release': version_info.get('release'),
            'repoid': version_info.get('repoid')
        }
    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }
