import argparse
import json
import os
from find_instance import find_instances
from create_instance import create_instance
from list_instances import list_instances
from delete_instance import delete_instance, find_and_delete_instance
from aws_instances import list_instances_aws, create_instance_aws, delete_instance_aws
from aws_instances import find_instance_types_aws
from aws_instances import find_instances_aws
from fastapi import FastAPI
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List

app = FastAPI()

# Default AWS region used when none provided
DEFAULT_REGION = 'us-west-2'

# Permitir CORS para llamadas desde Astro (ajusta orígenes según tu entorno)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)


def load_credentials(credentials_file):
    """Carga las credenciales desde un archivo JSON"""
    with open(credentials_file, 'r') as f:
        return json.load(f)


def _set_credentials_and_load(credentials_path: str):
    """Setea la variable de entorno y devuelve el JSON de credenciales."""
    import os
    import json
    if not credentials_path:
        raise ValueError("credentials path is required")
    os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = credentials_path
    with open(credentials_path, 'r') as f:
        return json.load(f)


def _load_aws_credentials_file(path: Optional[str] = None):
    """Carga credenciales AWS desde un JSON local si existe.

    El archivo esperado contiene claves como:
    {
      "aws_access_key_id": "...",
      "aws_secret_access_key": "...",
      "aws_session_token": "...",
      "region": "us-east-1"
    }
    """
    if path is None:
        path = os.path.join(os.path.dirname(__file__), 'credentials_aws.json')
    if not os.path.exists(path):
        return {}
    try:
        with open(path, 'r') as f:
            data = json.load(f)
            return data or {}
    except Exception:
        return {}

# Note: `aws_session_token` is optional. For permanent IAM user keys you only need
# `aws_access_key_id` and `aws_secret_access_key`. `aws_session_token` is required
# only when using temporary credentials obtained via STS (GetSessionToken / AssumeRole).


class FindRequest(BaseModel):
    credentials: str
    zone: str
    region: str
    cpus: int
    ram: int


class CreateRequest(BaseModel):
    credentials: str
    zone: str
    name: str
    machine_type: str
    ssh_key: Optional[str] = None
    password: Optional[str] = None


class ListRequest(BaseModel):
    credentials: Optional[str] = None
    zone: Optional[str] = None
    state: Optional[str] = None


class DeleteRequest(BaseModel):
    credentials: str
    name: str
    zone: Optional[str] = None


def _serialize_instances(instances, zone=None):
    out = []
    for inst in instances:
        item = {
            'name': getattr(inst, 'name', None),
            'status': getattr(inst, 'status', None),
            'machine_type': getattr(inst, 'machine_type', None).split('/')[-1] if getattr(inst, 'machine_type', None) else None,
            'creation_timestamp': getattr(inst, 'creation_timestamp', None),
            'zone': zone,
            'internal_ips': [],
            'external_ips': []
        }
        if getattr(inst, 'network_interfaces', None):
            for iface in inst.network_interfaces:
                if getattr(iface, 'network_i_p', None):
                    item['internal_ips'].append(iface.network_i_p)
                if getattr(iface, 'access_configs', None):
                    for ac in iface.access_configs:
                        ip = getattr(ac, 'nat_i_p', None) or getattr(ac, 'nat_ip', None)
                        if ip:
                            item['external_ips'].append(ip)
        out.append(item)
    return out


