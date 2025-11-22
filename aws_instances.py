import os
import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError, NoCredentialsError, EndpointConnectionError
import time
import uuid
from typing import Optional


def _get_ec2_client(region_name=None, aws_access_key=None, aws_secret_key=None, aws_session_token=None):
    # Default region for AWS operations
    if not region_name:
        region_name = 'us-west-2'
    # Use a short timeout and limited retries to avoid long hangs when AWS endpoints
    # are unreachable or metadata service is slow. If explicit keys are not provided
    # disable EC2 metadata lookups to prevent the client from blocking while trying
    # to fetch IAM role credentials from the instance metadata service.
    client_config = Config(connect_timeout=3, read_timeout=5, retries={'max_attempts': 2})

    if not aws_access_key or not aws_secret_key:
        # Prevent botocore from calling the IMDS (instance metadata) which can
        # cause long blocking delays when running outside EC2 without network.
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
    """Lista instancias EC2 en la región indicada (o por defecto).

    Devuelve únicamente instancias cuyo tag `Name` comienza con `t3-`.
    """
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
                # Only include instances whose Name tag starts with the t3- prefix
                if not name_tag or not name_tag.startswith('t3-'):
                    continue
                # If a state filter was provided, check instance state
                inst_state = inst.get('State', {}).get('Name')
                if state and (not inst_state or inst_state.upper() != state.upper()):
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
    except NoCredentialsError:
        raise RuntimeError("No AWS credentials found. Set aws_access_key_id/aws_secret_access_key or configure an IAM role.")
    except EndpointConnectionError as e:
        raise RuntimeError(f"Unable to connect to AWS endpoint: {e}")
    except ClientError as e:
        # Provide the AWS error code/message
        raise RuntimeError(f"AWS ClientError: {e.response.get('Error', {})}")
    except BotoCoreError as e:
        raise RuntimeError(f"BotoCoreError while listing EC2 instances: {e}")


def list_instances_aws_all(region_name=None, aws_access_key=None, aws_secret_key=None, aws_session_token=None):
    """Lista todas las instancias EC2 en la región indicada (sin filtrar por Name tag).

    Esta función es útil para depuración. No debe exponerse en producción sin control.
    """
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
    except NoCredentialsError:
        raise RuntimeError("No AWS credentials found. Set aws_access_key_id/aws_secret_access_key or configure an IAM role.")
    except EndpointConnectionError as e:
        raise RuntimeError(f"Unable to connect to AWS endpoint: {e}")
    except ClientError as e:
        raise RuntimeError(f"AWS ClientError: {e.response.get('Error', {})}")
    except BotoCoreError as e:
        raise RuntimeError(f"BotoCoreError while listing EC2 instances: {e}")


def find_instances_aws(name: Optional[str] = None, region_name=None, aws_access_key=None, aws_secret_key=None, aws_session_token=None):
    """Busca instancias por tag Name (solo devuelve las que empiecen por t3-).

    Si `name` se proporciona, busca instancias cuyo Name empieza con `t3-<name>` o `t3-` si `name` ya incluye el prefijo.
    """
    client = _get_ec2_client(region_name, aws_access_key, aws_secret_key, aws_session_token)
    try:
        if name:
            search_name = name if name.startswith('t3-') else f't3-{name}'
            resp = client.describe_instances(Filters=[{'Name': 'tag:Name', 'Values': [f'{search_name}*']}])
        else:
            # if no name provided, return same as list_instances_aws
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
    except NoCredentialsError:
        raise RuntimeError("No AWS credentials found for find operation.")
    except EndpointConnectionError as e:
        raise RuntimeError(f"Unable to connect to AWS endpoint for find: {e}")
    except ClientError as e:
        raise RuntimeError(f"AWS ClientError (find): {e.response.get('Error', {})}")
    except BotoCoreError as e:
        raise RuntimeError(f"BotoCoreError while finding EC2 instances: {e}")
    except NoCredentialsError:
        raise RuntimeError("No AWS credentials found. Set aws_access_key_id/aws_secret_access_key or configure an IAM role.")
    except EndpointConnectionError as e:
        raise RuntimeError(f"Unable to connect to AWS endpoint: {e}")
    except ClientError as e:
        # Provide the AWS error code/message
        raise RuntimeError(f"AWS ClientError: {e.response.get('Error', {})}")
    except BotoCoreError as e:
        raise RuntimeError(f"BotoCoreError while listing EC2 instances: {e}")


