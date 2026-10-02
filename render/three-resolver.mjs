// Lets Node resolve 'three' and 'three/addons/…' for the browser modules in ../tar3d, which
// expect an import map, using the copy installed in render/node_modules.
import { register } from 'node:module';

register('data:text/javascript,' + encodeURIComponent(`
  const base = ${JSON.stringify(new URL('./node_modules/three/', import.meta.url).href)};
  export async function resolve(spec, ctx, next) {
    if (spec === 'three') return next(base + 'build/three.module.js', ctx);
    if (spec.startsWith('three/addons/')) return next(base + 'examples/jsm/' + spec.slice(13), ctx);
    return next(spec, ctx);
  }
`));
