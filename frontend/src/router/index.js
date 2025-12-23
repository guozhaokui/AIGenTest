import { createRouter, createWebHistory } from 'vue-router';

const AdminIndex = () => import('../views/AdminIndex.vue');
const Dimensions = () => import('../views/Dimensions.vue');
const QuestionSets = () => import('../views/QuestionSets.vue');
const QuestionSetDetail = () => import('../views/QuestionSetDetail.vue');
const QuestionsAdmin = () => import('../views/QuestionsAdmin.vue');
const EvalIndex = () => import('../views/EvalIndex.vue');
const EvalHome = () => import('../views/EvalHome.vue'); // start
const EvalHistory = () => import('../views/EvalHistory.vue');
const LiveGenIndex = () => import('../views/LiveGen/index.vue');
const LiveGenHome = () => import('../views/LiveGen/LiveGenHome.vue');
const LiveGenHistory = () => import('../views/LiveGen/LiveGenHistory.vue');

// 图片管理
const ImageMgrIndex = () => import('../views/ImageMgr/index.vue');
const ImageList = () => import('../views/ImageMgr/ImageList.vue');
const ImageSearch = () => import('../views/ImageMgr/ImageSearch.vue');
const ImageUpload = () => import('../views/ImageMgr/ImageUpload.vue');
const BatchImport = () => import('../views/ImageMgr/BatchImport.vue');

const routes = [
  { path: '/', redirect: '/admin' },
  {
    path: '/admin',
    component: AdminIndex,
    children: [
      { path: '', redirect: '/admin/dimensions' },
      { path: 'dimensions', name: 'Dimensions', component: Dimensions },
      { path: 'question-sets', name: 'QuestionSets', component: QuestionSets },
      { path: 'question-sets/:id', name: 'QuestionSetDetail', component: QuestionSetDetail },
      { path: 'questions', name: 'QuestionsAdmin', component: QuestionsAdmin }
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
  },
  {
    path: '/live',
    component: LiveGenIndex,
    children: [
      { path: '', redirect: '/live/generate' },
      { path: 'generate', name: 'LiveGenHome', component: LiveGenHome },
      { path: 'history', name: 'LiveGenHistory', component: LiveGenHistory }
    ]
  },
  {
    path: '/imagemgr',
    component: ImageMgrIndex,
    children: [
      { path: '', redirect: '/imagemgr/list' },
      { path: 'list', name: 'ImageList', component: ImageList },
      { path: 'search', name: 'ImageSearch', component: ImageSearch },
      { path: 'upload', name: 'ImageUpload', component: ImageUpload },
      { path: 'batch', name: 'BatchImport', component: BatchImport }
    ]
  }
];

const router = createRouter({
  history: createWebHistory(),
  routes
});

export default router;


