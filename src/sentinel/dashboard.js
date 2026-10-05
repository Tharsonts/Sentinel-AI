'use strict';
const $=id=>document.getElementById(id),names={zone_enter:'Presença na área',zone_dwell:'Permaneceu na área',zone_exit:'Saiu da área',track_lost:'Acompanhamento interrompido',presence_ended:'Acompanhamento encerrado'},objects={person:'Pessoa',car:'Carro',motorcycle:'Moto',bicycle:'Bicicleta',bus:'Ônibus',truck:'Caminhão'};
let key=localStorage.getItem('sentinel-key')||sessionStorage.getItem('sentinel-key')||'',connected=false,state={},busy=false,page=0,snapshot=null,videoUrl=null,evidenceUrl=null,lastFrame=null,searchBusy=false;$('key').value=key;$('searchQuery').value='';
let draftZones=[],areaIndex=0,referenceImage=null,referenceUrl=null,dragStart=null,thumbnailUrls=[],renderVersion=0;
const cameraNames={NOTEBOOK_01:'Webcam do notebook',DEMO_SYNTHETIC:'Demonstração sintética',GPU_DEMO:'Teste técnico anterior',PUSH_GPU_TEST:'Teste de transmissão anterior',VIDEO_PEDESTRES:'Teste · Pedestres',VIDEO_CORREDOR:'Teste · Corredor',VIDEO_PATIO:'Teste · Pátio',VIDEO_VEICULOS:'Teste · Vista aérea',VIDEO_TRANSITO:'Teste · Trânsito',VIDEO_CAMERA_720P:'Teste · Câmera 720p'};
function cameraName(id){return cameraNames[id]||id||'Todas as câmeras';}
function areaName(id){return draftZones.find(z=>z.id===id)?.name||id;}
function message(text){$('message').textContent=text;}
function view(name){localStorage.setItem('sentinel-view',name);for(const e of document.querySelectorAll('[id^="view-"]'))e.hidden=e.id!=='view-'+name;for(const b of document.querySelectorAll('[data-view]'))b.setAttribute('aria-pressed',String(b.dataset.view===name));}
for(const b of document.querySelectorAll('[data-view]'))b.onclick=()=>view(b.dataset.view);
async function api(path,options={}){if(!connected&&path!=='/status')throw Error('Conecte ao servidor primeiro.');const headers={...options.headers,'X-API-Key':key};if(options.body&&!(options.body instanceof FormData))headers['Content-Type']='application/json';const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),path==='/chat'?190000:path==='/media'?120000:15000);try{const r=await fetch(path,{...options,headers,signal:controller.signal});if(!r.ok){let detail;try{detail=(await r.json()).detail;}catch{detail=r.statusText;}if(r.status===401){localStorage.removeItem('sentinel-key');sessionStorage.removeItem('sentinel-key');connected=false;$('login').hidden=false;$('connection').textContent='Verifique a chave de acesso';}throw Error(typeof detail==='string'?detail:JSON.stringify(detail));}return r;}catch(e){if(e.name==='AbortError')throw Error('O servidor demorou a responder. Tente novamente; seus filtros foram mantidos.');throw e;}finally{clearTimeout(timer);}}
async function json(path,options={}){return(await api(path,options)).json();}async function guard(action){try{message('');await action();}catch(e){message(e.message);}}
function localInput(date){return new Date(date.getTime()-date.getTimezoneOffset()*60000).toISOString().slice(0,16);}function setDay(){const start=new Date($('day').value+'T00:00:00'),end=new Date(start);end.setDate(end.getDate()+1);$('since').value=localInput(start);$('until').value=localInput(end);}$('day').value=localInput(new Date()).slice(0,10);setDay();$('day').onchange=setDay;$('timezone').textContent='Horários no fuso deste navegador: '+Intl.DateTimeFormat().resolvedOptions().timeZone+'.';
function filters(){const start=new Date($('since').value),end=new Date($('until').value);if(!Number.isFinite(start.getTime())||!Number.isFinite(end.getTime())||start>=end)throw Error('Escolha um intervalo válido.');return{since:start.toISOString(),until:end.toISOString(),camera:$('filterCamera').value||null,session_id:$('filterSession').value||null,zone:$('filterZone').value||null,event_type:$('filterKind').value||null,object_type:$('filterObject').value||null,min_duration:Number($('duration').value),query:$('searchQuery').value.trim(),limit:24,offset:0};}
for(const b of document.querySelectorAll('[data-query]'))b.onclick=()=>{$('searchQuery').value=b.dataset.query;$('filterKind').value='';$('filterObject').value='';};
function options(id,values,label){const e=$(id),selected=e.value;e.replaceChildren(new Option(label,''),...values.map(v=>new Option(id==='filterCamera'?cameraName(v):id==='filterZone'?areaName(v):v,v)));if(values.includes(selected))e.value=selected;}
let sessionCatalog=[],sessionChosen=false;
async function catalog(){const data=await json('/search/catalog');options('filterCamera',data.camera,'Todas as câmeras');options('filterZone',data.zone,'Todas as zonas');if(state.camera&&data.camera.includes(state.camera)&&!$('filterCamera').value)$('filterCamera').value=state.camera;sessionCatalog=data.sessions||[];reloadSessions();reloadVisualSessions();}
function paragraph(text,cls=''){const e=document.createElement('p');e.textContent=text;if(cls)e.className=cls;return e;}function label(e){if(e.metadata?.reason==='zones_changed')return 'Área reconfigurada';return(objects[e.object_type]||e.object_type)+' · '+(names[e.event_type]||e.event_type);}
function render(r){
  for(const url of thumbnailUrls)URL.revokeObjectURL(url);thumbnailUrls=[];const version=++renderVersion;
  $('results').replaceChildren();$('count').textContent=r.total+' acontecimentos encontrados'+(r.total?' · mostrando '+(r.offset+1)+'–'+(r.offset+r.items.length):'');
  $('previous').disabled=r.offset===0;$('next').disabled=!r.has_more;
  const f=r.filters;$('applied').textContent=cameraName(f.camera)+' · '+(f.zone?areaName(f.zone):'todas as áreas')+' · '+(names[f.event_type]||'todos os acontecimentos')+' · '+(objects[f.object_type]||'todos os objetos')+' · duração registrada ≥ '+f.min_duration+' s · '+new Date(f.since).toLocaleString()+' até '+new Date(f.until).toLocaleString();
  if(!r.items.length){const box=document.createElement('div');box.className='empty';box.append(paragraph('Nenhum registro neste recorte.','empty-title'),paragraph('Experimente outro dia, outra câmera ou a opção Tudo. Confira também se a câmera recebeu imagens.'));$('results').append(box);return;}
  for(const e of r.items){
    const row=document.createElement('button');row.type='button';row.className='event-row';row.dataset.eventId=e.id;row.setAttribute('aria-label','Ver registro: '+label(e)+' às '+new Date(e.timestamp).toLocaleTimeString());
    const clock=document.createElement('time');clock.textContent=new Date(e.timestamp).toLocaleTimeString([], {hour:'2-digit',minute:'2-digit',second:'2-digit'});row.append(clock);
    const marker=document.createElement('span');marker.className='event-marker '+e.event_type;marker.setAttribute('aria-hidden','true');row.append(marker);
    const content=document.createElement('span');content.className='event-content';const title=document.createElement('strong');title.textContent=label(e);content.append(title,paragraph(cameraName(e.camera)+' · '+(areaName(e.zone)||'Sem área')));row.append(content);
    const tail=document.createElement('span');tail.className='event-tail';tail.textContent=e.duration>0?e.duration+' s':e.evidence_available?'↗':'Sem imagem';row.append(tail);
    row.onclick=()=>guard(()=>showEvidence(e,true));$('results').append(row);
  }
  guard(()=>showEvidence(r.items.find(e=>e.evidence_available)||r.items[0],false));

}
let pendingSearch=false;
async function runSearch(reset=true){if(searchBusy){if(reset)pendingSearch=true;return;}searchBusy=true;$('search').disabled=true;$('count').textContent='Procurando os registros…';try{if(reset){++evidenceVersion;page=0;snapshot=filters();$('selection').hidden=true;if(evidenceUrl){URL.revokeObjectURL(evidenceUrl);evidenceUrl=null;}}render(await json('/search',{method:'POST',body:JSON.stringify({...snapshot,offset:page*24})}));}catch(e){$('count').textContent='Busca não concluída. Seus filtros foram mantidos.';throw e;}finally{searchBusy=false;$('search').disabled=false;if(pendingSearch){pendingSearch=false;queueMicrotask(()=>guard(()=>runSearch(true)));}}}
$('searchForm').onsubmit=e=>{e.preventDefault();guard(()=>runSearch());};$('previous').onclick=()=>guard(async()=>{page=Math.max(0,page-1);await runSearch(false);});$('next').onclick=()=>guard(async()=>{page++;await runSearch(false);});
let evidenceVersion=0;
async function showEvidence(e,scroll=true){const current=++evidenceVersion;for(const row of document.querySelectorAll(".event-row"))row.setAttribute("aria-pressed",String(row.dataset.eventId===e.id));$('selection').hidden=false;$('selectedTitle').textContent=label(e);$('selectedInfo').textContent=new Date(e.timestamp).toLocaleString()+' · '+cameraName(e.camera)+' · '+areaName(e.zone);$('selectedTechnical').textContent='Evento: '+e.id+' · sessão: '+e.session_id+' · objeto #'+e.track_id+' · confiança '+Math.round(e.confidence*100)+'% · estado '+e.status;$('selectedImage').hidden=true;if(evidenceUrl)URL.revokeObjectURL(evidenceUrl);selectedReviewEvent=e;reviewOpenedAt=performance.now();$('reviewState').textContent='Carregando conferência…';$('reviewNote').value='';$('reviewVerdict').value='uncertain';guard(()=>loadReview(e,current));$('selectedNote').textContent=e.evidence_available?'Carregando imagem…':'Não há imagem registrada para este evento. Não reconstruímos evidências antigas; perda de tracking e fim da fonte não recebem uma imagem nova.';if(e.evidence_available){const blob=await(await api('/events/'+encodeURIComponent(e.id)+'/evidence')).blob();if(current!==evidenceVersion)return;evidenceUrl=URL.createObjectURL(blob);$('selectedImage').src=evidenceUrl;$('selectedImage').hidden=false;$('selectedNote').textContent='Imagem anotada capturada em '+new Date(e.evidence_captured_at).toLocaleString()+'. Não é um trecho de vídeo.';}if(scroll)view('search');if(scroll&&window.innerWidth<900)$('selection').scrollIntoView({behavior:'smooth',block:'nearest'});}
async function ask(useLlm){$('chat').disabled=true;$('summary').disabled=true;$('answer').textContent='Consultando os registros selecionados…';try{const r=await json('/chat',{method:'POST',body:JSON.stringify({...filters(),question:$('question').value.trim()||'Resuma os acontecimentos, cite os IDs usados e explique as limitações.',use_llm:useLlm})});await presentAnswer((useLlm?r.answer:readableSummary(r.context))+'\n\n'+r.context.total+' registros consultados'+(r.llm_seconds?' · resposta em '+r.llm_seconds+' s':''),useLlm);}catch(e){$('answer').textContent='Consulta não concluída. Tente o resumo sem IA.';throw e;}finally{$('chat').disabled=false;$('summary').disabled=false;}}
$('chat').onclick=()=>guard(()=>ask(true));$('summary').onclick=()=>guard(()=>ask(false));$('report').onclick=()=>guard(async()=>{const r=await api('/search/report',{method:'POST',body:JSON.stringify(filters())}),url=URL.createObjectURL(await r.blob()),link=document.createElement('a');link.href=url;link.download='sentinel-busca.txt';link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);});
async function refresh(){if(!connected||busy)return;busy=true;try{state=await json('/status');const statusName={idle:'nenhuma câmera iniciada',starting:'preparando câmera',stopped:'câmera parada',stopping:'encerrando câmera',error:'falha de processamento'};$('connection').textContent=state.receiving?'● '+cameraName(state.camera)+' · recebendo imagens':'● Servidor conectado · '+(statusName[state.status]||'aguardando imagens');$('liveState').textContent=(state.receiving?'Recebendo imagens':state.status==='running'?'Aguardando imagens':(statusName[state.status]||'Aguardando imagens'))+' · '+cameraName(state.camera)+' · '+state.frames+' imagens'+(state.last_frame_age_seconds!=null?' · última há '+Math.floor(state.last_frame_age_seconds)+' s':'')+(state.error?' · '+state.error:'');updateSourceAction();renderObservations();$('stop').disabled=!['running','starting','stopping'].includes(state.status);$('video').style.opacity=state.receiving?'1':'.45';if(!state.frames){$('video').hidden=true;$('placeholder').hidden=false;lastFrame=null;}updatePreviewMode();const rows=await json('/events?limit=15'+(state.camera?'&camera='+encodeURIComponent(state.camera):''));$('timeline').replaceChildren();for(const e of rows){const b=document.createElement('button');b.textContent=new Date(e.timestamp).toLocaleTimeString()+' · '+label(e)+' · '+e.zone;b.onclick=()=>guard(async()=>{const found=await json('/search',{method:'POST',body:JSON.stringify({since:e.timestamp,until:new Date(new Date(e.timestamp).getTime()+1).toISOString(),camera:e.camera,limit:100})});await showEvidence(found.items.find(i=>i.id===e.id)||{...e,evidence_available:false});});$('timeline').append(b);}if(!rows.length)$('timeline').append(paragraph('Ainda não há eventos desta câmera.','hint'));}catch(e){$('liveState').textContent='Servidor sem resposta';$('connection').textContent='○ Sem resposta do servidor — tentando novamente';$('video').style.opacity='.45';message(e.message);}finally{busy=false;}}
async function diagnostics(){const m=await json('/metrics');$('metrics').textContent='CPU: '+m.cpu_percent+'% · RAM: '+m.ram_percent+'%\nGPU: '+(m.gpu.join(' | ')||'Sem dados')+'\nÚltima imagem: '+m.pipeline.inference_ms+' ms\nCapacidade instantânea: '+m.pipeline.fps+' FPS (não é a taxa de envio).';const l=await json('/llm/status');$('llm').textContent='IA local: '+l.status+' · '+l.model;}
async function connect(){key=$('key').value.trim();await json('/status');connected=true;localStorage.setItem('sentinel-key',key);sessionStorage.setItem('sentinel-key',key);$('login').hidden=true;await refresh();await reloadZones();await catalog();await reloadMedia();await diagnostics();await runSearch();}$('connect').onclick=()=>guard(connect);
async function reloadZones(){draftZones=await json('/zones');$('zones').value=JSON.stringify(draftZones,null,2);areaIndex=0;loadAreaForm();}$('reloadZones').onclick=()=>guard(reloadZones);$('demoZone').onclick=()=>{$('zones').value=JSON.stringify([{id:'demo',name:'Demonstracao',polygon:[[0,0],[1,0],[1,1],[0,1]],dwell_seconds:10,classes:['person','car','motorcycle','bicycle','bus','truck']}],null,2);message('Zona preparada, ainda não salva. Pare o processamento e clique em Salvar zonas.');};$('saveZones').onclick=()=>guard(async()=>{await json('/zones',{method:'PUT',body:JSON.stringify(JSON.parse($('zones').value))});message('Zonas salvas. Inicie o processamento para aplicar.');await catalog();});
$('kind').onchange=()=>{$('source').disabled=$('kind').value==='push';$('source').value=$('kind').value==='webcam'?'0':'';if($('kind').value==='push')$('camera').value='NOTEBOOK_01';};$('media').onchange=()=>{$('kind').value='file';$('source').disabled=false;$('source').value=$('media').value;};$('start').onclick=()=>guard(async()=>{const current=await json('/status');if(['starting','stopping'].includes(current.status))throw Error('Aguarde a troca da câmera.');if(current.status==='running'){if($('kind').value!=='file'||!$('source').value)throw Error('Pare a fonte atual antes de iniciar outra.');await json('/cameras/stop',{method:'POST'});}await json('/cameras/start',{method:'POST',body:JSON.stringify({kind:$('kind').value,source:$('source').value,camera:$('camera').value})});followActive=true;++visualAnimation;visualCurrent='';visualRendered='';$('visualAnswer').replaceChildren();$('visualEvidence').replaceChildren();$('visualSelected').hidden=true;$('visualState').textContent='Preparando imagens desta execução…';$('sourceSetup').open=false;view('live');$('previewMode').value=$('kind').value==='file'?'original':'processed';message($('kind').value==='file'?'Vídeo em análise. Ao terminar, os registros ficam em Pesquisar.':'Fonte iniciada. Acompanhe as imagens em Ao vivo.');await refresh();await catalog();});$('stop').onclick=()=>guard(async()=>{await json('/cameras/stop',{method:'POST'});await refresh();message('Processamento parado.');});$('upload').onclick=()=>guard(async()=>{if(!$('file').files.length)throw Error('Selecione um vídeo.');const file=$('file').files[0],data=new FormData();data.append('file',file);$('upload').disabled=true;$('upload').textContent='Enviando…';try{const r=await json('/media',{method:'POST',body:data});$('kind').value='file';$('source').disabled=false;$('source').value=r.filename;await reloadMedia();$('media').value=r.filename;sourceHelp();await refresh();message(file.name+' enviado. Iniciando acompanhamento…');$('start').click();}finally{$('upload').disabled=false;$('upload').textContent='Enviar e acompanhar';}});
setInterval(refresh,1500);setInterval(()=>{if(connected&&$('sourceSetup').open)guard(diagnostics);},5000);if(key)guard(connect);

