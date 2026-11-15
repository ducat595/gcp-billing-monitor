const $=id=>document.getElementById(id);
const money=(v,c)=>v==null?'データ反映待ち':new Intl.NumberFormat('ja-JP',{style:'currency',currency:c||'JPY',maximumFractionDigits:2}).format(v);
const status={pending:'課金データ反映待ち',error:'取得エラー',currency_mismatch:'通貨の確認が必要',ready:'取得済み'};
$('load').onclick=async()=>{
 $('message').textContent='取得中…';$('accounts').replaceChildren();$('total').textContent='取得中…';
 try{
  const u=new URL($('url').value);if(u.protocol!=='https:'&&!['localhost','127.0.0.1'].includes(u.hostname))throw Error('HTTPSのAPI URLを指定してください');
  const res=await fetch(u,{headers:{'X-API-Key':$('token').value},cache:'no-store'});
  if(!res.ok)throw Error('API応答: '+res.status);
  const data=await res.json();
  $('total').textContent=money(data.total_month,data.currency);
  $('updated').textContent=new Date(data.generated_at).toLocaleString('ja-JP');
  for(const a of Object.values(data.accounts)){
   const card=document.createElement('article');card.className='account';
   const h=document.createElement('h2');h.textContent=a.name;card.append(h);
   const strong=document.createElement('strong');strong.textContent=a.status==='ready'?money(a.month,a.currency):status[a.status]||'不明';card.append(strong);
   if(a.status==='ready'){
    const p=document.createElement('p');p.textContent='前月: '+money(a.previous_month,a.currency);card.append(p);
    const bars=document.createElement('div');bars.className='bars';const max=Math.max(1,...a.daily.map(x=>Math.max(0,x.amount)));
    for(const d of a.daily){const bar=document.createElement('div');bar.className='bar';bar.style.height=Math.max(2,Math.max(0,d.amount)/max*100)+'%';bar.title=d.date+' '+money(d.amount,a.currency);bars.append(bar)}card.append(bars)
   }$('accounts').append(card);
  }
  $('message').textContent=data.total_month==null?'一部の課金データが未取得のため、合計は表示していません。':'利用料金は反映遅延があります。確定請求額ではありません。';
 }catch(e){$('message').textContent=e.message;$('total').textContent='取得失敗'}
};