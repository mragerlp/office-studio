"""Behavior checks for the real room adapter (Node optional; no network)."""
import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent


class RoomAlertTests(unittest.TestCase):
    def run_node(self, script):
        node = shutil.which("node")
        if not node:
            self.skipTest("Node is required for the room adapter behavior check.")
        result = subprocess.run([node, "-e", script, str(ROOT)], capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_full_adapter_executive_alerts_and_parent_isolation(self):
        script = r"""
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict'),path=require('node:path');
const root=process.argv[1],T=require(path.join(root,'assets','three-r128.min.js'));
const source=fs.readFileSync(path.join(root,'room_theme.js'),'utf8');
function boot({brand='#123456',later=false,legacy=false,seed=true}={}){
  const parent={},messages={},events={},reported=[];
  const color=new T.Color('#a70008').convertSRGBToLinear();
  const mat=(gain=1)=>({color:color.clone().multiplyScalar(gain),opacity:.25});
  const sculpture={group:{userData:{},children:[{geometry:{native:true}}]},base:color.clone(),fast:false,k:.3,phase:7,
    lacquer:{color:color.clone().multiplyScalar(.55),emissive:color.clone(),emissiveIntensity:.17},
    haloMat:mat(),topMat:mat(),poolMat:mat(),revealMat:mat(.7)};
  const nativeGeometry=sculpture.group.children[0].geometry;
  const names=later?['CRIMSON','HOST']:['CRIMSON','HOST'];
  const agents={crimson:{id:'crimson',name:'CRIMSON',specialty:later?'Service':'Chief of Staff',look:{color:'crimson'}},
    host:{id:'host',name:'HOST',specialty:later?'Chief of Staff':'Service',look:{color:'azure'}}};
  const rows=names.map((agent,i)=>({agent,title:i===(later?1:0)?'Head Executive':'Service desk',color:i===(later?1:0)?brand:'#abcdef',
    ...(!legacy?{executive:i===(later?1:0)}:{})}));
  const executive=later?'host':'crimson';
  const state={order:['crimson','host'],agents,approvals:seed?[{id:'seed',agentId:executive,simulated:true}]:[],tasks:[]};
  const presentation={name:'Synthetic office',color:brand,logo:'',agents:rows,studioOrigin:'http://127.0.0.1:8123'};
  const brandNode={querySelector:()=>null,prepend(){}};
  const document={getElementById:id=>id==='office-studio-presentation'?{textContent:JSON.stringify(presentation)}:null,
    querySelector:s=>s==='#topbar .brand'?brandNode:null,querySelectorAll:()=>[],documentElement:{dataset:{}},body:{}};
  const UI={bubbles:{},selected:'',select(id){this.selected=id;},hoverId:'',openManual(){},showAdd(){},renderRosterRow(){},renderBubble(){},renderGate(){}};
  const office={UI,OFFICE_STATE:state,ROOM_OBJ:{sculpture},THREE:T,WORLD:{byId:{}},VIEW:{dirty(){}}};
  const sandbox={document,AGENT_COLORS:{crimson:{main:'#a70008'},azure:{main:'#2369dd'}},requestAnimationFrame:f=>f(),
    MutationObserver:class{observe(){}},setTimeout(){},console,window:null};
  sandbox.window=sandbox;sandbox.parent=parent;sandbox.__office=office;sandbox.addEventListener=(type,fn)=>messages[type]=fn;
  sandbox.AgentOffice={on:(type,fn)=>(events[type]??=[]).push(fn)};
  parent.postMessage=(data,origin)=>{assert.equal(origin,presentation.studioOrigin);reported.push({...data});};
  vm.runInNewContext(source,sandbox);
  const send=(data,origin=presentation.studioOrigin,from=parent)=>messages.message({data,origin,source:from});
  const update=()=>{for(const f of events.approval||[])f({});};
  function expect(hex,fast){
    assert.equal(sculpture.fast,fast);
    const expected=new T.Color(hex).convertSRGBToLinear();
    for(const [actual,gain]of [[sculpture.base,1],[sculpture.lacquer.color,.55],[sculpture.lacquer.emissive,1],[sculpture.haloMat.color,1]]){
      const wanted=expected.clone().multiplyScalar(gain);
      assert.ok(Math.max(Math.abs(actual.r-wanted.r),Math.abs(actual.g-wanted.g),Math.abs(actual.b-wanted.b))<1e-10);
    }
    assert.equal(sculpture.group.children[0].geometry,nativeGeometry);
    assert.equal(sculpture.phase,7);assert.equal(sculpture.k,.3);
    assert.equal(sculpture.lacquer.emissiveIntensity,.17);assert.equal(sculpture.haloMat.opacity,.25);
  }
  return{sculpture,state,send,update,expect,brand,executive,sandbox,reported,UI};
}
let b=boot();
b.expect('#a70008',true); // Initial simulated executive gate is a real displayed approval.
const signal=pending=>({type:'office-studio:room-executive-alert',pending});
assert.deepEqual(b.reported,[signal(true)]);
const open={type:'office-studio:open-executive-alert'};
b.send(open,'https://example.org');b.send(open,undefined,{});b.send({...open,other:true});
assert.equal(b.UI.selected,'');
b.send(open);assert.equal(b.UI.selected,b.executive);
b.state.approvals=[];b.update();b.expect(b.brand,false);
const queue=b.state.approvals;
b.state.approvals=new Proxy(queue,{get:(target,key,receiver)=>{if(key==='some'||key==='find')throw Error('Per-frame approval scan');return Reflect.get(target,key,receiver);}});
for(let i=0;i<1000;i++)assert.equal(b.sculpture.fast,false);
b.state.approvals=queue;
b.send({type:'office-studio:review-signal',pending:true,executivePending:false});b.expect(b.brand,true);
b.send({type:'office-studio:review-signal',pending:true,executivePending:true});b.expect('#a70008',true);
b.send({type:'office-studio:review-signal',pending:false,executivePending:false});b.expect(b.brand,false);
assert.deepEqual(b.reported,[signal(true),signal(false)]); // No echo or repeated messages.
b.state.approvals=[{agentId:'host',simulated:false}];b.sculpture.fast=true;b.update();b.expect(b.brand,true);
b.state.approvals.push({agentId:'crimson',simulated:true});b.update();b.expect('#a70008',true);
b.state.approvals=b.state.approvals.filter(g=>g.agentId!=='crimson');b.update();b.expect(b.brand,true);
b.state.approvals=[];b.sculpture.fast=false;b.update();b.expect(b.brand,false);
for(const [data,origin,from]of [
 [{type:'office-studio:review-signal',pending:true,executivePending:true},'https://example.org',undefined],
 [{type:'office-studio:review-signal',pending:true,executivePending:'true'},undefined,undefined],
 [{type:'office-studio:review-signal',pending:true,executivePending:true,extra:1},undefined,undefined],
 [{type:'office-studio:review-signal',pending:true,executivePending:true},undefined,{}],
 [{type:'other',pending:true,executivePending:true},undefined,undefined]]){
 b.send(data,origin,from);b.expect(b.brand,false);
}
b.send({type:'office-studio:review-signal',pending:true});b.expect(b.brand,true); // Old parent remains generic.
b.send({type:'office-studio:review-signal',pending:false});b.expect(b.brand,false);
b=boot({later:true});b.expect('#a70008',true);
b.state.approvals=[{agentId:'crimson',simulated:true}];b.update();b.expect(b.brand,false); // Transport chief is not saved executive.
b.state.approvals.push({agentId:'host',simulated:true});b.update();b.expect('#a70008',true);
b=boot({legacy:true});b.expect('#a70008',true);
b=boot({brand:'#000000',seed:false});b.expect('#000000',false);
b.send({type:'office-studio:review-signal',pending:true,executivePending:true});b.expect('#a70008',true);
b.send({type:'office-studio:review-signal',pending:false,executivePending:false});b.expect('#000000',false);
console.log('Full adapter: seeded/native/host/mixed/legacy/later-executive/black-brand/isolation PASS');
"""
        self.run_node(script)

    def test_studio_header_combines_sources_and_drops_retired_room(self):
        self.run_node(r"""
const fs = require('node:fs'), vm = require('node:vm'), path = require('node:path');
const assert = require('node:assert/strict');
const elements = new Map(), handlers = {};
function element() {
  return {dataset:{}, events:{}, setAttribute(key,value){this[key]=value;}, replaceChildren(){}, append(){},
    addEventListener(type,handler){this.events[type]=handler;}};
}
function byId(id) {
  if (!elements.has(id)) elements.set(id,element());
  return elements.get(id);
}
const ctx = vm.createContext({
  document:{getElementById:byId,createElement:element}, window:{addEventListener(type,fn){handlers[type]=fn;}},
  URL, structuredClone, location:new URL('http://127.0.0.1:8000'), fetch:()=>new Promise(()=>{}),
});
vm.runInContext(fs.readFileSync(path.join(process.argv[1],'app.js'),'utf8'),ctx);
const studio = vm.runInContext('state',ctx), mark = byId('review-mark');
const chief = {name:'CHIEF',specialty:'Chief of Staff',appearance:{title:'Principal'}};
studio.workspace = {id:'office-one',crew:[{name:'DESK'},chief],drafts:[]};
const roomOrigin = 'http://127.0.0.1:8001';
function room() {
  return {src:roomOrigin+'/room/index.html',contentWindow:{postMessage(data,origin){this.sent={...data};assert.equal(origin,roomOrigin);}},
    focus(){this.focused=true;},remove(){this.removed=true;}};
}
const frame = room();
studio.roomFrameId=studio.workspace.id; studio.roomFrame=frame;
function notify(pending,source=frame.contentWindow,origin=roomOrigin,extra={}) {
  handlers.message({source,origin,data:{type:'office-studio:room-executive-alert',pending,...extra}});
}
function expect(red) {assert.equal(mark.dataset.executiveAlert,String(red));}
ctx.updateReviewMark(); expect(false);
notify(true,{});notify(true,frame.contentWindow,'https://example.org');notify('true');notify(true,undefined,undefined,{extra:0});expect(false);
notify(true);expect(true);assert.match(mark.title,/Principal.*3D office/);assert.equal(mark.dataset.active,'true');
mark.events.click();assert.equal(frame.focused,true);
assert.deepEqual(frame.contentWindow.sent,{type:'office-studio:open-executive-alert'});
studio.workspace.drafts.push({agent:'CHIEF',status:'pending',id:'example'});
notify(false);expect(true);assert.match(mark.title,/Principal.*inbox/);
notify(true);studio.workspace.drafts[0].status='approved';ctx.updateReviewMark();expect(true);
notify(false);expect(false);
studio.workspace.drafts.push({agent:'DESK',status:'pending'});ctx.updateReviewMark();expect(false);assert.equal(mark.dataset.active,'true');
notify(true);ctx.releaseRoomFrame();expect(false);assert.equal(frame.removed,true);
studio.workspace={id:'office-two',crew:[chief],drafts:[]};studio.roomFrameId='office-two';studio.roomFrame=room();
notify(true);expect(false);notify(true,studio.roomFrame.contentWindow);expect(true);
""")


if __name__ == "__main__":
    unittest.main()