function readableSummary(ctx){
  if(!ctx.total)return 'Nenhum acontecimento registrado para esta seleção. Isso não comprova ausência de atividade.';
  const lines=['Resumo de '+cameraName(ctx.camera)+' · '+ctx.total+' registros no período.'];
  for(const row of ctx.counts)lines.push((names[row.event_type]||row.event_type)+' · '+(objects[row.object_type]||row.object_type)+': '+row.count);
  lines.push('');for(const e of ctx.events.slice(-8))lines.push(new Date(e.timestamp).toLocaleTimeString()+' — '+label(e)+' · '+areaName(e.zone));
  if(ctx.total>8)lines.push('Mostrando os oito registros mais recentes. Abra os registros ou baixe o relatório para revisar os demais.');
  lines.push('Perda de acompanhamento não confirma saída.');return lines.join('\n');
}
$('switchKey').onclick=()=>{$('login').hidden=!$('login').hidden;};
for(const [id,delta] of [['today',0],['yesterday',-1]])$(id).onclick=()=>guard(async()=>{const date=new Date();date.setDate(date.getDate()+delta);$('day').value=localInput(date).slice(0,10);setDay();sessionChosen=false;reloadSessions();if(connected)await runSearch();});
for(const b of document.querySelectorAll('[data-query]'))b.onclick=()=>guard(async()=>{for(const other of document.querySelectorAll('[data-query]'))other.setAttribute('aria-pressed',String(other===b));$('searchQuery').value=b.dataset.query;$('filterKind').value='';$('filterObject').value='';if(connected)await runSearch();});
let filterTimer=null;
for(const id of ['day','filterCamera'])$(id).addEventListener('change',()=>{clearTimeout(filterTimer);if(connected)filterTimer=setTimeout(()=>guard(()=>runSearch()),180);});
function loadAreaForm(){
  $('areaSelect').replaceChildren(...draftZones.map((z,i)=>new Option(z.name,String(i))));areaIndex=Math.min(areaIndex,Math.max(0,draftZones.length-1));$('areaSelect').value=String(areaIndex);
  const zone=draftZones[areaIndex];$('areaName').value=zone?.name||'';$('areaDwell').value=zone?.dwell_seconds||10;$('areaState').textContent=zone?'Arraste para ajustar '+zone.name+'. As mudanças só valem após Aplicar área.':'Adicione uma área para começar.';drawArea();
}
function drawArea(){const canvas=$('zoneCanvas'),ctx=canvas.getContext('2d');ctx.clearRect(0,0,canvas.width,canvas.height);ctx.fillStyle='#0a1321';ctx.fillRect(0,0,canvas.width,canvas.height);if(referenceImage)ctx.drawImage(referenceImage,0,0,canvas.width,canvas.height);const points=draftZones[areaIndex]?.polygon;if(points?.length){ctx.beginPath();points.forEach(([x,y],i)=>{if(i)ctx.lineTo(x*canvas.width,y*canvas.height);else ctx.moveTo(x*canvas.width,y*canvas.height);});ctx.closePath();ctx.fillStyle='rgba(157,232,211,.16)';ctx.fill();ctx.lineWidth=3;ctx.strokeStyle='#9de8d3';ctx.stroke();}if(!referenceImage){ctx.fillStyle='#a1aec1';ctx.font='18px Segoe UI';ctx.fillText('Carregue uma imagem da câmera para desenhar a área.',20,40);}}
async function loadReference(){const blob=await(await api('/frame')).blob();if(referenceUrl)URL.revokeObjectURL(referenceUrl);referenceUrl=URL.createObjectURL(blob);const image=new Image();image.src=referenceUrl;await image.decode();referenceImage=image;$('zoneCanvas').height=Math.round(800*image.naturalHeight/image.naturalWidth);drawArea();$('areaState').textContent='Imagem carregada. Arraste um retângulo para definir a área.';}
function point(event){const rect=$('zoneCanvas').getBoundingClientRect();return[Math.min(1,Math.max(0,(event.clientX-rect.left)/rect.width)),Math.min(1,Math.max(0,(event.clientY-rect.top)/rect.height))];}
$('zoneCanvas').onpointerdown=event=>{if(!referenceImage||!draftZones[areaIndex]){message('Carregue uma imagem e selecione uma área antes de desenhar.');return;}dragStart=point(event);$('zoneCanvas').setPointerCapture(event.pointerId);};
$('zoneCanvas').onpointermove=event=>{if(!dragStart)return;const end=point(event),[x,y]=dragStart;draftZones[areaIndex].polygon=[[Math.min(x,end[0]),Math.min(y,end[1])],[Math.max(x,end[0]),Math.min(y,end[1])],[Math.max(x,end[0]),Math.max(y,end[1])],[Math.min(x,end[0]),Math.max(y,end[1])]];drawArea();};
$('zoneCanvas').onpointerup=()=>{if(dragStart){dragStart=null;$('areaState').textContent='Área desenhada. Clique em Aplicar área para salvar.';}};
$('zoneCanvas').onpointercancel=()=>{dragStart=null;};
$('areaSelect').onchange=()=>{areaIndex=Number($('areaSelect').value);loadAreaForm();};
$('loadReference').onclick=()=>guard(loadReference);
$('addArea').onclick=()=>{draftZones.push({id:'area_'+Date.now().toString(36),name:'Nova área',polygon:[[.2,.2],[.8,.2],[.8,.8],[.2,.8]],dwell_seconds:10,classes:['person','car','motorcycle','bicycle','bus','truck']});areaIndex=draftZones.length-1;loadAreaForm();};
$('wholeArea').onclick=()=>{if(!draftZones.length)$('addArea').click();draftZones[areaIndex].polygon=[[0,0],[1,0],[1,1],[0,1]];drawArea();$('areaState').textContent='Imagem inteira selecionada. Clique em Aplicar área.';};
$('applyArea').onclick=()=>guard(async()=>{
  const zone=draftZones[areaIndex];if(!zone)throw Error('Adicione uma área primeiro.');const name=$('areaName').value.trim(),dwell=Number($('areaDwell').value);
  if(!name||!Number.isFinite(dwell)||dwell<.1||dwell>86400)throw Error('Informe o nome da área e um tempo entre 0,1 e 86400 segundos.');
  zone.name=name;zone.dwell_seconds=dwell;const response=await json('/zones/apply',{method:'POST',body:JSON.stringify(draftZones)});draftZones=response.zones;$('zones').value=JSON.stringify(draftZones,null,2);loadAreaForm();await catalog();message('Área aplicada.'+(response.processing_preserved?' A câmera continuou funcionando; novas permanências serão contadas a partir desta mudança.':''));$('areaState').textContent='Área salva e pronta para acompanhar novos acontecimentos.';
});

