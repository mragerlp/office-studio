-- Office Studio hosted pilot. No native app tables or existing schema objects are reused.
begin;

create table public.office_studio_offices (
  id uuid primary key default gen_random_uuid(),
  owner_id uuid not null references auth.users(id) on delete cascade,
  name text not null check (length(trim(name)) between 1 and 100),
  color text not null default '#285b53' check (color ~ '^#[a-fA-F0-9]{6}$')
);
create table public.office_studio_members (
  office_id uuid not null references public.office_studio_offices on delete cascade,
  user_id uuid not null references auth.users on delete cascade,
  primary key (office_id, user_id)
);
create index office_studio_members_user on public.office_studio_members(user_id, office_id);
alter table public.office_studio_offices add constraint office_studio_owner_is_member
  foreign key (id,owner_id) references public.office_studio_members(office_id,user_id)
  deferrable initially deferred;
create table public.office_studio_desks (
  id uuid primary key default gen_random_uuid(),
  office_id uuid not null references public.office_studio_offices on delete cascade,
  name text not null check (length(trim(name)) between 1 and 60 and name !~ '[[:cntrl:]]'),
  specialty text not null check (length(trim(specialty)) between 1 and 120 and specialty !~ '[[:cntrl:]]'),
  position smallint not null check (position between 1 and 10),
  provider text not null default 'demo' check (provider in ('demo','openai','anthropic','gemini','meta')),
  model text not null default '',
  unique (office_id, position), unique (office_id, id),
  check ((provider = 'demo' and model = '') or (provider <> 'demo' and length(model) between 1 and 120))
);
create unique index office_studio_desk_names on public.office_studio_desks(office_id,lower(trim(name)));
create table public.office_studio_files (
  id uuid not null,
  office_id uuid not null references public.office_studio_offices on delete cascade,
  name text not null check (length(name) between 5 and 100 and lower(right(name,4)) = '.txt'
    and name !~ '[[:cntrl:]/]' and position(chr(92) in name) = 0),
  content text not null check (octet_length(content) between 1 and 65536 and length(trim(content)) > 0),
  created_at timestamptz not null default now(),
  primary key (office_id, id)
);
create index office_studio_files_office on public.office_studio_files(office_id, created_at);
create table public.office_studio_runs (
  id uuid not null,
  office_id uuid not null references public.office_studio_offices on delete cascade,
  desk_id uuid not null,
  file_id uuid not null,
  brief text not null check (length(trim(brief)) between 1 and 2000),
  provider text not null check (provider in ('demo','openai','anthropic','gemini','meta')),
  model text not null,
  status text not null check (status in ('preparing','review','approved','declined','failed')),
  body text check (octet_length(body) <= 98304),
  created_at timestamptz not null default now(),
  primary key (office_id,id),
  foreign key (office_id, desk_id) references public.office_studio_desks(office_id, id) on delete cascade,
  foreign key (office_id, file_id) references public.office_studio_files(office_id, id) on delete cascade,
  check ((status in ('preparing','failed') and body is null) or
         (status in ('review','approved','declined') and length(trim(body)) > 0 and body is not null))
);
create index office_studio_runs_office on public.office_studio_runs(office_id,created_at);
create table public.office_studio_connections (
  office_id uuid not null references public.office_studio_offices on delete cascade,
  provider text not null check (provider in ('openai','anthropic','gemini','meta')),
  primary key (office_id, provider),
  revision uuid not null default gen_random_uuid(),
  sealed_key text not null
);
-- Retain only spent identifiers after a file and its work have been deleted.
-- An old provider response must never be able to complete a new assignment.
create table public.office_studio_receipts (
  office_id uuid not null references public.office_studio_offices on delete cascade,
  kind text not null check (kind in ('file','run')),
  id uuid not null,
  primary key (office_id,kind,id)
);
revoke all on public.office_studio_receipts from public, anon, authenticated;
grant select, insert on public.office_studio_receipts to service_role;
alter table public.office_studio_receipts enable row level security;

