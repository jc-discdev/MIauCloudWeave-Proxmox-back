import os
import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError, NoCredentialsError, EndpointConnectionError
import time
import uuid
import secrets
import string
from typing import Optional
def _get_ec2_client(region_name=None, aws_access_key=None, aws_secret_key=None, aws_session_token=None):
    if not region_name:
        region_name = 'us-west-2'
    client_config = Config(connect_timeout=3, read_timeout=5, retries={'max_attempts': 2})
    if not aws_access_key or not aws_secret_key:
        os.environ.setdefault('AWS_EC2_METADATA_DISABLED', 'true')
    if aws_access_key and aws_secret_key:
        return boto3.client(
            'ec2',
            region_name=region_name,
            aws_access_key_id=aws_access_key,
            aws_secret_access_key=aws_secret_key,
            aws_session_token=aws_session_token,
            config=client_config
        )
    else:
        return boto3.client('ec2', region_name=region_name, config=client_config)
def list_instances_aws(region_name=None, aws_access_key=None, aws_secret_key=None, aws_session_token=None, state: str | None = None):
    client = _get_ec2_client(region_name, aws_access_key, aws_secret_key, aws_session_token)
    try:
        resp = client.describe_instances()
        instances = []
        for reservation in resp.get('Reservations', []):
            for inst in reservation.get('Instances', []):
                tags = inst.get('Tags', []) or []
                name_tag = None
                for t in tags:
                    if t.get('Key') == 'Name':
                        name_tag = t.get('Value')
                        break
                if not name_tag or not name_tag.startswith('t3-'):
                    continue
                inst_state = inst.get('State', {}).get('Name')
                if state:
                    if not inst_state or inst_state.upper() != state.upper():
                        continue
                else:
                    if inst_state in ['terminated', 'shutting-down']:
                        continue
                instances.append({
                    'InstanceId': inst.get('InstanceId'),
                    'Name': name_tag,
                    'State': inst.get('State', {}).get('Name'),
                    'InstanceType': inst.get('InstanceType'),
                    'PublicIpAddress': inst.get('PublicIpAddress'),
                    'PrivateIpAddress': inst.get('PrivateIpAddress'),
                    'LaunchTime': inst.get('LaunchTime').isoformat() if inst.get('LaunchTime') else None,
                    'Tags': tags
                })
        return instances
    except Exception as e:
        raise RuntimeError(f"Error listing AWS instances: {e}")
def list_instances_aws_all(region_name=None, aws_access_key=None, aws_secret_key=None, aws_session_token=None):
    client = _get_ec2_client(region_name, aws_access_key, aws_secret_key, aws_session_token)
    try:
        resp = client.describe_instances()
        instances = []
        for reservation in resp.get('Reservations', []):
            for inst in reservation.get('Instances', []):
                instances.append({
                    'InstanceId': inst.get('InstanceId'),
                    'State': inst.get('State', {}).get('Name'),
                    'InstanceType': inst.get('InstanceType'),
                    'PublicIpAddress': inst.get('PublicIpAddress'),
                    'PrivateIpAddress': inst.get('PrivateIpAddress'),
                    'LaunchTime': inst.get('LaunchTime').isoformat() if inst.get('LaunchTime') else None,
                    'Tags': inst.get('Tags', [])
                })
        return instances
    except Exception as e:
        raise RuntimeError(f"Error listing all AWS instances: {e}")
def find_instances_aws(name: Optional[str] = None, region_name=None, aws_access_key=None, aws_secret_key=None, aws_session_token=None):
    client = _get_ec2_client(region_name, aws_access_key, aws_secret_key, aws_session_token)
    try:
        if name:
            search_name = name if name.startswith('t3-') else f't3-{name}'
            resp = client.describe_instances(Filters=[{'Name': 'tag:Name', 'Values': [f'{search_name}*']}])
        else:
            return list_instances_aws(region_name=region_name, aws_access_key=aws_access_key, aws_secret_key=aws_secret_key, aws_session_token=aws_session_token)
        instances = []
        for reservation in resp.get('Reservations', []):
            for inst in reservation.get('Instances', []):
                tags = inst.get('Tags', []) or []
                name_tag = None
                for t in tags:
                    if t.get('Key') == 'Name':
                        name_tag = t.get('Value')
                        break
                if not name_tag or not name_tag.startswith('t3-'):
                    continue
                instances.append({
                    'InstanceId': inst.get('InstanceId'),
                    'Name': name_tag,
                    'State': inst.get('State', {}).get('Name'),
                    'InstanceType': inst.get('InstanceType'),
                    'PublicIpAddress': inst.get('PublicIpAddress'),
                    'PrivateIpAddress': inst.get('PrivateIpAddress'),
                    'LaunchTime': inst.get('LaunchTime').isoformat() if inst.get('LaunchTime') else None,
                    'Tags': tags
                })
        return instances
    except Exception as e:
        raise RuntimeError(f"Error finding AWS instances: {e}")
