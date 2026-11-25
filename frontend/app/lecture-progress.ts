export type LectureProgressSave={position:number;completed:boolean;notes?:string};

// Preserve event order, while allowing a later explicit retry after a failed save.
export function createProgressQueue<T>(send:(snapshot:LectureProgressSave)=>Promise<T>){
 let pending:Promise<unknown>=Promise.resolve();
 return (snapshot:LectureProgressSave)=>{
  const result=pending.catch(()=>undefined).then(()=>send(snapshot));
  pending=result;
  return result;
 };
}
