# Exploring Graph Mamba

**A Comprehensive Survey on State-Space Models for Graph Learning**

**ACM Computing Surveys — Under Revision**

**Authors:** Safa Ben Atitallah · Chaima Ben Rabah · Maha Driss · Wadii Boulila · Anis Koubaa

🌐 **[Explore the Interactive Website](https://riotu-lab.github.io/awesome-graph-mamba/)**

## Abstract

Recently, Graph Mamba has emerged as a promising approach for extending selective State Space Models (SSMs) to graph-structured data, with the aim of efficiently capturing long-range dependencies in graphs. This survey provides a systematic review of Graph Mamba, with particular emphasis on its architectural developments, applications, comparative performance, limitations, and future research directions.

We first introduce the foundations of SSMs and Mamba necessary to understand their adaptation to graph-structured data. Then, we examine representative Graph Mamba architectures and focus on their graph-to-sequence construction, ordering strategies, structural encoding, and graph-aware state-space mechanisms. We organize these architectures around four design questions: what the state-space model reads (tokenization), in what order it reads it (ordering), how deeply graph structure shapes the state dynamics (coupling), and how the state-space model works alongside graph propagation (integration).

We also review recent applications of Graph Mamba across different domains and graph learning tasks. Furthermore, we provide benchmark and comparative analyses to examine the performance and characteristics of existing Graph Mamba approaches across different tasks. Finally, we discuss current limitations, open challenges, and emerging research directions, including opportunities for improving scalability, structural modeling, interpretability, and applicability.

This survey provides an architectural and comparative perspective on the rapidly evolving field of Graph Mamba and aims to support further research on selective state-space modeling for graph-structured data.

## Paper Structure

The survey is organized into eight sections:

**Section 1 — Introduction**

Introduces the motivation for Graph Mamba, research questions, survey contributions, and literature selection methodology.

**Section 2 — Foundations and Unified Formulation**

Reviews graph neural networks, state-space models, and Mamba, and presents a unified graph-to-state-space formulation based on four design dimensions:

- **D1 — Tokenization:** What does the state-space model read?
- **D2 — Ordering:** In what order are graph elements processed?
- **D3 — Coupling:** How does graph structure influence state-space dynamics?
- **D4 — Integration:** How does state-space processing interact with graph propagation?

**Section 3 — Architectural Taxonomy**

Classifies Graph Mamba architectures into three main categories:

- General-purpose graph learning models.
- Dynamic and spatio-temporal graph models.
- Heterogeneous and higher-order graph models.

**Section 4 — Structural and Computational Analysis**

Examines the implications of architectural design choices, including structural information preservation, permutation sensitivity, expressivity, computational complexity, and scalability.

**Section 5 — Applications and Cross-Domain Patterns**

Reviews Graph Mamba applications across different domains and identifies recurring graph–SSM integration patterns.

**Section 6 — Benchmark and Performance Analysis**

Analyzes reported experimental results, benchmark datasets, comparative performance, and efficiency evidence across existing approaches.

**Section 7 — Open Challenges and Future Research Directions**

Discusses remaining challenges, including structural modeling, computational efficiency, interpretability, evaluation consistency, and generalization.

**Section 8 — Conclusion**

Summarizes the main findings and outlines the broader perspectives for future Graph Mamba research.

## Interactive Companion Website

The **[Graph Mamba Explorer](https://riotu-lab.github.io/awesome-graph-mamba/)** complements the survey by providing interactive access to:

- The D1–D4 architectural taxonomy.
- Reviewed Graph Mamba models and their classifications.
- Research trends and application domains.
- Interactive comparison matrices, heatmaps, charts, and tables.
- Benchmark results and architectural comparisons.
- Research challenges and future directions.

## Repository Structure

| Path | Description |
|---|---|
| `docs/index.html` | Main interactive website |
| `docs/comparison.html` | Comparative analysis page |
| `README.md` | Survey and repository documentation |
| `CITATION.cff` | Citation metadata |
| `LICENSE` | Repository license |

The interactive website is hosted using GitHub Pages.

## Citation

If you use this survey or its companion website, please cite:

```bibtex
@article{benatitallah2026exploring,
  title   = {Exploring Graph Mamba: A Comprehensive Survey on State-Space Models for Graph Learning},
  author  = {Ben Atitallah, Safa and Ben Rabah, Chaima and Driss, Maha and Boulila, Wadii and Koubaa, Anis},
  journal = {ACM Computing Surveys},
  year    = {2026},
  note    = {Under revision}
}
```

## Repository

Maintained under the **Robotics and Internet of Things Laboratory (RIOTU)**, Prince Sultan University, Saudi Arabia.

**GitHub:** https://github.com/riotu-lab/awesome-graph-mamba

**Website:** https://riotu-lab.github.io/awesome-graph-mamba/

## License

This repository is released under the [MIT License](LICENSE).