def find_instance_types_aws(region_name=None, min_vcpus=1, min_memory_gb=1, aws_access_key=None, aws_secret_key=None, aws_session_token=None, max_results=500):
    client = _get_ec2_client(region_name, aws_access_key, aws_secret_key, aws_session_token)
    try:
        paginator = client.get_paginator('describe_instance_types')
        matches = []
        fetched = 0
        tolerance = 0.5
        target_vcpus = min_vcpus
        target_memory_gb = min_memory_gb
        
        for page in paginator.paginate():
            for it in page.get('InstanceTypes', []):
                vcpus = None
                mem_gb = None
                vcpu_info = it.get('VCpuInfo')
                mem_info = it.get('MemoryInfo')
                if vcpu_info:
                    vcpus = vcpu_info.get('DefaultVCpus')
                if mem_info:
                    mem_mib = mem_info.get('SizeInMiB')
                    if mem_mib is not None:
                        mem_gb = round(mem_mib / 1024, 2)
                if vcpus is None or mem_gb is None:
                    continue
                if not (target_vcpus - tolerance <= vcpus <= target_vcpus + tolerance):
                    continue
                if not (target_memory_gb - tolerance <= mem_gb <= target_memory_gb + tolerance):
                    continue
                matches.append({
                    'instance_type': it.get('InstanceType'),
                    'vcpus': vcpus,
                    'memory_gb': mem_gb,
                    'supported_virtuallization_types': it.get('SupportedVirtualizationTypes')
                })
                fetched += 1
                if fetched >= max_results:
                    matches.sort(key=lambda x: (x['vcpus'], x['memory_gb']))
                    return matches
        matches.sort(key=lambda x: (x['vcpus'], x['memory_gb']))
        return matches
    except Exception as e:
        raise RuntimeError(f"Error finding AWS instance types: {e}")
def create_instance_aws(region_name, image_id='ami-03c1f788292172a4e', instance_type='t3.micro', name=None, password: Optional[str]=None, key_name=None, security_group_ids=None, subnet_id=None, min_count=1, max_count=1, aws_access_key=None, aws_secret_key=None, aws_session_token=None, user_data_script: Optional[str] = None):
    client = _get_ec2_client(region_name, aws_access_key, aws_secret_key, aws_session_token)
    params = {
        'ImageId': image_id,
        'InstanceType': instance_type,
    }
    if key_name:
        params['KeyName'] = key_name
    if security_group_ids:
        params['SecurityGroupIds'] = security_group_ids
    if subnet_id:
        params['SubnetId'] = subnet_id
    if not name:
        name = f"t3-{uuid.uuid4().hex[:8]}"
    else:
        if not name.startswith('t3-'):
            name = f't3-{name}'
    params['TagSpecifications'] = [
        {
            'ResourceType': 'instance',
            'Tags': [
                {'Key': 'Name', 'Value': name}
            ]
        }
    ]
    def _gen_password(length: int = 14) -> str:
        alphabet = string.ascii_letters + string.digits + "!@#$%&*()-_=+"
        while True:
            pw = ''.join(secrets.choice(alphabet) for _ in range(length))
            if (any(c.islower() for c in pw) and any(c.isupper() for c in pw)
                    and any(c.isdigit() for c in pw) and any(c in "!@#$%&*()-_=+" for c in pw)):
                return pw
    try:
        count = max_count if (max_count and max_count > 1) else (min_count or 1)
        created = []
        for i in range(count):
            instance_pw = _gen_password()
            safe_pw = instance_pw.replace('"', '\\"')
            
            base_user_data = f"""#cloud-config
chpasswd:
  list: |
    ubuntu:{safe_pw}
  expire: False
ssh_pwauth: True
runcmd:
  - [ bash, -lc, "id -u ubuntu >/dev/null 2>&1 || useradd -m -s /bin/bash ubuntu" ]
  - [ bash, -lc, "echo 'ubuntu:{safe_pw}' | chpasswd" ]
"""
            full_user_data = base_user_data
            if user_data_script:
                script_lines = user_data_script.replace('"', '\\"').split('\n')
                for line in script_lines:
                    if line.strip():
                         full_user_data += f"  - [ bash, -c, \"{line}\" ]\n"
            params_iter = params.copy()
            params_iter['UserData'] = full_user_data
            resp = client.run_instances(**params_iter, MinCount=1, MaxCount=1)
            ids = [i.get('InstanceId') for i in resp.get('Instances', [])]
            if not ids:
                continue
            inst_id = ids[0]
            waiter = client.get_waiter('instance_running')
            try:
                waiter.wait(InstanceIds=[inst_id], WaiterConfig={'Delay': 3, 'MaxAttempts': 20})
            except Exception:
                pass
            desc = client.describe_instances(InstanceIds=[inst_id])
            for reservation in desc.get('Reservations', []):
                for inst in reservation.get('Instances', []):
                    inst_id = inst.get('InstanceId')
                    public_ip = inst.get('PublicIpAddress')
                    name_tag = None
                    for t in inst.get('Tags', []) or []:
                        if t.get('Key') == 'Name':
                            name_tag = t.get('Value')
                            break
                    created.append({
                        'InstanceId': inst_id,
                        'Name': name_tag,
                        'PublicIpAddress': public_ip,
                        'Password': instance_pw,
                        'username': 'ubuntu'
                    })
        return created
    except Exception as e:
        raise RuntimeError(f"Error creating AWS instance: {e}")
