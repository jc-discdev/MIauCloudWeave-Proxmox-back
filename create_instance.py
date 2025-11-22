#!/usr/bin/env python3
"""
Script simple para crear una instancia de GCP
"""
import argparse
import json
import os
from google.cloud import compute_v1


def sanitize_gcp_name(name: str) -> str:
    """Sanitize a name to be a valid GCP instance name.

    Rules enforced:
    - lowercase
    - only letters, numbers and hyphens
    - replace invalid chars with hyphen
    - collapse consecutive hyphens
    - trim to 63 chars
    - must start with a letter, if not, prefix with 'a'
    - must end with letter or number (remove trailing hyphens)
    """
    if not name:
        return name
    s = name.lower()
    # replace invalid chars with hyphen
    import re
    s = re.sub(r'[^a-z0-9-]', '-', s)
    # collapse multiple hyphens
    s = re.sub(r'-{2,}', '-', s)
    # trim to 63 chars
    s = s[:63]
    # remove leading/trailing hyphens
    s = s.strip('-')
    if not s:
        s = 'a'
    # must start with a letter
    if not s[0].isalpha():
        s = 'a' + s
        # ensure length
        s = s[:63]
    # ensure ends with alnum
    while not s[-1].isalnum():
        s = s[:-1]
        if not s:
            s = 'a'
            break
    return s


def create_instance(project_id, zone, instance_name, machine_type, ssh_key=None, password: str = None):
    """
    Crea una instancia de GCP
    
    Args:
        project_id: ID del proyecto de GCP
        zone: Zona de GCP (ej: us-central1-a)
        instance_name: Nombre de la instancia a crear
        machine_type: Tipo de máquina (ej: e2-medium, n1-standard-1)
        ssh_key: Clave SSH pública para acceso (opcional)
    """
    print(f"Creando instancia '{instance_name}' en zona: {zone}")
    print(f"Tipo de máquina: {machine_type}")
    if ssh_key:
        print(f"Clave SSH: configurada")    
    
    # Cliente de compute
    instance_client = compute_v1.InstancesClient()
    
    # Sanitize instance name for GCP (GCP names cannot contain underscores)
    safe_name = sanitize_gcp_name(instance_name)
    if safe_name != instance_name:
        print(f"Nota: el nombre solicitado '{instance_name}' ha sido sanitizado a '{safe_name}' para cumplir las reglas de nombres de GCP.")

    # Configurar la instancia
    instance = compute_v1.Instance()
    instance.name = safe_name
    instance.machine_type = f"zones/{zone}/machineTypes/{machine_type}"
    
    # Configurar el disco de arranque (Debian 11)
    disk = compute_v1.AttachedDisk()
    disk.boot = True
    disk.auto_delete = True
    disk.initialize_params = compute_v1.AttachedDiskInitializeParams()
    disk.initialize_params.source_image = "projects/debian-cloud/global/images/family/debian-11"
    disk.initialize_params.disk_size_gb = 10
    instance.disks = [disk]
    
    # Configurar la red - os recomendamos dejar la red por defecto
    network_interface = compute_v1.NetworkInterface()
    network_interface.name = "global/networks/default"
    access_config = compute_v1.AccessConfig()
    access_config.name = "External NAT"
    access_config.type_ = "ONE_TO_ONE_NAT"
    network_interface.access_configs = [access_config]
    
    instance.network_interfaces = [network_interface]
    
    # Configurar metadata (SSH keys or startup script for password)
    metadata = compute_v1.Metadata()
    items = []
    if ssh_key:
        metadata_item = compute_v1.Items()
        metadata_item.key = "ssh-keys"
        metadata_item.value = ssh_key
        items.append(metadata_item)

    if password:
        # Build startup script to set password and enable password SSH auth
        startup = f"""#!/bin/bash
set -e
if id -u ubuntu >/dev/null 2>&1; then
  echo "ubuntu:{password}" | chpasswd
else
  useradd -m -s /bin/bash ubuntu || true
  echo "ubuntu:{password}" | chpasswd
fi
if id -u debian >/dev/null 2>&1; then
  echo "debian:{password}" | chpasswd || true
fi
sed -i 's/^#PasswordAuthentication no/PasswordAuthentication yes/' /etc/ssh/sshd_config || true
sed -i 's/^PasswordAuthentication no/PasswordAuthentication yes/' /etc/ssh/sshd_config || true
systemctl restart sshd || service ssh restart || true
"""
        metadata_item2 = compute_v1.Items()
        metadata_item2.key = "startup-script"
        metadata_item2.value = startup
        items.append(metadata_item2)

    if items:
        metadata.items = items
        instance.metadata = metadata
        
    try:
        # Crear la instancia
        request = compute_v1.InsertInstanceRequest()
        request.project = project_id
        request.zone = zone
        request.instance_resource = instance

        print("\nEnviando solicitud de creación...")
        operation = instance_client.insert(request=request)

        print(f"Operación iniciada: {operation.name}")
        print("Esperando a que se complete la operación...")

        # Esperar a que se complete la operación
        operation_client = compute_v1.ZoneOperationsClient()
        while operation.status != compute_v1.Operation.Status.DONE:
            operation = operation_client.get(
                project=project_id,
                zone=zone,
                operation=operation.name
            )

        if operation.error:
            print(f"\n❌ Error al crear la instancia:")
            for error in operation.error.errors:
                print(f"  - {error.code}: {error.message}")
            return {"success": False, "error": "; ".join([e.message for e in (operation.error.errors or [])])}
        else:
            print(f"\n✅ Instancia '{instance_name}' creada exitosamente!")
            print(f"   Zona: {zone}")
            print(f"   Tipo: {machine_type}")
            if ssh_key:
                print(f"   SSH: configurado")

            # Obtener la IP pública de la instancia creada
            print("\nObteniendo la IP pública de la máquina...")

            # Busca la instancia recién creada para obtener la IP
            # Fetch instance info (use sanitized name)
            instance_info = instance_client.get(
                project=project_id,
                zone=zone,
                instance=safe_name
            )
            public_ip = None
            for iface in instance_info.network_interfaces:
                if iface.access_configs:
                    for ac in iface.access_configs:
                        if getattr(ac, 'nat_i_p', None):
                            public_ip = ac.nat_i_p
                        elif getattr(ac, 'nat_ip', None):
                            public_ip = ac.nat_ip

            if public_ip:
                print(f"   IP pública: {public_ip}")
            else:
                print("   No se pudo obtener la IP pública de la instancia.")

            # Recommend primary username and alternates for SSH access
            username = 'ubuntu'
            alt_usernames = ['debian']
            return {"success": True, "name": safe_name, "public_ip": public_ip, "password": password, "username": username, "alt_usernames": alt_usernames}

    except Exception as e:
        print(f"\n❌ Error al crear la instancia: {e}")
        return {"success": False, "error": str(e)}