# 高等代数解题要点

## 适用与边界

涵盖多项式理论、行列式、矩阵、线性方程组、二次型、线性空间与线性变换、欧氏空间、特征值与对角化、Jordan 标准形。群/环/域/Galois 结构题归抽象代数，实变量极限与收敛归数学分析。所有结果必须保留系数域、维数、重数、可逆变换与退化情形。

## 多项式理论

- **带余除法**：$f=qg+r$，$\deg r<\deg g$；余数定理 $r=f(a)$ 当 $g=x-a$。
- **最大公因式**用辗转相除法，最后一个非零余式归一化；中间余式可乘非零常数简化。
- **互素**：$(f,g)=1\iff\exists u,v:\ uf+vg=1$（Bézout）。
- **不可约**依赖系数域：$x^2+1$ 在 $\mathbb R[x]$ 不可约、在 $\mathbb C[x]$ 可约。
- **重根**：$f$ 有重根 $\iff\gcd(f,f')\neq1$。
- **Eisenstein 判据**：素数 $p$ 使 $p\mid a_i\ (i<n)$、$p\nmid a_n$、$p^2\nmid a_0$，则 $f$ 在 $\mathbb Q[x]$ 不可约；分圆多项式 $\Phi_p$ 需先代换 $x\to x+1$ 再用。

## 行列式

- 基本性质：$\det(AB)=\det A\det B$，$\det A^T=\det A$，交换两行变号，行倍加不变。
- **Vandermonde**：$\det(x_j^{\,i-1})_{i,j}=\prod_{i<j}(x_j-x_i)$。
- 计算流程：观察结构（Vandermonde/三对角/分块）→ 行倍加造零 → 按行/列展开 → 含参用试根法因式分解。
- 特征多项式 $p_A(\lambda)=\det(\lambda I-A)$。
- **易错点**：$k$ 行各有公因子 $c$ 时提出的是 $c^k$；Laplace 展开的 $(-1)^{i+j}$ 别漏；Hadamard 不等式 $\det A\le\prod a_{ii}$（$A$ 正定对称）。

## 矩阵

- **可逆**：$A$ 可逆 $\iff\det A\neq0\iff\operatorname{rank}A=n$；二阶逆 $\begin{pmatrix}a&b\\c&d\end{pmatrix}^{-1}=\frac{1}{ad-bc}\begin{pmatrix}d&-b\\-c&a\end{pmatrix}$。
- **求逆**：$[A|I]$ 只用行变换化 $[I|A^{-1}]$（不可混用列变换）。
- **秩**：行阶梯形非零行数；Sylvester 不等式 $\operatorname{rank}(AB)\ge\operatorname{rank}A+\operatorname{rank}B-n$。
- **Jordan 标准形**：每个复方阵相似于 $J=\bigoplus J_{m_i}(\lambda_i)$；块大小是特征链长度而非特征值重数。
- **对角化**：$A$ 可对角化 $\iff$ 每个特征值代数重数 $=$ 几何重数 $\iff$ 极小多项式无重根。实对称矩阵必可正交对角化。

## 线性方程组

- 齐次 $Ax=0$ 有非零解 $\iff\operatorname{rank}A<n$；非齐次 $Ax=b$ 有解 $\iff\operatorname{rank}A=\operatorname{rank}[A|b]$。
- 通解 $=$ 特解 $+$ 齐次解；基础解系含 $n-\operatorname{rank}A$ 个向量。
- 求基础解系：行变换化 RREF → 定主元列与自由列 → 自由变量依次取「1，其余 0」。
- 验证：把求得的解代回原方程组。

## 二次型

- 二次型 $f=x^TAx$（$A$ 实对称）；配方法化为平方和，线性替换必须可逆。
- 无平方项时用 $x_i=y_i+y_j,\ x_j=y_i-y_j$ 创造平方项。
- **正定判别**：所有顺序主子式 $>0$（或特征值全正）；半正定用顺序主子式 $\ge0$ 只是必要非充分。
- **惯性定理**：正负惯性指数由二次型唯一确定。

## 线性空间与线性变换

- 基与维数：极大线性无关组；坐标依赖基的次序。
- **秩-零化度**：$\dim\ker\sigma+\dim\operatorname{Im}\sigma=\dim V$。
- 求核：解 $Ax=0$ 得解空间基；证线性无关设线性组合为 0 推系数全零。
- 同时对角化：$AB=BA$ 且均可对角化 $\Rightarrow$ 可同时对角化。

## 欧氏空间与正交化

- **Gram–Schmidt**：$u_k=v_k-\sum_{i=1}^{k-1}\frac{\langle v_k,u_i\rangle}{\langle u_i,u_i\rangle}u_i$，再单位化；分母是 $\langle u_i,u_i\rangle$ 不是 $\langle v_i,v_i\rangle$。
- 正交变换 $Q^TQ=I$，$\det Q=\pm1$，保持内积与范数。
- 正交投影（到标准正交基张成的子空间）：$P_Wv=\sum_i\langle v,e_i\rangle e_i$；非正交基不能直接用求和公式。
- 谱定理：实对称（自伴）矩阵可正交对角化，特征值全实，不同特征值的特征向量正交。

## 特征值与对角化

- $Av=\lambda v$（$v\neq0$）；三角矩阵特征值即对角元。
- $\sum\lambda_i=\operatorname{tr}A$，$\prod\lambda_i=\det A$；$A$ 可逆 $\iff0$ 不是特征值；$A^{-1}$ 特征值为 $\lambda^{-1}$。
- Cayley–Hamilton：$p_A(A)=0$，故极小多项式 $m_A\mid p_A$。
- 几何重数 $=n-\operatorname{rank}(\lambda I-A)$；块结构由 $\dim\ker(\lambda I-A)^k$ 的增量 $r_k-r_{k-1}$ 递推得到。
- 验证：特征值用迹核对，特征向量代回 $Av=\lambda v$。

## 统一框架与验证

矩阵问题先问三问：在什么变换下有意义（等价/相似/合同）？该变换下什么量不变（秩/迹/行列式/特征多项式/极小多项式）？能否对角化？

| 计算 | 验证方法 |
|---|---|
| 逆矩阵 | $AA^{-1}=I$ |
| 特征值 | $\sum\lambda_i=\operatorname{tr}A$ |
| 基础解系 | 代回原方程组 |
| Schmidt 结果 | 两两内积为 0 |
| 秩 | 行、列阶梯形各算一次 |
