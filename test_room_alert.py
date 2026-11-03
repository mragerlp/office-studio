"""Behavior checks for the real room adapter (Node optional; no network)."""
import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent


class RoomAlertTests(unittest.TestCase):
    def test_full_adapter_executive_alerts_and_parent_isolation(self):
        node = shutil.which("node")
        if not node:
            self.skipTest("Node is required for the room adapter behavior check.")
        script = r"""
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict'),path=require('node:path');
const root=process.argv[1],T=require(path.join(root,'assets','three-r128.min.js'));
const source=fs.readFileSync(path.join(root,'room_theme.js'),'utf8');
function boot({brand='#123456',later=false,legacy=false,seed=true}={}){
  const parent={},messages={},events={};
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
  const UI={bubbles:{},selected:'',hoverId:'',openManual(){},showAdd(){},renderRosterRow(){},renderBubble(){},renderGate(){}};
  const office={UI,OFFICE_STATE:state,ROOM_OBJ:{sculpture},THREE:T,WORLD:{byId:{}},VIEW:{dirty(){}}};
  const sandbox={document,AGENT_COLORS:{crimson:{main:'#a70008'},azure:{main:'#2369dd'}},requestAnimationFrame:f=>f(),
    MutationObserver:class{observe(){}},setTimeout(){},console,window:null};
  sandbox.window=sandbox;sandbox.parent=parent;sandbox.__office=office;sandbox.addEventListener=(type,fn)=>messages[type]=fn;
  sandbox.AgentOffice={on:(type,fn)=>(events[type]??=[]).push(fn)};
  parent.postMessage=()=>{};
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
  return{sculpture,state,send,update,expect,brand,executive,sandbox};
}
let b=boot();
b.expect('#a70008',true); // Initial simulated executive gate is a real displayed approval.
b.state.approvals=[];b.update();b.expect(b.brand,false);
const queue=b.state.approvals;
b.state.approvals=new Proxy(queue,{get:(target,key,receiver)=>{if(key==='some')throw Error('Per-frame approval scan');return Reflect.get(target,key,receiver);}});
for(let i=0;i<1000;i++)assert.equal(b.sculpture.fast,false);
b.state.approvals=queue;
b.send({type:'office-studio:review-signal',pending:true,executivePending:false});b.expect(b.brand,true);
b.send({type:'office-studio:review-signal',pending:true,executivePending:true});b.expect('#a70008',true);
b.send({type:'office-studio:review-signal',pending:false,executivePending:false});b.expect(b.brand,false);
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
        result = subprocess.run([node, "-e", script, str(ROOT)], capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("isolation PASS", result.stdout)


if __name__ == "__main__":
    unittest.main()
