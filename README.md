## 目录

- `deai/`：链下规则。锁仓通行证、加权轮询、声誉、抽矿工、贡献分成、模型二分，以及欺诈结果写回调度。
- `chain/`：Hardhat 合约 `StakingContract`，提供锁仓、通行证、`weightOf` 和 `creditReward`。
- `coord/`：用 Go 写的进程内 PBFT。一次提交对应一个完整任务周期（下单、分配、确认、评价）。
- `scripts/`：画图和端到端实验。
- `tests/`：协议规则的单元测试。
- `figures/`、`tables/`：已经跑出来的图和表。

代码注释里的公式编号沿用 Li 等原文：加权轮询是 1，声誉是 2，贡献是 3，奖励是 4，按声誉抽矿工是 5。报告正文按公式出现的顺序重新编了号，所以报告里的式 (3)(4)(5) 分别对应这里的抽矿工、贡献和奖励。

## 一笔交易完成逻辑

1. 客户锁仓后才有免付费通行证。有效质押是本币加上 0.1 倍的其他资产。
2. 积压请求按锁仓权重排队。100、300、600 对应权重 1:3:6。
3. 协调者按声誉做加权随机，客户在订单里指定的矿工会被丢掉。随机数是 `SHA-256(seed || index)`，不是 Chainlink VRF。
4. 客户评分只有最新的一条进入声誉。和多数意见不一致的差评不写入，客户会被指数封禁。
5. 若对输出有争议，`ProtocolEngine.challenge` 在 12 层链上做二分。矿工在 `faulty_miners` 里时，输出从 L7 开始分叉。
6. `proof_feedback=True` 时，成立的欺诈会记成客观 BAD，该矿工在一段指数窗口内不再被抽到，这一周期也不计入贡献和奖励。
7. 成交记录交给 PBFT。0% 丢包时诚实节点账本一致；实现里没有 view-change，5% 及以上丢包时账本会分叉。

## 环境

- Python 3.12，依赖见 `requirements.txt`
- Node.js，在 `chain/` 里执行 `npm install`
- Go 1.21 以上

## 运行

```text
pip install -r requirements.txt
python -m pytest

python scripts/plot_figures.py
python scripts/plot_proof_feedback.py
python scripts/plot_fig34_en.py

cd coord
go test ./...
go run . -experiment

cd chain
npm test
```

端到端需要先能启动本机 Hardhat（8545 端口）：

```text
python scripts/e2e.py
```

它会锁仓 100/300/600，处理 1000 笔请求，再把成交周期交给 50 个协调者。

## 图和表

| 文件 | 内容 |
| --- | --- |
| `figures/fig1_wrr_convergence.png` | 服务份额趋向 0.1 / 0.3 / 0.6 |
| `figures/fig2_avrf_hist.png` | 抽矿工频率和声誉权重 |
| `figures/fig3_attacks.png` | 无通行证、指定矿工、恶意差评 |
| `figures/fig3_4_bisection.png` | 12 层链上 4 轮定位 L7 |
| `figures/fig13_proof_feedback.png` | 客户一律好评时，写回前后作弊矿工的份额 |
| `figures/fig8_e2e_trace.png` | 1000 笔请求的拒绝、成交和上链奖励 |
| `figures/fig6_tps_vs_loss.png` | 丢包后提交还在，诚实账本不再一致 |
| `tables/e2e_summary.json` | 端到端计数。0% 丢包时 922 笔一致 |
| `tables/proof_feedback.csv` | 写回对照的抽中次数和声誉 |
| `tables/pbft_results.csv` | 不同节点数和丢包率下的账本结果 |

`fig5`、`fig7` 是进程内吞吐，只作本地参考，不拿来和论文里的 1000 TPS 比较。
