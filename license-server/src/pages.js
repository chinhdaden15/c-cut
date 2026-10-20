// Trang mua (khách) + trang quản lý (chủ app). HTML tĩnh, gọi API cùng máy chủ.
const BASE_CSS = `
:root{--bg:#0f1012;--panel:#17181b;--panel2:#1f2024;--line:#2a2b30;--fg:#ececee;--fg2:#a0a1a8;--acc:#4f8cff;--ok:#3ecf8e;--bad:#ff6b6b}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif}
.wrap{max-width:560px;margin:0 auto;padding:28px 16px}h1{font-size:22px;margin:0 0 4px}h2{font-size:16px;margin:22px 0 8px}
.dim{color:var(--fg2);font-size:13px}.card{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:14px;margin:10px 0}
button{font:inherit;border:0;border-radius:8px;padding:9px 16px;background:var(--acc);color:#fff;cursor:pointer}button.ghost{background:var(--panel2);color:var(--fg)}
button:disabled{opacity:.5;cursor:default}input,select{font:inherit;color:var(--fg);background:var(--panel2);border:1px solid var(--line);border-radius:8px;padding:8px 10px;width:100%}
label.opt{display:flex;gap:10px;align-items:center;border:1px solid var(--line);border-radius:10px;padding:12px;margin:8px 0;cursor:pointer}
label.opt.on{border-color:var(--acc);background:#4f8cff1a}label.opt input{width:auto}.price{margin-left:auto;font-weight:600}
.key{font:600 20px ui-monospace,Menlo,monospace;letter-spacing:1px;background:var(--panel2);border-radius:8px;padding:10px;text-align:center;margin:8px 0}
.ok{color:var(--ok)}.bad{color:var(--bad)}img.qr{width:100%;max-width:300px;display:block;margin:8px auto;border-radius:10px;background:#fff}
table{width:100%;border-collapse:collapse;font-size:13px}td,th{border-bottom:1px solid var(--line);padding:6px 4px;text-align:left;vertical-align:top}
.row{display:flex;gap:8px;align-items:center;flex-wrap:wrap}.row>*{flex:1;min-width:120px}code{font-size:12px;word-break:break-all}
#toasts{position:fixed;right:16px;bottom:16px;display:flex;flex-direction:column;gap:8px;z-index:60;max-width:calc(100vw - 32px)}
#toasts div{background:var(--panel2);border:1px solid var(--line);border-left:3px solid var(--ok);border-radius:10px;padding:10px 14px;box-shadow:0 6px 24px #0008;font-size:14px;animation:tin .2s ease}
#toasts div.bad{border-left-color:var(--bad)}@keyframes tin{from{opacity:0;transform:translateY(8px)}}
.dlg{position:fixed;inset:0;background:#0009;display:flex;align-items:center;justify-content:center;z-index:70;padding:16px}
.dlg .box{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:18px;width:min(380px,100%)}.dlg .acts{display:flex;gap:8px;justify-content:flex-end;margin-top:16px}`;
const UI_JS = `function toast(m,k){let w=document.getElementById('toasts');if(!w){w=document.createElement('div');w.id='toasts';document.body.append(w)}
  const d=document.createElement('div');d.className=k||'';d.textContent=m;w.append(d);setTimeout(()=>d.remove(),4000)}
function ask(m){return new Promise(res=>{const d=document.createElement('div');d.className='dlg';
  d.innerHTML='<div class="box"><div></div><div class="acts"><button class="ghost">Huỷ</button><button>Đồng ý</button></div></div>';
  d.querySelector('.box>div').textContent=m;const b=d.querySelectorAll('button');const done=v=>{d.remove();res(v)};
  b[0].onclick=()=>done(false);b[1].onclick=()=>done(true);d.onclick=e=>{if(e.target===d)done(false)};document.body.append(d);b[1].focus()})}`;

