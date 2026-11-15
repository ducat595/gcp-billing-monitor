// Scriptable: keep API credentials private; do not commit secrets to GitHub.
const API_URL = ""; // private Tailscale API endpoint
const API_TOKEN = ""; // private read-only token, until authentication is migrated
const fm=FileManager.local();
const cachePath=fm.joinPath(fm.documentsDirectory(),"gcp-billing-widget-cache.json");
const today=new Date().toLocaleDateString("en-CA",{timeZone:"Asia/Tokyo"});
const format=(value,currency)=>value==null?"反映待ち":new Intl.NumberFormat("ja-JP",{style:"currency",currency:currency||"JPY",maximumFractionDigits:2}).format(value);
let cached=null;
try{if(fm.fileExists(cachePath))cached=JSON.parse(fm.readString(cachePath))}catch(e){cached=null}
let record=cached;
let error=false;
// One successful request per Japan calendar day; retry failures on later refreshes.
if(!cached||cached.day!==today){
 if(API_URL&&API_TOKEN){
  try{
   const req=new Request(API_URL);
   req.headers={"X-API-Key":API_TOKEN};
   req.timeoutInterval=15;
   const data=await req.loadJSON();
   if(!data||!data.accounts)throw Error("Invalid response");
   record={day:today,data};
   fm.writeString(cachePath,JSON.stringify(record));
  }catch(e){error=true}
 }else{error=true}
}
const w=new ListWidget();w.backgroundColor=new Color("#17243a");
const title=w.addText("GCP 利用料金");title.textColor=Color.white();title.font=Font.boldSystemFont(15);
w.addSpacer(12);
const amount=w.addText("取得待ち");amount.font=Font.boldSystemFont(25);amount.textColor=Color.white();
const detail=w.addText("");detail.textColor=new Color("#a9b7cb");detail.font=Font.systemFont(11);
if(record&&record.data){
 const data=record.data;
 amount.text=format(data.total_month,data.currency);
 const lines=Object.values(data.accounts).map(a=>a.name+": "+(a.status==="ready"?format(a.month,a.currency):"未取得"));
 lines.push("月末見込み: "+format(data.forecast,data.currency));
 lines.push((record.day===today?"取得日: ":"前回取得: ")+record.day+(error?"（更新失敗）":""));
 detail.text=lines.join("\n");
}else{
 amount.text="未取得";
 detail.text=API_URL&&API_TOKEN?"通信エラー：次回更新時に再試行":"API URLとトークンを設定してください";
}
// Scriptable/iOS may delay refresh; cache prevents repeated successful daily API calls.
const tomorrow=new Date();tomorrow.setHours(24,5,0,0);
w.refreshAfterDate=tomorrow;
Script.setWidget(w);
if(!config.runsInWidget)await w.presentMedium();
Script.complete();
