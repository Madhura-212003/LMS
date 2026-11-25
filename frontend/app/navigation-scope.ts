/** An async screen result belongs to one visit, including when a route is revisited. */
export function createNavigationScope(){
 let current={key:'',visit:0};
 return {
  enter(key:string){if(current.key!==key)current={key,visit:current.visit+1};return current;},
  owns(token:ReturnType<typeof this.enter>){return current===token;}
 };
}
