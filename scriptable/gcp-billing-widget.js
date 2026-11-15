// Scriptable: configure these values locally in Scriptable, never commit secrets to GitHub.
const API_URL = ""; // e.g. https://your-private-api.example/api/billing
const API_TOKEN = ""; // private read-only token
const w = new ListWidget();
w.backgroundColor = new Color("#17243a");
const title = w.addText("GCP 利用料金"); title.textColor = Color.white(); title.font = Font.boldSystemFont(15);
w.addSpacer(12);
const amount = w.addText("取得待ち"); amount.font = Font.boldSystemFont(25); amount.textColor = Color.white();
const detail = w.addText(""); detail.textColor = new Color("#a9b7cb"); detail.font = Font.systemFont(11);
if(API_URL && API_TOKEN){
 try{
  const req=new Request(API_URL);req.headers={"X-API-Key":API_TOKEN};req.timeoutInterval=15;
  const data=await req.loadJSON();
  if(data.total_month!==null && data.total_month!==undefined){
   amount.text= new Intl.NumberFormat("ja-JP",{style:"currency",currency:data.currency||"JPY"}).format(data.total_month);
  } else amount.text="反映待ち";
  detail.text=Object.values(data.accounts).map(a=>a.name+": "+(a.status==="ready"?a.month+" "+a.currency:"未取得")).join("\n");
 }catch(e){amount.text="取得エラー";detail.text="API接続を確認"}
}else{detail.text="API URLとトークンを設定してください"}
w.refreshAfterDate=new Date(Date.now()+60*60*1000);
Script.setWidget(w);if(!config.runsInWidget)await w.presentMedium();Script.complete();
