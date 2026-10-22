'use client';
import React,{useEffect,useState,useCallback} from 'react';

type Obj=Record<string,any>;
type Api=(path:string,method?:string,body?:any)=>Promise<any>;

const LABEL:Record<string,string>={supported:'Possible discrepancy — supported by evidence',review_required:'Needs human review',inconclusive:'Inconclusive',resolved:'Resolved',candidate:'Candidate'};
const REVIEW_ACTIONS=['Acknowledged','Resolved','Dismissed with Reason'];

function groupOf(f:Obj){
 if(f.finding_type==='missing_evidence')return 'Missing information';
 if(f.finding_type==='contradiction'||f.finding_type==='rule_violation')return 'Possible discrepancies';
 return 'Inconclusive evidence';
}

function GraphView({graph,claimIds}:{graph:Obj,claimIds:Set<string>}){
 const nodes:Obj[]=graph.nodes||[],edges:Obj[]=graph.edges||[];
 const claims=nodes.filter(n=>n.type==='Claim'&&claimIds.has(n.id));
 if(!claims.length)return <p className="muted">No contradicting or supporting claim pairs to draw.</p>;
 const docOf:Record<string,string>={};
 edges.filter(e=>e.type==='EXTRACTED_FROM').forEach(e=>{docOf[e.source]=e.target});
 const docs=Array.from(new Set(claims.map(c=>docOf[c.id]))).filter(Boolean);
 const y=(i:number)=>40+i*64;
 const pos:Record<string,number>={};claims.forEach((c,i)=>{pos[c.id]=i});
 const dpos:Record<string,number>={};docs.forEach((d,i)=>{dpos[d]=i});
 const h=Math.max(claims.length,docs.length)*64+70;
 return <div style={{overflowX:'auto'}}><svg role="img" aria-label="Evidence graph" viewBox={`0 0 760 ${h}`} width="100%" style={{minWidth:640}}>
  <style>{`text{font:12px system-ui,sans-serif;fill:currentColor}`}</style>
  {docs.map(d=>{const n=nodes.find(x=>x.id===d);return <g key={d}><rect x={8} y={y(dpos[d])-4} width={150} height={40} rx={8} fill="none" stroke="currentColor"/><text x={16} y={y(dpos[d])+20}>{(n?.kind||d).toString().replace(/_/g,' ')}</text></g>})}
  {claims.map(c=>{const d=docOf[c.id];return <g key={c.id}>
   {d!==undefined&&<line x1={158} y1={y(dpos[d])+16} x2={250} y2={y(pos[c.id])+16} stroke="currentColor" opacity={.45}/>}
   <rect x={250} y={y(pos[c.id])-4} width={300} height={40} rx={8} fill="none" stroke="currentColor"/>
   <text x={258} y={y(pos[c.id])+12}>{c.field}: {String(c.raw).slice(0,34)}</text>
   <text x={258} y={y(pos[c.id])+27} opacity={.7}>page {c.page}{c.ocr_confidence!=null?` · OCR ${Number(c.ocr_confidence).toFixed(0)}`:''}</text></g>})}
  {edges.filter(e=>(e.type==='CONTRADICTS'||e.type==='SUPPORTS')&&pos[e.source]!==undefined&&pos[e.target]!==undefined).map((e,i)=>{
   const a=y(pos[e.source])+16,b=y(pos[e.target])+16;const bad=e.type==='CONTRADICTS';
   return <path key={i} d={`M550,${a} C${620+(i%3)*30},${a} ${620+(i%3)*30},${b} 550,${b}`} fill="none" stroke={bad?'#c0392b':'#27ae60'} strokeWidth={2.2} strokeDasharray={bad?'6 4':undefined}><title>{e.type}</title></path>})}
  <text x={600} y={h-10} opacity={.7}>red dashed = CONTRADICTS · green = SUPPORTS</text>
 </svg></div>;
}

