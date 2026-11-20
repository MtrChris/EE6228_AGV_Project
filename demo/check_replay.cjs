/* Dependency-free replay data and UI-logic checks; this does not render a browser. */
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const html = fs.readFileSync(path.join(__dirname,"../replay/EE6228_AGV_Replay.html"),"utf8");
const summary = JSON.parse(fs.readFileSync(path.join(__dirname,"results/summary.json"),"utf8"));
const scripts = [...html.matchAll(/<script[^>]*>([\s\S]*?)<\/script>/g)];
const events = JSON.parse(scripts[0][1]);
assert.equal(scripts.length,2);
assert.ok(!/<(?:script|link|img)\b[^>]*(?:src|href)=/i.test(html));

class Element {
  constructor(){this.children=[];this.attrs={};this.style={};this.textContent="";this.value="";
    this.classList={toggle:(name,active)=>{this[name]=active;}};}
  append(...items){this.children.push(...items);}
  setAttribute(key,value){this.attrs[key]=value;}
  replaceChildren(){this.children=[];}
  insertRow(){const item=new Element();this.append(item);return item;}
  insertCell(){return this.insertRow();}
}
const elements=Object.fromEntries([...html.matchAll(/\bid="([^"]+)"/g)].map(m=>[m[1],new Element()]));
const el=id=>elements[id], click=id=>el(id).onclick(), label=id=>el(id).textContent;
el("rule").value="junction";el("policy").value="paired";el("speed").value="20";
el("events").textContent=scripts[0][1];
let nextFrame;
vm.runInContext(scripts[1][1], vm.createContext({
  document:{getElementById:el,createElementNS:()=>new Element(),createElement:()=>new Element(),createTextNode:text=>text},
  requestAnimationFrame:fn=>{nextFrame=fn;return 1;},cancelAnimationFrame:()=>{nextFrame=null;}
}));
function seek(time){el("seek").value=time;el("seek").oninput();}
function select(rule,policy){el("rule").value=rule;el("policy").value=policy;el("policy").onchange();}
const fmt=n=>n.toLocaleString("en-US");
const edges = new Map(events.edges.map(([a,b,s])=>[a+" "+b,s]));
for (const {rule,policy,makespan_s,last_home_s,trips,shared_passes,drive_s} of summary.cases){
  const entry = events.rules[rule].cases[policy];
  const scheduleFile=path.join(__dirname,"results",rule,policy,"job_schedule.csv");
  const jobs=fs.readFileSync(scheduleFile,"utf8").trim().split(/\r?\n/).slice(1).map(row=>row.split(","));
  const completion=jobs.map(row=>[Number(row[7]),row[0],row[1]]).sort((a,b)=>a[0]-b[0]||a[1].localeCompare(b[1]));
  assert.deepEqual(entry.done,completion);
  assert.equal(new Set(completion.map(row=>row[1])).size,100);
  assert.equal(entry.trips,trips);assert.equal(entry.road.length,shared_passes);
  assert.equal(entry.road.every((event,i,arr)=>i===0||arr[i-1][1]<=event[0]),true);
  let traversals=0, journey=0;
  for(const sequences of Object.values(entry.cars)){
    traversals+=sequences.length;
    for(const visits of sequences) {
      for(let i=1;i<visits.length;i++) {
        const a=visits[i-1],b=visits[i], duration=b[1]-a[2];
        assert.equal(duration,edges.get(a[0]+" "+b[0]));
        journey+=duration;
      }
    }
  }
  assert.equal(traversals,trips);assert.equal(journey,drive_s);
  select(rule,policy);
  assert.equal(label("done"),"0 / 100");
  assert.equal(label("end"),fmt(makespan_s)+" s");assert.equal(label("back"),fmt(last_home_s)+" s");
  assert.equal(el("seek").max,last_home_s);
  assert.equal(el("pairClip").disabled,!entry.clips.pair);
  assert.equal(el("roadClip").disabled,!entry.clips.road);
  for(const [time] of completion){
    seek(time-1);assert.equal(label("done"),completion.filter(row=>row[0]<time).length+" / 100");
    seek(time);assert.equal(label("done"),completion.filter(row=>row[0]<=time).length+" / 100");
    assert.ok(el("cars").children.every(car=>/^translate\([\d.]+,[\d.]+\)$/.test(car.attrs.transform)));
  }
  click("finish");assert.equal(label("done"),"100 / 100");
  click("home");assert.ok(el("vehicles").children.every(card=>card.children[1].textContent.includes("returned to depot")));
  if(entry.clips.road){
    click("roadClip"); const [first,second]=entry.clips.road;
    seek(first[0]);assert.ok(label("roadState").includes(first[2]));
    seek(first[1]);if(first[1]<second[0])assert.ok(label("roadState").includes("clear"));
    seek(second[0]);assert.ok(label("roadState").includes(second[2]));
  }
  if(entry.clips.pair){
    click("pairClip");const clip=entry.clips.pair;
    assert.ok(label("clipInfo").includes(clip[3])&&label("clipInfo").includes(clip[4]));
    el("speed").value="180";click("play");
    for(let k=0;nextFrame&&k<300;k++) nextFrame(k*100);
    assert.equal(label("play"),"Play");
    assert.ok(label("clock").startsWith(fmt(clip[1]+16)+" / "));
  }
}
select("original","baseline");click("play");assert.equal(label("play"),"Pause");click("play");
assert.equal(nextFrame,null);
click("restart");assert.equal(label("done"),"0 / 100");
console.log("PASS: 8 configurations, all completion boundaries, CSV/UI agreement, motion coordinates, toggles, clip transitions, speed and stop.");
