export type Row = Record<string, any> & {id:string};
export class APIError extends Error {constructor(public status:number,message:string){super(message)}}
export async function api<T=any>(path:string,method='GET',body?:unknown):Promise<T>{
  let response:Response;
  try { response=await fetch('/v1'+path,{method,credentials:'same-origin',headers:{'Content-Type':'application/json','X-Campus-Request':'1'},body:body===undefined?undefined:JSON.stringify(body)}); }
  catch { throw new APIError(0,'Cannot reach the server. Check your connection and try again.'); }
  if(response.status===204)return undefined as T;
  const result=await response.json().catch(()=>({detail:'The server could not complete this request.'}));
  if(!response.ok){
    const detail=Array.isArray(result.detail)?result.detail.map((x:any)=>`${x.loc?.slice(1).join('.')}: ${x.msg}`).join('; '):result.detail;
    throw new APIError(response.status,detail||'Request failed');
  }
  return result;
}
export async function list(path:string):Promise<Row[]>{
  const result:Row[]=[];
  for(let offset=0;;offset+=100){
    const batch=await api<Row[]>(`${path}${path.includes('?')?'&':'?'}limit=100&offset=${offset}`);
    result.push(...batch);if(batch.length<100)return result;
  }
}
export const unique=(items:Row[])=>[...new Map(items.map(x=>[x.id,x])).values()];
export type Workspace={unread:number;me:Row;clubs:Row[];openings:Row[];events:Row[];projects:Row[];teams:Row[];applications:Row[];requests:Row[];registrations:Row[];follows:Row[];saved:Row[];announcements:Row[];notifications:Row[];memberships:Row[];members:Row[];students:Row[];users:Row[];audit:Row[];teamMembers:Row[];rosters:Row[];coordinatorRequests:Row[]};
export async function workspace(page='Home'):Promise<Workspace>{
  const me=await api<Row>('/me');
  const [clubs,openings,events,projects,teams,applications,requests,registrations,follows,saved,announcements,notifications,memberships,students,ownProjects,ownEvents,users,audit]=await Promise.all([
    list(me.admin?'/admin/clubs':'/clubs'),list('/recruitments'),list(me.admin?'/admin/events':'/events'),list(me.admin?'/admin/projects':'/projects'),list('/teams'),list('/me/applications'),list('/me/team-requests'),list('/me/registrations'),list('/me/follows'),list('/me/saved-projects'),list('/announcements'),api<Row[]>('/notifications?limit=50'),api<Row[]>('/me/memberships'),['Manage','Admin'].includes(page)?list('/students'):[] as Row[],list('/me/projects'),list('/me/events'),me.admin&&page==='Admin'?list('/admin/users'):[],me.admin&&page==='Admin'?list('/admin/audit'):[]
  ]);
  const managed=page==='Manage'?clubs.filter(c=>me.admin||memberships.some(m=>m.club_id===c.id&&m.role==='coordinator')):[];
  const privateData=await Promise.all(managed.map(async c=>{
    const [rs,es,ms]=await Promise.all([list(`/clubs/${c.id}/recruitments`),list(`/clubs/${c.id}/events`),list(`/clubs/${c.id}/members`)]);
    const apps=await Promise.all(rs.map(r=>list(`/recruitments/${r.id}/applications`)));
    const rosters=await Promise.all(es.map(e=>list(`/events/${e.id}/registrations`)));
    return {rs,es,ms,apps:apps.flat(),rosters:rosters.flat()};
  }));
  const ownTeams=page==='My dashboard'?teams.filter(t=>t.owner_id===me.id):[];
  const incoming=(await Promise.all(ownTeams.map(t=>list(`/teams/${t.id}/requests`)))).flat();
  const joinedIds=new Set([...ownTeams.map(t=>t.id),...requests.filter(r=>r.status==='accepted').map(r=>r.team_id)]);
  const teamMembers=(await Promise.all([...joinedIds].map(id=>list(`/teams/${id}/members`)))).flat();
  const coordinatorRequests=await list(me.admin?"/admin/coordinator-requests":"/me/coordinator-requests");
  // Fetch only names referenced by loaded records, not the entire student directory.
  const known=new Set(students.map(u=>u.id));
  const ids=[...new Set([...teams.map(t=>t.owner_id),...projects.map(p=>p.owner_id),...incoming.map(r=>r.user_id),...teamMembers.map(m=>m.user_id)])].filter(id=>id&&!known.has(id));
  for(let i=0;i<ids.length;i+=100)students.push(...await api<Row[]>('/people?ids='+encodeURIComponent(ids.slice(i,i+100).join(','))));
  const summary=await api<{unread:number}>('/notifications/summary');
  return {unread:summary.unread,coordinatorRequests,me,clubs,openings:unique([...openings,...privateData.flatMap(d=>d.rs)]),events:unique([...events,...ownEvents,...privateData.flatMap(d=>d.es)]),projects:unique([...projects,...ownProjects]),teams,applications:unique([...applications,...privateData.flatMap(d=>d.apps)]),requests:unique([...requests,...incoming]),registrations,follows,saved,announcements,notifications,memberships,members:privateData.flatMap(d=>d.ms),students,users,audit,teamMembers,rosters:privateData.flatMap(d=>d.rosters)};
}