export const BUY_HTML = `<!doctype html><html lang="vi"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Mua skill C-Cut</title><style>${BASE_CSS}</style></head><body><div class="wrap">
<h1>Mua skill C-Cut</h1><div class="dim">Mua một lần, dùng vĩnh viễn trên 1 máy. App C-Cut và skill Talking Head miễn phí.</div>
<div id="step1"><h2>Chọn skill</h2><div id="prods" class="dim">Đang tải…</div>
<h2>Liên hệ nhận mã (email hoặc số Zalo)</h2><input id="contact" placeholder="vd: ban@gmail.com hoặc 09xx…">
<div style="margin-top:14px"><button id="go" disabled>Tạo mã chuyển khoản</button></div></div>
<div id="step2" hidden><div class="card"><div class="dim">Quét mã QR bằng app ngân hàng — số tiền và nội dung đã điền sẵn.</div>
<img class="qr" id="qr" alt="QR chuyển khoản"><div id="bank"></div></div>
<div class="card" id="wait"><b>Đang chờ tiền về…</b><div class="dim">Trang tự cập nhật khi ngân hàng báo đã nhận (thường dưới 1 phút). Giữ nguyên trang này.</div></div></div>
<div id="step3" hidden><div class="card"><b class="ok">Đã nhận tiền — cảm ơn bạn!</b><div class="dim">Mã bản quyền của bạn:</div>
<div class="key" id="key"></div><button class="ghost" id="copy">Chép mã</button>
<div class="dim" style="margin-top:10px" id="howto">Mở C-Cut → Cài đặt → Bản quyền skill → dán mã → Kích hoạt. Mỗi mã dùng cho 1 máy. Lưu lại mã này.</div></div></div>
</div><script>${UI_JS}
const q=new URLSearchParams(location.search),$=s=>document.querySelector(s);let sel=q.get('product'),order=null;
const vnd=n=>n.toLocaleString('vi-VN')+' đ';
fetch('/v1/products').then(r=>r.json()).then(d=>{const ps=d.products||[];if(!ps.length){$('#prods').textContent='Chưa mở bán.';return}
  if(!ps.some(p=>p.id===sel))sel=ps[0].id;
  $('#prods').innerHTML=ps.map(p=>'<label class="opt" data-id="'+p.id+'"><input type="radio" name="p"'+(p.id===sel?' checked':'')+'><span>'+p.name+'</span><span class="price">'+vnd(p.price)+'</span></label>').join('');
  const mark=()=>document.querySelectorAll('label.opt').forEach(l=>l.classList.toggle('on',l.dataset.id===sel));
  document.querySelectorAll('label.opt').forEach(l=>l.onclick=()=>{sel=l.dataset.id;mark()});mark();$('#go').disabled=false});
$('#go').onclick=async()=>{$('#go').disabled=true;
  const r=await fetch('/v1/order',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({product:sel,contact:$('#contact').value,device:q.get('device')})}).then(r=>r.json());
  if(!r.ok){toast(r.error,'bad');$('#go').disabled=false;return}order=r;$('#step1').hidden=true;$('#step2').hidden=false;$('#qr').src=r.qr;
  $('#bank').innerHTML='<table><tr><td class="dim">Ngân hàng</td><td>'+r.bank+'</td></tr><tr><td class="dim">Số tài khoản</td><td>'+r.account+'</td></tr><tr><td class="dim">Chủ tài khoản</td><td>'+(r.account_name||'')+'</td></tr><tr><td class="dim">Số tiền</td><td><b>'+vnd(r.amount)+'</b></td></tr><tr><td class="dim">Nội dung</td><td><b>'+r.code+'</b> (bắt buộc ghi đúng)</td></tr></table>';
  poll()};
async function poll(){const r=await fetch('/v1/order/'+order.id).then(r=>r.json()).catch(()=>({}));
  if(r.status==='paid'&&r.key){$('#step2').hidden=true;$('#step3').hidden=false;$('#key').textContent=r.key;
    if(r.token)$('#howto').textContent='Mã đã tự kích hoạt cho máy đang mở C-Cut — quay lại app là dùng được. Lưu lại mã này phòng khi cần.';return}
  setTimeout(poll,3000)}
$('#copy').onclick=()=>navigator.clipboard.writeText($('#key').textContent);
</script></body></html>`;

