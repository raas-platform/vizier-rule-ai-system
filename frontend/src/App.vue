<template>
  <div class="app">
    <header class="header">
      <div class="container">
        <h1>Rule AI System</h1>
      </div>
    </header>
    
    <main class="container">
      <ValidationReport />
    </main>
  </div>
</template>

<script lang="ts">
import { defineComponent } from 'vue'
import ValidationReport from './views/ValidationReport.vue'

export default defineComponent({
  name: 'App',
  components: {
    ValidationReport
  }
})
</script>

<style>
.app {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
}

.header {
  background-color: white;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
  padding: 1rem 0;
  margin-bottom: 2rem;
}

.header .container {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.header h1 {
  font-size: 1.5rem;
  margin: 0;
}

main {
  flex: 1;
  padding-bottom: 2rem;
}
</style> 