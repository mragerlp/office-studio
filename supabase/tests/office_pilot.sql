-- Run in a disposable local database with the fixture first; rolled back at the end.
begin;
insert into auth.users(id) values ('00000000-0000-4000-8000-000000000001'),('00000000-0000-4000-8000-000000000002');
set local role authenticated;
select set_config('request.jwt.claim.sub','00000000-0000-4000-8000-000000000001',true);
select set_config('test.office_a',public.office_studio_create('Studio A','#285b53')::text,true);
select public.office_studio_upload(current_setting('test.office_a')::uuid,'00000000-0000-4000-8000-000000000011','same.txt','Private A');
select set_config('request.jwt.claim.sub','00000000-0000-4000-8000-000000000002',true);
select set_config('test.office_b',public.office_studio_create('Studio B','#334455')::text,true);
select public.office_studio_upload(current_setting('test.office_b')::uuid,'00000000-0000-4000-8000-000000000012','same.txt','Private B');
do $$begin
  if (select count(*) from public.office_studio_files)<>1 or
     (select content from public.office_studio_files)<>'Private B' or
     (select count(*) from public.office_studio_offices)<>1 or
     (select count(*) from public.office_studio_desks)<>3 then raise exception 'Row isolation failed'; end if;
  begin perform public.office_studio_upload(current_setting('test.office_a')::uuid,gen_random_uuid(),'bad.txt','wrong');
    raise exception 'Cross-office upload succeeded'; exception when insufficient_privilege then null; end;
  begin perform public.office_studio_remove_file(current_setting('test.office_a')::uuid,'00000000-0000-4000-8000-000000000011');
    raise exception 'Cross-office delete succeeded'; exception when insufficient_privilege then null; end;
  begin perform 1 from public.office_studio_connections;
    raise exception 'Credential table readable'; exception when insufficient_privilege then null; end;
  begin insert into public.office_studio_members values(current_setting('test.office_a')::uuid,auth.uid());
    raise exception 'Self-enrollment permitted'; exception when insufficient_privilege then null; end;
  begin perform public.office_studio_add_desk(current_setting('test.office_a')::uuid,gen_random_uuid(),'Other desk','Wrong office');
    raise exception 'Cross-office desk creation succeeded'; exception when insufficient_privilege then null; end;
end$$;
do $$declare b uuid:=current_setting('test.office_b')::uuid; new_id uuid:=gen_random_uuid(); i integer;
begin
  perform public.office_studio_add_desk(b,new_id,'Scheduling','Appointment requests');
  perform public.office_studio_add_desk(b,new_id,'Scheduling','Appointment requests');
  if (select count(*) from public.office_studio_desks)<>4 or not exists (
      select 1 from public.office_studio_desks where id=new_id and office_id=b and name='Scheduling'
        and position=4 and provider='demo') then raise exception 'Desk insert or retry failed';end if;
  begin perform public.office_studio_add_desk(b,gen_random_uuid(),' scheduling ','Backlog');
    raise exception 'Duplicate name accepted'; exception when unique_violation then null;end;
  for i in 5..10 loop perform public.office_studio_add_desk(b,gen_random_uuid(),'Desk '||i,'Operations');end loop;
  begin perform public.office_studio_add_desk(b,gen_random_uuid(),'Overflow','Operations');
    raise exception 'Eleventh desk allowed';exception when raise_exception then
     if sqlerrm <> 'The office already has ten desks' then raise;end if;end;
  if (select count(*) from public.office_studio_desks where name='Legal Review')<>1 then raise exception 'Legal seat lost';end if;
end$$;
reset role;
set local role service_role;
do $$declare a uuid:=current_setting('test.office_a')::uuid; b uuid:=current_setting('test.office_b')::uuid;
  d uuid; req uuid:='00000000-0000-4000-8000-000000000021'; file uuid:='00000000-0000-4000-8000-000000000011';
  first jsonb; second jsonb;
begin
  select id into d from public.office_studio_desks where office_id=a and name='Intake';
  first:=public.office_studio_reserve(a,req,d,file,'Brief','demo','');
  second:=public.office_studio_reserve(a,req,d,file,'Brief','demo','');
  if first->>'fresh'<>'true' or second->>'fresh'<>'false' then raise exception 'Duplicate reservation'; end if;
  begin perform public.office_studio_reserve(a,gen_random_uuid(),d,'00000000-0000-4000-8000-000000000012','bad','demo','');
    raise exception 'Cross-office source accepted'; exception when foreign_key_violation then null; end;
  update public.office_studio_runs set status='review',body='Prepared A' where id=req;
end$$;
reset role;
set local role authenticated;
do $$begin
 if exists(select 1 from public.office_studio_runs) then raise exception 'Cross-office draft readable';end if;
 begin perform public.office_studio_decide(current_setting('test.office_a')::uuid,'00000000-0000-4000-8000-000000000021','approved');
   raise exception 'Cross-office decision succeeded'; exception when insufficient_privilege then null;end;
end$$;
select set_config('request.jwt.claim.sub','00000000-0000-4000-8000-000000000001',true);
select public.office_studio_decide(current_setting('test.office_a')::uuid,'00000000-0000-4000-8000-000000000021','approved');
do $$begin
 if (select status from public.office_studio_runs)<>'approved' then raise exception 'Decision not recorded'; end if;
 begin perform public.office_studio_decide(current_setting('test.office_a')::uuid,'00000000-0000-4000-8000-000000000021','declined');
   raise exception 'Decision reversed'; exception when insufficient_privilege then null; end;
end$$;
select public.office_studio_remove_file(current_setting('test.office_a')::uuid,'00000000-0000-4000-8000-000000000011');
do $$begin if exists(select 1 from public.office_studio_runs) or exists(select 1 from public.office_studio_files) then
 raise exception 'Source/draft deletion failed'; end if;end$$;
do $$begin
 begin perform public.office_studio_upload(current_setting('test.office_a')::uuid,'00000000-0000-4000-8000-000000000011','same.txt','replacement');
   raise exception 'Retired file id was reused'; exception when unique_violation then null;end;
end$$;
select public.office_studio_upload(current_setting('test.office_a')::uuid,'00000000-0000-4000-8000-000000000014','new.txt','new content');
reset role;
set local role service_role;
do $$declare a uuid:=current_setting('test.office_a')::uuid; d uuid;
begin
 select id into d from public.office_studio_desks where office_id=a and name='Intake';
 begin perform public.office_studio_reserve(a,'00000000-0000-4000-8000-000000000021',d,'00000000-0000-4000-8000-000000000014','new','demo','');
   raise exception 'Retired run id reused'; exception when unique_violation then null;end;
 update public.office_studio_desks set provider='openai',model='fixture' where id=d;
 insert into public.office_studio_connections(office_id,provider,revision,sealed_key) values
   (a,'openai','00000000-0000-4000-8000-000000000031','synthetic test only');
 begin perform public.office_studio_reserve(a,gen_random_uuid(),d,'00000000-0000-4000-8000-000000000014','brief','openai','fixture','00000000-0000-4000-8000-000000000030');
   raise exception 'Stale key could reserve a run'; exception when raise_exception then
     if sqlerrm <> 'Connection changed' then raise; end if;end;
end$$;
reset role;
set local role anon;
do $$begin
 begin perform 1 from public.office_studio_files; raise exception 'Anonymous could read a file';
 exception when insufficient_privilege then null; end;
 begin perform public.office_studio_create('Anonymous','#334455');raise exception 'Anonymous created an office';
 exception when insufficient_privilege then null;end;
end$$;
rollback;
