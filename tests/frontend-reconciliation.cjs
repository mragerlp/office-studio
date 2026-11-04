// Disposable real-server/Chromium regressions. No credentials or outside network.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const {spawn, execFileSync} = require('node:child_process');
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const root = path.resolve(__dirname, '..');
const selected = process.argv[2];
const report = [];
const wait = ms => new Promise(resolve => setTimeout(resolve, ms));
function fixture(name) {
  return {name, town:'Fictional town', practice:'Guest house', color:'#000000', logo:'', rules:'Owner reviews all outside actions.',
    crew:[{name:'CRIMSON',specialty:'Chief of Staff',instruction:'Prepare plans for owner review.'},
      {name:'GUEST DESK',specialty:'Guest communications',instruction:'Prepare guest replies for owner review.'}],
    gates:[{owner:'CRIMSON',need:'Owner approval for outside actions',brief:{action:'Record owner decision.',ifDecline:'Keep here.'}}]};
}
function luminance(rgb) {
  const c = rgb.match(/[\d.]+/g).slice(0,3).map(Number).map(n=>n/255).map(n=>n<=.04045?n/12.92:((n+.055)/1.055)**2.4);
  return c[0]*.2126+c[1]*.7152+c[2]*.0722;
}
async function main() {
  const scratch = fs.mkdtempSync(path.join(os.tmpdir(),'office-ui-reconcile-'));
  const python = process.env.PYTHON || execFileSync('py',['-3','-c','import sys; print(sys.executable)'],{encoding:'utf8'}).trim();
  const env = {...process.env};
  for (const key of Object.keys(env)) if (/API_KEY|^OFFICE_.*MODEL|^OFFICE_STUDIO_ROOM_FILE/.test(key)) delete env[key];
  const server = spawn(python,['-B',path.join(root,'launch.py'),'--port','0','--data-dir',scratch,'--no-browser'],{cwd:root,env,windowsHide:true});
  let output=''; server.stdout.on('data',d=>output+=d); server.stderr.on('data',d=>output+=d);
  let browser;
  try {
    for(let i=0;i<150&&!/Office Studio: (http:\/\/127\.0\.0\.1:\d+\/)/.test(output);i++) await wait(100);
    const origin = output.match(/Office Studio: (http:\/\/127\.0\.0\.1:\d+\/)/)?.[1];
    assert.ok(origin,'isolated server started: '+output);
    browser = await chromium.launch({executablePath:process.env.CHROME_PATH,headless:process.env.UI_VISIBLE!=='1',args:['--use-angle=swiftshader','--enable-unsafe-swiftshader']});
    async function api(route,body) {
      const response=await fetch(new URL(route,origin),{method:body?'POST':'GET',headers:body?{'Content-Type':'application/json'}:{},body:body?JSON.stringify(body):undefined});
      const value=await response.json(); assert.ok(response.ok,JSON.stringify(value)); return value;
    }
    async function officePage(office,options={}) {
      const {room=false,...contextOptions}=options;
      const context=await browser.newContext({viewport:{width:1280,height:900},reducedMotion:'reduce',...contextOptions});
      await context.route('**/*',route=>new URL(route.request().url()).hostname==='127.0.0.1'?route.continue():route.abort());
      // These cases exercise host UI; the dedicated WebGL case exercises the renderer.
      if(!room)await context.route('**/api/workspaces/*/room',route=>route.fulfill({contentType:'application/json',body:'{"url":null}'}));
      const page=await context.newPage();
      await page.goto(origin+'#office/'+office.id);
      await page.waitForFunction(id=>document.querySelector('#workspace-select').value===id&&!document.querySelector('#workspace').hidden,office.id);
      return {page,context};
    }
    async function draft(office,agent,brief) {return api('/api/workspaces/'+office.id+'/drafts',{provider:'demo',model:'',agent,brief,requestId:crypto.randomUUID()});}
    async function decide(office,d,decision) {return api(`/api/workspaces/${office.id}/drafts/${d.id}/decision`,{decision});}
    const tests = {
      async contrast() {
        const context=await browser.newContext({colorScheme:'light'}),page=await context.newPage();
        await page.goto(origin);
        for(const mode of ['light','dark']) {
          if(await page.locator('#appearance-toggle').getAttribute('aria-checked')!==String(mode==='dark'))
            await page.locator('#appearance-toggle').click();
          await page.waitForFunction(mode=>document.documentElement.dataset.appearance===mode,mode);
          for(const color of ['#000000','#ffffff','#33ccff','#0000ff','#285f55']) {
            await page.locator('#office-color').fill(color);
            const observed=await page.locator('.brand-symbol').evaluate(mark=>({fill:getComputedStyle(mark).backgroundColor,background:getComputedStyle(document.documentElement).backgroundColor,
              shadow:getComputedStyle(mark).boxShadow,filter:getComputedStyle(mark).filter,tile:getComputedStyle(mark.parentElement).backgroundColor}));
            const [hi,lo]=[luminance(observed.fill),luminance(observed.background)].sort((a,b)=>b-a),ratio=(hi+.05)/(lo+.05);
            report.push({mode,color,...observed,contrast:ratio});
            assert.ok(ratio>=3,`${mode} ${color} contrast ${ratio}`);
            assert.equal(observed.shadow,'none'); assert.equal(observed.filter,'none'); assert.equal(observed.tile,'rgba(0, 0, 0, 0)');
          }
        }
        await context.close();
      },
      async stale() {
        let a=await api('/api/workspaces',fixture('Birch Demo')), b=await api('/api/workspaces',fixture('Cedar Demo'));
        a=await draft(a,'GUEST DESK','Distinctive Birch draft'); a=await decide(a,a.drafts.at(-1),'approved');
        const {page,context}=await officePage(a);
        await page.locator('#view-desks').click();
        assert.match(await page.locator('#preview-text').textContent(),/Distinctive Birch draft/);
        await page.locator('#workspace-select').selectOption(b.id);
        await page.waitForFunction(()=>document.querySelector('#workspace-title').textContent==='Cedar Demo');
        for(const id of ['preview-text','preview-brief','preview-agent','preview-source','preview-provider','preview-status','decision-note'])
          assert.equal(await page.locator('#'+id).textContent(),'','previous office retained in '+id);
        assert.equal(await page.locator('#download-draft').getAttribute('href'),null);
        await context.close();
      },
      async retry() {
        const a=await api('/api/workspaces',fixture('Retry Demo')),{page,context}=await officePage(a);
        await page.locator('#view-desks').click();
        let calls=0; const sent=[];
        await page.route('**/api/workspaces/*/drafts',async route=>{
          sent.push(route.request().postDataJSON()); calls++;
          if(calls===1){await route.fetch(); await route.abort('failed');}else await route.continue();
        });
        await page.locator('#draft-brief').fill('Prepare a brief-only fictional note.');
        await page.locator('#draft-form button[type="submit"]').click();
        await page.waitForFunction(()=>document.querySelector('#draft-feedback').textContent!=='Preparing your draft…');
        await page.locator('#draft-form button[type="submit"]').click();
        await page.waitForFunction(()=>document.querySelector('#draft-feedback').textContent==='Ready in your approval inbox.');
        const saved=await api('/api/workspaces/'+a.id);
        assert.equal(saved.drafts.length,1,'uncertain retry must return original draft');
        assert.ok(sent[0].requestId); assert.equal(sent[0].requestId,sent[1].requestId);
        assert.equal(saved.drafts[0].requestId,sent[0].requestId);
        report.push({retryRequestId:sent[0].requestId,drafts:saved.drafts.length});
        await context.close();
      },
      async keyboard() {
        let a=await api('/api/workspaces',fixture('Keyboard Demo'));
        a=await draft(a,'GUEST DESK','First keyboard draft'); a=await draft(a,'GUEST DESK','Second keyboard draft');
        const {page,context}=await officePage(a);
        await page.locator('#view-desks').click();
        await page.locator('#draft-list button').last().focus(); await page.keyboard.press('Enter');
        assert.equal(await page.evaluate(()=>document.activeElement.id),'preview-brief','selected row must not lose keyboard focus into body');
        assert.equal(await page.locator('#preview-brief').textContent(),'First keyboard draft');
        await page.keyboard.press('Tab'); assert.equal(await page.evaluate(()=>document.activeElement.id),'approve-draft');
        await context.close();
      },
      async webgl() {
        const a=await api('/api/workspaces',fixture('No WebGL Demo'));
        const context=await browser.newContext();
        await context.addInitScript(()=>{const original=HTMLCanvasElement.prototype.getContext;HTMLCanvasElement.prototype.getContext=function(kind,...args){return /webgl/.test(kind)?null:original.call(this,kind,...args);};});
        const page=await context.newPage(); await page.goto(origin+'#office/'+a.id);
        await page.waitForFunction(()=>document.querySelector('#room-availability').textContent.includes('could not open'),{},{timeout:40000});
        assert.equal(await page.locator('#desk-workspace').isVisible(),true);
        assert.equal(await page.locator('#room-stage').isVisible(),false);
        report.push({webgl:await page.locator('#room-availability').textContent()});
        await context.close();
      },
      async alerts() {
        let a=await api('/api/workspaces',fixture('Alert Demo'));
        const {page,context}=await officePage(a);
        const check=async value=>{await page.reload();await page.waitForFunction(expected=>document.querySelector('#review-mark').dataset.executiveAlert===String(expected),value);};
        await check(false);
        a=await draft(a,'GUEST DESK','Guest pending'); await check(false);
        a=await draft(a,'CRIMSON','Executive first'); const first=a.drafts.at(-1);
        a=await draft(a,'CRIMSON','Executive second'); const second=a.drafts.at(-1);
        await check(true); await page.locator('#review-mark').click();
        assert.equal(await page.locator('#preview-brief').textContent(),'Executive first');
        a=await decide(a,first,'approved'); await check(true);
        a=await decide(a,second,'declined'); await check(false);
        assert.equal(a.drafts.find(d=>d.agent==='GUEST DESK').status,'pending');
        await context.close();
      },
      async delivered() {
        let a=await api('/api/workspaces',fixture('Delivered Demo'));
        const base='/api/workspaces/'+a.id;
        const {file}=await api(base+'/files',{name:'friday-inquiry.txt',content:fs.readFileSync(path.join(root,'examples/friday-inquiry.txt'),'utf8')});
        a=await api(base+'/drafts',{provider:'demo',model:'',agent:'GUEST DESK',brief:'Draft a short reply asking for their preferred time on Friday afternoon. Leave availability unconfirmed.',fileId:file.id,fileVersion:file.version,requestId:crypto.randomUUID()});
        const d=a.drafts.at(-1); a=await decide(a,d,'approved');
        a=await api(base+'/agents/appearance',{agent:'GUEST DESK',title:'Guest Welcome',color:'#2369dd'});
        const {page,context}=await officePage(a,{room:true});
        const errors=[];page.on('pageerror',e=>errors.push(e.message));
        for(let pass=0;pass<2;pass++) {
          if(pass)await page.reload();
          await page.waitForFunction(()=>document.querySelector('#room-availability').textContent==='3D office · simulated activity',null,{timeout:45000});
          const frame=page.frameLocator('#room-frames iframe');
          await frame.locator('button.row').filter({hasText:'Guest Welcome'}).click();
          await frame.getByRole('button',{name:'View approved drafts',exact:true}).click();
          await page.locator('#desk-history-list button').click();
          assert.equal(await page.locator('#preview-status').textContent(),'approved');
          assert.match(await page.locator('#preview-text').textContent(),/What time on Friday afternoon/);
          assert.equal(await page.locator('#preview-source').textContent(),'Source file: friday-inquiry.txt · '+file.version.slice(0,8));
          assert.match(await page.locator('#preview-agent').textContent(),/GUEST DESK/);
          assert.match(await page.locator('#decision-note').textContent(),/Approval recorded here/);
        }
        assert.deepEqual(errors,[]);
        report.push({deliveredDraft:d.id,stableDesk:d.agent,source:file.version,reload:true,rendererErrors:errors});
        await context.close();
      }
    };
    const failures=[];
    for(const [name,test] of Object.entries(tests)) {
      if(selected&&selected!==name)continue;
      try {await test();console.log('PASS '+name);}catch(e){failures.push(name);console.error('FAIL '+name+': '+e.stack);}
      finally {for(const context of browser.contexts())await context.close();}
    }
    console.log(JSON.stringify({browser:await browser.version(),platform:process.platform,arch:process.arch,headless:process.env.UI_VISIBLE!=='1',report,failures},null,2));
    if(failures.length) process.exitCode=1;
  } finally {
    if(browser)await browser.close();
    server.kill(); await new Promise(resolve=>server.exitCode!==null?resolve():server.once('exit',resolve));
    fs.rmSync(scratch,{recursive:true,force:true});
  }
}
main().catch(e=>{console.error(e);process.exitCode=1;});
