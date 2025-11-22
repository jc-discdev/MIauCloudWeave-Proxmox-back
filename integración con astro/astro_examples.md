# Integración con Astro — Ejemplos

Este archivo contiene ejemplos de cómo Astro puede interactuar con la API para:
- pedir tipos de instancia disponibles según vCPU/RAM
- crear un grupo de nodos (número de nodos, tipo de instancia, imagen)
- obtener la IP y la contraseña devuelta por el backend

Nota: la API espera rutas como `http://<backend_host>:8001`.

1) Obtener tipos de instancia GCP (GET)

Ejemplo (Astro hace un GET):

```
GET /instance-types/gcp?zone=europe-west1-b&cpus=2&ram_gb=4
Host: 127.0.0.1:8001
```

Respuesta (ejemplo):

```json
{
  "success": true,
  "count": 3,
  "instance_types": [
    {"name":"e2-standard-2","cpus":2,"ram_gb":4.0,"description":"..."},
    {"name":"n1-standard-2","cpus":2,"ram_gb":4.0,"description":"..."}
  ]
}
```

2) Obtener tipos de instancia AWS (GET)

Ejemplo (Astro hace un GET):

```
GET /instance-types/aws?min_vcpus=2&min_memory_gb=4
Host: 127.0.0.1:8001
```

Respuesta (ejemplo):

```json
{
  "success": true,
  "count": 5,
  "instance_types": [
    {"instance_type":"t3.large","vcpus":2,"memory_gb":8.0},
    {"instance_type":"m5.large","vcpus":2,"memory_gb":8.0}
  ]
}
```

3) Crear N nodos en GCP (POST -> `/create`):

Astro puede POSTear a `/create` enviando `count`, `machine_type`, y `image_project`/`image_family` o `image`.
Ejemplo body JSON:

```json
{
  "credentials": "./credentials.json",
  "zone": "europe-west1-b",
  "name": "t3-mycluster",
  "machine_type": "e2-medium",
  "count": 3,
  "image_project": "ubuntu-os-cloud",
  "image_family": "ubuntu-2204-lts"
}
```

Respuesta (ejemplo):

```json
{
  "success": true,
  "created": [
    {"success": true, "name": "t3-mycluster-1", "public_ip": "34.x.x.x", "password": "Abc123...", "username": "ubuntu"},
    {"success": true, "name": "t3-mycluster-2", "public_ip": "34.x.x.y", "password": "Zyx987...", "username": "ubuntu"}
  ]
}
```

4) Crear N nodos en AWS (POST `/aws/create`):

Astro POST a `/aws/create` con `min_count`/`max_count` o `min_count == max_count == count` y `instance_type`.
Ejemplo body JSON:

```json
{
  "region": "us-west-2",
  "name": "mi-cluster-aws",
  "instance_type": "t3.medium",
  "min_count": 3,
  "max_count": 3
}
```

Respuesta (ejemplo):

```json
{
  "success": true,
  "created": [
    {"InstanceId":"i-0123","Name":"t3-mi-cluster-aws","PublicIpAddress":"3.x.x.x","Password":"...","username":"ubuntu"}
  ]
}
```


Código de ejemplo (Astro/JS) usando fetch:

```js
// obtener tipos GCP
const res = await fetch('http://127.0.0.1:8001/instance-types/gcp?zone=europe-west1-b&cpus=2&ram_gb=4');
const data = await res.json();
console.log(data.instance_types);

// crear 3 nodos GCP
const createRes = await fetch('http://127.0.0.1:8001/create', {
  method: 'POST',
  headers: {'Content-Type': 'application/json'},
  body: JSON.stringify({
    credentials: './credentials.json',
    zone: 'europe-west1-b',
    name: 't3-mycluster',
    machine_type: 'e2-medium',
    count: 3,
    image_project: 'ubuntu-os-cloud',
    image_family: 'ubuntu-2204-lts'
  })
});
const createData = await createRes.json();
console.log(createData);
```


---

Dropdown UI example (Astro)

Below is a minimal React component you can include in an Astro project to let users select instance types from a dropdown (fetched from the backend), choose a node count and image, then create the nodes.

1) Install React support in your Astro project (if not already):

```bash
npm install react react-dom
npm install --save-dev @types/react
```

2) Example React component (client-side) — save as `src/components/NodeCreator.tsx` in your Astro site:

```tsx
import React, {useEffect, useState} from 'react';

type GcpType = { name: string; cpus: number; ram_gb: number; description?: string };

export default function NodeCreator(){
  const [zone, setZone] = useState('europe-west1-b');
  const [cpus, setCpus] = useState(2);
  const [ram, setRam] = useState(4);
  const [types, setTypes] = useState<GcpType[]>([]);
  const [selected, setSelected] = useState('');
  const [count, setCount] = useState(1);
  const [imageProject, setImageProject] = useState('ubuntu-os-cloud');
  const [imageFamily, setImageFamily] = useState('ubuntu-2204-lts');
  const [result, setResult] = useState<any>(null);

  useEffect(()=>{
    async function load(){
      const res = await fetch(`/instance-types/gcp?zone=${zone}&cpus=${cpus}&ram_gb=${ram}`);
      const j = await res.json();
      setTypes(j.instance_types || []);
      if(j.instance_types && j.instance_types.length) setSelected(j.instance_types[0].name);
    }
    load();
  }, [zone, cpus, ram]);

  async function createNodes(){
    const payload = {
      credentials: './credentials.json',
      zone,
      name: 't3-astrocluster',
      machine_type: selected,
      count,
      image_project: imageProject,
      image_family: imageFamily
    };
    const res = await fetch('/create',{method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(payload)});
    const j = await res.json();
    setResult(j);
  }

  return (
    <div>
      <h3>Create GCP Nodes</h3>
      <label>Zone: <input value={zone} onChange={e=>setZone(e.target.value)}/></label>
      <label>CPUs: <input type="number" value={cpus} onChange={e=>setCpus(Number(e.target.value))}/></label>
      <label>RAM(GB): <input type="number" value={ram} onChange={e=>setRam(Number(e.target.value))}/></label>
      <div>
        <label>Instance type:</label>
        <select value={selected} onChange={e=>setSelected(e.target.value)}>
          {types.map(t=> (<option key={t.name} value={t.name}>{t.name} — {t.cpus} vCPU / {t.ram_gb}GB</option>))}
        </select>
      </div>
      <label>Count: <input type="number" min={1} value={count} onChange={e=>setCount(Number(e.target.value))}/></label>
      <label>Image project: <input value={imageProject} onChange={e=>setImageProject(e.target.value)}/></label>
      <label>Image family: <input value={imageFamily} onChange={e=>setImageFamily(e.target.value)}/></label>
      <button onClick={createNodes}>Create</button>
      <pre>{JSON.stringify(result, null, 2)}</pre>
    </div>
  )
}
```

3) Use this component in an Astro page and enable client-side rendering (island):

```astro
---
import NodeCreator from '../components/NodeCreator';
---

<NodeCreator client:load />
```

This will render a dropdown with instance types fetched from the backend and let the user create nodes by pressing `Create`. The response includes generated passwords per node.

---

If you want, puedo añadir un ejemplo `src/pages/deploy.astro` completo y actualizar la guía con instrucciones puntuales para Astro + Vercel/Netlify.
