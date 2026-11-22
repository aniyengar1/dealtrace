import React from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import {beforeEach,it,expect,vi} from 'vitest';
vi.mock('server-only',()=>({}));
vi.mock('../queries',()=>({companyData:vi.fn()}));
vi.mock('next/link',()=>({default:({href,children}:{href:string;children:React.ReactNode})=><a href={href}>{children}</a>}));
import {companyData} from '../queries';
import CompanyPage from '@/app/crosscheck/[ticker]/page';
import Loading from '@/app/crosscheck/loading';
import ErrorState from '@/app/crosscheck/error';
const get=vi.mocked(companyData);
const company={ticker:'PD',name:'PagerDuty',cik:'0001568100',as_of:'2026-11-11',forecast_status:'experimental',verdict:'beat'};
const report={id:'report',as_of:'2026-11-11',report_version:'v1',company:{...company,fiscal_label:'FY2027',period_start:'2026-02-01',period_end:'2027-01-31',basis:'GAAP',calendar:'months'},guidance:[],guidance_review_through:'2026-11-11',overview:[],hurdle:{id:'hurdle',state:'blocked',codes:['STALE_INPUT'],details:['Actuals exceed manual 135-day threshold'],inputs:{},formula_version:'v1'},hurdle_display:{},forecast:{id:'forecast',method:'v1',status:'blocked',verdict:null,codes:['STALE_INPUT'],details:['Actuals exceed manual 135-day threshold'],interval_reason:'No calibrated interval',assumptions:[]},forecast_display:{},selected_inputs:{},evaluation:{status:'insufficient_validation',sample_size:0,covered_companies:0,coverage_denominator:10,classification_samples:0,classification_correct:0,limitations:['Insufficient evidence'],missing_companies:['PD'],cases:[]},evaluation_display:{},changes:{previous_report_id:null,causes:['initial_report'],input_versions:{}},reporting:{next_report:{type:'Q3 hurdle update',date:null,status:'unverified'},annual_result:{type:'Annual result',status:'estimated'}},coverage_notes:[]};
beforeEach(()=>{vi.resetAllMocks();vi.unstubAllEnvs();});
it('renders unsupported coverage as actual server HTML',async()=>{
 get.mockResolvedValueOnce(null);
 const html=renderToStaticMarkup(await CompanyPage({params:Promise.resolve({ticker:'MSFT'}),searchParams:Promise.resolve({})}));
 expect(html).toContain('This company is not supported yet.');expect(html).not.toContain('Model indication: beat');
});
it('renders the stale block without inventing an estimate',async()=>{
 get.mockResolvedValueOnce({company,report,dates:['2026-11-11']});
 const html=renderToStaticMarkup(await CompanyPage({params:Promise.resolve({ticker:'PD'}),searchParams:Promise.resolve({})}));
 expect(html).not.toContain('Forecast withheld');expect(html).not.toContain('Historical evaluation');expect(html).toContain('STALE_INPUT');expect(html).toContain('135-day');expect(html).not.toContain('Model indication: beat');
});
it('renders an explicit missing cutoff, never a substituted report',async()=>{
 get.mockResolvedValueOnce({company,report:null,dates:['2026-11-11']});
 const html=renderToStaticMarkup(await CompanyPage({params:Promise.resolve({ticker:'PD'}),searchParams:Promise.resolve({asOf:'2026-11-12'})}));
 expect(html).toContain('No published report');expect(html).toContain('2026-11-12');expect(html).toContain('Earlier snapshots are not silently substituted');
});
it('has meaningful loading and sanitized error states',()=>{
 expect(renderToStaticMarkup(<Loading/>)).toContain('aria-busy="true"');
 const html=renderToStaticMarkup(<ErrorState error={new Error('private connection details')} reset={()=>{}}/>);
 expect(html).toContain('Company research is unavailable');expect(html).not.toContain('private connection');
});

it('hides forecast/evaluation and their change messages by default',async()=>{
 get.mockResolvedValueOnce({company,report:{...report,changes:{...report.changes,causes:['forecast_estimate_changed','guidance_changed']}},dates:[]});
 const html=renderToStaticMarkup(await CompanyPage({params:Promise.resolve({ticker:'PD'}),searchParams:Promise.resolve({})}));
 expect(html).not.toContain('Annual revenue forecast');expect(html).not.toContain('Historical evaluation');
 expect(html).not.toContain('annual revenue estimate changed');expect(html).toContain('Management target');
 expect(html).toContain('Quarterly guidance-implied growth');expect(html).toContain('Guidance history');
});
it('allows explicit opt-in to the preserved experimental view',async()=>{
 vi.stubEnv('CROSSCHECK_EXPERIMENTAL_ANNUAL_FORECAST','true');get.mockResolvedValueOnce({company,report,dates:[]});
 const html=renderToStaticMarkup(await CompanyPage({params:Promise.resolve({ticker:'PD'}),searchParams:Promise.resolve({})}));
 expect(html).toContain('Annual revenue forecast');expect(html).toContain('Forecast withheld');
 expect(html).toContain('Historical evaluation');expect(html).toContain('Quarterly guidance-implied growth');
});

it('keeps an existing quarterly comparison and its sources visible with the forecast off',async()=>{
 const quarterly={company:'PD',as_of:'2026-11-11',formula_version:'quarter-guidance-implied-growth-v1',codes:[],details:[],
 target:{label:'Q3 FY2027',start:'2026-08-01',end:'2026-10-31',prior_start:'2025-08-01',prior_end:'2025-10-31'},inputs:{guidance:'quarter-guide',prior_quarter:'quarter-actual'},
 display:{low:'300.000',high:'350.000',prior:'200.000',growth_low:'50.00%',growth_high:'75.00%'},
 guidance:{low:'300000000',high:'350000000',issued:{start:'2026-08-01',end:'2026-08-01'},filed:'2026-08-01',accession:'guide-acc',exhibit:'99.1',quote:'Quarter consolidated revenue range',source_url:'https://www.sec.gov/Archives/quarter-guide'},
 comparison:{id:'quarter-actual',concept:'Revenues',start:'2025-08-01',end:'2025-10-31',filed:'2025-12-01',value:'200000000',unit:'USD',basis:'GAAP',accession:'actual-acc',source_url:'https://www.sec.gov/Archives/quarter-actual'}};
 get.mockResolvedValueOnce({company,report:{...report,quarterly},dates:[]});
 const html=renderToStaticMarkup(await CompanyPage({params:Promise.resolve({ticker:'PD'}),searchParams:Promise.resolve({})}));
 expect(html).toContain('50.00%');expect(html).toContain('75.00%');expect(html).toContain('quarter-actual');
 expect(html).toContain('https://www.sec.gov/Archives/quarter-guide');expect(html).toContain('YTD subtraction is not applicable');
 expect(html).not.toContain('Annual revenue forecast');
 const ranged={...quarterly,guidance:{...quarterly.guidance,issued:{start:'2026-08-01',end:'2026-08-31'}}};
 get.mockResolvedValueOnce({company,report:{...report,quarterly:ranged},dates:[]});
 const rangeHtml=renderToStaticMarkup(await CompanyPage({params:Promise.resolve({ticker:'PD'}),searchParams:Promise.resolve({})}));
 expect(rangeHtml).toContain('through 2026-08-31');

});
