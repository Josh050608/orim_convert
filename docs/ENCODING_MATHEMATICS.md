# ORIM 编码系统数学原理详解

## 目录
1. [系统概述](#系统概述)
2. [PRF 伪随机函数](#prf-伪随机函数)
3. [排列编码基础](#排列编码基础)
4. [完全二叉树变长编码](#完全二叉树变长编码)
5. [整体编码流程](#整体编码流程)
6. [解码流程](#解码流程)

---

## 系统概述

ORIM (Order Rewriting Implicit Messaging) 是一个隐蔽信道系统，通过重排比特币交易哈希的顺序来传递隐蔽信息。核心思想是：

**将秘密比特 → 编码为排列的秩 (Rank) → 对应唯一的排列 → 重排哈希顺序**

整个过程分为三个关键步骤：
1. **PRF混淆**：使用伪随机函数计算哈希的混淆值，确定"自然顺序"
2. **比特到秩映射**：使用完全二叉树变长编码将比特串映射到排列的秩
3. **秩到排列转换**：使用 Lehmer 码（阶乘进制）将秩转换为具体的排列

---

## PRF 伪随机函数

### 数学定义

伪随机函数（Pseudorandom Function, PRF）用于将比特币交易哈希映射到一个确定性但看似随机的整数空间：

$$
\text{PRF}: \{0,1\}^{256} \to \mathbb{Z}_{2^{256}}
$$

### 实现方法

使用 HMAC-SHA256 构造 PRF：

$$
\text{PRF}(h) = \text{HMAC-SHA256}(k, h)
$$

其中：
- $h$ 是交易哈希的十六进制字符串
- $k$ 是双方共享的密钥（256 位）
- 输出是 256 位整数

### 代码实现

```python
def prf(self, hash_hex: str) -> int:
    """PRF: Hash → Integer (HMAC-SHA256 based)"""
    hash_bytes = bytes.fromhex(hash_hex)
    hmac_obj = hmac.new(self.prf_key, hash_bytes, hashlib.sha256)
    # Use full 256-bit output for better distribution
    return int.from_bytes(hmac_obj.digest(), byteorder='big')
```

### 安全性质

1. **确定性**：相同输入产生相同输出
2. **单向性**：已知 $\text{PRF}(h)$ 无法反推 $h$
3. **伪随机性**：输出在 $[0, 2^{256})$ 上均匀分布
4. **密钥依赖**：不同密钥产生完全不同的映射

### 应用场景

给定 $n$ 个交易哈希 $H = \{h_1, h_2, \ldots, h_n\}$，计算混淆值：

$$
V_i = \text{PRF}(h_i), \quad i = 1, 2, \ldots, n
$$

**自然顺序**定义为混淆值从小到大排序后的索引序列：

$$
\sigma_{\text{natural}} = \text{argsort}(V_1, V_2, \ldots, V_n)
$$

发送端和接收端共享密钥 $k$，因此都能独立计算出相同的自然顺序。

---

## 排列编码基础

### 排列空间

对于 $n$ 个元素，所有可能的排列构成对称群 $S_n$，共有 $N = n!$ 个排列。

**示例**（$n=3$）：
$$
S_3 = \{(0,1,2), (0,2,1), (1,0,2), (1,2,0), (2,0,1), (2,1,0)\}
$$

其中 $N = 3! = 6$ 个排列。

### Lehmer 码（阶乘进制）

Lehmer 码是一种将排列映射到唯一整数的方法，基于**阶乘进制数系统**。

#### 排列 → Lehmer 码

对于排列 $\pi = (\pi_0, \pi_1, \ldots, \pi_{n-1})$，Lehmer 码定义为：

$$
L_i = \left|\{j > i : \pi_j < \pi_i\}\right|
$$

即：$L_i$ 表示 $\pi_i$ 右侧有多少个元素比它小（**逆序数**）。

**示例**：排列 $(2, 0, 1)$
- $L_0 = 2$（右侧有 0, 1 两个元素比 2 小）
- $L_1 = 0$（右侧只有 1，不比 0 小）
- $L_2 = 0$（右侧无元素）

$$
\text{Lehmer}(2, 0, 1) = [2, 0, 0]
$$

#### Lehmer 码 → 秩（Rank）

秩是排列在字典序中的索引，使用阶乘进制计算：

$$
\text{Rank}(\pi) = \sum_{i=0}^{n-1} L_i \cdot (n-1-i)!
$$

**示例**：$L = [2, 0, 0]$，$n = 3$

$$
\begin{align}
\text{Rank} &= 2 \cdot 2! + 0 \cdot 1! + 0 \cdot 0! \\
&= 2 \cdot 2 + 0 + 0 \\
&= 4
\end{align}
$$

因此排列 $(2, 0, 1)$ 的秩为 4。

#### 秩 → Lehmer 码

反向过程使用阶乘进制分解：

$$
\text{Rank} = \sum_{i=0}^{n-1} L_i \cdot (n-1-i)!
$$

从高位到低位依次计算：

$$
\begin{align}
L_i &= \left\lfloor \frac{\text{Rank}}{(n-1-i)!} \right\rfloor \\
\text{Rank} &\leftarrow \text{Rank} \mod (n-1-i)!
\end{align}
$$

#### Lehmer 码 → 排列

使用可用元素列表进行贪心选择：

```python
def lehmer_to_permutation(lehmer: List[int]) -> List[int]:
    available = list(range(len(lehmer)))
    return [available.pop(c) for c in lehmer]
```

**示例**：$L = [2, 0, 0]$

| 步骤 | $L_i$ | available     | 选择元素 | 排列 |
|------|-------|---------------|----------|------|
| 0    | 2     | [0, 1, 2]     | 2        | [2]  |
| 1    | 0     | [0, 1]        | 0        | [2, 0] |
| 2    | 0     | [1]           | 1        | [2, 0, 1] |

### 信息容量

$n$ 个元素的排列可以唯一表示 $[0, n!-1]$ 范围内的整数，因此信息容量为：

$$
C(n) = \log_2(n!) \approx n \log_2 n - n \log_2 e \quad \text{bits}
$$

**示例**：
- $n=5$: $C(5) = \log_2(120) \approx 6.91$ bits
- $n=10$: $C(10) = \log_2(3628800) \approx 21.79$ bits

---

## 完全二叉树变长编码

### 问题描述

**挑战**：排列容量 $N = n!$ 通常**不是 2 的幂次**，导致固定长度编码会浪费空间。

**示例**：$n=5$ 时 $N = 120$
- 固定 7 位编码：$2^7 = 128 > 120$，浪费 8 个码字
- 固定 6 位编码：$2^6 = 64 < 120$，容量不足

**解决方案**：使用**变长编码**，部分秩用短码，部分秩用长码。

### 层数计算

定义层数 $m$ 为满足以下条件的最小正整数：

$$
2^{m-1} \leq N < 2^m
$$

等价于：

$$
m = \lceil \log_2 N \rceil
$$

**物理意义**：
- $N$ 落在完全二叉树的第 $m$ 层和第 $m-1$ 层之间
- 第 $m$ 层最多容纳 $2^m$ 个叶子节点
- 第 $m-1$ 层最多容纳 $2^{m-1}$ 个叶子节点

### 阈值定义

定义阈值 $T$ 为第 $m$ 层的叶子节点数：

$$
T = 2N - 2^m
$$

**推导**：
- 完全二叉树总共需要 $N$ 个叶子节点
- 第 $m-1$ 层贡献 $2^{m-1}$ 个叶子
- 第 $m$ 层需要补充 $N - 2^{m-1}$ 个叶子
- 但第 $m$ 层每个叶子占用第 $m-1$ 层的 2 个位置
- 因此第 $m$ 层实际叶子数：$T = 2(N - 2^{m-1}) = 2N - 2^m$

### 编码规则

将秩空间 $[0, N-1]$ 划分为两个区间：

$$
\begin{cases}
\text{Layer } m \text{ (长码)}: & \text{Rank} \in [0, T-1] \to m \text{ bits} \\
\text{Layer } m-1 \text{ (短码)}: & \text{Rank} \in [T, N-1] \to m-1 \text{ bits}
\end{cases}
$$

#### Layer m (长码)

对于 $\text{Rank} \in [0, T-1]$：

$$
\text{Bits} = \text{Binary}(\text{Rank}, m)
$$

直接将秩转为 $m$ 位二进制。

#### Layer m-1 (短码)

对于 $\text{Rank} \in [T, N-1]$：

$$
\text{Bits} = \text{Binary}(\text{Rank} - (N - 2^{m-1}), m-1)
$$

**推导**：
- Layer m-1 的起始秩：$\text{Rank}_{\text{start}} = N - 2^{m-1}$
- 相对偏移：$\text{Offset} = \text{Rank} - (N - 2^{m-1})$
- 转为 $m-1$ 位二进制：$\text{Offset} \in [0, 2^{m-1}-1]$

### 数学示例

#### Case 1: $n=5, N=120$

$$
\begin{align}
m &= \lceil \log_2 120 \rceil = 7 \\
T &= 2 \times 120 - 2^7 = 240 - 128 = 112
\end{align}
$$

编码映射：
- Rank 0-111：7 位长码，值域 `0000000` - `1101111`
- Rank 112-119：6 位短码，值域 `000000` - `000111`

**验证**：
- 长码容量：$T = 112$ 个秩
- 短码容量：$2^{m-1} = 64$ 个秩
- 总容量：$112 + 64 = 176 > 120$（实际只用 120 个）

#### Case 2: $n=3, N=6$

$$
\begin{align}
m &= \lceil \log_2 6 \rceil = 3 \\
T &= 2 \times 6 - 2^3 = 12 - 8 = 4
\end{align}
$$

编码映射：

| Rank | Layer   | Bits   | 二进制值 |
|------|---------|--------|----------|
| 0    | m       | `000`  | 0        |
| 1    | m       | `001`  | 1        |
| 2    | m       | `010`  | 2        |
| 3    | m       | `011`  | 3        |
| 4    | m-1     | `00`   | 0        |
| 5    | m-1     | `01`   | 1        |

**验证**：
- Rank 0-3：3 位长码
- Rank 4-5：2 位短码
- 平均码长：$(4 \times 3 + 2 \times 2) / 6 = 2.67$ bits
- 理论最优：$\log_2 6 = 2.585$ bits（接近最优！）

### "检查与消费"策略

在编码时，发送端需要决定消费多少位比特。核心策略：

#### 步骤 1：窥视 $m$ 位

从待发送比特流中**窥视**（peek）前 $m$ 位，计算其值 $v_m$：

$$
v_m = \text{Binary2Int}(\text{bits}[0:m])
$$

#### 步骤 2：判断层数

$$
\begin{cases}
v_m < T & \to \text{使用 Layer m（长码）} \\
v_m \geq T & \to \text{使用 Layer m-1（短码）}
\end{cases}
$$

#### 步骤 3：消费比特并计算秩

**Case A：使用 Layer m**
$$
\begin{align}
\text{Consumed} &= m \\
\text{Rank} &= v_m
\end{align}
$$

**Case B：使用 Layer m-1**
$$
\begin{align}
\text{Consumed} &= m - 1 \\
v_{m-1} &= \text{Binary2Int}(\text{bits}[0:m-1]) \\
\text{Rank} &= N - 2^{m-1} + v_{m-1}
\end{align}
$$

#### 数学保证

**定理**：对于任意比特串，"检查与消费"策略保证：

$$
\text{Rank} < N
$$

**证明**：

**Case A**（$v_m < T$）：
$$
\text{Rank} = v_m < T < N \quad \checkmark
$$

**Case B**（$v_m \geq T$）：
$$
\begin{align}
\text{Rank} &= N - 2^{m-1} + v_{m-1} \\
&< N - 2^{m-1} + 2^{m-1} \\
&= N \quad \checkmark
\end{align}
$$

因为 $v_{m-1} \in [0, 2^{m-1}-1]$。

### 代码实现

```python
def bits_to_rank(self, bits: str, n: int) -> Tuple[int, int]:
    """Complete Binary Tree Variable-Length Encoding"""
    N = factorial(n)
    
    # Calculate layer m: 2^(m-1) ≤ N < 2^m
    m = 1
    while (1 << m) < N:
        m += 1
    
    # Threshold T = 2N - 2^m
    T = 2 * N - (1 << m)
    
    # Special case: N is exactly a power of 2
    if T == 0:
        val_m = int(bits[:m], 2)
        return val_m, m
    
    # Check & Consume strategy
    if len(bits) >= m:
        val_m = int(bits[:m], 2)
        
        if val_m < T:
            # Layer m (Long Code)
            return val_m, m
        else:
            # Layer m-1 (Short Code)
            val_m_minus_1 = int(bits[:m-1], 2)
            rank = N - (1 << (m - 1)) + val_m_minus_1
            return rank, m - 1
    
    # Insufficient bits, use Layer m-1
    elif len(bits) >= m - 1:
        val_m_minus_1 = int(bits[:m-1], 2)
        rank = N - (1 << (m - 1)) + val_m_minus_1
        return rank, m - 1
    
    # Too few bits, pad and use Layer m-1
    else:
        bits_padded = bits.ljust(m - 1, '0')
        val_m_minus_1 = int(bits_padded, 2)
        rank = N - (1 << (m - 1)) + val_m_minus_1
        return rank, len(bits)
```

---

## 整体编码流程

### 输入与输出

**输入**：
- $n$ 个比特币交易哈希 $H = \{h_1, h_2, \ldots, h_n\}$
- 共享密钥 $k$
- 待传输比特流 $B = b_1b_2\cdots b_L$

**输出**：
- 重排后的哈希序列 $H' = \{h_{\pi(1)}, h_{\pi(2)}, \ldots, h_{\pi(n)}\}$

### 完整数学流程

#### Step 1: PRF 混淆

计算每个哈希的混淆值：

$$
V_i = \text{PRF}(h_i) = \text{HMAC-SHA256}(k, h_i), \quad i = 1, \ldots, n
$$

#### Step 2: 确定自然顺序

对混淆值排序，得到自然顺序排列 $\sigma_{\text{natural}}$：

$$
\sigma_{\text{natural}} = \text{argsort}(V_1, V_2, \ldots, V_n)
$$

**示例**：
$$
V = [245, 67, 189] \to \sigma_{\text{natural}} = [1, 2, 0]
$$

（索引 1 的值最小，索引 2 次之，索引 0 最大）

#### Step 3: 比特到秩映射

使用完全二叉树编码将比特转为秩：

$$
(\text{Rank}, \text{Consumed}) = \text{BitsToRank}(B, n)
$$

**详细步骤**：
1. 计算 $N = n!$, $m$, $T$
2. 窥视 $m$ 位，判断使用 Layer m 还是 Layer m-1
3. 消费相应位数，计算目标秩

#### Step 4: 秩到排列映射

将秩转为 Lehmer 码，再转为排列：

$$
\begin{align}
L &= \text{RankToLehmer}(\text{Rank}, n) \\
\pi_{\text{relative}} &= \text{LehmerToPermutation}(L)
\end{align}
$$

**RankToLehmer**：
$$
L_i = \left\lfloor \frac{\text{Rank}}{(n-1-i)!} \right\rfloor, \quad \text{Rank} \leftarrow \text{Rank} \mod (n-1-i)!
$$

**LehmerToPermutation**：
$$
\pi_{\text{relative}}[i] = \text{available}[L_i], \quad \text{available} \leftarrow \text{available} \setminus \{\pi_{\text{relative}}[i]\}
$$

#### Step 5: 复合排列

将相对排列 $\pi_{\text{relative}}$ 作用到自然顺序 $\sigma_{\text{natural}}$ 上：

$$
\pi_{\text{final}}[i] = \sigma_{\text{natural}}[\pi_{\text{relative}}[i]]
$$

**数学含义**：
- $\sigma_{\text{natural}}$：PRF 确定的"基准"顺序
- $\pi_{\text{relative}}$：秘密比特编码的"相对"扰动
- $\pi_{\text{final}}$：最终发送的实际顺序

#### Step 6: 重排哈希

根据最终排列生成输出：

$$
H' = \{h_{\pi_{\text{final}}[0]}, h_{\pi_{\text{final}}[1]}, \ldots, h_{\pi_{\text{final}}[n-1]}\}
$$

### 完整示例

#### 初始数据

- 哈希：$H = [h_0, h_1, h_2]$
- 密钥：$k = \text{0x1234...}$
- 待传输比特：$B = \texttt{101}$

#### Step 1: PRF 混淆

$$
\begin{align}
V_0 &= \text{PRF}(h_0) = 250 \\
V_1 &= \text{PRF}(h_1) = 80 \\
V_2 &= \text{PRF}(h_2) = 160
\end{align}
$$

#### Step 2: 自然顺序

排序：$80 < 160 < 250$

$$
\sigma_{\text{natural}} = [1, 2, 0]
$$

#### Step 3: 比特到秩

$n = 3, N = 6, m = 3, T = 4$

比特 `101`，$v_m = 5 \geq T = 4$，使用 Layer m-1：

$$
\begin{align}
v_{m-1} &= \text{Binary}(\texttt{10}) = 2 \\
\text{Rank} &= 6 - 4 + 2 = 4
\end{align}
$$

#### Step 4: 秩到排列

**RankToLehmer**（$\text{Rank} = 4, n = 3$）：

$$
\begin{align}
L_0 &= \lfloor 4 / 2! \rfloor = 2, \quad \text{Rank} \leftarrow 4 \mod 2 = 0 \\
L_1 &= \lfloor 0 / 1! \rfloor = 0, \quad \text{Rank} \leftarrow 0 \mod 1 = 0 \\
L_2 &= 0
\end{align}
$$

$$
L = [2, 0, 0]
$$

**LehmerToPermutation**：

| 步骤 | $L_i$ | available | 选择 | $\pi_{\text{relative}}$ |
|------|-------|-----------|------|-------------------------|
| 0    | 2     | [0,1,2]   | 2    | [2]                     |
| 1    | 0     | [0,1]     | 0    | [2,0]                   |
| 2    | 0     | [1]       | 1    | [2,0,1]                 |

$$
\pi_{\text{relative}} = [2, 0, 1]
$$

#### Step 5: 复合排列

$$
\begin{align}
\pi_{\text{final}}[0] &= \sigma_{\text{natural}}[\pi_{\text{relative}}[0]] = \sigma_{\text{natural}}[2] = 0 \\
\pi_{\text{final}}[1] &= \sigma_{\text{natural}}[\pi_{\text{relative}}[1]] = \sigma_{\text{natural}}[0] = 1 \\
\pi_{\text{final}}[2] &= \sigma_{\text{natural}}[\pi_{\text{relative}}[2]] = \sigma_{\text{natural}}[1] = 2
\end{align}
$$

$$
\pi_{\text{final}} = [0, 1, 2]
$$

#### Step 6: 输出

$$
H' = [h_0, h_1, h_2]
$$

**结果**：原始顺序！（因为 $\pi_{\text{final}} = [0, 1, 2]$ 是恒等排列）

---

## 解码流程

### 输入与输出

**输入**：
- 接收到的哈希序列 $H' = \{h'_1, h'_2, \ldots, h'_n\}$
- 共享密钥 $k$

**输出**：
- 解码比特流 $B = b_1b_2\cdots b_c$（$c$ 是变长的，取决于层数）

### 完整数学流程

#### Step 1: PRF 混淆

与发送端相同，计算混淆值：

$$
V_i = \text{PRF}(h'_i), \quad i = 1, \ldots, n
$$

#### Step 2: 确定自然顺序

对混淆值排序：

$$
\sigma_{\text{natural}} = \text{argsort}(V_1, V_2, \ldots, V_n)
$$

#### Step 3: 还原排列

构建映射表 $M: \sigma_{\text{natural}}[i] \to i$：

$$
M[\sigma_{\text{natural}}[i]] = i
$$

接收排列（相对于原始索引 0 到 n-1）：

$$
\pi_{\text{received}}[i] = i
$$

相对排列（相对于自然顺序）：

$$
\pi_{\text{relative}}[i] = M[\pi_{\text{received}}[i]]
$$

#### Step 4: 排列到秩映射

$$
\begin{align}
L &= \text{PermutationToLehmer}(\pi_{\text{relative}}) \\
\text{Rank} &= \text{LehmerToRank}(L)
\end{align}
$$

**PermutationToLehmer**：

$$
L_i = \left|\{j > i : \pi_{\text{relative}}[j] < \pi_{\text{relative}}[i]\}\right|
$$

**LehmerToRank**：

$$
\text{Rank} = \sum_{i=0}^{n-1} L_i \cdot (n-1-i)!
$$

#### Step 5: 秩到比特映射

使用完全二叉树解码：

$$
B = \text{RankToBits}(\text{Rank}, n)
$$

**详细步骤**：
1. 计算 $N = n!$, $m$, $T$
2. 判断秩所在层：
   - 如果 $\text{Rank} < T$：Layer m，转为 $m$ 位二进制
   - 如果 $\text{Rank} \geq N - 2^{m-1}$：Layer m-1，转为 $m-1$ 位二进制

$$
B = \begin{cases}
\text{Binary}(\text{Rank}, m) & \text{if } \text{Rank} < T \\
\text{Binary}(\text{Rank} - (N - 2^{m-1}), m-1) & \text{if } \text{Rank} \geq N - 2^{m-1}
\end{cases}
$$

### 解码示例

沿用前面的编码示例，假设接收到 $H' = [h_0, h_1, h_2]$。

#### Step 1-2: PRF 和自然顺序

与编码相同：$\sigma_{\text{natural}} = [1, 2, 0]$

#### Step 3: 还原排列

接收排列：$\pi_{\text{received}} = [0, 1, 2]$

映射表：

$$
M = \{1 \to 0, 2 \to 1, 0 \to 2\}
$$

相对排列：

$$
\begin{align}
\pi_{\text{relative}}[0] &= M[0] = 2 \\
\pi_{\text{relative}}[1] &= M[1] = 0 \\
\pi_{\text{relative}}[2] &= M[2] = 1
\end{align}
$$

$$
\pi_{\text{relative}} = [2, 0, 1]
$$

#### Step 4: 排列到秩

**PermutationToLehmer**：

- $L_0 = |\{j > 0 : \pi[j] < 2\}| = |\{1:0, 2:1\}| = 2$
- $L_1 = |\{j > 1 : \pi[j] < 0\}| = 0$
- $L_2 = 0$

$$
L = [2, 0, 0]
$$

**LehmerToRank**：

$$
\text{Rank} = 2 \cdot 2! + 0 \cdot 1! + 0 \cdot 0! = 4
$$

#### Step 5: 秩到比特

$\text{Rank} = 4$, $n = 3$, $N = 6$, $m = 3$, $T = 4$

判断：$\text{Rank} = 4 \geq T = 4$ 且 $4 \geq 6 - 4 = 2$，使用 Layer m-1。

$$
\begin{align}
\text{Offset} &= 4 - (6 - 4) = 2 \\
B &= \text{Binary}(2, 2) = \texttt{10}
\end{align}
$$

**结果**：解码比特 $B = \texttt{10}$（2 位）

**验证**：编码时使用比特 `101` 的前 2 位 `10`，解码正确！

---

## 性能分析

### 编码效率

对于 $n$ 个排列，理论信息容量：

$$
C_{\text{theory}} = \log_2(n!) \approx n \log_2 n - 1.44n \quad \text{bits}
$$

完全二叉树变长编码的实际平均码长：

$$
\bar{L} = \frac{T \cdot m + (N - T) \cdot (m-1)}{N}
$$

展开：

$$
\bar{L} = \frac{T \cdot m + (N - T) \cdot (m-1)}{N} = m - \frac{N - T}{N}
$$

因为 $T = 2N - 2^m$：

$$
\bar{L} = m - \frac{2^m - N}{N}
$$

**冗余度**：

$$
\text{Redundancy} = \bar{L} - \log_2 N = m - \log_2 N - \frac{2^m - N}{N}
$$

由于 $2^{m-1} \leq N < 2^m$，有 $m - 1 < \log_2 N \leq m$，因此：

$$
\text{Redundancy} < 1 + \frac{2^m - N}{N} < 2 \quad \text{bits}
$$

**结论**：冗余度不超过 2 比特，接近理论最优！

### 示例计算

| $n$ | $N = n!$ | $m$ | $T$ | $\bar{L}$ | $\log_2 N$ | 冗余度 |
|-----|----------|-----|-----|-----------|------------|--------|
| 3   | 6        | 3   | 4   | 2.67      | 2.58       | 0.09   |
| 5   | 120      | 7   | 112 | 6.93      | 6.91       | 0.02   |
| 10  | 3628800  | 22  | 7129216 | 21.80     | 21.79      | 0.01   |

**观察**：随着 $n$ 增大，冗余度趋近于 0，编码效率接近 100%！

---

## 安全性分析

### 信息论安全

#### 假设

- 攻击者观察到哈希序列 $H'$
- 攻击者不知道密钥 $k$

#### 分析

1. **PRF 的伪随机性**：

攻击者无法区分混淆值 $V_i$ 和真随机数：

$$
\Pr[\mathcal{A} \text{ distinguishes PRF from random}] \leq \text{negl}(\lambda)
$$

2. **排列的均匀分布**：

在攻击者视角，所有 $n!$ 种排列等概率：

$$
\Pr[\pi_{\text{final}} = \sigma | H'] = \frac{1}{n!}, \quad \forall \sigma \in S_n
$$

3. **比特的语义安全**：

解码比特 $B$ 的后验分布等于先验分布：

$$
\Pr[B = b | H'] = \Pr[B = b] = \frac{1}{2^{|B|}}
$$

**结论**：在计算假设下（HMAC-SHA256 的安全性），ORIM 系统提供语义级安全。

### 隐蔽性

#### 统计检验

对于随机密钥 $k$ 和随机比特流 $B$，生成的哈希序列 $H'$ 在统计上与随机排列无法区分：

$$
\text{KL}(P_{H'} \| P_{\text{uniform}}) = 0
$$

#### 熵分析

系统的信息熵：

$$
H(H' | H) = \log_2(n!) \approx n \log_2 n - 1.44n \quad \text{bits}
$$

这意味着每次传输可以隐蔽地传输约 $n \log_2 n$ 比特信息。

---

## 总结

ORIM 编码系统巧妙地将三个数学工具结合：

1. **PRF**：建立密钥依赖的自然顺序
2. **Lehmer 码**：双射映射排列 ↔ 整数
3. **完全二叉树编码**：变长编码接近理论最优

整个流程可以用以下映射链表示：

$$
\text{Bits} \xrightarrow{\text{CBT}} \text{Rank} \xrightarrow{\text{Lehmer}} \text{Permutation} \xrightarrow{\text{PRF}} \text{Hash Order}
$$

**关键优势**：
- ✅ **高效**：编码效率接近 100%（冗余度 < 2 bits）
- ✅ **安全**：基于 HMAC-SHA256 的语义安全
- ✅ **隐蔽**：生成的顺序统计上不可区分
- ✅ **灵活**：变长编码自适应不同的排列数量

**应用场景**：
- 比特币隐蔽信道
- 网络流量水印
- 数字隐写术
- 抗审查通信

---

## 参考文献

1. Lehmer, D. H. (1960). "Teaching combinatorial tricks to a computer". *Proceedings of Symposia in Applied Mathematics*, 10, 179-193.

2. Knuth, D. E. (1997). *The Art of Computer Programming, Volume 2: Seminumerical Algorithms* (3rd ed.). Addison-Wesley.

3. Cover, T. M., & Thomas, J. A. (2006). *Elements of Information Theory* (2nd ed.). Wiley-Interscience.

4. Cachin, C. (2004). "An information-theoretic model for steganography". *Information and Computation*, 192(1), 41-56.

5. NIST (2008). "The Keyed-Hash Message Authentication Code (HMAC)". *FIPS PUB 198-1*.

---

**Document Version**: 1.0  
**Last Updated**: 2026-01-02  
**Author**: ORIM Development Team