def find_instance_types_aws(region_name=None, min_vcpus=1, min_memory_gb=1, aws_access_key=None, aws_secret_key=None, aws_session_token=None, max_results=500):
    """Busca tipos de instancia EC2 que cumplan mínimos de vCPU y memoria (GB).

    Nota: DescribeInstanceTypes puede devolver muchos tipos; limitamos por `max_results`.
    """
    client = _get_ec2_client(region_name, aws_access_key, aws_secret_key, aws_session_token)
    try:
        paginator = client.get_paginator('describe_instance_types')
        matches = []
        fetched = 0
        for page in paginator.paginate():
            for it in page.get('InstanceTypes', []):
                # vCPU
                vcpus = None
                mem_gb = None
                vcpu_info = it.get('VCpuInfo')
                mem_info = it.get('MemoryInfo')
                if vcpu_info:
                    vcpus = vcpu_info.get('DefaultVCpus')
                if mem_info:
                    # MemoryInfo returns MiB
                    mem_mib = mem_info.get('SizeInMiB')
                    if mem_mib is not None:
                        mem_gb = round(mem_mib / 1024, 2)

                if vcpus is None or mem_gb is None:
                    continue

                if vcpus >= min_vcpus and mem_gb >= min_memory_gb:
                    matches.append({
                        'instance_type': it.get('InstanceType'),
                        'vcpus': vcpus,
                        'memory_gb': mem_gb,
                        'supported_virtuallization_types': it.get('SupportedVirtualizationTypes')
                    })
                    fetched += 1
                    if fetched >= max_results:
                        return matches

        return matches
    except NoCredentialsError:
        raise RuntimeError("No AWS credentials found for instance-type lookup.")
    except EndpointConnectionError as e:
        raise RuntimeError(f"Unable to connect to AWS endpoint for instance types: {e}")
    except ClientError as e:
        raise RuntimeError(f"AWS ClientError (instance types): {e.response.get('Error', {})}")
    except BotoCoreError as e:
        raise RuntimeError(f"BotoCoreError while finding instance types: {e}")