export default function EvidenceTab({detail,reviewer,api,busy,act}:{detail:Obj,reviewer:boolean,api:Api,busy:boolean,act:(fn:()=>Promise<any>)=>void}){
 const [data,setData]=useState<Obj|null>(null),[graph,setGraph]=useState<Obj|null>(null),[err,setErr]=useState('');
 const load=useCallback(async()=>{
  try{setErr('');const [f,g]=await Promise.all([api('/applications/'+detail.id+'/cross-document-findings?run_id='+encodeURIComponent(detail.runId||'')),api('/applications/'+detail.id+'/evidence-graph?run_id='+encodeURIComponent(detail.runId||''))]);setData(f);setGraph(g.graph)}
  catch(e:any){setErr(e.message)}
 },[detail.id,detail.runId,api]);
 useEffect(()=>{load()},[load,detail.documents.length]);
 if(err)return <div role="alert" className="error">{err}</div>;
 if(!data)return <div className="card"><p className="muted">Loading stored evidence analysis…</p></div>;
 const claimNode=(id:string)=>graph?.nodes?.find((n:Obj)=>n.id===id);
 const versionOf=(cid:string)=>graph?.edges?.find((x:Obj)=>x.type==='EXTRACTED_FROM'&&x.source===cid)?.target;
 const docName=(cid:string)=>{const e=graph?.edges?.find((x:Obj)=>x.type==='EXTRACTED_FROM'&&x.source===cid);const d=graph?.nodes?.find((n:Obj)=>n.id===e?.target);return (d?.kind||'document').replace(/_/g,' ')};
 const groups:Record<string,Obj[]>={};(data.findings||[]).forEach((f:Obj)=>{(groups[groupOf(f)]=groups[groupOf(f)]||[]).push(f)});
 const involved=new Set<string>((data.findings||[]).flatMap((f:Obj)=>f.claim_ids));
 (graph?.edges||[]).filter((e:Obj)=>e.type==='CONTRADICTS').forEach((e:Obj)=>{involved.add(e.source);involved.add(e.target)});
 return <>
  <div className="card"><h2>Cross-document evidence</h2>
   <div className="notice">{data.disclaimer} {data.calibration_note}</div>
   <p className="muted">Status: {data.status} · pipeline {data.pipeline_version} · {Object.entries(data.stages||{}).map(([k,v])=>`${k}: ${v}`).join(' · ')}</p>
   <div className="actions"><button onClick={load} disabled={busy}>Refresh stored analysis</button></div></div>
  <div className="card"><h2>Evidence graph</h2><GraphView graph={graph||{}} claimIds={involved}/></div>
  {Object.keys(groups).length===0&&<div className="card"><p className="muted">No cross-document discrepancies, missing information or unresolved links were found among the claims extracted so far. Absence of findings is not verification: only extracted fields are compared.</p></div>}
  {Object.entries(groups).map(([title,list])=><div className="card" key={title}><h2>{title} <span className="pill">{list.length}</span></h2>
   {list.map((f:Obj)=><div className="finding" key={f.finding_id}>
    <div className="row between wrap"><span className="pill amber">{f.reviewed_status||LABEL[f.status]||f.status}</span><small className="metadata">{f.unit} · {f.method}</small></div>
    <p style={{marginTop:10}}>{f.explanation}</p>
    {f.claim_ids.length>0&&<div className="grid two">{f.claim_ids.map((id:string)=>{const c=claimNode(id);return c?<div className="notice" key={id}><b>{docName(id)}</b><br/>{c.field}: <code>{String(c.raw)}</code><br/>{versionOf(id)&&<a target="_blank" rel="noreferrer" href={'/api/v1/documents/'+encodeURIComponent(versionOf(id))+'/preview/'+c.page}>Open source page {c.page}</a>}<br/><small>page {c.page}{c.ocr_confidence!=null?` · OCR engine score ${Number(c.ocr_confidence).toFixed(0)} (not a probability)`:''}</small></div>:null})}</div>}
    <small>{f.calibrated_probability!=null?`Calibrated probability ${(f.calibrated_probability*100).toFixed(0)}% (synthetic-benchmark calibration)`:'No calibrated probability available.'}</small>
    {f.reviews?.length>0&&<div className="notice"><b>Reviewer history (original finding preserved)</b>{f.reviews.map((r:Obj,i:number)=><div key={i}><small>{r.status} — {r.reason} · {r.at}</small></div>)}</div>}
    {reviewer&&<div className="actions"><select aria-label="Review cross-document finding" value="" onChange={e=>{const action=e.target.value;if(!action)return;const reason=prompt('Record your review reason');if(reason)act(async()=>{await api('/applications/'+detail.id+'/cross-document-findings/review','POST',{run_id:data.run_id,finding_id:f.finding_id,status:action,reason});await load()})}}><option value="">Record review action…</option>{REVIEW_ACTIONS.map(s=><option key={s}>{s}</option>)}</select></div>}
   </div>)}</div>)}
 </>;
}
