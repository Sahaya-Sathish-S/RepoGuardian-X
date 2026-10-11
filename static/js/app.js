let allFindings=[], inventory=[];
const $=id=>document.getElementById(id);
function setMode(mode){
 $('mode').value=mode;
 document.querySelectorAll('.mode').forEach(b=>b.classList.toggle('active',b.dataset.mode===mode));
 $('uploadMode').classList.toggle('hidden',mode!=='upload');$('repoMode').classList.toggle('hidden',mode!=='repo');
}
$('projectFile').addEventListener('change',e=>{const f=e.target.files[0];$('filepicked').textContent=f?`Selected: ${f.name} · ${(f.size/1024/1024).toFixed(2)} MB`:'Choose a file'});
const dz=$('dropzone');
['dragenter','dragover'].forEach(ev=>dz.addEventListener(ev,e=>{e.preventDefault();dz.classList.add('drag')}));
['dragleave','drop'].forEach(ev=>dz.addEventListener(ev,e=>{e.preventDefault();dz.classList.remove('drag')}));
dz.addEventListener('drop',e=>{const f=e.dataTransfer.files[0];if(!f)return;const dt=new DataTransfer();dt.items.add(f);$('projectFile').files=dt.files;$('filepicked').textContent=`Selected: ${f.name} · ${(f.size/1024/1024).toFixed(2)} MB`});
$('scanForm').addEventListener('submit',async e=>{
 e.preventDefault();$('error').classList.add('hidden');$('dashboard').classList.add('hidden');
 const mode=$('mode').value;
 if(mode==='upload'&&!$('projectFile').files.length){showError('Choose a ZIP archive or source file first.');return}
 if(mode==='repo'&&!$('repoUrl').value.trim()){showError('Paste a public GitHub repository URL first.');return}
 $('loading').classList.remove('hidden');$('scanbtn').disabled=true;$('scanbtn').querySelector('span').textContent='Scanning…';
 const steps=[['Mapping the project universe…','Reading files and project structure'],['Inspecting code signals…','Checking common risk patterns and unfinished markers'],['Building risk constellation…','Grouping evidence by severity and language'],['Preparing repair roadmap…','Ranking findings for human review']];
 let step=0;$('loadingTitle').textContent=steps[0][0];$('loadingText').textContent=steps[0][1];$('loadpct').textContent='01 / 04';
 const ticker=setInterval(()=>{step=Math.min(step+1,3);$('loadingTitle').textContent=steps[step][0];$('loadingText').textContent=steps[step][1];$('loadpct').textContent=`0${step+1} / 04`},850);
 try{
  const form=new FormData($('scanForm'));const response=await fetch('/api/analyze',{method:'POST',body:form});const data=await response.json();
  if(!response.ok||data.error)throw new Error(data.error||'Analysis failed.');
  allFindings=data.findings||[];inventory=data.inventory||[];render(data);
  $('dashboard').classList.remove('hidden');$('dashboard').scrollIntoView({behavior:'smooth',block:'start'});
 }catch(err){showError(err.message||'Could not analyze the project.')}
 finally{clearInterval(ticker);$('loading').classList.add('hidden');$('scanbtn').disabled=false;$('scanbtn').querySelector('span').textContent='Run health scan'}
});
function showError(msg){$('error').textContent=msg;$('error').classList.remove('hidden');$('error').scrollIntoView({behavior:'smooth',block:'center'})}
function render(d){
 $('projectName').textContent=d.source||'Project Health Report';$('sourceName').textContent=(d.source||'PROJECT').toUpperCase();
 $('health').textContent='0';animateNumber($('health'),d.health,900);$('meter').style.width=d.health+'%';
 $('scoreLabel').textContent=d.health>=90?'Strong baseline':d.health>=75?'Some improvements recommended':d.health>=55?'Needs focused attention':'High-priority cleanup recommended';
 $('scoreBadge').textContent='RULE-BASED';$('files').textContent=d.files;$('lines').textContent=`${(d.lines||0).toLocaleString()} lines inspected`;
 $('count').textContent=allFindings.length;$('risk').textContent=d.counts?.HIGH||0;
 $('highCount').textContent=d.counts?.HIGH||0;$('medCount').textContent=d.counts?.MEDIUM||0;$('lowCount').textContent=d.counts?.LOW||0;$('donutTotal').textContent=allFindings.length;
 const high=d.counts?.HIGH||0,med=d.counts?.MEDIUM||0,low=d.counts?.LOW||0,total=Math.max(1,high+med+low);
 const deg1=high/total*360,deg2=(high+med)/total*360;
 $('donut').style.background=`conic-gradient(var(--red) 0deg ${deg1}deg,var(--yellow) ${deg1}deg ${deg2}deg,var(--green) ${deg2}deg 360deg)`;
 $('insight').textContent=high?`${high} high-risk signal${high===1?'':'s'} detected. Review those first; findings are pattern matches, not confirmed vulnerabilities.`:med?`No high-risk pattern matched. ${med} medium-risk signal${med===1?' needs':'s need'} review before release.`:'No high or medium rule matched. This is not proof of zero bugs—add tests and use dedicated scanners.';
 renderLanguages(d.languages||{});renderFindings(allFindings);renderHeatmap(inventory);renderRepair(allFindings);renderAgents(d.agents||[]);
}
function animateNumber(el,end,duration){let start=performance.now();function tick(now){let p=Math.min(1,(now-start)/duration);el.textContent=Math.round(end*(1-Math.pow(1-p,3)));if(p<1)requestAnimationFrame(tick)}requestAnimationFrame(tick)}
function renderLanguages(langs){const arr=Object.entries(langs).sort((a,b)=>b[1]-a[1]);const max=Math.max(1,...arr.map(x=>x[1]));$('languages').innerHTML=arr.length?arr.slice(0,8).map(([name,n])=>`<div class="langrow"><span class="langname" title="${esc(name)}">${esc(name)}</span><div class="langbar"><i style="width:${n/max*100}%"></i></div><span class="langnum">${n}</span></div>`).join(''):'<p class="note">No language metadata available.</p>'}
function renderFindings(arr){$('findings').innerHTML=arr.length?arr.map((f,i)=>`<article class="finding"><div class="findingtop"><span class="sev ${f.severity}">${esc(f.severity)}</span><h4>${esc(f.title)}</h4><span class="fileloc">${esc(f.file||'project')}${f.line?':'+f.line:''}</span></div><div class="findingbody"><p>${esc(f.agent||'Project Scanner')} · Review this signal and confirm it in context.</p><div class="evidence">${esc(f.evidence||'No evidence snippet available.')}</div><div class="fix"><b>↗ Recommended next step</b>${esc(f.fix||'Review this location and add a regression test if applicable.')}</div></div></article>`).join(''):'<div class="insight">No findings were generated for the supported rules. This does not guarantee the project is bug-free.</div>'}
function setFilter(type,btn){document.querySelectorAll('.filter').forEach(x=>x.classList.remove('active'));btn.classList.add('active');renderFindings(type==='ALL'?allFindings:allFindings.filter(f=>f.severity===type))}
function renderHeatmap(items){$('heatmap').innerHTML=items.length?items.map(f=>{let risk=(f.risk||'LOW').toLowerCase();return `<button class="tile ${risk}" title="${esc(f.path)} · ${f.lines} lines · ${risk} risk" onclick="focusFile('${encodeURIComponent(f.path)}')"><span class="tilepath">${esc(f.path)}</span><span class="tilemeta"><span>${esc(f.language)}</span><b>${f.lines} lines</b></span></button>`}).join(''):'<div class="insight">No file inventory available.</div>'}
function focusFile(path){const target=decodeURIComponent(path);const match=allFindings.find(f=>f.file===target);if(match){renderFindings(allFindings.filter(f=>f.file===target));document.querySelectorAll('.filter').forEach(x=>x.classList.remove('active'));toast(`Showing findings for ${target}. Use “All” to restore the complete list.`);$('findings').scrollIntoView({behavior:'smooth',block:'center'})}else{toast(`No rule-based finding recorded for ${target}. That does not mean the file has no defects.`)}}
function renderRepair(arr){const ordered=[...arr].sort((a,b)=>({HIGH:0,MEDIUM:1,LOW:2}[a.severity]??3)-({HIGH:0,MEDIUM:1,LOW:2}[b.severity]??3));$('repair').innerHTML=ordered.length?ordered.slice(0,8).map((f,i)=>`<div class="plan"><span class="planindex">0${i+1}</span><div><b>${esc(f.title)}</b><p>${esc(f.fix)}</p></div></div>`).join(''):'<p class="note">No repair actions suggested by the current rules.</p>'}
function renderAgents(agents){$('agents').innerHTML=agents.map(a=>`<div class="agent"><span>✳ &nbsp;${esc(a[0])}</span><span class="agentstate ${String(a[1]).includes('manual')||String(a[1]).includes('Approval')?'gated':''}">${esc(a[1])}</span></div>`).join('')}
function resetScan(){ $('dashboard').classList.add('hidden');$('error').classList.add('hidden');$('scanForm').reset();$('filepicked').textContent='Choose a file';setMode('upload');window.scrollTo({top:0,behavior:'smooth'})}
function toast(s){let t=$('toast');t.textContent=s;t.style.display='block';clearTimeout(window.toastTimer);window.toastTimer=setTimeout(()=>t.style.display='none',4000)}
function esc(s){return String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]))}

