'use client';
import {Children,cloneElement,createContext,isValidElement,ReactElement,ReactNode,useContext,useEffect,useState} from 'react';
import {translations} from './translations';
type Locale='en'|'hi'|'kn';
const LocaleContext=createContext<Locale>('en');
export function LocaleProvider({children}:{children:ReactNode}){
 const [locale,setLocale]=useState<Locale>('en');
 useEffect(()=>{const refresh=()=>{void fetch('/api/lms/features/preferences').then(r=>r.ok?r.json():null).then(p=>{if(p&&['en','hi','kn'].includes(p.ui_language))setLocale(p.ui_language);}).catch(()=>{});};const change=(event:Event)=>{const value=(event as CustomEvent).detail;if(['en','hi','kn'].includes(value))setLocale(value);else refresh();};refresh();window.addEventListener('lms:locale',change);return()=>window.removeEventListener('lms:locale',change);},[]);
 useEffect(()=>{document.documentElement.lang=locale;},[locale]);
 return <LocaleContext.Provider value={locale}>{children}</LocaleContext.Provider>;
}
function text(value:string,locale:Locale):string{
 if(locale==='en')return value;
 const trimmed=value.trim(),entry=translations[trimmed];
 if(entry)return value.replace(trimmed,entry[locale]);
 // Composed UI labels retain dynamic course titles and numeric values.
 for(const prefix of ['Sort by ','Search ','Save ','Create ','Edit ','Open ','Updated ','Due ']){
  if(trimmed.startsWith(prefix)){const translated=translations[prefix.trim()];if(translated)return value.replace(trimmed,translated[locale]+' '+text(trimmed.slice(prefix.length),locale));}
 }
 return value;
}
export function Localized({children}:{children:ReactNode}){
 const locale=useContext(LocaleContext);
 if(locale==='en')return <>{children}</>;
 function translate(node:ReactNode):ReactNode{
  if(typeof node==='string')return text(node,locale);
  if(Array.isArray(node))return Children.map(node,translate);
  if(!isValidElement(node))return node;
  const element=node as ReactElement<Record<string,unknown>>;
  // Authored/code input values are never translated or modified.
  if(['pre','code','textarea','script','style'].includes(String(element.type))||element.props['data-no-translate']||/reader-body|submitted-text|code-output|\boption\b/.test(String(element.props.className||'')))return node;
  const next:Record<string,unknown>={};
  // Native option values must remain stable when the visible label changes.
  if(element.type==='option'&&element.props.value===undefined&&typeof element.props.children==='string')next.value=element.props.children;
  for(const key of ['label','placeholder','title','aria-label'])if(typeof element.props[key]==='string')next[key]=text(element.props[key] as string,locale);
  if(element.props.children!==undefined)next.children=translate(element.props.children as ReactNode);
  return cloneElement(element,next);
 }
 return <>{translate(children)}</>;
}