function sourceHelp(){$('connectNotebook').hidden=$('kind').value!=='push';$('notebookHelp').hidden=$('kind').value!=='push';const help={file:'Escolha um vídeo disponível abaixo ou envie um arquivo. Ele será analisado na cadência original.',push:'O cliente do notebook transmite automaticamente. Este painel prepara o recebimento no PC.',rtsp:'Informe o endereço RTSP fornecido pela câmera ou pelo gravador. A análise acontece neste PC.',webcam:'Use o índice da webcam conectada ao PC (geralmente 0).'};$('source').parentElement.hidden=['file','push'].includes($('kind').value);$('mediaSection').hidden=$('kind').value!=='file';$('cameraSaveSection').hidden=$('kind').value==='file';$('sourceHelp').textContent=help[$('kind').value];updateSourceAction();}
$('kind').addEventListener('change',sourceHelp);$('media').addEventListener('change',sourceHelp);sourceHelp();

if(location.port==='18002')document.querySelector('.rail-note').prepend(paragraph('AMBIENTE DE TESTES','demo-label'));

$('key').addEventListener('keydown',event=>{if(event.key==='Enter'){event.preventDefault();$('connect').click();}});
if(location.port==='18002')document.querySelector('#login small').textContent='Demonstração local · porta 18002. Acesso lembrado neste navegador para testes. Pressione Enter ou clique em Conectar.';