-- Supabase projects can give anon/authenticated default privileges on new public tables.
-- Allow only the reads below; all writes have explicit callers and checks.
revoke all on public.office_studio_offices, public.office_studio_members, public.office_studio_desks,
  public.office_studio_files, public.office_studio_runs, public.office_studio_connections from public, anon, authenticated;
grant select on public.office_studio_offices, public.office_studio_members, public.office_studio_desks,
  public.office_studio_files, public.office_studio_runs to authenticated;
grant select,insert,update,delete on public.office_studio_offices, public.office_studio_members, public.office_studio_desks,
  public.office_studio_files, public.office_studio_runs, public.office_studio_connections to service_role;
alter table public.office_studio_offices enable row level security;
alter table public.office_studio_members enable row level security;
alter table public.office_studio_desks enable row level security;
alter table public.office_studio_files enable row level security;
alter table public.office_studio_runs enable row level security;
alter table public.office_studio_connections enable row level security;
create policy my_membership on public.office_studio_members for select to authenticated using (user_id=(select auth.uid()));
create policy my_offices on public.office_studio_offices for select to authenticated using
  (id in (select office_id from public.office_studio_members where user_id=(select auth.uid())));
create policy my_desks on public.office_studio_desks for select to authenticated using
  (office_id in (select office_id from public.office_studio_members where user_id=(select auth.uid())));
create policy my_files on public.office_studio_files for select to authenticated using
  (office_id in (select office_id from public.office_studio_members where user_id=(select auth.uid())));
create policy my_runs on public.office_studio_runs for select to authenticated using
  (office_id in (select office_id from public.office_studio_members where user_id=(select auth.uid())));

create function public.office_studio_create(p_name text, p_color text)
returns uuid language plpgsql security definer set search_path='' as $$
declare oid uuid; uid uuid := auth.uid();
begin
  if uid is null then raise exception 'Sign in required' using errcode='42501'; end if;
  perform pg_advisory_xact_lock(hashtextextended(uid::text,0));
  if (select count(*) from public.office_studio_offices where owner_id=uid) >= 12 then
    raise exception 'Office limit reached';
  end if;
  insert into public.office_studio_offices(name,color,owner_id) values (trim(p_name),p_color,uid) returning id into oid;
  insert into public.office_studio_members values (oid,uid);
  insert into public.office_studio_desks(office_id,name,specialty,position) values
    (oid,'Head Executive','Chief of Staff',1),(oid,'Intake','Intake and follow-up',2),(oid,'Legal Review','Legal Review',3);
  return oid;
end $$;

create function public.office_studio_add_desk(p_office uuid, p_id uuid, p_name text, p_specialty text)
returns uuid language plpgsql security definer set search_path='' as $$
declare next_position smallint;
begin
  if not exists(select 1 from public.office_studio_offices where id=p_office and owner_id=auth.uid() for update)
    then raise exception 'Office unavailable' using errcode='42501'; end if;
  if exists(select 1 from public.office_studio_desks where office_id=p_office and id=p_id
    and name=trim(p_name) and specialty=trim(p_specialty)) then return p_id; end if;
  select coalesce(max(position),0)+1 into next_position from public.office_studio_desks where office_id=p_office;
  if next_position>10 then raise exception 'The office already has ten desks'; end if;
  insert into public.office_studio_desks(office_id,id,name,specialty,position)
    values(p_office,p_id,trim(p_name),trim(p_specialty),next_position);
  return p_id;
end $$;
revoke all on function public.office_studio_add_desk(uuid,uuid,text,text) from public,anon,authenticated;
grant execute on function public.office_studio_add_desk(uuid,uuid,text,text) to authenticated;

create function public.office_studio_upload(p_office uuid, p_id uuid, p_name text, p_content text)
returns uuid language plpgsql security definer set search_path='' as $$
begin
  if not exists(select 1 from public.office_studio_offices where id=p_office and owner_id=auth.uid() for update)
    then raise exception 'Office unavailable' using errcode='42501'; end if;
  if exists(select 1 from public.office_studio_files where office_id=p_office and id=p_id and name=p_name and content=p_content)
    then return p_id; end if;
  if (select count(*) from public.office_studio_files where office_id=p_office) >= 64 then
    raise exception 'File limit reached'; end if;
  insert into public.office_studio_receipts values(p_office,'file',p_id);
  insert into public.office_studio_files(office_id,id,name,content) values(p_office,p_id,p_name,p_content);
  return p_id;
