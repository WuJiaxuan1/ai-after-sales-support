<!--
  App.vue — 根组件
  =================
  纯布局壳，不包含导航栏（用户端和客服端是完全独立的页面）。
  <router-view /> 根据 URL 渲染对应的视图组件。
-->
<template>
  <div id="app-root">
    <router-view />
  </div>
</template>

<script setup>
</script>

<style>
/* 全局基础样式 */
* { margin: 0; padding: 0; box-sizing: border-box; }
body {
  font-family: "PingFang SC", "Microsoft YaHei", sans-serif;
  background: #f5f5f5;
  color: #333;
  min-height: 100vh;
}
</style>
