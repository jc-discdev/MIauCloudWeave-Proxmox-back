import argparse
import json
import os
import secrets
import string
from google.cloud import compute_v1
def sanitize_gcp_name(name: str) -> str:
    """Sanitize a name to be a valid GCP instance name."""
    if not name:
        return name
    s = name.lower()
    import re
    s = re.sub(r'[^a-z0-9-]', '-', s)
    s = re.sub(r'-{2,}', '-', s)
    s = s[:63]
    s = s.strip('-')
    if not s:
        s = 'a'
    if not s[0].isalpha():
        s = 'a' + s
        s = s[:63]
    while not s[-1].isalnum():
        s = s[:-1]
        if not s:
            s = 'a'
            break
    return s
def create_instance(project_id, zone, instance_name, machine_type, ssh_key=None, password: str = None, count: int = 1, image_project: str = None, image_family: str = None, image: str = None, startup_script: str = None):
    """Crea una instancia de GCP"""
    print(f"Creando instancia '{instance_name}' en zona: {zone}")
    
    instance_client = compute_v1.InstancesClient()
    safe_name = sanitize_gcp_name(instance_name)
    
    results = []
    if image:
        source_image = image
    elif image_project and image_family:
        source_image = f"projects/{image_project}/global/images/family/{image_family}"
    else:
        source_image = "projects/debian-cloud/global/images/family/debian-11"

    network_interface = compute_v1.NetworkInterface()
    network_interface.name = "global/networks/default"
    access_config = compute_v1.AccessConfig()
    access_config.name = "External NAT"
    access_config.type_ = "ONE_TO_ONE_NAT"
    network_interface.access_configs = [access_config]
    
    metadata = compute_v1.Metadata()
    items = []
    if ssh_key:
        metadata_item = compute_v1.Items()
        metadata_item.key = "ssh-keys"
        metadata_item.value = ssh_key
        items.append(metadata_item)

    try:
        operation_client = compute_v1.ZoneOperationsClient()
        for idx in range(max(1, int(count or 1))):
            this_name = safe_name
            if count and int(count) > 1:
                suffix = f"-{idx+1}"
                trunc = this_name[:(63 - len(suffix))]
                this_name = f"{trunc}{suffix}"

            alphabet = string.ascii_letters + string.digits + "!@#$%&*()-_=+"
            while True:
                pw = ''.join(secrets.choice(alphabet) for _ in range(14))
                if (any(c.islower() for c in pw) and any(c.isupper() for c in pw)
                        and any(c.isdigit() for c in pw) and any(c in "!@#$%&*()-_=+" for c in pw)):
                    instance_password = pw
                    break

            instance = compute_v1.Instance()
            instance.name = this_name
            instance.machine_type = f"zones/{zone}/machineTypes/{machine_type}"

            disk = compute_v1.AttachedDisk()
            disk.boot = True
            disk.auto_delete = True
            disk.initialize_params = compute_v1.AttachedDiskInitializeParams()
            disk.initialize_params.source_image = source_image
            disk.initialize_params.disk_size_gb = 10
            instance.disks = [disk]
            instance.network_interfaces = [network_interface]

            md_items = list(items)
            startup = f"""#!/bin/bash
set -e
if id -u ubuntu >/dev/null 2>&1; then
    echo "ubuntu:{instance_password}" | chpasswd
else
    useradd -m -s /bin/bash ubuntu || true
    echo "ubuntu:{instance_password}" | chpasswd
fi
sed -i 's/^#PasswordAuthentication no/PasswordAuthentication yes/' /etc/ssh/sshd_config || true
sed -i 's/^PasswordAuthentication no/PasswordAuthentication yes/' /etc/ssh/sshd_config || true
systemctl restart sshd || service ssh restart || true
"""
            if startup_script:
                startup += f"\n# --- Cluster Setup ---\n{startup_script}\n"

            md_start = compute_v1.Items()
            md_start.key = "startup-script"
            md_start.value = startup
            md_items.append(md_start)

            if md_items:
                md = compute_v1.Metadata()
                md.items = md_items
                instance.metadata = md

            request = compute_v1.InsertInstanceRequest()
            request.project = project_id
            request.zone = zone
            request.instance_resource = instance
            
            print(f"Enviando solicitud de creación para {this_name}...")
            op = instance_client.insert(request=request)
            
            # Wait for operation to complete
            print(f"Esperando a que termine la operación para {this_name}...")
            op.result() # This blocks until the operation is complete

            instance_info = instance_client.get(project=project_id, zone=zone, instance=this_name)
            public_ip = None
            for iface in instance_info.network_interfaces:
                if iface.access_configs:
                    for ac in iface.access_configs:
                        ip = getattr(ac, 'nat_i_p', None) or getattr(ac, 'nat_ip', None)
                        if ip:
                            public_ip = ip
            
            results.append({"success": True, "name": this_name, "public_ip": public_ip, "password": instance_password, "username": "ubuntu"})

        if len(results) == 1:
            return results[0]
        return {"success": True, "created": results}
    except Exception as e:
        print(f"Error al crear la instancia(s): {e}")
        return {"success": False, "error": str(e)}