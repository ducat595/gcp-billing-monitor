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
const w=new ListWidget();
const gradient=new LinearGradient();
gradient.colors=[new Color("#1d3b62"),new Color("#10192c"),new Color("#0b1323")];
gradient.locations=[0,0.5,1];w.backgroundGradient=gradient;
w.setPadding(16,18,14,18);
const top=w.addStack();top.centerAlignContent();
const title=top.addText("◉  GCP BILLING");title.textColor=new Color("#a9d5ff");title.font=Font.boldSystemFont(11);
top.addSpacer();
const date=top.addText(today);date.textColor=new Color("#839bb9");date.font=Font.systemFont(10);
w.addSpacer(12);
const caption=w.addText("当月の利用料金");caption.textColor=new Color("#a9b7cb");caption.font=Font.systemFont(11);
w.addSpacer(4);
const amount=w.addText("取得待ち");amount.font=Font.boldSystemFont(27);amount.textColor=Color.white();
w.addSpacer(12);
const detail=w.addText("");detail.textColor=new Color("#c3d4e9");detail.font=Font.systemFont(11);
w.url="https://tesla-charge-collector.tail522b23.ts.net/";
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
