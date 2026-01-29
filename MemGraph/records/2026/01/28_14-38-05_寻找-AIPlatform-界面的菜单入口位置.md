---
role: 用户
project: LayaPro
directory: D:\work\laya\LayaPro
timestamp: 2026-01-28T14:38:05.104524
tags: [LayaPro, AIGC, MenuExt, 界面入口, 面板管理]
---

## 问题

寻找 AIPlatform 界面的菜单入口位置

## 解决方法

AIPlatform 界面的菜单入口在 `MenuExt.ts` 中，目前被暂时注释掉了。

代码位置：`feature-pack/aigc/MenuExt.ts`

```typescript
@IEditor.menu("App/ai/aigc", {
    label: "i18n:uiproj-fp:aigc.panelTitle",
})
static showPanel12() {
    Editor.panelManager.showPanel("AIGCPlatformPanel");
}
```

**说明：**
- 菜单路径：`App/ai/aigc`
- 国际化标签：`i18n:uiproj-fp:aigc.panelTitle`
- 面板名称：`AIGCPlatformPanel`
- 如需启用该功能，取消注释该装饰器和方法即可