end $$;

create function public.office_studio_remove_file(p_office uuid, p_file uuid)
returns void language plpgsql security definer set search_path='' as $$
begin
  delete from public.office_studio_files f using public.office_studio_offices o
    where f.id=p_file and f.office_id=p_office and o.id=p_office and o.owner_id=auth.uid();
  if not found then raise exception 'File unavailable' using errcode='42501'; end if;
end $$;

create function public.office_studio_decide(p_office uuid, p_run uuid, p_decision text)
returns void language plpgsql security definer set search_path='' as $$
begin
  if p_decision not in ('approved','declined') or p_decision is null then raise exception 'Invalid decision'; end if;
  update public.office_studio_runs r set status=p_decision from public.office_studio_offices o
    where r.id=p_run and r.office_id=p_office and o.id=p_office and o.owner_id=auth.uid()
      and r.status in ('review',p_decision);
  if not found then raise exception 'Decision unavailable' using errcode='42501'; end if;
end $$;

revoke all on function public.office_studio_create(text,text), public.office_studio_upload(uuid,uuid,text,text),
  public.office_studio_remove_file(uuid,uuid), public.office_studio_decide(uuid,uuid,text) from public,anon,authenticated;
grant execute on function public.office_studio_create(text,text), public.office_studio_upload(uuid,uuid,text,text),
  public.office_studio_remove_file(uuid,uuid),public.office_studio_decide(uuid,uuid,text) to authenticated;
-- Reserve one immutable step before contacting a billable provider. Only the
-- authenticated Edge Function invokes this service-role RPC after owner checks.
create function public.office_studio_reserve(p_office uuid, p_id uuid, p_desk uuid, p_file uuid,
  p_brief text, p_provider text, p_model text, p_connection uuid default null)
returns jsonb language plpgsql security invoker set search_path='' as $$
declare prior public.office_studio_runs%rowtype;
begin
  perform 1 from public.office_studio_offices where id=p_office for update;
  select * into prior from public.office_studio_runs where id=p_id and office_id=p_office;
  if found then
    if (prior.desk_id,prior.file_id,prior.brief,prior.provider,prior.model)
        is distinct from (p_desk,p_file,p_brief,p_provider,p_model) then raise exception 'Request already used'; end if;
    if prior.status='preparing' and prior.created_at < now()-interval '3 minutes' then
      update public.office_studio_runs set status='failed' where office_id=p_office and id=p_id and status='preparing';
      return jsonb_build_object('fresh',false,'status','failed');
    end if;
    return jsonb_build_object('fresh',false,'status',prior.status);
  end if;
  if (select count(*) from public.office_studio_runs where office_id=p_office) >= 256 then
    raise exception 'Draft limit reached'; end if;
  if not exists(select 1 from public.office_studio_desks d where d.office_id=p_office and d.id=p_desk
    and d.provider=p_provider and d.model=p_model for share) then raise exception 'Desk route changed'; end if;
  if p_provider<>'demo' and not exists(select 1 from public.office_studio_connections c
    where c.office_id=p_office and c.provider=p_provider and c.revision=p_connection for share) then raise exception 'Connection changed'; end if;
  insert into public.office_studio_receipts values(p_office,'run',p_id);
  insert into public.office_studio_runs(id,office_id,desk_id,file_id,brief,provider,model,status)
    values(p_id,p_office,p_desk,p_file,p_brief,p_provider,p_model,'preparing');
  return jsonb_build_object('fresh',true,'status','preparing');
end $$;
revoke all on function public.office_studio_reserve(uuid,uuid,uuid,uuid,text,text,text,uuid) from public,anon,authenticated;
grant execute on function public.office_studio_reserve(uuid,uuid,uuid,uuid,text,text,text,uuid) to service_role;
commit;
