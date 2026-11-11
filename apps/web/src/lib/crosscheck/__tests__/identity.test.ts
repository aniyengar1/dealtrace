import {describe,it,expect} from 'vitest';
import {filterCompanies,normalizedTicker,validAsOf} from '../identity';
const companies=[{ticker:'PD',name:'PagerDuty, Inc.',cik:'0001568100',as_of:null,forecast_status:null,verdict:null},{ticker:'GTLB',name:'GitLab Inc.',cik:'0001653482',as_of:null,forecast_status:null,verdict:null}];
describe('company identification',()=>{
 it('finds names and tickers without fabricating coverage',()=>{
  expect(filterCompanies(companies,'pagerduty')[0].ticker).toBe('PD');
  expect(filterCompanies(companies,'gtlb')[0].name).toBe('GitLab Inc.');
  expect(filterCompanies(companies,'MSFT')).toEqual([]);
  expect(filterCompanies(companies,'')).toHaveLength(2);
 });
 it('normalizes identifiers and rejects malformed ones',()=>{
  expect(normalizedTicker(' pd ')).toBe('PD');expect(normalizedTicker('BRK.B')).toBe('BRK.B');
  expect(normalizedTicker("PD'; DROP TABLE companies")).toBeNull();
 });
 it('accepts real date cutoffs only',()=>{
  expect(validAsOf('2026-11-11')).toBe(true);expect(validAsOf('2026-02-30')).toBe(false);
  expect(validAsOf('2026-13-01')).toBe(false);expect(validAsOf('tomorrow')).toBe(false);
 });
});
