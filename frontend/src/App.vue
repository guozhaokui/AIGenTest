<template>
  <div class="app">
    <nav style="display:flex; gap:12px; padding:12px;">
      <router-link to="/admin">管理端</router-link>
      <router-link to="/eval">评估端</router-link>
      <router-link to="/live">实时生成</router-link>
      <router-link to="/imagemgr">图片管理</router-link>
      <router-link to="/knowledge">知识查询</router-link>
    </nav>
    <router-view />
  </div>
</template>

<script setup>
</script>

<style>
body, html {
  margin: 0;
  padding: 0;
}
#app {
  margin: 0;
  min-height: 100vh;
}
nav a.router-link-active {
  font-weight: bold;
}
</style>