def delete_instance_aws(instance_id=None, name=None, region_name=None, aws_access_key=None, aws_secret_key=None, aws_session_token=None):
    client = _get_ec2_client(region_name, aws_access_key, aws_secret_key, aws_session_token)
    warning_msg = None
    try:
        target_ids = None
        if not instance_id and name:
            search_name = name if name.startswith('t3-') else f't3-{name}'
            resp = client.describe_instances(Filters=[{'Name': 'tag:Name', 'Values': [search_name]}])
            instances = []
            for r in resp.get('Reservations', []):
                for inst in r.get('Instances', []):
                    instances.append(inst.get('InstanceId'))
            if not instances:
                return {'terminated': [], 'message': f'No instance with Name={search_name} found'}
            target_ids = instances
        elif instance_id:
            target_ids = [instance_id]
            try:
                check = client.describe_instances(InstanceIds=[instance_id])
                found_name = None
                for r in check.get('Reservations', []):
                    for inst in r.get('Instances', []):
                        for t in inst.get('Tags', []) or []:
                            if t.get('Key') == 'Name':
                                found_name = t.get('Value')
                                break
                if found_name and not found_name.startswith('t3-'):
                    warning_msg = f"Warning: instance {instance_id} has Name='{found_name}' which does not start with 't3-'. Proceeding with termination as requested."
            except ClientError:
                pass
        if not target_ids:
            raise ValueError('instance_id or name must be provided')
        resp = client.terminate_instances(InstanceIds=target_ids)
        terminated = [t.get('InstanceId') for t in resp.get('TerminatingInstances', [])]
        result = {'terminated': terminated}
        if warning_msg:
            result['warning'] = warning_msg
        return result
    except Exception as e:
        raise RuntimeError(f"Error deleting AWS instance: {e}")
def start_instance_aws(instance_id, region_name=None, aws_access_key=None, aws_secret_key=None, aws_session_token=None):
    client = _get_ec2_client(region_name, aws_access_key, aws_secret_key, aws_session_token)
    try:
        client.start_instances(InstanceIds=[instance_id])
        return True
    except Exception as e:
        raise RuntimeError(f"Error starting AWS instance: {e}")
def stop_instance_aws(instance_id, region_name=None, aws_access_key=None, aws_secret_key=None, aws_session_token=None):
    client = _get_ec2_client(region_name, aws_access_key, aws_secret_key, aws_session_token)
    try:
        client.stop_instances(InstanceIds=[instance_id])
        return True
    except Exception as e:
        raise RuntimeError(f"Error stopping AWS instance: {e}")
