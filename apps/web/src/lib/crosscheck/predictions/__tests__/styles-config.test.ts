import {readFileSync} from 'node:fs';
import path from 'node:path';
import {describe,it,expect} from 'vitest';
import nextConfig from '../../../../../next.config';

describe('Crosscheck CSS merge safeguards',()=>{
 it('runs the Tailwind entry loader only on global CSS and leaves module identity to Next',()=>{
  const rules=nextConfig.turbopack?.rules;
  expect(Object.keys(rules??{})).toEqual(['globals.css']);
  expect(rules?.['globals.css']).toEqual({loaders:['@tailwindcss/turbopack'],as:'*.css'});
  expect(rules).not.toHaveProperty('*.css');
  expect(rules).not.toHaveProperty('*.module.css');
 });
 it('retains the default build command and standard PostCSS path without forcing Webpack',()=>{
  const pkg=JSON.parse(readFileSync(path.resolve(process.cwd(),'package.json'),'utf8'));
  expect(pkg.scripts.build).toBe('next build');
  expect(pkg.devDependencies['@tailwindcss/postcss']).toBe('4.3.3');
  expect(readFileSync(path.resolve(process.cwd(),'postcss.config.mjs'),'utf8')).toContain("'@tailwindcss/postcss'");
 });
});
