// Scriptable: keep API credentials private; do not commit secrets to GitHub.
const API_URL = "https://tesla-charge-collector.tail522b23.ts.net:8767/api/billing"; // private Tailscale API endpoint
const API_TOKEN = ""; // private read-only token, until authentication is migrated
const pairingKey="gcp-billing-widget-pairing-v1";
if(!Keychain.contains(pairingKey))Keychain.set(pairingKey,UUID.string().toLowerCase());
const widgetId=Keychain.get(pairingKey);
const fm=FileManager.local();
const cachePath=fm.joinPath(fm.documentsDirectory(),"gcp-billing-widget-cache.json");
const today=new Date().toLocaleDateString("en-CA",{timeZone:"Asia/Tokyo"});
const format=(value,currency)=>value==null?"反映待ち":new Intl.NumberFormat("ja-JP",{style:"currency",currency:currency||"JPY",maximumFractionDigits:2}).format(value);
let cached=null;
try{if(fm.fileExists(cachePath))cached=JSON.parse(fm.readString(cachePath))}catch(e){cached=null}
let record=cached;
let error=false;
// One successful request per Japan calendar day; retry failures on later refreshes.
if(!cached||cached.day!==today||cached.version!==3){
 if(API_URL&&API_TOKEN){
  try{
   const req=new Request(API_URL+'?widget_id='+encodeURIComponent(widgetId));
   req.headers={"X-API-Key":API_TOKEN};
   req.timeoutInterval=15;
   const data=await req.loadJSON();
   if(!data||!data.accounts||Object.values(data.accounts).some(a=>a.status!=="ready"||a.budget_status==="error"))throw Error("Data unavailable");
   record={day:today,data,version:3};
   fm.writeString(cachePath,JSON.stringify(record));
  }catch(e){error=true}
 }else{error=true}
}
const w=new ListWidget();
const gradient=new LinearGradient();
gradient.colors=[new Color("#1d3b62"),new Color("#10192c"),new Color("#0b1323")];
gradient.locations=[0,0.5,1];w.backgroundGradient=gradient;
w.setPadding(10,14,10,14);
const top=w.addStack();top.centerAlignContent();
const title=top.addText("◉  GCP BILLING");title.textColor=new Color("#a9d5ff");title.font=Font.boldSystemFont(11);
top.addSpacer();
const date=top.addText(today);date.textColor=new Color("#839bb9");date.font=Font.systemFont(10);
w.addSpacer(5);
const caption=w.addText("当月の利用料金");caption.textColor=new Color("#a9b7cb");caption.font=Font.systemFont(11);
w.addSpacer(4);
const amount=w.addText("取得待ち");amount.font=Font.boldSystemFont(24);amount.textColor=Color.white();
w.addSpacer(5);
const detail=w.addText("");detail.textColor=new Color("#c3d4e9");detail.font=Font.systemFont(11);
w.url="https://tesla-charge-collector.tail522b23.ts.net:8767/?widget_id="+encodeURIComponent(widgetId);
if(record&&record.data){
 const data=record.data;
 amount.text=format(data.total_month,data.currency);
 const lines=Object.values(data.accounts).map(a=>{
  const valid=a.status==="ready"&&Number.isFinite(a.month)&&Number.isFinite(a.budget)&&a.budget>0;
  const ratio=valid?a.month/a.budget:null;
  const light=ratio===null?"⚪":ratio>1?"🔴":ratio>=0.8?"🟡":"🟢";
  return light+" "+a.name+": "+(a.status==="ready"?format(a.month,a.currency):"未取得")+(valid?" ("+(ratio*100).toFixed(0)+"%)":" / 予算未取得");
 });
 lines.push("月末見込み: "+format(data.forecast,data.currency));
 lines.push((record.day===today?"取得日: ":"前回取得: ")+record.day+(error?"（更新失敗）":""));
 detail.text=lines.join("\n");
}else{
 amount.text="未取得";
 detail.text=API_URL&&API_TOKEN?"通信エラー：次回更新時に再試行":"API URLとトークンを設定してください";
}
w.addSpacer(3);
let expiry=record?.data?.browser_session_expires_at;
let expiryError=false;
if(API_URL&&API_TOKEN){
 try{
  const req=new Request(API_URL.replace(/\/billing$/, "/session-expiry")+'?widget_id='+encodeURIComponent(widgetId));
  req.headers={"X-API-Key":API_TOKEN};
  req.timeoutInterval=10;
  const state=await req.loadJSON();
  if(req.response.statusCode!==200||!Object.prototype.hasOwnProperty.call(state,"browser_session_expires_at"))throw Error("Expiry unavailable");
  expiry=state.browser_session_expires_at;
  if(record&&record.data){
   record.data.browser_session_expires_at=expiry;
   fm.writeString(cachePath,JSON.stringify(record));
  }
 }catch(e){expiryError=true}
}
const days=Number.isFinite(expiry)?Math.max(0,Math.ceil((expiry*1000-Date.now())/86400000)):null;
const auth=w.addText(days===null?"⚪ 認証期限：未確認・タップして連携":days===0?"🔴 認証期限切れ・再認証":days<=7?"🔴 残り"+days+"日・ブラウザを開く":days<=30?"🟡 残り"+days+"日・ブラウザを開く":"🟢 認証期限：残り"+days+"日");
if(expiryError)auth.text=auth.text+"（更新失敗）";
auth.font=Font.systemFont(10);
auth.textColor=new Color(days===null?"#c3d4e9":days<=7?"#ff8585":days<=30?"#ffd166":"#79e6af");
// Scriptable/iOS may delay refresh; cache prevents repeated successful daily API calls.
w.refreshAfterDate=new Date(Date.now()+30*60*1000);
Script.setWidget(w);
if(!config.runsInWidget)await w.presentMedium();
Script.complete();
