import {test,expect,Page} from '@playwright/test';
async function login(page:Page,role:string){
 await page.goto('/');
 const out=page.getByRole('button',{name:'Sign out',exact:true});
 await expect(out.or(page.getByRole('button',{name:'Sign in →',exact:true}))).toBeVisible();
 if(await out.isVisible())await out.click();
 else await page.getByRole('button',{name:'Sign in →',exact:true}).click();
 await page.getByLabel('Email address').fill(role+'@demo.local');
 await page.getByLabel('Password',{exact:true}).fill('DemoOnly!2026');
 await page.getByRole('button',{name:'Sign in',exact:true}).click();
 await expect(page.getByRole('heading',{name:role==='reviewer'?'Make every review count.':'Application overview'})).toBeVisible();
 if(role==='reviewer')await page.screenshot({path:'test-results/reviewer-desktop.png',fullPage:true});
}
async function api(page:Page,path:string,method='GET',data?:any){
 const me=await page.request.get('/api/v1/auth/me');const {csrf}=await me.json();
 const r=await page.request.fetch('/api/v1'+path,{method,headers:{'X-CSRF-Token':csrf},data});
 expect(r.ok(),await r.text()).toBeTruthy();return r.json();
}
function pdf(expiry:string){
 const lines=['SYNTHETIC DEMONSTRATION MATERIAL','Institution Name: Synthetic Institute of Technology','Institution Identifier: SYN-001','Reference Number: CERT-001','Issue Date: 2024-01-01',`Expiry Date: ${expiry}`,'Intake: 60'];
 const stream='BT /F1 12 Tf 40 750 Td '+lines.map((l,i)=>(i?'0 -24 Td ':'')+`(${l}) Tj`).join('\n')+' ET';
 const objs=['<< /Type /Catalog /Pages 2 0 R >>','<< /Type /Pages /Kids [3 0 R] /Count 1 >>','<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>','<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>',`<< /Length ${stream.length} >>\nstream\n${stream}\nendstream`];
 let s='%PDF-1.4\n';const offsets=[0];objs.forEach((o,i)=>{offsets.push(Buffer.byteLength(s));s+=`${i+1} 0 obj\n${o}\nendobj\n`});const start=Buffer.byteLength(s);s+='xref\n0 6\n0000000000 65535 f \n'+offsets.slice(1).map(x=>String(x).padStart(10,'0')+' 00000 n \n').join('')+`trailer\n<< /Root 1 0 R /Size 6 >>\nstartxref\n${start}\n%%EOF`;
 return Buffer.from(s);
}
test('applicant upload → worker → reviewer clarification → replacement → report',async({page})=>{
 await login(page,'applicant');
 const title='Browser workflow '+Date.now();
 await page.getByRole('button',{name:'＋ Create application'}).click();
 await page.getByLabel('Application title').fill(title);
 await page.getByRole('button',{name:'Continue',exact:true}).click();
 await page.getByRole('button',{name:'Continue',exact:true}).click();
 await page.getByLabel('Programme name').fill('Synthetic Engineering');
 await page.getByRole('button',{name:'Save draft & continue'}).click();
 await page.getByLabel('PDF, PNG or JPEG').setInputFiles({name:'arbitrary-filename.pdf',mimeType:'application/pdf',buffer:pdf('2025-01-01')});
 await page.getByRole('button',{name:'Upload evidence'}).click();
 await expect(page.getByText('✓ arbitrary-filename.pdf · version 1')).toBeVisible();
 await page.getByRole('button',{name:'Save draft & continue'}).click();
 await page.getByRole('button',{name:'Submit application',exact:true}).click();
 await expect(page.getByRole('heading',{name:title,exact:true})).toBeVisible();
 const list=await api(page,'/applications');const aid=list.items.find((x:any)=>x.title===title).id;
 await expect.poll(async()=>{const w=await api(page,'/applications/'+aid);return w.runs[0]?.status},{timeout:60000}).toBe('Completed');
 await login(page,'admin');
 const users=await api(page,'/admin/users');const reviewer=users.find((u:any)=>u.role==='reviewer');await api(page,'/admin/assignments','POST',{application_id:aid,user_id:reviewer.id});
 await login(page,'reviewer');
 await page.getByRole('row').filter({hasText:title}).getByRole('button',{name:'Open →'}).click();
 page.once('dialog',d=>d.accept('Begin preliminary review'));await page.getByRole('button',{name:'Start review'}).click();
 await page.getByRole('tab',{name:'Validation Findings',exact:true}).click();
 const finding=page.locator('.finding').filter({hasText:'Certificate reference-date validity'});
 await finding.getByRole('button',{name:'Certificate reference-date validity ↗',exact:true}).click();
 await expect(page.getByAltText('Source document page 1')).toBeVisible();
 await page.screenshot({path:'test-results/evidence-review.png',fullPage:true});
 await expect(finding.getByText('Failed',{exact:true})).toBeVisible();
 page.once('dialog',d=>d.accept('Please provide an updated certificate.'));await finding.getByRole('button',{name:'Request clarification'}).click();
 await expect(page.getByRole('heading',{name:'Please provide an updated certificate.'})).toBeVisible();
 await login(page,'applicant');await page.getByRole('row').filter({hasText:title}).getByRole('button',{name:'Open →'}).click();
 await page.getByRole('tab',{name:'Clarifications',exact:true}).click();await page.getByLabel('Your reply').fill('Updated certificate supplied.');await page.getByRole('button',{name:'Send reply'}).click();
 await expect(page.locator('.notice').filter({hasText:'Updated certificate supplied.'})).toBeVisible();
 await page.getByRole('tab',{name:'Documents',exact:true}).click();
 await page.getByLabel('Replace an existing document').selectOption({index:1});
 await page.getByLabel('PDF, PNG or JPEG').setInputFiles({name:'updated.pdf',mimeType:'application/pdf',buffer:pdf('2027-12-31')});await page.getByRole('button',{name:'Upload evidence'}).click();
 await expect(page.getByText('Superseded',{exact:true})).toBeVisible();
 page.once('dialog',d=>d.accept('Replacement evidence supplied'));await page.getByRole('button',{name:'Resubmit',exact:true}).click();
 await expect.poll(async()=>{const w=await api(page,'/applications/'+aid);return [w.runs.length,w.runs[0]?.status].join(':')},{timeout:60000}).toBe('2:Completed');
 await login(page,'reviewer');await page.getByRole('row').filter({hasText:title}).getByRole('button',{name:'Open →'}).click();
 page.once('dialog',d=>d.accept('Review replacement evidence'));await page.getByRole('button',{name:'Start review'}).click();
 await page.getByRole('tab',{name:'Validation Findings',exact:true}).click();
 await expect(page.locator('.finding').filter({hasText:'Certificate reference-date validity'}).getByText('Passed',{exact:true})).toBeVisible();
 await page.getByRole('tab',{name:'Revision Comparison',exact:true}).click();
 await expect(page.getByRole('row').filter({hasText:'Certificate reference-date validity'}).getByText('Improved',{exact:true})).toBeVisible();
 await page.screenshot({path:'test-results/revision-comparison.png',fullPage:true});
 page.once('dialog',d=>d.accept('Preliminary review recorded; no statutory approval issued'));await page.getByRole('button',{name:'Complete preliminary review'}).click();
 await page.getByRole('tab',{name:'Reports',exact:true}).click();
 const report=await page.request.get('/api/v1/applications/'+aid+'/report');expect(report.status()).toBe(200);expect((await report.body()).subarray(0,4).toString()).toBe('%PDF');
 await expect(page.getByText('Preliminary Review Completed',{exact:true})).toBeVisible();
});
test('responsive dashboard, source inspection, logout protection',async({page})=>{
 await login(page,'applicant');await page.setViewportSize({width:390,height:844});
 await expect(page.getByRole('heading',{name:'Application overview'})).toBeVisible();
 await page.screenshot({path:'test-results/applicant-mobile.png',fullPage:true});
 await page.getByRole('row').filter({hasText:'01 · Consistent submission'}).getByRole('button',{name:'Open →'}).click();
 await page.getByRole('tab',{name:'Extracted Fields',exact:true}).click();
 await page.getByLabel('Document version').selectOption({index:2});
 await expect(page.getByAltText('Source document page 1')).toBeVisible();
 await page.getByRole('button',{name:'Sign out'}).click();expect((await page.request.get('/api/v1/applications')).status()).toBe(401);
});