const savedView=localStorage.getItem('sentinel-view');view(['search','live'].includes(savedView)?savedView:'live');

var sourceSyncDone=false;
function updateSourceAction(){if(!sourceSyncDone&&state.kind){sourceSyncDone=true;if(state.kind!=='file'){$('kind').value=state.kind;$('camera').value=state.camera;$('source').disabled=state.kind==='push';sourceHelp();}}const running=state.status==='running',file=$('kind').value==='file'&&!!$('source').value.trim();$('start').disabled=['starting','stopping'].includes(state.status)||(running&&!file);$('start').textContent=running&&file?'Trocar fonte e analisar vídeo':'Iniciar processamento';if(running&&file)$('sourceHelp').textContent='Há uma fonte iniciada ('+cameraName(state.camera)+'). Trocar fonte encerra essa sessão e analisa o vídeo selecionado.';else if($('kind').value==='file')$('sourceHelp').textContent='Escolha um vídeo disponível abaixo ou envie um arquivo. Ele será analisado na cadência original.';}
$('source').addEventListener('input',updateSourceAction);

$('previewSize').value=localStorage.getItem('sentinel-preview-size')||'normal';
function previewSize(){$('video').dataset.size=$('previewSize').value;$('originalVideo').dataset.size=$('previewSize').value;localStorage.setItem('sentinel-preview-size',$('previewSize').value);}
$('previewSize').onchange=previewSize;previewSize();
async function previewLoop(){
 const started=performance.now();
 try{
  if(connected&&(followActive||$('visualSession').value===state.session_id)&&$('previewMode').value==='processed'&&!document.hidden&&!$('view-live').hidden&&state.frames&&(state.receiving||lastFrame!==state.last_frame_at)){
   const response=await api('/frame'),url=URL.createObjectURL(await response.blob()),image=new Image();image.src=url;
   try{await image.decode();if(videoUrl)URL.revokeObjectURL(videoUrl);videoUrl=url;$('video').src=url;$('video').hidden=false;$('placeholder').hidden=true;lastFrame=state.last_frame_at;}catch(e){URL.revokeObjectURL(url);throw e;}
  }
 }catch(e){/* A próxima atualização de estado mostra falhas de conexão. */}
 finally{setTimeout(previewLoop,Math.max(5,67-(performance.now()-started)));}
}
previewLoop();

