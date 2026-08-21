# 抽象代数解题要点

## 适用与边界

涵盖群论（子群、商群、同态与同构定理）、对称群与群作用（共轭类、类方程）、Sylow 定理、环论（零因子、理想、极大/素理想）、多项式环与域扩张、有限域、有限 Abel 群分类与 Galois 理论基本定理。纯矩阵/线性空间计算归高等代数，实变量函数方程归数学分析。必须明确运算、单位元、子群/理想闭性与扩张次数。

## 群的基本概念

- 群定义三要素：结合律、单位元 $e$、逆元；Abel 群满足 $ab=ba$。
- 循环群 $G=\langle g\rangle$：有限阶 $n$ 时 $G\cong\mathbb Z_n$；$g^k$ 的阶为 $\frac{n}{\gcd(k,n)}$。
- 置换的阶：分解为不相交轮换，阶为各轮换长度的最小公倍数 $\operatorname{lcm}(\ell_1,\dots,\ell_r)$。
- Lagrange 定理推论：有限群中元素阶必整除群阶。
- 证明 $a^2=e\Rightarrow G$ 交换：展开 $(ab)^2=e$ 得 $abab=e$，左乘 $a$、右乘 $b$ 得 $ba=ab$。

## 子群、商群与同态

- 子群判定：$H\neq\varnothing$ 且 $a,b\in H\Rightarrow ab^{-1}\in H$；循环群子群与 $n$ 的正因子一一对应（因子 $d$ 对应 $\langle n/d\rangle$）。
- 陪集：左陪集 $aH$、右陪集 $Ha$；$|aH|=|H|$，$[G:H]=|G|/|H|$。
- 正规子群：$gHg^{-1}=H$ 对所有 $g$；指数为 2 的子群必正规（$g\notin H$ 时 $gH=G\setminus H=Hg$）。
- 商群在 $(aH)(bH)=(ab)H$ 下成群的充要条件是 $H\trianglelefteq G$。
- 同态 $\varphi:G\to H$：核 $\ker\varphi\trianglelefteq G$，像 $\operatorname{Im}\varphi\le H$；第一同构定理 $G/\ker\varphi\cong\operatorname{Im}\varphi$（证明四步：良定、同态、单射、满射）。
- 循环群同态 $\varphi:\mathbb Z_m\to\mathbb Z_n,\ \varphi(1)=k$：像 $\operatorname{Im}\varphi=\langle\gcd(k,n)\rangle$，核为 $\{x\in\mathbb Z_m:kx\equiv0\pmod n\}$，且 $|\ker|\cdot|\operatorname{Im}|=m$。
- 直积中 $\operatorname{ord}((a,b))=\operatorname{lcm}(\operatorname{ord}a,\operatorname{ord}b)$。

## 对称群与群作用

- $|S_n|=n!$；置换唯一分解为不相交轮换；共轭类 $=$ 轮换型。
- 轮换型 $1^{c_1}2^{c_2}\cdots n^{c_n}$ 的共轭类大小：$\frac{n!}{\prod_i i^{c_i}\,c_i!}$（分母的 $c_i!$ 是相同长度轮换的排列冗余）。
- 类方程：$|G|=|Z(G)|+\sum[G:C_G(g_i)]$（$g_i$ 取非中心共轭类代表）。
- 轨道-稳定子：$|\operatorname{Orb}(x)|=[G:\operatorname{Stab}(x)]$。
- 二面体群 $D_{2n}=\langle r,s\mid r^n=s^2=e,srs=r^{-1}\rangle$：旋转构成正规循环子群，反射均为二阶元；中心与换位子群常用共轭公式 $sr^ks^{-1}=r^{-k}$ 判定。

## Sylow 定理

设 $|G|=p^km$（$p\nmid m$）：
- 第一定理（存在性）：$p^k$ 阶子群存在。
- 第二定理（共轭性）：所有 Sylow $p$-子群共轭。
- 第三定理（计数）：$n_p\equiv1\pmod p$ 且 $n_p\mid m$，且 $n_p=[G:N_G(P)]$。
- Sylow $p$-子群正规 $\iff n_p=1$。
- **易错点**：$n_p\mid m$ 不是 $n_p\mid|G|$；两个必要条件可能仍不唯一，需用群作用/嵌入 $S_{n_p}$ 进一步排除；$n_p=1$ 的排除必须给出理由。

## 环论基础

