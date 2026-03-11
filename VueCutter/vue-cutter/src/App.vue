<script setup>
import { useTheme } from 'vuetify'
import { get_themecookie } from '@/app';

const theme = useTheme()
theme.global.name.value = get_themecookie()
</script>

<template>
  <v-app>
    <MenuBar />
    <SideBar />
    <CutterBar />
    <MainArea />
    <FooterArea />
  </v-app>
</template>
