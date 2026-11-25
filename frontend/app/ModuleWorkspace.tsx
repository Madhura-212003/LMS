'use client';
// locale-wrapped
import {Localized} from './Locale';

import {FeatureProps} from './feature-shared';
import {LibraryModule,LiveModule,LectureModule,PathModule,PreferenceModule,LanguageModule,ActivityModule} from './LearningModules';
import {CodingModule,LabModule,SkillModule,PracticeModule,ExamModule} from './PracticeModules';
import {MarketplaceModule,TutorModule,CredentialManagement,NotificationModule,ProgressModule} from './ManagementModules';
export default function ModuleWorkspace(p:FeatureProps){
 if(p.module===158)return <Localized><LibraryModule {...p}/></Localized>;
 if(p.module===159)return <Localized><LiveModule {...p}/></Localized>;
 if(p.module===160)return <Localized><LectureModule {...p}/></Localized>;
 if(p.module===161)return <Localized><PathModule {...p}/></Localized>;
 if(p.module===162)return <Localized><PreferenceModule {...p}/></Localized>;
 if(p.module===163)return <Localized><TutorModule {...p}/></Localized>;
 if(p.module===164)return <Localized><LanguageModule {...p}/></Localized>;
 if(p.module===167)return <Localized><ActivityModule {...p}/></Localized>;
 if(p.module===169)return <Localized><CodingModule {...p}/></Localized>;
 if(p.module===170)return <Localized><LabModule {...p}/></Localized>;
 if(p.module===171)return <Localized><SkillModule {...p}/></Localized>;
 if(p.module===172||p.module===178||p.tab==='Mains writing'||p.tab==='Interview & GD'||p.tab==='Teacher review')return <Localized><PracticeModule {...p}/></Localized>;
 if([173,174,175,176,177].includes(p.module))return <Localized><ExamModule {...p}/></Localized>;
 if(p.module===179)return p.tab==='Progress'?<ProgressModule {...p}/>:<CredentialManagement {...p}/>;
 if(p.module===180)return <Localized><MarketplaceModule {...p}/></Localized>;
 return <Localized><NotificationModule {...p}/></Localized>;
}
