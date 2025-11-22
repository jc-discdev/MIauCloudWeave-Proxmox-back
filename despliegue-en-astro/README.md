# Despliegue en Astro — Guía rápida

Este documento explica cómo integrar Astro con la API del backend para: seleccionar tipos de instancia por CPU/RAM, crear grupos de nodos y recuperar credenciales (IP/password) devueltas por el servicio.

Requisitos previos
- El backend debe estar accesible desde Astro (ej: `http://<backend-host>:8001`).
- Credenciales GCP (`credentials.json`) y/o AWS (`credentials_aws.json`) deben estar disponibles y su ruta indicada en las requests.

Endpoints relevantes
- `GET /instance-types/gcp?zone=<zone>&cpus=<n>&ram_gb=<g>` — devuelve tipos GCP que coinciden con recursos.
- `GET /instance-types/aws?min_vcpus=<n>&min_memory_gb=<g>` — devuelve tipos AWS que coinciden.
- `POST /create` — crea N instancias GCP (parámetros: `credentials`, `zone`, `name`, `machine_type`, `count`, `image_project`/`image_family` o `image`).
- `POST /aws/create` — crea instancias AWS con `min_count/max_count`, `instance_type`, `name`.

Ejemplos de llamadas desde Astro (JS)

1) Consultar tipos GCP

```js
const res = await fetch('http://127.0.0.1:8001/instance-types/gcp?zone=europe-west1-b&cpus=2&ram_gb=4');
const json = await res.json();
// json.instance_types -> lista de opciones
```

2) Crear clúster GCP (3 nodos)

```js
const payload = {
  credentials: './credentials.json',
  zone: 'europe-west1-b',
  name: 't3-cluster-astro',
  machine_type: 'e2-medium',
  count: 3,
  image_project: 'ubuntu-os-cloud',
  image_family: 'ubuntu-2204-lts'
};
const res = await fetch('http://127.0.0.1:8001/create', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(payload)});
const data = await res.json();
console.log(data);
```

3) Crear clúster AWS (3 nodos)

```js
const payload = {
  region: 'us-west-2',
  name: 'mi-cluster-aws',
  instance_type: 't3.medium',
  min_count: 3,
  max_count: 3
};
const res = await fetch('http://127.0.0.1:8001/aws/create', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(payload)});
const data = await res.json();
console.log(data);
```

Notas y recomendaciones
- Las contraseñas generadas por el backend se devuelven en claro en la respuesta JSON (útil para pruebas). Para producción, considere enviar las credenciales por un canal seguro o almacenarlas en un secret store temporal.
- Para clústeres con muchos nodos, considere crear nombres únicos o prefijarlos con un identificador de clúster.
- Añada validaciones en Astro para comprobar que el backend devuelve `success: true` antes de mostrar credenciales al usuario.


Dropdown UI (Astro) — quick integration

To let users select instance types with a dropdown, the frontend must:
- Fetch instance types from the backend (`/instance-types/gcp` or `/instance-types/aws`).
- Populate a `<select>` element with the results.
- Allow the user to set `count`, `image_family` (or `image`) and submit to `/create` or `/aws/create`.

We provide a minimal React component example in `integración con astro/astro_examples.md` named `NodeCreator` that you can drop into an Astro project. Use `client:load` to render the component as an island in Astro.

Server notes:
- Backend endpoints `/instance-types/gcp` and `/instance-types/aws` already exist and accept query params for filtering (cpus/ram).
- The `/create` endpoint accepts `count`, `image_project`, `image_family`, `image` and `machine_type`.

Security note: Generated passwords are returned in responses. For production, use a secrets manager or ephemeral delivery channel.
Si quieres, puedo añadir ejemplos de código más completos para usar desde un `server` de Astro (TypeScript) y un componente UI que muestre tipos y permita crear clústeres interactivos.