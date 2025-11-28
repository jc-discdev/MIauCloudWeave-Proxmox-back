# Integración con Frontend (Astro/React)

## 🎯 Endpoints de la API Proxmox

### Base URL
```
http://localhost:8001
```

### Documentación Interactiva
- Swagger UI: http://localhost:8001/docs
- ReDoc: http://localhost:8001/redoc

---

## 📡 Endpoints Principales

### 1. Listar VMs y Contenedores

```javascript
// GET request
const response = await fetch('http://localhost:8001/proxmox/list');
const data = await response.json();

// Respuesta:
{
  "success": true,
  "count": 5,
  "vms": [
    {
      "vmid": 100,
      "name": "my-vm",
      "node": "pve",
      "type": "qemu",
      "status": "running",
      "cpu": 2,
      "memory": 2048,
      "disk": 20,
      "ip": "192.168.1.50"
    }
  ]
}
```

### 2. Crear VM o Contenedor

```javascript
// Crear VM QEMU
const createVM = async () => {
  const response = await fetch('http://localhost:8001/proxmox/create', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      name: 'my-vm',
      vm_type: 'qemu',
      cores: 2,
      memory: 2048,
      disk_size: 20,
      start: true
    })
  });
  return await response.json();
};

// Crear Contenedor LXC
const createContainer = async () => {
  const response = await fetch('http://localhost:8001/proxmox/create', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      name: 'my-container',
      vm_type: 'lxc',
      cores: 1,
      memory: 512,
      disk_size: 8,
      start: true
    })
  });
  return await response.json();
};
```

### 3. Crear Cluster Docker Swarm

```javascript
const createCluster = async () => {
  const response = await fetch('http://localhost:8001/cluster/create', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      manager: {
        name: 'swarm-manager',
        vm_type: 'qemu',
        cores: 2,
        memory: 2048,
        disk_size: 20
      },
      workers: [{
        name: 'swarm-worker',
        vm_type: 'lxc',
        cores: 1,
        memory: 1024,
        disk_size: 10,
        count: 2
      }]
    })
  });
  return await response.json();
};
```

### 4. Obtener Credenciales

```javascript
// Todas las credenciales
const response = await fetch('http://localhost:8001/credentials');
const data = await response.json();

// Credenciales de una VM específica
const response = await fetch('http://localhost:8001/credentials?instance_name=my-vm');
const data = await response.json();

// Respuesta:
{
  "success": true,
  "instance_name": "my-vm",
  "credentials": {
    "username": "ubuntu",
    "password": "generated_password",
    "ip": "192.168.1.50",
    "provider": "proxmox",
    "node": "pve",
    "vmid": 100,
    "type": "qemu"
  }
}
```

### 5. Operaciones (Start/Stop/Restart)

```javascript
// Iniciar VM
const startVM = async (name) => {
  const response = await fetch('http://localhost:8001/proxmox/start', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name })
  });
  return await response.json();
};

// Detener VM
const stopVM = async (name) => {
  const response = await fetch('http://localhost:8001/proxmox/stop', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name })
  });
  return await response.json();
};

// Eliminar VM
const deleteVM = async (name) => {
  const response = await fetch('http://localhost:8001/proxmox/delete', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name, force: true })
  });
  return await response.json();
};
```

---

## 🎨 Ejemplo de Componente React/Astro

### Componente de Listado de VMs

```tsx
import { useEffect, useState } from 'react';

interface VM {
  vmid: number;
  name: string;
  type: 'qemu' | 'lxc';
  status: string;
  cpu: number;
  memory: number;
  ip: string | null;
}

export default function VMList() {
  const [vms, setVms] = useState<VM[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadVMs();
  }, []);

  const loadVMs = async () => {
    try {
      const response = await fetch('http://localhost:8001/proxmox/list');
      const data = await response.json();
      if (data.success) {
        setVms(data.vms);
      }
    } catch (error) {
      console.error('Error loading VMs:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleStart = async (name: string) => {
    await fetch('http://localhost:8001/proxmox/start', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name })
    });
    loadVMs(); // Recargar lista
  };

  const handleStop = async (name: string) => {
    await fetch('http://localhost:8001/proxmox/stop', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name })
    });
    loadVMs();
  };

  if (loading) return <div>Cargando...</div>;

  return (
    <div>
      <h2>VMs y Contenedores</h2>
      <table>
        <thead>
          <tr>
            <th>Nombre</th>
            <th>Tipo</th>
            <th>Estado</th>
            <th>CPU</th>
            <th>RAM</th>
            <th>IP</th>
            <th>Acciones</th>
          </tr>
        </thead>
        <tbody>
          {vms.map(vm => (
            <tr key={vm.vmid}>
              <td>{vm.name}</td>
              <td>{vm.type === 'qemu' ? '🖥️ VM' : '📦 LXC'}</td>
              <td>
                <span className={vm.status === 'running' ? 'status-running' : 'status-stopped'}>
                  {vm.status}
                </span>
              </td>
              <td>{vm.cpu} vCPU</td>
              <td>{vm.memory} MB</td>
              <td>{vm.ip || 'N/A'}</td>
              <td>
                {vm.status === 'running' ? (
                  <button onClick={() => handleStop(vm.name)}>⏸️ Stop</button>
                ) : (
                  <button onClick={() => handleStart(vm.name)}>▶️ Start</button>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
```

