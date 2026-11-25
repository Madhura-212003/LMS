'use client';
import {useRef,useState,Dispatch,SetStateAction} from 'react';
import {createNavigationScope} from './navigation-scope';

/** Discard responses from another route/account rather than reopening its overlay. */
export function useNavigationState<T>(key:string,initial:T):[T,Dispatch<SetStateAction<T>>]{
 const owner=useRef<ReturnType<typeof createNavigationScope>|null>(null);
 if(!owner.current)owner.current=createNavigationScope();
 const scope=owner.current,token=scope.enter(key);
 const [state,setState]=useState({token,value:initial});
 const set:Dispatch<SetStateAction<T>>=update=>{
  if(!scope.owns(token))return;
  setState(previous=>{
   if(!scope.owns(token))return previous;
   const value=previous.token===token?previous.value:initial;
   return {token,value:typeof update==='function'?(update as (previous:T)=>T)(value):update};
  });
 };
 return [state.token===token?state.value:initial,set];
}
