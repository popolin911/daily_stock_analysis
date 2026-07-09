# daily_stock_analysis 项目档案

## 基本信息
- 仓库: https://github.com/popolin911/daily_stock_analysis
- 本地路径: ~/daily_stock_analysis
- 部署时间: 2026-07-08

## 核心配置
- AI模型: DeepSeek (替换原Gemini)
- 数据源: 腾讯财经(A股)/Yahoo(港美股)
- 推送: PushPlus → 微信
- 定时: 工作日18:00自动运行

## GitHub配置
- Secrets: DEEPSEEK_API_KEY, LLM_DEEPSEEK_API_KEY, PUSHPLUS_TOKEN
- Variables: LLM_CHANNELS, LLM_DEEPSEEK_BASE_URL, LLM_DEEPSEEK_MODELS, LITELLM_MODEL, STOCK_LIST

## 关键操作
- 触发分析: Actions → 每日股票分析 → Run workflow
- 修改股票: Settings → Variables → STOCK_LIST
- 查看报告: Actions → Artifacts 或 PushPlus微信

## 已验证
- [x] Actions定时运行
- [x] DeepSeek分析
- [x] PushPlus推送

## 待优化
- [ ] 搭建Dify对话Agent
- [ ] 优化报告模板
- [ ] 添加Tushare数据源
- [ ] 本地Web面板

## 快速启动
新Kimi Code会话开场白:
"继续操作daily_stock_analysis，读取PROJECT_MEMORY.md"
