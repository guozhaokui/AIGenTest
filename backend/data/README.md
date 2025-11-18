数据存储（JSON）

文件
- dimensions.json：维度数组
- questions.json：试题数组
- examples.json：样例数组（imagePath 指向 uploads）
- evaluations.json：题目级评估记录数组（EvaluationItem，含 runId）
- runs.json：评估批次数组（EvaluationRun，一次完整评估与导出单位）

约定
- UTF-8、顶层数组。
- 图片仅保存路径（相对后端工作目录或仓库根）。
- 写入采用“临时文件 + rename”原子替换，工具位于 `src/utils/jsonStore.js`。

备份建议
- 定期备份 `backend/data/` 与 `backend/uploads/`。
- 如需多人协作或更高可靠性，后续可迁移到数据库与对象存储。


