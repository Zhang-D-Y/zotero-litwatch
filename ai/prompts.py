"""
Prompt 模板管理
"""

from typing import Dict, List, Optional


class PromptTemplates:
    """Prompt 模板集合"""
    
    # 单篇文献总结
    SINGLE_PAPER_SUMMARY = """你是一位专业的学术研究助手。请对以下学术论文进行全面而深入的总结。

## 论文信息
- **标题**: {title}
- **作者**: {authors}
- **发表日期**: {date}
- **期刊/出版物**: {publication}

## 摘要
{abstract}

## 全文内容
{content}

---

请按照以下结构进行总结：

### 1. 研究背景与动机
- 研究的背景是什么？
- 解决什么问题？
- 为什么这个问题重要？

### 2. 核心方法
- 使用了什么方法/技术？
- 方法的创新点是什么？

### 3. 主要发现与结果
- 主要的实验结果是什么？
- 关键的数据或指标

### 4. 结论与贡献
- 论文的主要贡献是什么？
- 对领域的影响

### 5. 局限性与未来方向
- 研究的局限性
- 可能的未来研究方向

### 6. 关键词和主题
- 列出3-5个关键词
- 论文涉及的主要主题领域

请用清晰、专业的学术语言进行总结，控制在800-1200字左右。"""

    # 多篇文献综合分析
    MULTI_PAPER_SYNTHESIS = """你是一位专业的学术研究助手。请对以下多篇相关学术论文进行综合分析和对比。

## 文献列表

{papers_list}

---

**输出要求**：
- 使用 Markdown 格式输出，包括标题、列表、加粗等
- 引用文献时使用「缩写写名」（如 "Alphafold2", "AF2"）或「完整标题」，不要使用“论文1、论文2”等编号
- 使用表格、列表等增强可读性
- **重要**：对于短小的公式、变量名或代码片段（如 `z`, `Encoder(x)`），请务必使用行内代码格式（即使用单个反引号 `code`），不要使用代码块（三个反引号）。只有多行代码或长公式才使用代码块。

请按照以下结构进行综合分析：

### 1. 🎯 主题概述
- 这些论文共同关注的研究领域/问题是什么？
- 研究的整体背景

### 2. 🔬 方法对比
- 各论文使用的方法有何异同？
- 方法论上的演进或创新

### 3. 📊 发现与结论对比
- 各论文的主要发现
- 结论之间是否有一致性或矛盾？

### 4. 📈 研究趋势
- 从这些论文中可以看出什么研究趋势？
- 该领域的发展方向

### 5. 🔍 知识缺口与机会
- 现有研究的不足
- 潜在的研究机会

### 6. ✅ 综合结论
- 对这组文献的整体评价
- 对后续研究的建议

请提供深入、有洞察力的分析，控制在1500-2000字。"""

    # Deep Research 深度研究
    DEEP_RESEARCH = """你是一位资深的学术研究专家，擅长进行深度文献研究和知识综合。

## 研究问题
{research_question}

## 相关文献资料

{literature_content}

---

请进行深度研究分析，按以下结构输出研究报告：

# 深度研究报告

## 执行摘要
- 研究问题的简要回答
- 主要发现概述

## 1. 研究背景
- 问题的重要性
- 当前研究现状概述

## 2. 文献分析

### 2.1 理论框架
- 主要理论和概念
- 理论的演进

### 2.2 方法论综述
- 常用研究方法
- 方法的优缺点

### 2.3 实证发现
- 关键实证结果
- 证据的一致性分析

## 3. 批判性分析
- 现有研究的优势
- 研究的局限和不足
- 存在的争议或分歧

## 4. 知识图谱
- 核心概念之间的关系
- 研究主题的分类

## 5. 研究趋势与展望
- 新兴研究方向
- 未来研究建议
- 潜在的突破领域

## 6. 结论
- 关键洞察总结
- 实践建议

## 参考文献摘要
- 引用的关键文献列表

请提供全面、深入、有学术价值的研究报告，字数在2000-3000字之间。"""

    # 快速摘要
    QUICK_SUMMARY = """请用2-3句话简洁地总结以下论文的核心内容：

标题: {title}
作者: {authors}
摘要: {abstract}

内容片段: {content_snippet}

请直接给出简洁的总结，不需要标题或格式。"""

    # 关键点提取
    KEY_POINTS = """请从以下论文中提取5-7个关键要点：

标题: {title}
内容: {content}

请以简洁的要点形式输出，每个要点用一句话概括。"""

    # 研究问题生成
    RESEARCH_QUESTIONS = """基于以下文献内容，生成3-5个值得进一步研究的问题：

{content}

请列出具有研究价值的问题，每个问题应该：
1. 具体且可操作
2. 与现有文献相关但尚未充分解答
3. 具有学术或实践价值"""

    # 快速分类汇总（仅使用摘要）
    QUICK_CATEGORIZE = """你是一位专业的学术研究助手。请根据以下多篇论文的摘要信息，对这些文献进行智能分类和汇总分析。

## 文献摘要列表

{abstracts_list}

---

**输出要求**：
- 使用 Markdown 格式，包括标题、表格、列表、emoji 等
- 引用文献时使用「第一作者姓氏 + et al. + 年份」（如 "Smith et al., 2023"）或「标题缩写」（取标题前3-5个关键词）
- **绝对不要使用“论文1、论文2、论文3”等编号引用**
- 使用图例和可视化元素增强可读性

请按照以下结构进行分析和输出：

# 📊 文献分类汇总报告

## 1️⃣ 主题分类

将这些文献按研究主题/方向分成若干类别，每个类别包含：

### 🟢 [类别名称]
- **代表文献**：
  - Author1 et al. (2023): “标题缩写或关键词”
  - Author2 et al. (2022): “标题缩写或关键词”
- **主题特点**：该类别文献的共同特点（1-2句话）

### 🟡 [另一类别名称]
...
---

## 2️⃣ 方法论分类

| 方法类型 | 代表文献 | 特点 |
|---------|---------|-----|
| 📚 理论研究 | Author et al. (2023), ... | ... |
| 📊 实证研究 | Author et al. (2022), ... | ... |
| 📝 综述分析 | Author et al. (2021), ... | ... |

---

## 3️⃣ 整体概述

🎯 **研究领域**：...

🔑 **主要关注点**：...

---

## 4️⃣ 研究趋势与方向

```mermaid
graph LR
    A[早期研究] --> B[当前热点]
    B --> C[新兴方向]
```

- 📈 **主要趋势**：...
- ✨ **新兴方向**：...

---

## 5️⃣ 知识图谱

```
核心主题
    ├── 分支1: Author1 et al. (2023), Author2 et al. (2022)
    ├── 分支2: Author3 et al. (2021)
    └── 分支3: Author4 et al. (2020)
```

---

## 💡 关键洞察

> 用 2-3 句话总结最重要的发现和见解

请确保分析清晰、专业，突出文献之间的联系和差异。"""

    @classmethod
    def get_single_summary_prompt(
        cls,
        title: str,
        authors: str,
        date: Optional[str],
        publication: Optional[str],
        abstract: Optional[str],
        content: str
    ) -> str:
        """生成单篇论文总结 prompt"""
        return cls.SINGLE_PAPER_SUMMARY.format(
            title=title,
            authors=authors,
            date=date or "未知",
            publication=publication or "未知",
            abstract=abstract or "无摘要",
            content=content[:15000]  # 限制长度
        )
    
    @classmethod
    def get_multi_paper_prompt(cls, papers: List[Dict]) -> str:
        """生成多篇论文综合分析 prompt"""
        papers_text = []
        for i, paper in enumerate(papers, 1):
            # 生成文献引用名：作者 et al. (year)
            authors = paper.get('authors', '') or '未知'
            # 安全地提取第一作者
            if authors and authors != '未知':
                try:
                    author_parts = authors.replace(';', ',').split(',')[0].strip()
                    first_author = author_parts.split()[-1] if author_parts else '未知'
                except Exception:
                    first_author = '未知'
            else:
                first_author = '未知'
                
            date_str = paper.get('date', '') or ''
            year = date_str[:4] if date_str and len(date_str) >= 4 else '未知'
            citation = f"{first_author} et al. ({year})"
            
            paper_text = f"""
### 📝 {citation}: {paper.get('title', '') or '未知标题'}
- **作者**: {authors}
- **摘要**: {paper.get('abstract', '') or '无摘要'}
- **关键内容**: {(paper.get('content', '') or '')[:3000]}
"""
            papers_text.append(paper_text)
        
        return cls.MULTI_PAPER_SYNTHESIS.format(
            papers_list="\n".join(papers_text)
        )
    
    @classmethod
    def get_deep_research_prompt(
        cls,
        research_question: str,
        literature_content: str
    ) -> str:
        """生成深度研究 prompt"""
        return cls.DEEP_RESEARCH.format(
            research_question=research_question,
            literature_content=literature_content
        )
    
    @classmethod
    def get_quick_summary_prompt(
        cls,
        title: str,
        authors: str,
        abstract: Optional[str],
        content_snippet: str
    ) -> str:
        """生成快速摘要 prompt"""
        return cls.QUICK_SUMMARY.format(
            title=title,
            authors=authors,
            abstract=abstract or "无摘要",
            content_snippet=content_snippet[:2000]
        )
    
    @classmethod
    def get_quick_categorize_prompt(cls, papers: List[Dict]) -> str:
        """生成快速分类汇总 prompt（仅使用摘要）"""
        abstracts_text = []
        for i, paper in enumerate(papers, 1):
            # 生成文献引用名：作者 et al. (year)
            authors = paper.get('authors', '') or '未知'
            # 安全地提取第一作者
            if authors and authors != '未知':
                try:
                    # 按逗号或分号分割，然后取最后一个单词作为姓氏
                    author_parts = authors.replace(';', ',').split(',')[0].strip()
                    first_author = author_parts.split()[-1] if author_parts else '未知'
                except Exception:
                    first_author = '未知'
            else:
                first_author = '未知'
            
            date_str = paper.get('date', '') or ''
            year = date_str[:4] if date_str and len(date_str) >= 4 else '未知'
            citation = f"{first_author} et al. ({year})"
            
            # 生成标题缩写（取前3-5个关键词）
            title = paper.get('title', '') or '未知标题'
            try:
                title_words = [w for w in title.split() if len(w) > 3][:5]
                title_abbr = ' '.join(title_words) if title_words else title[:50]
            except Exception:
                title_abbr = title[:50]
            
            abstract_text = f"""
### 📝 {citation}
- **完整标题**: {title}
- **缩写引用**: "{title_abbr}"
- **作者**: {authors}
- **发表时间**: {paper.get('date', '') or '未知'}
- **期刊/会议**: {paper.get('publication', '') or '未知'}
- **摘要**: {paper.get('abstract', '') or '无摘要'}
"""
            abstracts_text.append(abstract_text)
        
        return cls.QUICK_CATEGORIZE.format(
            abstracts_list="\n".join(abstracts_text)
        )
