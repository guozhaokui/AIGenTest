import { createRouter, createWebHistory } from 'vue-router';

const AdminHome = () => import('../views/AdminHome.vue');
const EvalHome = () => import('../views/EvalHome.vue');

const routes = [
  { path: '/', redirect: '/admin' },
  { path: '/admin', name: 'AdminHome', component: AdminHome },
  { path: '/eval', name: 'EvalHome', component: EvalHome }
];

const router = createRouter({
  history: createWebHistory(),
  routes
});

export default router;