// Render a small Markdown subset using DOM nodes; model output is never HTML.
function answerInline(target,text){
 const pattern=/\*\*([^*]+)\*\*|`([^`]+)`/g;let start=0,match;
 while((match=pattern.exec(text))){target.append(document.createTextNode(text.slice(start,match.index)));const tag=document.createElement(match[1]?'strong':'code');tag.textContent=match[1]||match[2];target.append(tag);start=pattern.lastIndex;}
 target.append(document.createTextNode(text.slice(start)));
}
function answerMarkdown(text){
 const box=$('answer');box.replaceChildren();let list=null;
 for(const raw of text.split('\n')){
  const line=raw.trim();if(!line){list=null;continue;}
  const bullet=/^[-*]\s+(.+)$/.exec(line),number=/^\d+[.)]\s+(.+)$/.exec(line),heading=/^#{1,6}\s+(.+)$/.exec(line);
  let block;
  if(bullet||number){const kind=number?'OL':'UL';if(!list||list.tagName!==kind){list=document.createElement(kind.toLowerCase());box.append(list);}block=document.createElement('li');list.append(block);answerInline(block,(bullet||number)[1]);}
  else{list=null;block=document.createElement(heading||/^\*\*[^*]+\*\*:?$/.test(line)?'h3':'p');box.append(block);answerInline(block,heading?heading[1]:line);}
 }
}
async function presentAnswer(text,animate){
 answerMarkdown(text);
 if(!animate||$('answerMode').value==='instant')return;
 const walker=document.createTreeWalker($('answer'),NodeFilter.SHOW_TEXT),parts=[];let node;
 while((node=walker.nextNode()))parts.push({node,text:node.textContent});
 const total=parts.reduce((n,p)=>n+p.text.length,0);for(const p of parts)p.node.textContent='';
 $('answer').setAttribute('aria-busy','true');$('answer').classList.add('typing');
 $('finishTyping').hidden=false;$('answerProgress').textContent='Exibindo resposta…';
 await new Promise(resolve=>{let begin=null,done=false;function complete(){if(done)return;done=true;for(const p of parts)p.node.textContent=p.text;resolve();}finishAnswer=complete;function tick(now){if(done)return;begin??=now;let remaining=Math.floor(total*Math.min(1,(now-begin)/Math.min(3500,Math.max(1000,total*1.5))));for(const p of parts){p.node.textContent=p.text.slice(0,remaining);remaining=Math.max(0,remaining-p.text.length);}if(parts.every(p=>p.node.textContent===p.text))complete();else requestAnimationFrame(tick);}requestAnimationFrame(tick);});
 finishAnswer=null;$('finishTyping').hidden=true;$('answerProgress').textContent='Resposta completa.';
 $('answer').classList.remove('typing');$('answer').setAttribute('aria-busy','false');
}

function reloadSessions(){
 const camera=$('filterCamera').value,chosen=$('filterSession').value,start=new Date($('since').value).getTime(),end=new Date($('until').value).getTime(),rows=sessionCatalog.filter(s=>(!camera||s.camera===camera)&&new Date(s.started_at).getTime()<end&&(!s.ended_at||new Date(s.ended_at).getTime()>=start));
 $('filterSession').replaceChildren(new Option('Todas as execuções do período',''),...rows.map(s=>new Option(displaySessionName(s)+' · '+new Date(s.started_at).toLocaleString()+' · '+s.count+' registros',s.session_id)));
 if(sessionChosen&&rows.some(s=>s.session_id===chosen))$('filterSession').value=chosen;
 else if(!sessionChosen&&rows.length){$('filterSession').value=rows[0].session_id;}
}
$('filterSession').onchange=()=>{sessionChosen=true;if(connected)guard(()=>runSearch());};
$('filterCamera').addEventListener('change',()=>{sessionChosen=false;reloadSessions();});
$('answerMode').value=localStorage.getItem('sentinel-answer-mode')||'typing';
$('answerMode').onchange=()=>localStorage.setItem('sentinel-answer-mode',$('answerMode').value);
let finishAnswer=null;
$('finishTyping').onclick=()=>finishAnswer?.();

let followActive=true;
let visualCurrent='',visualRendered='',visualBusy=false,visualUrls=[],visualReportData=null,visualAnimation=0;
function reloadVisualSessions(){
 const previous=$('visualSession').value,rows=sessionCatalog.filter(s=>s.visual_count>0||s.session_id===state.session_id);
 $('visualSession').replaceChildren(...rows.map(s=>new Option(displaySessionName(s)+' · '+new Date(s.started_at).toLocaleString(),s.session_id)));
 if(rows.some(s=>s.session_id===previous))$('visualSession').value=previous;
 if(followActive&&state.session_id&&rows.some(s=>s.session_id===state.session_id))$('visualSession').value=state.session_id;
 if(!rows.length)$('visualSession').replaceChildren(new Option('Nenhuma imagem visual disponível',''));
}
function visualMarkdown(text){const holder=$('answer'),temporary=document.createElement('div');temporary.id='answer';holder.id='technical-answer';$('visualAnswer').append(temporary);try{answerMarkdown(text);while(temporary.firstChild)$('visualAnswer').append(temporary.firstChild);}finally{temporary.remove();holder.id='answer';}}
async function animateVisual(){
 const token=++visualAnimation,walker=document.createTreeWalker($('visualAnswer'),NodeFilter.SHOW_TEXT),parts=[];let node;
 while((node=walker.nextNode()))parts.push({node,text:node.textContent});const total=parts.reduce((n,p)=>n+p.text.length,0);for(const p of parts)p.node.textContent='';
 await new Promise(resolve=>{let begin=null;function tick(now){if(token!==visualAnimation){resolve();return;}begin??=now;let left=Math.floor(total*Math.min(1,(now-begin)/Math.min(2500,Math.max(700,total))));for(const p of parts){p.node.textContent=p.text.slice(0,left);left=Math.max(0,left-p.text.length);}if(parts.every(p=>p.node.textContent===p.text))resolve();else requestAnimationFrame(tick);}requestAnimationFrame(tick);});
}
async function renderVisual(report){
 visualReportData=report;const r=report.result;if(!r)return;$('visualTimeBasis').textContent=r.time_basis||'Horário registrado no servidor.';
 for(const url of visualUrls)URL.revokeObjectURL(url);visualUrls=[];$('visualAnswer').replaceChildren();$('visualEvidence').replaceChildren();$('visualSelected').hidden=true;
 visualMarkdown('## Leitura das imagens\n'+r.summary+'\n\n'+r.observations.map(o=>'- '+o.description+' ('+o.frame_labels.join(', ')+')').join('\n')+'\n\n**O que não dá para afirmar:** '+r.uncertainty);
 $('visualState').textContent=(r.selection?.start_seconds!=null?'Trecho '+r.selection.start_seconds.toFixed(1)+'–'+r.selection.end_seconds.toFixed(1)+' s · ':'Visão geral · ')+r.frames.length+' imagens analisadas · '+r.seconds+' s · '+r.scope;
 for(const f of r.frames){const b=document.createElement('button');b.className='visual-frame';b.type='button';const time=new Date(f.timestamp).toLocaleTimeString();b.textContent=f.label+' · '+(f.offset_seconds!=null?f.offset_seconds.toFixed(1)+' s':time);b.setAttribute('aria-label','Conferir '+f.label+' às '+time);b.onclick=()=>guard(async()=>{const url=URL.createObjectURL(await(await api('/visual/frames/'+encodeURIComponent(f.id))).blob());visualUrls.push(url);$('visualSelected').src=url;$('visualSelected').hidden=false;});$('visualEvidence').append(b);}
 await animateVisual();
}
async function visualPoll(){
 if(!connected||visualBusy)return;visualBusy=true;
 try{
  if(state.session_id&&state.frames){if(!sessionCatalog.some(s=>s.session_id===state.session_id)||(!['running','starting'].includes(state.status)&&sessionCatalog.find(s=>s.session_id===state.session_id)?.status==='running'))await catalog();}
  const session=$('visualSession').value;if(!session){$('visualState').textContent='Envie um vídeo para gerar imagens e uma análise visual.';return;}
  if(visualCurrent!==session){visualCurrent=session;visualRendered='';++visualAnimation;$('visualAnswer').replaceChildren();$('visualEvidence').replaceChildren();$('visualSelected').hidden=true;}
  const report=await json('/visual/report?session_id='+encodeURIComponent(session));
  if($('visualSession').value!==session)return;
  const texts={not_analyzed:'Imagens disponíveis. Clique em Analisar imagens para perguntar sobre elas.',queued:'Análise visual na fila…',running:'A IA está examinando as imagens…',error:report.error||'Não foi possível analisar.'};
  if(report.status!=='ready')$('visualState').textContent=texts[report.status]||report.status;
  if(state.session_id===session&&!state.frames)$('visualState').textContent='Aguardando imagens do notebook. A leitura visual será preparada após receber amostras.';
  const preparing=state.kind==='file'&&state.session_id===session&&['starting','running'].includes(state.status);$('visualAsk').disabled=preparing||['queued','running'].includes(report.status);$('visualClip').disabled=$('visualAsk').disabled||sessionCatalog.find(s=>s.session_id===session)?.kind!=='file';if(preparing&&report.status==='not_analyzed')$('visualState').textContent='Capturando amostras. A análise visual começará ao terminar o vídeo.';
  if(report.status==='ready'&&visualRendered!==report.updated_at){visualRendered=report.updated_at;await renderVisual(report);}
 }catch(e){$('visualState').textContent=e.message;}finally{visualBusy=false;}
}
$('visualSession').onchange=()=>{followActive=false;visualCurrent='';$('previewMode').value=sessionCatalog.find(s=>s.session_id===$('visualSession').value)?.kind==='file'?'original':'processed';guard(visualPoll);guard(updatePreviewMode);};
$('visualAsk').onclick=()=>guard(async()=>{const session=$('visualSession').value;if(!session)throw Error('Processe um vídeo ou conecte uma câmera primeiro.');$('visualAsk').disabled=true;try{await json('/visual/analyze',{method:'POST',body:JSON.stringify({session_id:session,question:$('visualQuestion').value.trim()||'Descreva o que é visível e as mudanças entre as imagens, com evidências e incertezas.',force:true})});visualRendered='';await visualPoll();}catch(e){$('visualAsk').disabled=false;throw e;}});
$('visualRecordSearch').onclick=()=>guard(async()=>{const session=$('visualSession').value,row=sessionCatalog.find(s=>s.session_id===session);if(!row)throw Error('Escolha uma execução.');$('filterCamera').value=row.camera;$('day').value=localInput(new Date(row.started_at)).slice(0,10);setDay();sessionChosen=true;reloadSessions();$('filterSession').value=session;view('search');await runSearch();});
setInterval(()=>{if(connected&&!document.hidden&&!$('view-live').hidden)visualPoll();},2000);

async function reloadMedia(){const values=await json('/media/catalog'),selected=$('media').value;$('media').replaceChildren(new Option('Escolha um vídeo enviado',''),...values.map(v=>new Option(v.name,v.filename)));if(values.some(v=>v.filename===selected))$('media').value=selected;}

$('saveCamera').onclick=()=>guard(async()=>{await json('/camera/profile',{method:'POST',body:JSON.stringify({kind:$('kind').value,source:$('source').value,camera:$('camera').value,auto_start:$('autoCamera').checked})});message('Câmera salva no servidor. O endereço não aparece nos relatórios.');});
$('savedCamera').onclick=()=>guard(async()=>{await json('/camera/profile/start',{method:'POST'});followActive=true;$('sourceSetup').open=false;view('live');await refresh();await catalog();message('Conectando a câmera salva.');});

let originalSession='',originalUrl=null,originalLoading=false;
async function updatePreviewMode(){
 const target=followActive&&state.session_id?state.session_id:$('visualSession').value||state.session_id,review=target!==state.session_id,selected=sessionCatalog.find(s=>s.session_id===target),kind=review?selected?.kind:state.kind,original=$('previewMode').value==='original'&&kind==='file';
 $('previewMode').querySelector('option[value="original"]').disabled=kind!=='file';
 $('observedObjects').hidden=review;$('liveCadence').hidden=review||original;if(review)$('liveState').textContent='Revisando '+displaySessionName(selected||{})+' · imagens desta execução.';
 if(!original){$('originalVideo').pause();$('originalVideo').hidden=true;$('video').hidden=review||!state.frames;$('placeholder').hidden=!review&&!!state.frames;$('placeholder').textContent=review?'Confira as imagens F1, F2… desta execução na análise visual.':'As imagens processadas aparecerão aqui.';$('playbackNote').textContent=review?'Esta é uma execução anterior; a imagem da câmera atual foi ocultada para evitar misturar fontes.':'Imagem anotada atualizada conforme os quadros disponíveis.';return;}
 $('video').hidden=true;
 if(originalUrl&&originalSession===target){$('originalVideo').hidden=false;$('placeholder').hidden=true;return;}
 if(originalLoading)return;originalLoading=true;
 const session=target;
 try{
  $('playbackNote').textContent='Carregando reprodução original…';const blob=await(await api('/sessions/'+encodeURIComponent(session)+'/video')).blob();
  if((followActive&&state.session_id?state.session_id:$('visualSession').value||state.session_id)!==session)return;if(originalUrl)URL.revokeObjectURL(originalUrl);originalUrl=URL.createObjectURL(blob);originalSession=session;$('originalVideo').src=originalUrl;$('originalVideo').hidden=false;$('placeholder').hidden=true;$('playbackNote').textContent='Reprodução original independente da análise. A IA usa imagens amostradas; este player não mostra caixas.';
  await $('originalVideo').play().catch(()=>{});
 }catch(e){$('previewMode').value='processed';$('originalVideo').hidden=true;$('video').hidden=review||!state.frames;$('placeholder').hidden=!review&&!!state.frames;$('playbackNote').textContent=e.message;}
 finally{originalLoading=false;}
}
$('previewMode').onchange=()=>guard(updatePreviewMode);
$('originalVideo').onerror=()=>{$('previewMode').value='processed';guard(updatePreviewMode);$('playbackNote').textContent='Formato não reproduzível neste navegador. Confira as imagens amostradas desta execução.';};

Object.assign(cameraNames,{CAMERA_01:'Câmera principal',DEMONSTRACAO_FINAL:'Demonstração · corredor',EXEMPLO_CORREDOR:'Exemplo · corredor',CONTROLE_VAZIO:'Controle sem atividade',VALIDACAO_NOITE:'Cena noturna · teste',VALIDACAO_VISUAL:'Cena noturna · teste anterior'});
function displaySessionName(s){return /^[0-9a-f-]{36}\.(mp4|avi|mov|mkv|webm)$/i.test(s.name||'')?'Vídeo enviado':s.name||cameraName(s.camera);}

$('day').addEventListener('change',()=>{sessionChosen=false;reloadSessions();});

let deliverySample=null;
function renderObservations(){
 const now=performance.now();if(deliverySample&&deliverySample.session===state.session_id&&state.frames>=deliverySample.frames){const seconds=(now-deliverySample.time)/1000;if(seconds>.4){const fps=(state.frames-deliverySample.frames)/seconds;$('liveCadence').textContent=state.receiving?'Chegando ao PC: '+fps.toFixed(1)+' imagens/s · análise: '+state.inference_ms+' ms por quadro'+(fps<5?' · movimento limitado pela taxa enviada pela câmera':''):'Aguardando novas imagens da câmera';}}deliverySample={session:state.session_id,frames:state.frames,time:now};
 const fresh=state.receiving,rows=state.observations||[];$('observationRows').replaceChildren();
 $('observationState').textContent=fresh?(rows.length?rows.length+' detecções neste quadro':'Nenhum objeto reconhecido neste quadro'):'Último quadro recebido · não é leitura atual';
 for(const row of rows){const p=document.createElement('p');p.className='observation-row';p.textContent=(row.label||row.object_type)+(row.track_id!=null?' · ID '+row.track_id:' · ainda sem acompanhamento')+' · confiança '+Math.round(row.confidence*100)+'%'+(row.tracking_recovery?' · continuidade incerta':'')+(row.motion?' · '+row.motion:'')+(row.keypoints?.length?' · pose estimada':'')+(row.near_wrist_candidates?.length?' · próximo do punho: '+row.near_wrist_candidates.map(c=>'pessoa ID '+c.person_id+', '+c.wrist).join('; ')+', sem confirmar que segura o item':row.near_person_ids?.length?' · próximo da pessoa ID '+row.near_person_ids.join(', ')+', sem confirmar contato':'');$('observationRows').append(p);}
}
async function loadDetectionOptions(){const r=await json('/detection/options');$('detectionScope').value=r.options.scope;$('detectionQuality').value=r.options.quality;const select=$('detectionConfidence'),value=String(r.options.confidence);if(!Array.from(select.options).some(o=>o.value===value))select.add(new Option(Math.round(r.options.confidence*100)+'%',value));select.value=value;$('detectionNote').textContent=r.model+(r.person_specialist_active?' · reforço treinado para pessoas':'')+' · '+r.note;}
$('applyDetection').onclick=()=>guard(async()=>{await json('/detection/options',{method:'PUT',body:JSON.stringify({scope:$('detectionScope').value,quality:$('detectionQuality').value,confidence:Number($('detectionConfidence').value)})});message('Reconhecimento atualizado e salvo. A câmera continua na mesma execução.');await loadDetectionOptions();await refresh();});
$('connectNotebook').onclick=()=>guard(async()=>{const current=await json('/status');if(current.status==='running'){if(current.kind!=='push'||current.camera!=='NOTEBOOK_01')throw Error('Outra fonte está ativa. Pare-a antes de conectar o notebook.');}else if(['starting','stopping'].includes(current.status))throw Error('Aguarde a câmera terminar a preparação.');else await json('/cameras/start',{method:'POST',body:JSON.stringify({kind:'push',source:'',camera:'NOTEBOOK_01'})});followActive=true;$('kind').value='push';$('camera').value='NOTEBOOK_01';sourceHelp();$('previewMode').value='processed';$('sourceSetup').open=false;view('live');await refresh();await catalog();message('PC preparado. No notebook, abra Iniciar.cmd e clique em Iniciar envio.');});
let detectionOptionsLoaded=false;setInterval(()=>{if(connected&&!detectionOptionsLoaded){detectionOptionsLoaded=true;guard(loadDetectionOptions);}},1000);

$('visualClip').onclick=()=>guard(async()=>{
 const session=$('visualSession').value,player=$('originalVideo');
 if(originalSession!==session||!Number.isFinite(player.duration)||player.hidden)throw Error('Selecione Vídeo original, pause no momento desejado e tente novamente.');
 const at=player.currentTime,start=Math.max(0,at-6),end=Math.min(player.duration,start+12);
 if(end<=start)throw Error('Trecho de vídeo indisponível.');
 player.pause();$('visualClip').disabled=true;
 try{await json('/visual/analyze',{method:'POST',body:JSON.stringify({session_id:session,question:$('visualQuestion').value.trim()||'Descreva os movimentos, objetos e interações visíveis neste trecho, citando as imagens. Separe observação de hipótese.',force:true,start_seconds:start,end_seconds:end})});visualRendered='';await visualPoll();}
 catch(e){$('visualClip').disabled=false;throw e;}
});

let selectedReviewEvent=null,reviewOpenedAt=0;
const reviewNames={confirmed:'Confere com a imagem',incorrect:'Registro incorreto',uncertain:'Inconclusivo',not_reviewed:'Ainda não conferido'};
async function loadReview(event,version){const r=await json('/events/'+encodeURIComponent(event.id)+'/review');if(version!==evidenceVersion)return;$('reviewState').textContent=reviewNames[r.verdict]+(r.created_at?' · '+new Date(r.created_at).toLocaleString():'');$('reviewVerdict').value=r.verdict==='not_reviewed'?'uncertain':r.verdict;$('reviewNote').value=r.note;}
$('saveReview').onclick=()=>guard(async()=>{const e=selectedReviewEvent;if(!e)throw Error('Selecione um registro.');const r=await json('/events/'+encodeURIComponent(e.id)+'/review',{method:'POST',body:JSON.stringify({verdict:$('reviewVerdict').value,note:$('reviewNote').value.trim()})});if(selectedReviewEvent?.id===e.id)$('reviewState').textContent=reviewNames[r.verdict]+' · salvo';message('Conferência salva. A detecção e os registros originais foram preservados.');});
$('exportReviews').onclick=()=>guard(async()=>{if(!selectedReviewEvent)throw Error('Selecione um registro.');const r=await json('/evaluation/reviews?session_id='+encodeURIComponent(selectedReviewEvent.session_id)),url=URL.createObjectURL(new Blob([JSON.stringify(r,null,2)],{type:'application/json'})),a=document.createElement('a');a.href=url;a.download='sentinel-conferencias.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);});

async function reloadPilot(){const r=await json('/evaluation/trials'),s=r.summary;$('pilotSummary').textContent=s.pairs?s.pairs+' tarefas comparadas · corretas: manual '+s.correct.manual+', Sentinel '+s.correct.sentinel+' · diferença mediana '+s.median_minutes_saved+' min. '+s.note:'Nenhum par de tarefas registrado. Ainda não há economia de tempo medida.';return r;}
$('pilot').ontoggle=()=>{if($('pilot').open&&connected)guard(reloadPilot);};
$('pilotSave').onclick=()=>guard(async()=>{await json('/evaluation/trials',{method:'POST',body:JSON.stringify({task_id:$('pilotTask').value.trim(),mode:$('pilotMode').value,seconds:Number($('pilotSeconds').value),outcome:$('pilotOutcome').value})});await reloadPilot();message('Medição salva. Compare a mesma tarefa com o outro método.');});
$('pilotExport').onclick=()=>guard(async()=>{const r=await reloadPilot(),u=URL.createObjectURL(new Blob([JSON.stringify(r,null,2)],{type:'application/json'})),a=document.createElement('a');a.href=u;a.download='sentinel-piloto-tempo.json';a.click();setTimeout(()=>URL.revokeObjectURL(u),1000);});
