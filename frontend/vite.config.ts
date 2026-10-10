import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'node:path';
export default defineConfig({
  plugins:[react()],
  resolve:{alias:{'@':path.resolve(import.meta.dirname,'.')}},
  build:{outDir:'../web',emptyOutDir:true},
  server:{proxy:{'/v1':'http://127.0.0.1:8000','/health':'http://127.0.0.1:8000','/ready':'http://127.0.0.1:8000'}}
});
