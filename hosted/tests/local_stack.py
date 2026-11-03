"""Exercise local Supabase Auth, PostgREST and the deployed draft function using generated users."""
import json
import secrets
import subprocess
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen
from uuid import uuid4

ORIGIN = "http://127.0.0.1:4173"


def main():
    settings = json.loads(subprocess.check_output(["supabase", "status", "-o", "json"]))
    origin = settings["API_URL"]
    if urlsplit(origin).hostname not in ("127.0.0.1", "localhost"):
        raise RuntimeError("Only a disposable local Supabase stack may run this test.")
    anon = settings["ANON_KEY"]
    service = settings["SERVICE_ROLE_KEY"]

    def call(path, data=None, *, token=None, admin=False, expect=(200, 201, 204)):
        key = service if admin else anon
        headers = {"apikey":key, "Authorization":"Bearer " + (token or key),
                   "Content-Type":"application/json", "Origin":ORIGIN}
        req = Request(origin+path, data=None if data is None else json.dumps(data).encode(), headers=headers)
        try:
            with urlopen(req,timeout=15) as result:
                code, raw = result.status,result.read()
        except HTTPError as exc:
            code,raw=exc.code,exc.read()
        if code not in expect:
            # Do not include response bodies, credentials or user session data in CI logs.
            raise AssertionError(f"{path.split('?')[0]} returned {code}; expected {expect}")
        return json.loads(raw) if raw else None

    def user():
        name = "pilot-" + uuid4().hex + "@example.test"
        password=secrets.token_urlsafe(30)
        call("/auth/v1/admin/users",{"email":name,"password":password,"email_confirm":True},admin=True)
        return call("/auth/v1/token?grant_type=password",{"email":name,"password":password})["access_token"]

    a,b=user(),user()
    def rpc(t,fn,data,**kw):
        return call("/rest/v1/rpc/office_studio_"+fn,data,token=t,**kw)
    def office(t,name):
        return rpc(t,"create",{"p_name":name,"p_color":"#285b53"})
    oa,ob=office(a,"Synthetic Pine"),office(b,"Synthetic Cedar")
    def upload(t,o,s):
        fid=str(uuid4())
        rpc(t,"upload",{"p_office":o,"p_id":fid,"p_name":"inquiry.txt","p_content":s})
        return fid
    fa=upload(a,oa,"Synthetic inquiry A: two Friday appointments.")
    fb=upload(b,ob,"Synthetic inquiry B: one Monday appointment.")
    assert fa!=fb
    assert call("/rest/v1/office_studio_files?select=id&id=eq."+fa,token=b)==[]
    assert call("/rest/v1/office_studio_files?select=id&id=eq."+fb,token=a)==[]
    ds=call("/rest/v1/office_studio_desks?select=id,name&office_id=eq."+oa,token=a)
    desk=next(row["id"] for row in ds if row["name"]=="Intake")
    run=str(uuid4())
    def edge(t,payload,**kw): return call("/functions/v1/office-drafts",payload,token=t,**kw)
    # Docker starts the Edge worker asynchronously. Keep retrying only its harmless status read.
    for attempt in range(30):
        try:
            if edge(a,{"action":"status","office":oa}) is not None: break
        except (URLError, AssertionError):
            if attempt==29: raise
            time.sleep(2)
    payload={"action":"draft","office":oa,"desk":desk,"file":fa,"provider":"demo","model":"",
             "brief":"Draft a reply.","run":run,"consent":False}
    edge(b,payload,expect=(403,))
    assert edge(a,payload)["status"]=="review"
    assert edge(a,payload)["status"]=="review"
    rpc(b,"decide",{"p_office":oa,"p_run":run,"p_decision":"approved"},expect=(400,403,404))
    rpc(a,"decide",{"p_office":oa,"p_run":run,"p_decision":"approved"})
    path="/rest/v1/office_studio_runs?select=body,status&id=eq."+run
    rows=call(path,token=a)
    assert len(rows)==1 and rows[0]["status"]=="approved"
    assert "Synthetic inquiry A" in rows[0]["body"] and "Synthetic inquiry B" not in rows[0]["body"]
    assert call(path,token=b)==[]
    rpc(a,"remove_file",{"p_office":oa,"p_file":fa})
    assert call(path,token=a)==[]
    print("PASS: two real local Auth sessions; same-name files isolated; wrong-office reads, runs and decisions denied; one sample draft on retry; approved output read and deletion verified.")


if __name__=="__main__":
    main()
