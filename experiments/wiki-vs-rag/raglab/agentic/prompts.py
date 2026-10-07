PROMPT_VERSION = "agentic-rag-p0-2026-10-02"

ROUTER_PROMPT = """你只负责分类问题，不回答问题。判断 targeted、broad、clarification_required 或 out_of_scope。"""
PLANNER_PROMPT = """你只负责制定检索计划，不输出游戏答案。宽泛问题拆成 4～8 个不重复维度。"""
AUDITOR_PROMPT = """你只检查现有证据是否足够，不得使用模型常识补全未出现的条件。"""
COMPOSER_PROMPT = """只能使用审核后的证据；每个实质结论标注来源 ID，证据不足时明确说明。"""
