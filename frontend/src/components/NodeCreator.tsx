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
      try{
        const res = await fetch(`/instance-types/gcp?zone=${zone}&cpus=${cpus}&ram_gb=${ram}`);
        const j = await res.json();
        setTypes(j.instance_types || []);
        if(j.instance_types && j.instance_types.length) setSelected(j.instance_types[0].name);
      }catch(e){
        console.error('Error loading types', e);
      }
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
    try{
      const res = await fetch('/create',{method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(payload)});
      const j = await res.json();
      setResult(j);
    }catch(e){
      setResult({success:false, error: String(e)});
    }
  }

  return (
    <div className="p-4 border rounded">
      <h3 className="text-lg font-semibold mb-2">Create GCP Nodes</h3>
      <div style={{display:'grid', gap:8}}>
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
        <button onClick={createNodes} className="px-3 py-2 bg-blue-600 text-white rounded">Create</button>
      </div>
      <pre style={{whiteSpace:'pre-wrap', marginTop:12}}>{JSON.stringify(result, null, 2)}</pre>
    </div>
  );
}