// Cloud integrations are opt-in and configured through server environment variables.
let supabaseClient=null, latestReport=null;
async function loadCloudConfig(){try{const r=await fetch('/api/config');const c=await r.json();if(c.supabase_url&&c.supabase_anon_key&&window.supabase){supabaseClient=window.supabase.createClient(c.supabase_url,c.supabase_anon_key);const {data}=await supabaseClient.auth.getSession();updateAuth(data?.session);supabaseClient.auth.onAuthStateChange((_event,session)=>updateAuth(session));}}catch(e){console.info('Cloud features not configured yet.')}}
function updateAuth(session){const b=$('authBtn');if(b)b.textContent=session?.user?.email?session.user.email.split('@')[0]+' · Sign out':'Sign in ↗';window.rgxSession=session||null;}
async function signInGoogle(){if(!supabaseClient){toast('Google sign-in needs SUPABASE_URL and SUPABASE_ANON_KEY in the deployment environment.');return}try{if(window.rgxSession){await supabaseClient.auth.signOut();toast('Signed out.');return}const {error}=await supabaseClient.auth.signInWithOAuth({provider:'google',options:{redirectTo:window.location.origin}});if(error)throw error;}catch(e){toast(e.message||'Could not start Google sign-in.')}}
async function startCheckout(plan){try{const r=await fetch('/api/checkout',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({plan})});const d=await r.json();if(!r.ok)throw new Error(d.error||'Checkout is not configured.');if(d.url)window.location.href=d.url;else toast(d.message||'Checkout setup required.')}catch(e){toast(e.message||'Checkout is not configured yet.')}}
async function explainWithAI(){if(!latestReport){toast('Run a project scan first.');return}const modal=$('aiModal');$('aiText').textContent='Reviewing scan signals…';modal.classList.remove('hidden');try{const r=await fetch('/api/ai/explain',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({source:latestReport.source,health:latestReport.health,counts:latestReport.counts,findings:(latestReport.findings||[]).slice(0,18).map(f=>({severity:f.severity,title:f.title,file:f.file,line:f.line,evidence:f.evidence,fix:f.fix}))})});const d=await r.json();if(!r.ok)throw new Error(d.error||'AI explanation unavailable.');$('aiText').textContent=d.explanation||'No explanation returned.';}catch(e){$('aiText').textContent=e.message||'AI explanation unavailable.'}}
function closeAIModal(){$('aiModal').classList.add('hidden')}
async function saveReportIfSignedIn(d){if(!supabaseClient||!window.rgxSession?.user)return;try{const {error}=await supabaseClient.from('scan_reports').insert({user_id:window.rgxSession.user.id,source_name:String(d.source||'Project').slice(0,180),health_score:d.health,files_count:d.files,lines_count:d.lines,findings_count:(d.findings||[]).length,high_count:d.counts?.HIGH||0,report_json:d});if(error)console.warn('Report history not saved:',error.message);else toast('Scan saved to your cloud history.')}catch(e){console.warn(e)}}
const originalRender=render;render=function(d){latestReport=d;originalRender(d);saveReportIfSignedIn(d)};
$('aiModal')?.addEventListener('click',e=>{if(e.target===$('aiModal'))closeAIModal()});
loadCloudConfig();
