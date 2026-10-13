import { defineConfig } from 'vite';
export default defineConfig({base:'/ui/',server:{proxy:{'/runs':'http://127.0.0.1:8000','/imports':'http://127.0.0.1:8000','/health':'http://127.0.0.1:8000'}}});
