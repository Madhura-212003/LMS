import type { Metadata } from 'next';
import './styles.css';
import './features.css';
import {LocaleProvider} from './Locale';
export const metadata: Metadata = {title: 'Admiezo | Learning workspace', description: 'Learning Management and Digital Education'};
export default function Layout({children}: {children: React.ReactNode}) {return <html lang="en"><body><LocaleProvider>{children}</LocaleProvider></body></html>;}
