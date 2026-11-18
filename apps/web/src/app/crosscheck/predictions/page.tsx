import type {Metadata} from 'next';
import {readPublishedPredictions} from '@/lib/crosscheck/predictions/read';
import Predictions from './Predictions';
export const dynamic='force-dynamic';
export const metadata:Metadata={title:'Locked predictions | Crosscheck',description:'Prospectively locked quarterly revenue probabilities, management targets, evidence and reviewed outcomes.'};
export default async function Page(){return <Predictions state={await readPublishedPredictions()}/>;}