@app.post('/find')
def api_find(req: FindRequest):
    creds = _set_credentials_and_load(req.credentials)
    try:
        results = find_instances(
            project_id=creds['project_id'],
            zone=req.zone,
            region=req.region,
            num_cpus=req.cpus,
            num_ram_gb=req.ram
        )
        return {"success": True, "results": results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post('/create')
def api_create(req: CreateRequest):
    creds = _set_credentials_and_load(req.credentials)
    try:
        result = create_instance(
            project_id=creds['project_id'],
            zone=req.zone,
            instance_name=req.name,
            machine_type=req.machine_type,
            ssh_key=req.ssh_key,
            password=req.password
        )
        # result is a dict with keys: success, name, public_ip, password or error
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post('/list')
def api_list(req: ListRequest):
    # Si no se envía credentials en el body, usar el archivo local ./credentials.json
    credentials_path = req.credentials or os.path.join(os.path.dirname(__file__), 'credentials.json')
    creds = _set_credentials_and_load(credentials_path)
    try:
        instances = list_instances(
            project_id=creds['project_id'],
            zone=req.zone,
            state=req.state
        )
        serialized = _serialize_instances(instances, zone=req.zone)
        if not serialized:
            return {"success": True, "count": 0, "instances": [], "message": "No se encontraron instancias"}
        return {"success": True, "count": len(serialized), "instances": serialized}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get('/list')
def api_list_get(zone: Optional[str] = None, credentials_path: Optional[str] = None, state: Optional[str] = None):
    """GET endpoint para listar instancias GCP (usa `credentials.json` por defecto).

    Query params:
      - zone: zona opcional
      - credentials_path: ruta al JSON de credenciales
      - state: filtro opcional por estado (ej: RUNNING, TERMINATED)
    """
    credentials_path = credentials_path or os.path.join(os.path.dirname(__file__), 'credentials.json')
    creds = _set_credentials_and_load(credentials_path)
    try:
        instances = list_instances(
            project_id=creds['project_id'],
            zone=zone,
            state=state
        )
        serialized = _serialize_instances(instances, zone=zone)
        if not serialized:
            return {"success": True, "count": 0, "instances": [], "message": "No se encontraron instancias"}
        return {"success": True, "count": len(serialized), "instances": serialized}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post('/delete')
def api_delete(req: DeleteRequest):
    creds = _set_credentials_and_load(req.credentials)
    try:
        if req.zone:
            success = delete_instance(
                project_id=creds['project_id'],
                zone=req.zone,
                instance_name=req.name
            )
        else:
            success = find_and_delete_instance(
                project_id=creds['project_id'],
                instance_name=req.name
            )
        return {"success": bool(success)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---- AWS endpoints ---------------------------------
class AwsListRequest(BaseModel):
    region: Optional[str] = "us-west-2"
    aws_access_key: Optional[str] = None
    aws_secret_key: Optional[str] = None
    aws_session_token: Optional[str] = None
    state: Optional[str] = None


class AwsDebugListRequest(BaseModel):
    region: Optional[str] = None
    aws_access_key: Optional[str] = None
    aws_secret_key: Optional[str] = None
    aws_session_token: Optional[str] = None


class AwsFindRequest(BaseModel):
    region: Optional[str] = "us-west-2"
    name: Optional[str] = None
    aws_access_key: Optional[str] = None
    aws_secret_key: Optional[str] = None
    aws_session_token: Optional[str] = None


class AwsCreateRequest(BaseModel):
    region: str = "us-west-2"
    name: Optional[str] = None
    image_id: str = "ami-03c1f788292172a4e"
    instance_type: str
    password: Optional[str] = None
    key_name: Optional[str] = None
    security_group_ids: Optional[List[str]] = None
    subnet_id: Optional[str] = None
    min_count: Optional[int] = 1
    max_count: Optional[int] = 1
    aws_access_key: Optional[str] = None
    aws_secret_key: Optional[str] = None
    aws_session_token: Optional[str] = None


class AwsDeleteRequest(BaseModel):
    region: Optional[str] = None
    instance_id: Optional[str] = None
    name: Optional[str] = None
    aws_access_key: Optional[str] = None
    aws_secret_key: Optional[str] = None
    aws_session_token: Optional[str] = None
@app.get('/aws/list')
def api_aws_list_get(region: Optional[str] = None, credentials_path: Optional[str] = None, state: Optional[str] = None):
    """GET endpoint para listar instancias AWS (usa `credentials_aws.json` por defecto).

    Query params:
      - region: region opcional
      - credentials_path: ruta al JSON de credenciales AWS
      - state: filtro opcional por estado (ej: running, stopped)
    """
    credentials_path = credentials_path or os.path.join(os.path.dirname(__file__), 'credentials_aws.json')
    creds = _load_aws_credentials_file(credentials_path)

    # If no credentials were found in file and none provided inline, fail fast.
    if not (creds.get('aws_access_key_id') or creds.get('aws_access_key') or creds.get('aws_secret_access_key') or creds.get('aws_secret_key')):
        raise HTTPException(status_code=400, detail=(
            "No AWS credentials found. Please provide a valid 'credentials_aws.json' in the repo root "
            "or pass 'aws_access_key' and 'aws_secret_key' in the request."
        ))
    try:
        instances = list_instances_aws(region_name=region or DEFAULT_REGION,
                                       aws_access_key=creds.get('aws_access_key_id'),
                                       aws_secret_key=creds.get('aws_secret_access_key'),
                                       aws_session_token=creds.get('aws_session_token'),
                                       state=state)
        if not instances:
            return {"success": True, "count": 0, "instances": [], "message": "No se encontraron instancias con el prefijo t3- activas"}
        return {"success": True, "count": len(instances), "instances": instances}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post('/aws/list_debug')
def api_aws_list_debug(req: AwsDebugListRequest):
    """Devuelve todas las instancias AWS (sin filtrar por t3-) — endpoint temporal para depuración."""
    try:
        aws_creds = {}
        if req.aws_access_key or req.aws_secret_key or req.aws_session_token:
            aws_creds = {
                'aws_access_key': req.aws_access_key,
                'aws_secret_key': req.aws_secret_key,
                'aws_session_token': req.aws_session_token,
                'region': req.region
            }
        else:
            aws_creds = _load_aws_credentials_file()

        # call debug function that returns all instances
        from aws_instances import list_instances_aws_all
        instances = list_instances_aws_all(
            region_name=req.region or aws_creds.get('region'),
            aws_access_key=aws_creds.get('aws_access_key_id') or aws_creds.get('aws_access_key'),
            aws_secret_key=aws_creds.get('aws_secret_access_key') or aws_creds.get('aws_secret_key'),
            aws_session_token=aws_creds.get('aws_session_token')
        )
        if not instances:
            return {"success": True, "count": 0, "instances": [], "message": "No se encontraron instancias (debug, sin filtro)"}
        return {"success": True, "count": len(instances), "instances": instances}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post('/aws/find')
def api_aws_find(req: AwsFindRequest):
    """Busca instancias AWS por nombre (sólo devuelve t3-)."""
    try:
        aws_creds = {}
        if req.aws_access_key or req.aws_secret_key or req.aws_session_token:
            aws_creds = {
                'aws_access_key': req.aws_access_key,
                'aws_secret_key': req.aws_secret_key,
                'aws_session_token': req.aws_session_token,
                'region': req.region
            }
        else:
            aws_creds = _load_aws_credentials_file()

        instances = find_instances_aws(
            name=req.name,
            region_name=req.region or aws_creds.get('region') or 'us-west-2',
            aws_access_key=aws_creds.get('aws_access_key_id') or aws_creds.get('aws_access_key'),
            aws_secret_key=aws_creds.get('aws_secret_access_key') or aws_creds.get('aws_secret_key'),
            aws_session_token=aws_creds.get('aws_session_token')
        )
        if not instances:
            return {"success": True, "count": 0, "instances": [], "message": "No se encontraron instancias t3- para esa búsqueda"}
        return {"success": True, "count": len(instances), "instances": instances}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post('/aws/create')
def api_aws_create(req: AwsCreateRequest):
    try:
        # cargar credenciales desde body o archivo local
        aws_creds = {}
        if req.aws_access_key or req.aws_secret_key or req.aws_session_token:
            aws_creds = {
                'aws_access_key': req.aws_access_key,
                'aws_secret_key': req.aws_secret_key,
                'aws_session_token': req.aws_session_token,
                'region': req.region
            }
        else:
            aws_creds = _load_aws_credentials_file()

        created = create_instance_aws(
            region_name=req.region or aws_creds.get('region') or 'us-west-2',
            image_id=req.image_id,
            instance_type=req.instance_type,
            password=req.password,
            name=req.name,
            key_name=req.key_name,
            security_group_ids=req.security_group_ids,
            subnet_id=req.subnet_id,
            min_count=req.min_count,
            max_count=req.max_count,
            aws_access_key=aws_creds.get('aws_access_key_id') or aws_creds.get('aws_access_key'),
            aws_secret_key=aws_creds.get('aws_secret_access_key') or aws_creds.get('aws_secret_key'),
            aws_session_token=aws_creds.get('aws_session_token')
        )
        return {"success": True, "created": created}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post('/aws/delete')
def api_aws_delete(req: AwsDeleteRequest):
    try:
        aws_creds = {}
        if req.aws_access_key or req.aws_secret_key or req.aws_session_token:
            aws_creds = {
                'aws_access_key': req.aws_access_key,
                'aws_secret_key': req.aws_secret_key,
                'aws_session_token': req.aws_session_token,
                'region': req.region
            }
        else:
            aws_creds = _load_aws_credentials_file()

        result = delete_instance_aws(
            instance_id=req.instance_id,
            name=req.name,
            region_name=req.region or aws_creds.get('region') or 'us-west-2',
            aws_access_key=aws_creds.get('aws_access_key_id') or aws_creds.get('aws_access_key'),
            aws_secret_key=aws_creds.get('aws_secret_access_key') or aws_creds.get('aws_secret_key'),
            aws_session_token=aws_creds.get('aws_session_token')
        )
        return {"success": True, "result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---- Combined endpoints: operate in BOTH providers ----------------
class AllCreateRequest(BaseModel):
    gcp: CreateRequest
    aws: AwsCreateRequest
    strategy: Optional[str] = "sequential"  # or 'parallel'


class AllListRequest(BaseModel):
    gcp_credentials: Optional[str] = None
    gcp_zone: Optional[str] = None
    aws_region: Optional[str] = None
    aws_access_key: Optional[str] = None
    aws_secret_key: Optional[str] = None
    aws_session_token: Optional[str] = None
    state: Optional[str] = None


class AllDeleteRequest(BaseModel):
    gcp_credentials: Optional[str] = None
    gcp_name: Optional[str] = None
    gcp_zone: Optional[str] = None
    aws_region: Optional[str] = None
    aws_instance_id: Optional[str] = None
    aws_name: Optional[str] = None
    aws_access_key: Optional[str] = None
    aws_secret_key: Optional[str] = None
    aws_session_token: Optional[str] = None


class AllFindRequest(BaseModel):
    # GCP find params
    gcp_credentials: Optional[str] = None
    gcp_zone: Optional[str] = None
    gcp_region: Optional[str] = None
    gcp_cpus: Optional[int] = None
    gcp_ram: Optional[int] = None
    # AWS find params
    aws_region: Optional[str] = None
    aws_min_vcpus: Optional[int] = None
    aws_min_memory_gb: Optional[int] = None
    aws_access_key: Optional[str] = None
    aws_secret_key: Optional[str] = None
    aws_session_token: Optional[str] = None


@app.post('/all/create')
def api_all_create(req: AllCreateRequest):
    results = {'gcp': None, 'aws': None}
    errors = {'gcp': None, 'aws': None}

    # GCP create
    try:
        creds = _set_credentials_and_load(req.gcp.credentials)
        # pass password through so startup script can enable SSH password auth
        gcp_result = create_instance(
            project_id=creds['project_id'],
            zone=req.gcp.zone,
            instance_name=req.gcp.name,
            machine_type=req.gcp.machine_type,
            ssh_key=req.gcp.ssh_key,
            password=getattr(req.gcp, 'password', None)
        )
        # create_instance returns a dict with success/name/public_ip/password
        results['gcp'] = gcp_result
    except Exception as e:
        errors['gcp'] = str(e)
        results['gcp'] = {'success': False}

    # AWS create
    try:
        # cargar credenciales AWS desde objeto aws del request o archivo local
        aws_creds = {}
        # buscar en req.aws.* (estos names: aws_access_key, aws_secret_key si se pasaron directamente)
        if getattr(req.aws, 'aws_access_key', None) or getattr(req.aws, 'aws_secret_key', None) or getattr(req.aws, 'aws_session_token', None):
            aws_creds = {
                'aws_access_key': getattr(req.aws, 'aws_access_key', None),
                'aws_secret_key': getattr(req.aws, 'aws_secret_key', None),
                'aws_session_token': getattr(req.aws, 'aws_session_token', None),
                'region': req.aws.region
            }
        else:
            aws_creds = _load_aws_credentials_file()

        ids = create_instance_aws(
            region_name=req.aws.region or aws_creds.get('region') or 'us-west-2',
            image_id=getattr(req.aws, 'image_id', None) or 'ami-03c1f788292172a4e',
            instance_type=getattr(req.aws, 'instance_type', None) or 't3.micro',
            password=getattr(req.aws, 'password', None),
            name=getattr(req.aws, 'name', None),
            key_name=req.aws.key_name,
            security_group_ids=req.aws.security_group_ids,
            subnet_id=req.aws.subnet_id,
            min_count=req.aws.min_count,
            max_count=req.aws.max_count,
            aws_access_key=aws_creds.get('aws_access_key_id') or aws_creds.get('aws_access_key'),
            aws_secret_key=aws_creds.get('aws_secret_access_key') or aws_creds.get('aws_secret_key'),
            aws_session_token=aws_creds.get('aws_session_token')
        )
        # create_instance_aws returns a list of created instance dicts (including PublicIpAddress, Password, username)
        results['aws'] = {'success': True, 'created': ids}
    except Exception as e:
        errors['aws'] = str(e)
        results['aws'] = {'success': False}

    return {"results": results, "errors": errors}


@app.post('/all/list')
def api_all_list(req: AllListRequest):
    out = {'gcp': None, 'aws': None, 'errors': {}}

    # GCP list
    try:
        credentials_path = req.gcp_credentials or os.path.join(os.path.dirname(__file__), 'credentials.json')
        creds = _set_credentials_and_load(credentials_path)
        insts = list_instances(project_id=creds['project_id'], zone=req.gcp_zone, state=req.state)
        out['gcp'] = _serialize_instances(insts, zone=req.gcp_zone)
    except Exception as e:
        out['errors']['gcp'] = str(e)

    # AWS list
    try:
        # Prefer AWS creds sent in the request body, otherwise fall back to local file
        if req.aws_access_key or req.aws_secret_key or req.aws_session_token:
            aws_access_key = req.aws_access_key
            aws_secret_key = req.aws_secret_key
            aws_session_token = req.aws_session_token
            aws_region = req.aws_region or 'us-west-2'
        else:
            aws_creds = _load_aws_credentials_file()
            aws_access_key = aws_creds.get('aws_access_key_id') or aws_creds.get('aws_access_key')
            aws_secret_key = aws_creds.get('aws_secret_access_key') or aws_creds.get('aws_secret_key')
            aws_session_token = aws_creds.get('aws_session_token')
            aws_region = req.aws_region or aws_creds.get('region') or 'us-west-2'

        aws_insts = list_instances_aws(region_name=aws_region,
                                       aws_access_key=aws_access_key,
                                       aws_secret_key=aws_secret_key,
                                       aws_session_token=aws_session_token)
        out['aws'] = aws_insts
    except Exception as e:
        out['errors']['aws'] = str(e)

    # Añadir mensajes cuando no hay instancias en alguno de los proveedores
    if not out.get('gcp'):
        out['gcp'] = []
        out['errors'].setdefault('gcp', None)
        out.setdefault('message_gcp', 'No se encontraron instancias en GCP')
    if not out.get('aws'):
        out['aws'] = []
        out['errors'].setdefault('aws', None)
        out.setdefault('message_aws', 'No se encontraron instancias en AWS')

    return out


@app.post('/all/delete')
def api_all_delete(req: AllDeleteRequest):
    results = {'gcp': None, 'aws': None}
    errors = {'gcp': None, 'aws': None}

    # GCP delete
    try:
        if req.gcp_name:
            credentials_path = req.gcp_credentials or os.path.join(os.path.dirname(__file__), 'credentials.json')
            creds = _set_credentials_and_load(credentials_path)
            if req.gcp_zone:
                ok = delete_instance(project_id=creds['project_id'], zone=req.gcp_zone, instance_name=req.gcp_name)
            else:
                ok = find_and_delete_instance(project_id=creds['project_id'], instance_name=req.gcp_name)
            results['gcp'] = {'success': bool(ok)}
    except Exception as e:
        errors['gcp'] = str(e)
        results['gcp'] = {'success': False}

    # AWS delete
    try:
        # Prefer AWS creds sent in body, otherwise rely on default credentials file
        if req.aws_access_key or req.aws_secret_key or req.aws_session_token:
            aws_access_key = req.aws_access_key
            aws_secret_key = req.aws_secret_key
            aws_session_token = req.aws_session_token
            aws_region = req.aws_region or 'us-west-2'
        else:
            aws_creds = _load_aws_credentials_file()
            aws_access_key = aws_creds.get('aws_access_key_id') or aws_creds.get('aws_access_key')
            aws_secret_key = aws_creds.get('aws_secret_access_key') or aws_creds.get('aws_secret_key')
            aws_session_token = aws_creds.get('aws_session_token')
            aws_region = req.aws_region or aws_creds.get('region') or 'us-west-2'

        res = delete_instance_aws(instance_id=req.aws_instance_id, name=req.aws_name, region_name=aws_region,
                                  aws_access_key=aws_access_key, aws_secret_key=aws_secret_key, aws_session_token=aws_session_token)
        results['aws'] = res
    except Exception as e:
        errors['aws'] = str(e)
        results['aws'] = {'success': False}

    return {"results": results, "errors": errors}


@app.post('/all/find')
def api_all_find(req: AllFindRequest):
    results = {'gcp': None, 'aws': None}
    errors = {'gcp': None, 'aws': None}

    # GCP find
    try:
        if req.gcp_cpus and req.gcp_ram and req.gcp_zone:
            credentials_path = req.gcp_credentials or os.path.join(os.path.dirname(__file__), 'credentials.json')
            creds = _set_credentials_and_load(credentials_path)
            gcp_results = find_instances(project_id=creds['project_id'], zone=req.gcp_zone, region=req.gcp_region or '', num_cpus=req.gcp_cpus, num_ram_gb=req.gcp_ram)
            results['gcp'] = gcp_results
        else:
            results['gcp'] = []
    except Exception as e:
        errors['gcp'] = str(e)

    # AWS find
    try:
        if req.aws_min_vcpus and req.aws_min_memory_gb:
            # Use provided AWS creds if present
            if req.aws_access_key or req.aws_secret_key or req.aws_session_token:
                aws_access_key = req.aws_access_key
                aws_secret_key = req.aws_secret_key
                aws_session_token = req.aws_session_token
                aws_region = req.aws_region
            else:
                aws_creds = _load_aws_credentials_file()
                aws_access_key = aws_creds.get('aws_access_key_id') or aws_creds.get('aws_access_key')
                aws_secret_key = aws_creds.get('aws_secret_access_key') or aws_creds.get('aws_secret_key')
                aws_session_token = aws_creds.get('aws_session_token')
                aws_region = req.aws_region or aws_creds.get('region')

            aws_results = find_instance_types_aws(region_name=aws_region, min_vcpus=req.aws_min_vcpus, min_memory_gb=req.aws_min_memory_gb,
                                                 aws_access_key=aws_access_key, aws_secret_key=aws_secret_key, aws_session_token=aws_session_token)
            results['aws'] = aws_results
        else:
            results['aws'] = []
    except Exception as e:
        errors['aws'] = str(e)

    return {"results": results, "errors": errors}


def main():
    parser = argparse.ArgumentParser(
        description='Gestionar instancias de GCP'
    )
    
    # Acciones
    parser.add_argument(
        '--find-instance',
        action='store_true',
        help='Buscar instancias compatibles'
    )
    
    parser.add_argument(
        '--create-instance',
        action='store_true',
        help='Crear una nueva instancia'
    )
    
    parser.add_argument(
        '--list-instances',
        action='store_true',
        help='Listar todas las instancias del proyecto'
    )
    
    parser.add_argument(
        '--delete-instance',
        action='store_true',
        help='Borrar una instancia del proyecto'
    )
    
    # Parámetros comunes
    parser.add_argument(
        '--credentials',
        required=True,
        help='Ruta al archivo de credenciales de GCP (JSON)'
    )
    
    parser.add_argument(
        '--zone',
        help='Zona de GCP (ej: us-central1-a) - requerido para --find-instance y --create-instance'
    )
    
    # Parámetros para find-instance
    parser.add_argument(
        '--region',
        help='Región de GCP (ej: us-central1) - requerido para --find-instance'
    )
    
    parser.add_argument(
        '--cpus',
        type=int,
        help='Número mínimo de CPUs - requerido para --find-instance'
    )
    
    parser.add_argument(
        '--ram',
        type=int,
        help='Cantidad mínima de RAM en GB - requerido para --find-instance'
    )
    
    
    parser.add_argument(
        '--machine-type',
        help='Tipo de máquina (ej: e2-medium, n1-standard-1) - requerido para --create-instance'
    )
    
    parser.add_argument(
        '--ssh-key',
        help='Clave SSH pública para acceso a la instancia (formato: usuario:ssh-rsa AAAA...)'
    )
    
    parser.add_argument(
        '--name',
        help='Nombre de la instancia (ej: node1, node2, node3, etc.)'
    )
    
    args = parser.parse_args()
    
    # Validar que se haya seleccionado una acción
    if not args.find_instance and not args.create_instance and not args.list_instances and not args.delete_instance:
        parser.print_help()
        return
    
    # Cargar credenciales
    print(f"Cargando credenciales desde: {args.credentials}")
    credentials = load_credentials(args.credentials)
    
    # Configurar variable de entorno para autenticación
    os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = args.credentials
    
    if args.find_instance:
        # Validar parámetros requeridos para find-instance
        if not all([args.region, args.cpus, args.ram, args.zone]):
            parser.error("--find-instance requiere --region, --cpus y --ram y --zone")
        
        # Buscar instancias
        find_instances(
            project_id=credentials['project_id'],
            zone=args.zone,
            region=args.region,
            num_cpus=args.cpus,
            num_ram_gb=args.ram
        )
    
    elif args.create_instance:
        # Validar parámetros requeridos para create-instance
        if not all([args.name, args.machine_type, args.zone]):
            parser.error("--create-instance requiere --name, --machine-type, --zone")
        
        
        # Crear instancia
        create_instance(
            project_id=credentials['project_id'],
            zone=args.zone,
            instance_name=args.name,
            machine_type=args.machine_type,
            ssh_key=args.ssh_key
        )
    
    elif args.list_instances:
        # Listar instancias
        list_instances(
            project_id=credentials['project_id'],
            zone=args.zone,
        )
    
    elif args.delete_instance:
        # Validar parámetros requeridos para delete-instance
        if not args.name:
            parser.error("--delete-instance requiere --name")
        
        # Borrar instancia
        if args.zone:
            # Borrar en una zona específica
            delete_instance(
                project_id=credentials['project_id'],
                zone=args.zone,
                instance_name=args.name
            )
        else:
            # Buscar en todas las zonas y borrar
            find_and_delete_instance(
                project_id=credentials['project_id'],
                instance_name=args.name
            )


if __name__ == '__main__':
    main()