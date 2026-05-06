# LLM 社会约定与集体偏见实验复现

本项目用于复现与扩展论文 **“Emergent social conventions and collective bias in LLM populations”** 的实验代码。

论文信息：

- **标题**：Emergent social conventions and collective bias in LLM populations
- **作者**：Ariel Flint Ashery, Luca Maria Aiello, Andrea Baronchelli
- **期刊**：Science Advances
- **发表时间**：2025 年 5 月 14 日

## 原作者权利与许可证

本仓库中的原始实验代码来自论文作者提供的项目代码。根据项目中的 `LICENSE` 文件，该代码采用 **MIT License**：

- **版权归属**：Copyright (c) 2024 Ariel Flint Ashery
- **使用、复制、修改、发布、分发等权利**：遵循 MIT License
- **保留要求**：任何副本或重要代码片段中都应保留原版权声明与许可声明

本项目对原作者代码进行了整理和扩展，但不改变原作者对原始代码的权利归属。使用、引用或分发本项目时，请同时尊重论文作者和原始代码许可证。

## 当前项目目标

本项目当前做了两件事：

- **复现原论文实验**
  - 保留原作者的核心实验逻辑、prompt 生成逻辑、theoretical naming game 模型和绘图 notebook。

- **扩展远程 LLM API 支持**
  - 在原 HuggingFace API 基础上，新增 OpenAI-compatible API 支持，例如 Kimi、OpenAI、DeepSeek、OpenRouter、Together、Groq、Mistral 等。

## 项目结构

```text
.
├── README.md
├── LICENSE
├── config.yaml
├── runner.py
├── plotter.ipynb
├── requirements.txt
├── author_code/
├── project_overrides/
├── data/
├── figures/
└── papers/
```

- **`config.yaml`**
  - 当前唯一主配置文件。
  - 控制实验类型、实验参数、输出命名和 LLM API provider。

- **`runner.py`**
  - 当前主运行入口。
  - 执行 `config.yaml` 中显式启用的实验类型。

- **`plotter.ipynb`**
  - 原作者绘图与统计分析 notebook。
  - 用于检查实验结果、复现论文图表、后续绘制我们自己的对比图。

- **`author_code/`**
  - 原作者核心实验代码和理论模型代码。
  - 包含群体模拟、prompt 构造、本地模型调用、theoretical naming game 等。

- **`project_overrides/`**
  - 本项目新增或改造的代码。
  - 当前主要包含多 provider API 适配层。

- **`data/`**
  - 实验输出数据目录。
  - 新实验默认输出 `.pkl` 文件到这里。

- **`figures/`**
  - 绘图输出目录。

- **`papers/`**
  - 论文 PDF 与补充材料。

## 实验类型

实验类型在 `config.yaml` 中控制：

```yaml
experiments:
  individual_bias: True
  collective_convergence: False
  committed_minority: False
  individual_repeats: 20
```

- **`individual_bias`**
  - 单个 LLM agent 的个体偏见测试。
  - 检查模型在没有群体互动时是否偏好某个 convention 标签。

- **`collective_convergence`**
  - 多个 LLM agents 的群体互动实验。
  - 检查群体是否会自发形成共同社会约定。

- **`committed_minority`**
  - 坚定少数派实验。
  - 检查少数坚定 agents 是否能推动群体改变已有 convention。

- **`individual_repeats`**
  - `individual_bias` 实验中的重复询问次数。
  - 数值越大，API 调用越多。

## 运行方式

请先进入项目目录，并使用自己的 conda 环境。例如：

```bash
conda activate cep
```

安装必要依赖：

```bash
pip install -r requirements.txt
```

运行当前启用的实验：

```bash
python runner.py
```

注意：本项目约定使用当前 conda 环境中的 `python`，不要使用项目内 `.venv`。

## LLM API 配置

远程 LLM API 在 `config.yaml` 的 `api` 部分配置：

```yaml
api:
  active_provider: kimi
  providers:
    kimi:
      type: openai_compatible
      model: "kimi-k2-turbo-preview"
      api_key: "..."
      base_url: "https://api.moonshot.cn/v1"
```

当前 `active_provider` 指向哪个 provider，实验就调用哪个远程模型。

`model.shorthand` 只用于输出文件名前缀，例如：

```yaml
model:
  shorthand: "kimi"
```

对应输出：

```text
data/kimi_*.pkl
```

## 输出数据

实验结果默认保存为 `.pkl` 文件。

`.pkl` 是 Python pickle 格式，可以保存复杂对象，例如：

- agents 的历史
- 每轮互动玩家
- 每轮选择结果
- 成功率轨迹
- 收敛信息

默认输出目录：

```text
data/
```

## 关于 Q 和 M

`Q` 和 `M` 是 naming game 中的候选 convention 标签，本身没有固定语义。

它们可以理解为两个任意符号：

- `Q`：候选约定 A
- `M`：候选约定 B

实验关注的是 LLM 群体是否会在互动后收敛到同一个标签。

## 理论 naming game

原作者还提供了 theoretical naming game 模型：

```text
author_code/run_NG.py
author_code/NG_module.py
```

这部分不调用 LLM API，用于生成理论对照数据。当前主实验入口仍是根目录下的：

```text
runner.py
```

## 绘图与结果复核

使用：

```text
plotter.ipynb
```

该 notebook 可用于：

- 读取 `.pkl` 实验结果
- 复核原论文图表
- 统计 individual bias、collective bias、convergence、committed minority 等结果
- 后续绘制我们自己的复现实验或微调实验对比图

## 重要说明

本项目是在原作者代码基础上的学习、复现与扩展项目。若用于论文、报告或公开发布，请引用原论文，并保留 `LICENSE` 中的原始版权与许可信息。
