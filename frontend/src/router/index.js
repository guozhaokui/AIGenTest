import { createRouter, createWebHistory } from 'vue-router';

const AdminIndex = () => import('../views/AdminIndex.vue');
const AdminHome = () => import('../views/AdminHome.vue');
const Dimensions = () => import('../views/Dimensions.vue');
const QuestionSets = () => import('../views/QuestionSets.vue');
const QuestionSetDetail = () => import('../views/QuestionSetDetail.vue');
const EvalIndex = () => import('../views/EvalIndex.vue');
const EvalHome = () => import('../views/EvalHome.vue'); // start
const EvalHistory = () => import('../views/EvalHistory.vue');

const routes = [
  { path: '/', redirect: '/admin' },
  {
    path: '/admin',
    component: AdminIndex,
    children: [
      { path: '', name: 'AdminHome', component: AdminHome },
      { path: 'dimensions', name: 'Dimensions', component: Dimensions },
      { path: 'question-sets', name: 'QuestionSets', component: QuestionSets },
      { path: 'question-sets/:id', name: 'QuestionSetDetail', component: QuestionSetDetail }
    ]
  },
  {
    path: '/eval',
    component: EvalIndex,
    children: [
      { path: '', redirect: '/eval/start' },
      { path: 'start', name: 'EvalStart', component: EvalHome },
      { path: 'history', name: 'EvalHistory', component: EvalHistory }
    ]
  }
];

const router = createRouter({
  history: createWebHistory(),
  routes
});

export default router;