export const ADMIN_HTML = `<!doctype html><html lang="vi"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Quản lý C-Cut</title><style>${BASE_CSS}.wrap{max-width:1100px}.card{overflow-x:auto}table{min-width:640px}</style></head><body><div class="wrap">
<h1>Quản lý bản quyền C-Cut</h1>
<div id="login" class="card"><div class="dim">Mật khẩu quản lý (ADMIN_TOKEN)</div><div class="row"><input id="tok" type="password"><button id="in" style="flex:0">Vào</button></div></div>
<div id="main" hidden>
<h2>Tạo mã bản quyền (bán qua fanpage / tặng)</h2><div class="card row"><select id="nk" style="flex:0;min-width:110px"><option value="sale">Bán</option><option value="gift">Tặng</option></select><select id="np"></select><input id="nn" placeholder="ghi chú: tên khách / Zalo"><button id="mk" style="flex:0">Tạo mã</button></div>
<div id="newkey"></div>
<h2>Giá bán (VND · 0 = chưa mở bán)</h2><div class="card"><table id="prods"></table></div>
<h2>Tài khoản nhận tiền + dùng thử</h2><div class="card"><div class="row"><input id="s_bank" placeholder="Mã ngân hàng (vd VCB, MB, TCB, ACB)"><input id="s_account" placeholder="Số tài khoản"><input id="s_account_name" placeholder="Tên chủ tài khoản"><input id="s_trial_limit" placeholder="Lượt dùng thử mỗi skill"></div><div style="margin-top:8px"><button id="save">Lưu</button></div></div>
<h2>Đơn hàng</h2><div class="card"><table id="orders"></table></div>
<h2>Mã bản quyền</h2><div class="row" style="margin-bottom:6px"><select id="lf" style="flex:0;min-width:160px"><option value="">Tất cả</option><option value="order">Mua qua QR</option><option value="sale">Bán tay</option><option value="gift">Tặng</option></select><span class="dim" id="lcount"></span></div><div class="card"><table id="lics"></table></div>
<h2>Máy dùng app</h2><div class="card"><table id="devs"></table></div>
</div></div><script>${UI_JS}
const $=s=>document.querySelector(s);let D=null,T=localStorage.getItem('ccut_admin')||'';const dt=t=>t?new Date(t*1000).toLocaleString('vi-VN'):'';
const vnd=n=>(n||0).toLocaleString('vi-VN');const esc=s=>String(s??'').replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
async function api(p,b){const r=await fetch('/admin/api/'+p,{method:b?'POST':'GET',headers:{authorization:'Bearer '+T,'content-type':'application/json'},body:b?JSON.stringify(b):undefined}).then(r=>r.json());
  if(!r.ok){toast(r.error,'bad');if(String(r.error).includes('mật khẩu')){$('#main').hidden=true;$('#login').hidden=false}throw r}return r}
let PAID=null;
async function load(){const d=await api('overview');
  const paid=d.orders.filter(o=>o.status==='paid');if(PAID)paid.filter(o=>!PAID.has(o.id)).forEach(o=>toast('Đơn mới đã thanh toán: '+o.code+' · '+vnd(o.amount)+' đ'));PAID=new Set(paid.map(o=>o.id));$('#login').hidden=true;$('#main').hidden=false;
  $('#np').innerHTML=d.products.map(p=>'<option value="'+p.id+'">'+esc(p.name)+'</option>').join('');
  for(const k of ['bank','account','account_name','trial_limit'])$('#s_'+k).value=d.settings[k]||'';
  $('#prods').innerHTML='<tr><th>Mã</th><th>Tên</th><th>Giá</th><th>Bán</th><th></th></tr>'+d.products.map(p=>'<tr data-id="'+p.id+'" data-sort="'+p.sort+'"><td><code>'+p.id+'</code></td><td><input value="'+esc(p.name)+'"></td><td><input type="number" value="'+p.price+'"></td><td><input type="checkbox" style="width:auto"'+(p.active?' checked':'')+'></td><td><button class="ghost" data-save>Lưu</button></td></tr>').join('');
  document.querySelectorAll('[data-save]').forEach(b=>b.onclick=async()=>{const tr=b.closest('tr'),i=tr.querySelectorAll('input');await api('product',{id:tr.dataset.id,name:i[0].value,price:i[1].value,active:i[2].checked,sort:tr.dataset.sort});toast('Đã lưu giá '+i[0].value+': '+vnd(+i[1].value)+' đ');load()});
  $('#orders').innerHTML='<tr><th>Thời gian</th><th>Nội dung CK</th><th>Sản phẩm</th><th>Số tiền</th><th>Liên hệ</th><th>Trạng thái</th><th>Mã</th></tr>'+d.orders.map(o=>'<tr><td>'+dt(o.created)+'</td><td><code>'+o.code+'</code></td><td>'+o.product+'</td><td>'+vnd(o.amount)+'</td><td>'+esc(o.contact)+'</td><td>'+(o.status==='paid'?'<span class="ok">đã trả</span> '+dt(o.paid):'chờ <button class="ghost" data-paid="'+o.id+'">Đã nhận tiền</button>')+'</td><td><code>'+(o.license||'')+'</code></td></tr>').join('');
  document.querySelectorAll('[data-paid]').forEach(b=>b.onclick=async()=>{if(await ask('Xác nhận đã nhận đủ tiền đơn này? Khách sẽ được cấp mã ngay.')){await api('order/paid',{id:b.dataset.paid});load()}});
  D=d;const KN={order:'Mua QR',sale:'Bán tay',gift:'Tặng'},f=$('#lf').value,ls=d.licenses.filter(l=>!f||l.kind===f);
  $('#lcount').textContent=['order','sale','gift'].map(k=>KN[k]+': '+d.licenses.filter(l=>l.kind===k).length).join(' · ');
  $('#lics').innerHTML='<tr><th>Mã</th><th>Loại</th><th>Sản phẩm</th><th>Máy</th><th>Tạo</th><th>Ghi chú</th><th></th></tr>'+ls.map(l=>'<tr><td><code>'+l.key+'</code>'+(l.revoked?' <span class="bad">thu hồi</span>':'')+'</td><td>'+(KN[l.kind]||l.kind)+'</td><td>'+l.product+'</td><td><code>'+(l.device?l.device.slice(0,12)+'…':'chưa kích hoạt')+'</code></td><td>'+dt(l.created)+'</td><td>'+esc(l.note)+'</td><td><button class="ghost" data-l="'+(l.revoked?'license/restore':'license/revoke')+'" data-k="'+l.key+'">'+(l.revoked?'Mở lại':'Thu hồi')+'</button>'+(l.device?' <button class="ghost" data-l="license/unbind" data-k="'+l.key+'">Gỡ khỏi máy</button>':'')+'</td></tr>').join('');
  document.querySelectorAll('[data-l]').forEach(b=>b.onclick=async()=>{if(await ask(b.textContent+' mã '+b.dataset.k+'?')){await api(b.dataset.l,{key:b.dataset.k});load()}});
  $('#devs').innerHTML='<tr><th>Máy</th><th>Hệ điều hành / app</th><th>Dùng thử</th><th>Lần đầu</th><th>Gần nhất</th><th></th></tr>'+d.devices.map(v=>'<tr><td><code>'+v.id.slice(0,16)+'…</code>'+(v.blocked?' <span class="bad">khoá</span>':'')+'</td><td>'+esc(v.os)+' · '+esc(v.app)+'</td><td>'+esc(v.trials||'')+'</td><td>'+dt(v.first_seen)+'</td><td>'+dt(v.last_seen)+'</td><td><button class="ghost" data-b="'+v.id+'" data-v="'+(v.blocked?0:1)+'">'+(v.blocked?'Mở khoá':'Khoá')+'</button> <button class="ghost" data-r="'+v.id+'">Cấp lại lượt thử</button></td></tr>').join('');
  document.querySelectorAll('[data-b]').forEach(b=>b.onclick=async()=>{await api('device/block',{id:b.dataset.b,blocked:b.dataset.v==='1'});load()});
  document.querySelectorAll('[data-r]').forEach(b=>b.onclick=async()=>{if(await ask('Cấp lại toàn bộ lượt dùng thử cho máy này?')){await api('device/reset-trial',{id:b.dataset.r});load()}});
}
$('#in').onclick=()=>{T=$('#tok').value;localStorage.setItem('ccut_admin',T);load()};
$('#mk').onclick=async()=>{const r=await api('license',{product:$('#np').value,note:$('#nn').value,kind:$('#nk').value});$('#newkey').innerHTML='<div class="card">Mã '+(r.kind==='gift'?'tặng':'bán')+' mới: <span class="key" style="display:inline-block">'+r.key+'</span> — gửi cho '+(r.kind==='gift'?'người được tặng':'khách')+'.</div>';$('#nn').value='';load()};
$('#lf').onchange=()=>load();
$('#save').onclick=async()=>{const b={};for(const k of ['bank','account','account_name','trial_limit'])b[k]=$('#s_'+k).value;await api('settings',b);toast('Đã lưu tài khoản nhận tiền');load()};
setInterval(async()=>{if(!T||$('#main').hidden||document.querySelector('.dlg'))return;const a=document.activeElement;if(a&&a.closest('#main')&&/INPUT|SELECT/.test(a.tagName))return;
  try{await load()}catch(e){}},15000);
if(T)load().catch(()=>{});
</script></body></html>`;
