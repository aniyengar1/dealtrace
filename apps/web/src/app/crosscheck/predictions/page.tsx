import type {Metadata} from 'next';
import {readPublishedPredictions,readPublishedBacktest} from '@/lib/crosscheck/predictions/read';
import Predictions from './Predictions';
export const dynamic='force-dynamic';
export const metadata:Metadata={title:'Locked predictions | Crosscheck',description:'Prospectively locked quarterly revenue probabilities, management targets, evidence and reviewed outcomes.'};
export default async function Page(){const [state,backtest]=await Promise.all([readPublishedPredictions(),readPublishedBacktest()]);return <Predictions state={state} backtest={backtest}/>;}