- 环 = 加法 Abel 群 + 结合分配乘法；含幺交换环、整环（无零因子）、域（每个非零元可逆）。
- $\mathbb Z_n$：$a$ 是单位 $\iff\gcd(a,n)=1$；$a$ 是零因子 $\iff\gcd(a,n)>1$；$\mathbb Z_n$ 是域 $\iff n$ 是素数。
- 理想 $I$ 是加法子群且 $rI,Ir\subseteq I$；商环 $R/I$ 元素为陪集。
- **极大理想**：$M$ 极大 $\iff R/M$ 是域；**素理想**：$P$ 素 $\iff R/P$ 是整环。含幺交换环中极大 $\Rightarrow$ 素，反之不成立（如 $\mathbb Z[x]$ 中 $\langle x\rangle$ 素但非极大）。
- $\mathbb Z[x]/\langle2,x\rangle\cong\mathbb Z_2$ 是域，故 $\langle2,x\rangle$ 极大，从而 $\mathbb Z[x]$ 不是 PID。
- 蕴含链：欧几里得环 $\Rightarrow$ PID $\Rightarrow$ UFD；$\mathbb Z[x]$ 是 UFD 非 PID。

## 多项式与域扩张

- 不可约判定：有理根检验、Eisenstein 判据、模 $p$ 约化（在 $\mathbb F_p$ 不可约则 $\mathbb Q$ 不可约）、分圆多项式代换后 Eisenstein。
- 单扩张：$\alpha$ 代数时 $[F(\alpha):F]=\deg m_\alpha$，其中 $m_\alpha$ 为极小多项式。
- **塔定理**：$F\subseteq K\subseteq E$ 则 $[E:F]=[E:K][K:F]$；基为两层的基之积 $\{e_if_j\}$。
- 极小多项式求法（降幂展开）：取线性无关基（如 $\{1,\sqrt[3]a,(\sqrt[3]a)^2\}$），把 $\alpha$ 的各次幂在基下展开，由维数有限必线性相关，解线性方程组得系数。
- 分裂域不能只凭「加入一个根」判断：$x^n+a$ 型需同时考虑本原单位根，用塔定理逐层计算，并验证根域与单位根域是否线性无交。
- **易错点**：$\sqrt3\notin\mathbb Q(\sqrt2)$ 需反证（设 $\sqrt3=a+b\sqrt2$ 平方比系数）；仅立方一次 $\alpha^3=a+b+3\sqrt[3]{ab}\,\alpha$ 仍含交叉项，需系统计算各次幂。

## 有限域

- 每个素数幂 $q=p^n$ 存在唯一 $q$ 元有限域 $\mathbb F_q\cong\mathbb F_p[x]/(f)$，$f$ 为 $n$ 次不可约多项式。
- 乘法群 $\mathbb F_q^\times$ 是 $q-1$ 阶循环群；生成元阶为 $q-1$，验证法：对 $q-1$ 的每个素因子 $p$，检查 $\alpha^{(q-1)/p}\neq1$。
- 加法群 $\mathbb F_q\cong(\mathbb Z_p)^n$ 是初等 Abel $p$-群，一般非循环（除非 $n=1$）。
- 生成元计数：$\alpha$ 生成 $\mathbb F_{p^n}$ $\iff$ $\alpha$ 不属于任何真子域 $\mathbb F_{p^d}$（$d\mid n,\ d<n$）；生成元个数 $=p^n-|\text{极大真子域并集}|$，多素因子时用容斥。

## 有限 Abel 群分类

- 结构定理：有限 Abel 群同构于循环 $p$-群的直积，分解（按初等因子）唯一。
- $|G|=\prod p_i^{e_i}$ 时，同构类个数 $=\prod_i P(e_i)$，$P(e)$ 为 $e$ 的分拆数。
- 初等因子是素数幂；不变因子满足 $d_1\mid d_2\mid\cdots\mid d_k$ 且乘积为 $|G|$。用 $\gcd(a,b)=1\Rightarrow\mathbb Z_a\times\mathbb Z_b\cong\mathbb Z_{ab}$（中国剩余定理）化简。
- **易错点**：分类必须枚举全部对象并给出总数；初等因子与不变因子是同一群的不同写法。

## Galois 理论基本定理

- 代数扩张 $[E:F]$ 为向量空间维数；可分（极小多项式无重根，特征 0 自动）+ 正规（分裂域）$\Rightarrow$ Galois 扩张，此时 $|\operatorname{Gal}(E/F)|=[E:F]$。
- 基本定理：中间域 $\{K\}$ 与子群 $\{H\}$ 反序双射，$[E:K]=|H|$、$[K:F]=[G:H]$；$K/F$ 正规 $\iff H\triangleleft G$，且 $\operatorname{Gal}(K/F)\cong G/H$。
- 求 Galois 群：确定分裂域次数与根上的置换，常为 $S_n,A_n,C_n,D_n$。
- **易错点**：分裂域次数 $\neq$ 极小多项式次数（要乘单位根部分）；基本定理是反序对应；可分非正规与正规不可分都存在。