### Componente de Creación de VM

```tsx
import { useState } from 'react';

export default function VMCreator() {
  const [formData, setFormData] = useState({
    name: '',
    vm_type: 'qemu',
    cores: 2,
    memory: 2048,
    disk_size: 10
  });
  const [result, setResult] = useState<any>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    try {
      const response = await fetch('http://localhost:8001/proxmox/create', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(formData)
      });
      const data = await response.json();
      setResult(data);
    } catch (error) {
      setResult({ success: false, error: String(error) });
    }
  };

  return (
    <div>
      <h2>Crear VM/Contenedor</h2>
      <form onSubmit={handleSubmit}>
        <div>
          <label>
            Nombre:
            <input
              type="text"
              value={formData.name}
              onChange={e => setFormData({...formData, name: e.target.value})}
              required
            />
          </label>
        </div>
        
        <div>
          <label>
            Tipo:
            <select
              value={formData.vm_type}
              onChange={e => setFormData({...formData, vm_type: e.target.value as 'qemu' | 'lxc'})}
            >
              <option value="qemu">🖥️ VM (QEMU)</option>
              <option value="lxc">📦 Contenedor (LXC)</option>
            </select>
          </label>
        </div>
        
        <div>
          <label>
            CPU Cores:
            <input
              type="number"
              min="1"
              value={formData.cores}
              onChange={e => setFormData({...formData, cores: Number(e.target.value)})}
            />
          </label>
        </div>
        
        <div>
          <label>
            RAM (MB):
            <input
              type="number"
              min="512"
              step="512"
              value={formData.memory}
              onChange={e => setFormData({...formData, memory: Number(e.target.value)})}
            />
          </label>
        </div>
        
        <div>
          <label>
            Disco (GB):
            <input
              type="number"
              min="8"
              value={formData.disk_size}
              onChange={e => setFormData({...formData, disk_size: Number(e.target.value)})}
            />
          </label>
        </div>
        
        <button type="submit">Crear</button>
      </form>
      
      {result && (
        <div>
          <h3>Resultado:</h3>
          <pre>{JSON.stringify(result, null, 2)}</pre>
        </div>
      )}
    </div>
  );
}
```

---

## 🔐 Seguridad

### CORS
El backend ya tiene CORS configurado para:
- `http://localhost:3000`
- `http://localhost:4321`

Si necesitas otros orígenes, edita `main.py`:

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:4321",
        "https://tu-dominio.com"  # Añade aquí
    ],
    ...
)
```

### Credenciales
Las credenciales (contraseñas) se devuelven en las respuestas JSON. Para producción:
- Usa HTTPS
- Implementa autenticación en el backend
- Almacena credenciales en un gestor de secretos

---

## 📝 TypeScript Types

```typescript
// types.ts
export interface VM {
  vmid: number;
  name: string;
  node: string;
  type: 'qemu' | 'lxc';
  status: 'running' | 'stopped';
  cpu: number;
  memory: number;
  disk: number;
  uptime: number;
  ip: string | null;
  template: boolean;
}

export interface CreateVMRequest {
  name: string;
  vm_type: 'qemu' | 'lxc';
  cores: number;
  memory: number;
  disk_size: number;
  node?: string;
  template?: number;
  iso?: string;
  lxc_template?: string;
  storage?: string;
  bridge?: string;
  cluster_type?: string;
  count?: number;
  ssh_key?: string;
  password?: string;
  start?: boolean;
}

export interface Credentials {
  username: string;
  password: string;
  ip: string;
  provider: 'proxmox';
  node: string;
  vmid: number;
  type: 'qemu' | 'lxc';
}
```

---

## 🚀 Uso en Astro

### Ejemplo de página Astro

```astro
---
// src/pages/vms.astro
import VMList from '../components/VMList';
---

<html>
  <head>
    <title>Gestión de VMs</title>
  </head>
  <body>
    <h1>Gestión de VMs Proxmox</h1>
    <VMList client:load />
  </body>
</html>
```

### API Routes en Astro

```typescript
// src/pages/api/vms.ts
export async function get() {
  const response = await fetch('http://localhost:8001/proxmox/list');
  const data = await response.json();
  return new Response(JSON.stringify(data), {
    status: 200,
    headers: { 'Content-Type': 'application/json' }
  });
}
```

---

Para más información, consulta la documentación interactiva en http://localhost:8001/docs
