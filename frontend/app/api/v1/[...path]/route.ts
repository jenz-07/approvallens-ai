import {NextRequest} from 'next/server';
export const dynamic='force-dynamic';
async function proxy(req:NextRequest,context:{params:Promise<{path:string[]}>}){
 const {path}=await context.params;
 if(path.some(p=>!p||p==='.'||p==='..'))return Response.json({error:{message:'Invalid path'}},{status:400});
 const target=(process.env.API_INTERNAL_URL||'http://127.0.0.1:8000')+'/api/v1/'+path.map(encodeURIComponent).join('/')+req.nextUrl.search;
 const headers=new Headers(req.headers);for(const h of ['host','connection','transfer-encoding','content-length'])headers.delete(h);
 try{
  const init:RequestInit & {duplex?:string}={method:req.method,headers,redirect:'manual',cache:'no-store'};
  if(!['GET','HEAD'].includes(req.method)){init.body=req.body;init.duplex='half'}
  const upstream=await fetch(target,init);const out=new Headers(upstream.headers);
  for(const h of ['content-encoding','content-length','transfer-encoding','connection'])out.delete(h);
  return new Response(upstream.body,{status:upstream.status,headers:out});
 }catch{return Response.json({error:{message:'Backend unavailable. Start the API service and retry.'}},{status:503})}
}
export {proxy as GET,proxy as POST,proxy as PUT,proxy as PATCH};