def create_instance_aws(region_name, image_id='ami-03c1f788292172a4e', instance_type='t3.micro', name=None, password: Optional[str]=None, key_name=None, security_group_ids=None, subnet_id=None, min_count=1, max_count=1, aws_access_key=None, aws_secret_key=None, aws_session_token=None):
    """Crea una instancia EC2 simple y devuelve la lista de InstanceIds creadas.

    Si `name` se proporciona, añade tag `Name` con prefijo `t3-`.
    """
    client = _get_ec2_client(region_name, aws_access_key, aws_secret_key, aws_session_token)
    params = {
        'ImageId': image_id,
        'InstanceType': instance_type,
        'MinCount': min_count,
        'MaxCount': max_count,
    }
    if key_name:
        params['KeyName'] = key_name
    if security_group_ids:
        params['SecurityGroupIds'] = security_group_ids
    if subnet_id:
        params['SubnetId'] = subnet_id
    # Ensure Name tag with t3- prefix. If no name passed, generate one.
    if not name:
        # deterministic-ish name: t3-<uuid4 short>
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
    # If a password is provided, build a cloud-init / userdata script to set it
        if password:
                # Use cloud-init (YAML) user-data to set passwords and enable SSH password authentication.
                # This is more portable across AMIs that support cloud-init.
                # The chpasswd block sets passwords for common users; expire: False avoids forcing password change.
                user_data = f"""#cloud-config
chpasswd:
    list: |
        ec2-user:{password}
        ubuntu:{password}
        debian:{password}
    expire: False
ssh_pwauth: True
"""
                params['UserData'] = user_data

    try:
        resp = client.run_instances(**params)
        ids = [i.get('InstanceId') for i in resp.get('Instances', [])]

        # Wait for instances to reach 'running' state and collect their public IPs
        created = []
        if ids:
            waiter = client.get_waiter('instance_running')
            try:
                waiter.wait(InstanceIds=ids, WaiterConfig={'Delay': 3, 'MaxAttempts': 20})
            except Exception:
                # If waiter fails or times out, proceed to describe instances anyway
                pass

            desc = client.describe_instances(InstanceIds=ids)
            for reservation in desc.get('Reservations', []):
                for inst in reservation.get('Instances', []):
                    inst_id = inst.get('InstanceId')
                    public_ip = inst.get('PublicIpAddress')
                    # Name tag
                    name_tag = None
                    for t in inst.get('Tags', []) or []:
                        if t.get('Key') == 'Name':
                            name_tag = t.get('Value')
                            break
                    # Determine recommended username based on common AMI types
                    primary_username = 'ec2-user'
                    alt_usernames = ['ubuntu', 'debian', 'admin']
                    created.append({
                        'InstanceId': inst_id,
                        'Name': name_tag,
                        'PublicIpAddress': public_ip,
                        'Password': password,
                        'username': primary_username,
                        'alt_usernames': alt_usernames
                    })

        return created
    except NoCredentialsError:
        raise RuntimeError("No AWS credentials found. Cannot create instance.")
    except EndpointConnectionError as e:
        raise RuntimeError(f"Unable to connect to AWS endpoint to create instance: {e}")
    except ClientError as e:
        raise RuntimeError(f"AWS ClientError creating instance: {e.response.get('Error', {})}")
    except BotoCoreError as e:
        raise RuntimeError(f"BotoCoreError while creating EC2 instance: {e}")


def delete_instance_aws(instance_id=None, name=None, region_name=None, aws_access_key=None, aws_secret_key=None, aws_session_token=None):
    """Termina una instancia EC2 por `instance_id` o por tag Name si se pasa `name`."""
    client = _get_ec2_client(region_name, aws_access_key, aws_secret_key, aws_session_token)
    try:
        if not instance_id and name:
            # Ensure we only search for t3- prefixed names
            search_name = name if name.startswith('t3-') else f't3-{name}'
            # Buscar por tag Name
            resp = client.describe_instances(Filters=[{'Name': 'tag:Name', 'Values': [search_name]}])
            instances = []
            for r in resp.get('Reservations', []):
                for inst in r.get('Instances', []):
                    instances.append(inst.get('InstanceId'))
            if not instances:
                return {'terminated': [], 'message': f'No instance with Name={search_name} found'}
            instance_id = instances[0]

        if not instance_id:
            raise ValueError('instance_id or name must be provided')

        # If instance_id provided directly, ensure it has Name tag starting with t3-
        if instance_id and not name:
            try:
                check = client.describe_instances(InstanceIds=[instance_id])
                found_name = None
                for r in check.get('Reservations', []):
                    for inst in r.get('Instances', []):
                        for t in inst.get('Tags', []) or []:
                            if t.get('Key') == 'Name':
                                found_name = t.get('Value')
                                break
                if not found_name or not found_name.startswith('t3-'):
                    return {'terminated': [], 'message': 'Refusing to delete instance without t3- prefix in Name tag'}
            except ClientError:
                # proceed to attempt termination (error will be handled below)
                pass

        resp = client.terminate_instances(InstanceIds=[instance_id])
        terminated = [t.get('InstanceId') for t in resp.get('TerminatingInstances', [])]
        return {'terminated': terminated}
    except NoCredentialsError:
        raise RuntimeError("No AWS credentials found. Cannot delete instance.")
    except EndpointConnectionError as e:
        raise RuntimeError(f"Unable to connect to AWS endpoint to delete instance: {e}")
    except ClientError as e:
        raise RuntimeError(f"AWS ClientError deleting instance: {e.response.get('Error', {})}")
    except BotoCoreError as e:
        raise RuntimeError(f"BotoCoreError while deleting EC2 instance: {e}")
