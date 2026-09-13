-- Run once in the dedicated Aaniang Supabase project SQL editor.
create table if not exists public.investment_notebooks (
  user_id uuid primary key references auth.users(id) on delete cascade,
  payload jsonb not null,
  version bigint not null default 1,
  updated_at timestamptz not null default now(),
  check (jsonb_typeof(payload) = 'object' and octet_length(payload::text) <= 2000000)
);
alter table public.investment_notebooks enable row level security;
revoke all on public.investment_notebooks from anon;
grant select, insert, update on public.investment_notebooks to authenticated;
create policy "Read own notebook" on public.investment_notebooks for select to authenticated using ((select auth.uid()) = user_id);
create policy "Insert own notebook" on public.investment_notebooks for insert to authenticated with check ((select auth.uid()) = user_id);
create policy "Update own notebook" on public.investment_notebooks for update to authenticated using ((select auth.uid()) = user_id) with check ((select auth.uid()) = user_id);

create or replace function public.save_investment_notebook(expected_version bigint, new_payload jsonb)
returns bigint language plpgsql security invoker set search_path = '' as $$
declare result_version bigint;
begin
  if auth.uid() is null then raise exception 'authentication_required'; end if;
  if expected_version = 0 then
    insert into public.investment_notebooks(user_id,payload) values(auth.uid(),new_payload)
      on conflict(user_id) do nothing returning version into result_version;
  else
    update public.investment_notebooks set payload=new_payload, version=version+1, updated_at=now()
      where user_id=auth.uid() and version=expected_version returning version into result_version;
  end if;
  if result_version is null then raise exception 'notebook_conflict'; end if;
  return result_version;
end; $$;
revoke all on function public.save_investment_notebook(bigint,jsonb) from public, anon;
grant execute on function public.save_investment_notebook(bigint,jsonb) to authenticated;
